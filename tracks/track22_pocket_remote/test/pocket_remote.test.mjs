import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { normalizeSafeNavigationUrl, TRACK22_ROOT } from "../src/cdp_client.mjs";
import { clampViewportPoint, mapClientPointToViewport } from "../src/coords.mjs";
import {
  checkMacDesktopPermissions,
  TCC_FALLBACK_MESSAGE_JA,
} from "../src/macos_desktop.mjs";
import {
  FILE_PRESETS,
  listPublicPresets,
  PresetValidationError,
  QUICK_SNIPPETS,
  resolveApprovedPreset,
  scoreFileInputForPreset,
} from "../src/presets.mjs";
import {
  createPocketBridgeServer,
  generateSecretToken,
  timingSafeVerifyToken,
} from "../src/server.mjs";

/**
 * Fake lightweight browser session for fast auth & security unit tests.
 */
function createStubBrowserSession() {
  return {
    viewportWidth: 1280,
    viewportHeight: 900,
    async getPageMeta() {
      return {
        url: "https://manage.booth.pm/items",
        title: "BOOTH Stub",
        viewport: { width: 1280, height: 900 },
        activeTargetId: "stub-1",
      };
    },
    async listTabs() {
      return [{ id: "stub-1", index: 0, title: "BOOTH Stub", url: "https://manage.booth.pm/items", active: true }];
    },
    async listFileInputs() {
      return [];
    },
    async attachPreapprovedFile(presetId) {
      const p = resolveApprovedPreset(presetId);
      return { ok: true, presetId: p.id, filename: p.filename, matchedIndex: 0, totalInputs: 1 };
    },
    async navigate(rawUrl) {
      const safe = normalizeSafeNavigationUrl(rawUrl);
      return { url: safe, title: "Navigated", viewport: { width: 1280, height: 900 } };
    },
    async close() {},
  };
}

test("1. Timing-safe 256-bit token auth, HttpOnly session cookie, and 429 rate-limit lockout", async () => {
  const token = generateSecretToken();
  assert.equal(token.length, 64, "Token must be 64 hex chars (256 bits)");
  assert.match(token, /^[0-9a-f]{64}$/);

  assert.equal(timingSafeVerifyToken(token, token), true);
  assert.equal(timingSafeVerifyToken("0".repeat(64), token), false);
  assert.equal(timingSafeVerifyToken("short", token), false);
  assert.equal(timingSafeVerifyToken(null, token), false);

  const bridge = await createPocketBridgeServer({
    host: "127.0.0.1",
    port: 0,
    token,
    maxFailedAttempts: 10,
    autoLaunchChrome: false,
    browserSession: createStubBrowserSession(),
  });

  try {
    const base = `http://127.0.0.1:${bridge.port}`;

    // Unauthenticated request -> 403
    const unauthRes = await fetch(`${base}/api/state`);
    assert.equal(unauthRes.status, 403);

    // Wrong magic token -> 403
    const wrongMagic = await fetch(`${base}/s/${"a".repeat(64)}/`);
    assert.equal(wrongMagic.status, 403);

    // Valid /s/<token>/ -> 200 HTML + HttpOnly; SameSite=Strict cookie
    const authRes = await fetch(`${base}/s/${token}/`);
    assert.equal(authRes.status, 200);
    const setCookie = authRes.headers.get("set-cookie") || "";
    assert.match(setCookie, /pocket_session=/);
    assert.match(setCookie, /HttpOnly/i);
    assert.match(setCookie, /SameSite=Strict/i);
    const html = await authRes.text();
    assert.match(html, /PocketBridge/);
    assert.match(html, /📎ファイル添付/);
    assert.match(html, /📋定型文投入/);

    // Subsequent API call with session cookie -> 200
    const cookiePair = setCookie.split(";")[0];
    const stateRes = await fetch(`${base}/api/state`, {
      headers: { Cookie: cookiePair },
    });
    assert.equal(stateRes.status, 200);
    const stateJson = await stateRes.json();
    assert.equal(stateJson.ok, true);
    assert.equal(stateJson.viewport.width, 1280);
    assert.equal(stateJson.viewport.height, 900);
    assert.ok(stateJson.presets.length >= 7);
    assert.ok(stateJson.snippets.length >= 20);

    // Brute-force lockout: already had 2 failed attempts above; trigger up to 10 total -> 429
    let lastStatus = 0;
    for (let i = 0; i < 8; i += 1) {
      const r = await fetch(`${base}/api/state`, {
        headers: { "X-Pocket-Token": "f".repeat(64) },
      });
      lastStatus = r.status;
    }
    assert.equal(lastStatus, 429, "10th failed attempt from IP must return 429 lockout");

    // Subsequent attempt while locked out stays 429
    const lockedRes = await fetch(`${base}/api/state`);
    assert.equal(lockedRes.status, 429);
    assert.ok(lockedRes.headers.get("retry-after"));
  } finally {
    await bridge.close();
  }
});

