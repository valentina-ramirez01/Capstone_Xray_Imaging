import sys
import time
import serial
import RPi.GPIO as GPIO

# ============================================================
# MOTOR 1 (DRV8825 via Arduino)
# Arduino must be running your working code
# ============================================================
ser = serial.Serial('/dev/ttyACM0', 115200, timeout=0.01)

SW1 = 17   # OPEN limit
SW2 = 18   # CLOSE limit

GPIO.setmode(GPIO.BCM)
GPIO.setup(SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def motor1_open_until_switch():
    print("Motor1 opening…")
    while GPIO.input(SW1) == 1:
        ser.write(b"M1B\n")     # backward = open
        time.sleep(0.002)
    print("Motor1 OPEN limit reached.")

def motor1_close_until_switch():
    print("Motor1 closing…")
    while GPIO.input(SW2) == 1:
        ser.write(b"M1F\n")     # forward = close
        time.sleep(0.002)
    print("Motor1 CLOSE limit reached.")


# ============================================================
# MOTOR 2 (ULN2003) — ALIGN SAMPLE
# ============================================================
M2_IN1 = 19
M2_IN2 = 20
M2_IN3 = 12
M2_IN4 = 24

M2_PINS = [M2_IN1, M2_IN2, M2_IN3, M2_IN4]

for p in M2_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

SW3 = 22   # origin switch

SEQ = [
    [1,0,0,0],
    [1,1,0,0],
    [0,1,0,0],
    [0,1,1,0],
    [0,0,1,0],
    [0,0,1,1],
    [0,0,0,1],
    [1,0,0,1],
]

STEP_SLEEP = 0.0015
step_index = 0

def m2_step(direction):
    global step_index
    step_index = (step_index + direction) % 8
    for pin, val in zip(M2_PINS, SEQ[step_index]):
        GPIO.output(pin, val)
    time.sleep(STEP_SLEEP)

def motor2_align():
    print("Motor2 aligning to camera…")
    steps_taken = 0
    while GPIO.input(SW3) == 1:
        m2_step(+1)
        steps_taken += 1

    print(f"Motor2 alignment complete — steps_taken = {steps_taken}")
    return steps_taken


# ============================================================
# MOTOR 3 — ROTATE 45°
# ============================================================
M3_IN1 = 16
M3_IN2 = 6
M3_IN3 = 5
M3_IN4 = 25

M3_PINS = [M3_IN1, M3_IN2, M3_IN3, M3_IN4]

for p in M3_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

STEPS_45 = 512   # your working value

def m3_step(direction):
    global step_index
    step_index = (step_index + direction) % 8
    for pin, val in zip(M3_PINS, SEQ[step_index]):
        GPIO.output(pin, val)
    time.sleep(STEP_SLEEP)

def motor3_rotate_45():
    print("Motor3: 45° rotation…")
    for _ in range(STEPS_45):
        m3_step(+1)
    print("Motor3 complete.")


# ============================================================
# MAIN LOOP — KEYBOARD CONTROL
# ============================================================
print("\n========== MOTOR TEST ==========")
print("o = Motor1 OPEN until switch")
print("c = Motor1 CLOSE until switch")
print("a = Motor2 ALIGN to camera")
print("r = Motor3 ROTATE 45°")
print("q = quit")
print("================================\n")

try:
    while True:
        key = input(">> ").strip().lower()

        if key == "o":
            motor1_open_until_switch()

        elif key == "c":
            motor1_close_until_switch()

        elif key == "a":
            motor2_align()

        elif key == "r":
            motor3_rotate_45()

        elif key == "q":
            print("Exiting.")
            break

        else:
            print("Unknown command.")

finally:
    print("Cleaning GPIO…")
    GPIO.cleanup()
