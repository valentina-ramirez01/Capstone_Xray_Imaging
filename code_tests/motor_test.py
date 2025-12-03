import sys
from pathlib import Path
import time
import RPi.GPIO as GPIO

# --------------------------------------------------------
# Fix import path so xavier is visible
# --------------------------------------------------------
project_root = Path("/home/xray/Xray/Capstone_Xray_Imaging")
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# --------------------------------------------------------
# Import motor functions
# --------------------------------------------------------
from xavier.stepper_Motor import (
    motor3_home,
    motor3_rotate_45,
    motor3_is_home,
    motor1_forward_until_limit,
    motor1_backward_until_limit,
    motor2_align_to_camera
)

print("\n=== MOTOR TEST ===")
print("Controls:")
print("  h = home motor 3")
print("  t = rotate motor 3 by 45°")
print("  o = open motor 1 (only if motor 3 is home)")
print("  c = close motor 1 (only if motor 3 is home)")
print("  a = align sample (motor 2)")
print("  q = quit\n")

GPIO.setwarnings(False)

while True:
    cmd = input(">> ").strip().lower()

    # ---------- Motor 3 ----------
    if cmd == "h":
        print("Homing motor 3...")
        motor3_home()

    elif cmd == "t":
        print("Rotating motor 3 by 45°...")
        motor3_rotate_45()

    # ---------- Motor 1 (OPEN/CLOSE) ----------
    elif cmd == "o":
        if not motor3_is_home():
            print("⚠️ Motor 3 is NOT home — cannot open motor 1.")
        else:
            print("Opening motor 1...")
            motor1_backward_until_limit()

    elif cmd == "c":
        if not motor3_is_home():
            print("⚠️ Motor 3 is NOT home — cannot close motor 1.")
        else:
            print("Closing motor 1...")
            motor1_forward_until_limit()

    # ---------- Motor 2 ----------
    elif cmd == "a":
        print("Aligning sample with motor 2...")
        motor2_align_to_camera()

    # ---------- Quit ----------
    elif cmd == "q":
        print("Exiting.")
        GPIO.cleanup()
        break
