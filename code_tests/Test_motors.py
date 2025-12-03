import time
import serial
import RPi.GPIO as GPIO

# ============================================================
# GPIO CONFIG
# ============================================================
GPIO.setmode(GPIO.BCM)

# ----- LIMIT SWITCHES -----
SW1 = 17   # Motor 1 OPEN stop
SW2 = 18   # Motor 1 CLOSE stop
SW3 = 22   # Motor 2 ORIGIN stop

GPIO.setup(SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ============================================================
# MOTOR 2 ULN2003 PINS (reverse & forward)
# ============================================================
M2_PINS = [19, 20, 12, 24]  # motor 2
for p in M2_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

# ============================================================
# MOTOR 3 ULN2003 PINS (45° rotation)
# ============================================================
M3_PINS = [16, 6, 5, 25]
for p in M3_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

# ============================================================
# STEPPER SEQUENCE + CONSTANTS
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
    for pat in SEQ:
        for p,val in zip(pins,pat):
            GPIO.output(p,val)
        time.sleep(STEP_DELAY)

def _step_backward(pins):
    for pat in reversed(SEQ):
        for p,val in zip(pins,pat):
            GPIO.output(p,val)
        time.sleep(STEP_DELAY)

def _motor_off(pins):
    for p in pins:
        GPIO.output(p,0)

# ============================================================
# MOTOR 1 — ARDUINO SERIAL CONTROL
# ============================================================
try:
    ser = serial.Serial('/dev/ttyACM1', 115200, timeout=0.01)
    time.sleep(2)
    print("Connected to Arduino.")
except:
    print("ERROR: Arduino not found at /dev/ttyACM1")
    ser = None

def motor1_forward_until_limit():
    print("Motor 1 → OPEN (forward) until SW1")
    if not ser:
        print("Arduino not connected.")
        return
    while GPIO.input(SW1) == 1:
        ser.write(b"M1F\n")
        time.sleep(0.003)
    print("Reached OPEN limit (SW1)")

def motor1_backward_until_limit():
    print("Motor 1 → CLOSE (backward) until SW2")
    if not ser:
        print("Arduino not connected.")
        return
    while GPIO.input(SW2) == 1:
        ser.write(b"M1B\n")
        time.sleep(0.003)
    print("Reached CLOSE limit (SW2)")

# ============================================================
# MOTOR 2 — AUTO ALIGN SEQUENCE
# ============================================================
def motor2_backward_until_origin():
    print("Motor 2 → BACKWARD until SW3")
    while GPIO.input(SW3) == 1:
        _step_backward(M2_PINS)
    _motor_off(M2_PINS)
    print("Motor 2 reached origin (SW3)")

def motor2_forward_90():
    print("Motor 2 → FORWARD 90°")
    for _ in range(STEPS_90):
        _step_forward(M2_PINS)
    _motor_off(M2_PINS)
    print("Motor 2 90° forward complete")

def align_sample():
    if GPIO.input(SW2) == 1:
        print("ERROR: Cannot align — Motor 1 not at SW2 yet!")
        return
    print("Aligning sample in 0.5s …")
    time.sleep(0.5)

    motor2_backward_until_origin()
    time.sleep(0.5)
    motor2_forward_90()

# ============================================================
# MOTOR 3 — 45 DEGREE ROTATION
# ============================================================
def rotate_45():
    print("Motor 3 → 45 degrees")
    for _ in range(STEPS_45):
        _step_forward(M3_PINS)
    _motor_off(M3_PINS)
    print("Motor 3 45° rotation complete")

# ============================================================
# TEST MENU
# ============================================================
def menu():
    print("\n=== MOTOR TEST MENU ===")
    print("1 → Motor 1 OPEN   (until SW1)")
    print("2 → Motor 1 CLOSE  (until SW2)")
    print("3 → Motor 2 ALIGN SAMPLE (requires SW2)")
    print("4 → Motor 3 ROTATE 45°")
    print("q → Quit")
    return input("Select: ").strip().lower()

# ============================================================
# MAIN LOOP
# ============================================================
try:
    while True:
        choice = menu()

        if choice == "1":
            motor1_forward_until_limit()

        elif choice == "2":
            motor1_backward_until_limit()

        elif choice == "3":
            align_sample()

        elif choice == "4":
            rotate_45()

        elif choice == "q":
            print("Bye!")
            break

        else:
            print("Invalid option.")

finally:
    GPIO.cleanup()
    print("GPIO cleaned up.")
