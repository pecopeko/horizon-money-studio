import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { clampViewportPoint, DEFAULT_VIEWPORT } from "./coords.mjs";
import {
  PresetValidationError,
  resolveApprovedPreset,
  scoreFileInputForPreset,
} from "./presets.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const TRACK22_ROOT = path.resolve(__dirname, "..");
export const DEFAULT_CHROME_BIN =
  process.env.CHROME_BIN ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
export const DEFAULT_PROFILE_DIR = path.join(TRACK22_ROOT, ".chrome_profile");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseAttributesArray(attrList = []) {
  const out = {};
  for (let i = 0; i + 1 < attrList.length; i += 2) {
    out[attrList[i]] = attrList[i + 1];
  }
  return out;
}

export function normalizeSafeNavigationUrl(rawUrl) {
  if (typeof rawUrl !== "string") {
    throw new PresetValidationError("url must be a string");
  }
  const trimmed = rawUrl.trim();
  if (!trimmed) {
    throw new PresetValidationError("url must not be empty");
  }
  if (trimmed === "about:blank") {
    return "about:blank";
  }

  const withScheme = /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(trimmed)
    ? trimmed
    : `https://${trimmed}`;

  let parsed;
  try {
    parsed = new URL(withScheme);
  } catch {
    throw new PresetValidationError(`Invalid URL: ${trimmed}`);
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new PresetValidationError(
      `Disallowed URL scheme "${parsed.protocol}" (only http/https allowed)`,
    );
  }
  return parsed.toString();
}

/**
 * Minimal native WebSocket JSON-RPC client for Chrome DevTools Protocol.
 */