test("2. Idle timeout automatically shuts down PocketBridge server", async () => {
  let idleFired = false;
  const bridge = await createPocketBridgeServer({
    host: "127.0.0.1",
    port: 0,
    idleTimeoutMs: 140,
    autoLaunchChrome: false,
    browserSession: createStubBrowserSession(),
    onIdleShutdown: () => {
      idleFired = true;
    },
  });

  await new Promise((r) => setTimeout(r, 260));
  assert.equal(idleFired, true, "Idle shutdown callback must fire after idleTimeoutMs");
  await bridge.close();
});

test("3. Coordinate mapping math (1x fit, zoomed/panned rect, and boundary clamping)", () => {
  // Exact 1x iPhone Safari width fit (384 x 270 preserves 1280:900 aspect ratio)
  const fitRect = { left: 12, top: 96, width: 384, height: 270 };
  const center = mapClientPointToViewport({
    clientX: 12 + 192,
    clientY: 96 + 135,
    rect: fitRect,
  });
  assert.equal(center.x, 640);
  assert.equal(center.y, 450);

  // Pinch-zoomed & scrolled rect (e.g., 2.5x zoom panned right & down so rect.left/top are negative)
  const zoomedRect = { left: -350, top: -200, width: 1000, height: 703.125 };
  // Target 75% across (960) and 50% down (450): clientX = -350 + 750 = 400, clientY = -200 + 351.5625 = 151.5625
  const zoomedPt = mapClientPointToViewport({
    clientX: 400,
    clientY: 151.5625,
    rect: zoomedRect,
  });
  assert.equal(zoomedPt.x, 960);
  assert.equal(zoomedPt.y, 450);

  // Out-of-bounds negative & overflow coordinates clamp safely into [0, 1279] x [0, 899]
  const topLeftClamp = mapClientPointToViewport({
    clientX: -9999,
    clientY: -9999,
    rect: fitRect,
  });
  assert.deepEqual(
    { x: topLeftClamp.x, y: topLeftClamp.y },
    { x: 0, y: 0 },
  );

  const bottomRightClamp = mapClientPointToViewport({
    clientX: 9999,
    clientY: 9999,
    rect: fitRect,
  });
  assert.deepEqual(
    { x: bottomRightClamp.x, y: bottomRightClamp.y },
    { x: 1279, y: 899 },
  );

  assert.deepEqual(clampViewportPoint({ x: -12, y: 950 }), { x: 0, y: 899 });
  assert.throws(() => mapClientPointToViewport({ clientX: 10, clientY: 10, rect: { left: 0, top: 0, width: 0, height: 100 } }), RangeError);
  assert.throws(() => mapClientPointToViewport({ clientX: Number.NaN, clientY: 10, rect: fitRect }), TypeError);
});

