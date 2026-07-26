"""
Unit tests for VideoDetector module
"""
import pytest
from detector import VideoDetector

def test_extract_title():
    detector = VideoDetector()
    html = '''
    <html>
    <head>
        <meta property="og:title" content="Sample &amp; Movie Title &#39;Test&#39; | Site" />
    </head>
    <body></body>
    </html>
    '''
    title = detector._extract_title(html)
    assert title == "Sample & Movie Title 'Test' | Site"


def test_extract_video_tags():
    detector = VideoDetector()
    html = '''
    <div>
        <video class="player" data-source="https://vod.example.com/master.m3u8"></video>
    </div>
    '''
    srcs = detector._extract_video_tags(html, "https://example.com")
    assert len(srcs) == 1
    assert srcs[0] == "https://vod.example.com/master.m3u8"

def test_extract_js_media_urls():
    detector = VideoDetector()
    html = '''
    <script>
        var videoUrl = "https://cdn.example.com/stream/file.m3u8?token=123";
        var backupUrl = "https://cdn.example.com/video.mp4";
    </script>
    '''
    srcs = detector._extract_js_media_urls(html, "https://example.com")
    assert len(srcs) >= 2
    assert "https://cdn.example.com/stream/file.m3u8?token=123" in srcs
    assert "https://cdn.example.com/video.mp4" in srcs

def test_extract_pagination_links():
    detector = VideoDetector()
    html = '''
    <a href="?page=1">1</a>
    <a href="?page=2">2</a>
    <a href="?page=3">3</a>
    '''
    pages = detector._extract_pagination_links(html, "https://mingky05.live/kor")
    assert len(pages) == 3
    assert "https://mingky05.live/kor?page=2" in pages


