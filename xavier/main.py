

import sys, time
from pathlib import Path
_here = Path(__file__).resolve()
_project_root = _here.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import RPi.GPIO as GPIO

from xavier.camera_picam2 import start_camera, capture_still, shutdown_cam, stop_windows
from xavier.relay import hv_on, hv_off
from xavier.leds import LedPanel
import xavier.gpio_estop as gpio_estop

# NEW: Motor system
from xavier.stepper_Motor import (
    motor3_rotate_45,
    motor2_alignment_sequence,
    SW1, SW2, SW3
)

# NEW: ADC safety module
from xavier.adc_reader import read_hv_voltage, hv_status_ok

leds = LedPanel()
PRE_ROLL_S = 0.5
POST_HOLD_S = 0.5

GPIO.setup(SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ============================================================
def update_leds(*, hv=False, fault=False, preview=False, armed=False):
    state = "IDLE"
    if fault: state="FAULT"
    elif preview: state="PREVIEW"
    elif hv: state="EXPOSE"
    elif armed: state="ARMED"
    leds.apply(alarm=fault, interlocks_ok=not fault, state=state)


# ============================================================
def banner():
    ok = gpio_estop.estop_ok_now()
    latched = gpio_estop.faulted()
    print(f"\n=== XRAY MENU ===\nE-STOP: {'OK' if ok else 'PRESSED'} | Latch: {'FAULT' if latched else 'no fault'}")


def _on_estop_fault():
    print("\n[E-STOP TRIPPED]")
    hv_off()
    update_leds(fault=True)
    shutdown_cam()
    stop_windows()


def run_preview():
    if gpio_estop.faulted(): return
    hv_on()
    update_leds(hv=True, preview=True)
    try:
        start_camera(on_capture=None, save_dir="captures", should_stop=gpio_estop.faulted)
    finally:
        hv_off()
        update_leds()


def run_photo():
    if gpio_estop.faulted(): return

    # NEW SAFETY — Check HV range
    hv = read_hv_voltage()
    ok, msg = hv_status_ok(hv)
    if not ok:
        print(f"[HV ERROR] {msg}")
        update_leds(fault=True)
        return

    update_leds(armed=True)
    input("Press ENTER to capture…")

    hv_on()
    update_leds(hv=True)
    time.sleep(PRE_ROLL_S)

    path,_ = capture_still((1920,1080),"captures")
    print(f"Saved: {path}")

    time.sleep(POST_HOLD_S)
    hv_off()
    update_leds()


def main():
    gpio_estop.start_monitor(_on_estop_fault)

    try:
        while True:
            banner()
            print("[1] Preview\n[2] Photo\n[3] Rotate 45°\n[4] Align Sample\n[q] Quit")
            cmd = input("Select: ").strip().lower()

            if cmd == "1": run_preview()
            elif cmd == "2": run_photo()
            elif cmd == "3": motor3_rotate_45()
            elif cmd == "4":
                # Only allowed AFTER switch 2
                if GPIO.input(SW2) == 0:
                    motor2_alignment_sequence()
                else:
                    print("Cannot align — CLOSE limit (SW2) not reached.")
            elif cmd == "q": break

    finally:
        hv_off()
        update_leds()
        shutdown_cam()
        stop_windows()
        gpio_estop.stop_monitor()
        leds.cleanup()

if __name__ == "__main__":
    main()