test("4. Strict allowlist-only file preset security, multi-input scoring, URL scheme guard, and macOS TCC check", async () => {
  // All 7 studio deliverables exist on disk and resolve cleanly
  const expectedIds = [
    "booth_cover",
    "booth_zip",
    "kdp_epub",
    "kdp_cover",
    "kdp_interior_pdf",
    "kdp_wrap_pdf",
    "vscode_vsix",
  ];
  for (const id of expectedIds) {
    const resolved = resolveApprovedPreset(id);
    assert.equal(resolved.id, id);
    assert.equal(fs.existsSync(resolved.path), true, `Deliverable missing: ${resolved.path}`);
  }
  assert.equal(listPublicPresets().length, expectedIds.length);
  assert.ok(QUICK_SNIPPETS.some((s) => s.category === "Apify"));
  assert.ok(QUICK_SNIPPETS.some((s) => s.category === "KDP"));
  assert.ok(QUICK_SNIPPETS.some((s) => s.category === "ココナラ"));

  // Path traversal, unknown IDs, prototype keys must throw PresetValidationError
  for (const malicious of [
    "",
    "unknown_preset",
    "../booth_cover",
    "../../etc/passwd",
    "/etc/passwd",
    "booth_cover/../../secret",
    "__proto__",
    "constructor",
    "toString",
    null,
    123,
  ]) {
    assert.throws(() => resolveApprovedPreset(malicious), PresetValidationError);
  }

  // Multi-input matching: BOOTH cover (.png) vs BOOTH archive (.zip)
  const imageInput = { accept: "image/*,.png,.jpg", id: "item_cover" };
  const zipInput = { accept: ".zip,application/zip", id: "item_file" };
  const genericInput = { accept: "", id: "downloadable_file" };

  assert.ok(
    scoreFileInputForPreset(FILE_PRESETS.booth_cover, imageInput) >
      scoreFileInputForPreset(FILE_PRESETS.booth_cover, zipInput),
  );
  assert.ok(
    scoreFileInputForPreset(FILE_PRESETS.booth_zip, zipInput) >
      scoreFileInputForPreset(FILE_PRESETS.booth_zip, imageInput),
  );
  assert.ok(
    scoreFileInputForPreset(FILE_PRESETS.booth_zip, genericInput) >
      scoreFileInputForPreset(FILE_PRESETS.booth_zip, imageInput),
  );

  // HTTP endpoint rejects unknown preset and raw filePath injection with 400
  const token = generateSecretToken();
  const bridge = await createPocketBridgeServer({
    host: "127.0.0.1",
    port: 0,
    token,
    autoLaunchChrome: false,
    browserSession: createStubBrowserSession(),
  });

  try {
    const base = `http://127.0.0.1:${bridge.port}`;
    const headers = {
      "Content-Type": "application/json",
      "X-Pocket-Token": token,
    };

    const badPresetRes = await fetch(`${base}/api/upload-preset`, {
      method: "POST",
      headers,
      body: JSON.stringify({ presetId: "../../etc/passwd" }),
    });
    assert.equal(badPresetRes.status, 400);

    const rawPathRes = await fetch(`${base}/api/upload-preset`, {
      method: "POST",
      headers,
      body: JSON.stringify({ presetId: "booth_cover", path: "/etc/hosts" }),
    });
    assert.equal(rawPathRes.status, 400);

    const fileUrlRes = await fetch(`${base}/api/navigate`, {
      method: "POST",
      headers,
      body: JSON.stringify({ url: "file:///etc/passwd" }),
    });
    assert.equal(fileUrlRes.status, 400);

    // Verify macOS TCC check returns clean Japanese fallback message without popups
    const perms = await checkMacDesktopPermissions();
    assert.equal(typeof perms.screenCapture, "boolean");
    assert.equal(typeof perms.accessibility, "boolean");
    if (!perms.available) {
      assert.equal(perms.message, TCC_FALLBACK_MESSAGE_JA);
      const modeRes = await fetch(`${base}/api/mode`, {
        method: "POST",
        headers,
        body: JSON.stringify({ mode: "desktop" }),
      });
      const modeJson = await modeRes.json();
      assert.equal(modeJson.mode, "browser");
      assert.equal(modeJson.message, TCC_FALLBACK_MESSAGE_JA);
    }
  } finally {
    await bridge.close();
  }
});

