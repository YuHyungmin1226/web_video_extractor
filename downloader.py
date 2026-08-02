"""
Web Video Downloader Module
Supports yt-dlp native downloads, multi-threaded HLS (m3u8) downloads via curl+ffmpeg, and direct MP4 downloads.
"""
import concurrent.futures
import os
import re
import shutil
import tempfile
import urllib.parse
from typing import Callable, List, Optional

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


from config import Config
from detector import VideoCandidate
from utils import check_ffmpeg_installed, normalize_url, run_hidden, sanitize_filename

class VideoDownloader:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.ffmpeg_path = self.config.get("ffmpeg_path") or check_ffmpeg_installed()

    def download(
        self,
        candidate: VideoCandidate,
        output_filename: str = "",
        status_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Optional[str]:
        """Download video candidate and return final file path if successful."""

        download_dir = self.config.get_download_path()
        filename = sanitize_filename(output_filename or candidate.title or "downloaded_video")
        if not filename.endswith(".mp4"):
            filename += ".mp4"

        final_path = os.path.join(download_dir, filename)

        def log(msg: str):
            if status_callback:
                status_callback(msg)

        def progress(p: float):
            if progress_callback:
                progress_callback(p)

        # Skip download if destination file already exists
        if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
            log(f"⏩ File already exists, skipping download: {final_path}")
            progress(100.0)
            return final_path

        log(f"Starting download: {candidate.title}")
        log(f"Stream type: {candidate.video_type}")
        log(f"Output target: {final_path}")


        if candidate.video_type == "ytdlp":
            return self._download_ytdlp(candidate, final_path, log, progress)
        elif candidate.video_type == "m3u8":
            return self._download_hls_m3u8(candidate, final_path, log, progress)
        else:
            return self._download_direct(candidate, final_path, log, progress)

    def download_batch(
        self,
        candidates: List[VideoCandidate],
        status_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> List[str]:
        """Download multiple video candidates sequentially."""
        saved_files = []
        total = len(candidates)
        if total == 0:
            return saved_files

        for i, candidate in enumerate(candidates, 1):
            if status_callback:
                status_callback(f"\n--- Batch Download [{i}/{total}]: {candidate.title} ---")

            def single_progress(pct: float):
                if progress_callback:
                    overall = ((i - 1 + pct / 100.0) / total) * 100.0
                    progress_callback(overall)

            path = self.download(
                candidate,
                output_filename=candidate.title,
                status_callback=status_callback,
                progress_callback=single_progress
            )

            if path and os.path.exists(path):
                saved_files.append(path)

        if progress_callback:
            progress_callback(100.0)
        return saved_files


    def _download_ytdlp(self, candidate: VideoCandidate, final_path: str, log, progress) -> Optional[str]:
        if yt_dlp is None:
            log("yt-dlp is not installed in the current Python environment.")
            return None
        output_template = final_path.rsplit('.', 1)[0] + '.%(ext)s'
        url = normalize_url(candidate.url)
        referer = normalize_url(candidate.referer or candidate.url)

        ydl_opts = {
            'outtmpl': output_template,
            'merge_output_format': 'mp4',
            'format': 'bestvideo*+bestaudio/best',
            'ffmpeg_location': self.ffmpeg_path or None,
            'quiet': True,
            'http_headers': {
                'User-Agent': self.config.get("user_agent"),
                'Referer': referer
            }
        }

        def hook(d):
            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                if total > 0:
                    pct = (downloaded / total) * 100.0
                    progress(pct)

        ydl_opts['progress_hooks'] = [hook]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            progress(100.0)
            log("Download completed successfully!")
            return final_path
        except Exception as e:
            log(f"yt-dlp download failed: {e}")
            return None

    def _parse_hls_segments(self, content: str):
        """Parse an HLS media playlist into (init_segment, segments).

        Each is {'uri': str, 'range': (offset, length) | None}. Handles
        #EXT-X-MAP (fMP4 init segment, RFC 8216 4.3.2.4) and
        #EXT-X-BYTERANGE (segments sharing one physical file via byte
        offsets, RFC 8216 4.3.2.2) in addition to plain per-segment URIs.
        """
        init_segment = None
        segments = []
        pending_range = None
        last_range_end = {}

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('#EXT-X-MAP'):
                m = re.search(r'URI="([^"]+)"', line)
                if m:
                    uri = m.group(1)
                    rng = None
                    rm = re.search(r'BYTERANGE="(\d+)@(\d+)"', line)
                    if rm:
                        rng = (int(rm.group(2)), int(rm.group(1)))
                    init_segment = {'uri': uri, 'range': rng}
                continue
            if line.startswith('#EXT-X-BYTERANGE'):
                value = line.split(':', 1)[1] if ':' in line else ''
                if '@' in value:
                    length_s, offset_s = value.split('@', 1)
                    pending_range = (int(offset_s), int(length_s))
                elif value.strip():
                    # Offset omitted: per spec, defaults to the byte
                    # immediately following the previous range on this URI.
                    pending_range = (None, int(value))
                continue
            if line.startswith('#'):
                continue

            uri = line
            if pending_range is not None:
                offset, length = pending_range
                if offset is None:
                    offset = last_range_end.get(uri, 0)
                last_range_end[uri] = offset + length
                segments.append({'uri': uri, 'range': (offset, length)})
                pending_range = None
            else:
                segments.append({'uri': uri, 'range': None})

        return init_segment, segments

    def _download_hls_m3u8(self, candidate: VideoCandidate, final_path: str, log, progress) -> Optional[str]:
        referer = normalize_url(candidate.referer or candidate.url)
        candidate_url = normalize_url(candidate.url)
        user_agent = self.config.get("user_agent")
        max_threads = int(self.config.get("threads", 8))

        log("Fetching HLS playlist...")
        # 1. Fetch main m3u8 using curl
        curl_cmd = [
            "curl", "-f", "-s", "-L",
            "-A", user_agent,
            "-H", f"Referer: {referer}",
            candidate_url
        ]
        try:
            res = run_hidden(curl_cmd, capture_output=True, text=True, timeout=15)
            if res.returncode != 0 or not res.stdout.strip():
                log("Failed to fetch m3u8 playlist.")
                return None
            m3u8_content = res.stdout
        except Exception as e:
            log(f"Error fetching playlist: {e}")
            return None

        # 2. Check if master playlist containing variant stream playlists
        base_url = candidate_url.rsplit('/', 1)[0] + '/'
        lines = [line.strip() for line in m3u8_content.splitlines() if line.strip()]

        # Check for sub-playlists (.m3u8)
        sub_playlists = [line for line in lines if not line.startswith('#') and '.m3u8' in line.lower()]
        if sub_playlists:
            target_sub = normalize_url(urllib.parse.urljoin(base_url, sub_playlists[-1])) # take highest resolution variant
            log(f"Resolved variant sub-playlist: {target_sub}")
            res2 = run_hidden([
                "curl", "-f", "-s", "-L", "-A", user_agent, "-H", f"Referer: {referer}", target_sub
            ], capture_output=True, text=True, timeout=15)
            if res2.returncode == 0 and res2.stdout.strip():
                m3u8_content = res2.stdout
                base_url = target_sub.rsplit('/', 1)[0] + '/'

        # 3. Extract segment URLs. fMP4/CMAF playlists often multiplex all
        # segments into one physical file addressed by #EXT-X-BYTERANGE, and
        # reference a shared init segment (moov/ftyp) via #EXT-X-MAP instead
        # of an inline URL, so both need explicit parsing rather than just
        # collecting non-'#' lines.
        init_segment, segments = self._parse_hls_segments(m3u8_content)
        if not segments:
            log("No valid media segments found in playlist.")
            return None

        total_segments = len(segments)
        is_byte_range_stream = init_segment is not None or any(s['range'] for s in segments)
        log(f"Total media segments to download: {total_segments}")

        # 4. Multi-threaded segment downloader into temp directory
        temp_dir = tempfile.mkdtemp(prefix="web_video_hls_")

        init_path = None
        if init_segment:
            init_url = normalize_url(urllib.parse.urljoin(base_url, init_segment['uri']))
            init_path = os.path.join(temp_dir, "init_seg")
            init_cmd = ["curl", "-f", "-s", "-L", "-A", user_agent, "-H", f"Referer: {referer}"]
            if init_segment['range']:
                offset, length = init_segment['range']
                init_cmd += ["--range", f"{offset}-{offset + length - 1}"]
            init_cmd += ["-o", init_path, init_url]
            run_hidden(init_cmd, check=False)
            if not (os.path.exists(init_path) and os.path.getsize(init_path) > 0):
                log("Failed to fetch fMP4 init segment.")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None

        ts_files = [None] * total_segments
        completed_count = 0
        import threading
        progress_lock = threading.Lock()

        def download_segment(idx: int, seg: dict):
            nonlocal completed_count
            seg_url = normalize_url(urllib.parse.urljoin(base_url, seg['uri']))
            out_ts = os.path.join(temp_dir, f"seg_{idx:05d}.ts")

            cmd = [
                "curl", "-f", "-s", "-L",
                "-A", user_agent,
                "-H", f"Referer: {referer}",
                "--retry", "3",
                "--max-time", "30",
            ]
            if seg['range']:
                offset, length = seg['range']
                cmd += ["--range", f"{offset}-{offset + length - 1}"]
            cmd += ["-o", out_ts, seg_url]
            run_hidden(cmd, check=False)
            if os.path.exists(out_ts) and os.path.getsize(out_ts) > 0:
                ts_files[idx] = out_ts
                with progress_lock:
                    completed_count += 1
                    current = completed_count
                progress((current / total_segments) * 95.0)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = [executor.submit(download_segment, i, seg) for i, seg in enumerate(segments)]
            concurrent.futures.wait(futures)

        valid_ts = [f for f in ts_files if f and os.path.exists(f)]
        log(f"Successfully downloaded {len(valid_ts)} / {total_segments} segments.")

        if not valid_ts:
            log("Download failed: No segments were saved.")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

        log("Stitching video segments...")

        if is_byte_range_stream:
            # CMAF fragments pulled out by byte range are raw moof+mdat
            # boxes, not independently decodable files, so ffmpeg's -f
            # concat demuxer (which expects each listed input to already be
            # a valid container) can't join them — it silently produced a
            # corrupt/wildly-wrong-duration output when tried. Appending
            # their bytes directly after the shared init segment (ftyp+moov)
            # is how CMAF fragments are designed to be joined in the first
            # place, and reconstructs a single valid fragmented MP4.
            try:
                with open(final_path, "wb") as outfile:
                    if init_path and os.path.exists(init_path):
                        with open(init_path, "rb") as f:
                            outfile.write(f.read())
                    for ts in valid_ts:
                        with open(ts, "rb") as infile:
                            outfile.write(infile.read())
                progress(100.0)
                log("fMP4 segment concatenation complete!")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return final_path
            except Exception as e:
                log(f"Concat failed: {e}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None

        # 5. Concatenate segments using FFmpeg or raw file join
        if not self.ffmpeg_path:
            self.ffmpeg_path = check_ffmpeg_installed()

        if self.ffmpeg_path:
            concat_list = os.path.join(temp_dir, "concat.txt")
            with open(concat_list, "w", encoding="utf-8") as f:
                for ts in valid_ts:
                    safe_ts = ts.replace("'", "'\\''")
                    f.write(f"file '{safe_ts}'\n")


            ff_cmd = [
                self.ffmpeg_path, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list,
                "-c", "copy",
                final_path
            ]
            res = run_hidden(ff_cmd, capture_output=True, text=True)
            if res.returncode == 0 and os.path.exists(final_path):
                progress(100.0)
                log("Concatenation complete! Video saved successfully.")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return final_path
            else:
                log(f"FFmpeg concat warning: {res.stderr[:200]}")

        # Fallback binary concat if ffmpeg is missing or failed
        log("Using direct stream concatenation fallback...")
        try:
            with open(final_path, "wb") as outfile:
                for ts in valid_ts:
                    with open(ts, "rb") as infile:
                        outfile.write(infile.read())
            progress(100.0)
            log("Fallback concatenation complete!")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return final_path
        except Exception as e:
            log(f"Concat failed: {e}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

    def _download_direct(self, candidate: VideoCandidate, final_path: str, log, progress) -> Optional[str]:
        referer = normalize_url(candidate.referer or candidate.url)
        url = normalize_url(candidate.url)
        user_agent = self.config.get("user_agent")

        cmd = [
            "curl", "-f", "-L",
            "-A", user_agent,
            "-H", f"Referer: {referer}",
            "-o", final_path,
            url
        ]

        try:
            log("Downloading direct media file via curl...")
            res = run_hidden(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0 and os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                progress(100.0)
                log("Direct download completed!")
                return final_path
        except Exception as e:
            log(f"Direct download error: {e}")
        return None
