"""
Unit tests for VideoDownloader & Utils
"""
import shutil

import pytest
from utils import sanitize_filename, format_bytes, check_ffmpeg_installed, check_curl_installed, normalize_url
from config import Config

def test_normalize_url_encodes_korean_path_and_query():
    url = normalize_url("https://example.com/한글경로/영화?제목=테스트")
    assert url == "https://example.com/%ED%95%9C%EA%B8%80%EA%B2%BD%EB%A1%9C/%EC%98%81%ED%99%94?%EC%A0%9C%EB%AA%A9=%ED%85%8C%EC%8A%A4%ED%8A%B8"
    assert url.isascii()

def test_normalize_url_encodes_korean_hostname_as_idna():
    url = normalize_url("http://한글사이트.com/영화")
    assert url.startswith("http://xn--")
    assert url.isascii()

def test_normalize_url_is_idempotent_on_already_encoded_url():
    url = "https://example.com/%ED%95%9C%EA%B8%80?a=1"
    assert normalize_url(url) == url

def test_normalize_url_leaves_ascii_url_unchanged():
    url = "https://example.com/movie/1?page=2"
    assert normalize_url(url) == url

def test_normalize_url_empty_string():
    assert normalize_url("") == ""

def test_sanitize_filename():
    raw = "Invalid / File : Name * With ? Special < Characters > |"
    clean = sanitize_filename(raw)
    assert "/" not in clean
    assert ":" not in clean
    assert "*" not in clean
    assert "<" not in clean

def test_sanitize_filename_strips_trailing_dots_and_spaces():
    # Windows silently drops trailing dots/spaces when creating the file, so
    # the sanitized name returned here must already match what lands on disk.
    assert sanitize_filename("My Video...  ") == "My Video"

def test_sanitize_filename_escapes_windows_reserved_device_names():
    # "CON", "PRN", "COM1", etc. are reserved on Windows even with an
    # extension appended later (e.g. "CON.mp4" fails to create).
    assert sanitize_filename("CON") == "_CON"
    assert sanitize_filename("com3") == "_com3"
    assert sanitize_filename("Console") == "Console"

def test_format_bytes():
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1048576) == "1.0 MB"
    assert format_bytes(1073741824) == "1.0 GB"

def test_check_curl_installed():
    assert isinstance(check_curl_installed(), bool)

def test_check_ffmpeg_installed():
    ff = check_ffmpeg_installed()
    assert isinstance(ff, str)
    # Only assert a path was found when ffmpeg is actually on this machine's
    # PATH — this test must not assume any particular dev machine's setup.
    if shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"):
        assert len(ff) > 0

def test_download_skip_existing(tmp_path):
    from downloader import VideoDownloader
    from detector import VideoCandidate
    import os

    cfg = Config()
    # Config always persists to ~/.web_video_extractor_config.json; redirect
    # it to a throwaway file so this test doesn't overwrite the real user
    # config's download_path with this test's tmp_path (which is deleted
    # once the test run ends, silently breaking the actual app afterward).
    cfg.config_file = tmp_path / "test_config.json"
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

