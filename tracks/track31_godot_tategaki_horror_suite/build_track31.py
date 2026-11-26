"""Build & Package Orchestrator for Track 31 (Godot 4 Tategaki/Furigana + Horror Shaders + 4 Covers).

Outputs:
1. `lite_repo/icon.png` (256x256 PNG) + 4 `covers/*.png` (exact 630x500 RGB PNGs)
2. Syncs `lite_repo/addons/tokyo_tategaki_furigana/` -> `pro_pack/addons/tokyo_tategaki_furigana/`
3. Builds 3 deterministic distribution ZIPs inside `dist/`:
   - `dist/godot-tategaki-html5-preview.zip`
   - `dist/godot-tategaki-lite-v1.0.zip`
   - `dist/godot-tokyo-horror-shaders-tategaki-pro-v1.0.zip`

Brand / Author: peco (https://pecopeko.itch.io | https://github.com/pecopeko)
"""

from __future__ import annotations

from pathlib import Path
import shutil
import sys
import zipfile

if __package__ in (None, ""):
    _repo_root = Path(__file__).resolve().parents[2]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

from tracks.track31_godot_tategaki_horror_suite.generate_covers import generate_all_images

TRACK_DIR = Path(__file__).resolve().parent
LITE_REPO_DIR = TRACK_DIR / "lite_repo"
PRO_PACK_DIR = TRACK_DIR / "pro_pack"
WEB_PREVIEW_DIR = TRACK_DIR / "web_preview"
COVERS_DIR = TRACK_DIR / "covers"
DIST_DIR = TRACK_DIR / "dist"

FIXED_ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def _write_deterministic_zip(zip_path: Path, file_map: list[tuple[str, Path]]) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_entries = sorted(file_map, key=lambda item: item[0])
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for arcname, src_path in sorted_entries:
            clean_arc = arcname.replace("\\", "/").lstrip("/")
            info = zipfile.ZipInfo(filename=clean_arc, date_time=FIXED_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, src_path.read_bytes())
    return zip_path


def sync_lite_addon_into_pro_pack() -> Path:
    """Ensure `pro_pack/addons/tokyo_tategaki_furigana` mirrors `lite_repo` single source of truth."""
    src_addon = LITE_REPO_DIR / "addons" / "tokyo_tategaki_furigana"
    dst_addon = PRO_PACK_DIR / "addons" / "tokyo_tategaki_furigana"
    if dst_addon.exists():
        shutil.rmtree(dst_addon)
    dst_addon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_addon, dst_addon)
    return dst_addon


def build_all() -> dict[str, Path]:
    """Generate all covers/icons, sync addons, and build the 3 distribution ZIP archives."""
    images = generate_all_images()
    sync_lite_addon_into_pro_pack()
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # 1. HTML5 itch.io playable embed archive (must have index.html at root)
    html5_zip = _write_deterministic_zip(
        DIST_DIR / "godot-tategaki-html5-preview.zip",
        [("index.html", WEB_PREVIEW_DIR / "index.html")],
    )

    # 2. Lite MIT Open-Source Addon ZIP
    lite_entries: list[tuple[str, Path]] = [
        ("LICENSE", LITE_REPO_DIR / "LICENSE"),
        ("README.md", LITE_REPO_DIR / "README.md"),
    ]
    lite_addon_root = LITE_REPO_DIR / "addons" / "tokyo_tategaki_furigana"
    for p in sorted(lite_addon_root.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            rel = p.relative_to(LITE_REPO_DIR).as_posix()
            lite_entries.append((rel, p))
    lite_zip = _write_deterministic_zip(
        DIST_DIR / "godot-tategaki-lite-v1.0.zip",
        lite_entries,
    )

    # 3. Pro Commercial Suite ZIP (Both Godot 4 Addons + 4 Shaders + Manga Balloon + Docs + Web Playground)
    pro_entries: list[tuple[str, Path]] = []
    for p in sorted(PRO_PACK_DIR.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            rel = p.relative_to(PRO_PACK_DIR).as_posix()
            pro_entries.append((rel, p))
    pro_entries.append(("web_playground/index.html", WEB_PREVIEW_DIR / "index.html"))
    pro_zip = _write_deterministic_zip(
        DIST_DIR / "godot-tokyo-horror-shaders-tategaki-pro-v1.0.zip",
        pro_entries,
    )

    result: dict[str, Path] = {
        "html5_preview_zip": html5_zip,
        "lite_zip": lite_zip,
        "pro_zip": pro_zip,
    }
    result.update(images)
    return result


if __name__ == "__main__":
    outputs = build_all()
    print("=== Track 31 Build Complete ===")
    for name, path in outputs.items():
        size_kb = path.stat().st_size / 1024.0
        print(f"  - {name:20s}: {path.relative_to(TRACK_DIR)} ({size_kb:.1f} KB)")
