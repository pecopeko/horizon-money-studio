"""Build standalone Lite & Pro OBS ZIP packages and Public GitHub Pages Showcase Site.

Outputs:
- `tracks/track27_obs_utawaku_pomodoro/dist/obs-utawaku-pomo-lite-v1.0.zip` (gitignored)
- `tracks/track27_obs_utawaku_pomodoro/dist/obs-utawaku-pomo-pro-v1.0.zip`  (gitignored)
- `tracks/track27_obs_utawaku_pomodoro/site/` (`index.html`, `overlay.html`, `dock.html`)

Author/Brand: peco (https://pecopeko1011.booth.pm/)
"""

from __future__ import annotations

from pathlib import Path
import shutil
import zipfile

TRACK_DIR = Path(__file__).resolve().parent
ENGINE_PATH = TRACK_DIR / "src" / "engine.js"
DIST_DIR = TRACK_DIR / "dist"
SITE_DIR = TRACK_DIR / "site"

BOOTH_URL = "https://pecopeko1011.booth.pm/"
GUMROAD_URL = "https://pecopeko.gumroad.com/l/tokyo-utawaku-obs-dock"
PAGES_BASE_URL = "https://pecopeko.github.io/obs-utawaku-pomodoro-dock"

SHARED_I18N_JS = r"""
const _pecoParams = new URLSearchParams(window.location.search);
function resolvePecoEdition(buildDefault) {
  if (buildDefault === "pro") return "pro";
  if (_pecoParams.get("pro") === "1" || _pecoParams.get("key") === "utawaku-pro-global") return "pro";
  return "lite";
}
function resolvePecoLang() {
  const q = (_pecoParams.get("lang") || localStorage.getItem("peco_obs_ui_lang") || "").toLowerCase();
  if (q.startsWith("en")) return "en";
  if (q.startsWith("ja")) return "ja";
  return ((navigator.language || "").toLowerCase().startsWith("ja")) ? "ja" : "en";
}
function applyDockI18nAndEdition(edition, lang) {
  document.documentElement.lang = lang;
  const upsell = document.querySelector(".upsell-strip");
  const pill = document.querySelector(".dock-header .edition-pill");
  if (edition === "pro") {
    if (upsell) upsell.style.display = "none";
    if (pill) pill.textContent = "PRO EDITION";
  } else if (upsell && lang === "en") {
    upsell.innerHTML = '<span>✨ <strong>Pro Pack ($12 USD)</strong> unlocks all 6 themes, unlimited setlist &amp; auto YouTube chapters</span><a href="https://pecopeko.gumroad.com/l/tokyo-utawaku-obs-dock" target="_blank" rel="noopener noreferrer" class="upsell-link">Gumroad ($12) ↗</a>';
  }
  if (lang !== "en") return;
  document.title = "OBS Custom Dock — Utawaku Setlist & Pomodoro Control | peco";
  const textMap = {
    "歌枠＆ポモドーロ操作ドック": "Utawaku & Pomodoro OBS Dock",
    "📺 オーバーレイ表示モード": "📺 Overlay Scene Mode",
    "🎤 歌枠": "🎤 Singing",
    "⏱ ポモドーロ": "⏱ Pomodoro",
    "🕒 時計・タグ": "🕒 Clock/Tag",
    "✨ 同時表示": "✨ Combo",
    "⬅ 左寄せ配置": "⬅ Left Align",
    "➡ 右寄せ配置": "➡ Right Align",
    "▬ 下部ワイド": "▬ Lower Third",
    "🎤 セトリ": "🎤 Setlist",
    "🎨 テーマ": "🎨 Themes",
    "▶ 次の曲へ進む（この曲を開始）": "▶ Start Next Song (+ Log Timestamp)",
    "⏮ 前の曲へ戻す": "⏮ Previous Song",
    "↺ 未歌唱に戻す": "↺ Reset Progress",
    "⏱ 配信経過＆YouTubeタイムスタンプ自動記録": "⏱ Stream Elapsed & Auto YouTube Chapters",
    "PRO機能": edition === "pro" ? "PRO ACTIVE" : "PRO FEATURE",
    "🔴 配信計測スタート": "🔴 Start Stream Timer",
    "0リセット": "Reset 0:00",
    "📋 YouTube概要欄・コメント用タイムスタンプをコピー": "📋 Copy YouTube Chapters to Clipboard",
    "⬇ JSON保存": "⬇ Export JSON",
    "🎛 OBS対話ミニ操作 (LITE)": edition === "pro" ? "🎛 OBS Mini Control (PRO)" : "🎛 OBS Mini Control (LITE)",
    "🎛 OBS対話ミニ操作 (PRO)": "🎛 OBS Mini Control (PRO)",
    "× 隠す": "× Hide",
    "⏮ 前曲": "⏮ Prev",
    "▶ 次の曲へ (開始)": "▶ Next Song",
    "⏱ 開始/停止": "⏱ Start/Pause",
    "⚙ 曲追加・テーマ": "⚙ Add Song / Theme",
    "＋ セトリに追加": "＋ Add to Setlist",
    "📋 タイムスタンプCopy": "📋 Copy Chapters",
    "マウスを離すと約2.5秒で自動的に透明化します（配信画面には映りません）。": "Auto-hides 2.5s after mouse leaves (invisible on stream)."
  };
  document.querySelectorAll("span, button, summary, label, div.ib-note").forEach((el) => {
    if (el.children.length === 0) {
      const t = el.textContent.trim();
      if (textMap[t]) el.textContent = textMap[t];
      else if (edition === "pro" && t.includes("🔒Pro")) el.textContent = t.replace("🔒Pro", "").trim();
    }
  });
  const phMap = {
    "ibSongTitle": "Song Title (e.g. Idol)",
    "ibSongArtist": "Artist (e.g. YOASOBI)",
    "inputSongTitle": "Song Title (e.g. Idol)",
    "inputSongArtist": "Artist (e.g. YOASOBI)",
    "inputSongNote": "Key / Request Note (optional)",
    "inputTodoText": "Add task for Pomodoro stream..."
  };
  Object.keys(phMap).forEach((id) => {
    const inp = document.getElementById(id);
    if (inp) inp.placeholder = phMap[id];
  });
}
"""


def load_inline_engine_js() -> str:
    """Load `src/engine.js` with ESM export lines stripped for inline `<script>` embedding."""
    raw = ENGINE_PATH.read_text(encoding="utf-8")
    marker = "export default PecoObsEngine;"
    idx = raw.find(marker)
    if idx != -1:
        raw = raw[:idx].rstrip()
    return raw


SHARED_OVERLAY_RENDERER_JS = r"""
function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatClockParts(now, use24Hour, showSeconds) {
  let hours = now.getHours();
  let ampm = "";
  if (!use24Hour) {
    ampm = hours >= 12 ? " PM" : " AM";
    hours = hours % 12 || 12;
  }
  const hh = String(hours).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const ss = String(now.getSeconds()).padStart(2, "0");
  const days = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
  const jpDays = ["日", "月", "火", "水", "木", "金", "土"];
  const dateStr = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, "0")}.${String(
    now.getDate()
  ).padStart(2, "0")} (${jpDays[now.getDay()]}) ${days[now.getDay()]}`;
  return {
    hm: `${hh}:${mm}`,
    sec: showSeconds ? `:${ss}` : "",
    ampm,
    dateStr,
  };
}

function applyThemeCssVariables(targetEl, state) {
  const t = window.PecoObsEngine.resolveEffectiveTheme(state);
  targetEl.style.setProperty("--ov-bg-rgb", t.bgRgb);
  targetEl.style.setProperty("--ov-bg-alt-rgb", t.bgAltRgb);
  targetEl.style.setProperty("--ov-opacity", String(t.opacity));
  targetEl.style.setProperty("--ov-border", t.borderColor);
  targetEl.style.setProperty("--ov-text", t.textPrimary);
  targetEl.style.setProperty("--ov-text-sec", t.textSecondary);
  targetEl.style.setProperty("--ov-muted", t.textMuted);
  targetEl.style.setProperty("--ov-accent", t.accent);
  targetEl.style.setProperty("--ov-accent2", t.accent2);
  targetEl.style.setProperty("--ov-badge-text", t.badgeText);
  targetEl.style.setProperty("--ov-radius", `${t.radiusPx}px`);
  targetEl.dataset.themeId = t.id;
  targetEl.dataset.pixel = t.pixelBorder ? "1" : "0";
  targetEl.dataset.light = t.isLight ? "1" : "0";
}

function renderUtawakuCardHtml(state, compactMode) {
  const Engine = window.PecoObsEngine;
  const summary = Engine.getSetlistSummary(state);
  const offsetSec = Number((state.streamTimer && state.streamTimer.offsetSec) || 0);
  const current = summary.currentSong;
  const next = summary.nextSong;
  const songs = (state.setlist && state.setlist.songs) || [];

  const eqBars = `
    <span class="ov-eq" aria-hidden="true">
      <i></i><i></i><i></i><i></i><i></i>
    </span>
  `;

  const currentHtml = current
    ? `
      <div class="ov-now-box">
        <div class="ov-now-label-row">
          <span class="ov-pill-accent">${eqBars}<span>♪ NOW SINGING</span></span>
          <span class="ov-song-num">#${String(current.number).padStart(2, "0")} / ${String(
        summary.totalCount
      ).padStart(2, "0")}</span>
        </div>
        <div class="ov-now-title">${escapeHtml(current.title)}</div>
        ${
          current.artist
            ? `<div class="ov-now-artist">${escapeHtml(current.artist)}</div>`
            : `<div class="ov-now-artist">Sing-Along Live</div>`
        }
      </div>
    `
    : `
      <div class="ov-now-box">
        <div class="ov-now-label-row">
          <span class="ov-pill-accent">♪ STANDBY</span>
          <span class="ov-song-num">${summary.sungSongs.length} / ${summary.totalCount} SUNG</span>
        </div>
        <div class="ov-now-title">リクエスト＆次の曲準備中♪</div>
        <div class="ov-now-artist">${escapeHtml(state.setlist.streamTitle)}</div>
      </div>
    `;

  const nextHtml = next
    ? `
      <div class="ov-next-row">
        <span class="ov-next-tag">NEXT UP ▸</span>
        <span class="ov-next-song">#${String(next.number).padStart(2, "0")} ${escapeHtml(
        next.title
      )}${next.artist ? ` <small>/ ${escapeHtml(next.artist)}</small>` : ""}</span>
      </div>
    `
    : "";

  if (compactMode) {
    return `
      <div class="ov-card ov-card-compact">
        ${currentHtml}
        ${nextHtml}
      </div>
    `;
  }

  let listItemsHtml = "";
  if (state.setlist.showSungHistory && songs.length > 0) {
    listItemsHtml = songs
      .map((s, idx) => {
        const num = String(idx + 1).padStart(2, "0");
        const isSung = s.status === "sung";
        const isCur = s.status === "current";
        const mark = isSung ? "✓" : isCur ? "▶" : "•";
        const tsBadge =
          state.edition === "pro" && s.startedAtSec !== null && s.startedAtSec !== undefined
            ? `<span class="ov-row-ts">${Engine.formatHms(Math.max(0, s.startedAtSec + offsetSec))}</span>`
            : "";
        return `
          <div class="ov-song-row status-${escapeHtml(s.status)}">
            <span class="ov-row-mark">${mark}</span>
            <span class="ov-row-idx">${num}</span>
            <span class="ov-row-main">
              <span class="ov-row-title">${escapeHtml(s.title)}</span>
              ${s.artist ? `<span class="ov-row-artist">/ ${escapeHtml(s.artist)}</span>` : ""}
            </span>
            ${tsBadge}
          </div>
        `;
      })
      .join("");
  }

  return `
    <div class="ov-card ov-utawaku-card">
      <div class="ov-card-header">
        <span class="ov-header-title">${escapeHtml(state.setlist.streamTitle)}</span>
        <span class="ov-header-count">${summary.sungSongs.length}/${summary.totalCount} SUNG</span>
      </div>
      ${currentHtml}
      ${nextHtml}
      ${
        listItemsHtml
          ? `<div class="ov-section-caption">SETLIST / SUNG LOG</div><div class="ov-song-list">${listItemsHtml}</div>`
          : ""
      }
    </div>
  `;
}

function renderPomodoroCardHtml(state, nowMs, compactMode) {
  const Engine = window.PecoObsEngine;
  const pomo = state.pomodoro;
  const remSec = Engine.getPomodoroRemainingSec(state, nowMs);
  const totalSec = Engine.getPhaseDurationSeconds(pomo, pomo.phase);
  const ratio = totalSec > 0 ? Math.min(1, Math.max(0, remSec / totalSec)) : 0;
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - ratio);

  const phaseMeta =
    pomo.phase === "break"
      ? { badge: "☕ BREAK TIME", sub: "小休憩・お茶タイム" }
      : pomo.phase === "long_break"
      ? { badge: "🌙 LONG BREAK", sub: "リフレッシュ長休憩" }
      : { badge: "🔥 FOCUS WORK", sub: "作業・勉強集中タイム" };

  const todos = pomo.todos || [];
  const doneCount = todos.filter((t) => t.done).length;

  const ringSvg = `
    <div class="ov-pomo-ring-wrap">
      <svg class="ov-pomo-ring" viewBox="0 0 140 140" aria-hidden="true">
        <circle class="ov-ring-track" cx="70" cy="70" r="${radius}" />
        <circle
          class="ov-ring-fill"
          cx="70"
          cy="70"
          r="${radius}"
          stroke-dasharray="${circumference.toFixed(2)}"
          stroke-dashoffset="${dashOffset.toFixed(2)}"
        />
      </svg>
      <div class="ov-ring-center">
        <div class="ov-pomo-time">${Engine.formatMmSs(remSec)}</div>
        <div class="ov-pomo-state">${pomo.isRunning ? "RUNNING" : "PAUSED"}</div>
      </div>
    </div>
  `;

  if (compactMode) {
    return `
      <div class="ov-card ov-card-compact ov-pomo-compact">
        ${ringSvg}
        <div class="ov-pomo-compact-info">
          <span class="ov-pill-accent">${phaseMeta.badge}</span>
          <div class="ov-pomo-set">SET ${pomo.currentSet} / ${pomo.cyclesBeforeLongBreak} · DONE ${pomo.completedSetsToday}</div>
          <div class="ov-pomo-sub">${phaseMeta.sub}</div>
        </div>
      </div>
    `;
  }

  const todoHtml =
    todos.length > 0
      ? `
        <div class="ov-section-caption">TASK LIST (${doneCount}/${todos.length})</div>
        <div class="ov-todo-list">
          ${todos
            .map(
              (t) => `
            <div class="ov-todo-row ${t.done ? "is-done" : ""}">
              <span class="ov-todo-check">${t.done ? "✓" : "□"}</span>
              <span class="ov-todo-text">${escapeHtml(t.text)}</span>
            </div>
          `
            )
            .join("")}
        </div>
      `
      : "";

  return `
    <div class="ov-card ov-pomo-card">
      <div class="ov-card-header">
        <span class="ov-pill-accent">${phaseMeta.badge}</span>
        <span class="ov-header-count">SET ${pomo.currentSet} / ${pomo.cyclesBeforeLongBreak}</span>
      </div>
      <div class="ov-pomo-hero">
        ${ringSvg}
        <div class="ov-pomo-meta">
          <div class="ov-pomo-sub">${phaseMeta.sub}</div>
          <div class="ov-pomo-stat-line">完了セット: <strong>${pomo.completedSetsToday}</strong></div>
          <div class="ov-pomo-stat-line">配分: <strong>${pomo.workMinutes}m / ${pomo.breakMinutes}m</strong></div>
        </div>
      </div>
      ${todoHtml}
    </div>
  `;
}

function renderClockBoardHtml(state, nowDate, isMiniCorner) {
  const parts = formatClockParts(
    nowDate,
    Boolean(state.clock && state.clock.use24Hour),
    Boolean(state.clock && state.clock.showSeconds)
  );
  const hashtag = (state.clock && state.clock.hashtag) || "";
  const marquee = (state.clock && state.clock.marqueeText) || "";

  if (isMiniCorner) {
    return `
      <div class="ov-card ov-mini-clock">
        <div class="ov-mini-clock-top">
          <span class="ov-mini-time">${parts.hm}<small>${parts.sec}${parts.ampm}</small></span>
          ${hashtag ? `<span class="ov-mini-tag">${escapeHtml(hashtag)}</span>` : ""}
        </div>
        <div class="ov-mini-date">${escapeHtml(parts.dateStr)}</div>
      </div>
    `;
  }

  return `
    <div class="ov-card ov-clock-card">
      <div class="ov-clock-top-row">
        <div>
          <div class="ov-clock-date">${escapeHtml(parts.dateStr)}</div>
          <div class="ov-clock-time">${parts.hm}<span class="ov-clock-sec">${parts.sec}${parts.ampm}</span></div>
        </div>
        ${hashtag ? `<div class="ov-clock-tag-pill">${escapeHtml(hashtag)}</div>` : ""}
      </div>
      ${
        marquee
          ? `
        <div class="ov-marquee-Viewport">
          <div class="ov-marquee-track">
            <span>${escapeHtml(marquee)}</span>
            <span aria-hidden="true">${escapeHtml(marquee)}</span>
          </div>
        </div>
      `
          : ""
      }
    </div>
  `;
}

function renderFullOverlaySceneHtml(state, nowMs) {
  const nowDate = new Date(nowMs);
  const compact = state.overlayPosition === "compact";
  const mode = state.activeMode;

  let mainHtml = "";
  let cornerClockHtml = "";

  if (mode === "clock") {
    mainHtml = renderClockBoardHtml(state, nowDate, false);
  } else if (mode === "pomodoro") {
    mainHtml = renderPomodoroCardHtml(state, nowMs, compact);
    if (state.showMiniClockInCorner) {
      cornerClockHtml = renderClockBoardHtml(state, nowDate, true);
    }
  } else if (mode === "all_in_one") {
    const topClock = renderClockBoardHtml(state, nowDate, false);
    const primaryCard =
      state.allInOnePrimary === "pomodoro"
        ? renderPomodoroCardHtml(state, nowMs, compact)
        : renderUtawakuCardHtml(state, compact);
    mainHtml = `<div class="ov-stack">${topClock}${primaryCard}</div>`;
  } else {
    mainHtml = renderUtawakuCardHtml(state, compact);
    if (state.showMiniClockInCorner) {
      cornerClockHtml = renderClockBoardHtml(state, nowDate, true);
    }
  }

  return { mainHtml, cornerClockHtml };
}
"""


