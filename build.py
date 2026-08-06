"""
Build script – produces a standalone HandCursor EXE via PyInstaller.

Usage:
    python build.py           # release build
    python build.py --debug   # keeps console window for troubleshooting
"""

import argparse
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from version import APP_NAME, VERSION

ROOT   = Path(__file__).resolve().parent
DIST   = ROOT / "dist"
BUILD  = ROOT / "build"
ENTRY  = ROOT / "hand_cursor.py"
# Path separator for --add-data differs between platforms
SEP    = ";" if sys.platform == "win32" else ":"


# ── Windows PE version-info file ─────────────────────────────────────────────

def _write_version_file(dest: Path) -> None:
    """Generate a PyInstaller-compatible Windows version-info file."""
    parts   = (VERSION.split(".") + ["0", "0", "0"])[:3]
    maj, min_, pat = (int(p) for p in parts)
    filevers = f"({maj}, {min_}, {pat}, 0)"

    dest.write_text(textwrap.dedent(f"""\
        VSVersionInfo(
          ffi=FixedFileInfo(
            filevers={filevers},
            prodvers={filevers},
            mask=0x3f,
            flags=0x0,
            OS=0x4,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
          ),
          kids=[
            StringFileInfo([
              StringTable(
                u'040904B0',
                [StringStruct(u'CompanyName',      u'HandCursor Project'),
                 StringStruct(u'FileDescription',  u'{APP_NAME} – Hand Gesture Mouse Control'),
                 StringStruct(u'FileVersion',      u'{VERSION}'),
                 StringStruct(u'InternalName',     u'{APP_NAME}'),
                 StringStruct(u'LegalCopyright',   u''),
                 StringStruct(u'OriginalFilename', u'{APP_NAME}.exe'),
                 StringStruct(u'ProductName',      u'{APP_NAME}'),
                 StringStruct(u'ProductVersion',   u'{VERSION}'),
                ])
            ]),
            VarFileInfo([VarStruct(u'Translation', [0x0409, 1200])])
          ]
        )
    """), encoding="utf-8")


# ── Build ─────────────────────────────────────────────────────────────────────

def build(debug: bool = False) -> None:
    print(f"Building {APP_NAME} v{VERSION}  (debug={debug})")

    # Clean previous artefacts
    for d in (DIST, BUILD):
        if d.exists():
            shutil.rmtree(d)
            print(f"  removed {d}")

    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", APP_NAME,
        # MediaPipe ships TFLite models and .so files as package data;
        # --collect-all pulls in everything including the framework bindings.
        "--collect-all", "mediapipe",
        # google.protobuf is used internally by mediapipe
        "--collect-all", "google.protobuf",
        # OpenCV haarcascades and other data files
        "--collect-data", "cv2",
        # Explicit hidden imports that PyInstaller's static analysis misses
        "--hidden-import", "mediapipe",
        "--hidden-import", "mediapipe.python",
        "--hidden-import", "mediapipe.python._framework_bindings",
        "--hidden-import", "mediapipe.tasks",
        "--hidden-import", "mediapipe.tasks.python",
        "--hidden-import", "mediapipe.tasks.python.vision",
        "--hidden-import", "google.protobuf.descriptor",
        "--hidden-import", "google.protobuf.descriptor_pool",
        "--hidden-import", "google.protobuf.message_factory",
        "--hidden-import", "google.protobuf.reflection",
        "--hidden-import", "pyautogui",
        "--hidden-import", "pyscreeze",
        "--hidden-import", "mouseinfo",
        # Seed profiles, read at runtime from sys._MEIPASS. These are
        # read-only; profile_manager copies/saves into a per-user directory,
        # because _MEIPASS is deleted when the executable exits.
        "--add-data", f"profiles{SEP}profiles",
        # Local modules live next to the entry point – PyInstaller picks them
        # up automatically, but explicit imports guard against tree-shaking.
        "--hidden-import", "config",
        "--hidden-import", "gestures",
        "--hidden-import", "profile_manager",
        "--hidden-import", "runtime",
        "--hidden-import", "camera",
        "--hidden-import", "version",
    ]

    # Console window: keep for debug, suppress for release
    args.append("--console" if debug else "--noconsole")

    # Windows-only: embed version metadata in the PE header
    if sys.platform == "win32":
        vfile = ROOT / "_version_info.txt"
        _write_version_file(vfile)
        args += ["--version-file", str(vfile)]

    # macOS-only: set bundle name
    if sys.platform == "darwin":
        args += ["--osx-bundle-identifier", f"com.handcursor.{APP_NAME.lower()}"]

    args.append(str(ENTRY))

    print("  running PyInstaller…")
    result = subprocess.run(args, cwd=ROOT)

    # Clean up temporary version file
    vfile_path = ROOT / "_version_info.txt"
    if vfile_path.exists():
        vfile_path.unlink()

    if result.returncode != 0:
        print("\nBuild FAILED.", file=sys.stderr)
        sys.exit(result.returncode)

    exe = DIST / (f"{APP_NAME}.exe" if sys.platform == "win32" else APP_NAME)
    print(f"\nBuild successful: {exe}")
    print(f"  size: {exe.stat().st_size / 1_048_576:.1f} MB")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build HandCursor standalone EXE")
    parser.add_argument("--debug", action="store_true",
                        help="Keep console window (useful for diagnosing startup errors)")
    build(**vars(parser.parse_args()))
