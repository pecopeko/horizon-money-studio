# DesignGate — 5-Minute `$0.00` Figma Community & Native Payments Publishing Guide

Publish **DesignGate** to the **Figma Community Plugin Marketplace** with **`$0.00` upfront cost** and enable **Figma Built-In Payments** (`$12/mo` subscription or `$39` one-time license) — **no external Stripe backend, no webhook servers, and no paid hosting required**.

---

## Prerequisites

- **Figma Desktop App** (free Starter account is sufficient to develop and publish Community plugins).
- Local copy of this repository (`manifest.json`, `code.js`, `ui.html`, `assets/icon-128.png`, `assets/community-cover-1920x960.png`).
- Zero npm install required — `code.js` and `ui.html` are 100% pre-built and dependency-free. (To re-bundle after editing `src/`, run `node scripts/build_plugin.mjs`.)

---

## Step 1 — Import into Figma Desktop (1 minute)

1. Open any design file in **Figma Desktop**.
2. Go to the top menu: **Plugins → Development → Import plugin from manifest...**
3. Select `manifest.json` from this repository.
4. Run **Plugins → Development → DesignGate — WCAG 2.2 Auto-Fix & Checkout Dark-Pattern Linter**.
5. Select any frame on your canvas and verify:
   - Live WCAG 2.2 AA/AAA + APCA contrast ratios and **1-click Apply AA / AAA** fill mutations (`Cmd+Z` undo works natively).
   - Touch target (`24×24px` / `44×44px`), micro-text (`< 12px`), heading outline, CVD matrix, and EN/JP dark-pattern / Tokushoho Art. 12-6 checks.
   - Zero network requests (`manifest.json` sets `"networkAccess": { "allowedDomains": ["none"] }`).

> **Note on `manifest.json` `id`**: When you prepare for Community publishing, Figma assigns your permanent numeric Plugin ID automatically during **Publish** (or via **Plugins → Development → New Plugin**). Keep `"permissions": ["payments"]` in `manifest.json` once you opt in to Figma Community Payments.

---

## Step 2 — Submit to Figma Community (`$0.00`, 2 minutes)

1. In Figma Desktop, open **Plugins → Manage plugins → Development**.
2. Click **`...` → Publish** next to **DesignGate**.
3. Fill in the Community listing metadata:
   - **Name**: `DesignGate — WCAG 2.2 Auto-Fix & Checkout Dark-Pattern Linter`
   - **Tagline**: `1-click brand-preserving WCAG 2.2 contrast auto-fix + EN/JP checkout dark-pattern & Tokushoho Art. 12-6 linter (100% local).`
   - **Icon (`128×128`)**: Upload `assets/icon-128.png`.
   - **Cover Art (`1920×960`)**: Upload `assets/community-cover-1920x960.png`.
   - **Category**: `Accessibility` / `Design Systems`
   - **Tags**: `accessibility`, `wcag`, `contrast`, `dark-patterns`, `design-systems`, `color-blindness`, `apca`, `japan`, `tokushoho`
   - **Live Interactive Demo Link** (in description): `https://pecopeko.github.io/designgate-figma-plugin/`
   - **Privacy & Security Note**: Highlight `networkAccess.allowedDomains: ["none"]` — Figma displays the zero-network local execution guarantee directly on the plugin page.
4. Click **Publish** to enter Figma Community review (typically 2–5 business days; `$0.00` fee).

---

## Step 3 — Enable Figma Native Payments (`$12/mo` or `$39` One-Time, 2 minutes)

DesignGate already ships with official **`figma.payments`** entitlement checks inside `code.js` (`src/core/audit-engine.js` -> `evaluateEntitlement()` & `src/figma/controller.js` -> `initiate-checkout`):

- **Free Tier (`figma.payments.status.type === "UNPAID"`)**:
  - Single-frame WCAG 2.2 + APCA contrast audit
  - 1-click individual **Apply AA** / **Apply AAA** Auto-Fix on canvas
  - Touch target & typography ergonomics audit
  - Full EN & JP dark-pattern + Tokushoho Art. 12-6 checkout legal linter
  - Color-blindness (Protanopia / Deuteranopia / Tritanopia) matrix check
- **Pro Tier (`figma.payments.status.type === "PAID"`)**:
  - **Full-Page Multi-Frame Batch Audit** (unlimited frames per scan)
  - **1-Click "Auto-Fix All Contrast"** across entire selection/page
  - **Dev-Handoff Accessibility & Dark-Pattern Certificate Export** (Markdown PR report + RFC-4180 CSV)

### How to Turn On Figma Built-In Payments

1. In your Figma Community Creator profile, complete **Monetization Onboarding** (Figma handles checkout, VAT/sales tax, invoicing, and payouts via Stripe Express inside Figma — `$0.00` monthly overhead; Figma only deducts a standard marketplace fee on completed sales).
2. On your published **DesignGate** plugin settings page, enable **Sell this resource on Community**:
   - **Pricing Model**: Choose **Freemium** (recommended: **`$12/month`** recurring subscription OR **`$39` one-time purchase** — test conversion across both!).
   - **Free Trial**: Optional 7-day free trial handled natively by `figma.payments.initiateCheckoutAsync()`.
3. Verify `manifest.json` contains `"permissions": ["payments"]` (already configured!) and publish the update.
4. Test both states locally before shipping updates using Figma Desktop's built-in **Plugins → Development → Set Payment Status (`PAID` / `UNPAID`)** toggle!

---

## Step 4 — Updating After Code Changes

```bash
# Re-assemble standalone code.js and sync docs/audit-engine.js
node scripts/build_plugin.mjs

# Run full automated test suite
node --test test/designgate.test.mjs
```

Zero bundlers (`webpack`, `esbuild`, `vite`) or `node_modules` are required.