SHARED_OVERLAY_CSS = r"""
.ov-root {
  --ov-bg-rgb: 15, 22, 36;
  --ov-bg-alt-rgb: 23, 33, 52;
  --ov-opacity: 0.86;
  --ov-border: rgba(148, 163, 184, 0.28);
  --ov-text: #F8FAFC;
  --ov-text-sec: #CBD5E1;
  --ov-muted: #94A3B8;
  --ov-accent: #38BDF8;
  --ov-accent2: #818CF8;
  --ov-badge-text: #082F49;
  --ov-radius: 18px;
  font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Yu Gothic UI", "Meiryo", system-ui, sans-serif;
  color: var(--ov-text);
  box-sizing: border-box;
}

.ov-root *, .ov-root *::before, .ov-root *::after {
  box-sizing: border-box;
}

.ov-card {
  background: rgba(var(--ov-bg-rgb), var(--ov-opacity));
  border: 1.5px solid var(--ov-border);
  border-radius: var(--ov-radius);
  padding: 20px 22px;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow: 0 14px 36px rgba(0, 0, 0, 0.28);
  transition: background 0.25s ease, border-color 0.25s ease, color 0.25s ease;
}

.ov-root[data-pixel="1"] .ov-card {
  border-width: 3px;
  border-radius: 0 !important;
  backdrop-filter: none;
  box-shadow: 6px 6px 0 rgba(0, 0, 0, 0.65);
  font-family: "DotGothic16", "MS Gothic", "Osaka-Mono", "Hiragino Kaku Gothic ProN", monospace;
}

.ov-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ov-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.ov-header-title {
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: var(--ov-text-sec);
}

.ov-header-count {
  font-size: 12px;
  font-weight: 700;
  color: var(--ov-muted);
  font-variant-numeric: tabular-nums;
}

.ov-pill-accent {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: var(--ov-accent);
  color: var(--ov-badge-text);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.05em;
  padding: 4px 11px;
  border-radius: 999px;
}

.ov-root[data-pixel="1"] .ov-pill-accent {
  border-radius: 0;
}

.ov-now-box {
  background: rgba(var(--ov-bg-alt-rgb), 0.78);
  border: 1px solid var(--ov-border);
  border-radius: calc(var(--ov-radius) * 0.72);
  padding: 15px 17px;
}

.ov-now-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.ov-song-num {
  font-size: 12px;
  font-weight: 800;
  color: var(--ov-muted);
  font-variant-numeric: tabular-nums;
}

.ov-now-title {
  font-size: 26px;
  font-weight: 900;
  line-height: 1.25;
  color: var(--ov-text);
  word-break: break-word;
}

.ov-now-artist {
  margin-top: 4px;
  font-size: 14px;
  font-weight: 700;
  color: var(--ov-accent);
}

.ov-eq {
  display: inline-flex;
  align-items: flex-end;
  gap: 2px;
  height: 12px;
}

.ov-eq i {
  display: block;
  width: 3px;
  background: currentColor;
  border-radius: 1px;
  animation: ovEqBounce 0.85s ease-in-out infinite alternate;
}

.ov-eq i:nth-child(1) { height: 5px; animation-delay: 0s; }
.ov-eq i:nth-child(2) { height: 11px; animation-delay: 0.16s; }
.ov-eq i:nth-child(3) { height: 7px; animation-delay: 0.32s; }
.ov-eq i:nth-child(4) { height: 12px; animation-delay: 0.11s; }
.ov-eq i:nth-child(5) { height: 6px; animation-delay: 0.25s; }

@keyframes ovEqBounce {
  0% { transform: scaleY(0.35); }
  100% { transform: scaleY(1); }
}

.ov-next-row {
  margin-top: 12px;
  padding: 9px 13px;
  border-radius: calc(var(--ov-radius) * 0.55);
  background: rgba(var(--ov-bg-alt-rgb), 0.5);
  border-left: 3px solid var(--ov-accent2);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  font-weight: 700;
}

.ov-next-tag {
  color: var(--ov-accent2);
  font-weight: 900;
  white-space: nowrap;
  font-size: 11px;
  letter-spacing: 0.04em;
}

.ov-next-song {
  color: var(--ov-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ov-next-song small {
  color: var(--ov-muted);
  font-weight: 600;
}

.ov-section-caption {
  margin-top: 14px;
  margin-bottom: 7px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: var(--ov-muted);
}

.ov-song-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
  max-height: 280px;
  overflow-y: auto;
  padding-right: 4px;
}

.ov-song-list::-webkit-scrollbar {
  width: 4px;
}
.ov-song-list::-webkit-scrollbar-thumb {
  background: var(--ov-border);
  border-radius: 4px;
}

.ov-song-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  transition: background 0.18s ease;
}

.ov-song-row.status-sung {
  opacity: 0.62;
}

.ov-song-row.status-sung .ov-row-mark {
  color: var(--ov-accent);
}

.ov-song-row.status-current {
  background: rgba(var(--ov-bg-alt-rgb), 0.9);
  border: 1px solid var(--ov-accent);
}

.ov-song-row.status-current .ov-row-mark {
  color: var(--ov-accent);
}

.ov-row-mark {
  width: 14px;
  text-align: center;
  font-weight: 900;
  color: var(--ov-muted);
}

.ov-row-idx {
  font-size: 11px;
  color: var(--ov-muted);
  font-variant-numeric: tabular-nums;
}

.ov-row-main {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ov-row-artist {
  font-size: 12px;
  color: var(--ov-muted);
  margin-left: 4px;
  font-weight: 600;
}

.ov-row-ts {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: var(--ov-accent);
  background: rgba(var(--ov-bg-rgb), 0.65);
  padding: 2px 6px;
  border-radius: 5px;
}

/* Pomodoro */
.ov-pomo-hero {
  display: flex;
  align-items: center;
  gap: 18px;
}

.ov-pomo-ring-wrap {
  position: relative;
  width: 132px;
  height: 132px;
  flex-shrink: 0;
}

.ov-pomo-ring {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.ov-ring-track {
  fill: none;
  stroke: var(--ov-border);
  stroke-width: 10;
}

.ov-ring-fill {
  fill: none;
  stroke: var(--ov-accent);
  stroke-width: 10;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.35s linear;
}

.ov-root[data-pixel="1"] .ov-ring-fill {
  stroke-linecap: butt;
}

.ov-ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.ov-pomo-time {
  font-size: 29px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  line-height: 1.05;
}

.ov-pomo-state {
  margin-top: 3px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: var(--ov-muted);
}

.ov-pomo-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ov-pomo-sub {
  font-size: 16px;
  font-weight: 800;
  color: var(--ov-text);
}

.ov-pomo-stat-line {
  font-size: 13px;
  color: var(--ov-text-sec);
}

.ov-todo-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ov-todo-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(var(--ov-bg-alt-rgb), 0.55);
  font-size: 13px;
  font-weight: 700;
}

.ov-todo-row.is-done {
  opacity: 0.58;
}

.ov-todo-row.is-done .ov-todo-text {
  text-decoration: line-through;
}

.ov-todo-check {
  color: var(--ov-accent);
  font-weight: 900;
}

/* Clock & Tag */
.ov-clock-top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.ov-clock-date {
  font-size: 13px;
  font-weight: 800;
  color: var(--ov-muted);
  letter-spacing: 0.04em;
}

.ov-clock-time {
  font-size: 42px;
  font-weight: 900;
  line-height: 1.05;
  font-variant-numeric: tabular-nums;
}

.ov-clock-sec {
  font-size: 20px;
  color: var(--ov-accent);
  margin-left: 3px;
}

.ov-clock-tag-pill {
  background: var(--ov-accent);
  color: var(--ov-badge-text);
  font-size: 14px;
  font-weight: 900;
  padding: 7px 14px;
  border-radius: 999px;
  white-space: nowrap;
}

.ov-root[data-pixel="1"] .ov-clock-tag-pill {
  border-radius: 0;
}

.ov-marquee-Viewport {
  margin-top: 12px;
  overflow: hidden;
  white-space: nowrap;
  background: rgba(var(--ov-bg-alt-rgb), 0.65);
  border-radius: 8px;
  padding: 7px 0;
}

.ov-marquee-track {
  display: inline-flex;
  gap: 48px;
  padding-left: 16px;
  font-size: 13px;
  font-weight: 700;
  color: var(--ov-text-sec);
  animation: ovMarqueeScroll 20s linear infinite;
}

@keyframes ovMarqueeScroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

.ov-mini-clock {
  padding: 12px 16px;
  min-width: 220px;
}

.ov-mini-clock-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.ov-mini-time {
  font-size: 24px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.ov-mini-time small {
  font-size: 13px;
  color: var(--ov-accent);
}

.ov-mini-tag {
  font-size: 11px;
  font-weight: 800;
  color: var(--ov-badge-text);
  background: var(--ov-accent);
  padding: 3px 9px;
  border-radius: 999px;
}

.ov-mini-date {
  margin-top: 2px;
  font-size: 11px;
  font-weight: 700;
  color: var(--ov-muted);
}

/* Compact mode */
.ov-card-compact {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
}

.ov-card-compact .ov-now-box {
  flex: 1;
  padding: 10px 14px;
}

.ov-card-compact .ov-next-row {
  margin-top: 0;
  max-width: 280px;
}
"""


