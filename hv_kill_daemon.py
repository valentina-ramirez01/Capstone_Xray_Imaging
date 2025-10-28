import RPi.GPIO as GPIO
import time
import logging
from logging.handlers import RotatingFileHandler
import os
import multiprocessing

#Clean input 

multiprocessing.current_process().name = "HV_DAEMON"

# ======================================================
# LOGGING SETUP
# ======================================================
LOG_DIR = "/home/xray_juanito/Capstone_Xray_Imaging/logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = f"{LOG_DIR}/hv_daemon.log"

handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=1_000_000,
    backupCount=10
)

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler],
    format="%(asctime)s [%(processName)s] %(message)s"
)

def log(msg):
    logging.info(msg)


# ======================================================
# FILE PATHS FOR IPC
# ======================================================
HEARTBEAT_FILE = "/tmp/xray_heartbeat"
SHUTDOWN_FLAG  = "/tmp/xray_shutdown_flag"

HEARTBEAT_TIMEOUT = 1.0     # GUI sends heartbeat every 0.2 sec
CHECK_RATE = 0.25           # Poll interval


# ======================================================
# GPIO CONFIG FOR HV RELAY
# ======================================================
HV_PIN = 23

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(HV_PIN, GPIO.OUT, initial=GPIO.LOW)

def force_hv_off():
    GPIO.output(HV_PIN, GPIO.LOW)
    log("HV forced OFF by daemon")


# ======================================================
# SAFE SHUTDOWN CHECK
# ======================================================
def safe_shutdown_requested() -> bool:
    return os.path.exists(SHUTDOWN_FLAG)


# ======================================================
# GUI HEARTBEAT CHECK
# ======================================================
def gui_is_alive():
    try:
        if not os.path.exists(HEARTBEAT_FILE):
            return False
        
        with open(HEARTBEAT_FILE, "r") as f:
            ts = float(f.read().strip())

        return (time.time() - ts) < HEARTBEAT_TIMEOUT

    except Exception as e:
        log(f"Heartbeat read error: {e}")
        return False


# ======================================================
# START STATE
# ======================================================
force_hv_off()
log("HV Daemon started — HV OFF enforced at boot")

hv_allowed = True     # Daemon blocks HV only after GUI crash


# ======================================================
# MAIN LOOP
# ======================================================
while True:
    try:
        alive = gui_is_alive()
        shutdown_mode = safe_shutdown_requested()
        hv_state = GPIO.input(HV_PIN)   # 1 = ON, 0 = OFF

        # --------------------------------------------------
        # CASE 1: GUI HEARTBEAT LOST
        # --------------------------------------------------
        if not alive:
            if shutdown_mode:
                # GUI is intentionally shutting down (safe)
                log("Daemon: Safe shutdown detected — allowing heartbeat silence")
            else:
                # GUI CRASH — emergency shutdown
                if hv_state == GPIO.HIGH:
                    log("Daemon: GUI crash → HV ON → FORCE OFF")
                    force_hv_off()

                if hv_allowed:
                    log("Daemon: HV interlock engaged (GUI crash mode)")
                hv_allowed = False

        # --------------------------------------------------
        # CASE 2: GUI HEARTBEAT PRESENT
        # --------------------------------------------------
        else:
            if not shutdown_mode:
                if not hv_allowed:
                    log("Daemon: GUI restart detected — HV interlock reset")
                hv_allowed = True

        # --------------------------------------------------
        # CASE 3: Enforce HV safety rule
        # --------------------------------------------------
        if hv_state == GPIO.HIGH and not hv_allowed:
            log("Daemon: HV ON while not allowed → forcing OFF")
            force_hv_off()

        time.sleep(CHECK_RATE)

    except Exception as e:
        log(f"Daemon runtime error: {e} — forcing HV off for safety")
        force_hv_off()
        time.sleep(CHECK_RATE)
