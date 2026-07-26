"""
Utility functions for Web Video Extractor
"""
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

def check_ffmpeg_installed() -> str:
    """Find FFmpeg binary across PATH and common installation directories."""
    # 1. Check PATH via shutil
    ffmpeg_bin = shutil.which("ffmpeg.exe") if platform.system() == "Windows" else shutil.which("ffmpeg")
    if ffmpeg_bin and _test_ffmpeg(ffmpeg_bin):
        return ffmpeg_bin

    # 2. Common macOS / Linux locations including user local path
    possible_paths = [
        Path.home() / ".local" / "ffmpeg" / "ffmpeg",
        Path.home() / ".local" / "bin" / "ffmpeg",
        Path("/opt/homebrew/bin/ffmpeg"),
        Path("/usr/local/bin/ffmpeg"),
        Path("/usr/bin/ffmpeg"),
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
        Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe",
    ]

    for p in possible_paths:
        if p.exists() and _test_ffmpeg(str(p)):
            return str(p)

    return ""

def _test_ffmpeg(ffmpeg_path: str) -> bool:
    try:
        res = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=5)
        return res.returncode == 0
    except Exception:
        return False

def sanitize_filename(filename: str, default: str = "video") -> str:
    """Sanitize string to be safe for filenames."""
    if not filename:
        return default
    # Remove invalid filename characters
    s = re.sub(r'[\\/*?:"<>|]', '', filename).strip()
    # Replace multiple spaces/newlines
    s = re.sub(r'\s+', ' ', s)
    return s[:150] if s else default

def format_bytes(size: float) -> str:
    """Format bytes to human readable format."""
    if size <= 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"

def open_folder(folder_path: str) -> bool:
    """Open folder in OS file explorer."""
    if not os.path.exists(folder_path):
        return False
    try:
        if platform.system() == 'Darwin':
            subprocess.run(['open', folder_path], check=True)
        elif platform.system() == 'Windows':
            os.startfile(folder_path)
        else:
            subprocess.run(['xdg-open', folder_path], check=True)
        return True
    except Exception:
        return False
