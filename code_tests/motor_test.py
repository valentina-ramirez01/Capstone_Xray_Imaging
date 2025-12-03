#!/usr/bin/env python3
import sys
import time
from pathlib import Path

# ----------------------------------------------------------------------
# FIX: Add project root so Python can import xavier.stepper_Motor
# (motor_test.py is OUTSIDE the xavier folder)
# ----------------------------------------------------------------------
_here = Path(__file__).resolve()
project_root = _here.parent      # folder that contains /xavier
xavier_path = project_root / "xavier"

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(xavier_path) not in sys.path:
    sys.path.insert(0, str(xavier_path))

print("Using xavier path:", xavier_path)

# ----------------------------------------------------------------------
# Import real stepper functions from your stepper_Motor.py
# ----------------------------------------------------------------------
from stepper_Motor import (
    motor1_forward_until_limit,
    motor1_backward_until_limit,
    motor2_home_and_measure,
    motor2_move_full_travel,
    motor3_home,
    motor3_rotate_45
)

# ----------------------------------------------------------------------
# Motor-3 HOME state — IMPORTANT SAFETY FLAG
# Motor-1 cannot run unless Motor-3 is homed
# ----------------------------------------------------------------------
motor3_is_home = False


# ======================================================================
# MAIN MENU
# ======================================================================
def print_menu():
    print("\n================ MOTOR TEST ================")
    print("Commands:")
    print("  h  -> Home Motor-3 (zero position REQUIRED)")
    print("  o  -> Motor-1 OPEN   (requires Motor-3 home)")
    print("  c  -> Motor-1 CLOSE  (requires Motor-3 home)")
    print("  a  -> ALIGN sample using Motor-2")
    print("  r  -> Motor-3 rotate 45°")
    print("  q  -> Quit")
    print("===========================================\n")


# ======================================================================
# MAIN LOOP
# ======================================================================
def main():
    global motor3_is_home

    print("\n=== MOTOR TEST STARTED ===")
    print("Homing Motor-3 first...")
    
    motor3_home()
    motor3_is_home = True

    print("Motor-3 is now at origin (0°).")
    print_menu()

    while True:
        cmd = input("Enter command: ").strip().lower()

        # Quit
        if cmd == "q":
            print("Exiting motor test...")
            break

        # --------------------------------------------------------------
        # Motor-3 HOME
        # --------------------------------------------------------------
        elif cmd == "h":
            print("Homing Motor-3...")
            motor3_home()
            motor3_is_home = True
            print("Motor-3 is now at HOME.")

        # --------------------------------------------------------------
        # Motor-1 OPEN
        # --------------------------------------------------------------
        elif cmd == "o":
            if not motor3_is_home:
                print("❌ Motor-3 is NOT at home — cannot OPEN Motor-1.")
                continue

            print("Opening Motor-1 (BACKWARD until SW1)...")
            motor1_backward_until_limit()
            print("Motor-1 is now OPEN.")

        # --------------------------------------------------------------
        # Motor-1 CLOSE
        # --------------------------------------------------------------
        elif cmd == "c":
            if not motor3_is_home:
                print("❌ Motor-3 is NOT at home — cannot CLOSE Motor-1.")
                continue

            print("Closing Motor-1 (FORWARD until SW2)...")
            motor1_forward_until_limit()
            print("Motor-1 is now CLOSED.")

        # --------------------------------------------------------------
        # Motor-2 ALIGN
        # --------------------------------------------------------------
        elif cmd == "a":
            print("Homing Motor-2 to SW3...")
            steps_home = motor2_home_and_measure()
            print(f"Motor-2 HOME reached after {steps_home} steps.")

            print("Now moving full travel...")
            motor2_move_full_travel()

        # --------------------------------------------------------------
        # Motor-3 ROTATE 45°
        # --------------------------------------------------------------
        elif cmd == "r":
            print("Rotating Motor-3 by 45°...")
            motor3_rotate_45()
            motor3_is_home = False     # moved away from home
            print("Motor-3 rotated 45°.")

        # --------------------------------------------------------------
        else:
            print("Invalid command.")
            print_menu()


# ======================================================================
if __name__ == "__main__":
    main()
