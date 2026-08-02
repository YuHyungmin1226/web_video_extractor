"""
Web Video Detection Module
Detects video streams (HLS m3u8, direct MP4, video tags, embedded players) in arbitrary web pages.
"""
import html
import re
import urllib.parse
from typing import Dict, List, Optional

from utils import normalize_url, run_hidden

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


class VideoCandidate:
    def __init__(self, url: str, title: str = "", video_type: str = "direct", referer: str = "", raw_info: Optional[Dict] = None):
        self.url = url
        self.title = title or "Web Video"
        self.video_type = video_type  # 'm3u8', 'direct', 'ytdlp'
        self.referer = referer
        self.raw_info = raw_info or {}

    def __repr__(self):
        return f"<VideoCandidate type={self.video_type} title='{self.title}' url='{self.url[:60]}...'>"


class VideoDetector:
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, user_agent: str = ""):
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT

    def fetch_html_curl(self, url: str, referer: str = "") -> str:
        """Fetch page HTML using curl (supports HTTP/2 and modern TLS signatures)."""
        url = normalize_url(url)
        cmd = [
            "curl", "-f", "-s", "-L",
            "-A", self.user_agent,
            "--max-time", "15"
        ]
        if referer:
            cmd.extend(["-H", f"Referer: {normalize_url(referer)}"])
        cmd.append(url)

        try:
            res = run_hidden(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode == 0:
                return res.stdout
        except Exception:
            pass
        return ""

    def detect(self, page_url: str, max_pages: int = 5) -> List[VideoCandidate]:
        """Detect video sources in given URL with pagination support."""
        page_url = page_url.strip()
        if not page_url:
            return []
        page_url = normalize_url(page_url)

        # 0. Check if input URL itself is a direct media file
        if re.search(r'\.(m3u8|mp4|webm|mkv|flv)(\?.*)?$', page_url, re.IGNORECASE):
            vtype = 'm3u8' if '.m3u8' in page_url.lower() else 'direct'
            return [VideoCandidate(url=page_url, title="Direct Media Stream", video_type=vtype, referer=page_url)]

        candidates: List[VideoCandidate] = []

        # 1. First, check yt-dlp native extraction (for Youtube, Pornhub, Vimeo, etc.)
        if yt_dlp is not None:
            try:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'logger': None,
                    'extract_flat': False,
                    'skip_download': True,
                    'http_headers': {
                        'User-Agent': self.user_agent,
                        'Referer': page_url
                    }
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(page_url, download=False)
                    if info and not info.get('_type') == 'url_transparent':
                        extractor = info.get('extractor_key', '').lower()
                        if extractor not in ('generic', ''):
                            title = info.get('title') or "Video"
                            candidates.append(VideoCandidate(
                                url=page_url,
                                title=title,
                                video_type="ytdlp",
                                referer=page_url,
                                raw_info=info
                            ))
                            return candidates
            except Exception:
                pass


        # 2. HTML Web Parsing for arbitrary web pages (like mingky05)
        html = self.fetch_html_curl(page_url)
        if not html:
            return candidates

        # Parse page title
        title = self._extract_title(html) or "Web Video"

        # A. Look for video tags & data attributes (data-source, src, data-url)
        video_srcs = self._extract_video_tags(html, page_url)
        for src in video_srcs:
            vtype = 'm3u8' if '.m3u8' in src.lower() else 'direct'
            candidates.append(VideoCandidate(url=src, title=title, video_type=vtype, referer=page_url))

        # B. Look for JavaScript inline m3u8/mp4 URLs
        js_srcs = self._extract_js_media_urls(html, page_url)
        for src in js_srcs:
            if not any(c.url == src for c in candidates):
                vtype = 'm3u8' if '.m3u8' in src.lower() else 'direct'
                candidates.append(VideoCandidate(url=src, title=title, video_type=vtype, referer=page_url))

        # C. Look for embedded iframes (recursive 1 level)
        iframes = self._extract_iframe_urls(html, page_url)
        for iframe_url in iframes:
            iframe_html = self.fetch_html_curl(iframe_url, referer=page_url)
            if iframe_html:
                iframe_title = self._extract_title(iframe_html) or title
                for src in self._extract_video_tags(iframe_html, iframe_url):
                    if not any(c.url == src for c in candidates):
                        vtype = 'm3u8' if '.m3u8' in src.lower() else 'direct'
                        candidates.append(VideoCandidate(url=src, title=iframe_title, video_type=vtype, referer=page_url))
                for src in self._extract_js_media_urls(iframe_html, iframe_url):
                    if not any(c.url == src for c in candidates):
                        vtype = 'm3u8' if '.m3u8' in src.lower() else 'direct'
                        candidates.append(VideoCandidate(url=src, title=iframe_title, video_type=vtype, referer=page_url))

        # D. Category / List Page Check: Multi-page pagination traversal
        movie_links = self._extract_movie_page_links(html, page_url)
        
        # If pagination is allowed and this is a list page, find pagination pages
        if movie_links and (max_pages == 0 or max_pages > 1):
            pagination_pages = self._extract_pagination_links(html, page_url)
            visited_pages = {page_url, page_url.rstrip('/') + '?page=1', page_url.rstrip('/') + '/?page=1'}
            queued_pages = set(pagination_pages)
            
            pages_fetched = 1
            page_index = 0
            while page_index < len(pagination_pages):
                if max_pages > 0 and pages_fetched >= max_pages:
                    break
                page_link = pagination_pages[page_index]
                page_index += 1
                if page_link in visited_pages:
                    continue
                visited_pages.add(page_link)
                pages_fetched += 1
                p_html = self.fetch_html_curl(page_link, referer=page_url)
                if p_html:
                    for next_page in self._extract_pagination_links(p_html, page_link):
                        if next_page not in visited_pages and next_page not in queued_pages:
                            pagination_pages.append(next_page)
                            queued_pages.add(next_page)
                    extra_movies = self._extract_movie_page_links(p_html, page_link)
                    for m_link in extra_movies:
                        if m_link not in movie_links:
                            movie_links.append(m_link)


        # Process all collected movie links across all pagination pages
        if movie_links:
            for child_url in movie_links:
                if child_url == page_url or any(c.referer == child_url for c in candidates):
                    continue
                child_html = self.fetch_html_curl(child_url, referer=page_url)
                if child_html:
                    child_title = self._extract_title(child_html) or "Video"
                    c_srcs = self._extract_video_tags(child_html, child_url) + self._extract_js_media_urls(child_html, child_url)
                    for src in c_srcs:
                        if not any(c.url == src for c in candidates):
                            vtype = 'm3u8' if '.m3u8' in src.lower() else 'direct'
                            candidates.append(VideoCandidate(url=src, title=child_title, video_type=vtype, referer=child_url))

        return candidates

    def _extract_movie_page_links(self, html: str, base_url: str) -> List[str]:
        results = []
        patterns = [
            r'href=["\']([^"\']*/movie/[^"\']+)["\']',
            r'href=["\']([^"\']*/video/[^"\']+)["\']',
            r'href=["\']([^"\']*/watch\?[^"\']+)["\']'
        ]
        for pattern in patterns:
            for m in re.finditer(pattern, html, re.IGNORECASE):
                href = m.group(1).strip()
                if href and not href.endswith('.css') and not href.endswith('.js'):
                    full_url = urllib.parse.urljoin(base_url, href)
                    if full_url not in results:
                        results.append(full_url)
        return results

    def _extract_pagination_links(self, html: str, base_url: str) -> List[str]:
        results = []
        for m in re.finditer(r'href=["\']([^"\']*[?&]page=\d+[^"\']*)["\']', html, re.IGNORECASE):
            href = m.group(1).strip()
            if href and not href.startswith('javascript:'):
                full_url = urllib.parse.urljoin(base_url, href)
                if full_url not in results and not re.search(r'/movie/', full_url):
                    results.append(full_url)
        return results

    def _extract_title(self, raw_html: str) -> str:
        raw_title = ""
        # og:title
        m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', raw_html, re.IGNORECASE)
        if not m:
            m = re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:title["\']', raw_html, re.IGNORECASE)
        if m:
            raw_title = m.group(1).strip()
        else:
            # <title>
            m = re.search(r'<title[^>]*>(.*?)</title>', raw_html, re.IGNORECASE | re.DOTALL)
            if m:
                raw_title = re.sub(r'\s+', ' ', m.group(1)).strip()

        return html.unescape(raw_title) if raw_title else ""

    def _extract_video_tags(self, raw_html: str, base_url: str) -> List[str]:
        results = []
        # video, source tags
        patterns = [
            r'<(?:video|source)[^>]+(?:data-source|src)=["\']([^"\']+)["\']',
            r'data-source=["\']([^"\']+)["\']',
            r'data-url=["\']([^"\']+)["\']',
            r'meta\s+property=["\']og:video(?::url)?["\']\s+content=["\']([^"\']+)["\']'
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, raw_html, re.IGNORECASE):
                url = html.unescape(match.group(1).strip())
                if url and not url.startswith('blob:') and not url.startswith('data:'):
                    full_url = urllib.parse.urljoin(base_url, url)
                    if full_url not in results:
                        results.append(full_url)
        return results


    def _extract_js_media_urls(self, html: str, base_url: str) -> List[str]:
        results = []
        matches = re.findall(r'https?://[^\s\'\"\<\>]+?\.(?:m3u8|mp4)[^\s\'\"\<\>]*', html, re.IGNORECASE)
        for url in matches:
            full_url = urllib.parse.urljoin(base_url, url)
            if full_url not in results:
                results.append(full_url)
        return results

    def _extract_iframe_urls(self, html: str, base_url: str) -> List[str]:
        results = []
        for m in re.finditer(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE):
            src = m.group(1).strip()
            if src and not src.startswith('javascript:') and 'googletagmanager' not in src:
                full_url = urllib.parse.urljoin(base_url, src)
                if full_url not in results:
                    results.append(full_url)
        return results
