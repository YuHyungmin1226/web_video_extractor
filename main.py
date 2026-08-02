"""
Web Video Extractor & Downloader Main Entry Point
Supports both CLI mode and GUI mode.
"""
import argparse
import subprocess
from pathlib import Path
import sys

# Auto-re-exec using local .venv if available and dependencies are missing in global python.
# venv layout differs by OS: Windows uses "Scripts\\python.exe", macOS/Linux use "bin/python".
_venv_dir = Path(__file__).parent / ".venv"
venv_py = _venv_dir / "Scripts" / "python.exe" if sys.platform == "win32" else _venv_dir / "bin" / "python"
if venv_py.exists():
    try:
        import PySide6
        import yt_dlp
    except ImportError:
        if Path(sys.executable).resolve() != venv_py.resolve():
            # subprocess+exit (rather than os.execv) behaves identically across
            # Windows/macOS/Linux and avoids platform-specific process-replacement quirks.
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
        main_gui()



if __name__ == "__main__":
    main()

