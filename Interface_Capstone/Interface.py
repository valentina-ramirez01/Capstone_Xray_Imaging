import sys
from pathlib import Path

# ------------------------------------------------------------------
# FIX: Ensure the project root (folder containing "xavier") is in sys.path
# ------------------------------------------------------------------
_here = Path(__file__).resolve()
project_root = _here.parent.parent   # Interface_Capstone -> Capstone_Xray_Imaging

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ------------------------------------------------------------------
# Normal imports AFTER sys.path is fixed
# ------------------------------------------------------------------
import time
import numpy as np
import cv2

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QToolButton, QStatusBar, QFileDialog,
    QMessageBox, QInputDialog, QMenuBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QAction

# Project helpers
from xavier.io_utils import capture_and_save_frame
from xavier.gallery import Gallery
from xavier import gpio_estop
from xavier.relay import hv_on, hv_off
from xavier.leds import LedPanel

# ⭐ NEW import — Pi-side stepper control
from xavier.stepper_Motor import (
    motor3_rotate_45,
    motor1_forward_until_limit,
    motor1_backward_until_limit
)

# Switch mapping for motor1 (already in stepper_Motor)
SW1 = 17
SW2 = 24

PRE_ROLL_S = 0.5
POST_HOLD_S = 0.5


# ============================================================
# PICAMERA BACKEND
# ============================================================
from xavier.camera_picam2 import Picamera2

class PiCamBackend:
    def __init__(self, preview_size=(1280,720), still_size=(1920,1080)):
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

    def _ensure(self):
        if self.cam is None:
            raise RuntimeError("Picamera2 not started")

    def _switch(self, mode):
        self._ensure()
        if mode == self._mode:
            return
        cfg = self.preview_cfg if mode == "preview" else self.still_cfg
        try:
            self.cam.switch_mode(cfg)
        except:
            try: self.cam.stop()
            except: pass
            self.cam.configure(cfg)
            self.cam.start()
        self._mode = mode
        time.sleep(0.05)

    def grab_gray(self):
        self._ensure()
        if self._mode != "preview":
            self._switch("preview")
        frame = self.cam.capture_array("main")
        if frame.ndim == 2:
            return frame
        return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

    def grab_bgr(self):
        self._ensure()
        if self._mode != "preview":
            self._switch("preview")
        frame = self.cam.capture_array("main")
        if frame.ndim == 2:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def capture_still_bgr(self):
        self._ensure()
        self._switch("still")
        img = self.cam.capture_array("main")
        try:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        except:
            pass
        self._switch("preview")
        return img


