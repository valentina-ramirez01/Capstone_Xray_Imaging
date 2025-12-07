import RPi.GPIO as GPIO
import time
import logging
from logging.handlers import RotatingFileHandler
import os
import multiprocessing

multiprocessing.current_process().name = "HV_DAEMON"

# ==========================================
# INSTRUCTIONS FOR IMPLEMENTATION
# ==========================================
'''
1) RUN sudo nano /etc/systemd/system/hv_kill_daemon.service

2) PASTE 
[Unit]
Description=High Voltage Safety Kill Daemon
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/xray_juanito/hv_kill_daemon.py

# Always restart if something goes wrong
Restart=always
RestartSec=2

# Run as root (needed to control GPIO safely)
User=root

# Give daemon access to GPIO and system logs
WorkingDirectory=/home/xray_juanito

# Prevent service from being killed accidentally
KillMode=process

[Install]
WantedBy=multi-user.target

3) Reload systemd with sudo systemctl daemon-reload
4) Enable daemon with sudo systemctl enable hv_kill_daemon.service
5) start the daemon sudo systemctl start hv_kill_daemon.service
6) check status sudo systemctl status hv_kill_daemon.service

'''

# ==========================================
# SHARED LOGGING CONFIG
# ==========================================
LOG_DIR = "/home/xray_juanito/Capstone_Xray_Imaging/logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = f"{LOG_DIR}/interface.log"

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

def log_event(msg):
    logging.info(msg)

# ==========================================
# HEARTBEAT SETTINGS
# ==========================================
HEARTBEAT_FILE = "/tmp/xray_heartbeat"
HEARTBEAT_TIMEOUT = 1   # GUI sends heartbeat every 0.2 sec

def gui_is_alive():
    try:
        with open(HEARTBEAT_FILE, "r") as f:
            ts = float(f.read().strip())
        return (time.time() - ts) < HEARTBEAT_TIMEOUT
    except:
        return False

# ==========================================
# HV SAFETY LOGIC
# ==========================================
HV_PIN = 23
CHECK_RATE = 1

GPIO.setmode(GPIO.BCM)
GPIO.setup(HV_PIN, GPIO.OUT)

def force_hv_off():
    GPIO.output(HV_PIN, GPIO.LOW)
    log_event("HV forced OFF by daemon")

# Always start safe
force_hv_off()
log_event("Daemon started — HV OFF enforced at boot")

# ==========================================
# MAIN LOOP
# ==========================================
while True:
    try:
        # If HV is ON:
        if GPIO.input(HV_PIN) == GPIO.HIGH:
            # If GUI heartbeat is missing → force shutdown
            if not gui_is_alive():
                log_event("GUI heartbeat lost while HV ON — forcing OFF")
                force_hv_off()

        time.sleep(CHECK_RATE)

    except Exception as e:
        log_event(f"Daemon error: {e} — forcing HV OFF")
        force_hv_off()
        time.sleep(CHECK_RATE)