def build_overlay_html(edition: str) -> str:
    """Build standalone `overlay.html` (`1920x1080` transparent + OBS Interact floating mini-dock)."""
    engine_js = load_inline_engine_js()
    edition_label = "PRO" if edition == "pro" else "LITE"

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>OBS Overlay ({edition_label}) — 歌枠セトリ＆ポモドーロ・時計 | peco</title>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      background: transparent !important;
      user-select: none;
    }}
    {SHARED_OVERLAY_CSS}

    .obs-canvas {{
      position: relative;
      width: 100vw;
      height: 100vh;
      padding: 36px 42px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      pointer-events: none;
    }}

    .obs-canvas.pos-right {{
      flex-direction: row-reverse;
    }}

    .obs-main-slot {{
      width: min(440px, 42vw);
      pointer-events: auto;
    }}

    .obs-canvas.pos-compact {{
      align-items: flex-end;
    }}

    .obs-canvas.pos-compact .obs-main-slot {{
      width: min(780px, 72vw);
    }}

    .obs-corner-slot {{
      pointer-events: auto;
    }}

    /* OBS Interact (対話) Floating Mini-Control Bar — Auto-hides completely on stream! */
    .interact-bar {{
      position: fixed;
      right: 24px;
      bottom: 24px;
      z-index: 9999;
      background: rgba(11, 16, 28, 0.95);
      color: #F8FAFC;
      border: 1px solid rgba(56, 189, 248, 0.55);
      border-radius: 14px;
      padding: 12px 14px;
      width: 360px;
      box-shadow: 0 18px 42px rgba(0, 0, 0, 0.55);
      font-family: "Hiragino Sans", "Noto Sans JP", system-ui, sans-serif;
      opacity: 0;
      visibility: hidden;
      transform: translateY(10px);
      pointer-events: none;
      transition: opacity 0.2s ease, transform 0.2s ease, visibility 0.2s ease;
    }}

    .interact-bar.is-visible {{
      opacity: 1;
      visibility: visible;
      transform: translateY(0);
      pointer-events: auto;
    }}

    .ib-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
      font-size: 12px;
      font-weight: 800;
      color: #38BDF8;
    }}

    .ib-row {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-bottom: 8px;
    }}

    .ib-btn {{
      appearance: none;
      border: 1px solid rgba(148, 163, 184, 0.3);
      background: #1E293B;
      color: #F8FAFC;
      border-radius: 8px;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
    }}

    .ib-btn:hover {{
      border-color: #38BDF8;
      background: #26354D;
    }}

    .ib-btn.primary {{
      background: #0284C7;
      border-color: #38BDF8;
      color: #FFFFFF;
      flex: 1;
    }}

    .ib-btn.is-active {{
      background: #38BDF8;
      color: #082F49;
      border-color: #38BDF8;
    }}

    .ib-drawer {{
      display: none;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid rgba(148, 163, 184, 0.22);
    }}

    .ib-drawer.is-open {{
      display: block;
    }}

    .ib-input {{
      width: 100%;
      background: #0F172A;
      color: #F8FAFC;
      border: 1px solid rgba(148, 163, 184, 0.35);
      border-radius: 7px;
      padding: 6px 8px;
      font-size: 12px;
      margin-bottom: 6px;
    }}

    .ib-note {{
      font-size: 11px;
      color: #94A3B8;
      line-height: 1.4;
    }}
  </style>
</head>
<body>
  <div id="obsRoot" class="ov-root">
    <div id="obsCanvas" class="obs-canvas">
      <div id="mainSlot" class="obs-main-slot"></div>
      <div id="cornerSlot" class="obs-corner-slot"></div>
    </div>
  </div>

  <!-- OBS「対話 (Interact)」ウィンドウ操作用の自動非表示ミニドック -->
  <aside id="interactBar" class="interact-bar" aria-label="OBS対話ミニ操作バー">
    <div class="ib-head">
      <span>🎛 OBS対話ミニ操作 ({edition_label})</span>
      <button type="button" id="ibHideBtn" class="ib-btn" style="padding:2px 8px;">× 隠す</button>
    </div>
    <div class="ib-row">
      <button type="button" class="ib-btn mode-btn" data-mode="utawaku">🎤 歌枠</button>
      <button type="button" class="ib-btn mode-btn" data-mode="pomodoro">⏱ ポモ</button>
      <button type="button" class="ib-btn mode-btn" data-mode="clock">🕒 時計</button>
      <button type="button" class="ib-btn mode-btn" data-mode="all_in_one">✨ 同時</button>
    </div>
    <div class="ib-row">
      <button type="button" id="ibPrevSong" class="ib-btn">⏮ 前曲</button>
      <button type="button" id="ibNextSong" class="ib-btn primary">▶ 次の曲へ (開始)</button>
      <button type="button" id="ibPomoToggle" class="ib-btn">⏱ 開始/停止</button>
    </div>
    <div class="ib-row">
      <button type="button" id="ibStreamTimerBtn" class="ib-btn">🔴 配信計測: <span id="ibStreamElapsed">0:00:00</span></button>
      <button type="button" id="ibDrawerToggle" class="ib-btn">⚙ 曲追加・テーマ</button>
    </div>
    <div id="ibDrawer" class="ib-drawer">
      <input id="ibSongTitle" class="ib-input" placeholder="曲名 (例: アイドル)" />
      <input id="ibSongArtist" class="ib-input" placeholder="アーティスト (例: YOASOBI)" />
      <div class="ib-row">
        <button type="button" id="ibAddSongBtn" class="ib-btn primary">＋ セトリに追加</button>
        <button type="button" id="ibCopyTsBtn" class="ib-btn">📋 タイムスタンプCopy</button>
      </div>
      <select id="ibThemeSelect" class="ib-input" aria-label="テーマ選択"></select>
      <div id="ibStatusMsg" class="ib-note">マウスを離すと約2.5秒で自動的に透明化します（配信画面には映りません）。</div>
    </div>
  </aside>

  <script>
    {SHARED_I18N_JS}
    const EDITION = resolvePecoEdition("{edition}");
    const UI_LANG = resolvePecoLang();
    {engine_js}
    {SHARED_OVERLAY_RENDERER_JS}

    (function initOverlayApp() {{
      applyDockI18nAndEdition(EDITION, UI_LANG);
      const Engine = window.PecoObsEngine;
      const rootEl = document.getElementById("obsRoot");
      const canvasEl = document.getElementById("obsCanvas");
      const mainSlotEl = document.getElementById("mainSlot");
      const cornerSlotEl = document.getElementById("cornerSlot");
      const interactBar = document.getElementById("interactBar");
      const ibDrawer = document.getElementById("ibDrawer");
      const ibThemeSelect = document.getElementById("ibThemeSelect");
      const ibStatusMsg = document.getElementById("ibStatusMsg");

      let appState = null;

      const bridge = Engine.createSyncBridge({{
        edition: EDITION,
        onStateReceived: (incomingState) => {{
          appState = incomingState;
          renderAll(Date.now());
        }},
      }});

      appState = bridge.loadInitialState();

      // Populate theme select
      Object.values(Engine.THEMES).forEach((t) => {{
        const opt = document.createElement("option");
        const locked = EDITION === "lite" && t.id !== "dark_frost";
        opt.value = t.id;
        opt.textContent = locked ? `🔒 ${{t.name}} (${{t.jpName}} - Pro)` : `${{t.name}} (${{t.jpName}})`;
        ibThemeSelect.appendChild(opt);
      }});

      function commitState(nextState) {{
        appState = bridge.publishState(nextState);
        renderAll(Date.now());
      }}

      function renderAll(nowMs) {{
        applyThemeCssVariables(rootEl, appState);
        canvasEl.className = "obs-canvas pos-" + appState.overlayPosition;
        const scene = renderFullOverlaySceneHtml(appState, nowMs);
        mainSlotEl.innerHTML = scene.mainHtml;
        cornerSlotEl.innerHTML = scene.cornerClockHtml;

        // Update mini-bar indicators
        document.querySelectorAll(".mode-btn").forEach((btn) => {{
          btn.classList.toggle("is-active", btn.dataset.mode === appState.activeMode);
        }});
        const elapsedEl = document.getElementById("ibStreamElapsed");
        if (elapsedEl) {{
          elapsedEl.textContent = Engine.formatHms(Engine.getStreamElapsedSec(appState, nowMs));
        }}
        ibThemeSelect.value = appState.theme.themeId;
      }}

      // Tick every 500ms for clock, stream elapsed timer & Pomodoro phase completion
      setInterval(() => {{
        const nowMs = Date.now();
        const tick = Engine.tickPomodoro(appState, nowMs);
        if (tick.phaseChanged) {{
          appState = bridge.publishState(tick.state);
          Engine.playWebAudioChime(
            appState.pomodoro.chimePreset,
            appState.pomodoro.chimeVolume,
            appState.pomodoro.chimeMuted
          );
        }}
        renderAll(nowMs);
      }}, 500);

      // Auto-hide OBS Interact Floating Controls
      let hideTimer = null;
      function revealInteractBar() {{
        interactBar.classList.add("is-visible");
        clearTimeout(hideTimer);
        hideTimer = setTimeout(() => {{
          const activeTag = document.activeElement && document.activeElement.tagName;
          if (activeTag === "INPUT" || activeTag === "SELECT" || ibDrawer.classList.contains("is-open")) {{
            return;
          }}
          interactBar.classList.remove("is-visible");
        }}, 2600);
      }}

      window.addEventListener("mousemove", revealInteractBar);
      window.addEventListener("mouseleave", () => {{
        if (!ibDrawer.classList.contains("is-open")) {{
          interactBar.classList.remove("is-visible");
        }}
      }});

      document.getElementById("ibHideBtn").addEventListener("click", () => {{
        ibDrawer.classList.remove("is-open");
        interactBar.classList.remove("is-visible");
      }});

      document.getElementById("ibDrawerToggle").addEventListener("click", () => {{
        ibDrawer.classList.toggle("is-open");
      }});

      document.querySelectorAll(".mode-btn").forEach((btn) => {{
        btn.addEventListener("click", () => {{
          commitState(Engine.setActiveMode(appState, btn.dataset.mode));
        }});
      }});

      document.getElementById("ibNextSong").addEventListener("click", () => {{
        commitState(Engine.advanceToNextSong(appState, Date.now()));
      }});

      document.getElementById("ibPrevSong").addEventListener("click", () => {{
        commitState(Engine.rewindToPreviousSong(appState));
      }});

      document.getElementById("ibPomoToggle").addEventListener("click", () => {{
        const next = appState.pomodoro.isRunning
          ? Engine.pausePomodoro(appState, Date.now())
          : Engine.startPomodoro(appState, Date.now());
        commitState(next);
      }});

      document.getElementById("ibStreamTimerBtn").addEventListener("click", () => {{
        const next = appState.streamTimer.isRunning
          ? Engine.pauseStreamTimer(appState, Date.now())
          : Engine.startStreamTimer(appState, Date.now());
        commitState(next);
      }});

      document.getElementById("ibAddSongBtn").addEventListener("click", () => {{
        const titleEl = document.getElementById("ibSongTitle");
        const artistEl = document.getElementById("ibSongArtist");
        const res = Engine.addSong(
          appState,
          {{ title: titleEl.value, artist: artistEl.value }},
          EDITION
        );
        if (res.error) {{
          ibStatusMsg.textContent = res.error;
          return;
        }}
        titleEl.value = "";
        artistEl.value = "";
        ibStatusMsg.textContent = "曲を追加しました！";
        commitState(res.state);
      }});

      document.getElementById("ibCopyTsBtn").addEventListener("click", async () => {{
        if (EDITION !== "pro") {{
          ibStatusMsg.textContent = "YouTubeタイムスタンプ1クリック出力はPro版の限定機能です！";
          return;
        }}
        const text = Engine.generateYoutubeTimestampList(appState);
        try {{
          await navigator.clipboard.writeText(text);
          ibStatusMsg.textContent = "YouTube用タイムスタンプをコピーしました！";
        }} catch (_e) {{
          ibStatusMsg.textContent = text;
        }}
      }});

      ibThemeSelect.addEventListener("change", () => {{
        const res = Engine.setTheme(appState, ibThemeSelect.value, EDITION);
        if (res.error) {{
          ibStatusMsg.textContent = res.error;
          ibThemeSelect.value = appState.theme.themeId;
          return;
        }}
        commitState(res.state);
      }});

      renderAll(Date.now());
    }})();
  </script>
