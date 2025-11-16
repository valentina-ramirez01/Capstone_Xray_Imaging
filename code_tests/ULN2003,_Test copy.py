import RPi.GPIO as GPIO
import time

# GPIO pin mapping
in1 = 16   # Phase A
in2 = 6    # Phase B
in3 = 5    # Phase C
in4 = 12   # Phase D
in5 = 25   # Phase E (new)

step_sleep = 0.01

angle = input("Rotation angle in degrees: ")
step_count = int(500/360 * abs(float(angle)))  # 5-phase motors: ~500 steps/rev

if float(angle) > 0:
    direction = True
    print("clockwise")
else:
    direction = False
    print("anticlockwise")

# ----- 5 Phase Full Step Sequence -----
step_sequence = [
    [1,0,0,1,0],
    [0,0,1,1,0],
    [0,1,1,0,0],
    [1,1,0,0,0],
    [1,0,0,0,1]
]

# Setup
GPIO.setmode(GPIO.BCM)
pins = [in1, in2, in3, in4, in5]

for pin in pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, 0)

step_index = 0

def cleanup():
    for pin in pins:
        GPIO.output(pin, 0)
    GPIO.cleanup()

# Main loop
try:
    for _ in range(step_count):
        # Output 5-phase pattern
        for pin, val in zip(pins, step_sequence[step_index]):
            GPIO.output(pin, val)

        # Direction handling
        if direction:
            step_index = (step_index + 1) % 5
        else:
            step_index = (step_index - 1) % 5

        time.sleep(step_sleep)

except KeyboardInterrupt:
    cleanup()

cleanup()
