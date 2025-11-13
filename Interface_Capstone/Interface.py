import sys
from pathlib import Path
import time

# ------------------------------------------------------------------
# Locate the project root (folder containing 'xavier')
# ------------------------------------------------------------------
_here = Path(__file__).resolve()
_root = None
for parent in [_here.parent, *_here.parents]:
    if (parent / "xavier").is_dir():
        _root = parent
        break
if _root is None:
    raise RuntimeError("Could not find the 'xavier' folder.")
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# ------------------------------------------------------------------
# Require Picamera2 (NO webcam fallback)
# ------------------------------------------------------------------
try:
    from picamera2 import Picamera2
except Exception as e:
    print("ERROR: Picamera2 required. Install on Pi: sudo apt install -y python3-picamera2")
    print("Details:", e)
    sys.exit(1)

import numpy as np
import cv2

# Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QToolButton, QStatusBar, QFileDialog,
    QMessageBox, QInputDialog, QMenuBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QAction

# ------------------------------------------------------------------
# Project helpers
# ------------------------------------------------------------------
from xavier.io_utils import capture_and_save_frame
from xavier.gallery import Gallery
from xavier import gpio_estop
from xavier.relayy import hv_on, hv_off

# HV timing (match your main.py)
PRE_ROLL_S = 0.5
POST_HOLD_S = 0.5

# ULN2003 stepper settings (from your ULN2003 test)
ULN_PINS_BCM = (16, 6, 5, 12)
ULN_STEP_SLEEP = 0.003
ULN_SEQUENCE = [
    [1,0,0,1], [1,0,0,0], [1,1,0,0], [0,1,0,0],
    [0,1,1,0], [0,0,1,0], [0,0,1,1], [0,0,0,1]
]
ULN_STEPS_PER_REV = 4096
ULN_STEPS_90 = ULN_STEPS_PER_REV // 4




# ============================================================
# PICAMERA BACKEND
# ============================================================
class PiCamBackend:
    def __init__(self, preview_size=(1280, 720), still_size=(1920, 1080)):
        self.preview_size = preview_size
        self.still_size   = still_size
        self.cam: Picamera2 | None = None
        self._mode = "stopped"

    def start(self):
        self.cam = Picamera2()
        self.preview_cfg = self.cam.create_preview_configuration(main={"size": self.preview_size})
        self.still_cfg   = self.cam.create_still_configuration(main={"size": self.still_size})
        self.cam.configure(self.preview_cfg)
        self.cam.start()
        self._mode = "preview"
        time.sleep(0.1)

    def stop(self):
        if self.cam:
            try: self.cam.stop()
            except: pass
            try: self.cam.close()
            except: pass
        self.cam = None
        self._mode = "stopped"
        time.sleep(0.2)

    def _ensure_running(self):
        if self.cam is None:
            raise RuntimeError("Picamera2 not started")

    def _switch_mode(self, mode):
        self._ensure_running()
        if mode == self._mode:
            return
        cfg = self.preview_cfg if mode == "preview" else self.still_cfg
        try:
            self.cam.switch_mode(cfg)
        except Exception:
            try: self.cam.stop()
            except: pass
            self.cam.configure(cfg)
            self.cam.start()
        self._mode = mode
        time.sleep(0.05)

    def grab_gray(self) -> np.ndarray:
        self._ensure_running()
        if self._mode != "preview":
            self._switch_mode("preview")
        frame = self.cam.capture_array("main")
        if frame.ndim == 2:
            return frame
        try:
            return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        except:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def grab_bgr(self) -> np.ndarray:
        self._ensure_running()
        if self._mode != "preview":
            self._switch_mode("preview")
        frame = self.cam.capture_array("main")
        if frame.ndim == 2:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        try:
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except:
            return frame

    def capture_still_bgr(self):
        self._ensure_running()
        self._switch_mode("still")
        frame = self.cam.capture_array("main")
        if frame.ndim == 2:
            img = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        else:
            try:
                img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            except:
                img = frame
        self._switch_mode("preview")
        return img




