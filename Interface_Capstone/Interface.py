# Interface.py (FINAL)

import sys
from pathlib import Path

_here = Path(__file__).resolve()
project_root = _here.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import time
import numpy as np
import cv2

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStatusBar, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap

# Project imports
from xavier.io_utils import capture_and_save_frame
from xavier.gallery import Gallery
from xavier.relay import hv_on, hv_off
from xavier import gpio_estop
from xavier.leds import LedPanel
from xavier.camera_picam2 import Picamera2

# ⭐ Motor functions
from xavier.stepper_Motor import (
    motor3_rotate_45,
    motor2_align_sequence,
    SW2
)

# Motor-1 is Arduino-controlled:
# Raspberry sends: "M1F\n" or "M1B\n"
import serial
ser = serial.Serial('/dev/ttyACM1',115200,timeout=1)
time.sleep(2)

def motor1_forward_until_limit():
    while GPIO.input(18) == 1:  # SW2 close limit
        ser.write(b"M1F\n")
        time.sleep(0.002)

def motor1_backward_until_limit():
    while GPIO.input(17) == 1:  # SW1 open limit
        ser.write(b"M1B\n")
        time.sleep(0.002)


import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # SW1
GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # SW2
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # SW3


# ============================================================
# CAMERA BACKEND
# ============================================================
class Backend:
    def __init__(self):
        self.cam = Picamera2()
        self.preview_cfg = self.cam.create_preview_configuration(main={"size":(1280,720)})
        self.still_cfg   = self.cam.create_still_configuration(main={"size":(1920,1080)})
        self.cam.configure(self.preview_cfg)
        self.cam.start()
        time.sleep(0.1)

    def grab_gray(self):
        f = self.cam.capture_array("main")
        return cv2.cvtColor(f, cv2.COLOR_RGB2GRAY)

    def capture_still(self):
        self.cam.switch_mode(self.still_cfg)
        img = self.cam.capture_array("main")
        self.cam.switch_mode(self.preview_cfg)
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


# ============================================================
# GUI
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.backend = Backend()
        self.leds = LedPanel()

        self.setWindowTitle("IC X-Ray System")
        self.resize(1280,720)

        self.alarm = QLabel("OK", alignment=Qt.AlignmentFlag.AlignCenter)
        self.view  = QLabel("Camera", alignment=Qt.AlignmentFlag.AlignCenter)

        self.btn_preview = QPushButton("Preview")
        self.btn_stop    = QPushButton("STOP")
        self.btn_xray    = QPushButton("XRAY Photo")

        # ⭐ Motor buttons
        self.btn_open   = QPushButton("OPEN")
        self.btn_close  = QPushButton("CLOSE")
        self.btn_rotate = QPushButton("Rotate 45°")
        self.btn_align  = QPushButton("Align Sample")   # ⭐ new

        self.btn_gallery = QPushButton("Gallery")
        self.btn_export  = QPushButton("Export Last")

        # Layout
        central = QWidget()
        root = QHBoxLayout(central)
        left = QVBoxLayout()

        for b in (
            self.btn_preview, self.btn_stop, self.btn_xray,
            self.btn_open, self.btn_close, self.btn_rotate,
            self.btn_align,                       # ⭐ added
            self.btn_gallery, self.btn_export
        ):
            left.addWidget(b)

        left.addStretch()
        root.addLayout(left)
        root.addWidget(self.view,1)
        self.setCentralWidget(central)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # Signals
        self.btn_preview.clicked.connect(self.on_preview)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_xray.clicked.connect(self.on_xray)
        self.btn_open.clicked.connect(self.on_open)
        self.btn_close.clicked.connect(self.on_close)
        self.btn_rotate.clicked.connect(self.on_rotate)
        self.btn_align.clicked.connect(self.on_align)
        self.btn_gallery.clicked.connect(self.on_gallery)
        self.btn_export.clicked.connect(self.on_export)

        self.preview_on = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start()

        # Check SW2 to enable Align Sample
        self.sw_timer = QTimer(self)
        self.sw_timer.timeout.connect(self.check_align_availability)
        self.sw_timer.start()

    # ============================================================
    # Motor Actions
    # ============================================================
    def on_open(self):
        self.alarm.setText("Opening…")
        motor1_backward_until_limit()
        self.alarm.setText("OPEN reached")

    def on_close(self):
        self.alarm.setText("Closing…")
        motor1_forward_until_limit()
        self.alarm.setText("CLOSED")

    def on_rotate(self):
        self.alarm.setText("Rotating 45°…")
        motor3_rotate_45()
        self.alarm.setText("Done")

    def on_align(self):
        self.alarm.setText("Aligning sample…")
        motor2_align_sequence()
        self.alarm.setText("Sample aligned")

    # Enable Align Sample ONLY when switch-2 is pressed
    def check_align_availability(self):
        if GPIO.input(SW2) == 0:
            self.btn_align.setEnabled(True)
        else:
            self.btn_align.setEnabled(False)


    # ============================================================
    # Preview / Camera
    # ============================================================
    def on_preview(self):
        self.preview_on = not self.preview_on

    def on_stop(self):
        self.preview_on = False

    def on_xray(self):
        hv_on()
        img = self.backend.capture_still()
        path,_ = capture_and_save_frame(img, save_dir="captures")
        hv_off()
        self.alarm.setText(f"Saved {path}")

    def on_gallery(self):
        files = sorted(Path("captures").glob("capture_*.png"))
        if files:
            Gallery([str(f) for f in files]).run()

    def on_export(self):
        img = self.backend.grab_gray()
        disp = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        path,_ = capture_and_save_frame(disp, save_dir="captures")
        self.status.showMessage(f"Saved {path}")

    def update_frame(self):
        if not self.preview_on:
            return
        gray = self.backend.grab_gray()
        disp = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        h,w = disp.shape[:2]
        qimg = QImage(disp.data,w,h,3*w,QImage.Format.Format_BGR888)
        self.view.setPixmap(QPixmap.fromImage(qimg))


# ============================================================
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
