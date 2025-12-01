# stepper_Motor.py
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

# ============================================================
# MOTOR 3 — SAMPLE ROTATE (45° BUTTON IN GUI)
# Pins: 16, 6, 5, 25  (ULN2003)
# ============================================================
M3_PINS = [16, 6, 5, 25]
for p in M3_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

# ============================================================
# MOTOR 2 — AUTO SEQUENCE (Triggered when SW2 hits)
# Pins: 19, 20, 12, 22  (ULN2003)
# ============================================================
M2_PINS = [19, 20, 12, 22]
for p in M2_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

# ============================================================
# SWITCHES (PI5)
# ============================================================
SW1 = 17   # Motor 1 forward limit (OPEN)
SW2 = 24   # Motor 1 backward limit (CLOSE)
SW3 = 18   # Motor 2 origin (start of auto sequence)

GPIO.setup(SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ============================================================
# SEQUENCE + CONSTANTS
# ============================================================
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
# MOTOR 3 — Rotate 45° each button press
# ============================================================
def motor3_rotate_45():
    for _ in range(STEPS_45):
        _step_forward(M3_PINS)
    _motor_off(M3_PINS)

# ============================================================
# MOTOR 2 — AUTOMATIC SEQUENCE
# ============================================================
def motor2_backward_until_origin():
    while GPIO.input(SW3) == 1:
        _step_backward(M2_PINS)
    _motor_off(M2_PINS)


def motor2_forward_90():
    for _ in range(STEPS_90):
        _step_forward(M2_PINS)
    _motor_off(M2_PINS)


def motor2_sequence_switch_driven():
    print("Motor 2 sequence will begin in 0.5s…")
    time.sleep(0.5)

    print("Motor 2 → BACKWARD until SW3")
    motor2_backward_until_origin()

    print("Reached SW3 — waiting 0.5s")
    time.sleep(0.5)

    print("Motor 2 → Forward 90°")
    motor2_forward_90()
