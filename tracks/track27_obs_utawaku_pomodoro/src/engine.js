/**
 * OBS Utawaku Setlist, YouTube Timestamp & Pomodoro All-in-One Engine
 * Crafted by peco (https://pecopeko1011.booth.pm/)
 * Zero external dependencies · 100% Browser-Local (BroadcastChannel + localStorage)
 */

const PecoObsEngine = (() => {
  const BROADCAST_CHANNEL_NAME = "peco_obs_utawaku_v1";
  const STORAGE_KEY = "peco_obs_utawaku_state_v1";
  const SCHEMA_VERSION = 1;

  const EDITIONS = {
    lite: {
      id: "lite",
      label: "Lite (¥0 無料体験版)",
      maxSongs: 5,
      allowedThemes: ["dark_frost"],
      allowCustomTheme: false,
      allowBulkPaste: false,
      allowTimestamps: false,
      allowCustomPomodoro: false,
      allowJsonPresets: false,
    },
    pro: {
      id: "pro",
      label: "Pro フルパック",
      maxSongs: 500,
      allowedThemes: [
        "dark_frost",
        "sakura_macaron",
        "cyber_neon",
        "starlight_navy",
        "latte_cafe",
        "pixel_retro",
      ],
      allowCustomTheme: true,
      allowBulkPaste: true,
      allowTimestamps: true,
      allowCustomPomodoro: true,
      allowJsonPresets: true,
    },
  };

  const THEMES = {
    dark_frost: {
      id: "dark_frost",
      name: "Dark Frost",
      jpName: "すりガラス黒",
      bgRgb: "15, 22, 36",
      bgAltRgb: "23, 33, 52",
      defaultOpacity: 0.86,
      borderColor: "rgba(148, 163, 184, 0.28)",
      textPrimary: "#F8FAFC",
      textSecondary: "#CBD5E1",
      textMuted: "#94A3B8",
      accent: "#38BDF8",
      accent2: "#818CF8",
      badgeText: "#082F49",
      radiusPx: 18,
      isLight: false,
      pixelBorder: false,
    },
    sakura_macaron: {
      id: "sakura_macaron",
      name: "Sakura Macaron",
      jpName: "ゆめかわピンク",
      bgRgb: "255, 245, 249",
      bgAltRgb: "253, 232, 241",
      defaultOpacity: 0.92,
      borderColor: "rgba(236, 72, 153, 0.36)",
      textPrimary: "#4A1D34",
      textSecondary: "#703252",
      textMuted: "#9D5C7D",
      accent: "#EC4899",
      accent2: "#F472B6",
      badgeText: "#FFFFFF",
      radiusPx: 24,
      isLight: true,
      pixelBorder: false,
    },
    cyber_neon: {
      id: "cyber_neon",
      name: "Cyber Neon",
      jpName: "ネオンシアン×マゼンタ",
      bgRgb: "9, 11, 24",
      bgAltRgb: "16, 20, 42",
      defaultOpacity: 0.9,
      borderColor: "rgba(0, 240, 255, 0.58)",
      textPrimary: "#ECFEFF",
      textSecondary: "#A5F3FC",
      textMuted: "#67E8F9",
      accent: "#00F0FF",
      accent2: "#FF2A85",
      badgeText: "#041E24",
      radiusPx: 6,
      isLight: false,
      pixelBorder: false,
    },
    starlight_navy: {
      id: "starlight_navy",
      name: "Starlight Navy",
      jpName: "夜空ゴールド",
      bgRgb: "12, 20, 44",
      bgAltRgb: "20, 32, 68",
      defaultOpacity: 0.88,
      borderColor: "rgba(245, 196, 81, 0.45)",
      textPrimary: "#FEFCE8",
      textSecondary: "#E2E8F0",
      textMuted: "#94A3B8",
      accent: "#F5C451",
      accent2: "#FDE047",
      badgeText: "#2A1B02",
      radiusPx: 16,
      isLight: false,
      pixelBorder: false,
    },
    latte_cafe: {
      id: "latte_cafe",
      name: "Latte Cafe",
      jpName: "カフェベージュ",
      bgRgb: "250, 243, 234",
      bgAltRgb: "241, 229, 214",
      defaultOpacity: 0.93,
      borderColor: "rgba(166, 118, 76, 0.38)",
      textPrimary: "#3B2818",
      textSecondary: "#5E432C",
      textMuted: "#8B6B4F",
      accent: "#B4693E",
      accent2: "#D9915B",
      badgeText: "#FFFFFF",
      radiusPx: 20,
      isLight: true,
      pixelBorder: false,
    },
    pixel_retro: {
      id: "pixel_retro",
      name: "Pixel Retro",
      jpName: "レトロドット風",
      bgRgb: "20, 18, 31",
      bgAltRgb: "32, 28, 48",
      defaultOpacity: 0.94,
      borderColor: "rgba(52, 211, 153, 0.88)",
      textPrimary: "#ECFDF5",
      textSecondary: "#A7F3D0",
      textMuted: "#6EE7B7",
      accent: "#34D399",
      accent2: "#FBBF24",
      badgeText: "#052E16",
      radiusPx: 0,
      isLight: false,
      pixelBorder: true,
    },
  };

  const CHIME_PRESETS = {
    crystal_bell: {
      id: "crystal_bell",
      name: "Crystal Bell",
      jpName: "クリスタルベル",
    },
    lofi_rhodes: {
      id: "lofi_rhodes",
      name: "Lo-Fi Rhodes",
      jpName: "チル作業エレピ",
    },
    retro_8bit: {
      id: "retro_8bit",
      name: "8-Bit Chime",
      jpName: "レトロピコピコ音",
    },
  };

  const VALID_MODES = ["utawaku", "pomodoro", "clock", "all_in_one"];
  const VALID_SUB_MODES = ["utawaku", "pomodoro"];
  const VALID_POSITIONS = ["left", "right", "compact"];

  let _idSeq = 1;
  function makeId(prefix = "item") {
    _idSeq += 1;
    const rand = Math.random().toString(36).slice(2, 7);
    return `${prefix}_${Date.now().toString(36)}_${_idSeq}_${rand}`;
  }

  function cloneState(state) {
    return JSON.parse(JSON.stringify(state));
  }

  function clampNumber(val, min, max, fallback) {
    const num = Number(val);
    if (!Number.isFinite(num)) return fallback;
    return Math.min(max, Math.max(min, num));
  }

  function sanitizeHexColor(hex, fallback = "") {
    if (typeof hex !== "string") return fallback;
    const trimmed = hex.trim();
    if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) {
      return trimmed.toUpperCase();
    }
    return fallback;
  }

  function sanitizeText(str, maxLen = 160) {
    if (typeof str !== "string") return "";
    return str.replace(/[\u0000-\u001F\u007F]/g, "").trim().slice(0, maxLen);
  }

  function getEditionRules(edition = "lite") {
    return EDITIONS[edition === "pro" ? "pro" : "lite"];
  }

  function createDefaultSongs() {
    return [
      {
        id: "song_default_1",
        title: "アイドル",
        artist: "YOASOBI",
        status: "current",
        startedAtSec: 312,
        note: "",
      },
      {
        id: "song_default_2",
        title: "怪獣の花唄",
        artist: "Vaundy",
        status: "queued",
        startedAtSec: null,
        note: "",
      },
      {
        id: "song_default_3",
        title: "残酷な天使のテーゼ",
        artist: "高橋洋子",
        status: "queued",
        startedAtSec: null,
        note: "",
      },
      {
        id: "song_default_4",
        title: "群青",
        artist: "YOASOBI",
        status: "queued",
        startedAtSec: null,
        note: "",
      },
      {
        id: "song_default_5",
        title: "ファンサ",
        artist: "mona (CV:夏川椎菜)",
        status: "queued",
        startedAtSec: null,
        note: "",
      },
    ];
  }

  function createDefaultTodos() {
    return [
      { id: "todo_default_1", text: "発声＆マイク音量バランス確認", done: true },
      { id: "todo_default_2", text: "歌枠サムネイル・待機画面セット", done: false },
      { id: "todo_default_3", text: "タイムスタンプ概要欄コピペ", done: false },
    ];
  }

  function createDefaultState(edition = "lite") {
    const rules = getEditionRules(edition);
    return {
      schemaVersion: SCHEMA_VERSION,
      edition: rules.id,
      updatedAt: 1,
      activeMode: "utawaku", // 'utawaku' | 'pomodoro' | 'clock' | 'all_in_one'
      allInOnePrimary: "utawaku", // 'utawaku' | 'pomodoro' when activeMode === 'all_in_one'
      overlayPosition: "left", // 'left' | 'right' | 'compact'
      showMiniClockInCorner: true,
      theme: {
        themeId: "dark_frost",
        customAccent: "",
        opacity: THEMES.dark_frost.defaultOpacity,
      },
      setlist: {
        streamTitle: "🎤 歌枠 SINGING STREAM",
        songs: createDefaultSongs(),
        showSungHistory: true,
        includeOpeningZero: true,
        openingLabel: "配信開始 / OP",
      },
      streamTimer: {
        isRunning: false,
        startedEpochMs: null,
        accumulatedSec: 312, // 0:05:12 demo default so preview shows realistic timestamp immediately
        offsetSec: 0,
      },
      pomodoro: {
        phase: "work", // 'work' | 'break' | 'long_break'
        isRunning: false,
        remainingSec: 25 * 60,
        endEpochMs: null,
        workMinutes: 25,
        breakMinutes: 5,
        longBreakMinutes: 15,
        currentSet: 1,
        cyclesBeforeLongBreak: 4,
        completedSetsToday: 0,
        autoStartNext: true,
        chimePreset: "crystal_bell",
        chimeVolume: 0.65,
        chimeMuted: false,
        todos: createDefaultTodos(),
      },
      clock: {
        hashtag: "#歌枠 #VTuber",
        marqueeText: "初見さん大歓迎！リクエスト＆コメントお気軽にどうぞ♪ 高評価・チャンネル登録よろしくね✨",
        showSeconds: false,
        use24Hour: true,
      },
    };
  }

  function sanitizeStateForEdition(rawState, edition = "lite") {
    const rules = getEditionRules(edition);
    const fallback = createDefaultState(rules.id);
    if (!rawState || typeof rawState !== "object") {
      return fallback;
    }

    const next = cloneState(fallback);
    next.edition = rules.id;
    next.updatedAt = Number.isFinite(Number(rawState.updatedAt))
      ? Number(rawState.updatedAt)
      : fallback.updatedAt;

    if (VALID_MODES.includes(rawState.activeMode)) {
      next.activeMode = rawState.activeMode;
    }
    if (VALID_SUB_MODES.includes(rawState.allInOnePrimary)) {
      next.allInOnePrimary = rawState.allInOnePrimary;
    }
    if (VALID_POSITIONS.includes(rawState.overlayPosition)) {
      next.overlayPosition = rawState.overlayPosition;
    }
    if (typeof rawState.showMiniClockInCorner === "boolean") {
      next.showMiniClockInCorner = rawState.showMiniClockInCorner;
    }

    // Theme gating
    const rawTheme = rawState.theme || {};
    const requestedThemeId = typeof rawTheme.themeId === "string" ? rawTheme.themeId : "dark_frost";
    next.theme.themeId = rules.allowedThemes.includes(requestedThemeId)
      ? requestedThemeId
      : "dark_frost";
    const themeObj = THEMES[next.theme.themeId] || THEMES.dark_frost;
    next.theme.customAccent = rules.allowCustomTheme
      ? sanitizeHexColor(rawTheme.customAccent, "")
      : "";
    next.theme.opacity = rules.allowCustomTheme
      ? clampNumber(rawTheme.opacity, 0.2, 1.0, themeObj.defaultOpacity)
      : themeObj.defaultOpacity;

    // Setlist gating
    const rawSetlist = rawState.setlist || {};
    if (typeof rawSetlist.streamTitle === "string") {
      next.setlist.streamTitle = sanitizeText(rawSetlist.streamTitle, 60) || fallback.setlist.streamTitle;
    }
    if (typeof rawSetlist.showSungHistory === "boolean") {
      next.setlist.showSungHistory = rawSetlist.showSungHistory;
    }
    if (typeof rawSetlist.includeOpeningZero === "boolean") {
      next.setlist.includeOpeningZero = rawSetlist.includeOpeningZero;
    }
    if (typeof rawSetlist.openingLabel === "string") {
      next.setlist.openingLabel = sanitizeText(rawSetlist.openingLabel, 50) || "配信開始 / OP";
    }
    if (Array.isArray(rawSetlist.songs)) {
      let currentFound = false;
      next.setlist.songs = rawSetlist.songs
        .slice(0, rules.maxSongs)
        .map((song, idx) => {
          const title = sanitizeText(song && song.title, 100);
          if (!title) return null;
          let status = ["queued", "current", "sung"].includes(song.status)
            ? song.status
            : "queued";
          if (status === "current") {
            if (currentFound) {
              status = "queued";
            } else {
              currentFound = true;
            }
          }
          const startedAtSec =
            song && song.startedAtSec !== null && song.startedAtSec !== undefined && Number.isFinite(Number(song.startedAtSec))
              ? Math.max(0, Math.floor(Number(song.startedAtSec)))
              : null;
          return {
            id: sanitizeText(song.id, 64) || `song_${idx + 1}`,
            title,
            artist: sanitizeText(song && song.artist, 80),
            status,
            startedAtSec,
            note: sanitizeText(song && song.note, 80),
          };
        })
        .filter(Boolean);
    }

    // Stream Timer
    const rawTimer = rawState.streamTimer || {};
    next.streamTimer.isRunning = Boolean(rawTimer.isRunning);
    next.streamTimer.startedEpochMs =
      next.streamTimer.isRunning && Number.isFinite(Number(rawTimer.startedEpochMs))
        ? Number(rawTimer.startedEpochMs)
        : null;
    if (!next.streamTimer.isRunning) {
      next.streamTimer.startedEpochMs = null;
    }
    next.streamTimer.accumulatedSec = clampNumber(rawTimer.accumulatedSec, 0, 86400 * 3, 0);
    next.streamTimer.offsetSec = rules.allowTimestamps
      ? Math.round(clampNumber(rawTimer.offsetSec, -3600, 3600, 0))
      : 0;

    // Pomodoro gating
    const rawPomo = rawState.pomodoro || {};
    next.pomodoro.phase = ["work", "break", "long_break"].includes(rawPomo.phase)
      ? rawPomo.phase
      : "work";
    next.pomodoro.workMinutes = rules.allowCustomPomodoro
      ? Math.round(clampNumber(rawPomo.workMinutes, 1, 180, 25))
      : 25;
    next.pomodoro.breakMinutes = rules.allowCustomPomodoro
      ? Math.round(clampNumber(rawPomo.breakMinutes, 1, 90, 5))
      : 5;
    next.pomodoro.longBreakMinutes = rules.allowCustomPomodoro
      ? Math.round(clampNumber(rawPomo.longBreakMinutes, 1, 120, 15))
      : 15;
    next.pomodoro.cyclesBeforeLongBreak = rules.allowCustomPomodoro
      ? Math.round(clampNumber(rawPomo.cyclesBeforeLongBreak, 2, 12, 4))
      : 4;
    next.pomodoro.currentSet = Math.round(
      clampNumber(rawPomo.currentSet, 1, next.pomodoro.cyclesBeforeLongBreak, 1)
    );
    next.pomodoro.completedSetsToday = Math.round(
      clampNumber(rawPomo.completedSetsToday, 0, 999, 0)
    );
    next.pomodoro.autoStartNext =
      typeof rawPomo.autoStartNext === "boolean" ? rawPomo.autoStartNext : true;
    next.pomodoro.chimePreset =
      rules.allowCustomPomodoro && CHIME_PRESETS[rawPomo.chimePreset]
        ? rawPomo.chimePreset
        : "crystal_bell";
    next.pomodoro.chimeVolume = clampNumber(rawPomo.chimeVolume, 0, 1, 0.65);
    next.pomodoro.chimeMuted = Boolean(rawPomo.chimeMuted);

    const phaseDurationSec = getPhaseDurationSeconds(next.pomodoro, next.pomodoro.phase);
    next.pomodoro.isRunning = Boolean(rawPomo.isRunning);
    next.pomodoro.remainingSec = Math.round(
      clampNumber(rawPomo.remainingSec, 0, 180 * 60, phaseDurationSec)
    );
    next.pomodoro.endEpochMs =
      next.pomodoro.isRunning && Number.isFinite(Number(rawPomo.endEpochMs))
        ? Number(rawPomo.endEpochMs)
        : null;
    if (!next.pomodoro.isRunning) {
      next.pomodoro.endEpochMs = null;
    }

    if (Array.isArray(rawPomo.todos)) {
      next.pomodoro.todos = rawPomo.todos
        .slice(0, 30)
        .map((todo, idx) => {
          const text = sanitizeText(todo && todo.text, 100);
          if (!text) return null;
          return {
            id: sanitizeText(todo.id, 64) || `todo_${idx + 1}`,
            text,
            done: Boolean(todo.done),
          };
        })
        .filter(Boolean);
    }

    // Clock
    const rawClock = rawState.clock || {};
    if (typeof rawClock.hashtag === "string") {
      next.clock.hashtag = sanitizeText(rawClock.hashtag, 60);
    }
    if (typeof rawClock.marqueeText === "string") {
      next.clock.marqueeText = sanitizeText(rawClock.marqueeText, 240);
    }
    if (typeof rawClock.showSeconds === "boolean") {
      next.clock.showSeconds = rawClock.showSeconds;
    }
    if (typeof rawClock.use24Hour === "boolean") {
      next.clock.use24Hour = rawClock.use24Hour;
    }

    return next;
  }

  function bumpRevision(state) {
    state.updatedAt = Math.max((state.updatedAt || 0) + 1, Date.now());
    return state;
  }

  // -------------------------------------------------------------------------
  // Formatting & Stream Timer / Timestamp Logic
  // -------------------------------------------------------------------------
  function formatHms(totalSec) {
    const clamped = Math.max(0, Math.floor(Number(totalSec) || 0));
    const hours = Math.floor(clamped / 3600);
    const minutes = Math.floor((clamped % 3600) / 60);
    const seconds = clamped % 60;
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  function formatMmSs(totalSec) {
    const clamped = Math.max(0, Math.ceil(Number(totalSec) || 0));
    const minutes = Math.floor(clamped / 60);
    const seconds = clamped % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  function parseHmsInput(str) {
    if (typeof str !== "string") return null;
    const cleaned = str.trim();
    if (!cleaned) return null;
    const parts = cleaned.split(":").map((p) => p.trim());
    if (parts.some((p) => !/^\d+$/.test(p))) return null;
    if (parts.length === 3) {
      return Number(parts[0]) * 3600 + Number(parts[1]) * 60 + Number(parts[2]);
    }
    if (parts.length === 2) {
      return Number(parts[0]) * 60 + Number(parts[1]);
    }
    if (parts.length === 1) {
      return Number(parts[0]);
    }
    return null;
  }

  function getStreamElapsedSec(state, nowMs = Date.now()) {
    const timer = state.streamTimer || { isRunning: false, startedEpochMs: null, accumulatedSec: 0 };
    const base = Math.max(0, Math.floor(Number(timer.accumulatedSec) || 0));
    if (timer.isRunning && Number.isFinite(timer.startedEpochMs)) {
      const delta = Math.max(0, Math.floor((nowMs - timer.startedEpochMs) / 1000));
      return base + delta;
    }
    return base;
  }

  function startStreamTimer(state, nowMs = Date.now()) {
    const next = cloneState(state);
    if (!next.streamTimer.isRunning) {
      next.streamTimer.isRunning = true;
      next.streamTimer.startedEpochMs = nowMs;
      bumpRevision(next);
    }
    return next;
  }

  function pauseStreamTimer(state, nowMs = Date.now()) {
    const next = cloneState(state);
    if (next.streamTimer.isRunning) {
      next.streamTimer.accumulatedSec = getStreamElapsedSec(next, nowMs);
      next.streamTimer.isRunning = false;
      next.streamTimer.startedEpochMs = null;
      bumpRevision(next);
    }
    return next;
  }

  function resetStreamTimer(state) {
    const next = cloneState(state);
    next.streamTimer.isRunning = false;
    next.streamTimer.startedEpochMs = null;
    next.streamTimer.accumulatedSec = 0;
    next.streamTimer.offsetSec = 0;
    next.setlist.songs = next.setlist.songs.map((s) => ({
      ...s,
      startedAtSec: null,
    }));
    bumpRevision(next);
    return next;
  }

  function adjustStreamOffset(state, deltaSec, edition = state.edition) {
    const rules = getEditionRules(edition);
    if (!rules.allowTimestamps) {
      return {
        state: cloneState(state),
        error: "タイムスタンプ微調整はPro版の機能です。",
      };
    }
    const next = cloneState(state);
    next.streamTimer.offsetSec = Math.round(
      clampNumber((next.streamTimer.offsetSec || 0) + Number(deltaSec || 0), -3600, 3600, 0)
    );
    bumpRevision(next);
    return { state: next, error: null };
  }

  function setStreamOffset(state, offsetSec, edition = state.edition) {
    const rules = getEditionRules(edition);
    if (!rules.allowTimestamps) {
      return {
        state: cloneState(state),
        error: "タイムスタンプ微調整はPro版の機能です。",
      };
    }
    const next = cloneState(state);
    next.streamTimer.offsetSec = Math.round(clampNumber(offsetSec, -3600, 3600, 0));
    bumpRevision(next);
    return { state: next, error: null };
  }

  function generateYoutubeTimestampList(state, options = {}) {
    const includeHeader = options.includeHeader !== undefined ? options.includeHeader : true;
    const includeOpeningZero =
      options.includeOpeningZero !== undefined
        ? options.includeOpeningZero
        : Boolean(state.setlist && state.setlist.includeOpeningZero);
    const offsetSec = Number((state.streamTimer && state.streamTimer.offsetSec) || 0);
    const songs = (state.setlist && state.setlist.songs) || [];

    const stamped = songs
      .map((song, index) => ({ song, index }))
      .filter(({ song }) => song.startedAtSec !== null && song.startedAtSec !== undefined)
      .map(({ song, index }) => {
        const adjustedSec = Math.max(0, Math.floor(Number(song.startedAtSec) + offsetSec));
        const label = song.artist ? `${song.title} / ${song.artist}` : song.title;
        return {
          adjustedSec,
          index,
          line: `${formatHms(adjustedSec)} ${label}`,
        };
      })
      .sort((a, b) => (a.adjustedSec !== b.adjustedSec ? a.adjustedSec - b.adjustedSec : a.index - b.index));

    const lines = [];
    if (includeHeader) {
      lines.push("🎤 本日のセトリ / TIMESTAMPS");
    }
    if (includeOpeningZero) {
      const opLabel = (state.setlist && state.setlist.openingLabel) || "配信開始 / OP";
      const alreadyHasZero = stamped.some((item) => item.adjustedSec === 0);
      if (!alreadyHasZero) {
        lines.push(`0:00:00 ${opLabel}`);
      }
    }
    for (const item of stamped) {
      lines.push(item.line);
    }
    return lines.join("\n");
  }

  // -------------------------------------------------------------------------
  // Setlist Operations & Bulk Text Parser
  // -------------------------------------------------------------------------
  function parseSongLine(rawLine) {
    if (typeof rawLine !== "string") return null;
    let line = rawLine.trim();
    if (!line) return null;

    // Strip leading bullet or numbering e.g. "01. ", "1) ", "① ", "♪ ", "- "
    line = line
      .replace(/^(?:[#♪♫♬・\-*]+|\d{1,3}[.)．:：、]\s*|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]\s*)/u, "")
      .trim();
    if (!line) return null;

    // Strip leading timestamp if user pasted an existing timestamp line
    line = line.replace(/^\d{1,2}:\d{2}(?::\d{2})?\s+/, "").trim();
    if (!line) return null;

    // Match explicit separators: " / ", " ／ ", " - ", " ― ", " | ", " ｜ "
    const sepPatterns = [
      /\s*[\/／｜|]\s*/,
      /\s+[-ー―–—]\s+/,
    ];
    for (const regex of sepPatterns) {
      const idx = line.search(regex);
      if (idx > 0) {
        const match = line.match(regex);
        const title = sanitizeText(line.slice(0, idx), 100);
        const artist = sanitizeText(line.slice(idx + match[0].length), 80);
        if (title) {
          return { title, artist };
        }
      }
    }

    // Match trailing parentheses e.g. "怪獣の花唄（Vaundy）" or "怪獣の花唄 (Vaundy)"
    const parenMatch = line.match(/^(.+?)\s*[（(]([^（）()]+)[）)]\s*$/u);
    if (parenMatch) {
      const title = sanitizeText(parenMatch[1], 100);
      const artist = sanitizeText(parenMatch[2], 80);
      if (title) {
        return { title, artist };
      }
    }

    return { title: sanitizeText(line, 100), artist: "" };
  }

  function parseBulkSetlistText(rawText) {
    if (typeof rawText !== "string") return [];
    return rawText
      .split(/\r?\n/)
      .map(parseSongLine)
      .filter((item) => item && item.title);
  }

  function addSong(state, songInput, edition = state.edition) {
    const rules = getEditionRules(edition);
    const title = sanitizeText(songInput && songInput.title, 100);
    const artist = sanitizeText(songInput && songInput.artist, 80);
    const note = sanitizeText(songInput && songInput.note, 80);

    if (!title) {
      return { state: cloneState(state), error: "曲名を入力してください。" };
    }
    if (state.setlist.songs.length >= rules.maxSongs) {
      return {
        state: cloneState(state),
        error:
          rules.id === "lite"
            ? `無料体験版(Lite)は最大${rules.maxSongs}曲まで登録できます。Pro版は無制限＋一括貼付に対応しています！`
            : `最大${rules.maxSongs}曲に達しています。`,
      };
    }

    const next = cloneState(state);
    const hasCurrent = next.setlist.songs.some((s) => s.status === "current");
    next.setlist.songs.push({
      id: makeId("song"),
      title,
      artist,
      status: hasCurrent || next.setlist.songs.length > 0 ? "queued" : "current",
      startedAtSec: null,
      note,
    });
    bumpRevision(next);
    return { state: next, error: null };
  }

  function bulkImportSongs(state, rawText, options = {}, edition = state.edition) {
    const rules = getEditionRules(edition);
    if (!rules.allowBulkPaste) {
      return {
        state: cloneState(state),
        addedCount: 0,
        error: "テキスト一括貼付はPro版の限定機能です。",
      };
    }
    const parsed = parseBulkSetlistText(rawText);
    if (parsed.length === 0) {
      return {
        state: cloneState(state),
        addedCount: 0,
        error: "追加できる曲が見つかりませんでした（1行に1曲ずつ「曲名 / アーティスト」で入力してください）。",
      };
    }

    const next = cloneState(state);
    const baseSongs = options.replace ? [] : next.setlist.songs;
    const availableSlots = Math.max(0, rules.maxSongs - baseSongs.length);
    const sliced = parsed.slice(0, availableSlots).map((item, idx) => ({
      id: makeId(`bulk_${idx}`),
      title: item.title,
      artist: item.artist,
      status: "queued",
      startedAtSec: null,
      note: "",
    }));

    next.setlist.songs = [...baseSongs, ...sliced];
    bumpRevision(next);
    return { state: next, addedCount: sliced.length, error: null };
  }

  function startSongById(state, songId, nowMs = Date.now()) {
    const next = cloneState(state);
    const targetIdx = next.setlist.songs.findIndex((s) => s.id === songId);
    if (targetIdx === -1) return next;

    const elapsedSec = getStreamElapsedSec(next, nowMs);
    const shouldStamp = next.streamTimer.isRunning || elapsedSec > 0;

    next.setlist.songs = next.setlist.songs.map((song, idx) => {
      if (idx === targetIdx) {
        return {
          ...song,
          status: "current",
          startedAtSec: shouldStamp ? elapsedSec : song.startedAtSec,
        };
      }
      if (song.status === "current") {
        return {
          ...song,
          status: "sung",
        };
      }
      return song;
    });

    bumpRevision(next);
    return next;
  }

  function advanceToNextSong(state, nowMs = Date.now()) {
    const next = cloneState(state);
    const songs = next.setlist.songs;
    if (songs.length === 0) return next;

    const currentIdx = songs.findIndex((s) => s.status === "current");
    let nextQueuedIdx = -1;

    if (currentIdx >= 0) {
      // Look for first queued song after currentIdx, else any queued song
      for (let i = currentIdx + 1; i < songs.length; i += 1) {
        if (songs[i].status === "queued") {
          nextQueuedIdx = i;
          break;
        }
      }
    }
    if (nextQueuedIdx === -1) {
      nextQueuedIdx = songs.findIndex((s) => s.status === "queued");
    }

    const elapsedSec = getStreamElapsedSec(next, nowMs);
    const shouldStamp = next.streamTimer.isRunning || elapsedSec > 0;

    if (currentIdx >= 0) {
      songs[currentIdx] = { ...songs[currentIdx], status: "sung" };
    }
    if (nextQueuedIdx >= 0) {
      songs[nextQueuedIdx] = {
        ...songs[nextQueuedIdx],
        status: "current",
        startedAtSec: shouldStamp ? elapsedSec : songs[nextQueuedIdx].startedAtSec,
      };
    }

    bumpRevision(next);
    return next;
  }

  function rewindToPreviousSong(state) {
    const next = cloneState(state);
    const songs = next.setlist.songs;
    if (songs.length === 0) return next;

    const currentIdx = songs.findIndex((s) => s.status === "current");
    if (currentIdx > 0) {
      songs[currentIdx] = { ...songs[currentIdx], status: "queued" };
      songs[currentIdx - 1] = { ...songs[currentIdx - 1], status: "current" };
    } else if (currentIdx === -1) {
      // Find last sung song and restore to current
      for (let i = songs.length - 1; i >= 0; i -= 1) {
        if (songs[i].status === "sung") {
          songs[i] = { ...songs[i], status: "current" };
          break;
        }
      }
    }
    bumpRevision(next);
    return next;
  }

  function removeSong(state, songId) {
    const next = cloneState(state);
    next.setlist.songs = next.setlist.songs.filter((s) => s.id !== songId);
    bumpRevision(next);
    return next;
  }

  function moveSong(state, songId, direction) {
    const next = cloneState(state);
    const idx = next.setlist.songs.findIndex((s) => s.id === songId);
    if (idx === -1) return next;
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= next.setlist.songs.length) return next;
    const temp = next.setlist.songs[idx];
    next.setlist.songs[idx] = next.setlist.songs[swapIdx];
    next.setlist.songs[swapIdx] = temp;
    bumpRevision(next);
    return next;
  }

  function updateSongTimestamp(state, songId, timestampInput) {
    const next = cloneState(state);
    const sec =
      timestampInput === null || timestampInput === ""
        ? null
        : typeof timestampInput === "number"
        ? Math.max(0, Math.floor(timestampInput))
        : parseHmsInput(String(timestampInput));
    next.setlist.songs = next.setlist.songs.map((s) =>
      s.id === songId ? { ...s, startedAtSec: sec } : s
    );
    bumpRevision(next);
    return next;
  }

  function resetSetlistProgress(state) {
    const next = cloneState(state);
    next.setlist.songs = next.setlist.songs.map((s, idx) => ({
      ...s,
      status: idx === 0 ? "current" : "queued",
      startedAtSec: null,
    }));
    bumpRevision(next);
    return next;
  }

  function getSetlistSummary(state) {
    const songs = (state.setlist && state.setlist.songs) || [];
    const currentIndex = songs.findIndex((s) => s.status === "current");
    const currentSong = currentIndex >= 0 ? { ...songs[currentIndex], number: currentIndex + 1 } : null;

    let nextSong = null;
    if (currentIndex >= 0) {
      for (let i = currentIndex + 1; i < songs.length; i += 1) {
        if (songs[i].status === "queued") {
          nextSong = { ...songs[i], number: i + 1 };
          break;
        }
      }
    }
    if (!nextSong) {
      const firstQueuedIdx = songs.findIndex((s) => s.status === "queued");
      if (firstQueuedIdx >= 0) {
        nextSong = { ...songs[firstQueuedIdx], number: firstQueuedIdx + 1 };
      }
    }

    const sungSongs = songs
      .map((s, idx) => ({ ...s, number: idx + 1 }))
      .filter((s) => s.status === "sung");
    const queuedSongs = songs
      .map((s, idx) => ({ ...s, number: idx + 1 }))
      .filter((s) => s.status === "queued");

    return {
      totalCount: songs.length,
      currentSong,
      nextSong,
      sungSongs,
      queuedSongs,
    };
  }

  // -------------------------------------------------------------------------
  // Pomodoro & Task Checklist Logic
  // -------------------------------------------------------------------------
  function getPhaseDurationSeconds(pomodoro, phase = pomodoro.phase) {
    if (phase === "break") {
      return Math.max(60, Math.round(Number(pomodoro.breakMinutes || 5) * 60));
    }
    if (phase === "long_break") {
      return Math.max(60, Math.round(Number(pomodoro.longBreakMinutes || 15) * 60));
    }
    return Math.max(60, Math.round(Number(pomodoro.workMinutes || 25) * 60));
  }

  function getPomodoroRemainingSec(state, nowMs = Date.now()) {
    const pomo = state.pomodoro;
    if (!pomo.isRunning || !Number.isFinite(pomo.endEpochMs)) {
      return Math.max(0, Math.round(Number(pomo.remainingSec) || 0));
    }
    return Math.max(0, Math.ceil((pomo.endEpochMs - nowMs) / 1000));
  }

  function startPomodoro(state, nowMs = Date.now()) {
    const next = cloneState(state);
    if (!next.pomodoro.isRunning) {
      if (next.pomodoro.remainingSec <= 0) {
        next.pomodoro.remainingSec = getPhaseDurationSeconds(next.pomodoro, next.pomodoro.phase);
      }
      next.pomodoro.isRunning = true;
      next.pomodoro.endEpochMs = nowMs + next.pomodoro.remainingSec * 1000;
      bumpRevision(next);
    }
    return next;
  }

  function pausePomodoro(state, nowMs = Date.now()) {
    const next = cloneState(state);
    if (next.pomodoro.isRunning) {
      next.pomodoro.remainingSec = getPomodoroRemainingSec(next, nowMs);
      next.pomodoro.isRunning = false;
      next.pomodoro.endEpochMs = null;
      bumpRevision(next);
    }
    return next;
  }

  function resetPomodoroPhase(state) {
    const next = cloneState(state);
    next.pomodoro.isRunning = false;
    next.pomodoro.endEpochMs = null;
    next.pomodoro.remainingSec = getPhaseDurationSeconds(next.pomodoro, next.pomodoro.phase);
    bumpRevision(next);
    return next;
  }

  function resetPomodoroAll(state) {
    const next = cloneState(state);
    next.pomodoro.phase = "work";
    next.pomodoro.currentSet = 1;
    next.pomodoro.completedSetsToday = 0;
    next.pomodoro.isRunning = false;
    next.pomodoro.endEpochMs = null;
    next.pomodoro.remainingSec = getPhaseDurationSeconds(next.pomodoro, "work");
    bumpRevision(next);
    return next;
  }

  function transitionPomodoroPhase(state, nowMs = Date.now(), forceRun = null) {
    const next = cloneState(state);
    const pomo = next.pomodoro;
    const wasRunning = forceRun !== null ? Boolean(forceRun) : Boolean(pomo.isRunning && pomo.autoStartNext);

    if (pomo.phase === "work") {
      pomo.completedSetsToday = (pomo.completedSetsToday || 0) + 1;
      if (pomo.currentSet >= pomo.cyclesBeforeLongBreak) {
        pomo.phase = "long_break";
      } else {
        pomo.phase = "break";
      }
    } else {
      if (pomo.phase === "long_break") {
        pomo.currentSet = 1;
      } else {
        pomo.currentSet = Math.min(pomo.cyclesBeforeLongBreak, (pomo.currentSet || 1) + 1);
      }
      pomo.phase = "work";
    }

    pomo.remainingSec = getPhaseDurationSeconds(pomo, pomo.phase);
    pomo.isRunning = wasRunning;
    pomo.endEpochMs = wasRunning ? nowMs + pomo.remainingSec * 1000 : null;
    bumpRevision(next);
    return {
      state: next,
      phaseChanged: true,
      newPhase: pomo.phase,
    };
  }

  function tickPomodoro(state, nowMs = Date.now()) {
    if (!state.pomodoro.isRunning || !Number.isFinite(state.pomodoro.endEpochMs)) {
      return { state, phaseChanged: false, newPhase: state.pomodoro.phase };
    }
    if (nowMs >= state.pomodoro.endEpochMs) {
      return transitionPomodoroPhase(state, nowMs, state.pomodoro.autoStartNext);
    }
    return { state, phaseChanged: false, newPhase: state.pomodoro.phase };
  }

  function configurePomodoro(state, config, edition = state.edition) {
    const rules = getEditionRules(edition);
    const next = cloneState(state);
    const pomo = next.pomodoro;

    if (typeof config.chimeVolume === "number") {
      pomo.chimeVolume = clampNumber(config.chimeVolume, 0, 1, pomo.chimeVolume);
    }
    if (typeof config.chimeMuted === "boolean") {
      pomo.chimeMuted = config.chimeMuted;
    }
    if (typeof config.autoStartNext === "boolean") {
      pomo.autoStartNext = config.autoStartNext;
    }

    if (!rules.allowCustomPomodoro) {
      const attemptedProChange =
        (config.workMinutes !== undefined && Number(config.workMinutes) !== 25) ||
        (config.breakMinutes !== undefined && Number(config.breakMinutes) !== 5) ||
        (config.chimePreset !== undefined && config.chimePreset !== "crystal_bell");
      bumpRevision(next);
      return {
        state: next,
        error: attemptedProChange
          ? "カスタム時間設定（50分/10分等）＆チャイム変更はPro版の機能です。"
          : null,
      };
    }

    if (config.workMinutes !== undefined) {
      pomo.workMinutes = Math.round(clampNumber(config.workMinutes, 1, 180, pomo.workMinutes));
    }
    if (config.breakMinutes !== undefined) {
      pomo.breakMinutes = Math.round(clampNumber(config.breakMinutes, 1, 90, pomo.breakMinutes));
    }
    if (config.longBreakMinutes !== undefined) {
      pomo.longBreakMinutes = Math.round(
        clampNumber(config.longBreakMinutes, 1, 120, pomo.longBreakMinutes)
      );
    }
    if (config.cyclesBeforeLongBreak !== undefined) {
      pomo.cyclesBeforeLongBreak = Math.round(
        clampNumber(config.cyclesBeforeLongBreak, 2, 12, pomo.cyclesBeforeLongBreak)
      );
      pomo.currentSet = Math.min(pomo.currentSet, pomo.cyclesBeforeLongBreak);
    }
    if (config.chimePreset && CHIME_PRESETS[config.chimePreset]) {
      pomo.chimePreset = config.chimePreset;
    }

    if (!pomo.isRunning) {
      pomo.remainingSec = getPhaseDurationSeconds(pomo, pomo.phase);
    }

    bumpRevision(next);
    return { state: next, error: null };
  }

  function addTodo(state, text) {
    const cleaned = sanitizeText(text, 100);
    if (!cleaned) return state;
    const next = cloneState(state);
    if (next.pomodoro.todos.length >= 30) return next;
    next.pomodoro.todos.push({
      id: makeId("todo"),
      text: cleaned,
      done: false,
    });
    bumpRevision(next);
    return next;
  }

  function toggleTodo(state, todoId) {
    const next = cloneState(state);
    next.pomodoro.todos = next.pomodoro.todos.map((t) =>
      t.id === todoId ? { ...t, done: !t.done } : t
    );
    bumpRevision(next);
    return next;
  }

  function removeTodo(state, todoId) {
    const next = cloneState(state);
    next.pomodoro.todos = next.pomodoro.todos.filter((t) => t.id !== todoId);
    bumpRevision(next);
    return next;
  }

  // -------------------------------------------------------------------------
  // Mode, Theme, Clock & Preset Export/Import
  // -------------------------------------------------------------------------
  function setActiveMode(state, mode, allInOnePrimary = null) {
    if (!VALID_MODES.includes(mode)) return state;
    const next = cloneState(state);
    next.activeMode = mode;
    if (allInOnePrimary && VALID_SUB_MODES.includes(allInOnePrimary)) {
      next.allInOnePrimary = allInOnePrimary;
    }
    bumpRevision(next);
    return next;
  }

  function setOverlayPosition(state, position) {
    if (!VALID_POSITIONS.includes(position)) return state;
    const next = cloneState(state);
    next.overlayPosition = position;
    bumpRevision(next);
    return next;
  }

  function setTheme(state, themeId, edition = state.edition) {
    const rules = getEditionRules(edition);
    if (!THEMES[themeId]) {
      return { state: cloneState(state), error: "不明なテーマです。" };
    }
    if (!rules.allowedThemes.includes(themeId)) {
      return {
        state: cloneState(state),
        error: `「${THEMES[themeId].name}」テーマはProフルパック(全6テーマ収録)で利用できます！`,
      };
    }
    const next = cloneState(state);
    next.theme.themeId = themeId;
    if (!rules.allowCustomTheme) {
      next.theme.opacity = THEMES[themeId].defaultOpacity;
      next.theme.customAccent = "";
    }
    bumpRevision(next);
    return { state: next, error: null };
  }

  function setCustomThemeOptions(state, opts, edition = state.edition) {
    const rules = getEditionRules(edition);
    if (!rules.allowCustomTheme) {
      return {
        state: cloneState(state),
        error: "アクセントカラー変更＆透過度スライダーはPro版の機能です。",
      };
    }
    const next = cloneState(state);
    if (opts.customAccent !== undefined) {
      next.theme.customAccent = sanitizeHexColor(opts.customAccent, "");
    }
    if (opts.opacity !== undefined) {
      next.theme.opacity = clampNumber(opts.opacity, 0.2, 1.0, next.theme.opacity);
    }
    bumpRevision(next);
    return { state: next, error: null };
  }

  function updateClockConfig(state, patch) {
    const next = cloneState(state);
    if (patch.hashtag !== undefined) {
      next.clock.hashtag = sanitizeText(patch.hashtag, 60);
    }
    if (patch.marqueeText !== undefined) {
      next.clock.marqueeText = sanitizeText(patch.marqueeText, 240);
    }
    if (typeof patch.showSeconds === "boolean") {
      next.clock.showSeconds = patch.showSeconds;
    }
    if (typeof patch.use24Hour === "boolean") {
      next.clock.use24Hour = patch.use24Hour;
    }
    if (typeof patch.showMiniClockInCorner === "boolean") {
      next.showMiniClockInCorner = patch.showMiniClockInCorner;
    }
    bumpRevision(next);
    return next;
  }

  function updateSetlistOptions(state, patch) {
    const next = cloneState(state);
    if (patch.streamTitle !== undefined) {
      next.setlist.streamTitle = sanitizeText(patch.streamTitle, 60) || "🎤 歌枠 SINGING STREAM";
    }
    if (typeof patch.showSungHistory === "boolean") {
      next.setlist.showSungHistory = patch.showSungHistory;
    }
    if (typeof patch.includeOpeningZero === "boolean") {
      next.setlist.includeOpeningZero = patch.includeOpeningZero;
    }
    if (patch.openingLabel !== undefined) {
      next.setlist.openingLabel = sanitizeText(patch.openingLabel, 50) || "配信開始 / OP";
    }
    bumpRevision(next);
    return next;
  }

  function resolveEffectiveTheme(state) {
    const base = THEMES[state.theme && state.theme.themeId] || THEMES.dark_frost;
    const customAccent = sanitizeHexColor(state.theme && state.theme.customAccent, "");
    const opacity = clampNumber(
      state.theme && state.theme.opacity,
      0.2,
      1.0,
      base.defaultOpacity
    );
    return {
      ...base,
      accent: customAccent || base.accent,
      opacity,
    };
  }

  function exportPresetJson(state, edition = state.edition) {
    const rules = getEditionRules(edition);
    if (!rules.allowJsonPresets) {
      return { json: null, error: "JSONプリセット保存・読込はPro版の機能です。" };
    }
    const clean = sanitizeStateForEdition(state, "pro");
    clean.pomodoro.isRunning = false;
    clean.pomodoro.endEpochMs = null;
    clean.streamTimer.isRunning = false;
    clean.streamTimer.startedEpochMs = null;
    return {
      json: JSON.stringify(
        {
          product: "peco_obs_utawaku_pomodoro",
          version: "1.0.0",
          exportedAt: new Date().toISOString(),
          state: clean,
        },
        null,
        2
      ),
      error: null,
    };
  }

  function importPresetJson(rawJson, edition = "pro") {
    const rules = getEditionRules(edition);
    if (!rules.allowJsonPresets) {
      return { state: null, error: "JSONプリセット保存・読込はPro版の機能です。" };
    }
    try {
      const parsed = JSON.parse(rawJson);
      const candidate = parsed && parsed.state ? parsed.state : parsed;
      if (!candidate || typeof candidate !== "object") {
        return { state: null, error: "JSONの形式が正しくありません。" };
      }
      const sanitized = sanitizeStateForEdition(candidate, rules.id);
      bumpRevision(sanitized);
      return { state: sanitized, error: null };
    } catch (_err) {
      return { state: null, error: "JSONファイルの解析に失敗しました。" };
    }
  }

  // -------------------------------------------------------------------------
  // Dual Real-Time Sync Bridge (BroadcastChannel + localStorage)
  // -------------------------------------------------------------------------
  function createSyncBridge(options = {}) {
    const edition = options.edition || "lite";
    const storageKey = options.storageKey || STORAGE_KEY;
    const channelName = options.channelName || BROADCAST_CHANNEL_NAME;
    const storage =
      options.storage !== undefined
        ? options.storage
        : typeof window !== "undefined" && window.localStorage
        ? window.localStorage
        : null;
    const BroadcastChannelCtor =
      options.BroadcastChannelImpl !== undefined
        ? options.BroadcastChannelImpl
        : typeof BroadcastChannel !== "undefined"
        ? BroadcastChannel
        : null;
    const win =
      options.windowObj !== undefined
        ? options.windowObj
        : typeof window !== "undefined"
        ? window
        : null;
    const onStateReceived =
      typeof options.onStateReceived === "function" ? options.onStateReceived : () => {};

    const instanceId = makeId("peer");
    let lastUpdatedAt = 0;
    let channel = null;

    if (BroadcastChannelCtor) {
      try {
        channel = new BroadcastChannelCtor(channelName);
        channel.onmessage = (event) => {
          const payload = event && event.data;
          if (!payload || payload.senderId === instanceId || !payload.state) return;
          const incomingRev = Number(payload.state.updatedAt || 0);
          if (incomingRev >= lastUpdatedAt) {
            lastUpdatedAt = incomingRev;
            onStateReceived(sanitizeStateForEdition(payload.state, edition), "broadcast");
          }
        };
      } catch (_err) {
        channel = null;
      }
    }

    function handleStorageEvent(event) {
      if (!event || event.key !== storageKey || !event.newValue) return;
      try {
        const parsed = JSON.parse(event.newValue);
        const stateObj = parsed && parsed.state ? parsed.state : parsed;
        if (!stateObj || (parsed && parsed.senderId === instanceId)) return;
        const incomingRev = Number(stateObj.updatedAt || 0);
        if (incomingRev >= lastUpdatedAt) {
          lastUpdatedAt = incomingRev;
          onStateReceived(sanitizeStateForEdition(stateObj, edition), "storage");
        }
      } catch (_err) {
        // Ignore malformed external writes
      }
    }

    if (win && typeof win.addEventListener === "function") {
      win.addEventListener("storage", handleStorageEvent);
    }

    function loadInitialState() {
      if (storage) {
        try {
          const raw = storage.getItem(storageKey);
          if (raw) {
            const parsed = JSON.parse(raw);
            const candidate = parsed && parsed.state ? parsed.state : parsed;
            const restored = sanitizeStateForEdition(candidate, edition);
            lastUpdatedAt = Number(restored.updatedAt || 1);
            return restored;
          }
        } catch (_err) {
          // Fallback to default state if localStorage is blocked on opaque origin
        }
      }
      const initial = createDefaultState(edition);
      lastUpdatedAt = initial.updatedAt;
      return initial;
    }

    function publishState(nextState) {
      const sanitized = sanitizeStateForEdition(nextState, edition);
      lastUpdatedAt = Math.max(lastUpdatedAt, Number(sanitized.updatedAt || 1));
      const envelope = {
        senderId: instanceId,
        sentAt: Date.now(),
        state: sanitized,
      };
      if (storage) {
        try {
          storage.setItem(storageKey, JSON.stringify(envelope));
        } catch (_err) {
          // Ignore quota or file:// restrictions
        }
      }
      if (channel) {
        try {
          channel.postMessage(envelope);
        } catch (_err) {
          // Ignore closed channel
        }
      }
      return sanitized;
    }

    function destroy() {
      if (win && typeof win.removeEventListener === "function") {
        win.removeEventListener("storage", handleStorageEvent);
      }
      if (channel && typeof channel.close === "function") {
        channel.close();
      }
    }

    return {
      instanceId,
      loadInitialState,
      publishState,
      destroy,
    };
  }

  // -------------------------------------------------------------------------
  // Gentle WebAudio API Synthesizer Chime (Zero External Audio Dependencies)
  // -------------------------------------------------------------------------
  let _audioCtx = null;
  function playWebAudioChime(presetId = "crystal_bell", volume = 0.65, muted = false) {
    if (muted || volume <= 0) return false;
    if (typeof window === "undefined") return false;
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return false;

    try {
      if (!_audioCtx) {
        _audioCtx = new AudioCtx();
      }
      if (_audioCtx.state === "suspended") {
        _audioCtx.resume();
      }

      const now = _audioCtx.currentTime;
      const master = _audioCtx.createGain();
      master.gain.setValueAtTime(Math.min(1, Math.max(0, volume)) * 0.35, now);
      master.connect(_audioCtx.destination);

      if (presetId === "retro_8bit") {
        const notes = [523.25, 659.25, 783.99, 1046.5];
        notes.forEach((freq, idx) => {
          const osc = _audioCtx.createOscillator();
          const gain = _audioCtx.createGain();
          osc.type = "square";
          osc.frequency.setValueAtTime(freq, now + idx * 0.09);
          gain.gain.setValueAtTime(0.001, now + idx * 0.09);
          gain.gain.linearRampToValueAtTime(0.45, now + idx * 0.09 + 0.015);
          gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.09 + 0.22);
          osc.connect(gain);
          gain.connect(master);
          osc.start(now + idx * 0.09);
          osc.stop(now + idx * 0.09 + 0.24);
        });
      } else if (presetId === "lofi_rhodes") {
        const chord = [261.63, 329.63, 392.0, 493.88, 587.33]; // Cmaj9
        chord.forEach((freq, idx) => {
          const osc = _audioCtx.createOscillator();
          const gain = _audioCtx.createGain();
          osc.type = "triangle";
          osc.frequency.setValueAtTime(freq, now + idx * 0.04);
          gain.gain.setValueAtTime(0.001, now + idx * 0.04);
          gain.gain.linearRampToValueAtTime(0.32, now + idx * 0.04 + 0.04);
          gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.04 + 1.35);
          osc.connect(gain);
          gain.connect(master);
          osc.start(now + idx * 0.04);
          osc.stop(now + idx * 0.04 + 1.4);
        });
      } else {
        // Default: crystal_bell
        const notes = [587.33, 880.0, 1174.66, 1479.98]; // D5 - A5 - D6 - F#6
        notes.forEach((freq, idx) => {
          const osc = _audioCtx.createOscillator();
          const gain = _audioCtx.createGain();
          osc.type = "sine";
          osc.frequency.setValueAtTime(freq, now + idx * 0.14);
          gain.gain.setValueAtTime(0.001, now + idx * 0.14);
          gain.gain.linearRampToValueAtTime(0.55, now + idx * 0.14 + 0.02);
          gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.14 + 1.15);
          osc.connect(gain);
          gain.connect(master);
          osc.start(now + idx * 0.14);
          osc.stop(now + idx * 0.14 + 1.2);
        });
      }
      return true;
    } catch (_err) {
      return false;
    }
  }

  return {
    BROADCAST_CHANNEL_NAME,
    STORAGE_KEY,
    SCHEMA_VERSION,
    EDITIONS,
    THEMES,
    CHIME_PRESETS,
    VALID_MODES,
    VALID_POSITIONS,
    getEditionRules,
    createDefaultState,
    sanitizeStateForEdition,
    formatHms,
    formatMmSs,
    parseHmsInput,
    getStreamElapsedSec,
    startStreamTimer,
    pauseStreamTimer,
    resetStreamTimer,
    adjustStreamOffset,
    setStreamOffset,
    generateYoutubeTimestampList,
    parseSongLine,
    parseBulkSetlistText,
    addSong,
    bulkImportSongs,
    startSongById,
    advanceToNextSong,
    rewindToPreviousSong,
    removeSong,
    moveSong,
    updateSongTimestamp,
    resetSetlistProgress,
    getSetlistSummary,
    getPhaseDurationSeconds,
    getPomodoroRemainingSec,
    startPomodoro,
    pausePomodoro,
    resetPomodoroPhase,
    resetPomodoroAll,
    transitionPomodoroPhase,
    tickPomodoro,
    configurePomodoro,
    addTodo,
    toggleTodo,
    removeTodo,
    setActiveMode,
    setOverlayPosition,
    setTheme,
    setCustomThemeOptions,
    updateClockConfig,
    updateSetlistOptions,
    resolveEffectiveTheme,
    exportPresetJson,
    importPresetJson,
    createSyncBridge,
    playWebAudioChime,
  };
})();

