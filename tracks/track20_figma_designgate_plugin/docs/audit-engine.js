/**
 * DesignGate Core Audit Engine — Pure Zero-Dependency JavaScript
 *
 * Shared single-source-of-truth engine used by:
 *   1. Figma Plugin Sandbox (bundled standalone into `code.js`)
 *   2. Standalone Browser Simulator (`docs/index.html` via `docs/audit-engine.js`)
 *   3. Node.js Unit & Integration Tests (`test/designgate.test.mjs`)
 *
 * Implements:
 *   - WCAG 2.2 AA / AAA relative luminance & contrast ratio (IEC 61966-2-1 0.04045)
 *   - APCA (SAPC-4G / 0.0.98G-4g) perceptual Lightness Contrast (Lc)
 *   - Porter-Duff source-over alpha compositing across inherited ancestor fills
 *   - Nearest Accessible Hex Auto-Fix Solver (binary search in HSL lightness with 8-bit quantization verification)
 *   - Touch Target (WCAG 2.2 SC 2.5.8 24x24px AA & Apple HIG/Material 44x44px) & Typography Ergonomics Linter
 *   - EN & JP Checkout Dark-Pattern & Japan Tokushoho Art. 12-6 (特定商取引法12条の6) Legal Clarity Linter
 *   - Color-Blindness Simulation Matrix (Protanopia / Deuteranopia / Tritanopia — Viénot 1999)
 *   - Figma Community Native Payments (`figma.payments`) Freemium Entitlement Gate
 *   - Markdown & RFC-4180 CSV Dev-Handoff Accessibility Certificate Exporters
 */