test("5. REAL End-to-End Headless Chrome Integration Test (Screenshot, Coordinate Tap, Japanese Text, 1-Tap Multi-File Upload, Zero Orphan Processes)", async () => {
  // 1. Spin up local target web app with known coordinate layout + dual file inputs
  let serverReceivedSubmission = null;

  const targetHtml = `<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <title>PocketBridge E2E Target</title>
  <style>
    html, body { margin: 0; padding: 0; width: 1280px; height: 900px; background: #f8fafc; font-family: sans-serif; }
    #txt {
      position: absolute;
      left: 80px;
      top: 100px;
      width: 420px;
      height: 52px;
      font-size: 20px;
      padding: 4px 10px;
      box-sizing: border-box;
    }
    #filesBox {
      position: absolute;
      left: 80px;
      top: 180px;
    }
    #submitBtn {
      position: absolute;
      left: 80px;
      top: 270px;
      width: 240px;
      height: 60px;
      background: #2563eb;
      color: #fff;
      font-size: 20px;
      border: none;
      border-radius: 8px;
      cursor: pointer;
    }
    #tallSpacer {
      position: absolute;
      top: 1600px;
      left: 80px;
      height: 100px;
    }
  </style>
</head>
<body>
  <input id="txt" type="text" value="初期ダミー文字列" />
  <div id="filesBox">
    <input id="coverInput" type="file" accept=".png,image/png" />
    <input id="zipInput" type="file" accept=".zip,application/zip" />
  </div>
  <button id="submitBtn" type="button">出品データを確定</button>
  <div id="tallSpacer">Bottom Marker</div>

  <script>
    window.__events = { clickedSubmit: false, clickCoords: null };
    document.getElementById("submitBtn").addEventListener("click", async (ev) => {
      const payload = {
        clicked: true,
        clickX: ev.clientX,
        clickY: ev.clientY,
        textValue: document.getElementById("txt").value,
        coverFile: document.getElementById("coverInput").files[0]?.name || null,
        coverBytes: document.getElementById("coverInput").files[0]?.size || 0,
        zipFile: document.getElementById("zipInput").files[0]?.name || null,
        zipBytes: document.getElementById("zipInput").files[0]?.size || 0,
      };
      window.__submitted = payload;
      await fetch("/submitted", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    });
  </script>
</body>
</html>`;

  const targetServer = http.createServer((req, res) => {
    if (req.method === "POST" && req.url === "/submitted") {
      const chunks = [];
      req.on("data", (c) => chunks.push(c));
      req.on("end", () => {
        serverReceivedSubmission = JSON.parse(Buffer.concat(chunks).toString("utf-8"));
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true }));
      });
      return;
    }
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(targetHtml);
  });

  await new Promise((resolve) => targetServer.listen(0, "127.0.0.1", resolve));
  const targetPort = targetServer.address().port;
  const targetUrl = `http://127.0.0.1:${targetPort}/`;

  const tmpProfileDir = fs.mkdtempSync(path.join(os.tmpdir(), "pocketbridge-e2e-profile-"));
  let bridge = null;

  try {
    bridge = await createPocketBridgeServer({
      host: "127.0.0.1",
      port: 0,
      autoLaunchChrome: true,
      chromeOptions: {
        userDataDir: tmpProfileDir,
        initialUrl: "about:blank",
      },
    });

    const base = `http://127.0.0.1:${bridge.port}`;

    // Authenticate via /s/<token>/ and capture session cookie
    const entryRes = await fetch(`${base}/s/${bridge.token}/`);
    assert.equal(entryRes.status, 200);
    const cookie = (entryRes.headers.get("set-cookie") || "").split(";")[0];
    const authHeaders = {
      Cookie: cookie,
      "Content-Type": "application/json",
    };

    // Navigate to local E2E test page
    const navRes = await fetch(`${base}/api/navigate`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ url: targetUrl }),
    });
    assert.equal(navRes.status, 200);
    const navJson = await navRes.json();
    assert.equal(navJson.url, targetUrl);
    assert.equal(navJson.title, "PocketBridge E2E Target");

    // Capture live JPEG screenshot -> verify valid 0xFF 0xD8 JPEG header & 0xFF 0xD9 trailer
    const shotRes = await fetch(`${base}/api/screenshot`, { headers: { Cookie: cookie } });
    assert.equal(shotRes.status, 200);
    assert.equal(shotRes.headers.get("content-type"), "image/jpeg");
    assert.equal(shotRes.headers.get("x-viewport-width"), "1280");
    assert.equal(shotRes.headers.get("x-viewport-height"), "900");
    const jpegBuf = Buffer.from(await shotRes.arrayBuffer());
    assert.equal(jpegBuf[0], 0xff, "JPEG SOI byte 0 must be 0xFF");
    assert.equal(jpegBuf[1], 0xd8, "JPEG SOI byte 1 must be 0xD8");
    assert.equal(jpegBuf[jpegBuf.length - 2], 0xff, "JPEG EOI byte -2 must be 0xFF");
    assert.equal(jpegBuf[jpegBuf.length - 1], 0xd9, "JPEG EOI byte -1 must be 0xD9");
    assert.ok(jpegBuf.length > 3000, `Expected non-trivial JPEG screenshot, got ${jpegBuf.length} bytes`);

    // Tap <input id="txt"> (logical center: x=290, y=126) via simulated iPhone Safari rect (320 x 225)
    // x=290 on 1280 -> ratioX = 290/1280 -> clientX = 10 + 320*(290/1280) = 82.5
    // y=126 on 900  -> ratioY = 126/900  -> clientY = 50 + 225*(126/900)  = 81.5
    const clickInputRes = await fetch(`${base}/api/click`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({
        clientX: 82.5,
        clientY: 81.5,
        rect: { left: 10, top: 50, width: 320, height: 225 },
      }),
    });
    assert.equal(clickInputRes.status, 200);
    const clickInputJson = await clickInputRes.json();
    assert.equal(clickInputJson.x, 290);
    assert.equal(clickInputJson.y, 126);
    assert.equal(clickInputJson.activeElement?.id, "txt");
    assert.equal(clickInputJson.activeElement?.isEditable, true);

    // Clear initial placeholder and type Japanese + ASCII email text via /api/type
    const typeRes = await fetch(`${base}/api/type`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({
        text: "テスト123@example.com",
        clearFirst: true,
      }),
    });
    assert.equal(typeRes.status, 200);

    // 1-Tap attach booth_cover (.png) and booth_zip (.zip) — automatic accept matching!
    const attachCoverRes = await fetch(`${base}/api/upload-preset`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ presetId: "booth_cover" }),
    });
    assert.equal(attachCoverRes.status, 200);
    const attachCoverJson = await attachCoverRes.json();
    assert.equal(attachCoverJson.filename, "jp-backoffice-top5-cover.png");
    assert.equal(attachCoverJson.matchedIndex, 0);

    const attachZipRes = await fetch(`${base}/api/upload-preset`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ presetId: "booth_zip" }),
    });
    assert.equal(attachZipRes.status, 200);
    const attachZipJson = await attachZipRes.json();
    assert.equal(attachZipJson.filename, "jp-backoffice-top5-pro-kit-v2.0.0.zip");
    assert.equal(attachZipJson.matchedIndex, 1);

    // Tap <button id="submitBtn"> (logical center: x=200, y=300)
    const clickBtnRes = await fetch(`${base}/api/click`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ x: 200, y: 300 }),
    });
    assert.equal(clickBtnRes.status, 200);

    // Wait briefly for the page's fetch("/submitted") to complete
    for (let i = 0; i < 25 && !serverReceivedSubmission; i += 1) {
      await new Promise((r) => setTimeout(r, 40));
    }

    assert.ok(serverReceivedSubmission, "Submit button coordinate tap must trigger form submission");
    assert.equal(serverReceivedSubmission.clicked, true);
    assert.equal(serverReceivedSubmission.clickX, 200);
    assert.equal(serverReceivedSubmission.clickY, 300);
    assert.equal(serverReceivedSubmission.textValue, "テスト123@example.com");
    assert.equal(serverReceivedSubmission.coverFile, "jp-backoffice-top5-cover.png");
    assert.ok(serverReceivedSubmission.coverBytes > 10000);
    assert.equal(serverReceivedSubmission.zipFile, "jp-backoffice-top5-pro-kit-v2.0.0.zip");
    assert.ok(serverReceivedSubmission.zipBytes > 100000);

    // Also test smooth scroll via /api/scroll
    const scrollRes = await fetch(`${base}/api/scroll`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ deltaX: 0, deltaY: 320 }),
    });
    assert.equal(scrollRes.status, 200);

    // Test multi-tab creation, switching, and closing + special keys (Enter, Backspace)
    const newTabRes = await fetch(`${base}/api/tabs/new`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ url: targetUrl }),
    });
    assert.equal(newTabRes.status, 200);

    const tabsRes = await fetch(`${base}/api/tabs`, { headers: { Cookie: cookie } });
    const tabsJson = await tabsRes.json();
    assert.equal(tabsJson.tabs.length, 2);

    const keyRes = await fetch(`${base}/api/key`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ key: "Escape" }),
    });
    assert.equal(keyRes.status, 200);

    const closeTabRes = await fetch(`${base}/api/tabs/close`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ targetId: tabsJson.tabs[1].id }),
    });
    assert.equal(closeTabRes.status, 200);

    // Shut down PocketBridge + Headless Chrome cleanly
    await bridge.close();
    bridge = null;

    // Verify 0 orphan Chrome processes referencing tmpProfileDir
    const psOut = execFileSync("ps", ["aux"], { encoding: "utf-8" });
    const orphans = psOut
      .split("\n")
      .filter((line) => line.includes(tmpProfileDir) && !line.includes("grep"));
    assert.equal(
      orphans.length,
      0,
      `Expected 0 orphan Chrome processes after close(), found: ${orphans.join("\n")}`,
    );
  } finally {
    if (bridge) {
      await bridge.close();
    }
    targetServer.closeAllConnections?.();
    await new Promise((resolve) => targetServer.close(() => resolve()));
    fs.rmSync(tmpProfileDir, {
      recursive: true,
      force: true,
      maxRetries: 5,
      retryDelay: 150,
    });
  }
});

