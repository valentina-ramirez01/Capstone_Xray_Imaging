import sys
import time
from pathlib import Path

# ---------------------------------------------------------------
# Ensure project root
# ---------------------------------------------------------------
_here = Path(__file__).resolve()
project_root = _here.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ---------------------------------------------------------------
# Imports
# ---------------------------------------------------------------
import numpy as np
import cv2
import serial
import RPi.GPIO as GPIO
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStatusBar, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap

from xavier.io_utils import capture_and_save_frame
from xavier.gallery import Gallery, ImageEditorWindow
from xavier.relay import hv_on, hv_off
from xavier.leds import LedPanel
from xavier import gpio_estop

# Stepper Motor imports
from xavier.stepper_Motor import (
    motor1_forward_until_switch2,
    motor1_backward_until_switch1,
    motor2_home_to_limit3,
    motor2_move_full_up,
    motor3_rotate_45,
    motor3_home
)

# Serial link for Motor 1 (Arduino)
ser = serial.Serial("/dev/ttyACM0", 115200, timeout=0.01)

# Camera backend
from xavier.camera_picam2 import Picamera2


# ============================================================
# CAMERA BACKEND
# ============================================================
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
        if mode == self._mode: return
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
        if self._mode != "preview": self._switch("preview")
        frame = self.cam.capture_array("main")
        try: return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        except: return frame

    def grab_bgr(self):
        self._ensure()
        if self._mode != "preview": self._switch("preview")
        frame = self.cam.capture_array("main")
        try: return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except: return frame

    def capture_xray_fixed(self):
        self._ensure()

        gain = 8
        shutter_us = 3_000_000   # 3 seconds

        config = self.cam.create_still_configuration(
            main={"size": self.still_size},
            controls={
                "AnalogueGain": float(gain),
                "ExposureTime": shutter_us,
                "AeEnable": False,
                "AwbEnable": False
            }
        )

        self.cam.stop()
        self.cam.configure(config)
        self.cam.start()

        time.sleep(0.3)
        time.sleep(3.0 + 0.4)
        frame = self.cam.capture_array("main")

        self.cam.stop()
        self.cam.configure(self.preview_cfg)
        self.cam.start()

        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)


