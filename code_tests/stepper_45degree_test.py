import RPi.GPIO as GPIO
import time

# ------------------------------------------
# ULN2003 stepper pins (BCM numbering)
# ------------------------------------------
IN1 = 16
IN2 = 6
IN3 = 5
IN4 = 25
PINS = (IN1, IN2, IN3, IN4)

# Half-step sequence
SEQ = [
    [1,0,0,1],
    [1,0,0,0],
    [1,1,0,0],
    [0,1,0,0],
    [0,1,1,0],
    [0,0,1,0],
    [0,0,1,1],
    [0,0,0,1],
]

STEP_DELAY = 0.002
STEPS_45 = 4096 // 8   # = 512 steps


def motor_off():
    for pin in PINS:
        GPIO.output(pin, 0)


def rotate_45():
    print("Rotating stepper motor 45 degrees...")
    idx = 0
    for _ in range(STEPS_45):
        seq = SEQ[idx]
        for pin, val in zip(PINS, seq):
            GPIO.output(pin, val)
        idx = (idx + 1) % len(SEQ)
        time.sleep(STEP_DELAY)
    motor_off()
    print("Done.")


def main():
    GPIO.setmode(GPIO.BCM)
    for pin in PINS:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, 0)

    try:
        rotate_45()
    except KeyboardInterrupt:
        pass
    finally:
        motor_off()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
