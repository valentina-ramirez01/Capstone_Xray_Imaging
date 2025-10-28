# Interface.py
# PyQt6 GUI for IMX415 (Picamera2) ONLY — no OpenCV webcam fallback.

import sys
from pathlib import Path
import numpy as np
import cv2

# --- make 'xavier' importable even when Interface.py is in a separate folder ---
import sys, os
from pathlib import Path

# 1) Try to locate the 'xavier' folder by walking up from this file
_here = Path(__file__).resolve()
_root = None
for parent in [_here.parent, *_here.parents]:
    if (parent / "xavier").is_dir():
        _root = parent
        break

if _root is None:
    raise RuntimeError("Could not find the 'xavier' folder. Make sure your project has a folder named 'xavier'.")

# 2) Add the project root to sys.path so 'from xavier. ...' works
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
# -------------------------------------------------------------------------------


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QToolButton, QStatusBar, QMenuBar,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QAction, QKeySequence

# --- your project helpers ---
from io_utils import capture_and_save_frame
from gallery import Gallery


# ─────────────────────────────────────────────────────────────
# Abort early if Picamera2 is missing (no fallback)
# ─────────────────────────────────────────────────────────────
try:
    from picamera2 import Picamera2
except Exception as e:
    print("ERROR: picamera2 is required for this interface (no fallback).")
    print("Install on Raspberry Pi OS Bookworm: sudo apt install -y python3-picamera2")
    print("Details:", e)
    sys.exit(1)


# ─────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────
def gray_to_qpix(gray: np.ndarray) -> QPixmap:
    """Convert a 2D uint8 array to QPixmap for QLabel."""
    if gray is None:
        raise RuntimeError("Empty frame")
    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)
    h, w = gray.shape[:2]
    rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)


# ─────────────────────────────────────────────────────────────
# Picamera2 backend (IMX415) — mirrors your test script
# ─────────────────────────────────────────────────────────────
class PiCamBackend:
    """
    Picamera2 backend that follows your minimal test:
      - cam = Picamera2()
      - cam.configure(cam.create_preview_configuration(main={"size": (1280, 720)}))
      - cam.start()
      - frame = cam.capture_array("main")
      - convert to gray if needed

    Exposes:
      start(), stop(), grab_gray(), grab_bgr()
    """
    def __init__(self, preview_size=(1280, 720)):
        self.preview_size = preview_size
        self.cam: Picamera2 | None = None

    def start(self):
        self.cam = Picamera2()
        self.cam.configure(self.cam.create_preview_configuration(main={"size": self.preview_size}))
        self.cam.start()

    def stop(self):
        try:
            if self.cam:
                self.cam.stop()
        finally:
            self.cam = None

    def _capture_main(self) -> np.ndarray:
        if not self.cam:
            raise RuntimeError("Picamera2 not started")
        return self.cam.capture_array("main")

    def grab_gray(self) -> np.ndarray:
        """
        Return a grayscale view of the current frame.
        Picamera2 arrays are typically RGB; convert robustly.
        """
        frame = self._capture_main()
        if frame.ndim == 2:
            return frame
        # If 3-ch, assume RGB (Picamera2 default) and convert to gray
        try:
            return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        except Exception:
            # Fallback to BGR2GRAY if driver delivered BGR
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def grab_bgr(self) -> np.ndarray:
        """
        Return a BGR frame suitable for cv2.imwrite.
        """
        frame = self._capture_main()
        if frame.ndim == 2:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        # Picamera2 usually returns RGB
        try:
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except Exception:
            return frame  # if it's already BGR


