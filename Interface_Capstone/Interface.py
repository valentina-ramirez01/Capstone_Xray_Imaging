import sys
import math                              # for a moving sine-wave stripe in dummy preview
import numpy as np                       # for image generation
import cv2                               # OpenCV for image conversion (gray->RGB)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QToolButton, QStatusBar, QMenuBar, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap


# ─────────────────────────────────────────────────────────────
# Optional: try real camera backend; fall back to dummy if not available
# ─────────────────────────────────────────────────────────────
try:
    from mipi_camera import CameraController
    HAS_CAMERA = True
except Exception as e:
    print("Camera backend not available", e)
    HAS_CAMERA = False


# ─────────────────────────────────────────────────────────────
# Helper: grayscale numpy array -> QPixmap to paint in QLabel
# ─────────────────────────────────────────────────────────────
def gray_to_qpix(gray: np.ndarray) -> QPixmap:
    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)
    h, w = gray.shape[:2]
    rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)


# ─────────────────────────────────────────────────────────────
# Dummy camera (runs on any PC). Generates a moving gradient.
# ─────────────────────────────────────────────────────────────
class DummyCam:
    def __init__(self, preview_size=(1280, 720), still_size=(3840, 2160)):
        self.preview_size = preview_size
        self.still_size = still_size
        self._t = 0

    def start(self):  # mirror real backend API
        pass

    def stop(self):
        pass

    def set_ae_limits(self, **kwargs):
        pass

    def auto_meter(self, settle_s=1.0, samples=3):
        # plausible constants for demo
        return (25000, 2.0, 33333, 127.0)

    def set_photo_shutter_us(self, us):  # for completeness
        pass

    def set_photo_gain(self, g):
        pass

    def grab_gray(self):
        w, h = self.preview_size
        x = np.tile(np.linspace(0, 255, w, dtype=np.uint8), (h, 1))
        y = np.tile(np.linspace(0, 255, h, dtype=np.uint8), (w, 1)).T
        img = ((0.6 * x + 0.4 * y) % 256).astype(np.uint8)
        col = int((math.sin(self._t / 10) * 0.5 + 0.5) * (w - 1))
        img[:, col:col + 2] = 255  # moving bright stripe so you see motion
        self._t += 1
        return img

    def capture_photo(self, path="mono_dummy.png"):
        cv2.imwrite(path, self.grab_gray())
        return path


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # ---- Window basics ----
        self.setWindowTitle("IC X-ray Viewer v0.3")
        self.resize(1280, 720)

        # ---- TOP: alarm/status banner ----
        self.alarm = QLabel("OK")
        self.alarm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alarm.setObjectName("alarmBar")  # for QSS targeting

        # ---- CENTER: camera view ----
        self.view = QLabel("Camera View")
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view.setMinimumSize(960, 540)
        self.view.setObjectName("cameraView")  # for QSS targeting

        # ---- LEFT: main action buttons ----
        self.btn_preview = QPushButton("Preview")
        self.btn_stop    = QPushButton("STOP")
        self.btn_gallery = QPushButton("Gallery")
        self.btn_export  = QPushButton("Export Last")
        self.btn_editor  = QPushButton("Open Editor")
        self.btn_stop.setObjectName("btnStop")  # for QSS targeting

        # ---- RIGHT: tools box ----
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

        # ---- STATUS BAR ----
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready.")

        # ---- MENU BAR ----
        menu = self.menuBar() if self.menuBar() else QMenuBar(self)
        menu.addMenu("&File")
        menu.addMenu("&View")
        menu.addMenu("&Help")

        # ---- LAYOUT: left | center | right ----
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
        root.addLayout(center, 1)  # center gets extra width
        root.addLayout(right)
        self.setCentralWidget(central)

        # ── Cute stylesheet (QSS) applied once
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

        # ── Backend selection (real on Pi, dummy on PC)
        self.cam = CameraController(preview_size=(1280, 720), still_size=(3840, 2160)) if HAS_CAMERA else DummyCam()
        self.cam.start()
        if HAS_CAMERA:
            try:
                self.cam.set_ae_limits(exposure_max_us=33333, gain_min=1.0, gain_max=16.0)  # smoother preview
            except Exception as e:
                print("AE limit warn:", e)

        # ── Preview state + timer
        self.preview_on = False
        self.preview_boost = False
        self.timer = QTimer(self)
        self.timer.setInterval(33)  # ~30 FPS
        self.timer.timeout.connect(self.update_frame)

        # ── Wire buttons
        self.btn_preview.clicked.connect(self.on_toggle_preview)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_gallery.clicked.connect(self.on_gallery)     # placeholder (wired later)
        self.btn_export.clicked.connect(self.on_export_last)  # placeholder (wired later)
        self.btn_editor.clicked.connect(self.on_open_editor)  # placeholder (wired later)

    # ─────────────────────────────────────────────────────────
    # Slots (button actions)
    # ─────────────────────────────────────────────────────────
    def on_toggle_preview(self):
        if not self.preview_on:
            self.preview_on = True
            self.timer.start()
            self.status.showMessage("Preview ON (AE)")
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
            self.cam.stop()
        except Exception:
            pass

    def on_gallery(self):
        QMessageBox.information(self, "Gallery", "Ya mismo se pone")

    def on_export_last(self):
        QMessageBox.information(self, "Export", "Ya mismo se pone")

    def on_open_editor(self):
        QMessageBox.information(self, "Editor", "Ya mismo se pone")

    # ─────────────────────────────────────────────────────────
    # Timer tick: pull a frame and paint it into the QLabel
    # ─────────────────────────────────────────────────────────
    def update_frame(self):
        try:
            frame = self.cam.grab_gray()
        except Exception as e:
            self.timer.stop()
            self.preview_on = False
            self.alarm.setText(f"Preview error: {e}")
            return

        # Optional: display-only boost (CLAHE)
        # (We’ll add a toggle/hotkey later)
        # clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        # frame = clahe.apply(frame)

        px = gray_to_qpix(frame)
        px = px.scaled(self.view.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.view.setPixmap(px)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
