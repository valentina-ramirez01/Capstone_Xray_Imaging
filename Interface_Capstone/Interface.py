import sys
import time
import os
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

from xavier.stepper_Motor import (
    motor1_forward_until_switch2,
    motor1_backward_until_switch1,
    motor3_rotate_45,
    motor3_home
)

ser = serial.Serial("/dev/ttyACM0", 115200, timeout=0.01)
from xavier.camera_picam2 import Picamera2

# ⭐ NEW: E-STOP module (final version)
from xavier import gpio_estop

# =====================================================
# LOGGING SYSTEM
# =====================================================
import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = "/home/xray_juanito/Capstone_Xray_Imaging/logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = f"{LOG_DIR}/interface_.log"

handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=1_000_000,
    backupCount=10
)

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler],
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def log_event(message):
    logging.info(message)


# =====================================================
# CAMERA BACKEND (Patched)
# =====================================================
class PiCamBackend:

    def __init__(self, preview_size=(2592,1944), still_size=(2592,1944)):
        self.preview_size = preview_size
        self.still_size   = still_size
        self.cam: Picamera2 | None = None
        self._mode = "stopped"
        self.ready = False  # PATCH A1 — backend state tracking

    # -------------------------------------------------
    def start(self):
        """Start camera safely."""
        try:
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
            self.ready = True              # PATCH A1
            time.sleep(0.15)
        except Exception as e:
            self.ready = False
            log_event(f"PATCH A1 — Camera failed to start: {e}")
            raise

    # -------------------------------------------------
    def stop(self):
        """Stop camera safely."""
        try:
            if self.cam:
                try: self.cam.stop()
                except: pass
                try: self.cam.close()
                except: pass
        finally:
            self.cam = None
            self.ready = False             # PATCH A1
            self._mode = "stopped"
            time.sleep(0.2)

    # -------------------------------------------------
    def ensure_running(self):
        """PATCH A1 — Guarantee camera is active."""
        if not self.ready or self.cam is None:
            log_event("PATCH A1 — Camera backend restarting (ensure_running)")
            self.start()

    # -------------------------------------------------
    def grab_gray(self):
        self.ensure_running()              # PATCH A1

        if self._mode != "preview":
            self.cam.switch_mode(self.preview_cfg)
            self._mode = "preview"
            time.sleep(0.05)

        frame = self.cam.capture_array("main")  # PATCH A3 safe
        return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

    # -------------------------------------------------
    def grab_bgr(self):
        self.ensure_running()              # PATCH A1

        if self._mode != "preview":
            self.cam.switch_mode(self.preview_cfg)
            self._mode = "preview"
            time.sleep(0.05)

        frame = self.cam.capture_array("main")  # PATCH A3 safe
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    # -------------------------------------------------
    def capture_xray_fixed(self):
        """Still capture with manual exposure."""
        self.ensure_running()              # PATCH A2

        cfg = self.cam.create_still_configuration(
            main={"size": self.still_size},
            controls={
                "AnalogueGain": 8.0,
                "ExposureTime": 3_000_000,
                "AeEnable": False,
                "AwbEnable": False
            }
        )

        # Enter still mode
        self.cam.stop()
        self.cam.configure(cfg)
        self.cam.start()
        time.sleep(3.4)

        frame = self.cam.capture_array("main")

        # PATCH A8 — return to preview mode safely
        self.cam.stop()
        self.cam.configure(self.preview_cfg)
        self.cam.start()
        self._mode = "preview"

        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)


