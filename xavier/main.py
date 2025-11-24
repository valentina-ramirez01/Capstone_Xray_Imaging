###############################################
#  main.py — Integrated Motor 2 + Motor 3     #
###############################################

import sys, time
from pathlib import Path

_here = Path(__file__).resolve()
_project_root = _here.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
from xavier.camera_picam2 import start_camera, capture_still, shutdown_cam, stop_windows
from xavier.relay import hv_on, hv_off
import xavier.gpio_estop as gpio_estop
from xavier.leds import LedPanel

# ⭐ NEW STEP MOTOR IMPORT
from xavier.stepper_Motor import (
    motor3_rotate_45,
    motor2_sequence_switch_driven
)

import RPi.GPIO as GPIO

# -------------------------------
# LEDS
# -------------------------------
leds = LedPanel(red=26, amber=13, green=21, blue=27)

PRE_ROLL_S = 0.5
POST_HOLD_S = 0.5

# -------------------------------
# SWITCHES
# -------------------------------
SW1 = 17    # open limit
SW2 = 24    # close limit → triggers motor 2
SW3 = 18    # Motor 2 origin

GPIO.setup(SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ============================================================
# LED CONTROL
# ============================================================
def update_leds(*, hv=False, fault=False, preview=False, armed=False):
    state = "IDLE"
    if fault: state = "FAULT"
    elif preview: state = "PREVIEW"
    elif hv: state = "EXPOSE"
    elif armed: state = "ARMED"

    leds.apply(alarm=fault, interlocks_ok=not fault, state=state)


# ============================================================
# CAMERA / ESTOP
# ============================================================
def handle_capture(filepath: str, frame: np.ndarray):
    print(f"[Capture] Saved {filepath}")


def _on_estop_fault():
    print("\n[E-STOP] TRIPPED")
    hv_off()
    update_leds(fault=True)
    shutdown_cam()
    stop_windows()


def should_stop_preview():
    return gpio_estop.faulted()


def banner():
    ok_now = gpio_estop.estop_ok_now()
    latched = gpio_estop.faulted()
    print("\n=== XRAY MENU ===")
    print(f"E-STOP: {'OK' if ok_now else 'PRESSED'} | Latch: {'FAULT' if latched else 'no fault'}")


def menu():
    while True:
        banner()
        if gpio_estop.faulted():
            print("[r] Reset")
            print("[q] Quit")
            c = input("Select: ").strip().lower()
            if c in ("r","q"): return c
            continue

        print("[1] Preview")
        print("[2] Photo")
        print("[3] Rotate stage 45°")
        print("[q] Quit")
        return input("Select: ").strip().lower()


# ============================================================
# EMERGENCY HOLD
# ============================================================
def emergency_hold_blocking():
    print("=== EMERGENCY HOLD ===")
    while True:
        hv_off()
        update_leds(fault=True)
        shutdown_cam()

        cmd = input("[r]=reset  [q]=quit: ").strip().lower()
        if cmd == "q": sys.exit(1)
        if cmd == "r":
            if gpio_estop.clear_fault():
                update_leds()
                return
            else:
                print("Still pressed!")


# ============================================================
# PREVIEW
# ============================================================
def run_preview():
    if gpio_estop.faulted():
        update_leds(fault=True)
        return
    hv_on()
    update_leds(hv=True, preview=True)
    try:
        start_camera(
            on_capture=handle_capture,
            save_dir="captures",
            should_stop=should_stop_preview
        )
    finally:
        hv_off()
        update_leds()


# ============================================================
# PHOTO
# ============================================================
def run_photo():
    if gpio_estop.faulted():
        update_leds(fault=True)
        return
    update_leds(armed=True)
    print("Photo mode.")
    while True:
        if gpio_estop.faulted():
            emergency_hold_blocking()
            return
        cmd = input("[ENTER]=shoot  [b]=back: ").strip().lower()
        if cmd == "b":
            update_leds()
            return

        hv_on()
        update_leds(hv=True)
        time.sleep(PRE_ROLL_S)

        if gpio_estop.faulted():
            emergency_hold_blocking()
            return

        path,_ = capture_still((1920,1080),"captures")
        print(f"Saved: {path}")
        time.sleep(POST_HOLD_S)
        hv_off()
        update_leds()


# ============================================================
# MAIN LOOP
# ============================================================
def main():
    gpio_estop.start_monitor(_on_estop_fault)

    try:
        while True:

            if gpio_estop.faulted():
                emergency_hold_blocking()
                continue

            update_leds()
            choice = menu()

            if choice == "1":
                run_preview()

            elif choice == "2":
                run_photo()

            elif choice == "3":
                print("Rotating 45°…")
                motor3_rotate_45()
                print("Done.")

            elif choice == "r":
                gpio_estop.clear_fault()
                update_leds()

            elif choice == "q":
                print("Bye.")
                break

            # AUTO MOTOR-2 AFTER SW2
            if GPIO.input(SW2) == 0:
                print("Motor-2 trigger detected — running auto sequence…")
                motor2_sequence_switch_driven()

    finally:
        hv_off()
        update_leds()
        shutdown_cam()
        stop_windows()
        gpio_estop.stop_monitor()
        leds.cleanup()


if __name__ == "__main__":
    main()
