import sys, time
from pathlib import Path

# ----------------------------------------------------------
# Ensure project root is in PYTHONPATH
# ----------------------------------------------------------
_here = Path(__file__).resolve()
project_root = _here.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ----------------------------------------------------------
# Normal imports
# ----------------------------------------------------------
import numpy as np
import cv2
import RPi.GPIO as GPIO

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QToolButton, QStatusBar, QFileDialog,
    QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QImage

# Project modules
from xavier.io_utils import capture_and_save_frame
from xavier.gallery import Gallery
from xavier.leds import LedPanel
from xavier import gpio_estop
from xavier.relay import hv_on, hv_off
from xavier.camera_picam2 import Picamera2

# ⭐ Correct stepper functions
from xavier.stepper_Motor import (
    motor1_forward_until_switch2,
    motor1_backward_until_switch1,
    motor2_home_to_limit3,
    motor2_move_full_up,
    motor3_rotate_45
)


# ============================================================
# CAMERA BACKEND
# ============================================================
class PiCamBackend:
    def __init__(self, preview_size=(1280,720), still_size=(1920,1080)):
        self.preview_size = preview_size
        self.still_size = still_size
        self.cam = None
        self._mode = "stopped"

    def start(self):
        self.cam = Picamera2()
        self.preview_cfg = self.cam.create_preview_configuration(
            main={"size": self.preview_size}
        )
        self.still_cfg = self.cam.create_still_configuration(
            main={"size": self.still_size}
        )
        self.cam.configure(self.preview_cfg)
        self.cam.start()
        time.sleep(0.1)
        self._mode = "preview"

    def stop(self):
        if self.cam:
            try: self.cam.stop()
            except: pass
            try: self.cam.close()
            except: pass
        self.cam = None
        self._mode = "stopped"

    def _ensure(self):
        if self.cam is None:
            raise RuntimeError("Camera not started")

    def grab_bgr(self):
        self._ensure()
        frame = self.cam.capture_array("main")
        if frame.ndim == 2:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def capture_still_bgr(self):
        self._ensure()
        self.cam.switch_mode(self.still_cfg)
        img = self.cam.capture_array("main")
        try:    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        except: pass
        self.cam.switch_mode(self.preview_cfg)
        return img


# ============================================================
# MAIN WINDOW
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

        # -----------------------------
        # GUI ELEMENTS
        # -----------------------------
        self.alarm = QLabel("OK", alignment=Qt.AlignmentFlag.AlignCenter)
        self.view  = QLabel("Camera View", alignment=Qt.AlignmentFlag.AlignCenter)

        self.btn_preview = QPushButton("Preview")
        self.btn_stop    = QPushButton("STOP")
        self.btn_export  = QPushButton("Export Last")
        self.btn_gallery = QPushButton("Gallery")
        self.btn_xray    = QPushButton("XRAY Photo")

        # ⭐ Motor Buttons (all enabled)
        self.btn_open  = QPushButton("OPEN (Motor1)")
        self.btn_close = QPushButton("CLOSE (Motor1)")
        self.btn_align = QPushButton("ALIGN SAMPLE (Motor2)")
        self.btn_rotate = QPushButton("Rotate 45° (Motor3)")

        # Layout
        central = QWidget()
        root = QHBoxLayout(central)

        left = QVBoxLayout()
        for b in (
            self.btn_preview, self.btn_stop,
            self.btn_export, self.btn_gallery,
            self.btn_xray,
            self.btn_open, self.btn_close,
            self.btn_align,
            self.btn_rotate
        ):
            left.addWidget(b)
        left.addStretch()

        center = QVBoxLayout()
        center.addWidget(self.alarm)
        center.addWidget(self.view,1)

        root.addLayout(left)
        root.addLayout(center,1)
        self.setCentralWidget(central)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # -----------------------------
        # SIGNALS
        # -----------------------------
        self.btn_preview.clicked.connect(self.on_preview)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_export.clicked.connect(self.on_export)
        self.btn_gallery.clicked.connect(self.on_gallery)
        self.btn_xray.clicked.connect(self.on_xray)

        self.btn_open.clicked.connect(self.on_open_motor)
        self.btn_close.clicked.connect(self.on_close_motor)
        self.btn_align.clicked.connect(self.on_align_sample)
        self.btn_rotate.clicked.connect(self.on_rotate45)

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
    # MOTOR BUTTONS
    # ============================================================
    def on_open_motor(self):
        self.alarm.setText("Opening...")
        motor1_backward_until_switch1()
        self.alarm.setText("OPEN reached")

    def on_close_motor(self):
        self.alarm.setText("Closing...")
        motor1_forward_until_switch2()
        self.alarm.setText("CLOSED")

    def on_align_sample(self):
        self.alarm.setText("Aligning sample…")
        motor2_home_to_limit3()
        motor2_move_full_up()
        self.alarm.setText("Aligned")

    def on_rotate45(self):
        self.alarm.setText("Rotating 45°…")
        motor3_rotate_45()
        self.alarm.setText("Done.")

    # ============================================================
    # E-STOP HANDLING
    # ============================================================
    def check_estop(self):
        if gpio_estop.faulted():
            self.alarm.setText("E-STOP TRIGGERED")
            for b in (
                self.btn_preview, self.btn_export, self.btn_xray,
                self.btn_open, self.btn_close,
                self.btn_align, self.btn_rotate
            ):
                b.setEnabled(False)
        else:
            for b in (
                self.btn_preview, self.btn_export, self.btn_xray,
                self.btn_open, self.btn_close,
                self.btn_align, self.btn_rotate
            ):
                b.setEnabled(True)
            self.alarm.setText("OK")

    # ============================================================
    # CAMERA CONTROLS
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

    def on_xray(self):
        if gpio_estop.faulted():
            return
        self.alarm.setText("Capturing XRAY…")
        hv_on()
        time.sleep(0.5)
        img = self.backend.capture_still_bgr()
        hv_off()
        path,_ = capture_and_save_frame(img, save_dir="captures")
        self.alarm.setText(f"Saved {path}")

    def on_export(self):
        img = self.backend.grab_bgr()
        path,_ = capture_and_save_frame(img, save_dir="captures")
        self.status.showMessage(f"Saved {path}")

    def on_gallery(self):
        paths = sorted(Path("captures").glob("capture_*.png"))
        if not paths:
            QMessageBox.information(self,"Gallery","No images.")
            return
        Gallery([str(p) for p in paths]).run()

    # ============================================================
    # FRAME UPDATE
    # ============================================================
    def update_frame(self):
        if not self.preview_on:
            return
        img = self.backend.grab_bgr()
        h,w = img.shape[:2]
        q = QImage(img.data, w,h, 3*w, QImage.Format.Format_BGR888)
        px = QPixmap.fromImage(q).scaled(
            self.view.size(),
            Qt.AspectRatioMode.KeepAspectRatio
        )
        self.view.setPixmap(px)

    # ============================================================
    def update_leds(self, *, hv=False, fault=False, preview=False, armed=False):
        state = "IDLE"
        if fault: state="FAULT"
        elif preview: state="PREVIEW"
        elif hv: state="EXPOSE"
        elif armed: state="ARMED"
        self.leds.apply(alarm=fault, interlocks_ok=not fault, state=state)


# ============================================================
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