# ============================================================
# GUI MAIN WINDOW
# ============================================================
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        try:
            if os.path.exists("/tmp/xray_shutdown_flag"):
                os.remove("/tmp/xray_shutdown_flag")
                log_event("Startup: old shutdown flag removed")
        except Exception as e:
            log_event(f"Startup: could not remove shutdown flag: {e}")

        self.setWindowTitle("IC X-ray Viewer")

        self.leds = LedPanel()

        # --------------------------------------------------------
        # INTERNAL STATES
        # --------------------------------------------------------
        self.preview_on     = False
        self.armed          = False
        self.hv_fault_active = False
        self.has_closed_once = False
        self.has_started     = False
        self.hv_active       = False
        self.xraying         = False   # ⭐ Prevent alignment overwrites

        # PATCH A6 — Track preview state before E-STOP
        self.preview_was_running_before_estop = False

        # PATCH A4 — banner spam limiter
        self._last_banner_time = 0

        # --------------------------------------------------------
        # SW2/SW1 input
        # --------------------------------------------------------
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # --------------------------------------------------------
        # Camera backend
        # --------------------------------------------------------
        self.backend = PiCamBackend()
        self.backend.start()

        # --------------------------------------------------------
        # UI Setup
        # --------------------------------------------------------
        self.alarm = QLabel("System Ready", alignment=Qt.AlignmentFlag.AlignCenter)
        self.alarm.setStyleSheet("font-size:26px;font-weight:bold;padding:8px;")

        self.view = QLabel("Camera", alignment=Qt.AlignmentFlag.AlignCenter)

        # CONTROL BUTTONS
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
        self.btn_shutdown = QPushButton("Shutdown System")
        self.btn_shutdown.setStyleSheet(
            "background-color: #D32F2F; color: white; font-weight: bold; font-size: 18px; padding: 10px;"
        )

        central = QWidget()
        root = QHBoxLayout(central)
        left = QVBoxLayout()

        for b in (
            self.btn_preview, self.btn_stop,
            self.btn_xray,
            self.btn_open, self.btn_close,
            self.btn_rotate, self.btn_home3,
            self.btn_gallery, self.btn_show_last,
            self.btn_editor, self.btn_shutdown
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

        self.resize(1280,720)
        QTimer.singleShot(300, self.showFullScreen)

        # --------------------------------------------------------
        # Connect buttons
        # --------------------------------------------------------
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
        self.btn_shutdown.clicked.connect(self.close)

        # --------------------------------------------------------
        # PATCH B1 — Detect tray position
        # --------------------------------------------------------
        sw1 = GPIO.input(17)
        sw2 = GPIO.input(18)

        if sw1 == 0:
            self.has_started = True
            self.has_closed_once = False
            self.armed = False
            self.all_leds_off()
            self.leds.write(self.leds.amber, True)
            self.banner("Tray Open — Insert Sample", color="yellow")
            log_event("PATCH B1 — Startup detected: TRAY OPEN")

        elif sw2 == 0:
            self.has_started = True
            self.has_closed_once = True
            self.armed = True
            self.all_leds_off()
            self.leds.write(self.leds.green, True)
            self.banner("Sample Aligned — Ready for X-Ray", color="green")
            log_event("PATCH B1 — Startup detected: TRAY CLOSED")

        else:
            self.has_started = True
            self.has_closed_once = False
            self.armed = False
            self.all_leds_off()
            self.leds.write(self.leds.amber, True)
            self.banner("Tray Position Unknown — Please CLOSE Tray", color="yellow")
            log_event("PATCH B1 — Startup detected: TRAY UNKNOWN")

        # --------------------------------------------------------
        # Timers
        # --------------------------------------------------------
        self	timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update_frame)

        self.adc_timer = QTimer(self)
        self.adc_timer.setInterval(300)
        self.adc_timer.timeout.connect(self.check_adc_safety)

        self.align_timer = QTimer(self)
        self.align_timer.setInterval(100)
        self.align_timer.timeout.connect(self.check_alignment)

        # HEARTBEAT
        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.setInterval(200)
        self.heartbeat_timer.timeout.connect(self.send_heartbeat)
        self.heartbeat_timer.start()

        self.all_leds_off()

        # --------------------------------------------------------
        # Start E-STOP monitoring
        # --------------------------------------------------------
        gpio_estop.start_monitor(self.handle_estop_fault,
                                 self.handle_estop_release)

    # ============================================================
    # HEARTBEAT WRITER
    # ============================================================
    def send_heartbeat(self):
        try:
            with open("/tmp/xray_heartbeat", "w") as f:
                f.write(str(time.time()))
        except:
            pass

    # ============================================================
    # E-STOP: PRESS HANDLER
    # ============================================================
    def handle_estop_fault(self):

        self.preview_was_running_before_estop = self.preview_on

        try: self.timer.stop()
        except: pass
        try: self.adc_timer.stop()
        except: pass
        try: self.align_timer.stop()
        except: pass

        try: hv_off()
        except: pass
        try: self.backend.stop()
        except: pass

        self.all_leds_off()
        self.leds.write(self.leds.red, True)

        def gui_updates():
            self.banner("E-STOP PRESSED — SYSTEM HALTED", color="red")

            for b in (
                self.btn_open, self.btn_close,
                self.btn_rotate, self.btn_home3,
                self.btn_preview, self.btn_xray,
                self.btn_gallery, self.btn_show_last,
                self.btn_editor, self.btn_shutdown
            ):
                b.setEnabled(False)

        QTimer.singleShot(0, gui_updates)

        log_event("E-STOP PRESSED — SYSTEM HALTED")

    # ============================================================
    # E-STOP: RELEASE HANDLER
    # ============================================================
    def handle_estop_release(self):

        log_event("E-STOP released — system re-enabled")

        try:
            self.backend.start()
        except Exception as e:
            log_event(f"Camera restart after E-STOP failed: {e}")

        QTimer.singleShot(0, self.adc_timer.start)
        QTimer.singleShot(0, self.align_timer.start)

        self.all_leds_off()

        def gui_updates():

            self.banner("System Ready")

            for b in (
                self.btn_open, self.btn_close,
                self.btn_rotate, self.btn_home3,
                self.btn_preview, self.btn_xray, self.btn_stop,
                self.btn_gallery, self.btn_show_last,
                self.btn_editor, self.btn_shutdown
            ):
                b.setEnabled(True)

            if self.preview_was_running_before_estop:
                self.preview_on = True
                self.timer.start()

        QTimer.singleShot(0, gui_updates)

    # ============================================================
    # LED RESET
    # ============================================================
    def all_leds_off(self):
        self.leds.write(self.leds.red, False)
        self.leds.write(self.leds.amber, False)
        self.leds.write(self.leds.green, False)
        self.leds.write(self.leds.blue, False)

    # ============================================================
    # BANNER DISPLAY
    # ============================================================
    def banner(self, text, color=None):

        now = time.time()
        if now - self._last_banner_time < 0.10:
            return
        self._last_banner_time = now

        log_event(f"BANNER: {text}")

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
    # ADC SAFETY SYSTEM
    # ============================================================
    def check_adc_safety(self):

        if not self.hv_active:
            return

        hv = read_hv_voltage()
        ok, msg = hv_status_ok(hv)

        log_event(f"ADC CHECK — HV reading: {hv:.2f} V")

        if not ok:
            log_event(f"HV FAULT DETECTED — {msg} — HV OFF triggered")
            self.hv_fault_active = True
            hv_off()
            self.hv_active = False

            self.all_leds_off()
            self.leds.write(self.leds.red, True)
            self.banner(f"HV FAULT — {msg}", color="red")

            for b in (
                self.btn_open, self.btn_close,
                self.btn_rotate, self.btn_home3,
                self.btn_xray, self.btn_preview,
                self.btn_stop, self.btn_gallery,
                self.btn_show_last, self.btn_editor,
                self.btn_shutdown
            ):
                b.setEnabled(False)

            return

        if self.hv_fault_active:
            log_event("HV SAFETY RECOVERY — HV back within safe limits")

        self.hv_fault_active = False

        for b in (
            self.btn_open, self.btn_close,
            self.btn_rotate, self.btn_home3,
            self.btn_xray, self.btn_preview,
            self.btn_gallery, self.btn_show_last,
            self.btn_editor, self.btn_shutdown
        ):
            b.setEnabled(True)

    # ============================================================
    # ALIGNMENT SYSTEM
    # ============================================================
    def check_alignment(self):

        # ⭐ Prevent overwriting XRAY banner
        if self.xraying:
            return

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
            log_event("Tray opened")
            return

        sw2 = GPIO.input(18)

        if sw2 == 0:
            self.armed = True
            self.all_leds_off()
            self.leds.write(self.leds.green, True)
            self.banner("Sample Aligned — Ready for X-Ray", color="green")
            log_event("Sample aligned — SW2 engaged")
        else:
            self.armed = False
            self.all_leds_off()
            self.leds.write(self.leds.amber, True)
            self.banner("Tray Closing…", color="yellow")
            log_event("Tray closing")

    # ============================================================
    # TRAY OPEN
    # ============================================================
    def on_open(self):
        log_event("Tray opening — user pressed OPEN")

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
    # TRAY CLOSE
    # ============================================================
    def on_close(self):
        log_event("Tray closing — user pressed CLOSE")

        if self.hv_fault_active:
            return

        self.has_started = True

        self.all_leds_off()
        self.leds.write(self.leds.amber, True)

        motor1_forward_until_switch2()
        self.has_closed_once = True

    # ============================================================
    # ROTATE 45°
    # ============================================================
    def on_rotate45(self):
        log_event("Rotate 45° requested")

        if not self.has_closed_once or not self.armed:
            QMessageBox.warning(self, "Tray Not Closed", "You must CLOSE the tray before rotating.")
            return

        if self.hv_fault_active:
            QMessageBox.warning(self, "HV Fault", "Cannot rotate while HV fault is active.")
            return

        motor3_rotate_45()

    # ============================================================
    # HOME ROTATION
    # ============================================================
    def on_home3(self):
        log_event("Motor 3 going HOME")

        if not self.hv_fault_active:
            motor3_home()

    # ============================================================
    # PREVIEW TOGGLE
    # ============================================================
    def on_preview(self):

        if not self.preview_on:
            log_event("Preview started")
            self.preview_on = True
            QTimer.singleShot(0, self.timer.start)
        else:
            log_event("Preview stopped")
            self.preview_on = False
            QTimer.singleShot(0, self.timer.stop)

    # ============================================================
    # STOP BUTTON
    # ============================================================
    def on_stop(self):

        log_event("STOP pressed — shutting down preview/camera/HV")

        self.preview_on = False
        try: self.timer.stop()
        except: pass

        try: self.backend.stop()
        except: pass

        self.all_leds_off()
        self.banner("STOPPED", color="red")

    # ============================================================
    # XRAY CAPTURE
    # ============================================================
    def on_xray(self):
        log_event("XRAY capture initiated — HV ON requested")

        if self.hv_fault_active:
            QMessageBox.warning(self, "HV Fault", "Unsafe HV level detected.")
            return

        if not self.armed:
            QMessageBox.warning(self, "Not Aligned", "Tray must be fully closed.")
            return

        # ⭐ Prevent alignment banner from overwriting XRAY banner
        self.xraying = True

        # ------------------------------------------------------------------
        # ⭐ DISPLAY BLUE BANNER *BEFORE* THE LONG BLOCKING XRAY OPERATIONS
        # ------------------------------------------------------------------
        self.all_leds_off()
        self.leds.write(self.leds.blue, True)

        self.banner("HV On — Taking X-Ray Picture", color="blue")
        self.alarm.repaint()

        # ⭐ Force Qt to actually draw the banner BEFORE the thread blocks
        QApplication.processEvents()
        QTimer.singleShot(5, lambda: None)
        QApplication.processEvents()
        # ------------------------------------------------------------------

        # (Your original sleep remains untouched)
        time.sleep(0.2)

        # ============================================================
        # XRAY SEQUENCE
        # ============================================================
        try:
            self.hv_active = True
            hv_on()
            time.sleep(0.4)

            self.backend.ensure_running()
            img = self.backend.capture_xray_fixed()

        except Exception as e:
            hv_off()
            self.hv_active = False
            self.xraying = False

            QMessageBox.critical(self, "Error",
                                 "Camera failure — HV turned OFF for safety.")
            log_event(f"XRAY ERROR: {e}")
            return

        finally:
            hv_off()
            log_event("HV OFF — XRAY sequence completed")
            self.hv_active = False

        # ⭐ XRAY done — allow alignment banners again
        self.xraying = False

        # ============================================================
        # UI Reset After XRAY
        # ============================================================
        self.all_leds_off()
        self.leds.write(self.leds.green, True)

        self.banner("Sample Aligned — Ready for X-Ray", color="green")

        # Save image
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = (
            f"/home/xray_juanito/Capstone_Xray_Imaging/captures/"
            f"capture_{timestamp}.jpg"
        )
        cv2.imwrite(filename, img)
        log_event(f"X-ray saved: {filename}")

        # Display on screen
        disp = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = disp.shape[:2]
        qimg = QImage(disp.data, w, h, 3*w, QImage.Format.Format_RGB888)
        px = QPixmap.fromImage(qimg).scaled(
            self.view.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.view.setPixmap(px)


    # ============================================================
    # SHOW LAST CAPTURE
    # ============================================================
    def on_show_last(self):
        log_event("User requested last X-ray preview")

        if self.hv_fault_active:
            return

        if self.preview_on:
            QMessageBox.warning(self,"Preview Active","Turn OFF preview first.")
            return

        import glob, os
        base = "/home/xray_juanito/Capstone_Xray_Imaging/captures"

        files = glob.glob(base+"/*.jpg") + glob.glob(base+"/*.png")
        if not files:
            QMessageBox.warning(self,"No Images","None found.")
            return

        files = sorted(files, key=os.path.getmtime)
        last_file = files[-1]

        img = cv2.imread(last_file)
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
        log_event(f"Showing last X-Ray: {last_file}")


    # ============================================================
    # EXPORT FRAME
    # ============================================================
    def on_export(self):

        try:
            frame = self.backend.grab_bgr()
            filename = capture_and_save_frame(frame, save_dir="captures")
            self.status.showMessage(f"Saved {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Export", str(e))


    # ============================================================
    # GALLERY WINDOW
    # ============================================================
    def on_gallery(self):
        log_event("Gallery opened")

        base_dir = Path("/home/xray_juanito/Capstone_Xray_Imaging/captures")
        all_imgs = sorted(list(base_dir.glob("*.jpg")) + list(base_dir.glob("*.png")))

        if not all_imgs:
            QMessageBox.information(self, "Gallery", "No images found.")
            return

        Gallery([str(p) for p in all_imgs]).run()


    # ============================================================
    # IMAGE EDITOR
    # ============================================================
    def on_editor(self):

        import glob
        base = "/home/xray_juanito/Capstone_Xray_Imaging/captures"
        files = sorted(glob.glob(base+"/*.jpg") + glob.glob(base+"/*.png"))

        if not files:
            QMessageBox.warning(self, "No Images", "None to edit.")
            return

        last = files[-1]
        self.editor_window = ImageEditorWindow(last)

        self.editor_window.setWindowFlag(Qt.WindowType.Window, True)
        self.editor_window.setGeometry(200, 200, 900, 700)

        self.editor_window.show()

        self.banner("Editing Image", color="yellow")
        log_event(f"Editor opened for {last}")


    # ============================================================
    # SHUTDOWN LOGIC
    # ============================================================
    def on_shutdown_clicked(self):
        reply = QMessageBox.question(
            self,
            "Confirm Shutdown",
            "Are you sure you want to shutdown the entire system?\n"
            "This will close the GUI, home the motors, and turn the Raspberry Pi OFF.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.perform_system_shutdown()


    def perform_system_shutdown(self):
        log_event("Shutdown button clicked — initiating safe sequence")

        try:
            with open("/tmp/xray_shutdown_flag", "w") as f:
                f.write("1")
            log_event("Shutdown flag written")
        except Exception as e:
            log_event(f"Error writing shutdown flag: {e}")

        try:
            hv_off()
            log_event("HV OFF for shutdown")
        except:
            pass

        try:
            motor3_home()
            log_event("Motor3 homed for shutdown")
        except:
            pass

        try:
            motor1_forward_until_switch2()
            log_event("Tray closed for shutdown")
        except:
            pass

        log_event("Closing GUI for system shutdown")
        QApplication.processEvents()
        self.close()

        os.system("sudo shutdown -h now")


    # ============================================================
    # PREVIEW FRAME UPDATE
    # ============================================================
    def update_frame(self):

        if not self.preview_on:
            return

        if not self.backend.ready:
            log_event("update_frame skipped — backend not ready")
            return

        try:
            gray = self.backend.grab_gray()
        except Exception as e:
            log_event(f"grab_gray failed: {e}")
            return

        disp = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        h, w = disp.shape[:2]
        qimg = QImage(disp.data, w, h, 3*w, QImage.Format.Format_BGR888)
        px = QPixmap.fromImage(qimg).scaled(
            self.view.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.view.setPixmap(px)


    # ============================================================
    # CLOSE EVENT — SAFE SHUTDOWN
    # ============================================================
    def closeEvent(self, event):
        print("[CLOSE] Safe shutdown…")
        log_event("GUI closed — safe shutdown sequence executed")

        try:
            with open("/tmp/xray_shutdown_flag", "w") as f:
                f.write("1")
            log_event("Shutdown: wrote flag")
        except Exception as e:
            log_event(f"Could not write shutdown flag: {e}")

        try:
            hv_off()
            log_event("Shutdown: HV OFF")
        except:
            pass

        try:
            motor3_home()
            log_event("Shutdown: Motor3 homed")
        except:
            pass

        try:
            motor1_forward_until_switch2()
            log_event("Shutdown: Motor1 CLOSED (SW2)")
        except:
            pass

        try: gpio_estop.stop_monitor()
        except: pass
        try: self.timer.stop()
        except: pass
        try: self.adc_timer.stop()
        except: pass
        try: self.align_timer.stop()
        except: pass

        try: self.backend.stop()
        except: pass

        try:
            self.all_leds_off()
            self.leds.cleanup()
        except:
            pass

        super().closeEvent(event)


# ============================================================
# MAIN ENTRY POINT
# ============================================================
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    log_event("GUI started")

    win.adc_timer.start()
    win.align_timer.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
