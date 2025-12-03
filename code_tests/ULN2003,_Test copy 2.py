import RPi.GPIO as GPIO
import time

# Stepper pins (BCM)
IN1 = 16
IN2 = 6
IN3 = 5
IN4 = 24

LIMIT_PIN = 22   # bottom/home switch

FULL_TRAVEL_STEPS = 6895   # your measured value

GPIO.setmode(GPIO.BCM)

# setup motor pins
for p in (IN1, IN2, IN3, IN4):
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, GPIO.LOW)

# setup limit switch input
GPIO.setup(LIMIT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Half-step sequence for 28BYJ-48
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

STEP_SLEEP = 0.0015  # speed

step_index = 0

def step(direction):
    global step_index
    pins = [IN1, IN2, IN3, IN4]
    step_index = (step_index + direction) % 8
    for i in range(4):
        GPIO.output(pins[i], SEQ[step_index][i])
    time.sleep(STEP_SLEEP)


def home_to_limit(direction):
    """Moves stepper until limit switch is pressed."""
    print("Homing... moving to limit switch...")
    steps_taken = 0
    
    while GPIO.input(LIMIT_PIN) == 1:  # switch NOT pressed
        step(direction)
        steps_taken += 1

    print(f"Home reached after {steps_taken} steps.")
    return steps_taken


def move_steps(direction, steps):
    """Moves stepper a fixed number of steps."""
    print(f"Moving {steps} steps in direction {direction}...")
    for _ in range(steps):
        step(direction)


try:
    print("\n--- SCISSOR LIFT AUTO HOME & FULL TRAVEL MOVE ---\n")

    # 1️⃣ HOME (move CCW until limit switch triggers)
    home_to_limit(direction=-1)   # -1 = CCW (down)

    # 2️⃣ MOVE TO MAX HEIGHT (CW)
    move_steps(direction=+1, steps=FULL_TRAVEL_STEPS)

    print("\nReached TOP position successfully.")

finally:
    for p in (IN1, IN2, IN3, IN4):
        GPIO.output(p, GPIO.LOW)
    GPIO.cleanup()
    print("\nGPIO cleanup done.")
