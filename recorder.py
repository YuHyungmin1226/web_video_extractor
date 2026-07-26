"""
Web Video Recorder Fallback Module
Provides stream capture or screen recording capabilities using FFmpeg.
"""
import os
import subprocess
from typing import Callable, Optional
from config import Config
from utils import check_ffmpeg_installed, sanitize_filename

class StreamRecorder:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.ffmpeg_path = self.config.get("ffmpeg_path") or check_ffmpeg_installed()
        self.process: Optional[subprocess.Popen] = None

    def record_stream(
        self,
        stream_url: str,
        output_filename: str,
        duration_seconds: int = 0,
        referer: str = "",
        status_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """Record live stream or video source directly using FFmpeg."""
        if not self.ffmpeg_path:
            if status_callback:
                status_callback("FFmpeg binary not found for recording.")
            return None

        download_dir = self.config.get_download_path()
        filename = sanitize_filename(output_filename or "stream_capture") + ".mp4"
        final_path = os.path.join(download_dir, filename)

        user_agent = self.config.get("user_agent")
        headers = f"User-Agent: {user_agent}\r\n"
        if referer:
            headers += f"Referer: {referer}\r\n"

        cmd = [
            self.ffmpeg_path, "-y",
            "-headers", headers,
            "-i", stream_url
        ]

        if duration_seconds > 0:
            cmd.extend(["-t", str(duration_seconds)])

        cmd.extend(["-c", "copy", final_path])

        try:
            if status_callback:
                status_callback(f"Recording stream to {final_path}...")
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                if status_callback:
                    status_callback("Stream recording finished successfully!")
                return final_path
            else:
                if status_callback:
                    status_callback(f"FFmpeg recorder failed: {res.stderr[:200]}")
        except Exception as e:
            if status_callback:
                status_callback(f"Stream recording exception: {e}")
        return None
