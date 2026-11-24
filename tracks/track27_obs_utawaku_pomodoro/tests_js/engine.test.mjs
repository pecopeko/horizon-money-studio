import test from "node:test";
import assert from "node:assert/strict";
import Engine from "../src/engine.js";

test("Edition rules & 6 designer themes are properly defined", () => {
  assert.equal(Engine.BROADCAST_CHANNEL_NAME, "peco_obs_utawaku_v1");
  assert.equal(Engine.STORAGE_KEY, "peco_obs_utawaku_state_v1");

  const themeIds = Object.keys(Engine.THEMES);
  assert.deepEqual(themeIds, [
    "dark_frost",
    "sakura_macaron",
    "cyber_neon",
    "starlight_navy",
    "latte_cafe",
    "pixel_retro",
  ]);

  const lite = Engine.getEditionRules("lite");
  const pro = Engine.getEditionRules("pro");
  assert.equal(lite.maxSongs, 5);
  assert.deepEqual(lite.allowedThemes, ["dark_frost"]);
  assert.equal(lite.allowTimestamps, false);
  assert.equal(pro.maxSongs, 500);
  assert.equal(pro.allowedThemes.length, 6);
  assert.equal(pro.allowTimestamps, true);
});

test("Lite vs Pro song cap & bulk text parser", () => {
  const liteState = Engine.createDefaultState("lite");
  assert.equal(liteState.setlist.songs.length, 5);

  const blockedAdd = Engine.addSong(
    liteState,
    { title: "6曲目テスト", artist: "Artist" },
    "lite"
  );
  assert.ok(blockedAdd.error);
  assert.equal(blockedAdd.state.setlist.songs.length, 5);

  const blockedBulk = Engine.bulkImportSongs(
    liteState,
    "新時代 / Ado\n唱 / Ado",
    { replace: true },
    "lite"
  );
  assert.ok(blockedBulk.error);

  // Pro allows unlimited songs & multi-format bulk paste
  const proState = Engine.createDefaultState("pro");
  const bulkText = [
    "01. アイドル / YOASOBI",
    "2) 怪獣の花唄 - Vaundy",
    "③ 残酷な天使のテーゼ（高橋洋子）",
    "♪ 群青 ／ YOASOBI",
    "0:12:34 星街すいせい | Stellar Stellar",
    "オリジナルアカペラ",
  ].join("\n");

  const parsed = Engine.parseBulkSetlistText(bulkText);
  assert.equal(parsed.length, 6);
  assert.deepEqual(parsed[0], { title: "アイドル", artist: "YOASOBI" });
  assert.deepEqual(parsed[1], { title: "怪獣の花唄", artist: "Vaundy" });
  assert.deepEqual(parsed[2], { title: "残酷な天使のテーゼ", artist: "高橋洋子" });
  assert.deepEqual(parsed[3], { title: "群青", artist: "YOASOBI" });
  assert.deepEqual(parsed[4], { title: "星街すいせい", artist: "Stellar Stellar" });
  assert.deepEqual(parsed[5], { title: "オリジナルアカペラ", artist: "" });

  const imported = Engine.bulkImportSongs(proState, bulkText, { replace: true }, "pro");
  assert.equal(imported.error, null);
  assert.equal(imported.addedCount, 6);
  assert.equal(imported.state.setlist.songs.length, 6);
});

