"""
Web Video Extractor Config Module
"""
import json
import os
from pathlib import Path
import platform

class Config:
    def __init__(self):
        if platform.system() == "Windows":
            self.config_file = Path.home() / "web_video_extractor_config.json"
        else:
            self.config_file = Path.home() / ".web_video_extractor_config.json"
            
        self.default_config = {
            "download_path": str(Path.home() / "Downloads" / "WebVideos"),
            "ffmpeg_path": "",
            "max_retries": 3,
            "threads": 8,
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "auto_open_folder": False,
            "max_pages": 5,
            "window_size": [800, 550]

        }
        self.config = self.load_config()

    def load_config(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in self.default_config.items():
                        if k not in data:
                            data[k] = v
                    return data
        except Exception:
            pass
        return self.default_config.copy()

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

    def get_download_path(self) -> Path:
        path = Path(self.config.get("download_path", self.default_config["download_path"]))
        path.mkdir(parents=True, exist_ok=True)
        return path