# ============================================================
# MAIN GUI
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("IC X-ray Viewer")
        self.resize(1280,720)

        self.leds = LedPanel()
        self.backend = PiCamBackend()
        self.backend.start()
        self.preview_on = False

        # ----------------------------
        # GUI WIDGETS
        # ----------------------------
        self.alarm = QLabel("OK", alignment=Qt.AlignmentFlag.AlignCenter)
        self.view  = QLabel("Camera", alignment=Qt.AlignmentFlag.AlignCenter)

        # Buttons
        self.btn_preview = QPushButton("Preview")
        self.btn_stop    = QPushButton("STOP")
        self.btn_gallery = QPushButton("Gallery")
        self.btn_export  = QPushButton("Export Last")
        self.btn_xray    = QPushButton("XRAY Photo")

        # ⭐ Motor controls
        self.btn_open  = QPushButton("OPEN")
        self.btn_close = QPushButton("CLOSE")
        self.btn_rotate = QPushButton("Rotate 45°")

        # ⭐ NEW: HV PULSE BUTTON
        self.btn_hv = QPushButton("HV Pulse")

        self.btn_editor = QPushButton("Open Editor")

        # Layout
        central = QWidget()
        root = QHBoxLayout(central)

        left = QVBoxLayout()
        for b in (
            self.btn_preview, self.btn_stop, self.btn_gallery,
            self.btn_export, self.btn_xray,
            self.btn_open, self.btn_close,
            self.btn_rotate,
            self.btn_hv,          # ⭐ Added cleanly
            self.btn_editor
        ):
            left.addWidget(b)
        left.addStretch()

        center = QVBoxLayout()
        center.addWidget(self.alarm)
        center.addWidget(self.view,1)

        right = QVBoxLayout()
        right.addStretch()

        root.addLayout(left)
        root.addLayout(center,1)
        root.addLayout(right)
        self.setCentralWidget(central)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # ----------------------------
        # SIGNALS
        # ----------------------------
        self.btn_preview.clicked.connect(self.on_preview)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_gallery.clicked.connect(self.on_gallery)
        self.btn_export.clicked.connect(self.on_export)
        self.btn_xray.clicked.connect(self.on_xray)

        self.btn_open.clicked.connect(self.on_open_motor)
        self.btn_close.clicked.connect(self.on_close_motor)
        self.btn_rotate.clicked.connect(self.on_rotate45)

        self.btn_hv.clicked.connect(self.on_hv_pulse)   # ⭐ NEW SIGNAL

        self.btn_editor.clicked.connect(self.on_open_editor)

        # Timers
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update_frame)

        self.estop_timer = QTimer(self)
        self.estop_timer.setInterval(100)
        self.estop_timer.timeout.connect(self.check_estop)
        self.estop_timer.start()

        self.update_leds()

    # ============================================================
    # MOTOR BUTTON ACTIONS
    # ============================================================
    def on_open_motor(self):
        self.alarm.setText("Opening...")
        motor1_forward_until_limit()
        self.alarm.setText("OPEN reached")

    def on_close_motor(self):
        self.alarm.setText("Closing...")
        motor1_backward_until_limit()
        self.alarm.setText("CLOSED")

    def on_rotate45(self):
        self.alarm.setText("Rotating 45°…")
        motor3_rotate_45()
        self.alarm.setText("Rotation complete")

    # ============================================================
    # HV 3-SECOND PULSE
    # ============================================================
    def on_hv_pulse(self):
        """Turn HV on for 3 seconds, then off."""
        if gpio_estop.faulted():
            self.alarm.setText("E-STOP TRIGGERED")
            return

        self.alarm.setText("HV ON…")
        self.update_leds(hv=True)
        hv_on()

        QApplication.processEvents()
        time.sleep(3)

        hv_off()
        self.update_leds(hv=False)
        self.alarm.setText("HV OFF")

    # ============================================================
    # E-STOP
    # ============================================================
    def check_estop(self):
        if gpio_estop.faulted():
            self.alarm.setText("E-STOP TRIGGERED")
            for b in (
                self.btn_preview, self.btn_export, self.btn_xray,
                self.btn_open, self.btn_close, self.btn_rotate, self.btn_hv
            ):
                b.setEnabled(False)
            return
        else:
            for b in (
                self.btn_preview, self.btn_export, self.btn_xray,
                self.btn_open, self.btn_close, self.btn_rotate, self.btn_hv
            ):
                b.setEnabled(True)
            self.alarm.setText("OK")

    # ============================================================
    # PREVIEW
    # ============================================================
    def on_preview(self):
        if not self.preview_on:
            self.preview_on = True
            self.timer.start()
            self.alarm.setText("Preview ON")
        else:
            self.preview_on = False
            self.timer.stop()
            self.alarm.setText("Preview OFF")

    def on_stop(self):
        self.preview_on = False
        self.timer.stop()
        self.backend.stop()
        self.alarm.setText("STOPPED")

    # ============================================================
    # XRAY PHOTO
    # ============================================================
    def on_xray(self):
        if gpio_estop.faulted():
            return

        self.alarm.setText("Arming HV…")
        hv_on()
        time.sleep(PRE_ROLL_S)

        img = self.backend.capture_still_bgr()
        path, _ = capture_and_save_frame(img, save_dir="captures")

        hv_off()
        self.alarm.setText(f"Saved {path}")

    # ============================================================
    # EXPORT / GALLERY / EDITOR
    # ============================================================
    def on_export(self):
        try:
            img = self.backend.grab_bgr()
            path, _ = capture_and_save_frame(img, save_dir="captures")
            self.status.showMessage(f"Saved {path}")
        except Exception as e:
            QMessageBox.critical(self,"Export",str(e))

    def on_gallery(self):
        all_paths = sorted(Path("captures").glob("capture_*.png"))
        if not all_paths:
            QMessageBox.information(self,"Gallery","No images found.")
            return
        Gallery([str(p) for p in all_paths]).run()

    def on_open_editor(self):
        QMessageBox.information(self,"Editor","Not implemented.")

    # ============================================================
    # LIVE FRAME UPDATE
    # ============================================================
    def update_frame(self):
        if not self.preview_on:
            return
        gray = self.backend.grab_gray()
        disp = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        h,w = disp.shape[:2]

        qimg = QImage(disp.data, w,h, 3*w, QImage.Format.Format_BGR888)
        px = QPixmap.fromImage(qimg).scaled(
            self.view.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.view.setPixmap(px)

    # ============================================================
    def update_leds(self, *, hv=False, fault=False, preview=False, armed=False):
        state="IDLE"
        if fault: state="FAULT"
        elif preview: state="PREVIEW"
        elif hv: state="EXPOSE"
        elif armed: state="ARMED"
        self.leds.apply(
            alarm=fault,
            interlocks_ok=not fault,
            state=state
        )


# ============================================================
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