test("Stream timer, advanceToNextSong & YouTube timestamp generation with offset adjustment", () => {
  let state = Engine.createDefaultState("pro");
  state = Engine.resetStreamTimer(state);
  state = Engine.resetSetlistProgress(state);

  const t0 = 1_700_000_000_000;
  state = Engine.startStreamTimer(state, t0);

  // Start song 1 at 0:05:12 (312 sec)
  const firstSongId = state.setlist.songs[0].id;
  state = Engine.startSongById(state, firstSongId, t0 + 312_000);
  assert.equal(state.setlist.songs[0].status, "current");
  assert.equal(state.setlist.songs[0].startedAtSec, 312);

  // Advance to song 2 at 0:09:48 (588 sec)
  state = Engine.advanceToNextSong(state, t0 + 588_000);
  assert.equal(state.setlist.songs[0].status, "sung");
  assert.equal(state.setlist.songs[1].status, "current");
  assert.equal(state.setlist.songs[1].startedAtSec, 588);

  // Advance to song 3 at 1:02:05 (3725 sec)
  state = Engine.advanceToNextSong(state, t0 + 3_725_000);
  assert.equal(state.setlist.songs[1].status, "sung");
  assert.equal(state.setlist.songs[2].status, "current");
  assert.equal(state.setlist.songs[2].startedAtSec, 3725);

  const output = Engine.generateYoutubeTimestampList(state);
  assert.ok(output.includes("0:00:00 配信開始 / OP"));
  assert.ok(output.includes("0:05:12 アイドル / YOASOBI"));
  assert.ok(output.includes("0:09:48 怪獣の花唄 / Vaundy"));
  assert.ok(output.includes("1:02:05 残酷な天使のテーゼ / 高橋洋子"));

  // Apply -12 sec offset adjustment (e.g. OBS stream started 12s after timer click)
  const adjusted = Engine.adjustStreamOffset(state, -12, "pro");
  assert.equal(adjusted.error, null);
  const adjustedText = Engine.generateYoutubeTimestampList(adjusted.state);
  assert.ok(adjustedText.includes("0:05:00 アイドル / YOASOBI"));
  assert.ok(adjustedText.includes("0:09:36 怪獣の花唄 / Vaundy"));
  assert.ok(adjustedText.includes("1:01:53 残酷な天使のテーゼ / 高橋洋子"));
});

test("Pomodoro state machine: custom durations, sets, long break, and todos", () => {
  let state = Engine.createDefaultState("pro");

  // Configure 50m work / 10m break / 20m long break every 2 sets
  const cfg = Engine.configurePomodoro(
    state,
    {
      workMinutes: 50,
      breakMinutes: 10,
      longBreakMinutes: 20,
      cyclesBeforeLongBreak: 2,
      chimePreset: "lofi_rhodes",
    },
    "pro"
  );
  assert.equal(cfg.error, null);
  state = cfg.state;
  assert.equal(state.pomodoro.remainingSec, 50 * 60);

  const t0 = 1_700_000_000_000;
  state = Engine.startPomodoro(state, t0);
  assert.equal(Engine.getPomodoroRemainingSec(state, t0 + 60_000), 49 * 60);

  // Finish Set 1 Work -> Short Break (10m)
  let tick = Engine.tickPomodoro(state, t0 + 50 * 60 * 1000);
  assert.equal(tick.phaseChanged, true);
  assert.equal(tick.newPhase, "break");
  state = tick.state;
  assert.equal(state.pomodoro.completedSetsToday, 1);
  assert.equal(state.pomodoro.remainingSec, 10 * 60);

  // Finish Set 1 Break -> Set 2 Work (50m)
  const t1 = t0 + 50 * 60 * 1000;
  tick = Engine.tickPomodoro(state, t1 + 10 * 60 * 1000);
  assert.equal(tick.phaseChanged, true);
  assert.equal(tick.newPhase, "work");
  state = tick.state;
  assert.equal(state.pomodoro.currentSet, 2);

  // Finish Set 2 Work -> Long Break (20m)
  const t2 = t1 + 10 * 60 * 1000;
  tick = Engine.tickPomodoro(state, t2 + 50 * 60 * 1000);
  assert.equal(tick.phaseChanged, true);
  assert.equal(tick.newPhase, "long_break");
  state = tick.state;
  assert.equal(state.pomodoro.completedSetsToday, 2);
  assert.equal(state.pomodoro.remainingSec, 20 * 60);

  // Todo checklist operations
  state = Engine.addTodo(state, "新曲ハモリ練習");
  const added = state.pomodoro.todos.at(-1);
  assert.equal(added.text, "新曲ハモリ練習");
  assert.equal(added.done, false);
  state = Engine.toggleTodo(state, added.id);
  assert.equal(state.pomodoro.todos.at(-1).done, true);
  state = Engine.removeTodo(state, added.id);
  assert.equal(state.pomodoro.todos.some((t) => t.id === added.id), false);
});

