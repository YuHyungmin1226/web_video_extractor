"""
Utility functions for Web Video Extractor
"""
import os
import platform
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path

_URL_SAFE_CHARS = "/%:@!$&'()*+,;=~-._"


def normalize_url(url: str) -> str:
    """Convert a URL that may contain raw Unicode (e.g. a Korean hostname
    or path/query typed or pasted by the user) into a fully ASCII URL
    safe to use as a curl argument or in an HTTP header value.

    curl auto-encodes non-ASCII characters in the *target* URL on modern
    versions, but it never encodes header values (e.g. `-H "Referer: ..."`),
    so a raw Unicode referer is sent as literal UTF-8 bytes. That violates
    RFC 7230 and gets silently rejected (400/403) by strict servers and
    WAFs such as Cloudflare. Normalizing every URL before it is used keeps
    behavior consistent regardless of curl version or where the URL is used.
    """
    if not url:
        return url
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return url

    netloc = parts.netloc
    if netloc:
        try:
            netloc.encode("ascii")
        except UnicodeEncodeError:
            userinfo, _, hostport = netloc.rpartition("@")
            host, _, port = hostport.partition(":")
            try:
                host = host.encode("idna").decode("ascii")
            except UnicodeError:
                host = urllib.parse.quote(host)
            netloc = f"{host}:{port}" if port else host
            if userinfo:
                netloc = f"{userinfo}@{netloc}"

    path = urllib.parse.quote(parts.path, safe=_URL_SAFE_CHARS)
    query = urllib.parse.quote(parts.query, safe=_URL_SAFE_CHARS + "?")
    fragment = urllib.parse.quote(parts.fragment, safe=_URL_SAFE_CHARS + "?")

    return urllib.parse.urlunsplit((parts.scheme, netloc, path, query, fragment))

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
