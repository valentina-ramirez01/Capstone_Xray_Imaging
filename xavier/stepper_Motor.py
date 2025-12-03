# stepper_Motor.py — FINAL A1 VERSION
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

# ============================================================
# MOTOR 3 — Rotate 45° (Sample Rotate button)
# Pins: 16, 6, 5, 25
# ============================================================
M3_PINS = [16, 6, 5, 25]
for p in M3_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

# ============================================================
# MOTOR 2 — Align Sample (Triggered manually by GUI)
# Pins: 19, 20, 12, 24
# ============================================================
M2_PINS = [19, 20, 12, 24]
for p in M2_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

# ============================================================
# SWITCHES
# ============================================================
SW1 = 17     # Motor 1 OPEN limit (Arduino)
SW2 = 18     # Motor 1 CLOSE limit (Arduino triggers ready state)
SW3 = 22     # Motor 2 origin

GPIO.setup(SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ============================================================
# Stepper Sequence
# ============================================================
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

STEP_DELAY = 0.002
STEPS_45 = 512
STEPS_90 = 1024


def _step_forward(pins):
    for pattern in SEQ:
        for pin, val in zip(pins, pattern):
            GPIO.output(pin, val)
        time.sleep(STEP_DELAY)


def _step_backward(pins):
    for pattern in reversed(SEQ):
        for pin, val in zip(pins, pattern):
            GPIO.output(pin, val)
        time.sleep(STEP_DELAY)


def _motor_off(pins):
    for p in pins:
        GPIO.output(p, 0)


# ============================================================
# MOTOR 3 — ROTATE 45°
# ============================================================
def motor3_rotate_45():
    for _ in range(STEPS_45):
        _step_forward(M3_PINS)
    _motor_off(M3_PINS)


# ============================================================
# MOTOR 2 — Align Sample to Camera (A1 behavior)
# 1. Move backward until SW3 (origin)
# 2. Then move forward 90°
# ============================================================
def motor2_align():
    print("Motor 2 alignment starting in 0.5s…")
    time.sleep(0.5)

    # BACKWARD until origin
    print("Motor 2 → backward to SW3 (origin)…")
    while GPIO.input(SW3) == 1:
        _step_backward(M2_PINS)
    _motor_off(M2_PINS)

    print("Origin reached, waiting 0.5s…")
    time.sleep(0.5)

    # FORWARD 90°
    print("Motor 2 → forward 90° for alignment…")
    for _ in range(STEPS_90):
        _step_forward(M2_PINS)

    _motor_off(M2_PINS)
    print("Motor 2 alignment complete.")
