"""
Unit tests for VideoDownloader & Utils
"""
import pytest
from utils import sanitize_filename, format_bytes, check_ffmpeg_installed
from config import Config

def test_sanitize_filename():
    raw = "Invalid / File : Name * With ? Special < Characters > |"
    clean = sanitize_filename(raw)
    assert "/" not in clean
    assert ":" not in clean
    assert "*" not in clean
    assert "<" not in clean

def test_format_bytes():
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1048576) == "1.0 MB"
    assert format_bytes(1073741824) == "1.0 GB"

def test_check_ffmpeg_installed():
    ff = check_ffmpeg_installed()
    # On this machine, FFmpeg is at /Users/yhm/.local/ffmpeg/ffmpeg
    assert isinstance(ff, str)
    assert len(ff) > 0
