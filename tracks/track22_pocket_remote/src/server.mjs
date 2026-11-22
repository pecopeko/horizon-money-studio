import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CdpBrowserSession } from "./cdp_client.mjs";
import { clampViewportPoint, mapClientPointToViewport } from "./coords.mjs";
import { MacDesktopController } from "./macos_desktop.mjs";
import {
  listPublicPresets,
  PresetValidationError,
  QUICK_BOOKMARKS,
  QUICK_SNIPPETS,
} from "./presets.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const UI_HTML_PATH = path.join(__dirname, "ui.html");
const COOKIE_NAME = "pocket_session";
const MAX_JSON_BODY_BYTES = 64 * 1024;

export function generateSecretToken() {
  return crypto.randomBytes(32).toString("hex"); // 256-bit (64 hex chars)
}

/**
 * Constant-time token verification using crypto.timingSafeEqual.
 */
export function timingSafeVerifyToken(candidate, expectedToken) {
  if (
    typeof candidate !== "string" ||
    typeof expectedToken !== "string" ||
    expectedToken.length < 32
  ) {
    return false;
  }
  const candBuf = Buffer.from(candidate, "utf-8");
  const expBuf = Buffer.from(expectedToken, "utf-8");
  if (candBuf.length !== expBuf.length) {
    // Perform dummy comparison of equal length to avoid timing leak
    crypto.timingSafeEqual(expBuf, expBuf);
    return false;
  }
  return crypto.timingSafeEqual(candBuf, expBuf);
}

function parseCookies(cookieHeader = "") {
  const out = {};
  if (!cookieHeader || typeof cookieHeader !== "string") return out;
  for (const part of cookieHeader.split(";")) {
    const eq = part.indexOf("=");
    if (eq <= 0) continue;
    const key = part.slice(0, eq).trim();
    const val = part.slice(eq + 1).trim();
    if (key) out[key] = val;
  }
  return out;
}

function getClientIp(req) {
  return req.socket?.remoteAddress || "unknown";
}

function sendJson(res, statusCode, payload, extraHeaders = {}) {
  const body = Buffer.from(JSON.stringify(payload), "utf-8");
  res.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": String(body.length),
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    ...extraHeaders,
  });
  res.end(body);
}

async function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let total = 0;
    req.on("data", (chunk) => {
      total += chunk.length;
      if (total > MAX_JSON_BODY_BYTES) {
        reject(new PresetValidationError("Request body exceeds 64 KB limit"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => {
      if (chunks.length === 0) {
        resolve({});
        return;
      }
      try {
        const parsed = JSON.parse(Buffer.concat(chunks).toString("utf-8"));
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          reject(new PresetValidationError("JSON body must be an object"));
          return;
        }
        resolve(parsed);
      } catch {
        reject(new PresetValidationError("Malformed JSON request body"));
      }
    });
    req.on("error", reject);
  });
}

export function detectLanIpv4() {
  const nets = os.networkInterfaces();
  for (const name of Object.keys(nets)) {
    for (const iface of nets[name] || []) {
      if (iface.family === "IPv4" && !iface.internal) {
        return iface.address;
      }
    }
  }
  return "127.0.0.1";
}

/**
 * Create and start a PocketBridge HTTP + CDP server instance.
 */
