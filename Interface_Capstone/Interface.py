import sys
import time
from pathlib import Path

_here = Path(__file__).resolve()
project_root = _here.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import numpy as np
import cv2
import serial
import RPi.GPIO as GPIO
from datetime import datetime

from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap

from xavier.io_utils import capture_and_save_frame   # <-- FIXED HERE
from xavier.gallery import Gallery, ImageEditorWindow
from xavier.relay import hv_on, hv_off
from xavier.leds import LedPanel
from xavier import gpio_estop

from xavier.stepper_Motor import (
    motor1_forward_until_switch2,
    motor1_backward_until_switch1,
    motor2_home_to_limit3,
    motor2_move_full_up,
    motor3_rotate_45,
    motor3_home
)

ser = serial.Serial("/dev/ttyACM0", 115200, timeout=0.01)
from xavier.camera_picam2 import Picamera2


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
        self.preview_cfg = self.cam.create_preview_configuration(main={"size": self.preview_size})
        self.still_cfg = self.cam.create_still_configuration(main={"size": self.still_size})
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

    def _ensure(self):
        if self.cam is None:
            raise RuntimeError("Picamera2 not started")

    def grab_gray(self):
        self._ensure()
        if self._mode != "preview":
            self.cam.switch_mode(self.preview_cfg)
            self._mode = "preview"
        frame = self.cam.capture_array("main")
        try: return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        except: return frame

    def grab_bgr(self):
        self._ensure()
        if self._mode != "preview":
            self.cam.switch_mode(self.preview_cfg)
            self._mode = "preview"
        frame = self.cam.capture_array("main")
        try: return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except: return frame

    def capture_xray_fixed(self):
        self._ensure()

        cfg = self.cam.create_still_configuration(
            main={"size": self.still_size},
            controls={
                "AnalogueGain": 8.0,
                "ExposureTime": 3_000_000,
                "AeEnable": False,
                "AwbEnable": False
            }
        )

        self.cam.stop()
        self.cam.configure(cfg)
        self.cam.start()

        time.sleep(3.4)
        frame = self.cam.capture_array("main")

        self.cam.stop()
        self.cam.configure(self.preview_cfg)
        self.cam.start()

        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)