test("6. CLI daemon lifecycle writes 0600 runtime info and cleans up Chrome on SIGTERM", async () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "pocketbridge-cli-"));
  const tmpProfile = path.join(tmpDir, "profile");
  const runtimeFile = path.join(tmpDir, ".runtime_secret.json");
  const cliPath = path.join(TRACK22_ROOT, "src", "cli.mjs");

  const proc = spawn(
    process.execPath,
    [
      cliPath,
      "--host",
      "127.0.0.1",
      "--port",
      "0",
      "--url",
      "about:blank",
      "--profile-dir",
      tmpProfile,
      "--runtime-file",
      runtimeFile,
    ],
    { stdio: ["ignore", "pipe", "pipe"] },
  );

  try {
    await new Promise((resolve, reject) => {
      let out = "";
      const timer = setTimeout(() => reject(new Error(`CLI startup timeout: ${out}`)), 12000);
      proc.stdout.on("data", (chunk) => {
        out += chunk.toString("utf-8");
        if (out.includes("PocketBridge Remote Console Ready")) {
          clearTimeout(timer);
          resolve();
        }
      });
      proc.once("exit", (code) => {
        clearTimeout(timer);
        reject(new Error(`CLI exited early with code ${code}`));
      });
    });

    assert.equal(fs.existsSync(runtimeFile), true);
    const mode = fs.statSync(runtimeFile).mode & 0o777;
    assert.equal(mode, 0o600, "Runtime secret file must have 0600 permissions");

    const info = JSON.parse(fs.readFileSync(runtimeFile, "utf-8"));
    assert.equal(info.token.length, 64);
    const uiRes = await fetch(info.localUrl);
    assert.equal(uiRes.status, 200);

    proc.kill("SIGTERM");
    await new Promise((resolve) => proc.once("exit", resolve));
    assert.equal(fs.existsSync(runtimeFile), false, "Runtime secret file must be unlinked on SIGTERM");

    const psOut = execFileSync("ps", ["aux"], { encoding: "utf-8" });
    const orphans = psOut
      .split("\n")
      .filter((line) => line.includes(tmpProfile) && !line.includes("grep"));
    assert.equal(orphans.length, 0, "Zero orphan Chrome processes must remain after CLI SIGTERM");
  } finally {
    if (proc.exitCode === null && proc.signalCode === null) {
      proc.kill("SIGKILL");
    }
    fs.rmSync(tmpDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 150 });
  }
});
