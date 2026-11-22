import { execFile } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export const TCC_FALLBACK_MESSAGE_JA =
  "macOS Screen Recording / Accessibility未許可のため、フタを閉じたまま使えるブラウザモードで動作中";

const PYTHON_TCC_PREFLIGHT = [
  "import ctypes, json, platform",
  "if platform.system() != 'Darwin':",
  "    print(json.dumps({'screenCapture': False, 'accessibility': False, 'darwin': False}))",
  "else:",
  "    cg = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')",
  "    cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool",
  "    app = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')",
  "    app.AXIsProcessTrusted.restype = ctypes.c_bool",
  "    sc = bool(cg.CGPreflightScreenCaptureAccess())",
  "    ax = bool(app.AXIsProcessTrusted())",
  "    disp_w = int(cg.CGDisplayPixelsWide(cg.CGMainDisplayID()))",
  "    disp_h = int(cg.CGDisplayPixelsHigh(cg.CGMainDisplayID()))",
  "    print(json.dumps({'screenCapture': sc, 'accessibility': ax, 'darwin': True, 'width': disp_w, 'height': disp_h}))",
].join("\n");

/**
 * Non-prompting macOS TCC preflight check.
 * Uses CGPreflightScreenCaptureAccess() and AXIsProcessTrusted() which NEVER trigger
 * macOS System Settings permission popups.
 */
export async function checkMacDesktopPermissions({ pythonBin = "/usr/bin/python3" } = {}) {
  if (process.platform !== "darwin") {
    return {
      screenCapture: false,
      accessibility: false,
      available: false,
      viewport: { width: 1280, height: 900 },
      message: TCC_FALLBACK_MESSAGE_JA,
    };
  }
  try {
    const { stdout } = await execFileAsync(pythonBin, ["-c", PYTHON_TCC_PREFLIGHT], {
      timeout: 4000,
    });
    const parsed = JSON.parse(stdout.trim());
    const available = Boolean(parsed.screenCapture && parsed.accessibility);
    return {
      screenCapture: Boolean(parsed.screenCapture),
      accessibility: Boolean(parsed.accessibility),
      available,
      viewport: {
        width: Number(parsed.width) > 0 ? Number(parsed.width) : 1440,
        height: Number(parsed.height) > 0 ? Number(parsed.height) : 900,
      },
      message: available ? "macOS デスクトップ操作モード利用可能" : TCC_FALLBACK_MESSAGE_JA,
    };
  } catch (err) {
    return {
      screenCapture: false,
      accessibility: false,
      available: false,
      viewport: { width: 1280, height: 900 },
      message: TCC_FALLBACK_MESSAGE_JA,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

/**
 * Optional macOS full-screen controller.
 * Strictly checks checkMacDesktopPermissions() first and refuses to touch
 * `screencapture` or `CGEventPost` unless both TCC permissions are already granted.
 */
export class MacDesktopController {
  constructor({ pythonBin = "/usr/bin/python3" } = {}) {
    this.pythonBin = pythonBin;
  }

  async getStatus() {
    return checkMacDesktopPermissions({ pythonBin: this.pythonBin });
  }

  async captureScreenshot() {
    const perms = await this.getStatus();
    if (!perms.available) {
      return {
        ok: false,
        fallbackToBrowser: true,
        message: TCC_FALLBACK_MESSAGE_JA,
        permissions: perms,
      };
    }

    const tmpFile = path.join(
      os.tmpdir(),
      `pocketbridge-screen-${process.pid}-${Date.now()}.jpg`,
    );
    try {
      await execFileAsync("/usr/sbin/screencapture", ["-x", "-t", "jpg", tmpFile], {
        timeout: 5000,
      });
      const buffer = fs.readFileSync(tmpFile);
      return {
        ok: true,
        buffer,
        viewport: perms.viewport,
        url: "macos://desktop",
        title: "macOS Desktop",
      };
    } finally {
      try {
        fs.rmSync(tmpFile, { force: true });
      } catch {
        // ignore cleanup race
      }
    }
  }

  async click({ x, y }) {
    const perms = await this.getStatus();
    if (!perms.available) {
      return {
        ok: false,
        fallbackToBrowser: true,
        message: TCC_FALLBACK_MESSAGE_JA,
        permissions: perms,
      };
    }

    const py = [
      "import ctypes, sys",
      "x, y = float(sys.argv[1]), float(sys.argv[2])",
      "cg = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')",
      "class CGPoint(ctypes.Structure):",
      "    _fields_ = [('x', ctypes.c_double), ('y', ctypes.c_double)]",
      "cg.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]",
      "cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p",
      "cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]",
      "cg.CFRelease.argtypes = [ctypes.c_void_p]",
      "pt = CGPoint(x, y)",
      "for ev_type in (5, 1, 2):", // kCGEventMouseMoved=5, LeftMouseDown=1, LeftMouseUp=2
      "    ev = cg.CGEventCreateMouseEvent(None, ev_type, pt, 0)",
      "    cg.CGEventPost(0, ev)",
      "    cg.CFRelease(ev)",
    ].join("\n");

    await execFileAsync(this.pythonBin, ["-c", py, String(x), String(y)], { timeout: 4000 });
    return { ok: true, x, y };
  }

  async typeText({ text }) {
    const perms = await this.getStatus();
    if (!perms.available) {
      return {
        ok: false,
        fallbackToBrowser: true,
        message: TCC_FALLBACK_MESSAGE_JA,
        permissions: perms,
      };
    }

    const py = [
      "import ctypes, sys",
      "txt = sys.argv[1]",
      "cg = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')",
      "cg.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]",
      "cg.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p",
      "cg.CGEventKeyboardSetUnicodeString.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_uint16)]",
      "cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]",
      "cg.CFRelease.argtypes = [ctypes.c_void_p]",
      "u16 = txt.encode('utf-16-le')",
      "arr_t = ctypes.c_uint16 * (len(u16) // 2)",
      "buf = arr_t.from_buffer_copy(u16)",
      "for down in (True, False):",
      "    ev = cg.CGEventCreateKeyboardEvent(None, 0, down)",
      "    cg.CGEventKeyboardSetUnicodeString(ev, len(buf), buf)",
      "    cg.CGEventPost(0, ev)",
      "    cg.CFRelease(ev)",
    ].join("\n");

    await execFileAsync(this.pythonBin, ["-c", py, String(text)], { timeout: 4000 });
    return { ok: true, length: String(text).length };
  }
}
