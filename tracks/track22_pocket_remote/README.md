# Track 22 — `PocketBridge` iPhone Safari Remote Browser Console

Zero-dependency (`dependencies: {}`, Node.js v22 built-ins + native `globalThis.WebSocket`) remote control console allowing full touch-screen, native iPhone keyboard, and 1-tap studio deliverable file-upload control of an isolated Headless Chrome session on Mac (`192.168.1.2`) directly from **iPhone Safari** — **with the MacBook lid closed and zero macOS TCC permission popups**.

## Key Capabilities

1. **Zero macOS TCC Popups (`--headless=new` Loopback CDP)**:
   - Spawns an isolated `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` process bound strictly to `127.0.0.1` with a dedicated profile (`tracks/track22_pocket_remote/.chrome_profile`).
   - Also includes `src/macos_desktop.mjs` which silently preflights `CGPreflightScreenCaptureAccess()` and `AXIsProcessTrusted()` via `ctypes` without triggering macOS System Settings dialogs, gracefully reporting `"macOS Screen Recording / Accessibility未許可のため、フタを閉じたまま使えるブラウザモードで動作中"` when TCC is disabled.
2. **Exact iPhone Touch-to-Viewport Coordinate Mapping + Pinch Zoom**:
   - **`👆 タップ操作`** mode: single tap dispatches exact `(x, y)` CDP mouse click with glowing cyan ripple feedback + `180ms` & `650ms` screenshot refresh; 1-finger vertical flick or `⬆️ / ⬇️` buttons scroll smoothly.
   - **`🔍 ピンチ拡大`** mode: zoom (`1x` / `1.8x` / `2.8x` + smooth pan) while preserving exact `(clientX - rect.left) / rect.width * 1280` coordinate clicks.
3. **Native iPhone Keyboard + AutoFill (`Input.insertText`)**:
   - Supports Japanese Kanji/Kana IME, email `@`, passwords (with optional local `🔒` input masking), **`送信`**, **`消して送信`** (`Cmd+A -> Backspace` + React/HTML native value reset), and hardware keys (`Enter`, `Tab`, `⌫`, `Esc`, `←戻る`, `↻更新`, `全選択`, `↑`, `↓`).
4. **1-Tap Server-Side Deliverable File Upload (`DOM.setFileInputFiles`)**:
   - Hardcoded allowlist of studio deliverables (`booth_cover`, `booth_zip`, `kdp_epub`, `kdp_cover`, `kdp_interior_pdf`, `kdp_wrap_pdf`, `vscode_vsix`) with automatic multi-input `accept` attribute matching (e.g. BOOTH `.png` cover vs `.zip` archive).
   - Arbitrary filesystem paths from HTTP requests are strictly rejected (`400`).
5. **1-Tap Quick-Copy Snippet Drawer**:
   - Pre-loaded with the 6 Apify Store descriptions & PPE event names/prices, BOOTH listing copy, Amazon KDP metadata + 7 backend keywords, and 3 Coconala package listings.
6. **Security Hardening**:
   - Mandatory 256-bit cryptographic entry URL (`/s/<64-hex-token>/`) setting `HttpOnly; SameSite=Strict` session cookie, verified via `crypto.timingSafeEqual`.
   - Per-IP brute-force lockout (`10` failed attempts -> `429 Too Many Requests`).
   - Automatic idle shutdown timer (default `120` minutes) cleanly closing Chrome & exiting.

## Usage

```bash
# Run verification suite
node --test test/pocket_remote.test.mjs

# Launch live console (binds LAN IP + prints /s/<256-bit-token>/ URL)
node src/cli.mjs --port 8788 --idle-minutes 120
```