if (typeof window !== "undefined") {
  window.PecoObsEngine = PecoObsEngine;
}

export default PecoObsEngine;
export const {
  BROADCAST_CHANNEL_NAME,
  STORAGE_KEY,
  SCHEMA_VERSION,
  EDITIONS,
  THEMES,
  CHIME_PRESETS,
  VALID_MODES,
  VALID_POSITIONS,
  getEditionRules,
  createDefaultState,
  sanitizeStateForEdition,
  formatHms,
  formatMmSs,
  parseHmsInput,
  getStreamElapsedSec,
  startStreamTimer,
  pauseStreamTimer,
  resetStreamTimer,
  adjustStreamOffset,
  setStreamOffset,
  generateYoutubeTimestampList,
  parseSongLine,
  parseBulkSetlistText,
  addSong,
  bulkImportSongs,
  startSongById,
  advanceToNextSong,
  rewindToPreviousSong,
  removeSong,
  moveSong,
  updateSongTimestamp,
  resetSetlistProgress,
  getSetlistSummary,
  getPhaseDurationSeconds,
  getPomodoroRemainingSec,
  startPomodoro,
  pausePomodoro,
  resetPomodoroPhase,
  resetPomodoroAll,
  transitionPomodoroPhase,
  tickPomodoro,
  configurePomodoro,
  addTodo,
  toggleTodo,
  removeTodo,
  setActiveMode,
  setOverlayPosition,
  setTheme,
  setCustomThemeOptions,
  updateClockConfig,
  updateSetlistOptions,
  resolveEffectiveTheme,
  exportPresetJson,
  importPresetJson,
  createSyncBridge,
  playWebAudioChime,
} = PecoObsEngine;
