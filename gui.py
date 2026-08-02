"""
PySide6 Graphical User Interface for Web Video Extractor
"""
import os
import re
import sys

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget
)

from config import Config
from detector import VideoCandidate, VideoDetector
from downloader import VideoDownloader
from utils import check_curl_installed, check_ffmpeg_installed, open_folder

APP_DISPLAY_NAME = "Web Video Extractor & Downloader"

# Minimal frameless dark theme, structured the same way as the reference
# MinimalPlayer UI (github.com/YuHyungmin1226/MinimalPlayer): a single QSS
# block keyed off object names for the title bar / control row, flat
# transparent buttons with subtle hover states, and explicit QMessageBox /
# QFileDialog styling so dialogs don't inherit a light OS theme's white
# background (they aren't children of MainWindow's widget tree on every
# platform, so they can't be assumed to pick up rules meant for it).
STYLE = (
    "QMainWindow, QWidget { background-color: #121212; color: #E1E1E6;"
    " font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;"
    " font-size: 13px; }"
    "#TitleBar { background-color: #1e1e1e; border-bottom: 1px solid #333; }"
    "#TitleLabel { color: #eee; font-weight: bold; }"
    "#TitleBar QPushButton { background: transparent; color: #eee; border: none;"
    " border-radius: 0; font-size: 14px; padding: 0; }"
    "#TitleBar QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }"
    "#TitleBar QPushButton:pressed { background-color: rgba(255, 255, 255, 0.2); }"
    "#CloseBtn:hover { background-color: #e81123; color: white; }"
    "QGroupBox { border: 1px solid #333; border-radius: 8px; margin-top: 12px;"
    " padding-top: 12px; font-weight: bold; color: #00E676; }"
    "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
    "QLineEdit { background-color: #1e1e1e; border: 1px solid #333; border-radius: 6px;"
    " padding: 8px 12px; color: #FFFFFF; }"
    "QLineEdit:focus { border: 1px solid #00E676; }"
    "QComboBox { background-color: #1e1e1e; border: 1px solid #333; border-radius: 6px;"
    " padding: 6px 10px; color: #E1E1E6; }"
    "QPushButton { background-color: #00E676; color: #121212; border: none;"
    " border-radius: 6px; padding: 8px 16px; font-weight: bold; }"
    "QPushButton:hover { background-color: #00C853; }"
    "QPushButton:pressed { background-color: #00B84D; }"
    "QPushButton:disabled { background-color: #29292E; color: #7C7C8A; }"
    "QPushButton#secBtn { background-color: #1e1e1e; color: #E1E1E6; border: 1px solid #333; }"
    "QPushButton#secBtn:hover { background-color: #29292E; border-color: #7C7C8A; }"
    "QListWidget { background-color: #1A1A1E; border: 1px solid #333; border-radius: 6px; padding: 4px; }"
    "QListWidget::item { padding: 8px; border-bottom: 1px solid #29292E; border-radius: 4px; }"
    "QListWidget::item:selected { background-color: #00E676; color: #121212; font-weight: bold; }"
    "QProgressBar { border: 1px solid #333; border-radius: 6px; text-align: center;"
    " background-color: #1e1e1e; color: #FFFFFF; }"
    "QProgressBar::chunk { background-color: #00E676; border-radius: 5px; }"
    "QTextEdit { background-color: #1A1A1E; border: 1px solid #333; border-radius: 6px;"
    " font-family: monospace; color: #A8A8B3; }"
    # Dialogs are top-level windows, not reliably part of MainWindow's widget
    # tree on every platform, so they need their dark colors spelled out here
    # rather than relying on inheritance from the rules above.
    "QMessageBox, QFileDialog { background-color: #1e1e1e; }"
    "QMessageBox QLabel { color: #eee; font-size: 13px; }"
    "QMessageBox QPushButton { background-color: #29292E; color: #eee; border: 1px solid #333;"
    " border-radius: 4px; min-width: 72px; min-height: 28px; padding: 2px 12px; }"
    "QMessageBox QPushButton:hover { background-color: #3a3a3a; }"
    "QMessageBox QPushButton:pressed { background-color: #454545; }"
    "QMessageBox QPushButton:default { border: 2px solid #00E676; }"
)

_RESIZE_MARGIN = 6


