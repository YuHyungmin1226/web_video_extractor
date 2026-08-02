"""
Web Video Extractor & Downloader Main Entry Point
Supports both CLI mode and GUI mode.
"""
import argparse
import os
import subprocess
from pathlib import Path
import sys

# Auto-re-exec using local .venv if available and dependencies are missing in global python.
# venv layout differs by OS: Windows uses "Scripts\\python.exe", macOS/Linux use "bin/python".
# Skipped entirely in a PyInstaller build (sys.frozen): a frozen build carries its
# own bundled interpreter and dependencies, and the extraction directory next to
# it has no ".venv" of its own to relaunch into.
#
# Loop guard: an env var sentinel, not a sys.executable/venv_py path comparison.
# venv's python is typically a symlink back to the base interpreter (this is the
# default on macOS framework builds and plain `python3 -m venv`), so resolving
# symlinks on both sides makes them compare equal even when NOT already running
# under the venv, which silently skips the re-exec entirely.
_venv_dir = Path(__file__).resolve().parent / ".venv"
venv_py = _venv_dir / "Scripts" / "python.exe" if sys.platform == "win32" else _venv_dir / "bin" / "python"
if not getattr(sys, "frozen", False) and venv_py.exists() and not os.environ.get("_WVE_VENV_REEXEC"):
    try:
        import PySide6
        import yt_dlp
    except ImportError:
        # subprocess+exit (rather than os.execv) behaves identically across
        # Windows/macOS/Linux and avoids platform-specific process-replacement quirks.
        os.environ["_WVE_VENV_REEXEC"] = "1"
        sys.exit(subprocess.run([str(venv_py)] + sys.argv).returncode)

from detector import VideoDetector
from downloader import VideoDownloader
from gui import main_gui
from utils import check_curl_installed, check_ffmpeg_installed



def run_cli(url: str, output: str = "", download_all: bool = False, max_pages: int = 5):
    print(f"=== Web Video Extractor CLI ===")
    print(f"Target URL: {url}")
    print(f"Max pages to crawl: {max_pages if max_pages > 0 else 'All'}")

    if not check_curl_installed():
        print("⚠️ Warning: curl not found on PATH. Generic page scraping, HLS, and direct MP4 downloads will fail (yt-dlp-supported sites like YouTube are unaffected).")

    ff = check_ffmpeg_installed()
    if ff:
        print(f"FFmpeg binary detected: {ff}")
    else:
        print("⚠️ Warning: FFmpeg not detected in system. Will fallback to stream concatenation.")

    print("\nDetecting video streams on page...")
    detector = VideoDetector()
    candidates = detector.detect(url, max_pages=max_pages)

    if not candidates:
        print("❌ No downloadable videos detected on the page.")
        sys.exit(1)

    print(f"✅ Detected {len(candidates)} video candidate(s):")
    for idx, c in enumerate(candidates, 1):
        print(f" [{idx}] {c.title} (Type: {c.video_type}) -> {c.url[:60]}...")

    downloader = VideoDownloader()

    def status_cb(msg):
        print(f"[STATUS] {msg}")

    def progress_cb(pct):
        print(f"[PROGRESS] {pct:.1f}%", end="\r", flush=True)

    if download_all or len(candidates) > 1:
        print(f"\n🚀 Starting batch download for {len(candidates)} video(s)...")
        saved_files = downloader.download_batch(
            candidates,
            status_callback=status_cb,
            progress_callback=progress_cb
        )
        print(f"\n🎉 Batch download complete! Total {len(saved_files)} video(s) saved.")
    else:
        selected = candidates[0]
        print(f"\nStarting download for stream [1]: {selected.title}")
        result_path = downloader.download(
            selected,
            output_filename=output,
            status_callback=status_cb,
            progress_callback=progress_cb
        )
        if result_path:
            print(f"\n🎉 Download successful! Saved file: {result_path}")
        else:
            print("\n❌ Download failed.")
            sys.exit(1)


def _hide_windows_console_if_frozen() -> None:
    """The packaged Windows build keeps a console subsystem (so --cli prints
    normally when run from a terminal/script), but that leaves a console box
    behind the GUI when double-clicked into GUI mode. Hide it in that case.

    No-op in dev mode: `python main.py` runs inside the user's own terminal,
    which must never be hidden. No-op on macOS/Linux: ctypes.windll only
    exists on Windows, and neither has this console/GUI split in the first
    place (see build.py for why only Windows needs a console subsystem)."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    import ctypes
    console_wnd = ctypes.windll.kernel32.GetConsoleWindow()
    if console_wnd:
        ctypes.windll.user32.ShowWindow(console_wnd, 0)  # SW_HIDE


def main():
    parser = argparse.ArgumentParser(description="Web Video Extractor & Downloader")
    parser.add_argument("--url", type=str, help="Web page URL to extract and download video from")
    parser.add_argument("--output", type=str, default="", help="Output filename for downloaded video")
    parser.add_argument("--max-pages", type=int, default=5, help="Max category pages to crawl (0 = unlimited)")
    parser.add_argument("--all", action="store_true", help="Download all detected videos on category/list page")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")

    args = parser.parse_args()

    if args.cli or args.url:
        if not args.url:
            print("Error: --url parameter is required in CLI mode.")
            sys.exit(1)
        run_cli(args.url, args.output, download_all=args.all, max_pages=args.max_pages)
    else:
        _hide_windows_console_if_frozen()
        main_gui()



if __name__ == "__main__":
    main()