class CdpSocket {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.seq = 0;
    this.pending = new Map();
    this.listeners = new Map();
    this.closed = false;
  }

  async connect(timeoutMs = 8000) {
    const ws = new globalThis.WebSocket(this.wsUrl);
    this.ws = ws;

    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error(`CDP WebSocket connect timeout (${this.wsUrl})`));
      }, timeoutMs);

      const onOpen = () => {
        clearTimeout(timer);
        ws.removeEventListener("error", onErr);
        resolve();
      };
      const onErr = (ev) => {
        clearTimeout(timer);
        ws.removeEventListener("open", onOpen);
        reject(new Error(`CDP WebSocket connection failed: ${ev?.message || this.wsUrl}`));
      };

      ws.addEventListener("open", onOpen, { once: true });
      ws.addEventListener("error", onErr, { once: true });
    });

    ws.addEventListener("message", (event) => {
      let msg;
      try {
        const text =
          typeof event.data === "string"
            ? event.data
            : Buffer.from(event.data).toString("utf-8");
        msg = JSON.parse(text);
      } catch {
        return;
      }

      if (typeof msg.id === "number") {
        const entry = this.pending.get(msg.id);
        if (entry) {
          this.pending.delete(msg.id);
          clearTimeout(entry.timer);
          if (msg.error) {
            entry.reject(
              new Error(`CDP ${entry.method} error: ${msg.error.message || JSON.stringify(msg.error)}`),
            );
          } else {
            entry.resolve(msg.result);
          }
        }
        return;
      }

      if (msg.method) {
        const handlers = this.listeners.get(msg.method);
        if (handlers) {
          for (const fn of handlers) {
            try {
              fn(msg.params || {});
            } catch {
              // keep loop healthy
            }
          }
        }
      }
    });

    const onDisconnect = () => {
      if (this.closed) return;
      this.closed = true;
      for (const [, entry] of this.pending) {
        clearTimeout(entry.timer);
        entry.reject(new Error(`CDP socket closed during ${entry.method}`));
      }
      this.pending.clear();
      const handlers = this.listeners.get("__disconnect__");
      if (handlers) {
        for (const fn of handlers) {
          try {
            fn({});
          } catch {
            // ignore
          }
        }
      }
    };

    ws.addEventListener("close", onDisconnect, { once: true });
    ws.addEventListener("error", onDisconnect, { once: true });
  }

  on(eventName, handler) {
    if (!this.listeners.has(eventName)) {
      this.listeners.set(eventName, new Set());
    }
    this.listeners.get(eventName).add(handler);
    return () => this.listeners.get(eventName)?.delete(handler);
  }

  send(method, params = {}, timeoutMs = 12000) {
    if (this.closed || !this.ws || this.ws.readyState !== globalThis.WebSocket.OPEN) {
      return Promise.reject(new Error(`CDP socket is not open (${method})`));
    }
    const id = ++this.seq;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP timeout after ${timeoutMs}ms: ${method}`));
      }, timeoutMs);
      timer.unref?.();

      this.pending.set(id, { resolve, reject, timer, method });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  close() {
    this.closed = true;
    for (const [, entry] of this.pending) {
      clearTimeout(entry.timer);
      entry.reject(new Error("CDP socket closed"));
    }
    this.pending.clear();
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // ignore
      }
      this.ws = null;
    }
  }
}

function isUserPageTarget(target) {
  if (!target || target.type !== "page") return false;
  const url = String(target.url || "");
  if (
    url.startsWith("devtools://") ||
    url.startsWith("chrome://omnibox") ||
    url.startsWith("chrome-extension://")
  ) {
    return false;
  }
  return true;
}

const KEY_DEFINITIONS = Object.freeze({
  Enter: {
    key: "Enter",
    code: "Enter",
    keyCode: 13,
    text: "\r",
  },
  Tab: {
    key: "Tab",
    code: "Tab",
    keyCode: 9,
  },
  Backspace: {
    key: "Backspace",
    code: "Backspace",
    keyCode: 8,
    commands: ["deleteBackward"],
  },
  Escape: {
    key: "Escape",
    code: "Escape",
    keyCode: 27,
  },
  ArrowUp: {
    key: "ArrowUp",
    code: "ArrowUp",
    keyCode: 38,
    commands: ["moveUp"],
  },
  ArrowDown: {
    key: "ArrowDown",
    code: "ArrowDown",
    keyCode: 40,
    commands: ["moveDown"],
  },
  ArrowLeft: {
    key: "ArrowLeft",
    code: "ArrowLeft",
    keyCode: 37,
    commands: ["moveLeft"],
  },
  ArrowRight: {
    key: "ArrowRight",
    code: "ArrowRight",
    keyCode: 39,
    commands: ["moveRight"],
  },
});

/**
 * Manages an isolated Headless Chrome instance and active page target via loopback CDP.
 */
export class CdpBrowserSession {
  constructor({
    chromePath = DEFAULT_CHROME_BIN,
    userDataDir = DEFAULT_PROFILE_DIR,
    viewportWidth = DEFAULT_VIEWPORT.width,
    viewportHeight = DEFAULT_VIEWPORT.height,
    deviceScaleFactor = 1.5,
    initialUrl = "about:blank",
  } = {}) {
    const resolvedProfile = path.resolve(userDataDir);
    if (resolvedProfile.includes(path.join("Application Support", "Google", "Chrome"))) {
      throw new Error(
        "Refusing to touch system Chrome profile; PocketBridge must use an isolated userDataDir",
      );
    }

    this.chromePath = chromePath;
    this.userDataDir = resolvedProfile;
    this.viewportWidth = viewportWidth;
    this.viewportHeight = viewportHeight;
    this.deviceScaleFactor = deviceScaleFactor;
    this.initialUrl = initialUrl;

    this.chromeProc = null;
    this.debugPort = null;
    this.browserWsUrl = null;
    this.socket = null;
    this.activeTargetId = null;
    this.lastFileChooserBackendNodeId = null;
    this.closed = false;
    this._switchingPromise = null;
  }

  async start() {
    if (this.chromeProc) return;
    this.closed = false;

    fs.mkdirSync(this.userDataDir, { recursive: true });
    const activePortFile = path.join(this.userDataDir, "DevToolsActivePort");
    try {
      fs.rmSync(activePortFile, { force: true });
    } catch {
      // ignore
    }

    const args = [
      "--headless=new",
      "--remote-debugging-port=0",
      "--remote-debugging-address=127.0.0.1",
      `--user-data-dir=${this.userDataDir}`,
      `--window-size=${this.viewportWidth},${this.viewportHeight}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-background-timer-throttling",
      "--disable-backgrounding-occluded-windows",
      "--disable-renderer-backgrounding",
      "--disable-popup-blocking",
      "--disable-sync",
      "--lang=ja-JP",
      this.initialUrl,
    ];

    const proc = spawn(this.chromePath, args, {
      stdio: ["ignore", "ignore", "pipe"],
    });
    this.chromeProc = proc;

    const endpoint = await new Promise((resolve, reject) => {
      let stderrBuf = "";
      let settled = false;

      const finish = (err, val) => {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        clearInterval(poller);
        err ? reject(err) : resolve(val);
      };

      const timeout = setTimeout(() => {
        finish(new Error(`Timed out waiting for Chrome DevTools port. stderr: ${stderrBuf}`));
      }, 12000);

      proc.once("error", (err) => finish(err));
      proc.once("exit", (code, sig) => {
        finish(
          new Error(
            `Chrome exited before DevTools ready (code=${code}, sig=${sig}). stderr: ${stderrBuf}`,
          ),
        );
      });

      proc.stderr.on("data", (chunk) => {
        stderrBuf += chunk.toString("utf-8");
        const m = stderrBuf.match(/DevTools listening on (ws:\/\/127\.0\.0\.1:(\d+)\/\S+)/);
        if (m) {
          finish(null, { browserWsUrl: m[1], port: Number(m[2]) });
        }
      });

      const poller = setInterval(() => {
        try {
          if (fs.existsSync(activePortFile)) {
            const lines = fs.readFileSync(activePortFile, "utf-8").trim().split(/\r?\n/);
            const port = Number(lines[0]);
            if (Number.isInteger(port) && port > 0 && lines[1]) {
              finish(null, {
                browserWsUrl: `ws://127.0.0.1:${port}${lines[1]}`,
                port,
              });
            }
          }
        } catch {
          // wait for next tick
        }
      }, 80);
    });

    this.debugPort = endpoint.port;
    this.browserWsUrl = endpoint.browserWsUrl;

    await this.ensureActiveTarget();
  }

  async _fetchJson(pathname, options = {}) {
    const res = await fetch(`http://127.0.0.1:${this.debugPort}${pathname}`, options);
    if (!res.ok) {
      throw new Error(`CDP HTTP ${pathname} failed: ${res.status}`);
    }
    return res.json();
  }

  async listTabs() {
    const rawList = await this._fetchJson("/json/list");
    const pages = rawList.filter(isUserPageTarget);
    return pages.map((t, idx) => ({
      id: t.id,
      index: idx,
      title: t.title || t.url || "New Tab",
      url: t.url || "about:blank",
      webSocketDebuggerUrl: t.webSocketDebuggerUrl,
      active: t.id === this.activeTargetId,
    }));
  }

  async ensureActiveTarget() {
    if (this.closed) {
      throw new Error("CdpBrowserSession is closed");
    }
    if (this.socket && !this.socket.closed && this.activeTargetId) {
      return;
    }
    if (this._switchingPromise) {
      await this._switchingPromise;
      return;
    }

    let tabs = await this.listTabs();
    if (tabs.length === 0) {
      const created = await this._fetchJson("/json/new?about:blank", { method: "PUT" });
      tabs = [
        {
          id: created.id,
          title: created.title || "about:blank",
          url: created.url || "about:blank",
          webSocketDebuggerUrl: created.webSocketDebuggerUrl,
        },
      ];
    }

    const chosen = tabs.find((t) => t.id === this.activeTargetId) || tabs[0];
    await this.attachToTarget(chosen.id);
  }

  async attachToTarget(targetId) {
    const run = async () => {
      const rawList = await this._fetchJson("/json/list");
      const target = rawList.find((t) => t.id === targetId && t.webSocketDebuggerUrl);
      if (!target) {
        throw new Error(`Target not found: ${targetId}`);
      }

      if (this.socket) {
        this.socket.close();
        this.socket = null;
      }

      const sock = new CdpSocket(target.webSocketDebuggerUrl);
      await sock.connect();
      this.socket = sock;
      this.activeTargetId = target.id;
      this.lastFileChooserBackendNodeId = null;

      await sock.send("Page.enable");
      await sock.send("DOM.enable");
      await sock.send("Runtime.enable");
      await sock.send("Emulation.setDeviceMetricsOverride", {
        width: this.viewportWidth,
        height: this.viewportHeight,
        deviceScaleFactor: this.deviceScaleFactor,
        mobile: false,
      });

      try {
        await sock.send("Page.setInterceptFileChooserDialog", { enabled: true });
        sock.on("Page.fileChooserOpened", (params) => {
          if (params && params.backendNodeId) {
            this.lastFileChooserBackendNodeId = params.backendNodeId;
          }
        });
      } catch {
        // optional enhancement on supported Chromium versions
      }

      try {
        await sock.send("Target.setDiscoverTargets", { discover: true });
        sock.on("Target.targetCreated", (params) => {
          const info = params?.targetInfo;
          if (
            !this.closed &&
            info &&
            isUserPageTarget(info) &&
            info.openerId &&
            info.targetId !== this.activeTargetId
          ) {
            setTimeout(() => {
              if (!this.closed) {
                this.attachToTarget(info.targetId).catch(() => {});
              }
            }, 150).unref?.();
          }
        });
      } catch {
        // ignore if target discovery unsupported on sub-target
      }

      sock.on("__disconnect__", () => {
        if (!this.closed && this.socket === sock) {
          this.socket = null;
          this.activeTargetId = null;
        }
      });

      try {
        await fetch(`http://127.0.0.1:${this.debugPort}/json/activate/${target.id}`);
      } catch {
        // non-fatal
      }
    };

    this._switchingPromise = run().finally(() => {
      this._switchingPromise = null;
    });
    return this._switchingPromise;
  }

  async send(method, params = {}, timeoutMs = 12000) {
    await this.ensureActiveTarget();
    return this.socket.send(method, params, timeoutMs);
  }

  async switchTab(targetId) {
    await this.attachToTarget(targetId);
    return this.getPageMeta();
  }

  async newTab(rawUrl = "https://www.google.com/") {
    const safeUrl = normalizeSafeNavigationUrl(rawUrl);
    const created = await this._fetchJson(
      `/json/new?${encodeURIComponent(safeUrl)}`,
      { method: "PUT" },
    );
    await this.attachToTarget(created.id);
    return this.getPageMeta();
  }

  async closeTab(targetId) {
    const tabs = await this.listTabs();
    if (tabs.length <= 1) {
      return this.navigate("about:blank");
    }
    const closingActive = targetId === this.activeTargetId;
    await fetch(`http://127.0.0.1:${this.debugPort}/json/close/${encodeURIComponent(targetId)}`);
    if (closingActive) {
      this.activeTargetId = null;
      if (this.socket) {
        this.socket.close();
        this.socket = null;
      }
      await sleep(80);
      await this.ensureActiveTarget();
    }
    return this.getPageMeta();
  }

  async getPageMeta() {
    await this.ensureActiveTarget();
    try {
      const evalRes = await this.send("Runtime.evaluate", {
        expression: "({ url: location.href, title: document.title || '' })",
        returnByValue: true,
      });
      const val = evalRes?.result?.value || {};
      return {
        url: val.url || "about:blank",
        title: val.title || "",
        viewport: {
          width: this.viewportWidth,
          height: this.viewportHeight,
        },
        activeTargetId: this.activeTargetId,
      };
    } catch {
      return {
        url: "about:blank",
        title: "",
        viewport: {
          width: this.viewportWidth,
          height: this.viewportHeight,
        },
        activeTargetId: this.activeTargetId,
      };
    }
  }

  async navigate(rawUrl, { waitMs = 3500 } = {}) {
    const safeUrl = normalizeSafeNavigationUrl(rawUrl);
    await this.ensureActiveTarget();

    let unsub = null;
    const loadWait = new Promise((resolve) => {
      const timer = setTimeout(resolve, waitMs);
      timer.unref?.();
      unsub = this.socket.on("Page.loadEventFired", () => {
        clearTimeout(timer);
        resolve();
      });
    });

    await this.send("Page.navigate", { url: safeUrl });
    await loadWait;
    if (unsub) unsub();
    await sleep(60);
    return this.getPageMeta();
  }

  async captureScreenshot({ format = "jpeg", quality = 78 } = {}) {
    await this.ensureActiveTarget();
    const params = {
      format,
      optimizeForSpeed: true,
    };
    if (format === "jpeg") {
      params.quality = Math.max(20, Math.min(95, Math.round(quality)));
    }
    const [shot, meta] = await Promise.all([
      this.send("Page.captureScreenshot", params),
      this.getPageMeta(),
    ]);
    const buffer = Buffer.from(shot.data, "base64");
    return {
      buffer,
      dataBase64: shot.data,
      url: meta.url,
      title: meta.title,
      viewport: meta.viewport,
    };
  }

  async click({ x, y, button = "left", clickCount = 1 }) {
    const pt = clampViewportPoint({
      x,
      y,
      viewportWidth: this.viewportWidth,
      viewportHeight: this.viewportHeight,
    });
    const safeButton = button === "right" ? "right" : "left";
    const buttonMask = safeButton === "right" ? 2 : 1;
    const clicks = clickCount === 2 ? 2 : 1;

    await this.send("Input.dispatchMouseEvent", {
      type: "mouseMoved",
      x: pt.x,
      y: pt.y,
      button: "none",
      buttons: 0,
    });

    for (let c = 1; c <= clicks; c += 1) {
      await this.send("Input.dispatchMouseEvent", {
        type: "mousePressed",
        x: pt.x,
        y: pt.y,
        button: safeButton,
        buttons: buttonMask,
        clickCount: c,
      });
      await this.send("Input.dispatchMouseEvent", {
        type: "mouseReleased",
        x: pt.x,
        y: pt.y,
        button: safeButton,
        buttons: 0,
        clickCount: c,
      });
    }

    let activeElement = null;
    try {
      const res = await this.send("Runtime.evaluate", {
        expression: `(() => {
          const el = document.activeElement;
          if (!el || el === document.body) return null;
          const tag = (el.tagName || '').toLowerCase();
          return {
            tag,
            type: el.type || '',
            id: el.id || '',
            name: el.name || '',
            placeholder: el.placeholder || '',
            isEditable: tag === 'input' || tag === 'textarea' || Boolean(el.isContentEditable)
          };
        })()`,
        returnByValue: true,
      });
      activeElement = res?.result?.value || null;
    } catch {
      activeElement = null;
    }

    return { ok: true, x: pt.x, y: pt.y, button: safeButton, clickCount: clicks, activeElement };
  }

  async drag({ fromX, fromY, toX, toY, steps = 8 }) {
    const start = clampViewportPoint({
      x: fromX,
      y: fromY,
      viewportWidth: this.viewportWidth,
      viewportHeight: this.viewportHeight,
    });
    const end = clampViewportPoint({
      x: toX,
      y: toY,
      viewportWidth: this.viewportWidth,
      viewportHeight: this.viewportHeight,
    });
    const count = Math.max(2, Math.min(25, Math.round(steps)));

    await this.send("Input.dispatchMouseEvent", {
      type: "mouseMoved",
      x: start.x,
      y: start.y,
      button: "none",
      buttons: 0,
    });
    await this.send("Input.dispatchMouseEvent", {
      type: "mousePressed",
      x: start.x,
      y: start.y,
      button: "left",
      buttons: 1,
      clickCount: 1,
    });
    for (let i = 1; i <= count; i += 1) {
      const ratio = i / count;
      await this.send("Input.dispatchMouseEvent", {
        type: "mouseMoved",
        x: Math.round(start.x + (end.x - start.x) * ratio),
        y: Math.round(start.y + (end.y - start.y) * ratio),
        button: "left",
        buttons: 1,
      });
    }
    await this.send("Input.dispatchMouseEvent", {
      type: "mouseReleased",
      x: end.x,
      y: end.y,
      button: "left",
      buttons: 0,
      clickCount: 1,
    });
    return { ok: true, from: start, to: end };
  }

  async scroll({ deltaX = 0, deltaY = 360, x = 640, y = 450 }) {
    const pt = clampViewportPoint({
      x,
      y,
      viewportWidth: this.viewportWidth,
      viewportHeight: this.viewportHeight,
    });
    const dx = Math.max(-4000, Math.min(4000, Math.round(Number(deltaX) || 0)));
    const dy = Math.max(-4000, Math.min(4000, Math.round(Number(deltaY) || 0)));

    await this.send("Input.dispatchMouseEvent", {
      type: "mouseWheel",
      x: pt.x,
      y: pt.y,
      deltaX: dx,
      deltaY: dy,
    });
    return { ok: true, deltaX: dx, deltaY: dy, x: pt.x, y: pt.y };
  }

  async selectAllFocused() {
    await this.send("Input.dispatchKeyEvent", {
      type: "rawKeyDown",
      key: "a",
      code: "KeyA",
      windowsVirtualKeyCode: 65,
      nativeVirtualKeyCode: 65,
      modifiers: 4, // Meta / Cmd on macOS
      commands: ["selectAll"],
    });
    await this.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: "a",
      code: "KeyA",
      windowsVirtualKeyCode: 65,
      nativeVirtualKeyCode: 65,
      modifiers: 4,
    });
    try {
      await this.send("Runtime.evaluate", {
        expression: `(() => {
          const el = document.activeElement;
          if (el && typeof el.select === 'function') el.select();
        })()`,
      });
    } catch {
      // ignore cross-context edge case
    }
  }

  async clearFocusedField() {
    await this.selectAllFocused();
    await this.sendKey("Backspace");
    try {
      await this.send("Runtime.evaluate", {
        expression: `(() => {
          const el = document.activeElement;
          if (!el) return;
          const tag = (el.tagName || '').toLowerCase();
          if ((tag === 'input' || tag === 'textarea') && el.value) {
            const proto = tag === 'textarea' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            const desc = Object.getOwnPropertyDescriptor(proto, 'value');
            if (desc && desc.set) desc.set.call(el, '');
            else el.value = '';
            el.dispatchEvent(new Event('input', { bubbles: true }));
          }
        })()`,
      });
    } catch {
      // ignore
    }
  }

  async typeText({ text, clearFirst = false, pressEnter = false }) {
    if (typeof text !== "string") {
      throw new PresetValidationError("text must be a string");
    }
    if (clearFirst) {
      await this.clearFocusedField();
    }
    if (text.length > 0) {
      await this.send("Input.insertText", { text });
    }
    if (pressEnter) {
      await this.sendKey("Enter");
    }
    return {
      ok: true,
      length: text.length,
      cleared: Boolean(clearFirst),
      pressedEnter: Boolean(pressEnter),
    };
  }

  async sendKey(keyName) {
    if (keyName === "SelectAll") {
      await this.selectAllFocused();
      return { ok: true, key: "SelectAll" };
    }
    if (keyName === "Back" || keyName === "Forward") {
      const hist = await this.send("Page.getNavigationHistory");
      const targetIdx =
        keyName === "Back" ? hist.currentIndex - 1 : hist.currentIndex + 1;
      if (targetIdx >= 0 && targetIdx < hist.entries.length) {
        await this.send("Page.navigateToHistoryEntry", {
          entryId: hist.entries[targetIdx].id,
        });
        await sleep(150);
      }
      return { ok: true, key: keyName };
    }
    if (keyName === "Reload") {
      await this.send("Page.reload", { ignoreCache: false });
      await sleep(180);
      return { ok: true, key: "Reload" };
    }

    if (!Object.hasOwn(KEY_DEFINITIONS, keyName)) {
      throw new PresetValidationError(`Unsupported key: ${String(keyName)}`);
    }
    const def = KEY_DEFINITIONS[keyName];

    await this.send("Input.dispatchKeyEvent", {
      type: def.text ? "keyDown" : "rawKeyDown",
      key: def.key,
      code: def.code,
      windowsVirtualKeyCode: def.keyCode,
      nativeVirtualKeyCode: def.keyCode,
      ...(def.text ? { text: def.text, unmodifiedText: def.text } : {}),
      ...(def.commands ? { commands: def.commands } : {}),
    });
    await this.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: def.key,
      code: def.code,
      windowsVirtualKeyCode: def.keyCode,
      nativeVirtualKeyCode: def.keyCode,
    });
    return { ok: true, key: keyName };
  }

  /**
   * Inspect all <input type="file"> elements currently present in the DOM.
   */
  async listFileInputs() {
    await this.ensureActiveTarget();
    const doc = await this.send("DOM.getDocument", { depth: -1, pierce: true });
    const q = await this.send("DOM.querySelectorAll", {
      nodeId: doc.root.nodeId,
      selector: 'input[type="file"]',
    });
    const nodeIds = q.nodeIds || [];
    const results = [];

    for (let i = 0; i < nodeIds.length; i += 1) {
      const nodeId = nodeIds[i];
      const attrRes = await this.send("DOM.getAttributes", { nodeId });
      const attrs = parseAttributesArray(attrRes.attributes || []);
      let currentFiles = [];
      try {
        const resolved = await this.send("DOM.resolveNode", { nodeId });
        if (resolved?.object?.objectId) {
          const fnRes = await this.send("Runtime.callFunctionOn", {
            objectId: resolved.object.objectId,
            functionDeclaration:
              "function() { return Array.from(this.files || []).map(f => f.name); }",
            returnByValue: true,
          });
          currentFiles = fnRes?.result?.value || [];
        }
      } catch {
        currentFiles = [];
      }

      results.push({
        index: i,
        nodeId,
        id: attrs.id || "",
        name: attrs.name || "",
        accept: attrs.accept || "",
        multiple: Object.hasOwn(attrs, "multiple"),
        disabled: Object.hasOwn(attrs, "disabled"),
        attrs,
        currentFiles,
      });
    }

    return results;
  }

  /**
   * Attach a strictly pre-approved studio deliverable directly to the page's file <input>.
   * Automatically scores and picks the best matching <input type="file"> (e.g. image vs .zip on BOOTH),
   * or honors an explicit inputIndex when supplied.
   */
  async attachPreapprovedFile(presetId, { inputIndex } = {}) {
    const preset = resolveApprovedPreset(presetId);

    if (!fs.existsSync(preset.path)) {
      throw new Error(`Pre-approved deliverable file is missing on disk: ${preset.filename}`);
    }

    const inputs = await this.listFileInputs();
    if (inputs.length === 0) {
      if (this.lastFileChooserBackendNodeId) {
        await this.send("DOM.setFileInputFiles", {
          backendNodeId: this.lastFileChooserBackendNodeId,
          files: [preset.path],
        });
        return {
          ok: true,
          presetId: preset.id,
          filename: preset.filename,
          matchedIndex: 0,
          totalInputs: 1,
          accept: "(fileChooser)",
        };
      }
      throw new PresetValidationError(
        "現在のページ上にファイル選択欄 (input[type=file]) が見つかりません。アップロード欄のある画面を開いてください。",
      );
    }

    let chosen;
    if (inputIndex !== undefined && inputIndex !== null && inputIndex !== "auto") {
      const idx = Number(inputIndex);
      if (!Number.isInteger(idx) || idx < 0 || idx >= inputs.length) {
        throw new PresetValidationError(
          `inputIndex ${String(inputIndex)} is out of range (0..${inputs.length - 1})`,
        );
      }
      chosen = inputs[idx];
    } else if (inputs.length === 1) {
      chosen = inputs[0];
    } else {
      let bestScore = -Infinity;
      chosen = inputs[0];
      for (const candidate of inputs) {
        const sc = scoreFileInputForPreset(preset, candidate.attrs);
        if (sc > bestScore) {
          bestScore = sc;
          chosen = candidate;
        }
      }
    }

    await this.send("DOM.setFileInputFiles", {
      nodeId: chosen.nodeId,
      files: [preset.path],
    });

    return {
      ok: true,
      presetId: preset.id,
      filename: preset.filename,
      matchedIndex: chosen.index,
      totalInputs: inputs.length,
      accept: chosen.accept,
      inputId: chosen.id,
    };
  }

  async close() {
    if (this.closed) return;
    this.closed = true;

    if (this.socket && !this.socket.closed) {
      try {
        await this.socket.send("Browser.close", {}, 1500);
      } catch {
        // fallback to process signal below
      }
      this.socket.close();
      this.socket = null;
    }

    const proc = this.chromeProc;
    this.chromeProc = null;
    if (!proc) return;

    if (proc.exitCode !== null || proc.signalCode !== null) {
      return;
    }

    const waitForExit = (ms) =>
      new Promise((resolve) => {
        if (proc.exitCode !== null || proc.signalCode !== null) {
          resolve(true);
          return;
        }
        const t = setTimeout(() => resolve(false), ms);
        t.unref?.();
        proc.once("exit", () => {
          clearTimeout(t);
          resolve(true);
        });
      });

    let exited = await waitForExit(1200);
    if (!exited) {
      try {
        proc.kill("SIGTERM");
      } catch {
        // ignore
      }
      exited = await waitForExit(1200);
    }
    if (!exited) {
      try {
        proc.kill("SIGKILL");
      } catch {
        // ignore
      }
      await waitForExit(800);
    }
  }
}
