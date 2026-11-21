#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { DEFAULT_PROFILE_DIR, TRACK22_ROOT } from "./cdp_client.mjs";
import { createPocketBridgeServer, generateSecretToken } from "./server.mjs";

function parseArgs(argv) {
  const opts = {
    host: process.env.POCKET_HOST || "0.0.0.0",
    port: Number(process.env.POCKET_PORT || 8788),
    idleMinutes: Number(process.env.POCKET_IDLE_MINUTES || 120),
    initialUrl: process.env.POCKET_INITIAL_URL || "https://www.google.com/",
    profileDir: process.env.POCKET_PROFILE_DIR || DEFAULT_PROFILE_DIR,
    runtimeFile:
      process.env.POCKET_RUNTIME_FILE ||
      path.join(TRACK22_ROOT, ".runtime_secret.json"),
    token: process.env.POCKET_BRIDGE_TOKEN || generateSecretToken(),
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--host" && argv[i + 1]) opts.host = argv[++i];
    else if (arg === "--port" && argv[i + 1]) opts.port = Number(argv[++i]);
    else if (arg === "--idle-minutes" && argv[i + 1]) opts.idleMinutes = Number(argv[++i]);
    else if (arg === "--url" && argv[i + 1]) opts.initialUrl = argv[++i];
    else if (arg === "--profile-dir" && argv[i + 1]) opts.profileDir = path.resolve(argv[++i]);
    else if (arg === "--runtime-file" && argv[i + 1]) opts.runtimeFile = path.resolve(argv[++i]);
    else if (arg === "--token" && argv[i + 1]) opts.token = argv[++i];
  }
  return opts;
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));

  const cleanupRuntimeFile = () => {
    try {
      if (opts.runtimeFile && fs.existsSync(opts.runtimeFile)) {
        fs.rmSync(opts.runtimeFile, { force: true });
      }
    } catch {
      // ignore
    }
  };

  const bridge = await createPocketBridgeServer({
    host: opts.host,
    port: opts.port,
    token: opts.token,
    idleTimeoutMs: Math.max(1, opts.idleMinutes) * 60 * 1000,
    chromeOptions: {
      userDataDir: opts.profileDir,
      initialUrl: opts.initialUrl,
    },
    onIdleShutdown: () => {
      cleanupRuntimeFile();
      process.exit(0);
    },
  });

  const info = {
    pid: process.pid,
    host: bridge.host,
    lanIp: bridge.lanIp,
    port: bridge.port,
    token: bridge.token,
    localUrl: bridge.localUrl,
    lanUrl: bridge.lanUrl,
    idleMinutes: opts.idleMinutes,
    startedAt: new Date().toISOString(),
  };

  fs.writeFileSync(opts.runtimeFile, JSON.stringify(info, null, 2), {
    encoding: "utf-8",
    mode: 0o600,
  });

  console.log("=== PocketBridge Remote Console Ready ===");
  console.log(`iPhone Safari LAN URL : ${bridge.lanUrl}`);
  console.log(`Local Loopback URL    : ${bridge.localUrl}`);
  console.log(`Auto-Idle Shutdown    : ${opts.idleMinutes} minutes`);

  const shutdown = async () => {
    cleanupRuntimeFile();
    await bridge.close();
    process.exit(0);
  };

  process.once("SIGINT", shutdown);
  process.once("SIGTERM", shutdown);
}

main().catch((err) => {
  console.error("[PocketBridge fatal]", err);
  process.exit(1);
});
