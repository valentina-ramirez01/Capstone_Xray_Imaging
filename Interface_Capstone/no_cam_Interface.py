import sys
import time
from pathlib import Path

_here = Path(__file__).resolve()
_project_root = _here.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

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
from xavier.adc_reader import read_hv_voltage, hv_status_ok

from xavier.hv_watchdog import start_watchdog, stop_watchdog, heartbeat

from xavier.stepper_Motor import (
    motor1_forward_until_switch2,
    motor1_backward_until_switch1,
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
        self.still_size   = still_size
        self.cam: Picamera2 | None = None
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
        self._mode = "preview"
        time.sleep(0.15)

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
        if self.cam is None:
            raise RuntimeError("Picamera2 not started")
        if self._mode != "preview":
            self.cam.switch_mode(self.preview_cfg)
            self._mode = "preview"
            time.sleep(0.05)
        frame = self.cam.capture_array("main")
        return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

    def grab_bgr(self):
        if self.cam is None:
            raise RuntimeError("Picamera2 not started")
        if self._mode != "preview":
            self.cam.switch_mode(self.preview_cfg)
            self._mode = "preview"
            time.sleep(0.05)
        frame = self.cam.capture_array("main")
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def capture_xray_fixed(self):
        if self.cam is None:
            raise RuntimeError("Picamera2 not started")

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

        # STATES
        self.preview_on = False
        self.armed = False
        self.hv_fault_active = False
        self.has_closed_once = False
        self.has_started = False
        self.hv_active = False     # <---- ADC only on when HV ON

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Optional camera mode
        self.camera_ok = True
        self.backend = None

        try:
            self.backend = PiCamBackend()
            self.backend.start()
        except Exception as e:
            print("[CAMERA] FAILED:", e)
            self.camera_ok = False

        # -------------------------------------------------
        # UI
        # -------------------------------------------------
        self.alarm = QLabel("System Ready", alignment=Qt.AlignmentFlag.AlignCenter)
        self.alarm.setStyleSheet("font-size:26px;font-weight:bold;padding:8px;")

        self.view = QLabel("Camera", alignment=Qt.AlignmentFlag.AlignCenter)

        self.btn_open   = QPushButton("OPEN")
        self.btn_close  = QPushButton("CLOSE")
        self.btn_rotate = QPushButton("Rotate 45°")
        self.btn_home3  = QPushButton("Home Rotation")
        self.btn_preview = QPushButton("Preview")
        self.btn_stop    = QPushButton("STOP")
        self.btn_xray    = QPushButton("XRAY Photo")
        self.btn_gallery = QPushButton("Gallery")
        self.btn_editor  = QPushButton("Editor")
        self.btn_show_last = QPushButton("Show Last X-ray")

        central = QWidget()
        root = QHBoxLayout(central)
        left = QVBoxLayout()

        for b in (
            self.btn_preview, self.btn_stop, self.btn_xray,
            self.btn_open, self.btn_close,
            self.btn_rotate, self.btn_home3,
            self.btn_gallery, self.btn_show_last,
            self.btn_editor
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

        # Button connects
        self.btn_open.clicked.connect(self.on_open)
        self.btn_close.clicked.connect(self.on_close)
        self.btn_rotate.clicked.connect(self.on_rotate45)
        self.btn_home3.clicked.connect(self.on_home3)
        self.btn_preview.clicked.connect(self.on_preview)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_xray.clicked.connect(self.on_xray)
        self.btn_gallery.clicked.connect(self.on_gallery)
        self.btn_show_last.clicked.connect(self.on_show_last)
        self.btn_editor.clicked.connect(self.on_editor)

        # Timers
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update_frame)

        self.adc_timer = QTimer(self)
        self.adc_timer.setInterval(300)
        self.adc_timer.timeout.connect(self.check_adc_safety)
        self.adc_timer.start()

        self.align_timer = QTimer(self)
        self.align_timer.setInterval(100)
        self.align_timer.timeout.connect(self.check_alignment)
        self.align_timer.start()

        start_watchdog()
        self.all_leds_off()


    # ============================================================
    def all_leds_off(self):
        self.leds.write(self.leds.red, False)
        self.leds.write(self.leds.amber, False)
        self.leds.write(self.leds.green, False)
        self.leds.write(self.leds.blue, False)


    # ============================================================
    def banner(self, text, color=None):
        if color == "green":
            st = "background-color:#4CAF50;color:white;font-size:26px;font-weight:bold;padding:8px;"
        elif color == "blue":
            st = "background-color:#2196F3;color:white;font-size:26px;font-weight:bold;padding:8px;"
        elif color == "yellow":
            st = "background-color:#FFEB3B;color:black;font-size:26px;font-weight:bold;padding:8px;"
        elif color == "red":
            st = "background-color:#F44336;color:white;font-size:26px;font-weight:bold;padding:8px;"
        else:
            st = "font-size:26px;font-weight:bold;padding:8px;"
        self.alarm.setStyleSheet(st)
        self.alarm.setText(text)


    # ============================================================
    # ADC SAFETY — ONLY WHEN HV ACTIVE
    # ============================================================
    def check_adc_safety(self):
        heartbeat()

        if not self.hv_active:
            return

        hv = read_hv_voltage()
        ok, msg = hv_status_ok(hv)

        if not ok:
            hv_off()
            self.hv_active = False
            self.hv_fault_active = True

            self.all_leds_off()
            self.leds.write(self.leds.red, True)
            self.banner(f"HV FAULT — {msg}", color="red")

            for b in (
                self.btn_open, self.btn_close,
                self.btn_rotate, self.btn_home3,
                self.btn_xray, self.btn_preview,
                self.btn_stop, self.btn_gallery,
                self.btn_show_last, self.btn_editor
            ):
                b.setEnabled(False)

            return


    # ============================================================
    # ALIGNMENT
    # ============================================================
    def check_alignment(self):
        heartbeat()

        if self.hv_fault_active:
            return

        if not self.has_started:
            self.all_leds_off()
            self.banner("System Ready")
            return

        if not self.has_closed_once:
            self.armed = False
            self.all_leds_off()
            self.leds.write(self.leds.amber, True)
            self.banner("Tray Open — Insert Sample", color="yellow")
            return

        sw2 = GPIO.input(18)

        if sw2 == 0:
            self.armed = True
            self.all_leds_off()
            self.leds.write(self.leds.green, True)
            self.banner("Sample Aligned — Ready for X-Ray", color="green")
        else:
            self.armed = False
            self.all_leds_off()
            self.leds.write(self.leds.amber, True)
            self.banner("Tray Closing…", color="yellow")


    # ============================================================
    # OPEN
    # ============================================================
    def on_open(self):
        heartbeat()

        if self.hv_fault_active:
            return

        self.has_started = True
        self.has_closed_once = False

        self.all_leds_off()
        self.leds.write(self.leds.amber, True)

        motor3_home()
        motor1_backward_until_switch1()

        self.banner("Tray Open — Insert Sample", color="yellow")


    # ============================================================
    # CLOSE
    # ============================================================
    def on_close(self):
        heartbeat()

        if self.hv_fault_active:
            return

        self.has_started = True

        self.all_leds_off()
        self.leds.write(self.leds.amber, True)

        motor1_forward_until_switch2()
        self.has_closed_once = True


    # ============================================================
    def on_rotate45(self):
        heartbeat()
        if not self.hv_fault_active:
            motor3_rotate_45()


    # ============================================================
    def on_home3(self):
        heartbeat()
        if not self.hv_fault_active:
            motor3_home()


    # ============================================================
    # XRAY (HV even without camera)
    # ============================================================
    def on_xray(self):
        heartbeat()

        if self.hv_fault_active:
            QMessageBox.warning(self, "HV Fault", "Unsafe HV level detected.")
            return

        if not self.armed:
            QMessageBox.warning(self, "Not Aligned", "Tray must be fully closed.")
            return

        # GUI feedback
        self.all_leds_off()
        self.leds.write(self.leds.blue, True)
        self.banner("HV On — Taking X-Ray", color="blue")
        QApplication.processEvents()

        try:
            # Enable HV safety window
            self.hv_active = True
            hv_on()
            time.sleep(0.4)

            # CAMERA OPTIONAL MODE
            if self.camera_ok:
                img = self.backend.capture_xray_fixed()
            else:
                img = None

        except Exception as e:
            hv_off()
            self.hv_active = False
            QMessageBox.critical(self, "Error",
                                 "Camera/HV error — HV turned OFF safely.")
            print("XRAY ERROR:", e)
            return

        finally:
            hv_off()
            self.hv_active = False

        # After HV cycle
        self.all_leds_off()
        self.leds.write(self.leds.green, True)
        self.banner("Sample Aligned — Ready for X-Ray", color="green")

        # Save only if camera exists
        if img is not None:
            filename = f"/home/xray_juanito/Capstone_Xray_Imaging/captures/capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            cv2.imwrite(filename, img)


    # ============================================================
    def on_show_last(self):
        heartbeat()

        if self.hv_fault_active:
            return

        if self.preview_on:
            QMessageBox.warning(self,"Preview Active","Turn OFF preview first.")
            return

        import glob
        base = "/home/xray_juanito/Capstone_Xray_Imaging/captures"
        files = sorted(glob.glob(base+"/*.jpg") + glob.glob(base+"/*.png"))

        if not files:
            QMessageBox.warning(self,"No Images","None found.")
            return

        img = cv2.imread(files[-1])
        disp = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = disp.shape[:2]
        qimg = QImage(disp.data, w, h, 3*w, QImage.Format.Format_RGB888)
        px = QPixmap.fromImage(qimg).scaled(
            self.view.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.view.setPixmap(px)

        self.banner("Showing Last X-Ray", color="yellow")


    # ============================================================
    def on_preview(self):
        heartbeat()

        if not self.camera_ok:
            QMessageBox.warning(
                self, "Camera Missing",
                "Preview disabled — no camera detected."
            )
            return

        if not self.preview_on:
            self.preview_on=True
            self.timer.start()
        else:
            self.preview_on=False
            self.timer.stop()


    # ============================================================
    def on_stop(self):
        heartbeat()

        self.preview_on=False
        self.timer.stop()

        if self.backend:
            try: self.backend.stop()
            except: pass

        self.all_leds_off()
        self.banner("STOPPED", color="red")


    # ============================================================
    def update_frame(self):
        heartbeat()

        if not self.preview_on:
            return
        if not self.camera_ok:
            return

        try:
            gray = self.backend.grab_gray()
        except:
            return

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
    def on_export(self):
        heartbeat()

        if not self.camera_ok:
            QMessageBox.warning(self, "Camera Missing",
                                "Cannot export — no camera connected.")
            return

        try:
            frame = self.backend.grab_bgr()
            filename = capture_and_save_frame(frame, save_dir="captures")
            self.status.showMessage(f"Saved {filename}")
        except Exception as e:
            QMessageBox.critical(self,"Export Error",str(e))


    # ============================================================
    def on_gallery(self):
        heartbeat()

        base_dir = Path("/home/xray_juanito/Capstone_Xray_Imaging/captures")
        all_imgs = sorted(list(base_dir.glob("*.jpg")) + list(base_dir.glob("*.png")))

        if not all_imgs:
            QMessageBox.information(self,"Gallery","No images found.")
            return

        Gallery([str(p) for p in all_imgs]).run()


    # ============================================================
    def on_editor(self):
        heartbeat()

        import glob
        base="/home/xray_juanito/Capstone_Xray_Imaging/captures"
        files = sorted(glob.glob(base+"/*.jpg") + glob.glob(base+"/*.png"))

        if not	files:
            QMessageBox.warning(self,"No Images","None to edit.")
            return

        last = files[-1]
        self.editor_window = ImageEditorWindow(last)
        self.editor_window.show()

        self.banner("Editing Image", color="yellow")


    # ============================================================
    def closeEvent(self, event):

        print("[CLOSE] Safe shutdown…")

        try: self.timer.stop()
        except: pass
        try: self.adc_timer.stop()
        except: pass
        try: self.align_timer.stop()
        except: pass

        try: hv_off()
        except: pass

        try:
            if self.backend:
                self.backend.stop()
        except:
            pass

        try: stop_watchdog()
        except: pass

        try:
            self.all_leds_off()
            self.leds.cleanup()
        except:
            pass

        super().closeEvent(event)



# ============================================================
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
