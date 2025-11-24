import sys
from pathlib import Path
import time
import serial
import RPi.GPIO as GPIO
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

# ============================================================
# PROJECT PATHING
# ============================================================
_here = Path(__file__).resolve()
_root = None
for parent in [_here.parent, *_here.parents]:
    if (parent / "xavier").is_dir():
        _root = parent
        break
if _root is None:
    raise RuntimeError("Could not find project root.")
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# ============================================================
# PROJECT IMPORTS
# ============================================================
from xavier.io_utils import capture_and_save_frame
from xavier.gallery import Gallery
from xavier import gpio_estop
from xavier.relayy import hv_on, hv_off
from xavier.leds import LedPanel
from xavier.stepper_Motor import motor3_rotate_45   # <-- NEW

# ============================================================
# GPIO & SERIAL SETUP
# ============================================================
GPIO.setmode(GPIO.BCM)

SW1 = 17  # OPEN limit
SW2 = 24  # CLOSE limit
GPIO.setup(SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Arduino M1 controller
try:
    ser = serial.Serial('/dev/ttyACM1', 115200, timeout=1)
    time.sleep(2)
except:
    ser = None
    print("WARNING: Arduino not found on /dev/ttyACM1")


# ============================================================
# STEPPER (Motor 1) CONTROL FUNCTIONS
# ============================================================
def motor1_forward_until_sw1():
    """OPEN: run M1 forward until SW1 hits (LOW)."""
    if ser is None:
        print("No serial connection to Arduino.")
        return

    print("Motor 1 → FORWARD (OPEN)")
    while GPIO.input(SW1) == 1:
        ser.write(b"M1F\n")
        time.sleep(0.002)

    print("Reached SW1 (OPEN limit).")


def motor1_backward_until_sw2():
    """CLOSE: run M1 backward until SW2 hits (LOW)."""
    if ser is None:
        print("No serial connection to Arduino.")
        return

    print("Motor 1 → BACKWARD (CLOSE)")
    while GPIO.input(SW2) == 1:
        ser.write(b"M1B\n")
        time.sleep(0.002)

    print("Reached SW2 (CLOSE limit).")


# ============================================================
# CAMERA BACKEND
# ============================================================
from picamera2 import Picamera2

class PiCamBackend:
    def __init__(self, preview_size=(1280,720), still_size=(1920,1080)):
        self.preview_size = preview_size
        self.still_size   = still_size
        self.cam = None
        self._mode = "stopped"

    def start(self):
        self.cam = Picamera2()
        self.preview_cfg = self.cam.create_preview_configuration(main={"size": self.preview_size})
        self.still_cfg = self.cam.create_still_configuration(main={"size": self.still_size})
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
        time.sleep(0.2)

    def grab_gray(self):
        if self._mode != "preview":
            self.cam.switch_mode(self.preview_cfg)
            self._mode = "preview"
        frame = self.cam.capture_array("main")
        if frame.ndim == 2:
            return frame
        return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

    def capture_still_bgr(self):
        self.cam.switch_mode(self.still_cfg)
        frame = self.cam.capture_array("main")
        try:
            out = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except:
            out = frame
        self.cam.switch_mode(self.preview_cfg)
        return out


# ============================================================
# GUI WINDOW
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IC X-Ray GUI")
        self.resize(1280, 720)

        self.leds = LedPanel()

        # ---- CAMERA ----
        self.backend = PiCamBackend()
        self.backend.start()
        self.preview_on = False

        # ---- LIMIT LABEL ----
        self.alarm = QLabel("OK", alignment=Qt.AlignCenter)

        # ---- CAMERA VIEW ----
        self.view = QLabel("Camera", alignment=Qt.AlignCenter)
        self.view.setMinimumSize(960,540)

        # ---- BUTTONS ----
        self.btn_preview = QPushButton("Preview")
        self.btn_stop    = QPushButton("STOP")
        self.btn_gallery = QPushButton("Gallery")
        self.btn_export  = QPushButton("Export Last")
        self.btn_xray    = QPushButton("XRAY Photo")

        # ⭐ NEW:
        self.btn_open  = QPushButton("OPEN (Motor 1)")
        self.btn_close = QPushButton("CLOSE (Motor 1)")
        self.btn_rotate = QPushButton("Rotate Sample 45° (Motor 3)")

        # ---- Layout ----
        left = QVBoxLayout()
        left.addWidget(self.btn_preview)
        left.addWidget(self.btn_stop)
        left.addWidget(self.btn_gallery)
        left.addWidget(self.btn_export)
        left.addWidget(self.btn_xray)
        left.addSpacing(20)
        left.addWidget(self.btn_open)
        left.addWidget(self.btn_close)
        left.addWidget(self.btn_rotate)
        left.addStretch(1)

        center = QVBoxLayout()
        center.addWidget(self.alarm)
        center.addWidget(self.view)

        root = QHBoxLayout()
        root.addLayout(left)
        root.addLayout(center, 1)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        # ---- TIMERS ----
        self.timer = QTimer()
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update_frame)

        # ---- CONNECT ----
        self.btn_preview.clicked.connect(self.on_preview)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_export.clicked.connect(self.on_export_last)
        self.btn_gallery.clicked.connect(self.on_gallery)
        self.btn_xray.clicked.connect(self.on_xray_photo)

        # ⭐ NEW motor controls
        self.btn_open.clicked.connect(self.on_open)
        self.btn_close.clicked.connect(self.on_close)
        self.btn_rotate.clicked.connect(self.on_rotate)

    # ============================================================
    # CAMERA ACTIONS
    # ============================================================
    def on_preview(self):
        if not self.preview_on:
            self.preview_on = True
            self.timer.start()
        self.alarm.setText("Preview ON")

    def on_stop(self):
        self.preview_on = False
        self.timer.stop()
        self.backend.stop()
        self.alarm.setText("STOP")

    def update_frame(self):
        try:
            gray = self.backend.grab_gray()
        except:
            return
        disp = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        h,w = disp.shape[:2]
        qimg = QImage(disp.data, w, h, 3*w, QImage.Format_BGR888)
        px = QPixmap.fromImage(qimg).scaled(
            self.view.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.view.setPixmap(px)

    # ============================================================
    # XRAY PHOTO
    # ============================================================
    def on_xray_photo(self):
        if not self.preview_on:
            QMessageBox.warning(self, "XRAY", "Preview must be ON.")
            return
        img = self.backend.capture_still_bgr()
        path, _ = capture_and_save_frame(img, save_dir="captures")
        self.alarm.setText(f"Saved: {path}")

    # ============================================================
    # EXPORT / GALLERY
    # ============================================================
    def on_export_last(self):
        img = self.backend.capture_still_bgr()
        path, _ = capture_and_save_frame(img, save_dir="captures")
        self.alarm.setText(f"Saved: {path}")

    def on_gallery(self):
        all_paths = sorted(Path("captures").glob("*.png"))
        if not all_paths:
            QMessageBox.information(self, "Gallery", "No images.")
            return
        gal = Gallery([str(p) for p in all_paths])
        gal.run()

    # ============================================================
    # MOTOR ACTIONS
    # ============================================================
    def on_open(self):
        self.alarm.setText("Opening…")
        QApplication.processEvents()
        motor1_forward_until_sw1()
        self.alarm.setText("OPEN complete.")

    def on_close(self):
        self.alarm.setText("Closing…")
        QApplication.processEvents()
        motor1_backward_until_sw2()
        self.alarm.setText("CLOSED.")

    def on_rotate(self):
        self.alarm.setText("Rotating sample 45°…")
        QApplication.processEvents()
        motor3_rotate_45()
        self.alarm.setText("Rotation done.")


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