# ============================================================
# MAIN GUI WINDOW
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("IC X-ray Viewer")
        self.resize(1280,720)

        # LED + Safety Logic
        self.leds = LedPanel()
        self.armed = False   # Green LED = Armed

        # Camera backend
        self.backend = PiCamBackend()
        self.backend.start()
        self.preview_on = False

        # Widgets
        self.alarm = QLabel("OK", alignment=Qt.AlignmentFlag.AlignCenter)
        self.view  = QLabel("Camera", alignment=Qt.AlignmentFlag.AlignCenter)

        # Buttons
        self.btn_open   = QPushButton("OPEN")
        self.btn_close  = QPushButton("CLOSE")
        self.btn_align  = QPushButton("ALIGN SAMPLE")
        self.btn_rotate = QPushButton("Rotate 45°")
        self.btn_home3 = QPushButton("Home Rotation")

        self.btn_preview = QPushButton("Preview")
        self.btn_stop    = QPushButton("STOP")
        self.btn_export  = QPushButton("Export Last")
        self.btn_xray    = QPushButton("XRAY Photo")
        self.btn_gallery = QPushButton("Gallery")
        self.btn_editor  = QPushButton("Editor")
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
        center.addWidget(self.view, 1)

        root.addLayout(left)
        root.addLayout(center, 1)
        self.setCentralWidget(central)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # Connections
        self.btn_open.clicked.connect(self.on_open)
        self.btn_close.clicked.connect(self.on_close)
        self.btn_align.clicked.connect(self.on_align)
        self.btn_rotate.clicked.connect(self.on_rotate45)
        self.btn_home3.clicked.connect(self.on_home3)

        self.btn_preview.clicked.connect(self.on_preview)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_export.clicked.connect(self.on_export)
        self.btn_xray.clicked.connect(self.on_xray)
        self.btn_gallery.clicked.connect(self.on_gallery)
        self.btn_show_last.clicked.connect(self.on_show_last)

        self.btn_editor.clicked.connect(self.on_editor)

        # Timers
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update_frame)

        self.estop_timer = QTimer(self)
        self.estop_timer.setInterval(200)
        self.estop_timer.timeout.connect(self.check_estop)
        self.estop_timer.start()

        self.update_leds()

    # ============================================================
    # MOTOR CONTROLS
    # ============================================================
    def on_open(self):
        self.alarm.setText("RETURNING ROTATION TO HOME…")
        motor3_home()
        self.alarm.setText("OPENING…")
        self.update_leds(amber=True)
        motor1_backward_until_switch1()
        self.alarm.setText("OPEN COMPLETE")

    def on_close(self):
        self.alarm.setText("CLOSING…")
        self.update_leds(amber=True)
        motor1_forward_until_switch2()
        self.update_leds()
        self.alarm.setText("CLOSE COMPLETE")

    def on_align(self):
        self.alarm.setText("ALIGNING SAMPLE…")
        self.update_leds(amber=True)
        motor2_home_to_limit3()
        motor2_move_full_up()

        # ----- ARM SYSTEM -----
        self.armed = True
        self.update_leds(green=True)

        self.alarm.setText("ALIGN COMPLETE — SYSTEM ARMED (GREEN)")

    def on_rotate45(self):
        self.alarm.setText("ROTATING 45°…")
        motor3_rotate_45()
        self.alarm.setText("ROTATION COMPLETE")

    def on_home3(self):
        self.alarm.setText("RETURNING TO HOME…")
        motor3_home()
        self.alarm.setText("HOME COMPLETE")

    # ============================================================
    # LED CONTROL
    # ============================================================
    def update_leds(self, *, amber=False, green=False, blue=False):
        self.leds.write(self.leds.amber, amber)
        self.leds.write(self.leds.green, green)
        self.leds.write(self.leds.blue, blue)

    # ============================================================
    # XRAY LOGIC (LED + HV + ARMING)
    # ============================================================
    def on_xray(self):
        # ---- SAFETY CHECK ----
        if not self.armed:
            QMessageBox.warning(self, "Not Armed",
                "System is NOT armed.\nAlign sample first to arm (Green ON).")
            return

        # ---- Activate HV ----
        self.alarm.setText("XRAY — HV ON")

        # Green OFF, Blue ON
        self.update_leds(green=False, blue=True)
        self.armed = False  # temporarily unarmed during HV

        hv_on()
        time.sleep(0.5)

        img = self.backend.capture_xray_fixed()

        time.sleep(0.5)
        hv_off()

        # ---- Restore ARMING after HV ----
        self.update_leds(blue=False, green=True)
        self.armed = True

        # Save image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/home/xray_juanito/Capstone_Xray_Imaging/captures/capture_{timestamp}.jpg"
        cv2.imwrite(filename, img)

        # Display image
        disp = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = disp.shape[:2]
        qimg = QImage(disp.data, w, h, 3*w, QImage.Format.Format_RGB888)
        px = QPixmap.fromImage(qimg).scaled(
            self.view.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.view.setPixmap(px)

        self.alarm.setText("XRAY COMPLETE — SYSTEM ARMED (GREEN)")

    # ============================================================
    # SHOW LAST PHOTO
    # ============================================================
    def on_show_last(self):
        if self.preview_on:
            QMessageBox.warning(self, "Preview Active",
                "Turn OFF preview before showing last image.")
            return

        import glob
        base_dir = "/home/xray_juanito/Capstone_Xray_Imaging/captures"
        files = sorted(glob.glob(base_dir + "/*.jpg") +
                       glob.glob(base_dir + "/*.jpeg") +
                       glob.glob(base_dir + "/*.png"))

        if not files:
            QMessageBox.warning(self, "No Images", "No X-ray images found.")
            return

        last_file = files[-1]
        img = cv2.imread(last_file)
        if img is None:
            QMessageBox.warning(self, "Error", "Could not load last X-ray image.")
            return

        disp = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = disp.shape[:2]
        qimg = QImage(disp.data, w, h, 3*w, QImage.Format.Format_RGB888)
        px = QPixmap.fromImage(qimg).scaled(
            self.view.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.view.setPixmap(px)

        self.alarm.setText(f"Showing Last X-ray: {last_file}")

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

    def update_frame(self):
        if not self.preview_on: return
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
            path,_ = capture_and_save_frame(frame, save_dir="captures")
            self.status.showMessage(f"Saved {path}")
        except Exception as e:
            QMessageBox.critical(self,"Export",str(e))

    def on_gallery(self):
        base_dir = Path("/home/xray_juanito/Capstone_Xray_Imaging/captures")

        all_imgs = []
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            all_imgs.extend(base_dir.glob(ext))

        all_imgs = sorted(all_imgs)

        if not all_imgs:
            QMessageBox.information(self, "Gallery", "No images found in captures folder.")
            return

        Gallery([str(p) for p in all_imgs]).run()

    # ============================================================
    # EDITOR WINDOW
    # ============================================================
    def on_editor(self):
        if self.preview_on:
            QMessageBox.warning(self, "Preview Active",
                "Turn OFF preview before editing an image.")
            return

        import glob
        base_dir = "/home/xray_juanito/Capstone_Xray_Imaging/captures"
        files = sorted(glob.glob(base_dir + "/*.jpg") +
                       glob.glob(base_dir + "/*.jpeg") +
                       glob.glob(base_dir + "/*.png"))

        if not files:
            QMessageBox.warning(self, "No Images", "No images found to edit.")
            return

        last_file = files[-1]

        self.editor_window = ImageEditorWindow(last_file)
        self.editor_window.show()

        self.alarm.setText(f"Editing: {last_file}")

    # ============================================================
    # E-STOP
    # ============================================================
    def check_estop(self):
        if gpio_estop.faulted():
            self.alarm.setText("E-STOP TRIGGERED")
            self.update_leds()
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
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
