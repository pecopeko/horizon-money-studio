/**
 * DesignGate Figma Sandbox Controller
 *
 * Bridges Figma Plugin API (`figma.*` SceneNodes, `figma.viewport`, `figma.payments`,
 * `figma.ui.postMessage`) with `DesignGateEngine`.
 *
 * Bundled into standalone `code.js` by `scripts/build_plugin.mjs` so Figma's QuickJS
 * runtime requires zero external module loader at runtime.
 */

(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  if (root && typeof root === "object") {
    root.DesignGateController = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function isMixedSymbol(figmaApi, val) {
    return Boolean(figmaApi && figmaApi.mixed && val === figmaApi.mixed);
  }

  function safeReadFills(figmaApi, node) {
    if (!node || !("fills" in node)) return [];
    let raw = node.fills;
    if (isMixedSymbol(figmaApi, raw)) {
      if (typeof node.getRangeFills === "function" && node.characters && node.characters.length > 0) {
        try {
          raw = node.getRangeFills(0, 1);
        } catch (_err) {
          return [];
        }
      } else {
        return [];
      }
    }
    return Array.isArray(raw) ? raw : [];
  }

  function safeReadFontSize(figmaApi, node) {
    if (!node || node.type !== "TEXT") return undefined;
    let size = node.fontSize;
    if (isMixedSymbol(figmaApi, size)) {
      if (typeof node.getRangeFontSize === "function" && node.characters && node.characters.length > 0) {
        try {
          size = node.getRangeFontSize(0, 1);
        } catch (_err) {
          return 14;
        }
      } else {
        return 14;
      }
    }
    return typeof size === "number" ? size : 14;
  }

  function safeReadFontStyle(figmaApi, node) {
    if (!node || node.type !== "TEXT") return "";
    let fontName = node.fontName;
    if (isMixedSymbol(figmaApi, fontName)) {
      if (typeof node.getRangeFontName === "function" && node.characters && node.characters.length > 0) {
        try {
          fontName = node.getRangeFontName(0, 1);
        } catch (_err) {
          return "";
        }
      } else {
        return "";
      }
    }
    if (fontName && typeof fontName === "object" && typeof fontName.style === "string") {
      return fontName.style;
    }
    return "";
  }

  function safeReadLineHeightPx(figmaApi, node, fontSize) {
    if (!node || node.type !== "TEXT" || !node.lineHeight) return undefined;
    let lh = node.lineHeight;
    if (isMixedSymbol(figmaApi, lh)) {
      if (typeof node.getRangeLineHeight === "function" && node.characters && node.characters.length > 0) {
        try {
          lh = node.getRangeLineHeight(0, 1);
        } catch (_err) {
          return undefined;
        }
      } else {
        return undefined;
      }
    }
    if (!lh || typeof lh !== "object") return undefined;
    if (lh.unit === "PIXELS" && typeof lh.value === "number") return lh.value;
    if (lh.unit === "PERCENT" && typeof lh.value === "number") {
      return ((fontSize || 14) * lh.value) / 100;
    }
    return undefined;
  }

  function getPageCanvasBackground(page) {
    if (page && Array.isArray(page.backgrounds)) {
      for (let i = 0; i < page.backgrounds.length; i += 1) {
        const bg = page.backgrounds[i];
        if (bg && bg.visible !== false && bg.type === "SOLID" && bg.color) {
          return {
            r: bg.color.r,
            g: bg.color.g,
            b: bg.color.b,
            a: 1,
          };
        }
      }
    }
    return { r: 1, g: 1, b: 1, a: 1 };
  }

  function boundsOverlap(inner, outer) {
    if (!inner || !outer) return false;
    const ix = inner.x || 0;
    const iy = inner.y || 0;
    const iw = inner.width || 0;
    const ih = inner.height || 0;
    const ox = outer.x || 0;
    const oy = outer.y || 0;
    const ow = outer.width || 0;
    const oh = outer.height || 0;
    if (iw <= 0 || ih <= 0 || ow <= 0 || oh <= 0) return false;
    const cx = ix + iw / 2;
    const cy = iy + ih / 2;
    return cx >= ox && cx <= ox + ow && cy >= oy && cy <= oy + oh;
  }

  function getNodeBox(node) {
    if (node.absoluteBoundingBox) return node.absoluteBoundingBox;
    if (typeof node.x === "number" && typeof node.y === "number") {
      return {
        x: node.x,
        y: node.y,
        width: typeof node.width === "number" ? node.width : 0,
        height: typeof node.height === "number" ? node.height : 0,
      };
    }
    return null;
  }

  /**
   * Resolves effective background behind `node` by walking ancestors from page root down,
   * and checking earlier overlapping SOLID sibling shapes inside the same parent.
   */
  function resolveNodeBackground(figmaApi, engine, node, canvasBg) {
    const chain = [];
    let cursor = node.parent;
    while (cursor && cursor.type !== "PAGE" && cursor.type !== "DOCUMENT") {
      chain.unshift(cursor);
      cursor = cursor.parent;
    }

    const layers = [];
    for (let i = 0; i < chain.length; i += 1) {
      const anc = chain[i];
      layers.push({
        visible: anc.visible !== false,
        opacity: typeof anc.opacity === "number" ? anc.opacity : 1,
        fills: safeReadFills(figmaApi, anc),
      });
    }

    // Check earlier sibling background shapes (e.g., RECTANGLE behind TEXT inside a GROUP)
    const parent = node.parent;
    if (parent && Array.isArray(parent.children)) {
      const selfIdx = parent.children.indexOf(node);
      const nodeBox = getNodeBox(node);
      for (let s = 0; s < selfIdx; s += 1) {
        const sib = parent.children[s];
        if (!sib || sib.visible === false) continue;
        if (sib.type === "TEXT") continue;
        const sibFills = safeReadFills(figmaApi, sib);
        if (sibFills.length === 0) continue;
        const sibBox = getNodeBox(sib);
        if (nodeBox && sibBox && boundsOverlap(nodeBox, sibBox)) {
          layers.push({
            visible: true,
            opacity: typeof sib.opacity === "number" ? sib.opacity : 1,
            fills: sibFills,
          });
        }
      }
    }

    return engine.resolveEffectiveBackground(layers, canvasBg);
  }

  function extractFrameSnapshot(figmaApi, engine, rootNode, canvasBg) {
    const collected = [];

    function walk(node, inheritedOpacity) {
      if (!node || node.visible === false) return;
      const ownOpacity = typeof node.opacity === "number" ? node.opacity : 1;
      const effectiveOpacity = inheritedOpacity * ownOpacity;

      if (node !== rootNode) {
        const fills = safeReadFills(figmaApi, node);
        const fontSize = safeReadFontSize(figmaApi, node);
        const fontStyle = safeReadFontStyle(figmaApi, node);
        const lineHeightPx = safeReadLineHeightPx(figmaApi, node, fontSize);
        const effectiveBackground = resolveNodeBackground(figmaApi, engine, node, canvasBg);

        collected.push({
          id: node.id,
          name: node.name || node.type,
          type: node.type,
          visible: true,
          characters: node.type === "TEXT" ? String(node.characters || "") : undefined,
          fontSize,
          fontWeight: typeof node.fontWeight === "number" ? node.fontWeight : undefined,
          fontStyle,
          lineHeightPx,
          width: typeof node.width === "number" ? node.width : undefined,
          height: typeof node.height === "number" ? node.height : undefined,
          opacity: effectiveOpacity,
          fills,
          effectiveBackground,
          checked: node.checked === true,
          isInteractive: node.isInteractive === true,
          isStatusBadge: node.isStatusBadge === true,
          role: node.role,
          headingLevel: node.headingLevel,
          ctaKind: node.ctaKind,
        });
      }

      if (Array.isArray(node.children)) {
        for (let i = 0; i < node.children.length; i += 1) {
          walk(node.children[i], effectiveOpacity);
        }
      }
    }

    // If rootNode itself is a leaf (e.g. designer selected a single TEXT layer), audit it directly
    if (!Array.isArray(rootNode.children) || rootNode.children.length === 0) {
      const fills = safeReadFills(figmaApi, rootNode);
      const fontSize = safeReadFontSize(figmaApi, rootNode);
      const fontStyle = safeReadFontStyle(figmaApi, rootNode);
      collected.push({
        id: rootNode.id,
        name: rootNode.name || rootNode.type,
        type: rootNode.type,
        visible: true,
        characters: rootNode.type === "TEXT" ? String(rootNode.characters || "") : undefined,
        fontSize,
        fontWeight: typeof rootNode.fontWeight === "number" ? rootNode.fontWeight : undefined,
        fontStyle,
        lineHeightPx: safeReadLineHeightPx(figmaApi, rootNode, fontSize),
        width: typeof rootNode.width === "number" ? rootNode.width : undefined,
        height: typeof rootNode.height === "number" ? rootNode.height : undefined,
        opacity: typeof rootNode.opacity === "number" ? rootNode.opacity : 1,
        fills,
        effectiveBackground: resolveNodeBackground(figmaApi, engine, rootNode, canvasBg),
      });
    } else {
      walk(rootNode, 1);
    }

    const rootBg = engine.resolveEffectiveBackground(
      [
        {
          visible: rootNode.visible !== false,
          opacity: typeof rootNode.opacity === "number" ? rootNode.opacity : 1,
          fills: safeReadFills(figmaApi, rootNode),
        },
      ],
      canvasBg
    );

    return {
      id: rootNode.id,
      name: rootNode.name || "Untitled Frame",
      width: typeof rootNode.width === "number" ? rootNode.width : 0,
      height: typeof rootNode.height === "number" ? rootNode.height : 0,
      background: rootBg,
      nodes: collected,
    };
  }

  function resolveTargetFrames(figmaApi, scope) {
    const page = figmaApi.currentPage;
    if (!page) return [];
    const selection = Array.isArray(page.selection) ? page.selection : [];

    if (scope === "selection" && selection.length > 0) {
      return selection;
    }

    // Full page scope or empty selection fallback: collect visible top-level frames/sections/components
    const children = Array.isArray(page.children) ? page.children : [];
    const frames = children.filter(
      (n) =>
        n &&
        n.visible !== false &&
        (n.type === "FRAME" ||
          n.type === "SECTION" ||
          n.type === "COMPONENT" ||
          n.type === "COMPONENT_SET" ||
          n.type === "INSTANCE" ||
          n.type === "GROUP")
    );
    return frames.length > 0 ? frames : selection;
  }

  async function findNodeById(figmaApi, nodeId) {
    if (!nodeId) return null;
    if (typeof figmaApi.getNodeByIdAsync === "function") {
      return await figmaApi.getNodeByIdAsync(nodeId);
    }
    if (typeof figmaApi.getNodeById === "function") {
      return figmaApi.getNodeById(nodeId);
    }
    return null;
  }

  async function applyColorFixToNode(figmaApi, engine, nodeId, hex, recommendedOpacity) {
    const node = await findNodeById(figmaApi, nodeId);
    if (!node) {
      return { ok: false, nodeId, error: "Node not found: " + nodeId };
    }
    if (!("fills" in node)) {
      return { ok: false, nodeId, error: "Node does not support fills: " + node.type };
    }

    const rgb = engine.hexToRgb01(hex);
    const existing = safeReadFills(figmaApi, node);
    const cloned = existing.map((fill) => {
      const copy = Object.assign({}, fill);
      if (fill && fill.color) {
        copy.color = { r: fill.color.r, g: fill.color.g, b: fill.color.b };
      }
      return copy;
    });

    let updated = false;
    for (let i = 0; i < cloned.length; i += 1) {
      const f = cloned[i];
      if (f && f.visible !== false && (!f.type || f.type === "SOLID")) {
        f.type = "SOLID";
        f.color = { r: rgb.r, g: rgb.g, b: rgb.b };
        if (typeof recommendedOpacity === "number" && recommendedOpacity > 0) {
          f.opacity = engine.clamp01(recommendedOpacity);
        }
        updated = true;
        break;
      }
    }

    if (!updated) {
      cloned.push({
        type: "SOLID",
        color: { r: rgb.r, g: rgb.g, b: rgb.b },
        opacity: typeof recommendedOpacity === "number" ? engine.clamp01(recommendedOpacity) : 1,
        visible: true,
      });
    }

    // Reassign cloned fills array (Figma freezes fills arrays; assigning registers native Undo)
    node.fills = cloned;
    if (typeof recommendedOpacity === "number" && recommendedOpacity >= 1 && typeof node.opacity === "number" && node.opacity < 1) {
      node.opacity = 1;
    }

    return {
      ok: true,
      nodeId: node.id,
      nodeName: node.name,
      appliedHex: engine.rgb01ToHex(rgb),
    };
  }

  /**
   * Creates a testable, self-contained Figma Plugin controller instance.
   */
  function createController(figmaApi, engine) {
    let lastAudit = null;
    let lastScope = "selection";

    function post(payload) {
      if (figmaApi && figmaApi.ui && typeof figmaApi.ui.postMessage === "function") {
        figmaApi.ui.postMessage(payload);
      }
    }

    function runAudit(scope) {
      const effectiveScope = scope || lastScope || "selection";
      lastScope = effectiveScope;
      const canvasBg = getPageCanvasBackground(figmaApi.currentPage);
      const targets = resolveTargetFrames(figmaApi, effectiveScope);
      const snapshots = targets.map((node) =>
        extractFrameSnapshot(figmaApi, engine, node, canvasBg)
      );

      const result = engine.auditDocumentFrames(snapshots, figmaApi.payments);
      result.scope = effectiveScope;
      result.selectionCount =
        figmaApi.currentPage && Array.isArray(figmaApi.currentPage.selection)
          ? figmaApi.currentPage.selection.length
          : 0;
      lastAudit = result;

      post({
        type: "audit-result",
        payload: result,
      });
      return result;
    }

    async function handleMessage(msg) {
      if (!msg || typeof msg !== "object") return null;

      switch (msg.type) {
        case "init":
        case "run-audit": {
          return runAudit(msg.scope || "selection");
        }

        case "get-entitlement": {
          const entitlement = engine.evaluateEntitlement(figmaApi.payments);
          post({ type: "entitlement", payload: entitlement });
          return entitlement;
        }

        case "apply-color-fix": {
          const outcome = await applyColorFixToNode(
            figmaApi,
            engine,
            msg.nodeId,
            msg.hex,
            msg.recommendedOpacity
          );
          if (outcome.ok && typeof figmaApi.commitUndo === "function") {
            figmaApi.commitUndo();
          }
          if (outcome.ok && typeof figmaApi.notify === "function") {
            figmaApi.notify("DesignGate: Applied " + outcome.appliedHex + " to " + outcome.nodeName);
          }
          const refreshed = runAudit(lastScope);
          post({ type: "fix-applied", payload: outcome });
          return { outcome, audit: refreshed };
        }

        case "apply-all-fixes": {
          const entitlement = engine.evaluateEntitlement(figmaApi.payments);
          if (!entitlement.canAutoFixAll) {
            const blocked = {
              ok: false,
              requiresPro: true,
              reason: "1-Click Auto-Fix All requires DesignGate Pro ($12/mo or $39 one-time via Figma Native Payments).",
            };
            post({ type: "pro-gate", payload: blocked });
            return blocked;
          }

          const fixes = Array.isArray(msg.fixes) ? msg.fixes : [];
          const applied = [];
          for (let i = 0; i < fixes.length; i += 1) {
            const fx = fixes[i];
            const res = await applyColorFixToNode(
              figmaApi,
              engine,
              fx.nodeId,
              fx.hex,
              fx.recommendedOpacity
            );
            applied.push(res);
          }
          if (typeof figmaApi.commitUndo === "function") {
            figmaApi.commitUndo();
          }
          const successCount = applied.filter((r) => r.ok).length;
          if (typeof figmaApi.notify === "function") {
            figmaApi.notify("DesignGate Pro: Auto-fixed " + successCount + " contrast issues.");
          }
          const refreshed = runAudit(lastScope);
          const summaryRes = { ok: true, appliedCount: successCount, results: applied, audit: refreshed };
          post({ type: "batch-fix-applied", payload: { appliedCount: successCount } });
          return summaryRes;
        }

        case "focus-node": {
          const node = await findNodeById(figmaApi, msg.nodeId);
          if (!node) {
            return { ok: false, error: "Node not found" };
          }
          if (figmaApi.currentPage) {
            figmaApi.currentPage.selection = [node];
          }
          if (figmaApi.viewport && typeof figmaApi.viewport.scrollAndZoomIntoView === "function") {
            figmaApi.viewport.scrollAndZoomIntoView([node]);
          }
          return { ok: true, nodeId: node.id };
        }

        case "export-report": {
          const entitlement = engine.evaluateEntitlement(figmaApi.payments);
          if (!entitlement.canExportCertificate) {
            const blocked = {
              ok: false,
              requiresPro: true,
              reason: "Dev-Handoff Accessibility Certificate export (Markdown/CSV) requires DesignGate Pro.",
            };
            post({ type: "pro-gate", payload: blocked });
            return blocked;
          }
          const audit = lastAudit || runAudit(lastScope);
          const format = msg.format === "csv" ? "csv" : "markdown";
          const content =
            format === "csv"
              ? engine.exportCsvReport(audit)
              : engine.exportMarkdownReport(audit);
          const payload = { ok: true, format, content };
          post({ type: "export-ready", payload });
          return payload;
        }

        case "initiate-checkout": {
          if (
            figmaApi.payments &&
            typeof figmaApi.payments.initiateCheckoutAsync === "function"
          ) {
            try {
              const checkoutRes = await figmaApi.payments.initiateCheckoutAsync({
                interstitial: "TRIAL_ENDED",
              });
              const entitlement = engine.evaluateEntitlement(figmaApi.payments);
              post({
                type: "checkout-complete",
                payload: { checkoutRes, entitlement },
              });
              runAudit(lastScope);
              return { ok: true, checkoutRes, entitlement };
            } catch (err) {
              const failure = {
                ok: false,
                error: err && err.message ? err.message : String(err),
              };
              post({ type: "checkout-error", payload: failure });
              return failure;
            }
          }
          const unavailable = {
            ok: false,
            error:
              "Figma Native Payments API is active only on published Community plugins. See FIGMA_COMMUNITY_PUBLISH_GUIDE.md to enable built-in payments.",
          };
          post({ type: "checkout-error", payload: unavailable });
          return unavailable;
        }

        case "close-plugin": {
          if (typeof figmaApi.closePlugin === "function") {
            figmaApi.closePlugin();
          }
          return { ok: true };
        }

        default:
          return null;
      }
    }

    function boot() {
      if (typeof figmaApi.showUI === "function" && typeof __html__ !== "undefined") {
        figmaApi.showUI(__html__, {
          width: 360,
          height: 580,
          themeColors: true,
          title: "DesignGate — WCAG 2.2 & Dark-Pattern Linter",
        });
      }

      if (figmaApi.ui) {
        figmaApi.ui.onmessage = (msg) => {
          handleMessage(msg);
        };
      }

      if (typeof figmaApi.on === "function") {
        figmaApi.on("selectionchange", () => {
          if (lastScope === "selection") {
            runAudit("selection");
          }
        });
      }

      runAudit("selection");
    }

    return {
      boot,
      runAudit,
      handleMessage,
      extractFrameSnapshot: (rootNode) =>
        extractFrameSnapshot(figmaApi, engine, rootNode, getPageCanvasBackground(figmaApi.currentPage)),
    };
  }

  return {
    createController,
    extractFrameSnapshot,
    resolveNodeBackground,
    applyColorFixToNode,
  };
});
