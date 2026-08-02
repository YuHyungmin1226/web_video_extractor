"""
Build script for Web Video Extractor & Downloader.

Produces a standalone executable (Windows), a .app bundle (macOS), or a
standalone binary (Linux) with PyInstaller. Run from the project root:

    python build.py

This app is dual-mode (GUI by default, `--cli` for scripted/terminal use),
which is why its packaging differs from a GUI-only app in one important way
on Windows — see the IS_WINDOWS branch below.

curl and ffmpeg are NOT bundled: they're expected to already be on the
target machine's PATH (see README.md's per-OS prerequisites table), the
same way MinimalPlayer expects libmpv to be system-installed on Linux.
"""
import os
import sys

import PyInstaller.__main__

from utils import IS_LINUX, IS_MAC, IS_WINDOWS

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ENTRY_POINT = os.path.join(PROJECT_DIR, "main.py")
APP_NAME = "WebVideoExtractor"
BUNDLE_IDENTIFIER = "com.yuhyungmin.webvideoextractor"


def build(dist_dir: str = "dist", work_dir: str = "build", spec_dir: str = "."):
    print(f"Starting build for {APP_NAME} on {sys.platform}...")

    for directory in (dist_dir, work_dir, spec_dir):
        os.makedirs(directory, exist_ok=True)

    params = [
        ENTRY_POINT,
        "--name=" + APP_NAME,
        "--noconfirm",
        "--clean",
        "--distpath=" + dist_dir,
        "--workpath=" + work_dir,
        "--specpath=" + spec_dir,
    ]

    # PyInstaller uses ';' as the add-data/add-binary separator on Windows and ':' elsewhere.
    sep = ";" if IS_WINDOWS else ":"

    icon_png = os.path.join(PROJECT_DIR, "icon.png")
    icon_ico = os.path.join(PROJECT_DIR, "icon.ico")
    icon_icns = os.path.join(PROJECT_DIR, "icon.icns")
    if os.path.exists(icon_png):
        # Bundled so gui.py's _resolve_icon_path() can find it next to the
        # frozen executable (or in _MEIPASS) and set the window icon.
        params.append(f"--add-data={icon_png}{sep}.")

    if IS_WINDOWS and os.path.exists(icon_ico):
        params.append("--icon=" + icon_ico)
    elif IS_MAC and os.path.exists(icon_icns):
        params.append("--icon=" + icon_icns)
    else:
        print("Note: no icon.ico/icon.icns found in the project root — building without a custom icon.")

    if IS_WINDOWS:
        # Deliberately NOT --windowed here. This app supports `--cli` for
        # scripted/terminal use, and a --windowed (GUI-subsystem) Windows
        # executable has no console at all — print() output would simply
        # vanish, breaking --cli entirely. Keeping the default console
        # subsystem means --cli works normally from a terminal or script;
        # main.py's _hide_windows_console_if_frozen() hides the console
        # window itself when the *GUI* path is launched instead, so
        # double-clicking the .exe doesn't leave a console box on screen.
        # (macOS/Linux don't have this GUI/console subsystem split at the
        # executable level, so neither needs an equivalent.)
        params.append("--onefile")
    elif IS_MAC:
        # --windowed on macOS builds a proper .app bundle (BUNDLE step) with
        # no Dock/menu-bar-less console flicker on double-click. Unlike
        # Windows, this does NOT remove the ability to run the bundle's
        # executable directly from Terminal with --cli and see stdout —
        # macOS has no separate GUI/console executable subsystem, so the
        # same binary works both ways. Using onedir (the default, not
        # --onefile) avoids onefile's temp-dir self-extraction, which
        # complicates code-signing/notarization for later distribution.
        params.append("--windowed")
        params.append("--osx-bundle-identifier=" + BUNDLE_IDENTIFIER)
    else:  # Linux
        # PyInstaller ignores --windowed on Linux (no subsystem concept
        # there), so there's nothing OS-specific to add beyond --onefile
        # for a single portable binary.
        params.append("--onefile")

    PyInstaller.__main__.run(params)

    if IS_MAC:
        app_path = os.path.join(dist_dir, f"{APP_NAME}.app")
        print(f"\nBuild complete! Check '{app_path}'.")
    else:
        out = os.path.join(dist_dir, APP_NAME)
        if IS_WINDOWS:
            out += ".exe"
        print(f"\nBuild complete! Check '{out}'.")
        if IS_LINUX:
            print("Note: this build expects curl and ffmpeg to be installed on the target machine (see README.md).")


if __name__ == "__main__":
    build()
