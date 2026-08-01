"""
Unit tests for VideoDetector module
"""
import pytest
import detector as detector_module
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


def test_detect_all_pages_discovers_later_pagination_block(monkeypatch):
    # Given
    first_page = '<a href="/movie/1">Movie 1</a>' + ''.join(
        f'<a href="?page={page}">{page}</a>' for page in range(2, 11)
    )
    pages = {
        "https://example.com/catalog": first_page,
        "https://example.com/catalog?page=10": (
            '<a href="/movie/10">Movie 10</a>'
            '<a href="?page=11">11</a>'
        ),
        "https://example.com/catalog?page=11": '<a href="/movie/11">Movie 11</a>',
        "https://example.com/movie/1": '<video src="https://cdn.example/1.mp4"></video>',
        "https://example.com/movie/10": '<video src="https://cdn.example/10.mp4"></video>',
        "https://example.com/movie/11": '<video src="https://cdn.example/11.mp4"></video>',
    }
    detector = VideoDetector()
    monkeypatch.setattr(detector_module, "yt_dlp", None)
    monkeypatch.setattr(
        detector,
        "fetch_html_curl",
        lambda url, referer="": pages.get(url, ""),
    )

    # When
    candidates = detector.detect("https://example.com/catalog", max_pages=0)

    # Then
    assert {candidate.url for candidate in candidates} == {
        "https://cdn.example/1.mp4",
        "https://cdn.example/10.mp4",
        "https://cdn.example/11.mp4",
    }


def test_detect_all_pages_ignores_duplicate_pagination_links(monkeypatch):
    # Given
    pages = {
        "https://example.com/catalog": (
            '<a href="/movie/1">Movie 1</a>'
            '<a href="?page=2">2</a>'
            '<a href="?page=2">2 duplicate</a>'
        ),
        "https://example.com/catalog?page=2": (
            '<a href="/movie/2">Movie 2</a>'
            '<a href="/catalog">1</a>'
            '<a href="?page=2">2</a>'
        ),
        "https://example.com/movie/1": '<video src="https://cdn.example/1.mp4"></video>',
        "https://example.com/movie/2": '<video src="https://cdn.example/2.mp4"></video>',
    }
    fetched_urls = []
    detector = VideoDetector()
    monkeypatch.setattr(detector_module, "yt_dlp", None)

    def fetch_html(url, referer=""):
        fetched_urls.append(url)
        return pages.get(url, "")

    monkeypatch.setattr(detector, "fetch_html_curl", fetch_html)

    # When
    candidates = detector.detect("https://example.com/catalog", max_pages=0)

    # Then
    assert {candidate.url for candidate in candidates} == {
        "https://cdn.example/1.mp4",
        "https://cdn.example/2.mp4",
    }
    assert fetched_urls.count("https://example.com/catalog?page=2") == 1


def test_fetch_html_curl_encodes_korean_url_and_referer(monkeypatch):
    # Given: a page URL and referer that both contain raw Korean characters
    captured_cmd = {}

    class FakeResult:
        returncode = 0
        stdout = "<html></html>"

    def fake_run(cmd, **kwargs):
        captured_cmd["cmd"] = cmd
        return FakeResult()

    monkeypatch.setattr(detector_module.subprocess, "run", fake_run)
    detector = VideoDetector()

    # When
    detector.fetch_html_curl(
        "https://example.com/한글경로/영화",
        referer="https://example.com/한글카테고리/목록",
    )

    # Then: every argument passed to curl (including the Referer header) is ASCII
    for arg in captured_cmd["cmd"]:
        assert arg.isascii(), f"non-ASCII curl argument leaked through: {arg!r}"


def test_detect_respects_finite_page_limit(monkeypatch):
    # Given
    pages = {
        "https://example.com/catalog": (
            '<a href="/movie/1">Movie 1</a>'
            '<a href="?page=2">2</a>'
            '<a href="?page=3">3</a>'
        ),
        "https://example.com/catalog?page=2": (
            '<a href="/movie/2">Movie 2</a>'
            '<a href="?page=4">4</a>'
        ),
        "https://example.com/catalog?page=3": '<a href="/movie/3">Movie 3</a>',
        "https://example.com/movie/1": '<video src="https://cdn.example/1.mp4"></video>',
        "https://example.com/movie/2": '<video src="https://cdn.example/2.mp4"></video>',
        "https://example.com/movie/3": '<video src="https://cdn.example/3.mp4"></video>',
    }
    fetched_urls = []
    detector = VideoDetector()
    monkeypatch.setattr(detector_module, "yt_dlp", None)

    def fetch_html(url, referer=""):
        fetched_urls.append(url)
        return pages.get(url, "")

    monkeypatch.setattr(detector, "fetch_html_curl", fetch_html)

    # When
    candidates = detector.detect("https://example.com/catalog", max_pages=2)

    # Then
    assert {candidate.url for candidate in candidates} == {
        "https://cdn.example/1.mp4",
        "https://cdn.example/2.mp4",
    }
    assert "https://example.com/catalog?page=3" not in fetched_urls