# ─────────────────────────────────────────────────────────────
# Main GUI
# ─────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Window
        self.setWindowTitle("IC X-ray Viewer — IMX415 (Picamera2)")
        self.resize(1280, 720)

        # Capture/session state
        self.session_paths: list[str] = []
        self.last_path: Path | None = None
        self.save_dir = "captures"

        # Top alarm bar
        self.alarm = QLabel("OK")
        self.alarm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alarm.setObjectName("alarmBar")

        # Camera view
        self.view = QLabel("Camera View")
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view.setMinimumSize(960, 540)
        self.view.setObjectName("cameraView")

        # Left column
        self.btn_preview = QPushButton("Preview")
        self.btn_stop    = QPushButton("STOP"); self.btn_stop.setObjectName("btnStop")
        self.btn_gallery = QPushButton("Gallery")
        self.btn_export  = QPushButton("Export Last")
        self.btn_editor  = QPushButton("Open Editor")

        # Right tools (placeholders)
        tools_box = QGroupBox("Image Processing Tools")
        tools_col = QVBoxLayout(tools_box)
        self.tb_zoom     = QToolButton(); self.tb_zoom.setText("Zoom")
        self.tb_contrast = QToolButton(); self.tb_contrast.setText("Contrast")
        self.tb_sharp    = QToolButton(); self.tb_sharp.setText("Sharpness")
        self.tb_expo     = QToolButton(); self.tb_expo.setText("Exposure")
        self.tb_flip     = QToolButton(); self.tb_flip.setText("Flip")
        self.tb_focus    = QToolButton(); self.tb_focus.setText("Focus")
        for tb in (self.tb_zoom, self.tb_contrast, self.tb_sharp, self.tb_expo, self.tb_flip, self.tb_focus):
            tools_col.addWidget(tb)

        # Status + menu
        self.status = QStatusBar(); self.setStatusBar(self.status); self.status.showMessage("Ready.")
        menu = self.menuBar() if self.menuBar() else QMenuBar(self)
        menu.addMenu("&File"); menu.addMenu("&View"); menu.addMenu("&Help")

        # Hotkeys
        act_prev   = QAction("Toggle Preview", self); act_prev.setShortcut(QKeySequence("P"))
        act_stop   = QAction("STOP", self);           act_stop.setShortcut(QKeySequence("S"))
        act_export = QAction("Export Last", self);    act_export.setShortcut(QKeySequence("Ctrl+S"))
        act_gal    = QAction("Open Gallery", self);   act_gal.setShortcut(QKeySequence("G"))
        self.addAction(act_prev); self.addAction(act_stop); self.addAction(act_export); self.addAction(act_gal)
        act_prev.triggered.connect(self.on_toggle_preview)
        act_stop.triggered.connect(self.on_stop)
        act_export.triggered.connect(self.on_export_last)
        act_gal.triggered.connect(self.on_gallery)

        # Layout: left | center | right
        central = QWidget(self)
        root    = QHBoxLayout(central)

        left = QVBoxLayout()
        for b in (self.btn_preview, self.btn_stop, self.btn_gallery, self.btn_export, self.btn_editor):
            left.addWidget(b)
        left.addStretch(1)

        center = QVBoxLayout()
        center.addWidget(self.alarm)
        center.addWidget(self.view, 1)

        right = QVBoxLayout()
        right.addWidget(tools_box)
        right.addStretch(1)

        root.addLayout(left)
        root.addLayout(center, 1)
        root.addLayout(right)
        self.setCentralWidget(central)

        # Cute QSS
        self.setStyleSheet("""
        QMainWindow { background: #f7f9fc; }
        QLabel#cameraView {
          background: #ffffff;
          border: 1px solid #e6eaf0;
          border-radius: 16px;
        }
        QLabel#alarmBar {
          background: #e9fbf0;
          color: #2f7a43;
          border: 1px solid #e6eaf0;
          border-radius: 12px;
          padding: 6px;
        }
        QGroupBox {
          background: #ffffff;
          border: 1px solid #e6eaf0;
          border-radius: 16px;
          margin-top: 12px;
          padding: 12px;
        }
        QPushButton, QToolButton {
          background: #ffffff;
          border: 1px solid #e6eaf0;
          border-radius: 14px;
          padding: 8px 12px;
        }
        QPushButton:hover, QToolButton:hover {
          background: #f0f4ff;
          border-color: #cdd7ff;
        }
        QPushButton#btnStop {
          background: #ff6b6b;
          color: white;
          border: none;
          font-weight: 700;
        }
        QStatusBar {
          background: #ffffff;
          border-top: 1px solid #e6eaf0;
          padding: 4px 8px;
          color: #5b6472;
        }
        """)

        # Backend: Picamera2 only
        self.backend = PiCamBackend(preview_size=(1280, 720))
        try:
            self.backend.start()
            self.status.showMessage("Backend: Picamera2 (IMX415)")
        except Exception as e:
            QMessageBox.critical(self, "Picamera2 Error",
                                 f"Failed to start Picamera2:\n{e}\n\n"
                                 "Ensure the camera is connected and enabled.")
            sys.exit(1)

        # Preview state + timer
        self.preview_on = False
        self.preview_boost = False  # reserved if you want CLAHE toggle later
        self.timer = QTimer(self); self.timer.setInterval(33); self.timer.timeout.connect(self.update_frame)

        # Wire buttons
        self.btn_preview.clicked.connect(self.on_toggle_preview)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_gallery.clicked.connect(self.on_gallery)
        self.btn_export.clicked.connect(self.on_export_last)
        self.btn_editor.clicked.connect(self.on_open_editor)

    # Actions
    def on_toggle_preview(self):
        if not self.preview_on:
            self.preview_on = True
            self.timer.start()
            self.status.showMessage("Preview ON")
            self.alarm.setText("Preview: ON")
        else:
            self.preview_on = False
            self.timer.stop()
            self.status.showMessage("Preview OFF")
            self.alarm.setText("Preview: OFF")

    def on_stop(self):
        self.preview_on = False
        self.timer.stop()
        self.status.showMessage("Stopped")
        self.alarm.setText("STOP PRESSED!")
        try:
            self.backend.stop()
        except Exception:
            pass

    def on_export_last(self):
        """
        Save the CURRENT live frame to disk (captures/capture_XXXX.png).
        Uses your io_utils.capture_and_save_frame().
        """
        if not self.preview_on:
            QMessageBox.information(self, "Export", "Start preview first to export the current frame.")
            return
        try:
            bgr = self.backend.grab_bgr()
            path, _ = capture_and_save_frame(bgr, save_dir=self.save_dir)
            self.session_paths.append(path)
            self.last_path = Path(path)
            self.status.showMessage(f"Saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export", f"Failed to save frame:\n{e}")

    def on_gallery(self):
        was_on = self.preview_on
        if was_on:
            self.on_toggle_preview()

        try:
            if self.session_paths:
                gal = Gallery(self.session_paths, window_name="Gallery (session)")
                gal.run(start_at=str(self.last_path) if self.last_path else None)
            else:
                import glob, os
                all_paths = sorted(glob.glob(os.path.join(self.save_dir, "capture_*.png")))
                if not all_paths:
                    QMessageBox.information(self, "Gallery", "No images in captures/.")
                else:
                    gal = Gallery(all_paths, window_name="Gallery (all)")
                    gal.run(start_at=str(self.last_path) if self.last_path else None)
        except Exception as e:
            QMessageBox.critical(self, "Gallery", f"Failed to open gallery:\n{e}")
        finally:
            if was_on:
                self.on_toggle_preview()
            self.status.showMessage("Returned from Gallery.")

    def on_open_editor(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open image", "", "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        if not path:
            return
        QMessageBox.information(self, "Editor", f"Selected: {path}\n(You can wire image_tools.py here later.)")

    # Timer tick — grab, convert, paint
    def update_frame(self):
        try:
            frame = self.backend.grab_gray()
        except Exception as e:
            self.timer.stop()
            self.preview_on = False
            self.alarm.setText(f"Preview error: {e}")
            return

        # Optional: if self.preview_boost: apply CLAHE here
        px = gray_to_qpix(frame)
        px = px.scaled(
            self.view.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.view.setPixmap(px)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
