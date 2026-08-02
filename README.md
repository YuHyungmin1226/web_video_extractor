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
   - 테두리 없는(frameless) 미니멀 다크 테마 GUI: 커스텀 타이틀바(드래그 이동), 가장자리 드래그로 창 크기 조절, 최소화·최대화·닫기 버튼 제공
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

## 🛠 빌드 방법 (직접 실행 파일 만들기)

의존성이 설치된 가상환경에서 아래 명령어를 실행하면 `dist/` 폴더 내에 실행 파일(Windows) 또는 `.app` 번들(macOS), 단일 바이너리(Linux)가 생성됩니다.

```bash
python build.py
```

빌드는 실행하는 OS에 맞춰서만 만들어지며(교차 컴파일 미지원), `curl`/`ffmpeg`는 실행 파일에 내장되지 않고 실행 시점에 시스템 PATH에서 찾습니다(위 "OS별 사전 요구사항" 참고).

| OS | 산출물 | 콘솔 창 처리 |
|---|---|---|
| Windows | 단일 파일 `dist/WebVideoExtractor.exe` | 콘솔 서브시스템으로 빌드되어 `--cli`가 터미널에서 정상 출력됩니다. GUI 모드로 실행(인자 없이 실행)하면 앱이 시작 직후 콘솔 창을 스스로 숨깁니다. 더블클릭 실행 시 아주 짧게(1초 미만) 콘솔 창이 깜빡일 수 있는데, 이는 GUI+CLI 겸용 실행 파일에서 흔히 나타나는 정상적인 동작입니다. |
| macOS | `dist/WebVideoExtractor.app` | `--windowed`로 빌드되어 Finder 실행 시 콘솔이 뜨지 않으며, 같은 실행 파일을 터미널에서 `.app/Contents/MacOS/WebVideoExtractor --cli ...`로 직접 실행해도 표준출력이 정상 동작합니다(직접 빌드해 검증됨). |
| Linux | 단일 파일 `dist/WebVideoExtractor` | Linux는 실행 파일 서브시스템 구분이 없어 별도 처리가 필요 없습니다. |

> 💡 저장소에 포함된 `icon.png`(모든 OS 공용, GUI 창 아이콘) / `icon.ico`(Windows) / `icon.icns`(macOS)를 `build.py`가 자동으로 감지해 실행 파일에 아이콘을 포함합니다. 다른 아이콘으로 바꾸고 싶다면 같은 파일명으로 교체하면 되며, 아이콘 파일이 없어도 빌드는 정상적으로 진행됩니다.

## 🧪 테스트 실행 (Pytest)

```bash
pytest tests/
```
