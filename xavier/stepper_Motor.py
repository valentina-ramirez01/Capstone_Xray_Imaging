# stepper_Motor.py  (FINAL BUILD)
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

# ============================================================
# MOTOR 3 — Rotate 45° each press (ULN2003)
# Pins: 16, 6, 5, 25
# ============================================================
M3_PINS = [16, 6, 5, 25]
for p in M3_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

# ============================================================
# MOTOR 2 — Alignment motor (ULN2003)
# Pins: 19, 20, 12, 24
# ============================================================
M2_PINS = [19, 20, 12, 24]
for p in M2_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

# ============================================================
# SWITCHES
# ============================================================
SW1 = 17     # Motor 1 OPEN limit
SW2 = 18     # Motor 1 CLOSE limit (must be hit before motor 2 allowed)
SW3 = 22     # Motor 2 origin

GPIO.setup(SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ============================================================
# STEP SEQUENCE & CONSTANTS
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


# ============================================================
# STEP HELPERS
# ============================================================
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
# MOTOR 3 — Rotate 45° (GUI button)
# ============================================================
def motor3_rotate_45():
    for _ in range(STEPS_45):
        _step_forward(M3_PINS)
    _motor_off(M3_PINS)


# ============================================================
# MOTOR 2 — Alignment Sequence
# ============================================================
def motor2_backward_until_origin():
    while GPIO.input(SW3) == 1:
        _step_backward(M2_PINS)
    _motor_off(M2_PINS)

def motor2_forward_90():
    for _ in range(STEPS_90):
        _step_forward(M2_PINS)
    _motor_off(M2_PINS)

def motor2_alignment_sequence():
    print("Motor 2 starting in 0.5s…")
    time.sleep(0.5)

    print(" → BACKWARD until SW3")
    motor2_backward_until_origin()

    print(" → Pausing at origin…")
    time.sleep(0.5)

    print(" → Forward 90°")
    motor2_forward_90()