export async function createPocketBridgeServer({
  host = "127.0.0.1",
  port = 0,
  token = generateSecretToken(),
  maxFailedAttempts = 10,
  lockoutWindowMs = 15 * 60 * 1000,
  idleTimeoutMs = 120 * 60 * 1000,
  autoLaunchChrome = true,
  chromeOptions = {},
  browserSession = null,
  desktopController = null,
  onIdleShutdown = null,
} = {}) {
  if (typeof token !== "string" || token.length < 64) {
    throw new Error("PocketBridge requires at least a 256-bit (64-hex-char) secret token");
  }

  const uiHtml = fs.readFileSync(UI_HTML_PATH, "utf-8");
  const cdp = browserSession || new CdpBrowserSession(chromeOptions);
  const desktop = desktopController || new MacDesktopController();

  let activeMode = "browser";
  let closed = false;
  let lastActivityAt = Date.now();
  const failedAttemptsByIp = new Map();

  if (autoLaunchChrome && !browserSession) {
    await cdp.start();
  }

  function isIpLockedOut(ip) {
    const rec = failedAttemptsByIp.get(ip);
    if (!rec) return false;
    if (Date.now() - rec.windowStart > lockoutWindowMs) {
      failedAttemptsByIp.delete(ip);
      return false;
    }
    return rec.count >= maxFailedAttempts;
  }

  function recordFailedAttempt(ip) {
    const now = Date.now();
    const rec = failedAttemptsByIp.get(ip);
    if (!rec || now - rec.windowStart > lockoutWindowMs) {
      const fresh = { count: 1, windowStart: now };
      failedAttemptsByIp.set(ip, fresh);
      return fresh.count;
    }
    rec.count += 1;
    return rec.count;
  }

  let idleTimer = null;
  function resetIdleTimer() {
    lastActivityAt = Date.now();
    if (idleTimer) clearTimeout(idleTimer);
    if (idleTimeoutMs > 0 && Number.isFinite(idleTimeoutMs)) {
      idleTimer = setTimeout(async () => {
        await close({ reason: "idle_timeout" });
        if (typeof onIdleShutdown === "function") {
          onIdleShutdown();
        }
      }, idleTimeoutMs);
      idleTimer.unref?.();
    }
  }

  function serveUiHtml(res, setCookieValue = null) {
    const body = Buffer.from(uiHtml, "utf-8");
    const headers = {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Length": String(body.length),
      "Cache-Control": "no-store, no-cache, must-revalidate",
      "X-Frame-Options": "DENY",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
      "Content-Security-Policy":
        "default-src 'self'; img-src 'self' blob: data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'",
    };
    if (setCookieValue) {
      headers["Set-Cookie"] =
        `${COOKIE_NAME}=${setCookieValue}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200`;
    }
    res.writeHead(200, headers);
    res.end(body);
  }

  function checkRequestAuthorized(req) {
    const headerTok = req.headers["x-pocket-token"];
    if (typeof headerTok === "string" && timingSafeVerifyToken(headerTok, token)) {
      return true;
    }
    const cookies = parseCookies(req.headers.cookie);
    if (cookies[COOKIE_NAME] && timingSafeVerifyToken(cookies[COOKIE_NAME], token)) {
      return true;
    }
    return false;
  }

  const server = http.createServer(async (req, res) => {
    const ip = getClientIp(req);

    if (isIpLockedOut(ip)) {
      sendJson(
        res,
        429,
        {
          ok: false,
          error: "Too many invalid token attempts. Temporarily locked out.",
        },
        { "Retry-After": String(Math.ceil(lockoutWindowMs / 1000)) },
      );
      return;
    }

    let parsedUrl;
    try {
      parsedUrl = new URL(req.url || "/", "http://localhost");
    } catch {
      sendJson(res, 400, { ok: false, error: "Invalid request URL" });
      return;
    }
    const pathname = parsedUrl.pathname;

    // 1. Magic Token Bootstrap Entrypoint: GET /s/<token> or /s/<token>/
    if (pathname.startsWith("/s/")) {
      const segments = pathname.split("/").filter(Boolean); // ["s", "<token>", ...]
      const candidateToken = segments[1] || "";
      if (segments.length === 2 && timingSafeVerifyToken(candidateToken, token)) {
        resetIdleTimer();
        serveUiHtml(res, token);
        return;
      }
      const fails = recordFailedAttempt(ip);
      if (fails >= maxFailedAttempts) {
        sendJson(
          res,
          429,
          { ok: false, error: "Too many invalid token attempts. Temporarily locked out." },
          { "Retry-After": String(Math.ceil(lockoutWindowMs / 1000)) },
        );
      } else {
        sendJson(res, 403, { ok: false, error: "Forbidden: invalid session token" });
      }
      return;
    }

    // 2. All other routes require valid session cookie or X-Pocket-Token header
    if (!checkRequestAuthorized(req)) {
      const fails = recordFailedAttempt(ip);
      if (fails >= maxFailedAttempts) {
        sendJson(
          res,
          429,
          { ok: false, error: "Too many invalid token attempts. Temporarily locked out." },
          { "Retry-After": String(Math.ceil(lockoutWindowMs / 1000)) },
        );
      } else {
        sendJson(res, 403, { ok: false, error: "Forbidden: authentication required" });
      }
      return;
    }

    resetIdleTimer();

    try {
      if (req.method === "GET" && pathname === "/") {
        serveUiHtml(res, null);
        return;
      }

      if (req.method === "GET" && pathname === "/api/state") {
        const [meta, tabs, desktopStatus] = await Promise.all([
          cdp.getPageMeta(),
          cdp.listTabs(),
          desktop.getStatus(),
        ]);
        const elapsedMs = Date.now() - lastActivityAt;
        const idleMinutesRemaining = Math.max(
          0,
          Math.round((idleTimeoutMs - elapsedMs) / 60000),
        );
        sendJson(res, 200, {
          ok: true,
          mode: activeMode,
          desktopStatus,
          url: meta.url,
          title: meta.title,
          viewport: meta.viewport,
          tabs,
          presets: listPublicPresets(),
          bookmarks: QUICK_BOOKMARKS,
          snippets: QUICK_SNIPPETS,
          idleMinutesRemaining,
        });
        return;
      }

      if (req.method === "GET" && pathname === "/api/screenshot") {
        const quality = Number(parsedUrl.searchParams.get("q")) || 78;
        const shot = await cdp.captureScreenshot({ format: "jpeg", quality });
        if (parsedUrl.searchParams.get("encoding") === "json") {
          sendJson(res, 200, {
            ok: true,
            mimeType: "image/jpeg",
            dataBase64: shot.dataBase64,
            url: shot.url,
            title: shot.title,
            viewport: shot.viewport,
          });
          return;
        }
        res.writeHead(200, {
          "Content-Type": "image/jpeg",
          "Content-Length": String(shot.buffer.length),
          "Cache-Control": "no-store, no-cache, must-revalidate",
          "X-Page-Url": encodeURIComponent(shot.url || ""),
          "X-Page-Title": encodeURIComponent(shot.title || ""),
          "X-Viewport-Width": String(shot.viewport.width),
          "X-Viewport-Height": String(shot.viewport.height),
        });
        res.end(shot.buffer);
        return;
      }

      if (req.method === "POST" && pathname === "/api/navigate") {
        const body = await readJsonBody(req);
        const meta = await cdp.navigate(body.url);
        sendJson(res, 200, { ok: true, ...meta });
        return;
      }

      if (req.method === "POST" && pathname === "/api/click") {
        const body = await readJsonBody(req);
        let coords;
        if (body.rect && typeof body.rect === "object") {
          coords = mapClientPointToViewport({
            clientX: Number(body.clientX),
            clientY: Number(body.clientY),
            rect: body.rect,
            viewportWidth: cdp.viewportWidth,
            viewportHeight: cdp.viewportHeight,
          });
        } else if (Number.isFinite(Number(body.x)) && Number.isFinite(Number(body.y))) {
          coords = clampViewportPoint({
            x: Number(body.x),
            y: Number(body.y),
            viewportWidth: cdp.viewportWidth,
            viewportHeight: cdp.viewportHeight,
          });
        } else {
          throw new PresetValidationError("Provide either (x, y) or (clientX, clientY, rect)");
        }

        const result = await cdp.click({
          x: coords.x,
          y: coords.y,
          button: body.button,
          clickCount: body.clickCount,
        });
        sendJson(res, 200, result);
        return;
      }

      if (req.method === "POST" && pathname === "/api/drag") {
        const body = await readJsonBody(req);
        const result = await cdp.drag({
          fromX: Number(body.fromX),
          fromY: Number(body.fromY),
          toX: Number(body.toX),
          toY: Number(body.toY),
          steps: body.steps,
        });
        sendJson(res, 200, result);
        return;
      }

      if (req.method === "POST" && pathname === "/api/scroll") {
        const body = await readJsonBody(req);
        const result = await cdp.scroll({
          deltaX: body.deltaX,
          deltaY: body.deltaY,
          x: body.x ?? 640,
          y: body.y ?? 450,
        });
        sendJson(res, 200, result);
        return;
      }

      if (req.method === "POST" && pathname === "/api/type") {
        const body = await readJsonBody(req);
        const result = await cdp.typeText({
          text: body.text,
          clearFirst: Boolean(body.clearFirst),
          pressEnter: Boolean(body.pressEnter),
        });
        sendJson(res, 200, result);
        return;
      }

      if (req.method === "POST" && pathname === "/api/key") {
        const body = await readJsonBody(req);
        const result = await cdp.sendKey(body.key);
        sendJson(res, 200, result);
        return;
      }

      if (req.method === "GET" && pathname === "/api/file-inputs") {
        const inputs = await cdp.listFileInputs();
        sendJson(res, 200, {
          ok: true,
          inputs: inputs.map((inp) => ({
            index: inp.index,
            id: inp.id,
            name: inp.name,
            accept: inp.accept,
            multiple: inp.multiple,
            currentFiles: inp.currentFiles,
          })),
        });
        return;
      }

      if (req.method === "POST" && pathname === "/api/upload-preset") {
        const body = await readJsonBody(req);
        if (Object.hasOwn(body, "path") || Object.hasOwn(body, "filePath")) {
          throw new PresetValidationError(
            "Arbitrary filesystem paths are strictly forbidden; pass presetId only",
          );
        }
        const result = await cdp.attachPreapprovedFile(body.presetId, {
          inputIndex: body.inputIndex,
        });
        sendJson(res, 200, result);
        return;
      }

      if (req.method === "GET" && pathname === "/api/tabs") {
        const tabs = await cdp.listTabs();
        sendJson(res, 200, { ok: true, tabs });
        return;
      }

      if (req.method === "POST" && pathname === "/api/tabs/switch") {
        const body = await readJsonBody(req);
        const meta = await cdp.switchTab(String(body.targetId || ""));
        sendJson(res, 200, { ok: true, ...meta });
        return;
      }

      if (req.method === "POST" && pathname === "/api/tabs/new") {
        const body = await readJsonBody(req);
        const meta = await cdp.newTab(body.url || "https://www.google.com/");
        sendJson(res, 200, { ok: true, ...meta });
        return;
      }

      if (req.method === "POST" && pathname === "/api/tabs/close") {
        const body = await readJsonBody(req);
        const meta = await cdp.closeTab(String(body.targetId || ""));
        sendJson(res, 200, { ok: true, ...meta });
        return;
      }

      if (req.method === "POST" && pathname === "/api/mode") {
        const body = await readJsonBody(req);
        if (body.mode === "desktop") {
          const status = await desktop.getStatus();
          if (!status.available) {
            activeMode = "browser";
            sendJson(res, 200, {
              ok: false,
              fallbackToBrowser: true,
              mode: "browser",
              message: status.message,
              permissions: status,
            });
            return;
          }
          activeMode = "desktop";
          sendJson(res, 200, {
            ok: true,
            mode: "desktop",
            message: status.message,
            permissions: status,
          });
          return;
        }
        activeMode = "browser";
        sendJson(res, 200, {
          ok: true,
          mode: "browser",
          message: "フタを閉じたまま使えるブラウザモードで動作中",
        });
        return;
      }

      sendJson(res, 404, { ok: false, error: `Unknown endpoint: ${pathname}` });
    } catch (err) {
      const status =
        err instanceof PresetValidationError || err instanceof RangeError || err instanceof TypeError
          ? 400
          : 500;
      sendJson(res, status, {
        ok: false,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  });

  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, host, () => {
      server.removeListener("error", reject);
      resolve();
    });
  });

  resetIdleTimer();

  const addr = server.address();
  const boundPort = typeof addr === "object" && addr ? addr.port : port;
  const lanIp = detectLanIpv4();

  async function close() {
    if (closed) return;
    closed = true;
    if (idleTimer) {
      clearTimeout(idleTimer);
      idleTimer = null;
    }
    server.closeAllConnections?.();
    await new Promise((resolve) => server.close(() => resolve()));
    await cdp.close();
  }

  return {
    server,
    cdp,
    desktop,
    host,
    port: boundPort,
    lanIp,
    token,
    localUrl: `http://127.0.0.1:${boundPort}/s/${token}/`,
    lanUrl: `http://${lanIp}:${boundPort}/s/${token}/`,
    close,
  };
}
