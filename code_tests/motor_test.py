import RPi.GPIO as GPIO
import time

# -------------------------
# DRV8825 Pins (CNC Shield X Axis)
# -------------------------
STEP_PIN = 2
DIR_PIN  = 5
EN_PIN   = 8

PULSE_US = 800   # Try 800–1200 if motor is rough


GPIO.setmode(GPIO.BCM)
GPIO.setup(STEP_PIN, GPIO.OUT)
GPIO.setup(DIR_PIN,  GPIO.OUT)
GPIO.setup(EN_PIN,   GPIO.OUT)

# Enable driver (LOW = enabled on most DRV8825 boards)
GPIO.output(EN_PIN, GPIO.LOW)

print("\n=== MOTOR 1 DEBUG ===")
print("s = forward")
print("r = backward")
print("q = quit\n")

def step_once():
    GPIO.output(STEP_PIN, GPIO.HIGH)
    time.sleep(PULSE_US / 1_000_000)
    GPIO.output(STEP_PIN, GPIO.LOW)
    time.sleep(PULSE_US / 1_000_000)


try:
    while True:
        cmd = input(">> ").strip().lower()

        if cmd == "q":
            print("Quitting.")
            break

        elif cmd == "s":
            print("FORWARD... (press ENTER to stop)")
            GPIO.output(DIR_PIN, GPIO.HIGH)   # forward
            while True:
                step_once()
                if sys.stdin in select.select([sys.stdin],[],[],0)[0]:
                    break

        elif cmd == "r":
            print("BACKWARD... (press ENTER to stop)")
            GPIO.output(DIR_PIN, GPIO.LOW)   # backward
            while True:
                step_once()
                if sys.stdin in select.select([sys.stdin],[],[],0)[0]:
                    break

        else:
            print("Unknown command")

finally:
    GPIO.output(EN_PIN, GPIO.HIGH)  # disable driver
    GPIO.cleanup()
    print("GPIO cleaned up.")
