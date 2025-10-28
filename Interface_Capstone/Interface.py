# Interface.py — PyQt6 GUI for IMX415 (Picamera2) ONLY, with live display controls + export mode toggle.
# Includes robust STOP → Preview restart logic.

# --- locate 'xavier' package even if this file is in a different folder ---
import sys
from pathlib import Path
import time  # <-- added

_here = Path(__file__).resolve()
_root = None
for parent in [_here.parent, *_here.parents]:
    if (parent / "xavier").is_dir():
        _root = parent
        break
if _root is None:
    raise RuntimeError("Could not find the 'xavier' folder. Place this file within the project tree.")
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# --- require Picamera2 (no fallback) ---
try:
    from picamera2 import Picamera2
except Exception as e:
    print("ERROR: picamera2 is required (no fallback). Install: sudo apt install -y python3-picamera2")
    print("Details:", e)
    sys.exit(1)

# --- std imports ---
import numpy as np
import cv2

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QToolButton, QStatusBar, QMenuBar,
    QFileDialog, QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QAction

# --- your helpers from xavier/ ---
from xavier.io_utils import capture_and_save_frame
from xavier.gallery import Gallery


# ─────────────────────────────────────────────────────────────
# Picamera2 backend (IMX415) — mirrors your test script
# ─────────────────────────────────────────────────────────────
class PiCamBackend:
    def __init__(self, preview_size=(1280, 720)):
        self.preview_size = preview_size
        self.cam: Picamera2 | None = None

    def start(self):
        self.cam = Picamera2()
        self.cam.configure(self.cam.create_preview_configuration(main={"size": self.preview_size}))
        self.cam.start()
        time.sleep(0.1)  # give the pipeline a moment to initialize

    def stop(self):
        if self.cam:
            try:
                self.cam.stop()
            except Exception:
                pass
            try:
                # Fully release the camera device (if available in your Picamera2 build)
                self.cam.close()
            except Exception:
                pass
        self.cam = None
        time.sleep(0.2)  # short breather so libcamera settles before restart

    def _capture(self):
        if not self.cam:
            raise RuntimeError("Picamera2 not started")
        return self.cam.capture_array("main")

    def grab_gray(self) -> np.ndarray:
        frame = self._capture()
        if frame.ndim == 2:
            return frame
        # Picamera2 typically returns RGB
        try:
            return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        except Exception:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def grab_bgr(self) -> np.ndarray:
        frame = self._capture()
        if frame.ndim == 2:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        try:
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except Exception:
            return frame  # assume already BGR