def _resolve_icon_path() -> str:
    """Locate icon.png next to the script in dev, or next to the executable /
    inside the PyInstaller bundle when frozen. Returns "" if none is found —
    the caller then simply skips setWindowIcon(), matching how build.py only
    bundles an icon when one exists rather than requiring it."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        candidate = os.path.join(base, "icon.png")
        if not os.path.exists(candidate):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidate = os.path.join(meipass, "icon.png")
    else:
        candidate = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
    return candidate if os.path.exists(candidate) else ""


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
        self._drag_pos = None
        self._resize_edge = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMouseTracking(True)

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(APP_DISPLAY_NAME)
        ws = self.config.get("window_size", [800, 550])
        self.resize(ws[0], ws[1])
        self.setMinimumSize(600, 420)
        self.setStyleSheet(STYLE)

        icon_path = _resolve_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        central_widget = QWidget()
        central_widget.setMouseTracking(True)
        self.setCentralWidget(central_widget)
        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        outer_layout.addWidget(self._build_title_bar())

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        outer_layout.addWidget(body, 1)

        # URL Input Section
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter web page URL (e.g. https://mingky05.live/kor or /movie/... or video link)")

        pages_label = QLabel("Pages:")
        self.pages_combo = QComboBox()
        self.pages_combo.addItems(["5 Pages", "1 Page", "3 Pages", "10 Pages", "20 Pages", "All Pages"])
        self.pages_combo.setCurrentIndex(0)

        self.detect_btn = QPushButton("Detect Video")
        self.detect_btn.setToolTip("Detect video streams on the entered URL")
        self.detect_btn.setAccessibleName("Detect Video")
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
        self.download_path_btn.setToolTip("Choose the download destination folder")
        self.download_path_btn.clicked.connect(self.select_download_folder)

        self.open_folder_btn = QPushButton("Open Folder", objectName="secBtn")
        self.open_folder_btn.setToolTip("Open the download destination folder")
        self.open_folder_btn.clicked.connect(self.open_download_folder)

        self.download_btn = QPushButton("Download Selected")
        self.download_btn.setToolTip("Download the selected video stream")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self.start_download)

        self.download_all_btn = QPushButton("Download All Videos")
        self.download_all_btn.setToolTip("Download every detected video stream")
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

    def _build_title_bar(self) -> QFrame:
        self.title_bar = QFrame()
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(35)
        self.title_bar.setMouseTracking(True)
        title_bar_layout = QHBoxLayout(self.title_bar)
        title_bar_layout.setContentsMargins(15, 0, 0, 0)
        title_bar_layout.setSpacing(0)

        title_label = QLabel(f"🎬 {APP_DISPLAY_NAME}")
        title_label.setObjectName("TitleLabel")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()

        self.min_btn = QPushButton("–")
        self.min_btn.setFixedSize(40, 35)
        self.min_btn.setToolTip("Minimize")
        self.min_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.min_btn.clicked.connect(self.showMinimized)

        self.maximize_btn = QPushButton("☐")
        self.maximize_btn.setFixedSize(40, 35)
        self.maximize_btn.setToolTip("Maximize")
        self.maximize_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.maximize_btn.clicked.connect(self._toggle_maximized)

        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setFixedSize(40, 35)
        self.close_btn.setToolTip("Close")
        self.close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_btn.clicked.connect(self.close)

        title_bar_layout.addWidget(self.min_btn)
        title_bar_layout.addWidget(self.maximize_btn)
        title_bar_layout.addWidget(self.close_btn)
        return self.title_bar

    def _toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
            self.maximize_btn.setText("☐")
            self.maximize_btn.setToolTip("Maximize")
        else:
            self.showMaximized()
            self.maximize_btn.setText("❐")
            self.maximize_btn.setToolTip("Restore")

    # --- Frameless window drag-to-move / edge-resize -----------------------
    # Uses QWindow.startSystemMove()/startSystemResize() (Qt 5.15+) rather
    # than hand-rolled per-pixel math: the window manager handles the actual
    # move/resize natively, so this behaves correctly on Windows, macOS, and
    # Linux (X11 and Wayland) without any OS-specific code here.

    def _edge_at(self, pos):
        if self.isMaximized() or self.isFullScreen():
            return None
        rect = self.rect()
        x, y = pos.x(), pos.y()
        left = x <= _RESIZE_MARGIN
        right = x >= rect.width() - _RESIZE_MARGIN
        top = y <= _RESIZE_MARGIN
        bottom = y >= rect.height() - _RESIZE_MARGIN
        edge = Qt.Edge(0)
        if top:
            edge |= Qt.Edge.TopEdge
        if bottom:
            edge |= Qt.Edge.BottomEdge
        if left:
            edge |= Qt.Edge.LeftEdge
        if right:
            edge |= Qt.Edge.RightEdge
        return edge if edge != Qt.Edge(0) else None

    _EDGE_CURSORS = {
        Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor,
        Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor,
        Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor,
        Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
        Qt.Edge.TopEdge | Qt.Edge.LeftEdge: Qt.CursorShape.SizeFDiagCursor,
        Qt.Edge.BottomEdge | Qt.Edge.RightEdge: Qt.CursorShape.SizeFDiagCursor,
        Qt.Edge.TopEdge | Qt.Edge.RightEdge: Qt.CursorShape.SizeBDiagCursor,
        Qt.Edge.BottomEdge | Qt.Edge.LeftEdge: Qt.CursorShape.SizeBDiagCursor,
    }

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._edge_at(event.position().toPoint())
            if edge is not None:
                self.windowHandle().startSystemResize(edge)
                event.accept()
                return
            if self.childAt(event.position().toPoint()) is self.title_bar or \
                    self.title_bar.underMouse():
                self.windowHandle().startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        edge = self._edge_at(event.position().toPoint())
        self.setCursor(self._EDGE_CURSORS.get(edge, Qt.CursorShape.ArrowCursor))
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.title_bar.underMouse():
            self._toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

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
        if not self.isMaximized():
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
