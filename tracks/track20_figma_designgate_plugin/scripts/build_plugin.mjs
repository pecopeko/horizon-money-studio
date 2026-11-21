#!/usr/bin/env node
/**
 * Zero-dependency bundler for DesignGate Figma Plugin.
 *
 * 1. Combines `src/core/audit-engine.js` + `src/figma/controller.js` into a
 *    100% standalone `code.js` with ZERO runtime `require()` calls so Figma's
 *    QuickJS plugin sandbox loads it directly via `manifest.json`.
 * 2. Syncs `src/core/audit-engine.js` -> `docs/audit-engine.js` so the
 *    GitHub Pages Browser Preview Simulator runs the exact same engine.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

const ENGINE_SRC = path.join(ROOT, "src", "core", "audit-engine.js");
const CONTROLLER_SRC = path.join(ROOT, "src", "figma", "controller.js");
const CODE_OUT = path.join(ROOT, "code.js");
const DOCS_ENGINE_OUT = path.join(ROOT, "docs", "audit-engine.js");

function main() {
  const engineCode = fs.readFileSync(ENGINE_SRC, "utf8");
  const controllerCode = fs.readFileSync(CONTROLLER_SRC, "utf8");

  // Wrap engine & controller in isolated IIFEs capturing exports without needing Node `require`
  const standaloneBundle = [
    "/**",
    " * DesignGate — Production Figma Plugin Sandbox Bundle (`code.js`)",
    " * Auto-assembled from `src/core/audit-engine.js` + `src/figma/controller.js`.",
    " * Zero external dependencies. 100% local execution (`networkAccess: none`).",
    " */",
    "(function (globalScope) {",
    '  "use strict";',
    "",
    "  // --- Module 1: DesignGate Core Audit Engine ---",
    "  var __dgEngineModule = { exports: {} };",
    "  (function (module, exports) {",
    engineCode,
    "  })(__dgEngineModule, __dgEngineModule.exports);",
    "  var DesignGateEngine = __dgEngineModule.exports;",
    "",
    "  // --- Module 2: Figma Sandbox Controller ---",
    "  var __dgControllerModule = { exports: {} };",
    "  (function (module, exports) {",
    controllerCode,
    "  })(__dgControllerModule, __dgControllerModule.exports);",
    "  var DesignGateController = __dgControllerModule.exports;",
    "",
    "  function bootPlugin(figmaInstance) {",
    "    var controller = DesignGateController.createController(figmaInstance, DesignGateEngine);",
    "    controller.boot();",
    "    return controller;",
    "  }",
    "",
    '  if (typeof module === "object" && module.exports) {',
    "    module.exports = {",
    "      DesignGateEngine: DesignGateEngine,",
    "      DesignGateController: DesignGateController,",
    "      bootPlugin: bootPlugin,",
    "    };",
    "  }",
    "",
    '  if (typeof figma !== "undefined" && figma && typeof figma.showUI === "function") {',
    "    bootPlugin(figma);",
    "  }",
    '})(typeof globalThis !== "undefined" ? globalThis : this);',
    "",
  ].join("\n");

  fs.writeFileSync(CODE_OUT, standaloneBundle, "utf8");

  fs.mkdirSync(path.dirname(DOCS_ENGINE_OUT), { recursive: true });
  fs.writeFileSync(DOCS_ENGINE_OUT, engineCode, "utf8");

  console.log(
    "Built code.js (" +
      Buffer.byteLength(standaloneBundle, "utf8") +
      " bytes) and synced docs/audit-engine.js (" +
      Buffer.byteLength(engineCode, "utf8") +
      " bytes)."
  );
}

main();