# ============================================================
# GUI MAIN WINDOW
# ============================================================
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("IC X-ray Viewer")
        self.resize(1280,720)

        self.leds = LedPanel()
        self.armed = False
        self.preview_on = False

        self.backend = PiCamBackend()
        self.backend.start()

        # GUI Elements
        self.alarm = QLabel("OK", alignment=Qt.AlignCenter)
        self.alarm.setStyleSheet("font-size:26px;font-weight:bold;padding:8px;")

        self.view = QLabel("Camera", alignment=Qt.AlignCenter)

        # Buttons
        self.btn_open = QPushButton("OPEN")
        self.btn_close = QPushButton("CLOSE")
        self.btn_align = QPushButton("ALIGN SAMPLE")
        self.btn_rotate = QPushButton("Rotate 45°")
        self.btn_home3 = QPushButton("Home Rotation")
        self.btn_preview = QPushButton("Preview")
        self.btn_stop = QPushButton("STOP")
        self.btn_export = QPushButton("Export Last")
        self.btn_xray = QPushButton("XRAY Photo")
        self.btn_gallery = QPushButton("Gallery")
        self.btn_editor = QPushButton("Editor")
        self.btn_show_last = QPushButton("Show Last X-ray")

        # Layout
        central = QWidget()
        root = QHBoxLayout(central)
        left = QVBoxLayout()

        for b in (
            self.btn_preview, self.btn_stop,
            self.btn_export, self.btn_xray,
            self.btn_open, self.btn_close,
            self.btn_align, self.btn_rotate,
            self.btn_home3, self.btn_gallery,
            self.btn_show_last, self.btn_editor
        ):
            left.addWidget(b)

        left.addStretch()

        center = QVBoxLayout()
        center.addWidget(self.alarm)
        center.addWidget(self.view)
        root.addLayout(left)
        root.addLayout(center, 1)
        self.setCentralWidget(central)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # Button connections
        self.btn_open.clicked.connect(self.on_open)
        self.btn_close.clicked.connect(self.on_close)
        self.btn_align.clicked.connect(self.on_align)
        self.btn_rotate.clicked.connect(self.on_rotate45)
        self.btn_home3.clicked.connect(self.on_home3)
        self.btn_preview.clicked.connect(self.on_preview)
        self.btn_stop.clicked.connect(self.on_stop)   # <-- STOP FIXED
        self.btn_export.clicked.connect(self.on_export)
        self.btn_xray.clicked.connect(self.on_xray)
        self.btn_gallery.clicked.connect(self.on_gallery)
        self.btn_show_last.clicked.connect(self.on_show_last)
        self.btn_editor.clicked.connect(self.on_editor)

        # Timers
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.setInterval(33)

        self.estop_timer = QTimer(self)
        self.estop_timer.timeout.connect(self.check_estop)
        self.estop_timer.setInterval(200)
        self.estop_timer.start()

        self.all_leds_off()



    # ============================================================
    # SIMPLE BANNER FUNCTION
    # ============================================================
    def banner(self, text, color=None):

        if color == "green":
            style = "background-color:#4CAF50;color:white;font-size:26px;font-weight:bold;padding:8px;"
        elif color == "blue":
            style = "background-color:#2196F3;color:white;font-size:26px;font-weight:bold;padding:8px;"
        elif color == "yellow":
            style = "background-color:#FFEB3B;color:black;font-size:26px;font-weight:bold;padding:8px;"
        elif color == "red":
            style = "background-color:#F44336;color:white;font-size:26px;font-weight:bold;padding:8px;"
        elif color == "orange":
            style = "background-color:#FF9800;color:white;font-size:26px;font-weight:bold;padding:8px;"
        else:
            style = "font-size:26px;font-weight:bold;padding:8px;"

        self.alarm.setStyleSheet(style)
        self.alarm.setText(text)



    # ============================================================
    # LED UTILITY
    # ============================================================
    def all_leds_off(self):
        self.leds.write(self.leds.red, False)
        self.leds.write(self.leds.amber, False)
        self.leds.write(self.leds.green, False)
        self.leds.write(self.leds.blue, False)



    # ============================================================
    # TRAY OPEN
    # ============================================================
    def on_open(self):
        self.all_leds_off()
        self.leds.write(self.leds.amber, True)

        motor3_home()
        motor1_backward_until_switch1()

        self.banner("Tray Opened — Place Sample", color="yellow")



    # ============================================================
    # TRAY CLOSE
    # ============================================================
    def on_close(self):
        self.all_leds_off()
        self.leds.write(self.leds.amber, True)

        motor1_forward_until_switch2()

        self.banner("Tray Closed", color="yellow")



    # ============================================================
    # ALIGN SAMPLE
    # ============================================================
    def on_align(self):
        self.all_leds_off()
        self.leds.write(self.leds.amber, True)

        motor2_home_to_limit3()
        motor2_move_full_up()

        self.armed = True

        self.all_leds_off()
        self.leds.write(self.leds.green, True)

        self.banner("Alignment Complete — Ready for X-Ray Picture", color="green")



    # ============================================================
    # ROTATION
    # ============================================================
    def on_rotate45(self):
        motor3_rotate_45()

    def on_home3(self):
        motor3_home()



    # ============================================================
    # XRAY PHOTO
    # ============================================================
    def on_xray(self):

        if not self.armed:
            QMessageBox.warning(self, "Not Armed",
                "System is NOT armed.\nAlign sample first.")
            self.banner("XRAY BLOCKED — NOT ARMED", color="orange")
            return

        # TURN ON BLUE LED
        self.all_leds_off()
        self.leds.write(self.leds.blue, True)
        self.banner("HV On — Taking X-Ray Picture", color="blue")

        hv_on()
        time.sleep(0.4)
        img = self.backend.capture_xray_fixed()
        hv_off()

        # RESTORE GREEN LED
        self.all_leds_off()
        self.leds.write(self.leds.green, True)

        self.banner("Alignment Complete — Ready for X-Ray Picture", color="green")

        # Save image
        fname = f"/home/xray_juanito/Capstone_Xray_Imaging/captures/capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        cv2.imwrite(fname, img)

        disp = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h,w = disp.shape[:2]
        qimg = QImage(disp.data, w, h, 3*w, QImage.Format.Format_RGB888)
        px = QPixmap.fromImage(qimg).scaled(
            self.view.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.view.setPixmap(px)



    # ============================================================
    # PREVIEW + STOP FIX
    # ============================================================
    def on_preview(self):
        if not self.preview_on:
            self.preview_on = True
            self.timer.start()
        else:
            self.preview_on = False
            self.timer.stop()

    def on_stop(self):
        """STOP button now works."""
        self.preview_on = False
        self.timer.stop()
        self.backend.stop()
        self.all_leds_off()
        self.banner("STOPPED", color="red")

    def update_frame(self):
        if not self.preview_on:
            return

        gray = self.backend.grab_gray()
        disp = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        h,w = disp.shape[:2]
        qimg = QImage(disp.data, w, h, 3*w, QImage.Format.Format_BGR888)
        px = QPixmap.fromImage(qimg).scaled(
            self.view.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.view.setPixmap(px)



    # ============================================================
    # EXPORT & GALLERY
    # ============================================================
    def on_export(self):
        try:
            frame = self.backend.grab_bgr()
            filename = capture_and_save_frame(frame, save_dir="captures")
            self.status.showMessage(f"Saved {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Export", str(e))

    def on_gallery(self):
        base = Path("/home/xray_juanito/Capstone_Xray_Imaging/captures")
        imgs = sorted(list(base.glob("*.jpg")) + list(base.glob("*.png")))

        if not imgs:
            QMessageBox.information(self, "Gallery", "No images found.")
            return

        Gallery([str(p) for p in imgs]).run()



    # ============================================================
    # EDITOR
    # ============================================================
    def on_editor(self):
        import glob
        base = "/home/xray_juanito/Capstone_Xray_Imaging/captures"
        files = sorted(glob.glob(base+"/*.jpg")+glob.glob(base+"/*.png"))

        if not files:
            QMessageBox.warning(self, "No Images", "None to edit.")
            return

        last = files[-1]
        self.editor_window = ImageEditorWindow(last)
        self.editor_window.show()

        self.banner("Editing Image", color="yellow")



    # ============================================================
    # ESTOP
    # ============================================================
    def check_estop(self):
        if gpio_estop.faulted():
            self.all_leds_off()
            self.leds.write(self.leds.red, True)

            self.banner("Fault Detected", color="red")

            self.btn_open.setEnabled(False)
            self.btn_close.setEnabled(False)
            self.btn_align.setEnabled(False)
            self.btn_rotate.setEnabled(False)
            self.btn_xray.setEnabled(False)
        else:
            self.btn_open.setEnabled(True)
            self.btn_close.setEnabled(True)
            self.btn_align.setEnabled(True)
            self.btn_rotate.setEnabled(True)
            self.btn_xray.setEnabled(True)



    # ============================================================
    # EXIT CLEANUP
    # ============================================================
    def closeEvent(self, event):
        self.all_leds_off()
        super().closeEvent(event)



# ============================================================
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