(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  if (root && typeof root === "object") {
    root.DesignGateEngine = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const ENGINE_VERSION = "1.0.0";

  const PRICING = Object.freeze({
    proMonthlyUsd: 12,
    proOneTimeUsd: 39,
    currency: "USD",
    paymentRail: "Figma Community Native Payments (figma.payments)",
    freeFrameLimit: 1,
  });

  // =========================================================================
  // 1. Color Utilities, Alpha Compositing, WCAG 2.2 & APCA Math
  // =========================================================================

  function clamp01(v) {
    if (typeof v !== "number" || Number.isNaN(v)) return 0;
    if (v <= 0) return 0;
    if (v >= 1) return 1;
    return v;
  }

  function quantizeChannel(c) {
    return Math.round(clamp01(c) * 255) / 255;
  }

  function quantizeRgb01(color) {
    const c = normalizeColor(color);
    return {
      r: quantizeChannel(c.r),
      g: quantizeChannel(c.g),
      b: quantizeChannel(c.b),
      a: clamp01(c.a),
    };
  }

  function hexToRgb01(hex) {
    if (typeof hex !== "string") {
      throw new TypeError("Expected hex color string");
    }
    const cleaned = hex.trim().replace(/^#/, "");
    if (/^[0-9a-fA-F]{3}$/.test(cleaned)) {
      return {
        r: parseInt(cleaned[0] + cleaned[0], 16) / 255,
        g: parseInt(cleaned[1] + cleaned[1], 16) / 255,
        b: parseInt(cleaned[2] + cleaned[2], 16) / 255,
        a: 1,
      };
    }
    if (/^[0-9a-fA-F]{6}$/.test(cleaned)) {
      return {
        r: parseInt(cleaned.slice(0, 2), 16) / 255,
        g: parseInt(cleaned.slice(2, 4), 16) / 255,
        b: parseInt(cleaned.slice(4, 6), 16) / 255,
        a: 1,
      };
    }
    if (/^[0-9a-fA-F]{8}$/.test(cleaned)) {
      return {
        r: parseInt(cleaned.slice(0, 2), 16) / 255,
        g: parseInt(cleaned.slice(2, 4), 16) / 255,
        b: parseInt(cleaned.slice(4, 6), 16) / 255,
        a: parseInt(cleaned.slice(6, 8), 16) / 255,
      };
    }
    throw new Error("Invalid hex color: " + hex);
  }

  function parseRgbaString(str) {
    const match = str
      .trim()
      .match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)$/i);
    if (!match) return null;
    return {
      r: clamp01(parseFloat(match[1]) / 255),
      g: clamp01(parseFloat(match[2]) / 255),
      b: clamp01(parseFloat(match[3]) / 255),
      a: match[4] !== undefined ? clamp01(parseFloat(match[4])) : 1,
    };
  }

  function normalizeColor(input) {
    if (!input) {
      return { r: 0, g: 0, b: 0, a: 1 };
    }
    if (typeof input === "string") {
      const rgba = parseRgbaString(input);
      if (rgba) return rgba;
      return hexToRgb01(input);
    }
    if (typeof input === "object" && typeof input.r === "number") {
      return {
        r: clamp01(input.r),
        g: clamp01(input.g),
        b: clamp01(input.b),
        a: input.a !== undefined ? clamp01(input.a) : 1,
      };
    }
    throw new TypeError("Unsupported color format");
  }

  function rgb01ToHex(color) {
    const c = normalizeColor(color);
    const toByte = (v) =>
      Math.round(clamp01(v) * 255)
        .toString(16)
        .padStart(2, "0")
        .toUpperCase();
    return "#" + toByte(c.r) + toByte(c.g) + toByte(c.b);
  }

  /**
   * Porter-Duff source-over alpha compositing of foreground over background.
   */
  function compositeOver(fgInput, bgInput) {
    const fg = normalizeColor(fgInput);
    const bg = normalizeColor(bgInput);
    const fgA = clamp01(fg.a);
    const bgA = clamp01(bg.a);
    const outA = fgA + bgA * (1 - fgA);
    if (outA <= 1e-6) {
      return { r: 1, g: 1, b: 1, a: 0 };
    }
    return {
      r: clamp01((fg.r * fgA + bg.r * bgA * (1 - fgA)) / outA),
      g: clamp01((fg.g * fgA + bg.g * bgA * (1 - fgA)) / outA),
      b: clamp01((fg.b * fgA + bg.b * bgA * (1 - fgA)) / outA),
      a: clamp01(outA),
    };
  }

  /**
   * Resolves effective opaque background by compositing visible SOLID fills
   * from root canvas down through ancestor containers.
   * Each layer can be `{ fills: [...], opacity?: number }` or a direct color.
   */
  function resolveEffectiveBackground(layers, canvasBg) {
    let current = normalizeColor(canvasBg || { r: 1, g: 1, b: 1, a: 1 });
    current.a = 1;
    if (!Array.isArray(layers)) return current;

    for (let i = 0; i < layers.length; i += 1) {
      const layer = layers[i];
      if (!layer) continue;
      if (typeof layer === "string" || typeof layer.r === "number") {
        current = compositeOver(layer, current);
        continue;
      }
      if (layer.visible === false) continue;
      const nodeOpacity = layer.opacity !== undefined ? clamp01(layer.opacity) : 1;
      const fills = Array.isArray(layer.fills) ? layer.fills : [];
      for (let f = 0; f < fills.length; f += 1) {
        const fill = fills[f];
        if (!fill || fill.visible === false) continue;
        if (fill.type && fill.type !== "SOLID") continue;
        if (!fill.color) continue;
        const fillOpacity = fill.opacity !== undefined ? clamp01(fill.opacity) : 1;
        const effectiveAlpha = fillOpacity * nodeOpacity;
        if (effectiveAlpha <= 0) continue;
        current = compositeOver(
          {
            r: fill.color.r,
            g: fill.color.g,
            b: fill.color.b,
            a: effectiveAlpha,
          },
          current
        );
      }
    }
    return current;
  }

  /**
   * IEC 61966-2-1 / WCAG 2.1+ sRGB linearization.
   */
  function srgbToLinear(c) {
    const v = clamp01(c);
    return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  }

  function linearToSrgb(c) {
    const v = clamp01(c);
    return v <= 0.0031308 ? v * 12.92 : 1.055 * Math.pow(v, 1 / 2.4) - 0.055;
  }

  /**
   * WCAG 2.2 Relative Luminance L in [0, 1].
   */
  function relativeLuminance(color) {
    const c = normalizeColor(color);
    const R = srgbToLinear(c.r);
    const G = srgbToLinear(c.g);
    const B = srgbToLinear(c.b);
    return 0.2126 * R + 0.7152 * G + 0.0722 * B;
  }

  /**
   * Exact WCAG 2.2 contrast ratio in [1, 21].
   * If fg has alpha < 1, composites fg over bg first.
   */
  function contrastRatio(fgInput, bgInput) {
    const bg = normalizeColor(bgInput);
    const rawFg = normalizeColor(fgInput);
    const effectiveFg = rawFg.a < 1 ? compositeOver(rawFg, bg) : rawFg;
    const L1 = relativeLuminance(effectiveFg);
    const L2 = relativeLuminance(bg);
    const lighter = Math.max(L1, L2);
    const darker = Math.min(L1, L2);
    return (lighter + 0.05) / (darker + 0.05);
  }

  /**
   * APCA (SAPC-4G / 0.0.98G-4g) Perceptual Lightness Contrast (Lc).
   * Positive Lc = dark text on light background; negative Lc = light text on dark background.
   */
  function apcaContrast(fgInput, bgInput) {
    const bg = normalizeColor(bgInput);
    const rawFg = normalizeColor(fgInput);
    const fg = rawFg.a < 1 ? compositeOver(rawFg, bg) : rawFg;

    const toY = (c) => {
      const y =
        0.2126729 * Math.pow(clamp01(c.r), 2.4) +
        0.7151522 * Math.pow(clamp01(c.g), 2.4) +
        0.072175 * Math.pow(clamp01(c.b), 2.4);
      return y >= 0.022 ? y : y + Math.pow(0.022 - y, 1.414);
    };

    const Ytxt = toY(fg);
    const Ybg = toY(bg);
    if (Math.abs(Ybg - Ytxt) < 0.0005) return 0;

    let sapc = 0;
    let output = 0;
    if (Ybg > Ytxt) {
      sapc = (Math.pow(Ybg, 0.56) - Math.pow(Ytxt, 0.57)) * 1.14;
      output = sapc < 0.1 ? 0 : (sapc - 0.027) * 100;
    } else {
      sapc = (Math.pow(Ybg, 0.65) - Math.pow(Ytxt, 0.62)) * 1.14;
      output = sapc > -0.1 ? 0 : (sapc + 0.027) * 100;
    }
    return Math.round(output * 10) / 10;
  }

  function rgb01ToHsl(color) {
    const c = normalizeColor(color);
    const r = c.r;
    const g = c.g;
    const b = c.b;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const l = (max + min) / 2;
    let h = 0;
    let s = 0;
    if (max !== min) {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      switch (max) {
        case r:
          h = (g - b) / d + (g < b ? 6 : 0);
          break;
        case g:
          h = (b - r) / d + 2;
          break;
        default:
          h = (r - g) / d + 4;
          break;
      }
      h /= 6;
    }
    return { h, s, l };
  }

  function hslToRgb01(h, s, l) {
    const H = ((h % 1) + 1) % 1;
    const S = clamp01(s);
    const L = clamp01(l);
    if (S === 0) {
      return { r: L, g: L, b: L, a: 1 };
    }
    const hue2rgb = (p, q, t) => {
      let tt = t;
      if (tt < 0) tt += 1;
      if (tt > 1) tt -= 1;
      if (tt < 1 / 6) return p + (q - p) * 6 * tt;
      if (tt < 1 / 2) return q;
      if (tt < 2 / 3) return p + (q - p) * (2 / 3 - tt) * 6;
      return p;
    };
    const q = L < 0.5 ? L * (1 + S) : L + S - L * S;
    const p = 2 * L - q;
    return {
      r: clamp01(hue2rgb(p, q, H + 1 / 3)),
      g: clamp01(hue2rgb(p, q, H)),
      b: clamp01(hue2rgb(p, q, H - 1 / 3)),
      a: 1,
    };
  }

  function perceptualRgbDistance(a, b) {
    const ca = normalizeColor(a);
    const cb = normalizeColor(b);
    const rMean = (ca.r + cb.r) / 2;
    const dr = ca.r - cb.r;
    const dg = ca.g - cb.g;
    const db = ca.b - cb.b;
    return Math.sqrt((2 + rMean) * dr * dr + 4 * dg * dg + (3 - rMean) * db * db);
  }

  /**
   * Nearest Accessible Hex Auto-Fix Solver.
   * Binary-searches HSL lightness preserving brand hue & saturation in both darker and lighter
   * directions, verifying 8-bit quantized hex compliance strictly >= targetRatio.
   */
  function solveAccessibleColor(fgInput, bgInput, targetRatio, fgAlphaOverride) {
    const rawFg = normalizeColor(fgInput);
    const bg = normalizeColor(bgInput);
    bg.a = 1;
    const alpha =
      fgAlphaOverride !== undefined ? clamp01(fgAlphaOverride) : clamp01(rawFg.a);
    const target = typeof targetRatio === "number" && targetRatio > 1 ? targetRatio : 4.5;

    const baseQuantized = quantizeRgb01({ r: rawFg.r, g: rawFg.g, b: rawFg.b, a: alpha });
    const currentRatio = contrastRatio(baseQuantized, bg);

    if (currentRatio >= target) {
      return {
        hex: rgb01ToHex(baseQuantized),
        rgb01: { r: baseQuantized.r, g: baseQuantized.g, b: baseQuantized.b },
        originalHex: rgb01ToHex(baseQuantized),
        ratio: round2(currentRatio),
        apcaLc: apcaContrast(baseQuantized, bg),
        targetRatio: target,
        passed: true,
        direction: "unchanged",
        recommendedOpacity: alpha,
        requiresHigherOpacity: false,
      };
    }

    function solveWithAlpha(testAlpha) {
      const hsl = rgb01ToHsl(baseQuantized);
      const candidates = [];

      const evalAtL = (l) => {
        const rgb = quantizeRgb01(hslToRgb01(hsl.h, hsl.s, l));
        rgb.a = testAlpha;
        return {
          rgb,
          ratio: contrastRatio(rgb, bg),
        };
      };

      // Darker branch: [0, hsl.l] — want HIGHEST lightness that still passes
      const darkest = evalAtL(0);
      if (darkest.ratio >= target) {
        let lo = 0;
        let hi = hsl.l;
        let best = darkest;
        for (let iter = 0; iter < 28; iter += 1) {
          const mid = (lo + hi) / 2;
          const res = evalAtL(mid);
          if (res.ratio >= target) {
            best = res;
            lo = mid;
          } else {
            hi = mid;
          }
        }
        candidates.push({
          rgb: best.rgb,
          ratio: best.ratio,
          direction: "darker",
          dist: perceptualRgbDistance(baseQuantized, best.rgb),
        });
      }

      // Lighter branch: [hsl.l, 1] — want LOWEST lightness that still passes
      const lightest = evalAtL(1);
      if (lightest.ratio >= target) {
        let lo = hsl.l;
        let hi = 1;
        let best = lightest;
        for (let iter = 0; iter < 28; iter += 1) {
          const mid = (lo + hi) / 2;
          const res = evalAtL(mid);
          if (res.ratio >= target) {
            best = res;
            hi = mid;
          } else {
            lo = mid;
          }
        }
        candidates.push({
          rgb: best.rgb,
          ratio: best.ratio,
          direction: "lighter",
          dist: perceptualRgbDistance(baseQuantized, best.rgb),
        });
      }

      // Fallback pure black/white check if saturated endpoints missed due to rounding
      if (candidates.length === 0) {
        const black = { r: 0, g: 0, b: 0, a: testAlpha };
        const white = { r: 1, g: 1, b: 1, a: testAlpha };
        const rBlack = contrastRatio(black, bg);
        const rWhite = contrastRatio(white, bg);
        if (rBlack >= target) {
          candidates.push({
            rgb: black,
            ratio: rBlack,
            direction: "darker",
            dist: perceptualRgbDistance(baseQuantized, black),
          });
        }
        if (rWhite >= target) {
          candidates.push({
            rgb: white,
            ratio: rWhite,
            direction: "lighter",
            dist: perceptualRgbDistance(baseQuantized, white),
          });
        }
      }

      if (candidates.length === 0) return null;
      candidates.sort((a, b) => a.dist - b.dist);
      return candidates[0];
    }

    let chosen = solveWithAlpha(alpha);
    let recommendedOpacity = alpha;
    let requiresHigherOpacity = false;

    if (!chosen && alpha < 1) {
      chosen = solveWithAlpha(1);
      recommendedOpacity = 1;
      requiresHigherOpacity = true;
    }

    if (!chosen) {
      // Mid-gray background cannot physically reach 7:1 AAA with either black or white;
      // pick whichever of #000000 or #FFFFFF gives strictly higher contrast.
      const black = { r: 0, g: 0, b: 0, a: 1 };
      const white = { r: 1, g: 1, b: 1, a: 1 };
      const rBlack = contrastRatio(black, bg);
      const rWhite = contrastRatio(white, bg);
      const bestExtreme = rBlack >= rWhite ? { rgb: black, ratio: rBlack, direction: "darker" } : { rgb: white, ratio: rWhite, direction: "lighter" };
      return {
        hex: rgb01ToHex(bestExtreme.rgb),
        rgb01: { r: bestExtreme.rgb.r, g: bestExtreme.rgb.g, b: bestExtreme.rgb.b },
        originalHex: rgb01ToHex(baseQuantized),
        ratio: round2(bestExtreme.ratio),
        apcaLc: apcaContrast(bestExtreme.rgb, bg),
        targetRatio: target,
        passed: bestExtreme.ratio >= target,
        direction: bestExtreme.direction,
        recommendedOpacity: 1,
        requiresHigherOpacity: alpha < 1,
      };
    }

    return {
      hex: rgb01ToHex(chosen.rgb),
      rgb01: { r: chosen.rgb.r, g: chosen.rgb.g, b: chosen.rgb.b },
      originalHex: rgb01ToHex(baseQuantized),
      ratio: round2(chosen.ratio),
      apcaLc: apcaContrast(chosen.rgb, bg),
      targetRatio: target,
      passed: chosen.ratio >= target,
      direction: chosen.direction,
      recommendedOpacity,
      requiresHigherOpacity,
    };
  }

  function isLargeText(fontSize, fontWeight, fontStyle) {
    const size = typeof fontSize === "number" ? fontSize : 14;
    if (size >= 24) return true;
    const boldByWeight = typeof fontWeight === "number" && fontWeight >= 700;
    const boldByStyle =
      typeof fontStyle === "string" && /\b(bold|heavy|black|extrabold|ultrabold)\b/i.test(fontStyle);
    return size >= 18.66 && (boldByWeight || boldByStyle);
  }

  function round2(n) {
    return Math.round(n * 100) / 100;
  }

  // =========================================================================
  // 2. Color-Blindness Simulation (Viénot 1999 Linear sRGB Matrices)
  // =========================================================================

  const CVD_MATRICES = Object.freeze({
    protanopia: [
      [0.152286, 1.052583, -0.204868],
      [0.114503, 0.786281, 0.099216],
      [-0.003882, -0.048116, 1.051998],
    ],
    deuteranopia: [
      [0.367322, 0.860646, -0.227968],
      [0.280085, 0.672501, 0.047413],
      [-0.01182, 0.04294, 0.968881],
    ],
    tritanopia: [
      [1.255528, -0.076749, -0.178779],
      [-0.078411, 0.930809, 0.147602],
      [0.004733, 0.691367, 0.3039],
    ],
  });

  function simulateColorBlindness(colorInput, type) {
    const mat = CVD_MATRICES[type];
    if (!mat) {
      throw new Error("Unsupported CVD type: " + type);
    }
    const c = normalizeColor(colorInput);
    const R = srgbToLinear(c.r);
    const G = srgbToLinear(c.g);
    const B = srgbToLinear(c.b);

    const simR = linearToSrgb(clamp01(mat[0][0] * R + mat[0][1] * G + mat[0][2] * B));
    const simG = linearToSrgb(clamp01(mat[1][0] * R + mat[1][1] * G + mat[1][2] * B));
    const simB = linearToSrgb(clamp01(mat[2][0] * R + mat[2][1] * G + mat[2][2] * B));

    const out = quantizeRgb01({ r: simR, g: simG, b: simB, a: c.a });
    return {
      r: out.r,
      g: out.g,
      b: out.b,
      a: out.a,
      hex: rgb01ToHex(out),
    };
  }

  function evaluateColorBlindnessContrast(fgInput, bgInput) {
    const bg = normalizeColor(bgInput);
    const rawFg = normalizeColor(fgInput);
    const effectiveFg = rawFg.a < 1 ? compositeOver(rawFg, bg) : rawFg;
    const results = {};
    const types = ["protanopia", "deuteranopia", "tritanopia"];
    for (let i = 0; i < types.length; i += 1) {
      const t = types[i];
      const simFg = simulateColorBlindness(effectiveFg, t);
      const simBg = simulateColorBlindness(bg, t);
      results[t] = {
        fgHex: simFg.hex,
        bgHex: simBg.hex,
        ratio: round2(contrastRatio(simFg, simBg)),
      };
    }
    return results;
  }

  // =========================================================================
  // 3. EN & JP Dark-Pattern & Tokushoho Art. 12-6 Rule Definitions
  // =========================================================================

  const DARK_PATTERN_RULES = [
    {
      id: "DP_CONFIRMSHAMING",
      category: "darkPatterns",
      severity: "error",
      title: "Confirmshaming / Guilt-Tripping Opt-Out",
      titleJa: "コンファームシェイミング（罪悪感を煽る拒否文言）",
      regulation: "EU DSA Art. 25 / FTC Dark Patterns",
      patterns: [
        /no\s+thanks?,?\s*i\s*(hate|don['’]t\s*want|prefer\s*paying|like\s*wasting|want\s*to\s*miss|don['’]t\s*care)/i,
        /i['’]?ll\s*(stay\s*broke|keep\s*overpaying|skip\s*saving|pay\s*full\s*price)/i,
        /i\s*prefer\s*paying\s*full\s*price/i,
        /いいえ[、,\s]*(損しても|損したまま|割引を諦め|お得.*拒否|高いまま)/,
        /損を承知で(スキップ|閉じる|拒否)/,
      ],
      recommendation:
        "Use neutral decline copy such as 'No thanks' / 'Continue without offer' or '今は申し込まない'.",
    },
    {
      id: "DP_FAKE_URGENCY",
      category: "darkPatterns",
      severity: "warning",
      title: "Manufactured Urgency / Countdown Pressure",
      titleJa: "偽の緊急性・カウントダウン圧力",
      regulation: "FTC Act Sec. 5 / UK DMCC / 景品表示法",
      patterns: [
        /(offer|deal|discount|price)\s*(expires|ends|doubles)\s*in\s*\d{1,2}:\d{2}/i,
        /hurry!?\s*only\s*\d+\s*(left|remaining|spots?)/i,
        /\d+\s*people\s*(are\s*)?(viewing|looking|buying)\s*(this\s*)?(right\s*now|now)/i,
        /act\s*now\s*or\s*lose\s*(forever|this\s*offer)/i,
        /あと\s*\d+\s*分\s*(\d+\s*秒)?\s*で(終了|失効|値上げ)/,
        /残りわずか[！!]?\s*(今すぐ|急いで|あと\d+)/,
        /本日限定[・\s]*二度と(手に入らない|ない価格)/,
      ],
      recommendation:
        "Remove artificial countdowns or substantiate real inventory/deadline dates plainly.",
    },
    {
      id: "DP_ROACH_MOTEL_CANCEL",
      category: "darkPatterns",
      severity: "error",
      title: "Asymmetric Cancellation / Phone-Only Cancel Trap",
      titleJa: "解約妨害（電話限定・書面限定キャンセル）",
      regulation: "FTC Click-to-Cancel / EU CRD / 特定商取引法12条の6",
      patterns: [
        /call\s*(us|support|customer\s*service)?\s*to\s*cancel/i,
        /cancel(lation)?\s*(is\s*)?(by\s*)?phone\s*only/i,
        /written\s*notice\s*(\d+\s*days?)?\s*to\s*cancel/i,
        /cancel\s*by\s*(postal\s*)?mail/i,
        /解約は(お)?電話のみ/,
        /電話でのみ(解約|キャンセル|退会)/,
        /(解約|退会)は.*窓口まで(お)?電話/,
        /(書面|郵送|FAX)にて(解約|退会)/,
        /平日\s*\d{1,2}時.*電話.*(解約|キャンセル)/,
      ],
      recommendation:
        "Provide online self-serve cancellation with the same friction as signup (1-click cancel in account settings).",
    },
    {
      id: "DP_HIDDEN_AUTORENEWAL",
      category: "darkPatterns",
      severity: "warning",
      title: "Auto-Renewal / Recurring Billing Clarity Risk",
      titleJa: "自動更新・定期課金の不明瞭な表示リスク",
      regulation: "FTC Negative Option / 特定商取引法12条の6",
      patterns: [
        /(auto(matically)?[- ]?renew|renews?\s*automatically)/i,
        /after\s*(your\s*)?\d+[- ]?day\s*free\s*trial.*(charged|billed)/i,
        /subsequently\s*(billed|charged)/i,
        /無料(期間|トライアル)終了後.*(自動|課金|請求|移行)/,
        /2回目以降.*(自動|円|請求|定期)/,
        /自動で(更新|課金|月額|年額)/,
        /解約しない限り自動更新/,
      ],
      recommendation:
        "Display recurring price, billing frequency, trial end date, and cancel method at >= 14px with >= 4.5:1 contrast near the CTA.",
    },
    {
      id: "DP_PRECHECKED_ADDON",
      category: "darkPatterns",
      severity: "error",
      title: "Pre-Checked Paid Add-On / Sneaky Opt-In",
      titleJa: "事前チェック済み有料オプション（スニーク・イン）",
      regulation: "EU Consumer Rights Directive Art. 22 / 特定商取引法",
      patterns: [
        /(protection\s*plan|extended\s*warranty|travel\s*insurance|priority\s*support|vip\s*shield).*\+\s*[\$¥€£]?\d/i,
        /(安心保証パック|延長保証|有料サポート|プレミアム補償|お急ぎ便パック).*[+＋¥￥]\s*\d/,
        /automatically\s*added\s*to\s*your\s*(order|cart)/i,
      ],
      recommendation:
        "Paid add-ons and optional subscriptions must default to UNCHECKED and require explicit affirmative opt-in.",
    },
  ];

  const INTERACTIVE_NAME_RE =
    /(^|[\s_\-/])(btn|button|cta|input|field|textfield|select|dropdown|checkbox|radio|switch|toggle|link|tab|icon[-_ ]?btn|close|dismiss|chip|action|submit|buy|purchase|checkout|subscribe|cancel|skip|解約|購入|申込|ボタン|閉じる|スキップ)($|[\s_\-/0-9])/i;

  const STATUS_NAME_RE =
    /(status|badge|pill|tag|dot|indicator|chip|alert|state|success|error|warning|danger|info|active|inactive|paid|failed|overdue|ステータス|バッジ|警告|エラー|成功)/i;

  const JP_CHAR_RE = /[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]/;

  const JP_CHECKOUT_TRIGGER_RE =
    /(購入|注文を確定|ご注文内容|最終確認|お申し込み|申し込む|定期購入|定期コース|決済|お支払い|カートを確認)/;

  const EN_CHECKOUT_TRIGGER_RE =
    /(checkout|complete\s*(your\s*)?order|place\s*order|start\s*(your\s*)?(free\s*)?trial|subscribe\s*now|upgrade\s*to\s*pro|pay\s*now|pricing\s*plan|billing\s*summary|confirm\s*subscription)/i;

  const JP_TOKUSHOHO_ITEMS = [
    {
      key: "quantity_or_plan",
      label: "分量・プラン (Quantity / Plan)",
      regex: /(数量|個数|\d+\s*(個|点|箱|袋|本|回)|月額|年額|プラン|コース|定期)/,
    },
    {
      key: "total_price",
      label: "支払総額 (Total Amount incl. Tax)",
      regex: /(支払総額|お支払い合計|合計金額|総額|合計\s*[:：]?\s*[¥￥]?\d|税込)/,
    },
    {
      key: "payment_timing_method",
      label: "支払時期・方法 (Payment Method & Timing)",
      regex: /(支払方法|お支払い方法|決済方法|クレジットカード|銀行振込|請求日|支払時期|引き落とし|決済タイミング)/,
    },
    {
      key: "delivery_timing",
      label: "引渡・提供時期 (Delivery / Fulfillment Timing)",
      regex: /(引渡時期|お届け予定|発送予定|配送予定|営業日以内|提供時期|即時利用|決済完了後すぐ)/,
    },
    {
      key: "cancel_withdrawal",
      label: "申込期間・解約/撤回条件 (Cancellation & Withdrawal Terms)",
      regex: /(解約条件|解約方法|いつでも解約|キャンセル条件|申込の撤回|返品特約|申込期間|退会方法|次回発送の\d+日前)/,
    },
  ];

  // =========================================================================
  // 4. Main Tree / Frame Audit Pipeline
  // =========================================================================

  function extractFirstSolidFill(node) {
    if (node.textColor) {
      const c = normalizeColor(node.textColor);
      const nodeOpacity = node.opacity !== undefined ? clamp01(node.opacity) : 1;
      return {
        color: { r: c.r, g: c.g, b: c.b, a: clamp01(c.a * nodeOpacity) },
        fillOpacity: c.a,
        nodeOpacity,
        fillIndex: 0,
      };
    }
    const fills = Array.isArray(node.fills) ? node.fills : [];
    const nodeOpacity = node.opacity !== undefined ? clamp01(node.opacity) : 1;
    for (let i = 0; i < fills.length; i += 1) {
      const fill = fills[i];
      if (!fill || fill.visible === false) continue;
      if (fill.type && fill.type !== "SOLID") continue;
      if (!fill.color) continue;
      const fillOpacity = fill.opacity !== undefined ? clamp01(fill.opacity) : 1;
      return {
        color: {
          r: clamp01(fill.color.r),
          g: clamp01(fill.color.g),
          b: clamp01(fill.color.b),
          a: clamp01(fillOpacity * nodeOpacity),
        },
        fillOpacity,
        nodeOpacity,
        fillIndex: i,
      };
    }
    return null;
  }

  function inferHeadingLevel(node) {
    if (!node || node.type !== "TEXT") return null;
    if (typeof node.headingLevel === "number" && node.headingLevel >= 1 && node.headingLevel <= 6) {
      return node.headingLevel;
    }
    const name = String(node.name || "");
    const m = name.match(/\bH([1-6])\b/i);
    if (m) return parseInt(m[1], 10);
    return null;
  }

  function isInteractiveCandidate(node) {
    if (!node || node.visible === false) return false;
    if (node.isInteractive === true) return true;
    const role = String(node.role || "").toUpperCase();
    if (
      ["BUTTON", "CTA", "INPUT", "LINK", "TAB", "ICON_BUTTON", "CHECKBOX", "SWITCH", "TOGGLE"].includes(
        role
      )
    ) {
      return true;
    }
    // Avoid flagging full-screen frames/sections as tiny touch targets
    const w = typeof node.width === "number" ? node.width : 0;
    const h = typeof node.height === "number" ? node.height : 0;
    if (w > 560 || h > 160) return false;
    if (INTERACTIVE_NAME_RE.test(String(node.name || ""))) {
      return true;
    }
    return false;
  }

  function isStatusIndicator(node) {
    if (!node || node.visible === false) return false;
    if (node.isStatusBadge === true) return true;
    const w = typeof node.width === "number" ? node.width : 0;
    const h = typeof node.height === "number" ? node.height : 0;
    if (w > 260 || h > 80) return false;
    return STATUS_NAME_RE.test(String(node.name || ""));
  }

  /**
   * Audits a normalized Frame Snapshot (used identically by Figma controller and Browser Simulator).
   *
   * FrameSnapshot shape:
   * {
   *   id: string,
   *   name: string,
   *   width?: number,
   *   height?: number,
   *   background?: color | hex,
   *   nodes: Array<{
   *     id: string,
   *     name: string,
   *     type: "TEXT" | "FRAME" | "RECTANGLE" | "COMPONENT" | "INSTANCE" | "VECTOR" | "ELLIPSE" | "GROUP",
   *     visible?: boolean,
   *     characters?: string,
   *     fontSize?: number,
   *     fontWeight?: number,
   *     fontStyle?: string,
   *     lineHeightPx?: number,
   *     width?: number,
   *     height?: number,
   *     opacity?: number,
   *     fills?: Array<{ type: "SOLID", color: {r,g,b}, opacity?: number, visible?: boolean }>,
   *     textColor?: hex | rgb01,
   *     effectiveBackground?: hex | rgb01,
   *     ancestorLayers?: Array<...>,
   *     isInteractive?: boolean,
   *     role?: string,
   *     checked?: boolean,
   *     headingLevel?: number,
   *     isStatusBadge?: boolean,
   *     ctaKind?: "primary" | "decline"
   *   }>
   * }
   */
  function auditFrame(frame, options) {
    const opts = options || {};
    const canvasBg = normalizeColor(frame.background || opts.canvasBg || "#FFFFFF");
    canvasBg.a = 1;

    const findings = [];
    const nodes = Array.isArray(frame.nodes) ? frame.nodes : [];
    const headings = [];
    const statusNodes = [];
    const primaryCtas = [];
    const declineCtas = [];
    const allTexts = [];

    let contrastCheckedCount = 0;
    let contrastPassCount = 0;

    for (let i = 0; i < nodes.length; i += 1) {
      const node = nodes[i];
      if (!node || node.visible === false) continue;

      const effectiveBg = node.effectiveBackground
        ? normalizeColor(node.effectiveBackground)
        : resolveEffectiveBackground(node.ancestorLayers || [], canvasBg);
      effectiveBg.a = 1;

      const text = typeof node.characters === "string" ? node.characters.trim() : "";
      if (text) {
        allTexts.push(text);
      }

      // ---- A. Contrast & APCA & Auto-Fix + CVD Check ----
      const solid = extractFirstSolidFill(node);
      let nodeContrastRatio = null;

      if (solid && (node.type === "TEXT" || isInteractiveCandidate(node) || isStatusIndicator(node))) {
        const isText = node.type === "TEXT";
        const large = isText ? isLargeText(node.fontSize, node.fontWeight, node.fontStyle) : false;
        const requiredAA = isText ? (large ? 3.0 : 4.5) : 3.0;
        const requiredAAA = isText ? (large ? 4.5 : 7.0) : 4.5;

        const fgColor = solid.color;
        const ratio = contrastRatio(fgColor, effectiveBg);
        const apcaLc = apcaContrast(fgColor, effectiveBg);
        nodeContrastRatio = ratio;
        contrastCheckedCount += 1;

        const fgHex = rgb01ToHex(fgColor);
        const bgHex = rgb01ToHex(effectiveBg);

        if (ratio < requiredAA) {
          const aaFix = solveAccessibleColor(fgColor, effectiveBg, requiredAA, fgColor.a);
          const aaaFix = solveAccessibleColor(fgColor, effectiveBg, requiredAAA, fgColor.a);
          findings.push({
            id: frame.id + "::" + node.id + "::CONTRAST",
            frameId: frame.id,
            frameName: frame.name,
            nodeId: node.id,
            nodeName: node.name,
            nodeType: node.type,
            category: "contrast",
            severity: "error",
            ruleId: isText ? "WCAG_1_4_3_TEXT_CONTRAST" : "WCAG_1_4_11_UI_CONTRAST",
            title: isText
              ? "Low Text Contrast (" + round2(ratio) + ":1 < " + requiredAA + ":1 AA)"
              : "Low UI Component Contrast (" + round2(ratio) + ":1 < 3.0:1 AA)",
            message:
              fgHex +
              " on " +
              bgHex +
              " scores " +
              round2(ratio) +
              ":1 (APCA Lc " +
              apcaLc +
              "). Nearest brand-preserving AA fix: " +
              aaFix.hex +
              " (" +
              aaFix.ratio +
              ":1).",
            currentHex: fgHex,
            backgroundHex: bgHex,
            currentOpacity: round2(fgColor.a),
            currentRatio: round2(ratio),
            apcaLc,
            requiredAA,
            requiredAAA,
            isLargeText: large,
            aaFix,
            aaaFix,
            fixable: true,
            snippet: text ? text.slice(0, 72) : node.name,
          });
        } else {
          contrastPassCount += 1;
        }

        // CVD Contrast Collapse Check
        const cvd = evaluateColorBlindnessContrast(fgColor, effectiveBg);
        const worstTypes = [];
        const cvdKeys = ["protanopia", "deuteranopia", "tritanopia"];
        for (let k = 0; k < cvdKeys.length; k += 1) {
          const typeKey = cvdKeys[k];
          if (cvd[typeKey].ratio < 3.0 && ratio >= 3.0) {
            worstTypes.push({ type: typeKey, ...cvd[typeKey] });
          }
        }
        if (worstTypes.length > 0) {
          worstTypes.sort((a, b) => a.ratio - b.ratio);
          const worst = worstTypes[0];
          findings.push({
            id: frame.id + "::" + node.id + "::CVD_COLLAPSE",
            frameId: frame.id,
            frameName: frame.name,
            nodeId: node.id,
            nodeName: node.name,
            nodeType: node.type,
            category: "colorBlindness",
            severity: "warning",
            ruleId: "CVD_CONTRAST_COLLAPSE",
            title:
              "Color-Blind Contrast Collapse (" +
              worst.type +
              ": " +
              worst.ratio +
              ":1)",
            message:
              "Normal vision ratio is " +
              round2(ratio) +
              ":1, but under " +
              worst.type +
              " (" +
              worst.fgHex +
              " on " +
              worst.bgHex +
              ") contrast drops to " +
              worst.ratio +
              ":1 (< 3.0:1). Increase luminance separation.",
            currentHex: fgHex,
            backgroundHex: bgHex,
            currentRatio: round2(ratio),
            cvdSimulation: cvd,
            fixable: false,
            snippet: text ? text.slice(0, 72) : node.name,
          });
        }
      }

      // Track status indicators for pairwise CVD confusion check
      if (solid && isStatusIndicator(node)) {
        statusNodes.push({
          node,
          color: compositeOver(solid.color, effectiveBg),
          hex: rgb01ToHex(compositeOver(solid.color, effectiveBg)),
        });
      }

      // Track primary vs decline CTAs for visual asymmetry dark-pattern check
      if (node.ctaKind === "primary" || (isInteractiveCandidate(node) && /\b(primary|accept|subscribe|upgrade|buy)\b/i.test(String(node.name || "")))) {
        primaryCtas.push({ node, ratio: nodeContrastRatio });
      }
      if (
        node.ctaKind === "decline" ||
        (isInteractiveCandidate(node) &&
          (/\b(decline|cancel|dismiss|skip|opt[-_ ]?out|no[-_ ]?thanks)\b/i.test(String(node.name || "")) ||
            /解約|スキップ|今はしない|拒否/.test(text)))
      ) {
        declineCtas.push({ node, ratio: nodeContrastRatio });
      }

      // ---- B. Touch Target & Typography Ergonomics ----
      if (isInteractiveCandidate(node) && typeof node.width === "number" && typeof node.height === "number") {
        const w = Math.round(node.width);
        const h = Math.round(node.height);
        if (w < 24 || h < 24) {
          findings.push({
            id: frame.id + "::" + node.id + "::TOUCH_AA",
            frameId: frame.id,
            frameName: frame.name,
            nodeId: node.id,
            nodeName: node.name,
            nodeType: node.type,
            category: "ergonomics",
            severity: "error",
            ruleId: "TOUCH_TARGET_WCAG_AA",
            title: "Touch Target Too Small (" + w + "×" + h + "px < 24×24px)",
            message:
              "Interactive control '" +
              node.name +
              "' is " +
              w +
              "×" +
              h +
              "px, failing WCAG 2.2 SC 2.5.8 minimum target size (24×24px). Resize hit area to >= 24×24px (44×44px recommended for mobile).",
            dimensions: { width: w, height: h },
            fixable: false,
            snippet: text || node.name,
          });
        } else if (w < 44 || h < 44) {
          findings.push({
            id: frame.id + "::" + node.id + "::TOUCH_HIG",
            frameId: frame.id,
            frameName: frame.name,
            nodeId: node.id,
            nodeName: node.name,
            nodeType: node.type,
            category: "ergonomics",
            severity: "warning",
            ruleId: "TOUCH_TARGET_MOBILE_HIG",
            title: "Below Mobile Touch Target (" + w + "×" + h + "px < 44×44px)",
            message:
              "Control '" +
              node.name +
              "' passes WCAG AA (24px) but falls below Apple HIG / Material 44×44px mobile touch ergonomics.",
            dimensions: { width: w, height: h },
            fixable: false,
            snippet: text || node.name,
          });
        }
      }

      if (node.type === "TEXT") {
        const fs = typeof node.fontSize === "number" ? node.fontSize : 14;
        if (fs < 12) {
          findings.push({
            id: frame.id + "::" + node.id + "::MICRO_TEXT",
            frameId: frame.id,
            frameName: frame.name,
            nodeId: node.id,
            nodeName: node.name,
            nodeType: node.type,
            category: "ergonomics",
            severity: fs < 10 ? "error" : "warning",
            ruleId: "TYPOGRAPHY_MICRO_TEXT",
            title: "Micro Text Size (" + fs + "px < 12px)",
            message:
              "Text '" +
              (text.slice(0, 40) || node.name) +
              "' is set at " +
              fs +
              "px, harming legibility" +
              (fs < 10 ? " and creating fine-print compliance risk." : "."),
            fontSize: fs,
            fixable: false,
            snippet: text.slice(0, 72),
          });
        }
        if (
          typeof node.lineHeightPx === "number" &&
          node.lineHeightPx > 0 &&
          fs <= 18 &&
          node.lineHeightPx / fs < 1.2
        ) {
          findings.push({
            id: frame.id + "::" + node.id + "::LINE_HEIGHT",
            frameId: frame.id,
            frameName: frame.name,
            nodeId: node.id,
            nodeName: node.name,
            nodeType: node.type,
            category: "ergonomics",
            severity: "warning",
            ruleId: "TYPOGRAPHY_TIGHT_LINE_HEIGHT",
            title: "Tight Body Line-Height (" + round2(node.lineHeightPx / fs) + "×)",
            message:
              "Line height is " +
              node.lineHeightPx +
              "px for " +
              fs +
              "px text (< 1.2×). Increase line height to >= 1.4× for readable body copy.",
            fixable: false,
            snippet: text.slice(0, 72),
          });
        }

        const headingLevel = inferHeadingLevel(node);
        if (headingLevel !== null) {
          headings.push({ level: headingLevel, fontSize: fs, node });
        }
      }

      // ---- C. Node-Level EN & JP Dark-Pattern Linter ----
      if (text) {
        for (let r = 0; r < DARK_PATTERN_RULES.length; r += 1) {
          const rule = DARK_PATTERN_RULES[r];
          let matched = false;
          for (let p = 0; p < rule.patterns.length; p += 1) {
            if (rule.patterns[p].test(text)) {
              matched = true;
              break;
            }
          }
          if (!matched) continue;

          // Pre-checked add-on only fires if the node is explicitly pre-checked OR explicitly auto-added
          if (rule.id === "DP_PRECHECKED_ADDON") {
            const explicitAutoAdd = /automatically\s*added/i.test(text);
            const isPrechecked =
              node.checked === true ||
              /pre[-_ ]?checked|checked/i.test(String(node.name || "")) ||
              /^[☑✓✔]/.test(text);
            if (!explicitAutoAdd && !isPrechecked) {
              continue;
            }
          }

          let severity = rule.severity;
          let extraNote = "";
          if (rule.id === "DP_HIDDEN_AUTORENEWAL") {
            const fs = typeof node.fontSize === "number" ? node.fontSize : 14;
            const lowContrast = nodeContrastRatio !== null && nodeContrastRatio < 4.5;
            if (fs < 12 || lowContrast) {
              severity = "error";
              extraNote =
                " Escalated to ERROR because renewal disclosure is hidden in " +
                (fs < 12 ? fs + "px micro text" : "") +
                (fs < 12 && lowContrast ? " + " : "") +
                (lowContrast ? round2(nodeContrastRatio) + ":1 low contrast." : ".");
            }
          }

          findings.push({
            id: frame.id + "::" + node.id + "::" + rule.id,
            frameId: frame.id,
            frameName: frame.name,
            nodeId: node.id,
            nodeName: node.name,
            nodeType: node.type,
            category: "darkPatterns",
            severity,
            ruleId: rule.id,
            title: rule.title,
            regulation: rule.regulation,
            message:
              'Detected "' +
              text.slice(0, 88) +
              '". ' +
              rule.recommendation +
              extraNote,
            fixable: false,
            snippet: text.slice(0, 88),
          });
        }
      }
    }

    // ---- D. Heading Hierarchy Check ----
    if (headings.length > 0) {
      const levels = headings.map((h) => h.level);
      const h1List = headings.filter((h) => h.level === 1);
      if (h1List.length === 0 && levels.some((l) => l >= 2)) {
        findings.push({
          id: frame.id + "::HEADING_NO_H1",
          frameId: frame.id,
          frameName: frame.name,
          nodeId: headings[0].node.id,
          nodeName: headings[0].node.name,
          nodeType: "TEXT",
          category: "ergonomics",
          severity: "warning",
          ruleId: "HEADING_MISSING_H1",
          title: "Heading Hierarchy Missing H1",
          message:
            "Frame uses H" +
            Math.min.apply(null, levels) +
            " without an H1 primary heading. Establish a clear single H1 for screen-reader navigation.",
          fixable: false,
        });
      }
      if (h1List.length > 1) {
        findings.push({
          id: frame.id + "::HEADING_MULTI_H1",
          frameId: frame.id,
          frameName: frame.name,
          nodeId: h1List[1].node.id,
          nodeName: h1List[1].node.name,
          nodeType: "TEXT",
          category: "ergonomics",
          severity: "warning",
          ruleId: "HEADING_MULTIPLE_H1",
          title: "Multiple H1 Headings in Single Frame (" + h1List.length + ")",
          message:
            "Screen contains " +
            h1List.length +
            " H1 headings. Keep one primary H1 per view and demote secondary titles to H2.",
          fixable: false,
        });
      }
      const uniqueSorted = Array.from(new Set(levels)).sort((a, b) => a - b);
      for (let idx = 1; idx < uniqueSorted.length; idx += 1) {
        if (uniqueSorted[idx] - uniqueSorted[idx - 1] > 1) {
          findings.push({
            id: frame.id + "::HEADING_SKIP_" + uniqueSorted[idx - 1] + "_" + uniqueSorted[idx],
            frameId: frame.id,
            frameName: frame.name,
            nodeId: headings.find((h) => h.level === uniqueSorted[idx]).node.id,
            nodeName: headings.find((h) => h.level === uniqueSorted[idx]).node.name,
            nodeType: "TEXT",
            category: "ergonomics",
            severity: "warning",
            ruleId: "HEADING_SKIPPED_LEVEL",
            title: "Skipped Heading Level (H" + uniqueSorted[idx - 1] + " → H" + uniqueSorted[idx] + ")",
            message:
              "Heading outline jumps from H" +
              uniqueSorted[idx - 1] +
              " directly to H" +
              uniqueSorted[idx] +
              ". Avoid skipping heading levels for assistive technology clarity.",
            fixable: false,
          });
        }
      }
      // Inverted heading scale check (H2 bigger than H1)
      if (h1List.length >= 1) {
        const minH1Size = Math.min.apply(
          null,
          h1List.map((h) => h.fontSize)
        );
        const oversizedSub = headings.find((h) => h.level > 1 && h.fontSize > minH1Size);
        if (oversizedSub) {
          findings.push({
            id: frame.id + "::HEADING_INVERTED",
            frameId: frame.id,
            frameName: frame.name,
            nodeId: oversizedSub.node.id,
            nodeName: oversizedSub.node.name,
            nodeType: "TEXT",
            category: "ergonomics",
            severity: "warning",
            ruleId: "HEADING_INVERTED_SCALE",
            title:
              "Inverted Heading Scale (H" +
              oversizedSub.level +
              " " +
              oversizedSub.fontSize +
              "px > H1 " +
              minH1Size +
              "px)",
            message:
              "Subheading '" +
              oversizedSub.node.name +
              "' is visually larger than H1, causing semantic/visual hierarchy mismatch.",
            fixable: false,
          });
        }
      }
    }

    // ---- E. Visual Asymmetry (Accept vs Decline CTA) ----
    if (primaryCtas.length > 0 && declineCtas.length > 0) {
      const pNode = primaryCtas[0].node;
      for (let d = 0; d < declineCtas.length; d += 1) {
        const dec = declineCtas[d];
        const pFont = typeof pNode.fontSize === "number" ? pNode.fontSize : 16;
        const dFont = typeof dec.node.fontSize === "number" ? dec.node.fontSize : 14;
        const ratioFail = dec.ratio !== null && dec.ratio < 3.0;
        const fontShrink = dFont < pFont * 0.65 && dFont <= 11;
        if (ratioFail || fontShrink) {
          findings.push({
            id: frame.id + "::" + dec.node.id + "::DP_ASYMMETRY",
            frameId: frame.id,
            frameName: frame.name,
            nodeId: dec.node.id,
            nodeName: dec.node.name,
            nodeType: dec.node.type,
            category: "darkPatterns",
            severity: "warning",
            ruleId: "DP_VISUAL_ASYMMETRY",
            title: "Visual Hierarchy Manipulation on Decline / Cancel Action",
            regulation: "EU DSA Art. 25 / EDPB Dark Patterns",
            message:
              "Decline/cancel control '" +
              dec.node.name +
              "' is visually buried relative to primary CTA '" +
              pNode.name +
              "' (" +
              (ratioFail ? "contrast " + round2(dec.ratio) + ":1" : dFont + "px vs " + pFont + "px") +
              "). Give reject/cancel choices fair legibility.",
            fixable: false,
            snippet: dec.node.characters || dec.node.name,
          });
        }
      }
    }

    // ---- F. Pairwise Color-Blindness Status Indicator Confusion ----
    for (let a = 0; a < statusNodes.length; a += 1) {
      for (let b = a + 1; b < statusNodes.length; b += 1) {
        const sA = statusNodes[a];
        const sB = statusNodes[b];
        const normalDist = perceptualRgbDistance(sA.color, sB.color);
        if (normalDist < 0.28) continue; // Already similar color intentionally
        const checkTypes = ["deuteranopia", "protanopia"];
        for (let t = 0; t < checkTypes.length; t += 1) {
          const typeKey = checkTypes[t];
          const simA = simulateColorBlindness(sA.color, typeKey);
          const simB = simulateColorBlindness(sB.color, typeKey);
          const simDist = perceptualRgbDistance(simA, simB);
          const simCR = contrastRatio(simA, simB);
          if (simDist <= 0.16 && simCR <= 1.45) {
            findings.push({
              id: frame.id + "::CVD_PAIR::" + sA.node.id + "::" + sB.node.id + "::" + typeKey,
              frameId: frame.id,
              frameName: frame.name,
              nodeId: sA.node.id,
              nodeName: sA.node.name + " vs " + sB.node.name,
              nodeType: sA.node.type,
              category: "colorBlindness",
              severity: "warning",
              ruleId: "CVD_STATUS_CONFUSION",
              title: "Status Colors Indistinguishable under " + typeKey,
              message:
                "'" +
                sA.node.name +
                "' (" +
                sA.hex +
                " → " +
                simA.hex +
                ") and '" +
                sB.node.name +
                "' (" +
                sB.hex +
                " → " +
                simB.hex +
                ") collapse to " +
                round2(simCR) +
                ":1 separation under " +
                typeKey +
                ". Pair status colors with distinct shapes/icons or explicit text.",
              pairColors: {
                a: { original: sA.hex, simulated: simA.hex, name: sA.node.name },
                b: { original: sB.hex, simulated: simB.hex, name: sB.node.name },
              },
              fixable: false,
            });
            break;
          }
        }
      }
    }

    // ---- G. Screen-Level Checkout Legal Disclosure Audit (JP Tokushoho Art. 12-6 & EN) ----
    const combinedText = (String(frame.name || "") + "\n" + allTexts.join("\n")).trim();
    const hasJapanese = JP_CHAR_RE.test(combinedText);
    const isJpCheckout = hasJapanese && JP_CHECKOUT_TRIGGER_RE.test(combinedText);
    const isEnCheckout = !isJpCheckout && EN_CHECKOUT_TRIGGER_RE.test(combinedText);

    if (isJpCheckout) {
      const missing = [];
      for (let idx = 0; idx < JP_TOKUSHOHO_ITEMS.length; idx += 1) {
        const item = JP_TOKUSHOHO_ITEMS[idx];
        if (!item.regex.test(combinedText)) {
          missing.push(item.label);
        }
      }
      if (missing.length > 0) {
        findings.push({
          id: frame.id + "::JP_TOKUSHOHO_ART12_6",
          frameId: frame.id,
          frameName: frame.name,
          nodeId: frame.id,
          nodeName: frame.name,
          nodeType: "FRAME",
          category: "darkPatterns",
          severity: "error",
          ruleId: "JP_TOKUSHOHO_ART12_6",
          title:
            "Japan Tokushoho Art. 12-6 Missing Final-Screen Disclosures (" +
            missing.length +
            "/5)",
          regulation: "特定商取引法 第12条の6（最終確認画面表示義務）",
          message:
            "Japanese checkout/order screen is missing mandatory statutory disclosures: " +
            missing.join(", ") +
            ". Display all 6 statutory items clearly before the final order button.",
          missingDisclosures: missing,
          fixable: false,
        });
      }
    } else if (isEnCheckout) {
      const hasTotal = /(total|billed|per\s*month|\/mo|\/yr|\$\d)/i.test(combinedText);
      const hasCancel = /(cancel\s*anytime|cancellation|cancel\s*before|refund|terms)/i.test(
        combinedText
      );
      const missingEn = [];
      if (!hasTotal) missingEn.push("Total / Recurring Price");
      if (!hasCancel) missingEn.push("Cancellation Policy / Terms");
      if (missingEn.length > 0) {
        findings.push({
          id: frame.id + "::EN_CHECKOUT_DISCLOSURE",
          frameId: frame.id,
          frameName: frame.name,
          nodeId: frame.id,
          nodeName: frame.name,
          nodeType: "FRAME",
          category: "darkPatterns",
          severity: "warning",
          ruleId: "EN_CHECKOUT_DISCLOSURE",
          title: "Checkout Screen Missing Key Billing Disclosures",
          regulation: "FTC Negative Option / EU Consumer Rights",
          message:
            "Checkout/pricing screen lacks visible: " +
            missingEn.join(", ") +
            ". Place total due and cancellation terms clearly above the submit CTA.",
          missingDisclosures: missingEn,
          fixable: false,
        });
      }
    }

    const summary = computeSummary(findings, contrastCheckedCount, contrastPassCount);

    return {
      frameId: frame.id,
      frameName: frame.name,
      nodeCount: nodes.length,
      summary,
      findings,
    };
  }

  function computeSummary(findings, contrastChecked, contrastPassed) {
    let errors = 0;
    let warnings = 0;
    let info = 0;
    let fixableCount = 0;
    const byCategory = {
      contrast: 0,
      ergonomics: 0,
      darkPatterns: 0,
      colorBlindness: 0,
    };

    for (let i = 0; i < findings.length; i += 1) {
      const f = findings[i];
      if (f.severity === "error") errors += 1;
      else if (f.severity === "warning") warnings += 1;
      else info += 1;
      if (f.fixable) fixableCount += 1;
      if (byCategory[f.category] !== undefined) {
        byCategory[f.category] += 1;
      }
    }

    const weightedPenalty = errors * 0.13 + warnings * 0.05 + info * 0.015;
    const score =
      findings.length === 0
        ? 100
        : Math.max(1, Math.min(99, Math.round(100 * Math.exp(-weightedPenalty))));
    let grade = "F";
    if (score >= 95) grade = "A+";
    else if (score >= 90) grade = "A";
    else if (score >= 80) grade = "B";
    else if (score >= 70) grade = "C";
    else if (score >= 55) grade = "D";

    return {
      score,
      grade,
      totalFindings: findings.length,
      errors,
      warnings,
      info,
      fixableCount,
      contrastChecked: contrastChecked || 0,
      contrastPassed: contrastPassed || 0,
      byCategory,
    };
  }

  // =========================================================================
  // 5. Figma Native Payments Entitlement Gate (`figma.payments`)
  // =========================================================================

  function evaluateEntitlement(paymentsApi, options) {
    const opts = options || {};
    const statusType =
      paymentsApi && paymentsApi.status && typeof paymentsApi.status.type === "string"
        ? paymentsApi.status.type
        : "UNPAID";
    const isPaid = statusType === "PAID" || opts.forcePro === true;

    return {
      tier: isPaid ? "PRO" : "FREE",
      isPaid,
      paymentsStatusType: statusType,
      canBatchAudit: isPaid,
      canAutoFixAll: isPaid,
      canExportCertificate: isPaid,
      maxFramesPerAudit: isPaid ? Infinity : PRICING.freeFrameLimit,
      pricing: PRICING,
    };
  }

  /**
   * Audits 1 or more frames respecting Figma Native Payments Free vs Pro gating.
   */
  function auditDocumentFrames(frames, paymentsApi, options) {
    const list = Array.isArray(frames) ? frames : [];
    const entitlement = evaluateEntitlement(paymentsApi, options);

    const truncatedByFreeTier = !entitlement.canBatchAudit && list.length > entitlement.maxFramesPerAudit;
    const scopedFrames = truncatedByFreeTier
      ? list.slice(0, entitlement.maxFramesPerAudit)
      : list;

    const frameResults = [];
    const allFindings = [];
    let totalContrastChecked = 0;
    let totalContrastPassed = 0;

    for (let i = 0; i < scopedFrames.length; i += 1) {
      const res = auditFrame(scopedFrames[i], options);
      frameResults.push(res);
      for (let j = 0; j < res.findings.length; j += 1) {
        allFindings.push(res.findings[j]);
      }
      totalContrastChecked += res.summary.contrastChecked;
      totalContrastPassed += res.summary.contrastPassed;
    }

    const summary = computeSummary(allFindings, totalContrastChecked, totalContrastPassed);

    return {
      engineVersion: ENGINE_VERSION,
      auditedAt: new Date().toISOString(),
      entitlement,
      totalFramesSelected: list.length,
      auditedFrameCount: scopedFrames.length,
      truncatedByFreeTier,
      skippedFrameCount: Math.max(0, list.length - scopedFrames.length),
      summary,
      frames: frameResults,
      findings: allFindings,
    };
  }

  // =========================================================================
  // 6. Dev-Handoff Accessibility & Dark-Pattern Certificate Exporters
  // =========================================================================

  function exportMarkdownReport(auditResult) {
    const res = auditResult || {};
    const summary = res.summary || computeSummary([], 0, 0);
    const findings = Array.isArray(res.findings) ? res.findings : [];
    const lines = [];

    lines.push("# DesignGate — WCAG 2.2 & Dark-Pattern Accessibility Certificate");
    lines.push("");
    lines.push("- **Generated**: " + (res.auditedAt || new Date().toISOString()));
    lines.push("- **Engine**: DesignGate v" + (res.engineVersion || ENGINE_VERSION) + " (100% Local Zero-Network)");
    lines.push(
      "- **Audit Score**: **" +
        summary.score +
        "/100 (" +
        summary.grade +
        ")** — " +
        summary.errors +
        " errors, " +
        summary.warnings +
        " warnings"
    );
    lines.push(
      "- **Frames Audited**: " +
        (res.auditedFrameCount || (res.frames ? res.frames.length : 1)) +
        " | **Contrast Checks Passed**: " +
        summary.contrastPassed +
        "/" +
        summary.contrastChecked
    );
    lines.push("");

    const contrastFindings = findings.filter((f) => f.category === "contrast");
    const ergonomicsFindings = findings.filter((f) => f.category === "ergonomics");
    const dpFindings = findings.filter((f) => f.category === "darkPatterns");
    const cvdFindings = findings.filter((f) => f.category === "colorBlindness");

    if (findings.length === 0) {
      lines.push("## Status: PASS (Zero Accessibility or Dark-Pattern Findings)");
      lines.push("");
      lines.push("All audited nodes meet WCAG 2.2 AA contrast, touch target ergonomics, CVD separation, and EN/JP checkout transparency checks.");
      return lines.join("\n");
    }

    if (contrastFindings.length > 0) {
      lines.push("## 1. WCAG 2.2 Contrast & Auto-Fix Tokens");
      lines.push("");
      lines.push("| Frame | Node | Current | Background | Ratio (APCA) | AA Auto-Fix | AAA Auto-Fix |");
      lines.push("| --- | --- | --- | --- | --- | --- | --- |");
      for (let i = 0; i < contrastFindings.length; i += 1) {
        const f = contrastFindings[i];
        lines.push(
          "| " +
            escapeMd(f.frameName) +
            " | " +
            escapeMd(f.nodeName) +
            " | `" +
            f.currentHex +
            "` | `" +
            f.backgroundHex +
            "` | " +
            f.currentRatio +
            ":1 (Lc " +
            f.apcaLc +
            ") | `" +
            f.aaFix.hex +
            "` (" +
            f.aaFix.ratio +
            ":1) | `" +
            f.aaaFix.hex +
            "` (" +
            f.aaaFix.ratio +
            ":1) |"
        );
      }
      lines.push("");
    }

    if (dpFindings.length > 0) {
      lines.push("## 2. EN/JP Dark-Pattern & Legal Compliance Findings");
      lines.push("");
      for (let i = 0; i < dpFindings.length; i += 1) {
        const f = dpFindings[i];
        lines.push(
          "- **[" +
            f.severity.toUpperCase() +
            "] " +
            f.ruleId +
            "** (`" +
            f.frameName +
            "` / `" +
            f.nodeName +
            "`): " +
            f.title +
            (f.regulation ? " — *" + f.regulation + "*" : "") +
            ". " +
            f.message
        );
      }
      lines.push("");
    }

    if (ergonomicsFindings.length > 0) {
      lines.push("## 3. Touch Target & Typography Ergonomics");
      lines.push("");
      for (let i = 0; i < ergonomicsFindings.length; i += 1) {
        const f = ergonomicsFindings[i];
        lines.push(
          "- **[" +
            f.severity.toUpperCase() +
            "] " +
            f.ruleId +
            "** (`" +
            f.nodeName +
            "`): " +
            f.title +
            " — " +
            f.message
        );
      }
      lines.push("");
    }

    if (cvdFindings.length > 0) {
      lines.push("## 4. Color-Blindness (CVD) Simulation Warnings");
      lines.push("");
      for (let i = 0; i < cvdFindings.length; i += 1) {
        const f = cvdFindings[i];
        lines.push("- **[" + f.severity.toUpperCase() + "] " + f.ruleId + "**: " + f.title + " — " + f.message);
      }
      lines.push("");
    }

    return lines.join("\n");
  }

  function escapeMd(val) {
    return String(val || "").replace(/\|/g, "\\|").replace(/\r?\n/g, " ");
  }

  function escapeCsvCell(val) {
    const str = String(val === undefined || val === null ? "" : val);
    if (/[",\r\n]/.test(str)) {
      return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
  }

  function exportCsvReport(auditResult) {
    const findings = Array.isArray(auditResult && auditResult.findings)
      ? auditResult.findings
      : [];
    const header = [
      "Frame",
      "NodeId",
      "NodeName",
      "Category",
      "Severity",
      "RuleId",
      "Title",
      "CurrentHex",
      "BackgroundHex",
      "CurrentRatio",
      "SuggestedAAHex",
      "SuggestedAARatio",
      "SuggestedAAAHex",
      "Message",
    ];
    const rows = [header.map(escapeCsvCell).join(",")];
    for (let i = 0; i < findings.length; i += 1) {
      const f = findings[i];
      rows.push(
        [
          f.frameName,
          f.nodeId,
          f.nodeName,
          f.category,
          f.severity,
          f.ruleId,
          f.title,
          f.currentHex || "",
          f.backgroundHex || "",
          f.currentRatio !== undefined ? f.currentRatio : "",
          f.aaFix ? f.aaFix.hex : "",
          f.aaFix ? f.aaFix.ratio : "",
          f.aaaFix ? f.aaaFix.hex : "",
          f.message,
        ]
          .map(escapeCsvCell)
          .join(",")
      );
    }
    return rows.join("\r\n");
  }

  return {
    ENGINE_VERSION,
    PRICING,
    CVD_MATRICES,
    DARK_PATTERN_RULES,
    JP_TOKUSHOHO_ITEMS,
    clamp01,
    quantizeRgb01,
    hexToRgb01,
    rgb01ToHex,
    normalizeColor,
    compositeOver,
    resolveEffectiveBackground,
    srgbToLinear,
    linearToSrgb,
    relativeLuminance,
    contrastRatio,
    apcaContrast,
    rgb01ToHsl,
    hslToRgb01,
    perceptualRgbDistance,
    solveAccessibleColor,
    isLargeText,
    simulateColorBlindness,
    evaluateColorBlindnessContrast,
    auditFrame,
    auditDocumentFrames,
    evaluateEntitlement,
    exportMarkdownReport,
    exportCsvReport,
  };
});
