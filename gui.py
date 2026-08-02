"""
PySide6 Graphical User Interface for Web Video Extractor
"""
import re
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget
)

from config import Config
from detector import VideoCandidate, VideoDetector
from downloader import VideoDownloader
from utils import check_curl_installed, check_ffmpeg_installed, open_folder


class DetectWorker(QThread):
    finished = Signal(list)
    status = Signal(str)

    def __init__(self, url: str, max_pages: int = 5):
        super().__init__()
        self.url = url
        self.max_pages = max_pages

    def run(self):
        msg = f"Analyzing URL and crawling up to {self.max_pages if self.max_pages > 0 else 'all'} page(s)..."
        self.status.emit(msg)
        detector = VideoDetector()
        candidates = detector.detect(self.url, max_pages=self.max_pages)
        self.finished.emit(candidates)



class DownloadWorker(QThread):
    status = Signal(str)
    progress = Signal(float)
    finished = Signal(bool, str)

    def __init__(self, candidate: VideoCandidate, output_name: str):
        super().__init__()
        self.candidate = candidate
        self.output_name = output_name

    def run(self):
        downloader = VideoDownloader()
        saved_path = downloader.download(
            self.candidate,
            output_filename=self.output_name,
            status_callback=lambda msg: self.status.emit(msg),
            progress_callback=lambda p: self.progress.emit(p)
        )
        if saved_path:
            self.finished.emit(True, saved_path)
        else:
            self.finished.emit(False, "")


