import time
import RPi.GPIO as GPIO

# Actual LED pins
RED = 4
AMBER = 13
GREEN = 21
BLUE = 27

GPIO.setmode(GPIO.BCM)

for pin in (RED, AMBER, GREEN, BLUE):
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

print("Testing LEDs... Press CTRL+C to exit.")

try:
    while True:
        GPIO.output(RED, GPIO.HIGH)
        print("RED ON")
        time.sleep(1)
        GPIO.output(RED, GPIO.LOW)

        GPIO.output(AMBER, GPIO.HIGH)
        print("AMBER ON")
        time.sleep(1)
        GPIO.output(AMBER, GPIO.LOW)

        GPIO.output(GREEN, GPIO.HIGH)
        print("GREEN ON")
        time.sleep(1)
        GPIO.output(GREEN, GPIO.LOW)

        GPIO.output(BLUE, GPIO.HIGH)
        print("BLUE ON")
        time.sleep(1)
        GPIO.output(BLUE, GPIO.LOW)

except KeyboardInterrupt:
    print("\nCleaning up GPIO...")
    GPIO.cleanup()
