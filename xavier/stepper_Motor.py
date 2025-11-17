import RPi.GPIO as GPIO
import time

# GPIO setup
GPIO.setmode(GPIO.BCM)

IN1 = 16
IN2 = 6
IN3 = 5
IN4 = 25

pins = [IN1, IN2, IN3, IN4]
for p in pins:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 0)

BUTTON = 17
GPIO.setup(BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)

sequence = [
    [1,0,0,0],
    [1,1,0,0],
    [0,1,0,0],
    [0,1,1,0],
    [0,0,1,0],
    [0,0,1,1],
    [0,0,0,1],
    [1,0,0,1]
]

step_delay = 0.002
STEPS_45 = 512

def rotate_45():
    """Rotate the stepper motor 45 degrees forward."""
    for _ in range(STEPS_45):
        for pattern in sequence:
            for pin, val in zip(pins, pattern):
                GPIO.output(pin, val)
            time.sleep(step_delay)
    motor_off()

def motor_off():
    for p in pins:
        GPIO.output(p, 0)
