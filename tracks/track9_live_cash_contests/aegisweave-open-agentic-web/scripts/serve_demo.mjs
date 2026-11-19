#!/usr/bin/env node
/**
 * AegisWeave Multi-Origin Open Agentic Web Local Demo Server
 * Spins up 3 distinct loopback origins with real CORS headers to demonstrate
 * all 7 MVP Profile 0.3 Section 6 Interoperability Checks live in any browser:
 *   - Caller Hub Origin:      http://localhost:8781  (AegisWeave UI + Hub)
 *   - Legitimate Peer Origin: http://localhost:8782  (Nordic Compute + Kyoto Studio)
 *   - Adversarial Peer Origin:http://localhost:8783  (Rogue Peer + Redirect + Tamper testbed)
 */

import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "..");

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".mjs": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".md": "text/markdown; charset=utf-8",
  ".txt": "text/plain; charset=utf-8"
};

function createStaticHandler({ baseDir, enableCors = true, receivedAuthLog = [], tamperState = null, redirectTargetFn = null }) {
  return async (req, res) => {
    const reqUrl = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
    if (enableCors) {
      res.setHeader("Access-Control-Allow-Origin", "*");
      res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
      res.setHeader("Access-Control-Allow-Headers", "Content-Type");
      res.setHeader("Vary", "Origin");
    }

    if (req.method === "OPTIONS") {
      res.writeHead(204);
      res.end();
      return;
    }

    // Record whether ANY Authorization or secret-like header ever arrived at this origin
    receivedAuthLog.push({
      path: reqUrl.pathname,
      hasAuthorizationHeader: Boolean(req.headers.authorization),
      authorizationPreview: req.headers.authorization ? "[PRESENT]" : null,
      timestamp: new Date().toISOString()
    });

    if (reqUrl.pathname === "/_inspect_headers") {
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ requests: receivedAuthLog }));
      return;
    }

    if (redirectTargetFn && reqUrl.pathname.startsWith("/redirect/")) {
      const target = redirectTargetFn(reqUrl.pathname.replace(/^\/redirect\//, ""));
      res.writeHead(302, { Location: target });
      res.end();
      return;
    }

    let relPath = decodeURIComponent(reqUrl.pathname);
    if (relPath === "/") relPath = "/index.html";
    const resolvedPath = path.resolve(baseDir, `.${relPath}`);

    // Prevent directory traversal outside baseDir
    if (!resolvedPath.startsWith(baseDir)) {
      res.writeHead(403, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("Forbidden");
      return;
    }

    try {
      let data = await fs.readFile(resolvedPath);
      if (tamperState?.enabled && resolvedPath.endsWith(".network.json")) {
        const parsed = JSON.parse(data.toString("utf-8"));
        parsed.metadata = {
          ...(parsed.metadata || {}),
          tamper_notice: "RUNTIME_HASH_DRIFT_INJECTED_FOR_TEST"
        };
        data = Buffer.from(JSON.stringify(parsed, null, 2), "utf-8");
      }
      const ext = path.extname(resolvedPath).toLowerCase();
      res.writeHead(200, { "Content-Type": MIME_TYPES[ext] || "application/octet-stream" });
      res.end(data);
    } catch {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end(`Not Found: ${relPath}`);
    }
  };
}

export async function startDemoServers({ callerPort = 8781, legitPeerPort = 8782, roguePeerPort = 8783 } = {}) {
  const callerAuthLog = [];
  const legitAuthLog = [];
  const rogueAuthLog = [];
  const tamperState = { enabled: false };

  let rogueOrigin = "";

  const callerServer = http.createServer(
    createStaticHandler({
      baseDir: ROOT_DIR,
      enableCors: true,
      receivedAuthLog: callerAuthLog
    })
  );

  const legitPeerServer = http.createServer(
    createStaticHandler({
      baseDir: path.join(ROOT_DIR, "peers"),
      enableCors: true,
      receivedAuthLog: legitAuthLog,
      tamperState,
      redirectTargetFn: (rest) => `${rogueOrigin}/${rest}`
    })
  );

  const roguePeerServer = http.createServer(
    createStaticHandler({
      baseDir: path.join(ROOT_DIR, "peers", "rogue_peer"),
      enableCors: true,
      receivedAuthLog: rogueAuthLog
    })
  );

  await Promise.all([
    new Promise((resolve) => callerServer.listen(callerPort, "127.0.0.1", resolve)),
    new Promise((resolve) => legitPeerServer.listen(legitPeerPort, "127.0.0.1", resolve)),
    new Promise((resolve) => roguePeerServer.listen(roguePeerPort, "127.0.0.1", resolve))
  ]);

  const callerAddr = callerServer.address();
  const legitAddr = legitPeerServer.address();
  const rogueAddr = roguePeerServer.address();

  const callerOrigin = `http://127.0.0.1:${callerAddr.port}`;
  const legitOrigin = `http://127.0.0.1:${legitAddr.port}`;
  rogueOrigin = `http://127.0.0.1:${rogueAddr.port}`;

  return {
    callerOrigin,
    legitOrigin,
    rogueOrigin,
    callerAuthLog,
    legitAuthLog,
    rogueAuthLog,
    tamperState,
    async close() {
      await Promise.all([
        new Promise((resolve) => callerServer.close(resolve)),
        new Promise((resolve) => legitPeerServer.close(resolve)),
        new Promise((resolve) => roguePeerServer.close(resolve))
      ]);
    }
  };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const servers = await startDemoServers();
  console.log("AegisWeave Open Agentic Web Multi-Origin Demo Running:");
  console.log(`  Caller Hub UI:         ${servers.callerOrigin}/`);
  console.log(`  Legitimate Peer Host:  ${servers.legitOrigin}/nordic_compute/nordic_compute`);
  console.log(`                         ${servers.legitOrigin}/kyoto_studio/kyoto_studio`);
  console.log(`  Adversarial Peer Host: ${servers.rogueOrigin}/rogue_peer`);
  console.log("Press Ctrl+C to stop.");
}