</body>
</html>
"""


def build_dock_html(edition: str) -> str:
    """Build standalone `dock.html` (OBS Custom Browser Dock)."""
    engine_js = load_inline_engine_js()
    is_pro = edition == "pro"
    badge_text = "PRO FULL PACK" if is_pro else "FREE LITE"

    pro_upsell_banner = (
        ""
        if is_pro
        else f"""
      <div class="upsell-strip">
        <span>✨ <strong>Pro版 (¥680)</strong> で全6テーマ・曲数無制限・タイムスタンプ自動生成を解放</span>
        <a href="{BOOTH_URL}" target="_blank" rel="noopener noreferrer" class="upsell-link">BOOTHで見る ↗</a>
      </div>
    """
    )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>OBS Custom Dock ({badge_text}) — 歌枠＆ポモドーロ操作パネル | peco</title>
  <style>
    :root {{
      --bg: #0B101B;
      --panel: #131C2E;
      --panel-alt: #1A263D;
      --border: rgba(148, 163, 184, 0.22);
      --text: #F8FAFC;
      --muted: #94A3B8;
      --accent: #38BDF8;
      --accent-strong: #0284C7;
      --pink: #F472B6;
      --green: #34D399;
      --amber: #FBBF24;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      padding: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Yu Gothic UI", system-ui, sans-serif;
      font-size: 13px;
    }}
    .dock-shell {{
      max-width: 540px;
      margin: 0 auto;
      padding: 12px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .dock-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 8px 12px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
    }}
    .brand-title {{
      font-weight: 900;
      font-size: 13px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .sync-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 8px var(--green);
    }}
    .edition-pill {{
      font-size: 10px;
      font-weight: 900;
      letter-spacing: 0.06em;
      padding: 3px 8px;
      border-radius: 999px;
      background: {"rgba(52, 211, 153, 0.18)" if is_pro else "rgba(56, 189, 248, 0.18)"};
      color: {"#34D399" if is_pro else "#38BDF8"};
      border: 1px solid {"rgba(52, 211, 153, 0.4)" if is_pro else "rgba(56, 189, 248, 0.4)"};
    }}
    .upsell-strip {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      background: rgba(244, 114, 182, 0.12);
      border: 1px solid rgba(244, 114, 182, 0.35);
      border-radius: 10px;
      padding: 8px 11px;
      font-size: 11.5px;
    }}
    .upsell-link {{
      color: #F9A8D4;
      font-weight: 800;
      text-decoration: none;
      white-space: nowrap;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px;
    }}
    .panel-title {{
      font-size: 12px;
      font-weight: 800;
      color: var(--muted);
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .grid-4 {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 6px;
    }}
    .grid-3 {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px;
    }}
    .row {{
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }}
    button, select, input, textarea {{
      font: inherit;
    }}
    .btn {{
      appearance: none;
      border: 1px solid var(--border);
      background: var(--panel-alt);
      color: var(--text);
      border-radius: 8px;
      padding: 7px 10px;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.15s ease, border-color 0.15s ease;
    }}
    .btn:hover {{
      border-color: var(--accent);
    }}
    .btn.is-active {{
      background: var(--accent);
      color: #062235;
      border-color: var(--accent);
      font-weight: 900;
    }}
    .btn-primary {{
      background: var(--accent-strong);
      border-color: var(--accent);
      color: #FFFFFF;
      font-weight: 900;
    }}
    .btn-primary:hover {{
      background: #0369A1;
    }}
    .btn-hero {{
      width: 100%;
      padding: 11px 14px;
      font-size: 14px;
      border-radius: 10px;
    }}
    .tab-bar {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 5px;
      background: var(--panel);
      padding: 5px;
      border-radius: 11px;
      border: 1px solid var(--border);
    }}
    .tab-btn {{
      border: none;
      background: transparent;
      color: var(--muted);
      padding: 8px 4px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 800;
      cursor: pointer;
    }}
    .tab-btn.is-active {{
      background: var(--panel-alt);
      color: var(--text);
      box-shadow: inset 0 0 0 1px var(--accent);
    }}
    .tab-pane {{
      display: none;
      flex-direction: column;
      gap: 10px;
    }}
    .tab-pane.is-active {{
      display: flex;
    }}
    .input {{
      width: 100%;
      background: #0B111E;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 7px 9px;
      font-size: 12.5px;
    }}
    .input:focus {{
      outline: none;
      border-color: var(--accent);
    }}
    .song-item {{
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 7px 8px;
      border-radius: 8px;
      background: var(--panel-alt);
      border: 1px solid transparent;
      margin-bottom: 5px;
    }}
    .song-item.is-current {{
      border-color: var(--accent);
      background: rgba(56, 189, 248, 0.13);
    }}
    .song-item.is-sung {{
      opacity: 0.65;
    }}
    .song-item-main {{
      flex: 1;
      min-width: 0;
    }}
    .song-item-title {{
      font-weight: 800;
      font-size: 12.5px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .song-item-sub {{
      font-size: 11px;
      color: var(--muted);
    }}
    .mini-btn {{
      padding: 4px 7px;
      font-size: 11px;
      border-radius: 6px;
    }}
    .theme-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 7px;
    }}
    .theme-swatch {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      border-radius: 9px;
      background: var(--panel-alt);
      border: 1px solid var(--border);
      cursor: pointer;
      text-align: left;
      color: var(--text);
    }}
    .theme-swatch.is-active {{
      border-color: var(--accent);
      box-shadow: 0 0 0 1px var(--accent);
    }}
    .swatch-dot {{
      width: 20px;
      height: 20px;
      border-radius: 6px;
      flex-shrink: 0;
      border: 1px solid rgba(255,255,255,0.25);
    }}
    .toast-bar {{
      font-size: 11.5px;
      color: var(--amber);
      min-height: 17px;
      font-weight: 700;
    }}
    .timer-readout {{
      font-size: 22px;
      font-weight: 900;
      font-variant-numeric: tabular-nums;
      color: var(--accent);
    }}
  </style>
</head>
<body>
  <div class="dock-shell">
    <header class="dock-header">
      <div class="brand-title">
        <span class="sync-dot" title="OBS Browser Source リアルタイム同期中"></span>
        <span>歌枠＆ポモドーロ操作ドック</span>
      </div>
      <div class="row" style="gap:6px;">
        <button type="button" id="btnToggleLang" class="btn mini-btn" title="Switch Language (EN / JP)">🌐 EN/JP</button>
        <span class="edition-pill">{badge_text}</span>
      </div>
    </header>

    {pro_upsell_banner}

    <!-- 配信画面の表示モード＆レイアウト切替 -->
    <section class="panel">
      <div class="panel-title">
        <span>📺 オーバーレイ表示モード</span>
        <span id="toastMsg" class="toast-bar"></span>
      </div>
      <div class="grid-4" style="margin-bottom:8px;">
        <button type="button" class="btn ov-mode-btn" data-mode="utawaku">🎤 歌枠</button>
        <button type="button" class="btn ov-mode-btn" data-mode="pomodoro">⏱ ポモドーロ</button>
        <button type="button" class="btn ov-mode-btn" data-mode="clock">🕒 時計・タグ</button>
        <button type="button" class="btn ov-mode-btn" data-mode="all_in_one">✨ 同時表示</button>
      </div>
      <div class="grid-3">
        <button type="button" class="btn ov-pos-btn" data-pos="left">⬅ 左寄せ配置</button>
        <button type="button" class="btn ov-pos-btn" data-pos="right">➡ 右寄せ配置</button>
        <button type="button" class="btn ov-pos-btn" data-pos="compact">▬ 下部ワイド</button>
      </div>
    </section>

    <!-- 操作タブ -->
    <nav class="tab-bar" aria-label="機能タブ">
      <button type="button" class="tab-btn is-active" data-tab="tab-utawaku">🎤 セトリ</button>
      <button type="button" class="tab-btn" data-tab="tab-pomo">⏱ ポモドーロ</button>
      <button type="button" class="tab-btn" data-tab="tab-clock">🕒 時計・タグ</button>
      <button type="button" class="tab-btn" data-tab="tab-theme">🎨 テーマ</button>
    </nav>

    <!-- TAB 1: 歌枠セトリ & YouTubeタイムスタンプ -->
    <div id="tab-utawaku" class="tab-pane is-active">
      <section class="panel">
        <button type="button" id="btnNextSong" class="btn btn-primary btn-hero">▶ 次の曲へ進む（この曲を開始）</button>
        <div class="row" style="margin-top:8px;">
          <button type="button" id="btnPrevSong" class="btn" style="flex:1;">⏮ 前の曲へ戻す</button>
          <button type="button" id="btnResetSongs" class="btn" style="flex:1;">↺ 未歌唱に戻す</button>
        </div>
      </section>

      <!-- YouTube概要欄・コメント用タイムスタンプ自動生成 -->
      <section class="panel">
        <div class="panel-title">
          <span>⏱ 配信経過＆YouTubeタイムスタンプ自動記録</span>
          <span class="edition-pill">{"PRO ACTIVE" if is_pro else "PRO機能"}</span>
        </div>
        <div class="row" style="justify-content:space-between; margin-bottom:8px;">
          <span id="streamElapsedReadout" class="timer-readout">0:05:12</span>
          <div class="row">
            <button type="button" id="btnStreamToggle" class="btn btn-primary">🔴 配信計測スタート</button>
            <button type="button" id="btnStreamReset" class="btn">0リセット</button>
          </div>
        </div>
        <div class="row" style="margin-bottom:8px;">
          <span style="font-size:11px;color:var(--muted);">開始ズレ微調整 (<strong id="offsetReadout">±0s</strong>):</span>
          <button type="button" class="btn mini-btn offset-btn" data-delta="-10">-10s</button>
          <button type="button" class="btn mini-btn offset-btn" data-delta="-5">-5s</button>
          <button type="button" class="btn mini-btn offset-btn" data-delta="-1">-1s</button>
          <button type="button" class="btn mini-btn offset-btn" data-delta="1">+1s</button>
          <button type="button" class="btn mini-btn offset-btn" data-delta="5">+5s</button>
          <button type="button" class="btn mini-btn offset-btn" data-delta="10">+10s</button>
        </div>
        <textarea id="ytTimestampBox" class="input" rows="4" readonly style="font-family:monospace;font-size:11.5px;margin-bottom:7px;"></textarea>
        <button type="button" id="btnCopyYtTimestamps" class="btn btn-primary" style="width:100%;">📋 YouTube概要欄・コメント用タイムスタンプをコピー</button>
      </section>

      <!-- 曲追加 & セトリ一覧 -->
      <section class="panel">
        <div class="panel-title">
          <span>🎵 セットリスト編集</span>
          <span id="songCountLabel">0 / 5</span>
        </div>
        <div class="row" style="margin-bottom:6px;">
          <input id="inputStreamTitle" class="input" placeholder="枠タイトル (例: 🎤 歌枠 SINGING STREAM)" />
        </div>
        <div class="row" style="margin-bottom:8px;">
          <input id="inputSongTitle" class="input" style="flex:1.2;" placeholder="曲名 (例: アイドル)" />
          <input id="inputSongArtist" class="input" style="flex:1;" placeholder="歌手名 (例: YOASOBI)" />
          <button type="button" id="btnAddSong" class="btn btn-primary">＋追加</button>
        </div>

        <details style="margin-bottom:10px;">
          <summary style="cursor:pointer;font-size:12px;font-weight:800;color:var(--accent);">📝 1行ずつ一括貼付 (曲名 / アーティスト) {"" if is_pro else "🔒Pro"}</summary>
          <div style="margin-top:7px;">
            <textarea id="bulkPasteBox" class="input" rows="4" placeholder="アイドル / YOASOBI&#10;怪獣の花唄 / Vaundy&#10;残酷な天使のテーゼ / 高橋洋子"></textarea>
            <div class="row" style="margin-top:6px;">
              <button type="button" id="btnBulkAppend" class="btn btn-primary" style="flex:1;">末尾に一括追加</button>
              <button type="button" id="btnBulkReplace" class="btn" style="flex:1;">セトリを入れ替え</button>
            </div>
          </div>
        </details>

        <div id="songListContainer"></div>
      </section>
    </div>

    <!-- TAB 2: ポモドーロ & タスク -->
    <div id="tab-pomo" class="tab-pane">
      <section class="panel">
        <div class="panel-title">
          <span>⏱ 作業・勉強ポモドーロタイマー</span>
          <span id="pomoPhaseLabel">WORK · SET 1/4</span>
        </div>
        <div class="row" style="justify-content:space-between; margin-bottom:10px;">
          <span id="pomoTimeReadout" class="timer-readout">25:00</span>
          <div class="row">
            <button type="button" id="btnPomoStartPause" class="btn btn-primary">▶ スタート</button>
            <button type="button" id="btnPomoSkip" class="btn">⏭ 次へ</button>
            <button type="button" id="btnPomoReset" class="btn">↺ リセット</button>
          </div>
        </div>

        <div class="panel-title"><span>⚡ 時間プリセット {"" if is_pro else "(カスタムは🔒Pro)"}</span></div>
        <div class="grid-3" style="margin-bottom:8px;">
          <button type="button" class="btn pomo-preset-btn" data-work="25" data-break="5">25m / 5m</button>
          <button type="button" class="btn pomo-preset-btn" data-work="50" data-break="10">50m / 10m</button>
          <button type="button" class="btn pomo-preset-btn" data-work="45" data-break="15">45m / 15m</button>
        </div>
        <div class="grid-3" style="margin-bottom:10px;">
          <label style="font-size:11px;color:var(--muted);">作業(分)<input id="numWorkMin" type="number" min="1" max="180" class="input" /></label>
          <label style="font-size:11px;color:var(--muted);">小休憩(分)<input id="numBreakMin" type="number" min="1" max="90" class="input" /></label>
          <label style="font-size:11px;color:var(--muted);">長休憩(分)<input id="numLongMin" type="number" min="1" max="120" class="input" /></label>
        </div>

        <div class="panel-title"><span>🔔 チャイム音 (WebAudio内蔵・MP3不要)</span></div>
        <div class="row" style="margin-bottom:6px;">
          <select id="selectChimePreset" class="input" style="flex:1;">
            <option value="crystal_bell">Crystal Bell (クリスタルベル)</option>
            <option value="lofi_rhodes">Lo-Fi Rhodes (チルエレピ和音)</option>
            <option value="retro_8bit">8-Bit Chime (レトロピコピコ音)</option>
          </select>
          <button type="button" id="btnTestChime" class="btn">🔔 試聴</button>
        </div>
        <div class="row">
          <label style="font-size:11.5px;display:flex;align-items:center;gap:5px;">
            <input type="checkbox" id="chkChimeMute" /> ミュート
          </label>
          <input type="range" id="rangeChimeVol" min="0" max="100" value="65" style="flex:1;" />
        </div>
      </section>

      <section class="panel">
        <div class="panel-title"><span>✅ 作業タスク (TODOリスト)</span></div>
        <div class="row" style="margin-bottom:8px;">
          <input id="inputTodoText" class="input" style="flex:1;" placeholder="今日やること (例: ラフ線画仕上げ)" />
          <button type="button" id="btnAddTodo" class="btn btn-primary">＋追加</button>
        </div>
        <div id="todoListContainer"></div>
      </section>
    </div>

    <!-- TAB 3: 時計・ハッシュタグ・お知らせ -->
    <div id="tab-clock" class="tab-pane">
      <section class="panel">
        <div class="panel-title"><span>🕒 時計・ハッシュタグ・流れるメッセージ設定</span></div>
        <label style="display:block;font-size:11.5px;color:var(--muted);margin-bottom:4px;">配信ハッシュタグ</label>
        <input id="inputHashtag" class="input" style="margin-bottom:8px;" placeholder="#歌枠 #VTuber" />

        <label style="display:block;font-size:11.5px;color:var(--muted);margin-bottom:4px;">スクロールお知らせメッセージ (時計ボード下部)</label>
        <textarea id="inputMarquee" class="input" rows="3" style="margin-bottom:8px;"></textarea>

        <div class="row" style="gap:14px;">
          <label style="display:flex;align-items:center;gap:6px;font-size:12px;">
            <input type="checkbox" id="chkShowSeconds" /> 秒(:SS)を表示
          </label>
          <label style="display:flex;align-items:center;gap:6px;font-size:12px;">
            <input type="checkbox" id="chkCornerClock" /> 歌枠/ポモ中もミニ時計を表示
          </label>
        </div>
      </section>
    </div>

    <!-- TAB 4: テーマ & JSONプリセット -->
    <div id="tab-theme" class="tab-pane">
      <section class="panel">
        <div class="panel-title">
          <span>🎨 配信デザインテーマ (全6種)</span>
          <span>{"全開放済" if is_pro else "Lite: 1種 / Pro: 全6種"}</span>
        </div>
        <div id="themeSwatchGrid" class="theme-grid" style="margin-bottom:12px;"></div>

        <div class="panel-title"><span>✨ カスタムカラー＆背景透過度 {"" if is_pro else "🔒Pro"}</span></div>
        <div class="row" style="margin-bottom:8px;">
          <label style="font-size:12px;">差し色:</label>
          <input type="color" id="inputCustomAccent" value="#38BDF8" style="height:30px;width:48px;background:none;border:none;cursor:pointer;" />
          <button type="button" id="btnResetAccent" class="btn mini-btn">テーマ標準に戻す</button>
        </div>
        <div class="row">
          <label style="font-size:12px;">透過度 (<span id="opacityValLabel">86%</span>):</label>
          <input type="range" id="rangeOpacity" min="20" max="100" value="86" style="flex:1;" />
        </div>
      </section>

      <section class="panel">
        <div class="panel-title"><span>💾 セトリ＆設定プリセット保存・読込 {"" if is_pro else "🔒Pro"}</span></div>
        <div class="row">
          <button type="button" id="btnExportJson" class="btn btn-primary" style="flex:1;">⬇ JSON保存</button>
          <label class="btn" style="flex:1;text-align:center;">
            ⬆ JSON読込
            <input type="file" id="fileImportJson" accept=".json,application/json" style="display:none;" />
          </label>
        </div>
      </section>
    </div>
  </div>

  <script>
    {SHARED_I18N_JS}
    const EDITION = resolvePecoEdition("{edition}");
    const UI_LANG = resolvePecoLang();
    {engine_js}

    (function initDockApp() {{
      applyDockI18nAndEdition(EDITION, UI_LANG);
      const langBtn = document.getElementById("btnToggleLang");
      if (langBtn) {{
        langBtn.addEventListener("click", () => {{
          const next = UI_LANG === "en" ? "ja" : "en";
          localStorage.setItem("peco_obs_ui_lang", next);
          const u = new URL(window.location.href);
          u.searchParams.set("lang", next);
          window.location.href = u.toString();
        }});
      }}
      const Engine = window.PecoObsEngine;
      const toastEl = document.getElementById("toastMsg");
      let appState = null;

      function showToast(msg) {{
        toastEl.textContent = msg;
        clearTimeout(showToast._t);
        showToast._t = setTimeout(() => {{
          toastEl.textContent = "";
        }}, 3400);
      }}

      const bridge = Engine.createSyncBridge({{
        edition: EDITION,
        onStateReceived: (st) => {{
          appState = st;
          renderDockUI(Date.now());
        }},
      }});

      appState = bridge.loadInitialState();

      function commit(nextState) {{
        appState = bridge.publishState(nextState);
        renderDockUI(Date.now());
      }}

      // Tabs
      document.querySelectorAll(".tab-btn").forEach((btn) => {{
        btn.addEventListener("click", () => {{
          document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("is-active"));
          document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("is-active"));
          btn.classList.add("is-active");
          document.getElementById(btn.dataset.tab).classList.add("is-active");
        }});
      }});

      // Mode & Position buttons
      document.querySelectorAll(".ov-mode-btn").forEach((btn) => {{
        btn.addEventListener("click", () => {{
          const targetMode = btn.dataset.mode;
          const primary = targetMode === "pomodoro" ? "pomodoro" : targetMode === "utawaku" ? "utawaku" : appState.allInOnePrimary;
          commit(Engine.setActiveMode(appState, targetMode, primary));
        }});
      }});

      document.querySelectorAll(".ov-pos-btn").forEach((btn) => {{
        btn.addEventListener("click", () => {{
          commit(Engine.setOverlayPosition(appState, btn.dataset.pos));
        }});
      }});

      // Utawaku Controls
      document.getElementById("btnNextSong").addEventListener("click", () => {{
        commit(Engine.advanceToNextSong(appState, Date.now()));
      }});
      document.getElementById("btnPrevSong").addEventListener("click", () => {{
        commit(Engine.rewindToPreviousSong(appState));
      }});
      document.getElementById("btnResetSongs").addEventListener("click", () => {{
        commit(Engine.resetSetlistProgress(appState));
        showToast("セトリ進行をリセットしました");
      }});

      // Stream Timer & Timestamps
      document.getElementById("btnStreamToggle").addEventListener("click", () => {{
        const next = appState.streamTimer.isRunning
          ? Engine.pauseStreamTimer(appState, Date.now())
          : Engine.startStreamTimer(appState, Date.now());
        commit(next);
      }});
      document.getElementById("btnStreamReset").addEventListener("click", () => {{
        commit(Engine.resetStreamTimer(appState));
        showToast("配信経過タイマーを0:00:00にリセットしました");
      }});
      document.querySelectorAll(".offset-btn").forEach((btn) => {{
        btn.addEventListener("click", () => {{
          const res = Engine.adjustStreamOffset(appState, Number(btn.dataset.delta), EDITION);
          if (res.error) return showToast(res.error);
          commit(res.state);
        }});
      }});
      document.getElementById("btnCopyYtTimestamps").addEventListener("click", async () => {{
        if (EDITION !== "pro") {{
          showToast("YouTubeタイムスタンプ自動出力はPro版の機能です！");
          return;
        }}
        const text = Engine.generateYoutubeTimestampList(appState);
        try {{
          await navigator.clipboard.writeText(text);
          showToast("タイムスタンプをコピーしました！");
        }} catch (_err) {{
          document.getElementById("ytTimestampBox").select();
          document.execCommand("copy");
          showToast("タイムスタンプをコピーしました！");
        }}
      }});

      document.getElementById("inputStreamTitle").addEventListener("change", (e) => {{
        commit(Engine.updateSetlistOptions(appState, {{ streamTitle: e.target.value }}));
      }});

      document.getElementById("btnAddSong").addEventListener("click", () => {{
        const tEl = document.getElementById("inputSongTitle");
        const aEl = document.getElementById("inputSongArtist");
        const res = Engine.addSong(appState, {{ title: tEl.value, artist: aEl.value }}, EDITION);
        if (res.error) return showToast(res.error);
        tEl.value = "";
        aEl.value = "";
        commit(res.state);
      }});

      function handleBulk(replace) {{
        const box = document.getElementById("bulkPasteBox");
        const res = Engine.bulkImportSongs(appState, box.value, {{ replace }}, EDITION);
        if (res.error) return showToast(res.error);
        box.value = "";
        showToast(`${{res.addedCount}}曲を一括登録しました！`);
        commit(res.state);
      }}
      document.getElementById("btnBulkAppend").addEventListener("click", () => handleBulk(false));
      document.getElementById("btnBulkReplace").addEventListener("click", () => handleBulk(true));

      // Pomodoro Controls
      document.getElementById("btnPomoStartPause").addEventListener("click", () => {{
        const next = appState.pomodoro.isRunning
          ? Engine.pausePomodoro(appState, Date.now())
          : Engine.startPomodoro(appState, Date.now());
        commit(next);
      }});
      document.getElementById("btnPomoSkip").addEventListener("click", () => {{
        const tr = Engine.transitionPomodoroPhase(appState, Date.now(), appState.pomodoro.isRunning);
        Engine.playWebAudioChime(
          tr.state.pomodoro.chimePreset,
          tr.state.pomodoro.chimeVolume,
          tr.state.pomodoro.chimeMuted
        );
        commit(tr.state);
      }});
      document.getElementById("btnPomoReset").addEventListener("click", () => {{
        commit(Engine.resetPomodoroAll(appState));
      }});

      document.querySelectorAll(".pomo-preset-btn").forEach((btn) => {{
        btn.addEventListener("click", () => {{
          const res = Engine.configurePomodoro(
            appState,
            {{ workMinutes: Number(btn.dataset.work), breakMinutes: Number(btn.dataset.break) }},
            EDITION
          );
          if (res.error) return showToast(res.error);
          commit(res.state);
        }});
      }});

      ["numWorkMin", "numBreakMin", "numLongMin"].forEach((id) => {{
        document.getElementById(id).addEventListener("change", () => {{
          const res = Engine.configurePomodoro(
            appState,
            {{
              workMinutes: Number(document.getElementById("numWorkMin").value),
              breakMinutes: Number(document.getElementById("numBreakMin").value),
              longBreakMinutes: Number(document.getElementById("numLongMin").value),
            }},
            EDITION
          );
          if (res.error) {{
            showToast(res.error);
            renderDockUI(Date.now());
            return;
          }}
          commit(res.state);
        }});
      }});

      document.getElementById("selectChimePreset").addEventListener("change", (e) => {{
        const res = Engine.configurePomodoro(appState, {{ chimePreset: e.target.value }}, EDITION);
        if (res.error) {{
          showToast(res.error);
          renderDockUI(Date.now());
          return;
        }}
        commit(res.state);
      }});
      document.getElementById("btnTestChime").addEventListener("click", () => {{
        Engine.playWebAudioChime(
          appState.pomodoro.chimePreset,
          appState.pomodoro.chimeVolume,
          false
        );
      }});
      document.getElementById("chkChimeMute").addEventListener("change", (e) => {{
        commit(Engine.configurePomodoro(appState, {{ chimeMuted: e.target.checked }}, EDITION).state);
      }});
      document.getElementById("rangeChimeVol").addEventListener("input", (e) => {{
        commit(
          Engine.configurePomodoro(
            appState,
            {{ chimeVolume: Number(e.target.value) / 100 }},
            EDITION
          ).state
        );
      }});

      document.getElementById("btnAddTodo").addEventListener("click", () => {{
        const el = document.getElementById("inputTodoText");
        if (!el.value.trim()) return;
        commit(Engine.addTodo(appState, el.value));
        el.value = "";
      }});

      // Clock
      document.getElementById("inputHashtag").addEventListener("input", (e) => {{
        commit(Engine.updateClockConfig(appState, {{ hashtag: e.target.value }}));
      }});
      document.getElementById("inputMarquee").addEventListener("input", (e) => {{
        commit(Engine.updateClockConfig(appState, {{ marqueeText: e.target.value }}));
      }});
      document.getElementById("chkShowSeconds").addEventListener("change", (e) => {{
        commit(Engine.updateClockConfig(appState, {{ showSeconds: e.target.checked }}));
      }});
      document.getElementById("chkCornerClock").addEventListener("change", (e) => {{
        commit(Engine.updateClockConfig(appState, {{ showMiniClockInCorner: e.target.checked }}));
      }});

      // Theme Swatches
      const swatchGrid = document.getElementById("themeSwatchGrid");
      Object.values(Engine.THEMES).forEach((t) => {{
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "theme-swatch";
        btn.dataset.themeId = t.id;
        const locked = EDITION === "lite" && t.id !== "dark_frost";
        btn.innerHTML = `
          <span class="swatch-dot" style="background:linear-gradient(135deg, rgb(${{t.bgRgb}}) 45%, ${{t.accent}} 100%);"></span>
          <span>
            <strong style="display:block;font-size:12px;">${{locked ? "🔒 " : ""}}${{t.name}}</strong>
            <small style="color:var(--muted);font-size:10.5px;">${{t.jpName}}</small>
          </span>
        `;
        btn.addEventListener("click", () => {{
          const res = Engine.setTheme(appState, t.id, EDITION);
          if (res.error) return showToast(res.error);
          commit(res.state);
        }});
        swatchGrid.appendChild(btn);
      }});

      document.getElementById("inputCustomAccent").addEventListener("input", (e) => {{
        const res = Engine.setCustomThemeOptions(appState, {{ customAccent: e.target.value }}, EDITION);
        if (res.error) return showToast(res.error);
        commit(res.state);
      }});
      document.getElementById("btnResetAccent").addEventListener("click", () => {{
        const res = Engine.setCustomThemeOptions(appState, {{ customAccent: "" }}, EDITION);
        if (res.error) return showToast(res.error);
        commit(res.state);
      }});
      document.getElementById("rangeOpacity").addEventListener("input", (e) => {{
        const res = Engine.setCustomThemeOptions(
          appState,
          {{ opacity: Number(e.target.value) / 100 }},
          EDITION
        );
        if (res.error) return showToast(res.error);
        commit(res.state);
      }});

      // JSON Export/Import
      document.getElementById("btnExportJson").addEventListener("click", () => {{
        const res = Engine.exportPresetJson(appState, EDITION);
        if (res.error) return showToast(res.error);
        const blob = new Blob([res.json], {{ type: "application/json" }});
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "obs_utawaku_pomo_preset.json";
        a.click();
        URL.revokeObjectURL(a.href);
      }});

      document.getElementById("fileImportJson").addEventListener("change", (e) => {{
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {{
          const res = Engine.importPresetJson(String(reader.result || ""), EDITION);
          if (res.error) return showToast(res.error);
          commit(res.state);
          showToast("プリセットを読み込みました！");
        }};
        reader.readAsText(file);
      }});

      function escapeText(str) {{
        return String(str ?? "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;");
      }}

      function renderDockUI(nowMs) {{
        const rules = Engine.getEditionRules(EDITION);

        document.querySelectorAll(".ov-mode-btn").forEach((b) => {{
          b.classList.toggle("is-active", b.dataset.mode === appState.activeMode);
        }});
        document.querySelectorAll(".ov-pos-btn").forEach((b) => {{
          b.classList.toggle("is-active", b.dataset.pos === appState.overlayPosition);
        }});

        // Stream Timer
        const elapsed = Engine.getStreamElapsedSec(appState, nowMs);
        document.getElementById("streamElapsedReadout").textContent = Engine.formatHms(elapsed);
        document.getElementById("btnStreamToggle").textContent = appState.streamTimer.isRunning
          ? "⏸ 計測一時停止"
          : "🔴 配信計測スタート";
        const off = appState.streamTimer.offsetSec || 0;
        document.getElementById("offsetReadout").textContent = (off >= 0 ? "+" : "") + off + "s";

        const ytBox = document.getElementById("ytTimestampBox");
        ytBox.value =
          EDITION === "pro"
            ? Engine.generateYoutubeTimestampList(appState)
            : "🔒 Pro版で『0:05:12 アイドル / YOASOBI』形式のYouTubeチャプターリストを自動記録＆1クリックコピーできます！";

        // Songs
        const songs = appState.setlist.songs;
        document.getElementById("songCountLabel").textContent =
          EDITION === "pro" ? `${{songs.length}} 曲 (無制限)` : `${{songs.length}} / ${{rules.maxSongs}} 曲`;
        if (document.activeElement !== document.getElementById("inputStreamTitle")) {{
          document.getElementById("inputStreamTitle").value = appState.setlist.streamTitle;
        }}

        const songContainer = document.getElementById("songListContainer");
        songContainer.innerHTML = songs
          .map((s, idx) => {{
            const cls =
              s.status === "current" ? "is-current" : s.status === "sung" ? "is-sung" : "";
            const tsText =
              s.startedAtSec !== null && s.startedAtSec !== undefined
                ? ` · ${{(Engine.formatHms(Math.max(0, s.startedAtSec + off)))}}`
                : "";
            return `
              <div class="song-item ${{cls}}">
                <button type="button" class="btn mini-btn song-start-btn" data-id="${{escapeText(s.id)}}">▶</button>
                <div class="song-item-main">
                  <div class="song-item-title">#${{String(idx + 1).padStart(2, "0")}} ${{escapeText(s.title)}}</div>
                  <div class="song-item-sub">${{escapeText(s.artist || "—")}}${{tsText}}</div>
                </div>
                <button type="button" class="btn mini-btn song-up-btn" data-id="${{escapeText(s.id)}}">↑</button>
                <button type="button" class="btn mini-btn song-down-btn" data-id="${{escapeText(s.id)}}">↓</button>
                <button type="button" class="btn mini-btn song-del-btn" data-id="${{escapeText(s.id)}}">×</button>
              </div>
            `;
          }})
          .join("");

        songContainer.querySelectorAll(".song-start-btn").forEach((b) => {{
          b.addEventListener("click", () => commit(Engine.startSongById(appState, b.dataset.id, Date.now())));
        }});
        songContainer.querySelectorAll(".song-up-btn").forEach((b) => {{
          b.addEventListener("click", () => commit(Engine.moveSong(appState, b.dataset.id, "up")));
        }});
        songContainer.querySelectorAll(".song-down-btn").forEach((b) => {{
          b.addEventListener("click", () => commit(Engine.moveSong(appState, b.dataset.id, "down")));
        }});
        songContainer.querySelectorAll(".song-del-btn").forEach((b) => {{
          b.addEventListener("click", () => commit(Engine.removeSong(appState, b.dataset.id)));
        }});

        // Pomodoro
        const rem = Engine.getPomodoroRemainingSec(appState, nowMs);
        document.getElementById("pomoTimeReadout").textContent = Engine.formatMmSs(rem);
        document.getElementById("pomoPhaseLabel").textContent = `${{appState.pomodoro.phase.toUpperCase()}} · SET ${{appState.pomodoro.currentSet}}/${{appState.pomodoro.cyclesBeforeLongBreak}}`;
        document.getElementById("btnPomoStartPause").textContent = appState.pomodoro.isRunning
          ? (UI_LANG === "en" ? "⏸ Pause" : "⏸ 一時停止")
          : (UI_LANG === "en" ? "▶ Start" : "▶ スタート");
        if (document.activeElement !== document.getElementById("numWorkMin")) {{
          document.getElementById("numWorkMin").value = appState.pomodoro.workMinutes;
        }}
        if (document.activeElement !== document.getElementById("numBreakMin")) {{
          document.getElementById("numBreakMin").value = appState.pomodoro.breakMinutes;
        }}
        if (document.activeElement !== document.getElementById("numLongMin")) {{
          document.getElementById("numLongMin").value = appState.pomodoro.longBreakMinutes;
        }}
        document.getElementById("selectChimePreset").value = appState.pomodoro.chimePreset;
        document.getElementById("chkChimeMute").checked = appState.pomodoro.chimeMuted;
        document.getElementById("rangeChimeVol").value = Math.round(appState.pomodoro.chimeVolume * 100);

        // Todos
        const todoContainer = document.getElementById("todoListContainer");
        todoContainer.innerHTML = appState.pomodoro.todos
          .map(
            (t) => `
            <div class="song-item ${{t.done ? "is-sung" : ""}}">
              <button type="button" class="btn mini-btn todo-toggle-btn" data-id="${{escapeText(t.id)}}">${{t.done ? "✓" : "□"}}</button>
              <div class="song-item-main"><div class="song-item-title">${{escapeText(t.text)}}</div></div>
              <button type="button" class="btn mini-btn todo-del-btn" data-id="${{escapeText(t.id)}}">×</button>
            </div>
          `
          )
          .join("");
        todoContainer.querySelectorAll(".todo-toggle-btn").forEach((b) => {{
          b.addEventListener("click", () => commit(Engine.toggleTodo(appState, b.dataset.id)));
        }});
        todoContainer.querySelectorAll(".todo-del-btn").forEach((b) => {{
          b.addEventListener("click", () => commit(Engine.removeTodo(appState, b.dataset.id)));
        }});

        // Clock
        if (document.activeElement !== document.getElementById("inputHashtag")) {{
          document.getElementById("inputHashtag").value = appState.clock.hashtag;
        }}
        if (document.activeElement !== document.getElementById("inputMarquee")) {{
          document.getElementById("inputMarquee").value = appState.clock.marqueeText;
        }}
        document.getElementById("chkShowSeconds").checked = appState.clock.showSeconds;
        document.getElementById("chkCornerClock").checked = appState.showMiniClockInCorner;

        // Theme
        document.querySelectorAll(".theme-swatch").forEach((sw) => {{
          sw.classList.toggle("is-active", sw.dataset.themeId === appState.theme.themeId);
        }});
        const effTheme = Engine.resolveEffectiveTheme(appState);
        document.getElementById("inputCustomAccent").value = effTheme.accent;
        document.getElementById("rangeOpacity").value = Math.round(effTheme.opacity * 100);
        document.getElementById("opacityValLabel").textContent = `${{Math.round(effTheme.opacity * 100)}}%`;
      }}

      setInterval(() => {{
        const nowMs = Date.now();
        const tick = Engine.tickPomodoro(appState, nowMs);
        if (tick.phaseChanged) {{
          appState = bridge.publishState(tick.state);
        }}
        // Refresh dynamic timer readouts cleanly
        document.getElementById("streamElapsedReadout").textContent = Engine.formatHms(
          Engine.getStreamElapsedSec(appState, nowMs)
        );
        document.getElementById("pomoTimeReadout").textContent = Engine.formatMmSs(
          Engine.getPomodoroRemainingSec(appState, nowMs)
        );
      }}, 500);

      renderDockUI(Date.now());
    }})();
  </script>
</body>
</html>
"""