# ─────────────────────────────────────────────────────────────
# Main GUI
# ─────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Window
        self.setWindowTitle("IC X-ray Viewer — IMX415 (Picamera2)")
        self.resize(1280, 720)

        # Session / export state
        self.session_paths: list[str] = []
        self.last_path: Path | None = None
        self.save_dir = "captures"
        self.export_processed = False  # False=save RAW camera frame, True=save processed display

        # Top banner
        self.alarm = QLabel("OK", alignment=Qt.AlignmentFlag.AlignCenter, objectName="alarmBar")

        # Camera view
        self.view = QLabel("Camera View", alignment=Qt.AlignmentFlag.AlignCenter, objectName="cameraView")
        self.view.setMinimumSize(960, 540)

        # Left column buttons
        self.btn_preview = QPushButton("Preview")
        self.btn_stop    = QPushButton("STOP", objectName="btnStop")
        self.btn_gallery = QPushButton("Gallery")
        self.btn_export  = QPushButton("Export Last")
        self.btn_editor  = QPushButton("Open Editor")

        # Right column tools
        tools_box = QGroupBox("Display Controls")
        tlay = QVBoxLayout(tools_box)
        self.tb_zoom     = QToolButton(text="Zoom")
        self.tb_contrast = QToolButton(text="Contrast")
        self.tb_sharp    = QToolButton(text="Sharpness")
        self.tb_gamma    = QToolButton(text="Exposure (Gamma)")
        self.tb_filter   = QToolButton(text="Filter")
        self.tb_reset    = QToolButton(text="Reset View")
        for b in (self.tb_zoom, self.tb_contrast, self.tb_sharp, self.tb_gamma, self.tb_filter, self.tb_reset):
            tlay.addWidget(b)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready. (Export mode: RAW)")

        # Menu / hotkeys
        menu = self.menuBar() or QMenuBar(self)
        menu.addMenu("&File"); menu.addMenu("&View"); menu.addMenu("&Help")

        act_prev  = QAction("Toggle Preview", self, shortcut="P")
        act_stop  = QAction("STOP", self, shortcut="S")
        act_exp   = QAction("Export Last", self, shortcut="Ctrl+S")
        act_gal   = QAction("Gallery", self, shortcut="G")
        act_mode  = QAction("Toggle Export Mode (RAW/Processed)", self, shortcut="Ctrl+E")
        self.addActions([act_prev, act_stop, act_exp, act_gal, act_mode])
        act_prev.triggered.connect(self.on_toggle_preview)
        act_stop.triggered.connect(self.on_stop)
        act_exp.triggered.connect(self.on_export_last)
        act_gal.triggered.connect(self.on_gallery)
        act_mode.triggered.connect(self.on_toggle_export_mode)

        # Layout: left | center | right
        central = QWidget(self)
        root = QHBoxLayout(central)

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

        # Styles
        self.setStyleSheet("""
        QMainWindow { background: #f7f9fc; }
        QLabel#cameraView {
          background: #ffffff; border: 1px solid #e6eaf0; border-radius: 16px;
        }
        QLabel#alarmBar {
          background: #e9fbf0; color: #2f7a43; border: 1px solid #e6eaf0;
          border-radius: 12px; padding: 6px;
        }
        QPushButton, QToolButton {
          background: #ffffff; border: 1px solid #e6eaf0;
          border-radius: 14px; padding: 8px 12px;
        }
        QPushButton:hover, QToolButton:hover {
          background: #f0f4ff; border-color: #cdd7ff;
        }
        QPushButton#btnStop {
          background: #ff6b6b; color: white; border: none; font-weight: 700;
        }
        QGroupBox {
          background: #ffffff; border: 1px solid #e6eaf0;
          border-radius: 16px; margin-top: 12px; padding: 12px;
        }
        QStatusBar {
          background: #ffffff; border-top: 1px solid #e6eaf0;
          padding: 4px 8px; color: #5b6472;
        }
        """)

        # Backend: Picamera2 only
        self.backend = PiCamBackend((1280, 720))
        try:
            self.backend.start()
            self.status.showMessage("Backend: Picamera2 (IMX415) — Export mode: RAW")
        except Exception as e:
            QMessageBox.critical(self, "Picamera2 Error", f"Cannot start camera:\n{e}")
            sys.exit(1)

        # Preview timer
        self.preview_on = False
        self.timer = QTimer(self)
        self.timer.setInterval(33)  # ~30 FPS
        self.timer.timeout.connect(self.update_frame)

        # Live display params (matching image_tools defaults)
        self.lv_zoom = 1.0
        self.lv_cx, self.lv_cy = 640, 360  # set on first frame
        self.lv_contrast = 1.0             # 0.2–3.0
        self.lv_sharpness = 0.0            # 0.0–3.0
        self.lv_gamma = 1.0                # 0.2–3.0
        self.lv_filter_idx = 0
        self.lv_filters = ["none", "invert", "equalize", "clahe", "edges", "magma"]
        self._center_inited = False

        # Connect buttons
        self.btn_preview.clicked.connect(self.on_toggle_preview)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_gallery.clicked.connect(self.on_gallery)
        self.btn_export.clicked.connect(self.on_export_last)
        self.btn_editor.clicked.connect(self.on_open_editor)

        self.tb_zoom.clicked.connect(self.on_set_zoom)
        self.tb_contrast.clicked.connect(self.on_set_contrast)
        self.tb_sharp.clicked.connect(self.on_set_sharpness)
        self.tb_gamma.clicked.connect(self.on_set_gamma)
        self.tb_filter.clicked.connect(self.on_cycle_filter)
        self.tb_reset.clicked.connect(self.on_reset_view)

    # ---------- helpers ----------
    def _clamp(self, v, lo, hi): return max(lo, min(hi, v))

    # ---------- actions ----------
    def on_toggle_preview(self):
        """
        Toggle the live preview.
        If STOP was pressed earlier (camera released), this safely re-inits Picamera2.
        """
        if not self.preview_on:
            # Ensure timer is off to avoid a grab during (re)start
            self.timer.stop()

            # If the camera was fully stopped, re-create it
            if self.backend.cam is None:
                try:
                    self.backend.start()
                    self.status.showMessage("Camera restarted — Preview ON")
                    time.sleep(0.05)  # small cushion before first capture
                except Exception as e:
                    QMessageBox.critical(self, "Camera", f"Failed to (re)start camera:\n{e}")
                    return

            # Start periodic grabs
            self.preview_on = True
            self.timer.start()
            self.alarm.setText("Preview: ON")

        else:
            # Pause only the UI updates; camera keeps running
            self.preview_on = False
            self.timer.stop()
            self.alarm.setText("Preview: OFF")

    def on_stop(self):
        self.preview_on = False
        self.timer.stop()
        self.alarm.setText("STOP PRESSED!")
        self.backend.stop()

    def on_toggle_export_mode(self):
        self.export_processed = not self.export_processed
        mode = "PROCESSED" if self.export_processed else "RAW"
        self.status.showMessage(f"Backend: Picamera2 (IMX415) — Export mode: {mode}")

    def on_export_last(self):
        if not self.preview_on:
            QMessageBox.information(self, "Export", "Start preview first.")
            return
        try:
            if self.export_processed:
                gray = self.backend.grab_gray()
                disp_bgr = self.apply_pipeline(gray)
                path, _ = capture_and_save_frame(disp_bgr, save_dir=self.save_dir)
            else:
                bgr = self.backend.grab_bgr()
                path, _ = capture_and_save_frame(bgr, save_dir=self.save_dir)
            self.session_paths.append(path)
            self.last_path = Path(path)
            self.status.showMessage(f"Saved ({'processed' if self.export_processed else 'raw'}): {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export", f"Failed to save:\n{e}")

    def on_gallery(self):
        was_on = self.preview_on
        if was_on: self.on_toggle_preview()
        try:
            if self.session_paths:
                gal = Gallery(self.session_paths, window_name="Gallery (session)")
                gal.run(start_at=str(self.last_path) if self.last_path else None)
            else:
                all_paths = sorted((Path(self.save_dir)).glob("capture_*.png"))
                if not all_paths:
                    QMessageBox.information(self, "Gallery", "No images in captures/.")
                else:
                    gal = Gallery([str(p) for p in all_paths], window_name="Gallery (all)")
                    gal.run()
        except Exception as e:
            QMessageBox.critical(self, "Gallery", str(e))
        finally:
            if was_on: self.on_toggle_preview()

    def on_open_editor(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        if path:
            QMessageBox.information(self, "Editor", f"Selected:\n{path}\n(Integrate image_tools.py here if desired.)")

    # ---------- live controls ----------
    def on_set_zoom(self):
        val, ok = QInputDialog.getInt(self, "Zoom", "Zoom (%)", int(self.lv_zoom * 100), 100, 1000, 5)
        if ok: self.lv_zoom = self._clamp(val / 100.0, 1.0, 10.0)

    def on_set_contrast(self):
        val, ok = QInputDialog.getDouble(self, "Contrast (alpha)", "0.2 – 3.0", self.lv_contrast, 0.2, 3.0, 2)
        if ok: self.lv_contrast = self._clamp(val, 0.2, 3.0)

    def on_set_sharpness(self):
        val, ok = QInputDialog.getDouble(self, "Sharpness", "0.0 – 3.0", self.lv_sharpness, 0.0, 3.0, 2)
        if ok: self.lv_sharpness = self._clamp(val, 0.0, 3.0)

    def on_set_gamma(self):
        val, ok = QInputDialog.getDouble(self, "Gamma (display-only)", "0.2 – 3.0", self.lv_gamma, 0.2, 3.0, 2)
        if ok: self.lv_gamma = self._clamp(val, 0.2, 3.0)

    def on_cycle_filter(self):
        self.lv_filter_idx = (self.lv_filter_idx + 1) % len(self.lv_filters)
        self.status.showMessage(f"Filter → {self.lv_filters[self.lv_filter_idx]}")

    def on_reset_view(self):
        self.lv_zoom = 1.0
        self.lv_contrast = 1.0
        self.lv_sharpness = 0.0
        self.lv_gamma = 1.0
        self.lv_filter_idx = 0
        self.status.showMessage("View reset")

    # ---------- live processing pipeline (like image_tools.Editor.render) ----------
    def apply_pipeline(self, gray: np.ndarray) -> np.ndarray:
        img = gray
        h, w = img.shape[:2]
        if not self._center_inited:
            self.lv_cx, self.lv_cy = w // 2, h // 2
            self._center_inited = True

        # Zoom & pan (centered on lv_cx, lv_cy)
        if self.lv_zoom > 1.0:
            hw = int((w / self.lv_zoom) / 2)
            hh = int((h / self.lv_zoom) / 2)
            x1 = max(0, min(w - 1, self.lv_cx - hw))
            y1 = max(0, min(h - 1, self.lv_cy - hh))
            x2 = max(0, min(w,     self.lv_cx + hw))
            y2 = max(0, min(h,     self.lv_cy + hh))
            crop = img[y1:y2, x1:x2]
            if crop.size:
                img = cv2.resize(crop, (w, h), interpolation=cv2.INTER_CUBIC)

        # Contrast (alpha around 128)
        if abs(self.lv_contrast - 1.0) > 1e-3:
            img = cv2.convertScaleAbs(img, alpha=self.lv_contrast, beta=(1 - self.lv_contrast) * 128)

        # Gamma (display-only)
        if abs(self.lv_gamma - 1.0) > 1e-3:
            inv = 1.0 / max(self.lv_gamma, 1e-6)
            lut = np.array([((i / 255.0) ** inv) * 255.0 for i in range(256)], dtype=np.uint8)
            img = cv2.LUT(img, lut)

        # Sharpness (unsharp mask)
        if self.lv_sharpness > 0:
            blur = cv2.GaussianBlur(img, (0, 0), sigmaX=1.0 + self.lv_sharpness)
            img = cv2.addWeighted(img, 1 + self.lv_sharpness, blur, -self.lv_sharpness, 0)

        # Filters
        f = self.lv_filters[self.lv_filter_idx]
        if f == "invert":
            img = 255 - img
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif f == "equalize":
            img = cv2.equalizeHist(img)
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif f == "clahe":
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img = clahe.apply(img)
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif f == "edges":
            edges = cv2.Canny(img, 50, 150)
            img = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        elif f == "magma":
            img = cv2.applyColorMap(img, cv2.COLORMAP_MAGMA)  # BGR
            return img
        else:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        return img

    # ---------- preview tick ----------
    def update_frame(self):
        try:
            gray = self.backend.grab_gray()
        except Exception as e:
            self.timer.stop()
            self.preview_on = False
            self.alarm.setText(f"Error: {e}")
            return

        disp_bgr = self.apply_pipeline(gray)
        h, w = disp_bgr.shape[:2]
        qimg = QImage(disp_bgr.data, w, h, 3 * w, QImage.Format.Format_BGR888)
        px = QPixmap.fromImage(qimg).scaled(
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
