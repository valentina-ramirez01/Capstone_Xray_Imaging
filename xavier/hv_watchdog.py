import threading
import time
from xavier.relay import hv_off

# GLOBAL heartbeat flag shared across threads
_last_heartbeat = time.time()
_running = False

def hv_watchdog_thread():
    global _last_heartbeat, _running
    print("[WATCHDOG] HV watchdog started")

    while _running:
        now = time.time()

        # If more than 0.5 seconds passed with no heartbeat → SAFETY SHUTDOWN
        if now - _last_heartbeat > 0.5:
            print("[WATCHDOG] HEARTBEAT LOST → HV OFF")
            hv_off()

        time.sleep(0.05)  # Check 20 times per second

    print("[WATCHDOG] HV watchdog stopped")


def start_watchdog():
    global _running, _last_heartbeat
    _running = True
    _last_heartbeat = time.time()
    t = threading.Thread(target=hv_watchdog_thread, daemon=True)
    t.start()


def stop_watchdog():
    global _running
    _running = False


def heartbeat():
    global _last_heartbeat
    _last_heartbeat = time.time()
