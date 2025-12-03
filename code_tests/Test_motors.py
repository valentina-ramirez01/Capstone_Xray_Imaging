import time
import serial
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)

# -------------------------------------------------------------------
# SWITCHES
# -------------------------------------------------------------------
SW1 = 17    # Motor 1 OPEN limit
SW2 = 18    # Motor 1 CLOSE limit
SW3 = 22    # Motor 2 origin

for sw in (SW1, SW2, SW3):
    GPIO.setup(sw, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# -------------------------------------------------------------------
# MOTOR 2 – ULN2003 PINS (REVISED)
# -------------------------------------------------------------------
M2_PINS = [19, 20, 12, 24]
for p in M2_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

# -------------------------------------------------------------------
# MOTOR 3 – ULN2003 PINS
# -------------------------------------------------------------------
M3_PINS = [16, 6, 5, 25]
for p in M3_PINS:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

# -------------------------------------------------------------------
# STEPPER SEQUENCE
# -------------------------------------------------------------------
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

STEP_DELAY = 0.003    # slower = safer

def step_forward(pins):
    for pattern in SEQ:
        for pin, val in zip(pins, pattern):
            GPIO.output(pin, val)
        time.sleep(STEP_DELAY)

def step_backward(pins):
    for pattern in reversed(SEQ):
        for pin, val in zip(pins, pattern):
            GPIO.output(pin, val)
        time.sleep(STEP_DELAY)

def motor_off(pins):
    for p in pins:
        GPIO.output(p, 0)

# -------------------------------------------------------------------
# MOTOR 3 – 45° ROTATION EXACTLY ONCE
# -------------------------------------------------------------------
STEPS_45 = 512

def motor3_rotate_45():
    print("Motor 3 → rotating 45° once")
    for _ in range(STEPS_45):
        step_forward(M3_PINS)
    motor_off(M3_PINS)
    print("✔ Motor 3 finished 45°")

# -------------------------------------------------------------------
# MOTOR 2 – TEST FORWARD AND BACKWARD
# -------------------------------------------------------------------
def motor2_backward_test():
    print("Motor 2 → backward test (until SW3)")
    while GPIO.input(SW3) == 1:
        step_backward(M2_PINS)
    motor_off(M2_PINS)
    print("✔ Motor 2 reached origin (SW3)")

def motor2_forward_test(steps=800):
    print("Motor 2 → forward test")
    for _ in range(steps):
        step_forward(M2_PINS)
    motor_off(M2_PINS)
    print("✔ Motor 2 forward movement done")

# -------------------------------------------------------------------
# MOTOR 1 – VIA ARDUINO
# -------------------------------------------------------------------
ser = serial.Serial("/dev/ttyACM1", 115200, timeout=1)
time.sleep(2)

def motor1_open():
    print("Motor 1 → OPEN until SW1")
    while GPIO.input(SW1) == 1:
        ser.write(b"M1F\n")  # reversed logically if needed
        time.sleep(0.002)
    print("✔ Motor 1 OPEN (SW1 reached)")

def motor1_close():
    print("Motor 1 → CLOSE until SW2")
    while GPIO.input(SW2) == 1:
        ser.write(b"M1B\n")
        time.sleep(0.002)
    print("✔ Motor 1 CLOSE (SW2 reached)")

# -------------------------------------------------------------------
# MAIN TEST LOOP
# -------------------------------------------------------------------
print("""
==========================
  MOTOR TEST CONSOLE
==========================
Controls:
  1 → Motor 1 OPEN (until SW1)
  2 → Motor 1 CLOSE (until SW2)

  3 → Motor 2 BACKWARD (until SW3 origin)
  4 → Motor 2 FORWARD (manual test)

  5 → Motor 3 rotate 45° ONCE

  q → quit
==========================
""")

try:
    while True:
        cmd = input("Select: ").strip().lower()

        if cmd == "1":
            motor1_open()

        elif cmd == "2":
            motor1_close()

        elif cmd == "3":
            motor2_backward_test()

        elif cmd == "4":
            motor2_forward_test()

        elif cmd == "5":
            motor3_rotate_45()

        elif cmd == "q":
            print("Exiting…")
            break

        else:
            print("Invalid option.")

finally:
    ser.close()
    GPIO.cleanup()
    print("GPIO cleaned up. Goodbye!")
