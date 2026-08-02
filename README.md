# Web Video Extractor & Downloader

Web Video Extractor는 임의의 웹페이지 URL(예: `https://mingky05.live/movie/3feec10550?page=1`, YouTube, 일반 비디오 스트리밍 사이트 등)에서 동영상 스트림(HLS `.m3u8`, direct `.mp4`, iframe embed, HTML5 video 태그 등)을 자동으로 감지하고, Cloudflare 등의 403 차단을 우회하여 고화질 MP4 파일로 추출/다운로드해주는 자율형 비디오 다운로더입니다.

---

## 🌟 주요 기능

1. **자동 비디오 스트림 감지 (Smart Video Detector)**:
   - `<video>`, `<source>`, `data-source`, `data-url`, `og:video` 태그 및 인라인 JavaScript 파싱
   - 임베드된 중첩 `<iframe>` 플레이어 자동 추적 및 복원
   - YouTube, Vimeo 등 표준 플랫폼의 yt-dlp 통합 지원

2. **Cloudflare & 403 보안 우회 다운로드**:
   - HTTP/2 핸드셰이크 지원 `curl` + `Referer` / `User-Agent` 헤더 동적 바인딩
   - HLS (`.m3u8`) 멀티스레드 병렬 세그먼트 수집 및 무손실 병합

3. **FFmpeg 무손실 병합 & 스트림 캡처 (Recorder)**:
   - 시스템 내 FFmpeg 자동 감지 및 세그먼트 무손실 수집
   - 보호된 스트림에 대한 FFmpeg 기반 폴백 스트림 녹화 기능 제공

4. **PySide6 GUI & CLI 완벽 지원**:
   - 직관적이고 세련된 다크 테마 GUI 제공
   - 자동화 터미널 실행을 위한 CLI 옵션 제공

---

## 🚀 설치 및 실행 방법

### 0. OS별 사전 요구사항

이 프로그램은 Python 패키지 외에 시스템에 설치된 `curl`과 `ffmpeg` 실행 파일에 의존합니다. `curl`은 일반 웹페이지 스크레이핑·HLS·직접 MP4 다운로드에 필수이며(YouTube 등 yt-dlp 지원 사이트는 예외), `ffmpeg`는 없어도 동작하지만 있어야 무손실 세그먼트 병합이 가능합니다. 둘 다 없으면 실행 시 경고 메시지로 안내합니다.

| OS | curl | ffmpeg |
|---|---|---|
| Windows 10(1803+)/11 | 기본 내장 | `winget install ffmpeg` 또는 [공식 빌드](https://ffmpeg.org/download.html) 설치 후 PATH 등록 |
| macOS | 기본 내장 | `brew install ffmpeg` |
| Ubuntu 26.04 등 Linux | 최소 설치 이미지엔 없을 수 있음 → `sudo apt install curl` | `sudo apt install ffmpeg` |

### 1. 가상환경 생성 및 의존성 설치

```bash
cd /Users/yhm/Documents/YuHyungmin1226/web_video_extractor
python3 -m venv .venv
source .venv/bin/activate   # Windows(PowerShell/cmd)는: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. GUI 실행

```bash
python main.py
```

### 3. CLI 터미널 실행 (URL 직결 다운로드)

```bash
python main.py --cli --url "https://mingky05.live/movie/3feec10550?page=1"
```

---

## 🧪 테스트 실행 (Pytest)

```bash
pytest tests/
```
