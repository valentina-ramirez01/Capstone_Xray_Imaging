import RPi.GPIO as GPIO
import time
import serial
import sys
import termios
import tty

# ============================================================
# MOTOR 1 — DRV8825 via Arduino
# ============================================================
# Arduino listens for:
#   "M1F"  → forward (close)
#   "M1B"  → backward (open)

ser = serial.Serial("/dev/ttyACM0", 115200, timeout=0.01)

SW1 = 17   # open limit
SW2 = 18   # close limit

GPIO.setmode(GPIO.BCM)
GPIO.setup(SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def motor1_forward_until_switch2():
    print("Motor1 → FORWARD until Switch2...")
    while GPIO.input(SW2) == 1:    # NOT pressed
        ser.write(b"M1F\n")
        time.sleep(0.002)
    print("Switch2 hit.")

def motor1_backward_until_switch1():
    print("Motor1 → BACKWARD until Switch1...")
    while GPIO.input(SW1) == 1:
        ser.write(b"M1B\n")
        time.sleep(0.002)
    print("Switch1 hit.")


# ============================================================
# MOTOR 2 — ULN2003 using WORKING TEST CODE
# ============================================================
IN1 = 19
IN2 = 20
IN3 = 12
IN4 = 24
LIMIT3 = 22  # origin

FULL_TRAVEL_STEPS = 6895

for p in (IN1, IN2, IN3, IN4):
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, GPIO.LOW)

GPIO.setup(LIMIT3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

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
step_index = 0

def motor2_step(direction):
    global step_index
    pins = [IN1, IN2, IN3, IN4]
    step_index = (step_index + direction) % 8
    for i in range(4):
        GPIO.output(pins[i], SEQ[step_index][i])
    time.sleep(STEP_SLEEP)

def motor2_home_to_limit3():
    print("Motor2 → Homing to Switch3…")
    steps_taken = 0
    while GPIO.input(LIMIT3) == 1:
        motor2_step(+1)
        steps_taken += 1
    print(f"Reached Switch3 after {steps_taken} steps.")
    return steps_taken

def motor2_move_full_up():
    print(f"Motor2 → moving {FULL_TRAVEL_STEPS} steps…")
    for _ in range(FULL_TRAVEL_STEPS):
        motor2_step(-1)


# ============================================================
# MOTOR 3 — 45° rotation (ULN2003)
# ============================================================
M3_PINS = [16, 6, 5, 25]
for p in M3_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

M3_SEQ = SEQ
M3_SLEEP = 0.002
M3_STEPS_45 = 512
m3_index = 0

def motor3_step():
    global m3_index
    m3_index = (m3_index + 1) % 8
    for pin,val in zip(M3_PINS, M3_SEQ[m3_index]):
        GPIO.output(pin, val)
    time.sleep(M3_SLEEP)

def motor3_rotate_45():
    print("Motor3 → 45° rotation")
    for _ in range(M3_STEPS_45):
        motor3_step()
    for pin in M3_PINS:
        GPIO.output(pin, 0)
    print("Done.")


# ============================================================
# KEYBOARD INPUT (NO ENTER REQUIRED)
# ============================================================
def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ============================================================
# MAIN LOOP
# ============================================================
print("""
===============================
   MOTOR TEST CONTROLS
===============================
Motor1 (Arduino):
    s = open  (backward until SW1)
    r = close (forward until SW2)

Motor2:
    a = ALIGN sample 
        (home to SW3 → move 6895 steps)

Motor3:
    p = rotate 45° once

q = quit
===============================
""")

try:
    while True:
        k = getch()

        if k == "s":
            motor1_backward_until_switch1()

        elif k == "r":
            motor1_forward_until_switch2()

        elif k == "a":
            motor2_home_to_limit3()
            motor2_move_full_up()

        elif k == "p":
            motor3_rotate_45()

        elif k == "q":
            print("Exiting.")
            break

finally:
    GPIO.cleanup()
    ser.close()
    print("GPIO + Serial cleanup complete.")