class DownloadBatchWorker(QThread):
    status = Signal(str)
    progress = Signal(float)
    finished = Signal(list)

    def __init__(self, candidates: list):
        super().__init__()
        self.candidates = candidates

    def run(self):
        downloader = VideoDownloader()
        saved_files = downloader.download_batch(
            self.candidates,
            status_callback=lambda msg: self.status.emit(msg),
            progress_callback=lambda p: self.progress.emit(p)
        )
        self.finished.emit(saved_files)



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = Config()
        self.candidates = []
        self.selected_candidate = None
        self.detect_worker = None
        self.download_worker = None

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Web Video Extractor & Downloader")
        ws = self.config.get("window_size", [800, 550])
        self.resize(ws[0], ws[1])

        # Dark Theme Styling
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #121214;
                color: #E1E1E6;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #29292E;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
                color: #00E676;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLineEdit {
                background-color: #202024;
                border: 1px solid #323238;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
            }
            QLineEdit:focus {
                border: 1px solid #00E676;
            }
            QPushButton {
                background-color: #00E676;
                color: #121214;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00C853;
            }
            QPushButton:disabled {
                background-color: #29292E;
                color: #7C7C8A;
            }
            QPushButton#secBtn {
                background-color: #29292E;
                color: #E1E1E6;
                border: 1px solid #323238;
            }
            QPushButton#secBtn:hover {
                background-color: #323238;
                border-color: #7C7C8A;
            }
            QListWidget {
                background-color: #1A1A1E;
                border: 1px solid #29292E;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #29292E;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #00E676;
                color: #121214;
                font-weight: bold;
            }
            QProgressBar {
                border: 1px solid #29292E;
                border-radius: 6px;
                text-align: center;
                background-color: #202024;
                color: #FFFFFF;
            }
            QProgressBar::chunk {
                background-color: #00E676;
                border-radius: 5px;
            }
            QTextEdit {
                background-color: #1A1A1E;
                border: 1px solid #29292E;
                border-radius: 6px;
                font-family: monospace;
                color: #A8A8B3;
            }
        """)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header Title
        title_label = QLabel("🎬 Web Video Extractor & Downloader")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title_label)

        # URL Input Section
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter web page URL (e.g. https://mingky05.live/kor or /movie/... or video link)")
        
        pages_label = QLabel("Pages:")
        self.pages_combo = QComboBox()
        self.pages_combo.addItems(["5 Pages", "1 Page", "3 Pages", "10 Pages", "20 Pages", "All Pages"])
        self.pages_combo.setCurrentIndex(0)

        self.detect_btn = QPushButton("Detect Video")
        self.detect_btn.clicked.connect(self.start_detection)

        url_layout.addWidget(self.url_input, stretch=4)
        url_layout.addWidget(pages_label)
        url_layout.addWidget(self.pages_combo)
        url_layout.addWidget(self.detect_btn, stretch=1)
        layout.addLayout(url_layout)


        # Detected Candidates List
        list_box = QGroupBox("Detected Video Streams")
        list_layout = QVBoxLayout(list_box)
        self.video_list = QListWidget()
        self.video_list.itemSelectionChanged.connect(self.on_candidate_selected)
        list_layout.addWidget(self.video_list)
        layout.addWidget(list_box, stretch=2)

        # Download & Save Controls
        dl_layout = QHBoxLayout()
        self.download_path_btn = QPushButton("Save Path...", objectName="secBtn")
        self.download_path_btn.clicked.connect(self.select_download_folder)
        
        self.open_folder_btn = QPushButton("Open Folder", objectName="secBtn")
        self.open_folder_btn.clicked.connect(self.open_download_folder)

        self.download_btn = QPushButton("Download Selected")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self.start_download)

        self.download_all_btn = QPushButton("Download All Videos")
        self.download_all_btn.setEnabled(False)
        self.download_all_btn.clicked.connect(self.start_batch_download)

        dl_layout.addWidget(self.download_path_btn)
        dl_layout.addWidget(self.open_folder_btn)
        dl_layout.addStretch()
        dl_layout.addWidget(self.download_btn)
        dl_layout.addWidget(self.download_all_btn)
        layout.addLayout(dl_layout)


        # Progress & Status Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Log Console
        log_box = QGroupBox("Execution Logs")
        log_layout = QVBoxLayout(log_box)
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        log_layout.addWidget(self.log_console)
        layout.addWidget(log_box, stretch=2)

        # curl warning if missing (required for generic page scraping, HLS, and direct MP4 downloads)
        if not check_curl_installed():
            self.log("⚠️ curl not found on PATH. Generic page scraping, HLS, and direct MP4 downloads will fail (yt-dlp-supported sites like YouTube are unaffected).")

        # FFmpeg warning if missing
        ff = check_ffmpeg_installed()
        if ff:
            self.log(f"FFmpeg binary detected: {ff}")
        else:
            self.log("⚠️ FFmpeg binary not found in system. HLS stitching will fallback to raw join.")

    def log(self, text: str):
        self.log_console.append(text)

    def start_detection(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", "Please enter a valid URL.")
            return

        self.detect_btn.setEnabled(False)
        self.video_list.clear()
        self.candidates = []
        self.selected_candidate = None
        self.download_btn.setEnabled(False)

        combo_text = self.pages_combo.currentText()
        if "All" in combo_text:
            max_pages = 0
        else:
            m = re.search(r'\d+', combo_text)
            max_pages = int(m.group()) if m else 5

        self.detect_worker = DetectWorker(url, max_pages=max_pages)
        self.detect_worker.status.connect(self.log)
        self.detect_worker.finished.connect(self.on_detection_finished)
        self.detect_worker.start()


    def on_detection_finished(self, candidates: list):
        self.detect_btn.setEnabled(True)
        self.candidates = candidates

        if not candidates:
            self.download_all_btn.setEnabled(False)
            self.log("❌ No downloadable videos detected in this URL.")
            QMessageBox.information(self, "Result", "No video streams were detected on the page.")
            return

        self.download_all_btn.setEnabled(True)
        self.log(f"✅ Found {len(candidates)} video stream(s).")
        for idx, c in enumerate(candidates):
            item_text = f"[{c.video_type.upper()}] {c.title} — {c.url[:70]}..."
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, idx)
            self.video_list.addItem(item)

        self.video_list.setCurrentRow(0)

    def on_candidate_selected(self):
        items = self.video_list.selectedItems()
        if items:
            idx = items[0].data(Qt.UserRole)
            self.selected_candidate = self.candidates[idx]
            self.download_btn.setEnabled(True)
        else:
            self.selected_candidate = None
            self.download_btn.setEnabled(False)

    def select_download_folder(self):
        current_path = str(self.config.get_download_path())
        new_dir = QFileDialog.getExistingDirectory(self, "Select Download Directory", current_path)
        if new_dir:
            self.config.set("download_path", new_dir)
            self.log(f"Download directory set to: {new_dir}")

    def open_download_folder(self):
        path = str(self.config.get_download_path())
        open_folder(path)

    def start_download(self):
        if not self.selected_candidate:
            return

        self.download_btn.setEnabled(False)
        self.download_all_btn.setEnabled(False)
        self.detect_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        title = self.selected_candidate.title
        self.download_worker = DownloadWorker(self.selected_candidate, output_name=title)
        self.download_worker.status.connect(self.log)
        self.download_worker.progress.connect(self.progress_bar.setValue)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.start()

    def start_batch_download(self):
        if not self.candidates:
            return

        self.download_btn.setEnabled(False)
        self.download_all_btn.setEnabled(False)
        self.detect_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        self.log(f"🚀 Starting batch download for {len(self.candidates)} video(s)...")
        self.download_worker = DownloadBatchWorker(self.candidates)
        self.download_worker.status.connect(self.log)
        self.download_worker.progress.connect(self.progress_bar.setValue)
        self.download_worker.finished.connect(self.on_batch_finished)
        self.download_worker.start()

    def on_download_finished(self, success: bool, file_path: str):
        self.download_btn.setEnabled(True)
        self.download_all_btn.setEnabled(True)
        self.detect_btn.setEnabled(True)

        if success:
            self.log(f"🎉 Download successfully finished! Saved at:\n{file_path}")
            if self.config.get("auto_open_folder", False):
                open_folder(str(self.config.get_download_path()))
            QMessageBox.information(self, "Success", f"Video saved to:\n{file_path}")
        else:
            self.log("❌ Download failed. Please check logs.")
            QMessageBox.critical(self, "Error", "Failed to download video. See logs for details.")

    def on_batch_finished(self, saved_files: list):
        self.download_btn.setEnabled(True)
        self.download_all_btn.setEnabled(True)
        self.detect_btn.setEnabled(True)

        if saved_files:
            self.log(f"🎉 Batch download completed! Total {len(saved_files)} video(s) saved.")
            open_folder(str(self.config.get_download_path()))
            QMessageBox.information(self, "Batch Complete", f"Successfully downloaded {len(saved_files)} video(s)!")
        else:
            self.log("❌ Batch download finished with 0 files saved.")
            QMessageBox.warning(self, "Batch Warning", "No videos were successfully downloaded.")


    def closeEvent(self, event):
        ws = [self.width(), self.height()]
        self.config.set("window_size", ws)
        event.accept()


def main_gui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main_gui()
