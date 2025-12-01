# stepper_Motor.py
import RPi.GPIO as GPIO
import time
import serial

GPIO.setmode(GPIO.BCM)

# ============================================================
# MOTOR 1 — CONTROLLED VIA ARDUINO OVER SERIAL
# ============================================================
try:
    ser = serial.Serial('/dev/ttyACM1', 115200, timeout=1)
    time.sleep(2)
except:
    ser = None
    print("WARNING: Arduino not detected on /dev/ttyACM1")

SW1 = 17   # Motor 1 OPEN limit
SW2 = 24   # Motor 1 CLOSE limit

GPIO.setup(SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def motor1_forward_until_limit():
    """Motor-1 forward until SW1 goes LOW"""
    if ser is None:
        print("ERROR: Serial not available")
        return

    print("Motor-1 → FORWARD")
    while GPIO.input(SW1) == 1:
        ser.write(b"M1F\n")
        time.sleep(0.002)
    print("SW1 reached — STOP")


def motor1_backward_until_limit():
    """Motor-1 backward until SW2 goes LOW"""
    if ser is None:
        print("ERROR: Serial not available")
        return

    print("Motor-1 → BACKWARD")
    while GPIO.input(SW2) == 1:
        ser.write(b"M1B\n")
        time.sleep(0.002)
    print("SW2 reached — STOP")

# ============================================================
# MOTOR 3 — SAMPLE ROTATE (GUI BUTTON)
# Pins: 16, 6, 5, 25  (ULN2003)
# ============================================================
M3_PINS = [16, 6, 5, 25]
for p in M3_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

# ============================================================
# MOTOR 2 — AUTO SEQUENCE (Triggered by SW2)
# Pins: 19, 20, 12, 22
# ============================================================
M2_PINS = [19, 20, 12, 22]
for p in M2_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

SW3 = 18  # Motor-2 origin switch
GPIO.setup(SW3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

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
# MOTOR 3 — 45° rotation
# ============================================================
def motor3_rotate_45():
    for _ in range(STEPS_45):
        _step_forward(M3_PINS)
    _motor_off(M3_PINS)

# ============================================================
# MOTOR 2 — AUTOMATIC SWITCH-DRIVEN SEQUENCE
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
    print("Motor-2: waiting 0.5s")
    time.sleep(0.5)

    print("Motor-2 → backward until SW3")
    motor2_backward_until_origin()

    print("Reached SW3 — waiting 0.5s")
    time.sleep(0.5)

    print("Motor-2 → forward 90°")
    motor2_forward_90()