def build_readme_txt(edition: str) -> str:
    """Build Japanese 30-second OBS setup guide (`README_使い方_30秒導入.txt`)."""
    is_pro = edition == "pro"
    tier_title = "Pro フルパック (全6テーマ・曲数無制限・タイムスタンプ自動生成)" if is_pro else "Lite 無料体験版"

    return f"""======================================================================
『OBS 歌枠セトリ＆作業ポモドーロ・時計 オールインワン透過オーバーレイ＋操作ドック』
 エディション: {tier_title} (v1.0)
 制作: peco ({BOOTH_URL})
======================================================================

ダウンロードありがとうございます！
本ツールは Windows / Mac 両方の OBS Studio で、サーバー通信ゼロ・完全ブラウザ内保存で
すぐに使える「歌枠セットリスト」「YouTubeタイムスタンプ自動生成」「作業ポモドーロ」「配信時計」
オールインワン透過オーバーレイです。

お好みに合わせて【導入方法A】または【導入方法B】のどちらでも30秒で導入できます！

----------------------------------------------------------------------
■ 導入方法A：【完全オフライン・1ファイル30秒導入】（一番かんたん！ネット不要）
----------------------------------------------------------------------
1. このZIPを好きなフォルダに展開（解凍）します。
2. OBS Studio の「ソース」欄で「＋」→「ブラウザ」を追加します。
3. 「ローカルファイル」にチェックを入れ、展開した『overlay.html』を選択します。
   - 幅 (Width): 1920
   - 高さ (Height): 1080
   に設定して「OK」を押します（背景は自動で綺麗に透過されます！）。
4. 【操作のしかた】
   OBSのソース一覧で、今追加したブラウザソースを右クリック →『対話 (Interact)』を開きます。
   マウスを動かすと右下に「🎛 OBS対話ミニ操作バー」がふわっと現れ、
   曲送り・配信タイマー計測・ポモドーロ開始・テーマ切替・曲追加がその場で完結します！
   ※マウスを離すと約2.5秒で完全に消えるため、視聴者の配信画面には一切映りません。

----------------------------------------------------------------------
■ 導入方法B：【OBSカスタムブラウザドック＋オーバーレイ連動導入】
----------------------------------------------------------------------
OBSの画面横に「専用リモコン（カスタムドック）」を常駐させたい場合の方法です。

【B-1. URLコピペ30秒導入（Lite版 / 同一オリジン即時連動）】
OBS内蔵ブラウザの同一オリジン機能（BroadcastChannel + localStorage）により、
外部サーバーへデータを一切送信せずミリ秒単位でドックと配信画面が連動します。
- ① OBS「ソース」→「ブラウザ」（1920×1080）のURL欄に貼付:
  {PAGES_BASE_URL}/overlay.html
- ② OBS上部メニュー「ドック」→「カスタムブラウザドック」のURL欄に貼付:
  {PAGES_BASE_URL}/dock.html

【B-2. ローカルProフルパックをカスタムドックで連動させる場合】
※OBS(Chromium)の仕様上、`file://` の別ファイル間はブラウザ保護によりストレージが分離される場合があります。
ローカルフォルダで『dock.html』と『overlay.html』を連動させる場合は：
- 方法1（手軽）：上記の【導入方法A：overlay.html の「対話(Interact)」ウィンドウ】を使う（設定不要で全Pro機能が100%動作します！）
- 方法2（ドック常駐）：展開したフォルダでターミナル/コマンドプロンプトから
  `python3 -m http.server 18765 --bind 127.0.0.1`（Windowsは `py -m http.server 18765 --bind 127.0.0.1`）
  を起動し、OBSのブラウザソースに `http://127.0.0.1:18765/overlay.html`、
  カスタムドックに `http://127.0.0.1:18765/dock.html` を登録すると、完全オフラインで超高速連動します！

----------------------------------------------------------------------
■ 歌枠タイムスタンプ自動生成のコツ（Pro機能）
----------------------------------------------------------------------
1. 配信開始と同時にドックの『🔴 配信計測スタート』をクリックします。
2. 歌い始めるタイミングで『▶ 次の曲へ進む（この曲を開始）』を押すだけで、
   `0:05:12 アイドル / YOASOBI` のように経過時間が自動記録されます！
3. もしOBSの配信開始ボタンと数秒ズレていても、『-10s / -5s / -1s / +1s / +5s / +10s』ボタンで
   全曲まとめて一発補正できます。
4. 配信終了後、『📋 YouTube概要欄・コメント用タイムスタンプをコピー』を押して貼るだけ！
   （先頭に `0:00:00 配信開始 / OP` が自動付与されるため、YouTubeチャプターが自動有効化されます）

----------------------------------------------------------------------
■ クレジット・利用規約まとめ
----------------------------------------------------------------------
・個人VTuber / 企業・事務所所属VTuber / YouTube収益化・スパチャ・メンバーシップ・Twitchサブスク配信すべて商用利用OK！
・クレジット表記・使用報告は任意です（概要欄に BOOTH URL `{BOOTH_URL}` を記載いただけると制作者が泣いて喜びます！）。
・本ファイル自体の再配布・転売・自作発言のみ禁止となります。
"""