test("Theme switching, custom accent/opacity gating & JSON preset export/import", () => {
  const liteState = Engine.createDefaultState("lite");
  const blockedTheme = Engine.setTheme(liteState, "cyber_neon", "lite");
  assert.ok(blockedTheme.error);
  assert.equal(blockedTheme.state.theme.themeId, "dark_frost");

  let proState = Engine.createDefaultState("pro");
  const neonRes = Engine.setTheme(proState, "cyber_neon", "pro");
  assert.equal(neonRes.error, null);
  proState = neonRes.state;

  const customRes = Engine.setCustomThemeOptions(
    proState,
    { customAccent: "#ff55aa", opacity: 0.72 },
    "pro"
  );
  assert.equal(customRes.error, null);
  proState = customRes.state;

  const resolved = Engine.resolveEffectiveTheme(proState);
  assert.equal(resolved.id, "cyber_neon");
  assert.equal(resolved.accent, "#FF55AA");
  assert.equal(resolved.opacity, 0.72);

  const exported = Engine.exportPresetJson(proState, "pro");
  assert.equal(exported.error, null);
  const imported = Engine.importPresetJson(exported.json, "pro");
  assert.equal(imported.error, null);
  assert.equal(imported.state.theme.themeId, "cyber_neon");
  assert.equal(imported.state.theme.customAccent, "#FF55AA");
});

test("Dual BroadcastChannel + localStorage SyncBridge delivers instant cross-view updates", () => {
  const sharedMemory = new Map();
  const storageListeners = new Set();
  const bcPeers = new Set();

  const fakeStorage = {
    getItem: (k) => (sharedMemory.has(k) ? sharedMemory.get(k) : null),
    setItem: (k, v) => {
      sharedMemory.set(k, v);
      for (const fn of storageListeners) {
        fn({ key: k, newValue: v });
      }
    },
  };

  class FakeBroadcastChannel {
    constructor(name) {
      this.name = name;
      this.onmessage = null;
      bcPeers.add(this);
    }
    postMessage(data) {
      for (const peer of bcPeers) {
        if (peer !== this && peer.name === this.name && typeof peer.onmessage === "function") {
          peer.onmessage({ data });
        }
      }
    }
    close() {
      bcPeers.delete(this);
    }
  }

  const makeFakeWindow = () => ({
    addEventListener: (type, fn) => {
      if (type === "storage") storageListeners.add(fn);
    },
    removeEventListener: (type, fn) => {
      if (type === "storage") storageListeners.delete(fn);
    },
  });

  let overlayReceived = null;
  const dockBridge = Engine.createSyncBridge({
    edition: "pro",
    storage: fakeStorage,
    BroadcastChannelImpl: FakeBroadcastChannel,
    windowObj: makeFakeWindow(),
  });
  const overlayBridge = Engine.createSyncBridge({
    edition: "pro",
    storage: fakeStorage,
    BroadcastChannelImpl: FakeBroadcastChannel,
    windowObj: makeFakeWindow(),
    onStateReceived: (st) => {
      overlayReceived = st;
    },
  });

  let dockState = dockBridge.loadInitialState();
  dockState = Engine.setTheme(dockState, "sakura_macaron", "pro").state;
  dockState = Engine.advanceToNextSong(dockState, Date.now());
  dockBridge.publishState(dockState);

  assert.ok(overlayReceived);
  assert.equal(overlayReceived.theme.themeId, "sakura_macaron");
  assert.equal(overlayReceived.setlist.songs[1].status, "current");

  dockBridge.destroy();
  overlayBridge.destroy();
});
