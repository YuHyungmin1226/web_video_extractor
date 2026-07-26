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

def test_download_skip_existing(tmp_path):
    from downloader import VideoDownloader
    from detector import VideoCandidate
    import os

    cfg = Config()
    cfg.set("download_path", str(tmp_path))
    downloader = VideoDownloader(config=cfg)

    # Create dummy existing file
    existing_file = tmp_path / "existing_video.mp4"
    existing_file.write_bytes(b"dummy data")

    cand = VideoCandidate(url="https://example.com/stream.m3u8", title="existing_video", video_type="m3u8")
    
    logs = []
    res = downloader.download(cand, output_filename="existing_video", status_callback=lambda m: logs.append(m))
    
    assert res == str(existing_file)
    assert any("already exists" in log for log in logs)