def build_license_txt(edition: str) -> str:
    """Build commercial stream friendly license file (`LICENSE_利用規約.txt`)."""
    edition_name = "Pro フルパック" if edition == "pro" else "Lite 無料体験版"
    return f"""======================================================================
利用規約・ライセンス ({edition_name})
制作: peco ({BOOTH_URL})
======================================================================

【OKなこと（許諾事項）】
1. YouTube / Twitch / ツイキャス / ニコニコ生放送 / TikTok Live / IRIAM 等の配信・動画での使用
2. スーパーチャット・メンバーシップ・広告収益・案件配信などの収益化・商用配信での使用
3. 個人勢・事務所/企業所属ライバー・法人チャンネルでの使用
4. ご自身の配信画面に合わせたCSS/HTMLの色・サイズ・フォント改変（個人利用の範囲内）

【NGなこと（禁止事項）】
1. 本商品のデータ（HTML/コード/画像/改変物を含む）の二次配布、転売、公開リポジトリへのアップロード
2. 自作発言、公序良俗に反する配信・誹謗中傷目的での使用

【免責事項】
本ツールの利用により生じたいかなる損害・配信トラブルについても制作者(peco)は責任を負いかねます。
事前にOBS上で動作確認のうえご利用ください。
"""


def build_showcase_index_html() -> str:
    """Build public interactive showcase (`site/index.html`) following `The page is the object` direction."""
    engine_js = load_inline_engine_js()

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>OBS 歌枠セトリ＆作業ポモドーロ・時計 透過オーバーレイ＋操作ドック | peco</title>
  <meta name="description" content="OBSに入れるだけ！歌枠セットリスト、YouTubeタイムスタンプ1クリック自動生成、作業ポモドーロ、配信時計が1つになったVTuber・配信者向け透過オーバーレイ＆操作ドック。" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@800&family=Noto+Sans+JP:wght@400;600;800;900&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --ground: #0C111C;
      --surface: #141D2E;
      --surface-raised: #1B273D;
      --paper: #F6F8FB;
      --paper-ink: #0F172A;
      --ink: #F8FAFC;
      --ink-sec: #CBD5E1;
      --muted: #94A3B8;
      --accent: #38BDF8;
      --accent-ink: #062134;
      --margin: clamp(16px, 3.5vw, 44px);
    }}
    *, *::before, *::after {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      background: var(--ground);
      color: var(--ink);
      font-family: "Noto Sans JP", "Hiragino Sans", system-ui, sans-serif;
      font-size: 16px;
      line-height: 1.6;
    }}
    a {{ color: inherit; }}

    .page-wrap {{
      max-width: 1360px;
      margin: 0 auto;
      padding: 0 var(--margin);
    }}

    /* Plain Navigation Bar */
    .top-nav {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 22px 0;
      gap: 16px;
      flex-wrap: wrap;
    }}
    .wordmark {{
      font-family: "Big Shoulders Display", "Noto Sans JP", sans-serif;
      font-weight: 800;
      font-size: 26px;
      letter-spacing: 0.02em;
      text-decoration: none;
    }}
    .nav-links {{
      display: flex;
      align-items: center;
      gap: 24px;
      flex-wrap: wrap;
      font-size: 15px;
      font-weight: 600;
    }}
    .nav-links a {{
      text-decoration: none;
      color: var(--ink-sec);
    }}
    .nav-links a:hover {{
      color: var(--accent);
    }}
    .cta-btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      background: var(--accent);
      color: var(--accent-ink);
      font-weight: 900;
      font-size: 15px;
      padding: 12px 22px;
      border-radius: 0;
      text-decoration: none;
      border: none;
      cursor: pointer;
      transition: transform 0.15s ease, background 0.15s ease;
    }}
    .cta-btn:hover {{
      background: #7DD3FC;
      transform: translateY(-1px);
    }}
    .cta-btn-secondary {{
      background: var(--surface-raised);
      color: var(--ink);
      padding: 12px 20px;
      font-weight: 800;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
    }}

    /* Hero */
    .hero-sec {{
      padding: 28px 0 96px;
    }}
    .hero-head {{
      display: grid;
      grid-template-columns: 1.25fr 0.75fr;
      gap: 32px;
      align-items: end;
      margin-bottom: 36px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(32px, 4.1vw, 56px);
      font-weight: 900;
      line-height: 1.14;
      letter-spacing: -0.02em;
    }}
    .hero-lead-col {{
      display: flex;
      flex-direction: column;
      gap: 18px;
      align-items: flex-start;
    }}
    .hero-lead {{
      margin: 0;
      font-size: 17px;
      color: var(--ink-sec);
    }}
    .hero-actions {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }}

    /* Live OBS Broadcast Stage Artefact (`data-ui`) */
    .obs-desk {{
      background: var(--surface);
      padding: 20px;
      display: grid;
      grid-template-columns: 1.55fr 1fr;
      gap: 20px;
      align-items: stretch;
    }}
    .obs-preview-monitor {{
      position: relative;
      min-height: 520px;
      background: #10192B;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 24px;
    }}
    .obs-preview-monitor.bg-checker {{
      background-color: #1A2232;
      background-image:
        linear-gradient(45deg, #232E42 25%, transparent 25%),
        linear-gradient(-45deg, #232E42 25%, transparent 25%),
        linear-gradient(45deg, transparent 75%, #232E42 75%),
        linear-gradient(-45deg, transparent 75%, #232E42 75%);
      background-size: 24px 24px;
      background-position: 0 0, 0 12px, 12px -12px, -12px 0;
    }}
    .obs-preview-monitor.bg-daylight {{
      background: #D8CFC4;
    }}
    .stage-silhouette {{
      position: absolute;
      right: 28px;
      bottom: 0;
      width: 220px;
      height: 360px;
      pointer-events: none;
      opacity: 0.32;
    }}
    .stage-toolbar {{
      position: relative;
      z-index: 3;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }}
    .stage-label {{
      font-size: 13px;
      font-weight: 800;
      color: var(--ink-sec);
      background: rgba(12, 17, 28, 0.78);
      padding: 5px 11px;
    }}
    .stage-bg-btns {{
      display: flex;
      gap: 6px;
    }}
    .stage-bg-btn {{
      border: none;
      background: rgba(12, 17, 28, 0.78);
      color: var(--ink-sec);
      font-size: 12px;
      font-weight: 700;
      padding: 5px 10px;
      cursor: pointer;
    }}
    .stage-bg-btn.is-active {{
      background: var(--accent);
      color: var(--accent-ink);
    }}
    .live-overlay-mount {{
      position: relative;
      z-index: 2;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      flex: 1;
    }}
    .live-overlay-mount.pos-right {{
      flex-direction: row-reverse;
    }}
    .live-main-col {{
      width: min(390px, 100%);
    }}

    /* Right side Live Controller inside Hero */
    .obs-live-dock {{
      background: #0E1524;
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .dock-sec-head {{
      font-size: 14px;
      font-weight: 900;
      color: var(--ink);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .ctrl-grid-4 {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 6px;
    }}
    .ctrl-grid-3 {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px;
    }}
    .ctrl-grid-2 {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 6px;
    }}
    .ctrl-btn {{
      border: none;
      background: var(--surface-raised);
      color: var(--ink);
      padding: 9px 10px;
      font-size: 13px;
      font-weight: 800;
      cursor: pointer;
      text-align: center;
    }}
    .ctrl-btn:hover {{
      background: #263654;
    }}
    .ctrl-btn.is-active {{
      background: var(--accent);
      color: var(--accent-ink);
    }}
    .ctrl-btn-big {{
      background: var(--accent);
      color: var(--accent-ink);
      padding: 12px;
      font-size: 14px;
      font-weight: 900;
      width: 100%;
      border: none;
      cursor: pointer;
    }}
    .ctrl-btn-big:hover {{
      background: #7DD3FC;
    }}
    .ts-slip {{
      background: var(--paper);
      color: var(--paper-ink);
      padding: 12px 14px;
      font-size: 13px;
      line-height: 1.55;
      white-space: pre-wrap;
      max-height: 138px;
      overflow-y: auto;
      font-variant-numeric: tabular-nums;
    }}

    /* Sections */
    .sec-block {{
      padding: 110px 0;
    }}
    .sec-alt {{
      background: var(--surface);
    }}
    h2 {{
      margin: 0 0 28px;
      font-size: clamp(26px, 3vw, 40px);
      font-weight: 900;
      line-height: 1.18;
    }}
    .two-col-asymmetric {{
      display: grid;
      grid-template-columns: 1fr 1.15fr;
      gap: 48px;
      align-items: start;
    }}
    .url-box {{
      background: var(--ground);
      padding: 18px 20px;
      margin-bottom: 16px;
    }}
    .url-box-title {{
      font-weight: 900;
      font-size: 16px;
      margin-bottom: 8px;
    }}
    .url-copy-row {{
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .url-input {{
      flex: 1;
      min-width: 220px;
      background: var(--surface);
      color: var(--ink);
      border: none;
      padding: 10px 12px;
      font-size: 14px;
    }}

    /* Menu-style Pricing Sheet */
    .menu-sheet {{
      background: var(--paper);
      color: var(--paper-ink);
      padding: clamp(24px, 4vw, 48px);
      display: grid;
      grid-template-columns: 1fr 1.2fr;
      gap: 40px;
    }}
    .tier-col h3 {{
      margin: 0 0 8px;
      font-size: 24px;
      font-weight: 900;
    }}
    .price-tag {{
      font-family: "Big Shoulders Display", sans-serif;
      font-size: 54px;
      font-weight: 800;
      line-height: 1;
      margin-bottom: 16px;
    }}
    .spec-list {{
      list-style: none;
      padding: 0;
      margin: 0 0 24px;
    }}
    .spec-list li {{
      padding: 9px 0;
      font-size: 15px;
      font-weight: 600;
    }}

    /* FAQ */
    .faq-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 28px;
    }}
    .faq-item {{
      background: var(--surface);
      padding: 24px;
    }}
    .faq-item h3 {{
      margin: 0 0 10px;
      font-size: 18px;
      font-weight: 800;
    }}
    .faq-item p {{
      margin: 0;
      color: var(--ink-sec);
      font-size: 15px;
    }}

    .site-footer {{
      padding: 64px 0 48px;
      background: #080C14;
    }}
    .footer-big {{
      font-family: "Big Shoulders Display", "Noto Sans JP", sans-serif;
      font-size: clamp(36px, 7vw, 88px);
      font-weight: 800;
      line-height: 0.95;
      margin-bottom: 20px;
    }}

    {SHARED_OVERLAY_CSS}

    @media (max-width: 980px) {{
      .hero-head,
      .obs-desk,
      .two-col-asymmetric,
      .menu-sheet,
      .faq-grid {{
        grid-template-columns: 1fr;
      }}
      .obs-preview-monitor {{
        min-height: 440px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page-wrap">
    <nav class="top-nav" aria-label="メインナビゲーション">
      <a href="#" class="wordmark">PECO OBS STUDIO TOOLS</a>
      <div class="nav-links">
        <a href="#live-demo">ライブ操作デモ</a>
        <a href="#obs-setup">30秒OBS導入</a>
        <a href="#pricing">無料版 / Pro比較</a>
        <a href="#faq">よくある質問</a>
        <a href="{BOOTH_URL}" target="_blank" rel="noopener noreferrer" class="cta-btn">BOOTHで入手 (¥0 / ¥680)</a>
      </div>
    </nav>

    <section class="hero-sec" id="live-demo">
      <div class="hero-head">
        <h1>歌枠セトリもポモドーロも、<br />OBSに貼るだけで配信完成。</h1>
        <div class="hero-lead-col">
          <p class="hero-lead">
            曲送り1クリックでYouTube用タイムスタンプを自動記録。作業ポモドーロと配信時計まで1つに統合した、VTuber・配信者向け透過オーバーレイ＆操作ドックです。
          </p>
          <div class="hero-actions">
            <a href="{BOOTH_URL}" target="_blank" rel="noopener noreferrer" class="cta-btn">BOOTHでProフルパック(¥680)・無料ローカル版を入手 ↗</a>
            <a href="{GUMROAD_URL}" target="_blank" rel="noopener noreferrer" class="cta-btn-secondary">🌐 Global English Edition on Gumroad ($12 USD) ↗</a>
            <a href="#obs-setup" class="cta-btn-secondary">今すぐOBSにURLコピペで試す</a>
          </div>
        </div>
      </div>

      <!-- 実物ライブ操作ステージ -->
      <div class="obs-desk" data-ui="obs-broadcast-desk">
        <div id="demoMonitor" class="obs-preview-monitor">
          <div class="stage-toolbar">
            <span class="stage-label">OBS 配信キャンバス実物プレビュー (1920×1080 透過対応)</span>
            <div class="stage-bg-btns">
              <button type="button" class="stage-bg-btn is-active" data-bg="night">夜配信背景</button>
              <button type="button" class="stage-bg-btn" data-bg="checker">透過チェッカー</button>
              <button type="button" class="stage-bg-btn" data-bg="daylight">昼カフェ背景</button>
            </div>
          </div>

          <div id="demoOverlayRoot" class="ov-root">
            <div id="demoOverlayMount" class="live-overlay-mount">
              <div id="demoMainSlot" class="live-main-col"></div>
              <div id="demoCornerSlot"></div>
            </div>
          </div>

          <!-- VTuber立ち絵ポジション目安シルエット -->
          <svg class="stage-silhouette" viewBox="0 0 220 360" fill="none" aria-hidden="true">
            <circle cx="115" cy="92" r="46" fill="#38BDF8" />
            <path d="M42 360C46 236 76 168 115 168C154 168 184 236 188 360H42Z" fill="#38BDF8" />
          </svg>
        </div>

        <!-- 右側：ライブ操作ドック体験パネル -->
        <div class="obs-live-dock">
          <div class="dock-sec-head">
            <span>🎛 ドック操作をここでそのまま体験</span>
            <span id="demoToast" style="font-size:12px;color:#38BDF8;"></span>
          </div>

          <div class="ctrl-grid-4">
            <button type="button" class="ctrl-btn demo-mode-btn is-active" data-mode="utawaku">歌枠</button>
            <button type="button" class="ctrl-btn demo-mode-btn" data-mode="pomodoro">ポモドーロ</button>
            <button type="button" class="ctrl-btn demo-mode-btn" data-mode="clock">時計</button>
            <button type="button" class="ctrl-btn demo-mode-btn" data-mode="all_in_one">同時表示</button>
          </div>

          <button type="button" id="demoNextSongBtn" class="ctrl-btn-big">▶ 次の曲へ進む（開始時刻を自動記録）</button>

          <div class="ctrl-grid-3">
            <button type="button" id="demoPrevSongBtn" class="ctrl-btn">⏮ 前の曲</button>
            <button type="button" id="demoPomoToggleBtn" class="ctrl-btn">⏱ ポモ開始/停止</button>
            <button type="button" id="demoChimeBtn" class="ctrl-btn">🔔 チャイム試聴</button>
          </div>

          <div class="dock-sec-head" style="margin-top:4px;">
            <span>🎨 Pro収録 全6テーマを着せ替え体験</span>
          </div>
          <div id="demoThemeBtns" class="ctrl-grid-2"></div>

          <div class="dock-sec-head" style="margin-top:4px;">
            <span>📋 YouTube概要欄タイムスタンプ自動生成 (Pro)</span>
            <button type="button" id="demoCopyTsBtn" class="ctrl-btn" style="padding:4px 10px;font-size:12px;">コピー</button>
          </div>
          <div id="demoTsSlip" class="ts-slip"></div>
        </div>
      </div>
    </section>
  </div>

  <!-- 30秒OBS導入セクション -->
  <section class="sec-block sec-alt" id="obs-setup">
    <div class="page-wrap two-col-asymmetric">
      <div>
        <h2>URLを貼るだけ、30秒でOBS導入。<br />ローカル完全オフラインZIPも用意。</h2>
        <p style="color:var(--ink-sec);margin:0 0 20px;">
          OBS内蔵ブラウザの同一オリジン同期（BroadcastChannel ＋ localStorage）を使うため、外部サーバーへの通信やアカウント登録は一切不要。さらにダウンロードZIP版ならネット接続ゼロの「対話(Interact)」1ファイル操作にも対応しています。
        </p>
        <a href="{BOOTH_URL}" target="_blank" rel="noopener noreferrer" class="cta-btn">BOOTHでローカルZIP版 (無料Lite / Pro ¥680) をDL ↗</a>
      </div>

      <div>
        <div class="url-box">
          <div class="url-box-title">① OBS「ブラウザ」ソースに貼るURL（幅 1920 × 高さ 1080・無料Lite体験）</div>
          <div class="url-copy-row">
            <input id="urlOverlayInput" class="url-input" readonly value="{PAGES_BASE_URL}/overlay.html" aria-label="OBSブラウザソースURL" />
            <button type="button" class="cta-btn copy-url-btn" data-target="urlOverlayInput">URLをコピー</button>
          </div>
        </div>

        <div class="url-box">
          <div class="url-box-title">② OBS「ドック」→「カスタムブラウザドック」に貼る操作パネルURL</div>
          <div class="url-copy-row">
            <input id="urlDockInput" class="url-input" readonly value="{PAGES_BASE_URL}/dock.html" aria-label="OBSカスタムドックURL" />
            <button type="button" class="cta-btn copy-url-btn" data-target="urlDockInput">URLをコピー</button>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- 価格・エディション比較 -->
  <section class="sec-block" id="pricing">
    <div class="page-wrap">
      <h2>まずは¥0無料版で動作確認。<br />本気配信には¥680買い切りProパック。</h2>
      <div class="menu-sheet">
        <div class="tier-col">
          <h3>Lite 無料体験版</h3>
          <div class="price-tag">¥0</div>
          <ul class="spec-list">
            <li>✓ Dark Frost（すりガラス黒）テーマ収録</li>
            <li>✓ 歌枠セットリスト最大5曲まで登録</li>
            <li>✓ 作業ポモドーロ（定番 25分 / 5分）＆TODOリスト</li>
            <li>✓ 配信時計・日付・ハッシュタグ・流れる告知バー</li>
            <li>✓ OBSカスタムドック連動 ＋ オフライン対話モード両対応</li>
          </ul>
          <a href="{BOOTH_URL}" target="_blank" rel="noopener noreferrer" class="cta-btn-secondary" style="background:#0F172A;color:#F8FAFC;">BOOTHから無料版ZIPをダウンロード ↗</a>
        </div>

        <div class="tier-col">
          <h3>Pro フルパック（買い切り）</h3>
          <div class="price-tag">¥680</div>
          <ul class="spec-list">
            <li>★ デザイナーズ全6テーマ収録（Sakura / Cyber Neon / Starlight / Latte / Pixel Retro）</li>
            <li>★ 推し色に合わせられるカスタム差し色ピッカー＆背景透過度スライダー</li>
            <li>★ セットリスト曲数無制限 ＋「曲名 / アーティスト」1行ずつ一括貼付</li>
            <li>★ YouTube概要欄・コメント用タイムスタンプ自動記録＆ズレ秒数一括補正</li>
            <li>★ ポモドーロ時間自由設定（50m/10m等）・長休憩・3種シンセチャイム・JSON保存</li>
            <li>★ 収益化・スパチャ・メンバーシップ・事務所所属VTuber商用配信フル許諾</li>
          </ul>
          <a href="{BOOTH_URL}" target="_blank" rel="noopener noreferrer" class="cta-btn" style="width:100%;">BOOTHでProフルパック(¥680)を手に入れる ↗</a>
        </div>
      </div>
    </div>
  </section>

  <!-- よくある質問 -->
  <section class="sec-block sec-alt" id="faq">
    <div class="page-wrap">
      <h2>導入前によくある質問</h2>
      <div class="faq-grid">
        <div class="faq-item">
          <h3>WindowsでもMacでもOBS Studioで動きますか？</h3>
          <p>はい。OBS Studio標準搭載のブラウザソースおよびカスタムブラウザドックのみで動作するため、Windows / macOS どちらでも外部プラグイン不要でそのまま動きます。</p>
        </div>
        <div class="faq-item">
          <h3>セットリストや作業タスクの内容が外部に送信されませんか？</h3>
          <p>一切送信されません。お使いのPCのOBSブラウザ内（BroadcastChannel と localStorage）だけで完結する設計のため、未公開の新曲セトリも安心して準備できます。</p>
        </div>
        <div class="faq-item">
          <h3>収益化済みチャンネルや事務所所属ライバーでも使えますか？</h3>
          <p>はい！個人勢・企業/事務所所属を問わず、スーパーチャットやメンバーシップを含む商用・収益化配信で追加費用なくご利用いただけます。</p>
        </div>
        <div class="faq-item">
          <h3>歌枠の開始時刻とタイマー押下がズレた場合は直せますか？</h3>
          <p>Pro版では「±1秒 / ±5秒 / ±10秒」のオフセット微調整ボタンを搭載しており、全曲のタイムスタンプをまとめて実際のアーカイブ秒数へピッタリ合わせられます。</p>
        </div>
      </div>
    </div>
  </section>

  <footer class="site-footer">
    <div class="page-wrap">
      <div class="footer-big">PECO STREAM OVERLAYS</div>
      <div style="display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;color:var(--muted);font-size:14px;">
        <span>Crafted by peco · OBS Studio Browser-Source &amp; Custom Dock Suite</span>
        <a href="{BOOTH_URL}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-weight:800;">pecopeko1011.booth.pm ↗</a>
      </div>
    </div>
  </footer>

  <script>
    {engine_js}
    {SHARED_OVERLAY_RENDERER_JS}

    (function initShowcaseDemo() {{
      const Engine = window.PecoObsEngine;
      const overlayRoot = document.getElementById("demoOverlayRoot");
      const mainSlot = document.getElementById("demoMainSlot");
      const cornerSlot = document.getElementById("demoCornerSlot");
      const tsSlip = document.getElementById("demoTsSlip");
      const toast = document.getElementById("demoToast");
      const monitor = document.getElementById("demoMonitor");

      // Interactive stage runs in Pro preview mode in-page so visitors can test all 6 themes & timestamps!
      let demoState = Engine.createDefaultState("pro");
      demoState = Engine.startStreamTimer(demoState, Date.now());

      function flash(msg) {{
        toast.textContent = msg;
        clearTimeout(flash._t);
        flash._t = setTimeout(() => {{ toast.textContent = ""; }}, 2600);
      }}

      function renderDemo(nowMs) {{
        applyThemeCssVariables(overlayRoot, demoState);
        const scene = renderFullOverlaySceneHtml(demoState, nowMs);
        mainSlot.innerHTML = scene.mainHtml;
        cornerSlot.innerHTML = scene.cornerClockHtml;
        tsSlip.textContent = Engine.generateYoutubeTimestampList(demoState);

        document.querySelectorAll(".demo-mode-btn").forEach((b) => {{
          b.classList.toggle("is-active", b.dataset.mode === demoState.activeMode);
        }});
        document.querySelectorAll(".demo-theme-btn").forEach((b) => {{
          b.classList.toggle("is-active", b.dataset.theme === demoState.theme.themeId);
        }});
      }}

      const themeGrid = document.getElementById("demoThemeBtns");
      Object.values(Engine.THEMES).forEach((t) => {{
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "ctrl-btn demo-theme-btn";
        btn.dataset.theme = t.id;
        btn.textContent = `${{t.name}} (${{t.jpName}})`;
        btn.addEventListener("click", () => {{
          demoState = Engine.setTheme(demoState, t.id, "pro").state;
          renderDemo(Date.now());
        }});
        themeGrid.appendChild(btn);
      }});

      document.querySelectorAll(".demo-mode-btn").forEach((btn) => {{
        btn.addEventListener("click", () => {{
          const m = btn.dataset.mode;
          const prim = m === "pomodoro" ? "pomodoro" : m === "utawaku" ? "utawaku" : demoState.allInOnePrimary;
          demoState = Engine.setActiveMode(demoState, m, prim);
          renderDemo(Date.now());
        }});
      }});

      document.getElementById("demoNextSongBtn").addEventListener("click", () => {{
        // Advance simulated clock by +225 sec on demo click if Songs 2+ have null timestamps so timestamp list looks awesome!
        const virtualNow = Date.now() + demoState.setlist.songs.filter((s) => s.status === "sung").length * 242000;
        demoState = Engine.advanceToNextSong(demoState, virtualNow);
        flash("次の曲を開始＆タイムスタンプを記録しました！");
        renderDemo(Date.now());
      }});

      document.getElementById("demoPrevSongBtn").addEventListener("click", () => {{
        demoState = Engine.rewindToPreviousSong(demoState);
        renderDemo(Date.now());
      }});

      document.getElementById("demoPomoToggleBtn").addEventListener("click", () => {{
        demoState = Engine.setActiveMode(demoState, "pomodoro", "pomodoro");
        demoState = demoState.pomodoro.isRunning
          ? Engine.pausePomodoro(demoState, Date.now())
          : Engine.startPomodoro(demoState, Date.now());
        renderDemo(Date.now());
      }});

      document.getElementById("demoChimeBtn").addEventListener("click", () => {{
        const preset = demoState.theme.themeId === "pixel_retro" ? "retro_8bit" : "crystal_bell";
        Engine.playWebAudioChime(preset, 0.7, false);
        flash("WebAudioチャイムを再生しました♪");
      }});

      document.getElementById("demoCopyTsBtn").addEventListener("click", async () => {{
        const text = Engine.generateYoutubeTimestampList(demoState);
        try {{
          await navigator.clipboard.writeText(text);
          flash("タイムスタンプをコピーしました！");
        }} catch (_e) {{
          flash("コピー完了！");
        }}
      }});

      document.querySelectorAll(".stage-bg-btn").forEach((btn) => {{
        btn.addEventListener("click", () => {{
          document.querySelectorAll(".stage-bg-btn").forEach((b) => b.classList.remove("is-active"));
          btn.classList.add("is-active");
          monitor.classList.remove("bg-checker", "bg-daylight");
          if (btn.dataset.bg === "checker") monitor.classList.add("bg-checker");
          if (btn.dataset.bg === "daylight") monitor.classList.add("bg-daylight");
        }});
      }});

      document.querySelectorAll(".copy-url-btn").forEach((btn) => {{
        btn.addEventListener("click", async () => {{
          const input = document.getElementById(btn.dataset.target);
          try {{
            await navigator.clipboard.writeText(input.value);
            const orig = btn.textContent;
            btn.textContent = "コピー完了！";
            setTimeout(() => {{ btn.textContent = orig; }}, 1800);
          }} catch (_e) {{
            input.select();
            document.execCommand("copy");
          }}
        }});
      }});

      setInterval(() => renderDemo(Date.now()), 1000);
      renderDemo(Date.now());
    }})();
  </script>
</body>
</html>
"""


def write_zip_bundle(zip_path: Path, folder_prefix: str, files_map: dict[str, str]) -> None:
    """Create deterministic, clean UTF-8 ZIP archive."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_name, content in files_map.items():
            arcname = f"{folder_prefix}/{rel_name}"
            zf.writestr(arcname, content.encode("utf-8"))


def build_all() -> dict[str, Path]:
    """Build Lite ZIP, Pro ZIP, and Public GitHub Pages `site/` folder."""
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    lite_overlay = build_overlay_html("lite")
    lite_dock = build_dock_html("lite")
    lite_readme = build_readme_txt("lite")
    lite_license = build_license_txt("lite")

    pro_overlay = build_overlay_html("pro")
    pro_dock = build_dock_html("pro")
    pro_readme = build_readme_txt("pro")
    pro_license = build_license_txt("pro")

    lite_zip = DIST_DIR / "obs-utawaku-pomo-lite-v1.0.zip"
    pro_zip = DIST_DIR / "obs-utawaku-pomo-pro-v1.0.zip"

    write_zip_bundle(
        lite_zip,
        "obs-utawaku-pomo-lite-v1.0",
        {
            "overlay.html": lite_overlay,
            "dock.html": lite_dock,
            "README_使い方_30秒導入.txt": lite_readme,
            "LICENSE_利用規約.txt": lite_license,
        },
    )

    write_zip_bundle(
        pro_zip,
        "obs-utawaku-pomo-pro-v1.0",
        {
            "overlay.html": pro_overlay,
            "dock.html": pro_dock,
            "README_使い方_30秒導入.txt": pro_readme,
            "LICENSE_利用規約.txt": pro_license,
        },
    )

    # Public GitHub Pages site (Interactive Demo + Hosted Lite Overlay & Dock)
    (SITE_DIR / "index.html").write_text(build_showcase_index_html(), encoding="utf-8")
    (SITE_DIR / "overlay.html").write_text(lite_overlay, encoding="utf-8")
    (SITE_DIR / "dock.html").write_text(lite_dock, encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")

    return {
        "lite_zip": lite_zip,
        "pro_zip": pro_zip,
        "site_dir": SITE_DIR,
    }


if __name__ == "__main__":
    outputs = build_all()
    for key, path in outputs.items():
        size_info = f" ({path.stat().st_size:,} bytes)" if path.is_file() else ""
        print(f"[OK] {key}: {path}{size_info}")
