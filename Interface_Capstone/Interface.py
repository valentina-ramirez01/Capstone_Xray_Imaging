# Interface.py — FINAL A1 VERSION (matching stepper_Motor.py)

import sys, time
from pathlib import Path
import numpy as np
import cv2

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QPushButton, QLabel, QVBoxLayout, QHBoxLayout,
    QMessageBox, QStatusBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap

# Fix project path
_here = Path(__file__).resolve()
project_root = _here.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Project imports
from xavier.relay import hv_on, hv_off
from xavier.leds import LedPanel
from xavier.gallery import Gallery
from xavier.io_utils import capture_and_save_frame
from xavier import gpio_estop

# Camera
from xavier.camera_picam2 import Picamera2

# Stepper control (A1)
from xavier.stepper_Motor import (
    motor3_rotate_45,
    motor2_align
)

import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

SW2 = 18   # Required for enabling "Align Sample"
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)

class PiCamBackend:
    def __init__(self):
        self.cam = Picamera2()
        self.preview_cfg = self.cam.create_preview_configuration(
            main={"size": (1280,720)}
        )
        self.still_cfg = self.cam.create_still_configuration(
            main={"size": (1920,1080)}
        )
        self.cam.configure(self.preview_cfg)
        self.cam.start()
        self.mode = "preview"

    def grab_bgr(self):
        frame = self.cam.capture_array("main")
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def capture_still_bgr(self):
        self.cam.switch_mode(self.still_cfg)
        frame = self.cam.capture_array("main")
        self.cam.switch_mode(self.preview_cfg)
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("IC X-ray Viewer")
        self.resize(1280, 720)

        self.backend = PiCamBackend()
        self.leds = LedPanel()
        self.preview_on = False

        # GUI elements
        self.alarm = QLabel("OK", alignment=Qt.AlignCenter)
        self.view  = QLabel("", alignment=Qt.AlignCenter)

        # Buttons
        self.btn_preview = QPushButton("Preview")
        self.btn_xray    = QPushButton("XRAY Photo")
        self.btn_open    = QPushButton("OPEN")
        self.btn_close   = QPushButton("CLOSE")
        self.btn_rotate  = QPushButton("Rotate 45°")
        self.btn_align   = QPushButton("Align Sample")   # motor 2

        # Layout
        left = QVBoxLayout()
        for b in (
            self.btn_preview,
            self.btn_xray,
            self.btn_open,
            self.btn_close,
            self.btn_rotate,
            self.btn_align,
        ):
            left.addWidget(b)
        left.addStretch()

        center = QVBoxLayout()
        center.addWidget(self.alarm)
        center.addWidget(self.view, 1)

        root = QHBoxLayout()
        root.addLayout(left)
        root.addLayout(center, 1)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

        # STATUS BAR
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # SIGNALS
        self.btn_preview.clicked.connect(self.on_preview)
        self.btn_xray.clicked.connect(self.on_xray)

        self.btn_open.clicked.connect(self.on_open)
        self.btn_close.clicked.connect(self.on_close)

        self.btn_rotate.clicked.connect(self.on_rotate45)
        self.btn_align.clicked.connect(self.on_align_sample)

        # Timers
        self.timer = QTimer()
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update_frame)

        # Estop
        self.estop_timer = QTimer()
        self.estop_timer.setInterval(150)
        self.estop_timer.timeout.connect(self.check_estop)
        self.estop_timer.start()

    ##############################################
    # MOTOR BUTTONS
    ##############################################

    def on_open(self):
        import serial
        ser = serial.Serial('/dev/ttyACM1', 115200)
        print("OPEN motor…")
        ser.write(b"M1B\n")
        ser.close()

    def on_close(self):
        import serial
        ser = serial.Serial('/dev/ttyACM1', 115200)
        print("CLOSE motor…")
        ser.write(b"M1F\n")
        ser.close()

    def on_rotate45(self):
        self.alarm.setText("Rotating 45°…")
        motor3_rotate_45()
        self.alarm.setText("Rotation complete")

    def on_align_sample(self):
        if GPIO.input(SW2) == 1:
            QMessageBox.warning(self, "Error", "Cannot align — CLOSE LIMIT not reached.")
            return
        self.alarm.setText("Aligning sample…")
        motor2_align()
        self.alarm.setText("Alignment complete")

    ##############################################
    # CAMERA / XRAY
    ##############################################

    def on_preview(self):
        if not self.preview_on:
            self.preview_on = True
            self.timer.start()
        else:
            self.preview_on = False
            self.timer.stop()
            self.view.clear()

    def update_frame(self):
        if not self.preview_on:
            return
        img = self.backend.grab_bgr()
        h, w = img.shape[:2]
        qimg = QImage(img.data, w, h, 3*w, QImage.Format_BGR888)
        self.view.setPixmap(QPixmap.fromImage(qimg))

    def on_xray(self):
        img = self.backend.capture_still_bgr()
        path, _ = capture_and_save_frame(img, save_dir="captures")
        self.alarm.setText(f"Saved {path}")

    ##############################################
    # ESTOP
    ##############################################

    def check_estop(self):
        if gpio_estop.faulted():
            self.alarm.setText("E-STOP TRIGGERED")
            for b in (self.btn_preview, self.btn_xray,
                      self.btn_open, self.btn_close,
                      self.btn_rotate, self.btn_align):
                b.setEnabled(False)
        else:
            for b in (self.btn_preview, self.btn_xray,
                      self.btn_open, self.btn_close,
                      self.btn_rotate, self.btn_align):
                b.setEnabled(True)
            self.alarm.setText("OK")


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    app.exec()


if __name__ == "__main__":
    main()
