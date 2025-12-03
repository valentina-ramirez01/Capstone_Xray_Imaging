# ============================================================
# stepper_Motor.py  — Motor1, Motor2, Motor3 with safety logic
# ============================================================

import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

# ------------------------------------------------------------
# MOTOR 1 — DRV8825 (controlled by Arduino)
# (Python only sends commands, no GPIO pins here)
# ------------------------------------------------------------
import serial
ser = serial.Serial('/dev/ttyACM1', 115200, timeout=1)
time.sleep(2)

# Motor-1 limit switches
SW1 = 17   # OPEN limit
SW2 = 18   # CLOSE limit
GPIO.setup(SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ------------------------------------------------------------
# MOTOR 2 — 28BYJ-48 (verified working with your test code)
# ------------------------------------------------------------
M2_PINS = [19,20,12,24]
for p in M2_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

SW3 = 22   # Motor 2 origin switch
GPIO.setup(SW3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

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

step_index_M2 = 0

def _m2_step(direction):
    global step_index_M2
    step_index_M2 = (step_index_M2 + direction) % 8
    for pin, val in zip(M2_PINS, SEQ[step_index_M2]):
        GPIO.output(pin, val)
    time.sleep(STEP_SLEEP)

def motor2_home_to_limit():
    while GPIO.input(SW3) == 1:
        _m2_step(+1)
    return True

def motor2_move_steps(direction, steps):
    for _ in range(steps):
        _m2_step(direction)

# ============================================================
# MOTOR 3 — 28BYJ-48 sample rotation + ZERO POSITION LOGIC
# ============================================================

M3_PINS = [16,6,5,25]
for p in M3_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

SW_M3_HOME = 23     # 🆕 Motor 3 home position switch
GPIO.setup(SW_M3_HOME, GPIO.IN, pull_up_down=GPIO.PUD_UP)

step_index_M3 = 0
M3_angle = 0          # tracks 0°, 45°, 90°, 135°... etc.

def _m3_step(direction):
    global step_index_M3
    step_index_M3 = (step_index_M3 + direction) % 8
    for pin, val in zip(M3_PINS, SEQ[step_index_M3]):
        GPIO.output(pin, val)
    time.sleep(STEP_SLEEP)

def motor3_home():
    """Moves M3 until home switch is pressed."""
    global M3_angle
    while GPIO.input(SW_M3_HOME) == 1:
        _m3_step(-1)
    M3_angle = 0
    return True

def motor3_rotate_45():
    """Rotates exactly 45° and updates angle counter."""
    global M3_angle
    for _ in range(512):
        _m3_step(+1)
    M3_angle = (M3_angle + 45) % 360

def motor3_go_to_zero():
    """Returns motor 3 to origin before Motor 1 moves."""
    return motor3_home()

# ============================================================
# MOTOR 1 — SAFE OPEN / CLOSE (requires Motor 3 = 0°)
# ============================================================

def _require_motor3_zero():
    if M3_angle != 0:
        print("❌ Motor-3 not at origin — homing first")
        motor3_go_to_zero()

def motor1_forward_until_limit():   # CLOSE (DIR=HIGH)
    _require_motor3_zero()
    print("Motor-1 forward until SW2 close limit...")
    while GPIO.input(SW2) == 1:
        ser.write(b"M1F\n")
        time.sleep(0.002)
    print("Reached CLOSE limit (SW2).")

def motor1_backward_until_limit():  # OPEN (DIR=LOW)
    _require_motor3_zero()
    print("Motor-1 backward until SW1 open limit...")
    while GPIO.input(SW1) == 1:
        ser.write(b"M1B\n")
        time.sleep(0.002)
    print("Reached OPEN limit (SW1).")

# ============================================================
# MOTOR 2 ALIGN BUTTON
# ============================================================

def motor2_align_sample():
    """Press GUI button → Motor 2 homes to SW3 and then moves FULL_TRAVEL_STEPS."""
    print("Aligning sample...")
    motor2_home_to_limit()
    motor2_move_steps(-1, 6895)
    print("Sample aligned.")