# ============================================================
# MAIN GUI
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("IC X-ray Viewer — IMX415 (Picamera2)")
        self.resize(1280, 720)

        # Session state
        self.session_paths = []
        self.last_path = None
        self.save_dir = "captures"
        self.export_processed = False

        # Top banner
        self.alarm = QLabel("OK", alignment=Qt.AlignmentFlag.AlignCenter, objectName="alarmBar")

        # Camera display
        self.view = QLabel("Camera View", alignment=Qt.AlignmentFlag.AlignCenter, objectName="cameraView")
        self.view.setMinimumSize(960, 540)

        # Left column buttons
        self.btn_preview = QPushButton("Preview")
        self.btn_stop    = QPushButton("STOP", objectName="btnStop")
        self.btn_gallery = QPushButton("Gallery")
        self.btn_export  = QPushButton("Export Last")
        self.btn_xray    = QPushButton("XRAY Photo")
        self.btn_twist   = QPushButton("Twist 90°")
        self.btn_editor  = QPushButton("Open Editor")

        # Display controls
        tools_box = QGroupBox("Display Controls")
        tlay = QVBoxLayout(tools_box)
        self.tb_zoom     = QToolButton(text="Zoom")
        self.tb_contrast = QToolButton(text="Contrast")
        self.tb_sharp    = QToolButton(text="Sharpness")
        self.tb_gamma    = QToolButton(text="Gamma")
        self.tb_filter   = QToolButton(text="Filter")
        self.tb_reset    = QToolButton(text="Reset View")
        for b in (self.tb_zoom, self.tb_contrast, self.tb_sharp, self.tb_gamma, self.tb_filter, self.tb_reset):
            tlay.addWidget(b)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # ----------- Menu ----------
        menu = self.menuBar() or QMenuBar(self)
        act_prev  = QAction("Toggle Preview", self, shortcut="P")
        act_stop  = QAction("STOP", self, shortcut="S")
        act_exp   = QAction("Export Last", self, shortcut="Ctrl+S")
        act_gal   = QAction("Gallery", self, shortcut="G")
        act_mode  = QAction("Toggle Export Mode", self, shortcut="Ctrl+E")
        act_xray  = QAction("XRAY Photo", self, shortcut="Ctrl+X")
        self.addActions([act_prev, act_stop, act_exp, act_gal, act_mode, act_xray])
        act_prev.triggered.connect(self.on_toggle_preview)
        act_stop.triggered.connect(self.on_stop)
        act_exp.triggered.connect(self.on_export_last)
        act_gal.triggered.connect(self.on_gallery)
        act_mode.triggered.connect(self.on_toggle_export_mode)
        act_xray.triggered.connect(self.on_xray_photo)

        # Layout root
        central = QWidget(self)
        root = QHBoxLayout(central)

        left = QVBoxLayout()
        for b in (self.btn_preview, self.btn_stop, self.btn_gallery,
                  self.btn_export, self.btn_xray, self.btn_twist, self.btn_editor):
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

        # Styling
        self.setStyleSheet("""
        QLabel#alarmBar {
            background:#e9fbf0; color:#2f7a43; border-radius:12px;
            padding:6px; border:1px solid #e6eaf0;
        }
        QLabel#cameraView {
            background:white; border-radius:16px;
            border:1px solid #e6eaf0;
        }
        QPushButton#btnStop {
            background:#ff6b6b; color:white; font-weight:700;
            border-radius:14px;
        }
        """)

        # Camera backend
        self.backend = PiCamBackend()
        self.backend.start()
        self.preview_on = False

        # Preview refresh timer
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update_frame)

        # E-stop polling timer
        self.estop_timer = QTimer(self)
        self.estop_timer.setInterval(100)
        self.estop_timer.timeout.connect(self.check_estop)
        self.estop_timer.start()

        # Display params
        self.lv_zoom = 1.0
        self.lv_cx, self.lv_cy = 640, 360
        self.lv_contrast = 1.0
        self.lv_sharpness = 0.0
        self.lv_gamma = 1.0
        self.lv_filter_idx = 0
        self.filters = ["none", "invert", "equalize", "clahe", "edges", "magma"]
        self._center_init = False

        # Connect buttons
        self.btn_preview.clicked.connect(self.on_toggle_preview)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_gallery.clicked.connect(self.on_gallery)
        self.btn_export.clicked.connect(self.on_export_last)
        self.btn_xray.clicked.connect(self.on_xray_photo)
        self.btn_twist.clicked.connect(self.on_uln_twist)
        self.btn_editor.clicked.connect(self.on_open_editor)

        self.tb_zoom.clicked.connect(self.on_set_zoom)
        self.tb_contrast.clicked.connect(self.on_set_contrast)
        self.tb_sharp.clicked.connect(self.on_set_sharpness)
        self.tb_gamma.clicked.connect(self.on_set_gamma)
        self.tb_filter.clicked.connect(self.on_cycle_filter)
        self.tb_reset.clicked.connect(self.on_reset_view)

        # Track previous E-stop state
        self._prev_estop_fault = False


    # ============================================================
    # E-STOP MONITOR
    # ============================================================
    def check_estop(self):
        try:
            latched = gpio_estop.faulted()
        except:
            latched = False

        if latched:
            # NEW MESSAGE YOU REQUESTED:
            self.alarm.setText("E-STOP FAULT — Reset latch manually on the hardware.")
            self.alarm.setStyleSheet("background:#ffe9e9;color:#7a2f2f;"
                                     "border-radius:12px;padding:6px;"
                                     "border:1px solid #f3b8b8;")

            # Disable dangerous buttons
            for b in (self.btn_preview, self.btn_export, self.btn_xray, self.btn_twist):
                b.setEnabled(False)

            self._prev_estop_fault = True

        else:
            # If fault was previously active and now is cleared → show message:
            if self._prev_estop_fault:
                self.alarm.setText("Safety latch has been reset.")
                self.alarm.setStyleSheet("background:#e9fbf0;color:#2f7a43;"
                                         "border-radius:12px;padding:6px;"
                                         "border:1px solid #e6eaf0;")
            else:
                self.alarm.setText("OK")
                self.alarm.setStyleSheet("")

            for b in (self.btn_preview, self.btn_export, self.btn_xray, self.btn_twist):
                b.setEnabled(True)

            self._prev_estop_fault = False


    # ============================================================
    # BUTTON ACTIONS
    # ============================================================
    def on_toggle_preview(self):
        if not self.preview_on:
            if self.backend.cam is None:
                self.backend.start()
            self.preview_on = True
            self.timer.start()
            self.alarm.setText("Preview: ON")
        else:
            self.preview_on = False
            self.timer.stop()
            self.alarm.setText("Preview: OFF")

    def on_stop(self):
        self.preview_on = False
        self.timer.stop()
        self.backend.stop()
        self.alarm.setText("STOP PRESSED!")

    def on_toggle_export_mode(self):
        self.export_processed = not self.export_processed
        mode = "PROCESSED" if self.export_processed else "RAW"
        self.status.showMessage(f"Export Mode: {mode}")

    def on_export_last(self):
        if not self.preview_on:
            QMessageBox.information(self, "Export", "Start preview first.")
            return
        try:
            if self.export_processed:
                gray = self.backend.grab_gray()
                disp = self.apply_pipeline(gray)
                path, _ = capture_and_save_frame(disp, save_dir=self.save_dir)
            else:
                bgr = self.backend.grab_bgr()
                path, _ = capture_and_save_frame(bgr, save_dir=self.save_dir)

            self.session_paths.append(path)
            self.last_path = Path(path)
            self.status.showMessage(f"Saved: {path}")

        except Exception as e:
            QMessageBox.critical(self, "Export", str(e))

    def on_gallery(self):
        if self.session_paths:
            gal = Gallery(self.session_paths, window_name="Gallery (session)")
            gal.run(start_at=str(self.last_path) if self.last_path else None)
        else:
            all_paths = sorted(Path(self.save_dir).glob("capture_*.png"))
            if not all_paths:
                QMessageBox.information(self, "Gallery", "No images found.")
                return
            gal = Gallery([str(p) for p in all_paths], window_name="Gallery (all)")
            gal.run()

    def on_open_editor(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        if path:
            QMessageBox.information(self, "Editor",
                f"You selected:\n{path}\nIntegrate image_tools if desired.")

    # ============================================================
    # XRAY PHOTO (HV CONTROL)
    # ============================================================
    def on_xray_photo(self):
        try:
            if gpio_estop.faulted():
                QMessageBox.warning(self, "XRAY", "Cannot capture: E-STOP latched.")
                return
        except:
            pass

        was_on = self.preview_on
        if was_on:
            self.on_toggle_preview()

        self.alarm.setText("XRAY: Arming HV…")
        QApplication.processEvents()

        try:
            # HV ON
            hv_on()
            t0 = time.time()
            self.alarm.setText("XRAY: HV ON (pre-roll)")
            while time.time() - t0 < PRE_ROLL_S:
                QApplication.processEvents()
                if gpio_estop.faulted():
                    raise RuntimeError("E-STOP triggered during pre-roll")
                time.sleep(0.01)

            # Capture still
            self.alarm.setText("XRAY: Capturing…")
            img_bgr = self.backend.capture_still_bgr()
            path, _ = capture_and_save_frame(img_bgr, save_dir=self.save_dir)
            self.session_paths.append(path)
            self.last_path = Path(path)
            self.status.showMessage(f"[XRAY] Saved: {path}")

            # Post hold
            t1 = time.time()
            self.alarm.setText("XRAY: post-hold")
            while time.time() - t1 < POST_HOLD_S:
                QApplication.processEvents()
                if gpio_estop.faulted():
                    raise RuntimeError("E-STOP triggered during post-hold")
                time.sleep(0.01)

        except Exception as e:
            QMessageBox.critical(self, "XRAY", str(e))
        finally:
            try: hv_off()
            except: pass
            self.alarm.setText("XRAY: HV OFF")

            if was_on:
                self.on_toggle_preview()



    # ============================================================
    # ULN2003 TWIST 90° + RETURN
    # ============================================================
    def on_uln_twist(self):
        try:
            import RPi.GPIO as GPIO
        except Exception as e:
            QMessageBox.critical(self, "Stepper", str(e))
            return

        self.alarm.setText("Stepper: +90°, then return…")
        QApplication.processEvents()

        try:
            GPIO.setmode(GPIO.BCM)
            for pin in ULN_PINS_BCM:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)

            def step(values):
                for pin, val in zip(ULN_PINS_BCM, values):
                    GPIO.output(pin, GPIO.HIGH if val else GPIO.LOW)
                time.sleep(ULN_STEP_SLEEP)

            # forward 90
            idx = 0
            for _ in range(ULN_STEPS_90):
                step(ULN_SEQUENCE[idx])
                idx = (idx + 1) % 8

            # backward 90
            for _ in range(ULN_STEPS_90):
                step(ULN_SEQUENCE[idx])
                idx = (idx - 1) % 8

        except Exception as e:
            QMessageBox.critical(self, "Stepper", str(e))
        finally:
            try:
                for pin in ULN_PINS_BCM:
                    GPIO.output(pin, GPIO.LOW)
                GPIO.cleanup()
            except:
                pass
            self.alarm.setText("Stepper: done")



    # ============================================================
    # DISPLAY CONTROLS
    # ============================================================
    def on_set_zoom(self):
        v, ok = QInputDialog.getInt(self, "Zoom", "Zoom (%)",
            int(self.lv_zoom*100), 100, 1000, 10)
        if ok: self.lv_zoom = max(1.0, min(v/100.0, 10.0))

    def on_set_contrast(self):
        v, ok = QInputDialog.getDouble(self, "Contrast", "0.2–3.0",
            self.lv_contrast, 0.2, 3.0, 2)
        if ok: self.lv_contrast = v

    def on_set_sharpness(self):
        v, ok = QInputDialog.getDouble(self, "Sharpness", "0.0–3.0",
            self.lv_sharpness, 0.0, 3.0, 2)
        if ok: self.lv_sharpness = v

    def on_set_gamma(self):
        v, ok = QInputDialog.getDouble(self, "Gamma", "0.2–3.0",
            self.lv_gamma, 0.2, 3.0, 2)
        if ok: self.lv_gamma = v

    def on_cycle_filter(self):
        self.lv_filter_idx = (self.lv_filter_idx + 1) % len(self.filters)
        self.status.showMessage(f"Filter: {self.filters[self.lv_filter_idx]}")

    def on_reset_view(self):
        self.lv_zoom = 1.0
        self.lv_contrast = 1.0
        self.lv_sharpness = 0.0
        self.lv_gamma = 1.0
        self.lv_filter_idx = 0
        self.status.showMessage("View reset.")



    # ============================================================
    # LIVE PROCESSING PIPELINE
    # ============================================================
    def apply_pipeline(self, gray):
        img = gray
        h, w = img.shape[:2]

        # Lazy center init
        if not self._center_init:
            self.lv_cx, self.lv_cy = w//2, h//2
            self._center_init = True

        # Zoom crop
        if self.lv_zoom > 1.0:
            hw = int((w / self.lv_zoom) / 2)
            hh = int((h / self.lv_zoom) / 2)
            x1 = max(0, self.lv_cx - hw)
            y1 = max(0, self.lv_cy - hh)
            x2 = min(w, self.lv_cx + hw)
            y2 = min(h, self.lv_cy + hh)
            crop = img[y1:y2, x1:x2]
            if crop.size:
                img = cv2.resize(crop, (w, h), interpolation=cv2.INTER_CUBIC)

        # Contrast
        if abs(self.lv_contrast - 1.0) > 1e-3:
            img = cv2.convertScaleAbs(img, alpha=self.lv_contrast,
                                      beta=(1 - self.lv_contrast) * 128)

        # Gamma
        if abs(self.lv_gamma - 1.0) > 1e-3:
            inv = 1.0 / max(self.lv_gamma, 1e-6)
            lut = np.array([((i/255.0)**inv)*255 for i in range(256)],
                           dtype=np.uint8)
            img = cv2.LUT(img, lut)

        # Sharpness
        if self.lv_sharpness > 0:
            blur = cv2.GaussianBlur(img, (0,0), 1 + self.lv_sharpness)
            img = cv2.addWeighted(img, 1 + self.lv_sharpness,
                                  blur, -self.lv_sharpness, 0)

        # Filters
        f = self.filters[self.lv_filter_idx]
        if f == "invert":
            img = 255 - img
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif f == "equalize":
            img = cv2.equalizeHist(img)
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif f == "clahe":
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            img = clahe.apply(img)
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif f == "edges":
            e = cv2.Canny(img, 50, 150)
            return cv2.cvtColor(e, cv2.COLOR_GRAY2BGR)
        elif f == "magma":
            return cv2.applyColorMap(img, cv2.COLORMAP_MAGMA)
        else:
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)



    # ============================================================
    # PREVIEW UPDATE
    # ============================================================
    def update_frame(self):
        try:
            gray = self.backend.grab_gray()
        except Exception as e:
            self.timer.stop()
            self.preview_on = False
            self.alarm.setText(f"Camera error: {e}")
            return

        disp = self.apply_pipeline(gray)
        h, w = disp.shape[:2]
        qimg = QImage(disp.data, w, h, 3*w, QImage.Format.Format_BGR888)
        px = QPixmap.fromImage(qimg).scaled(
            self.view.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.view.setPixmap(px)



# ============================================================
# MAIN
# ============================================================
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
