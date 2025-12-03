# ============================================================
#  stepper_Motor.py — FINAL VERSION (MATCHES TEST SCRIPT)
# ============================================================
import RPi.GPIO as GPIO
import time
import serial

# ============================================================
#  SERIAL FOR MOTOR 1 (DRV8825 THROUGH ARDUINO)
# ============================================================
# Arduino listens for:
#   "M1F" → forward  (close)
#   "M1B" → backward (open)

ser = serial.Serial("/dev/ttyACM0", 115200, timeout=0.01)

# Motor 1 limit switches
SW1 = 17   # OPEN limit
SW2 = 18   # CLOSE limit

GPIO.setmode(GPIO.BCM)
GPIO.setup(SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)


# ============================================================
# MOTOR 1 — FUNCTIONS
# ============================================================
def motor1_forward_until_switch2():
    """CLOSE until SW2 pressed"""
    print("Motor1 → FORWARD (close) until Switch2...")

    while GPIO.input(SW2) == 1:   # 1 = NOT pressed
        ser.write(b"M1F\n")
        time.sleep(0.002)

    print("Switch2 hit.")


def motor1_backward_until_switch1():
    """OPEN until SW1 pressed"""
    print("Motor1 → BACKWARD (open) until Switch1...")

    while GPIO.input(SW1) == 1:
        ser.write(b"M1B\n")
        time.sleep(0.002)

    print("Switch1 hit.")


# ============================================================
#  MOTOR 2 — ULN2003 USING WORKING TEST CODE
# ============================================================
IN1 = 19
IN2 = 20
IN3 = 12
IN4 = 24

LIMIT3 = 22   # origin/home switch

FULL_TRAVEL_STEPS = 6895   # EXACT working value

# Setup pins
for p in (IN1, IN2, IN3, IN4):
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, GPIO.LOW)

GPIO.setup(LIMIT3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# 28BYJ-48 half-step sequence
SEQ = [
    [1,0,0,0],
    [1,1,0,0],
    [0,1,0,0],
    [0,1,1,0],
    [0,0,1,0],
    [0,0,1,1],
    [0,0,0,1],
    [1,0,0,1]
]

STEP_SLEEP = 0.0015
m2_index = 0


def motor2_step(direction):
    """direction: +1 = clockwise, -1 = counterclockwise"""
    global m2_index
    pins = [IN1, IN2, IN3, IN4]
    m2_index = (m2_index + direction) % 8

    for i in range(4):
        GPIO.output(pins[i], SEQ[m2_index][i])

    time.sleep(STEP_SLEEP)


def motor2_home_to_limit3():
    """Move motor2 until LIMIT3 is pressed"""
    print("Motor2 → Homing to Switch3…")
    steps_taken = 0

    while GPIO.input(LIMIT3) == 1:   # NOT pressed
        motor2_step(+1)
        steps_taken += 1

    print(f"Reached Switch3 after {steps_taken} steps.")
    return steps_taken


def motor2_move_full_up():
    """Move full travel"""
    print(f"Motor2 → moving {FULL_TRAVEL_STEPS} steps upward…")

    for _ in range(FULL_TRAVEL_STEPS):
        motor2_step(-1)

    print("Motor2 full travel complete.")


# ============================================================
#  MOTOR 3 — 45° ROTATION + HOME (ULN2003)
# ============================================================
M3_PINS = [16, 6, 5, 25]
for p in M3_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

# Your existing ULN2003 half-step sequence
M3_SEQ = SEQ      
M3_SLEEP = 0.002
M3_STEPS_45 = 512

m3_index = 0                # current index in the 8-step sequence
m3_total_steps = 0          # total steps moved FORWARD from "home"


# ------------------------------------------------------------
#  ONE STEP FORWARD
# ------------------------------------------------------------
def motor3_step_forward():
    global m3_index
    m3_index = (m3_index + 1) % 8

    for pin, val in zip(M3_PINS, M3_SEQ[m3_index]):
        GPIO.output(pin, val)

    time.sleep(M3_SLEEP)


# ------------------------------------------------------------
#  ONE STEP BACKWARD
# ------------------------------------------------------------
def motor3_step_backward():
    global m3_index
    m3_index = (m3_index - 1) % 8

    for pin, val in zip(M3_PINS, M3_SEQ[m3_index]):
        GPIO.output(pin, val)

    time.sleep(M3_SLEEP)


# ------------------------------------------------------------
#  ROTATE +45°
# ------------------------------------------------------------
def motor3_rotate_45():
    global m3_total_steps

    print("Motor3 → 45° rotation")

    for _ in range(M3_STEPS_45):
        motor3_step_forward()

    m3_total_steps += M3_STEPS_45

    # turn all coils OFF
    for pin in M3_PINS:
        GPIO.output(pin, 0)

    print(f"Motor3 → done. Total steps = {m3_total_steps}")


# ------------------------------------------------------------
#  HOME FUNCTION
#  Move EXACT number of steps backward to return to zero.
# ------------------------------------------------------------
def motor3_home():
    global m3_total_steps

    print("Motor3 → HOMING...")

    # reverse all steps taken so far
    for _ in range(m3_total_steps):
        motor3_step_backward()

    # turn off coils
    for pin in M3_PINS:
        GPIO.output(pin, 0)

    print("Motor3 → Home complete.")

    m3_total_steps = 0



# ============================================================
#  CLEANUP FUNCTION (optional)
# ============================================================
def cleanup_all():
    ser.close()
    GPIO.cleanup()
    print("Stepper + Serial cleanup complete.")
