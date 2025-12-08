import RPi.GPIO as GPIO
import time

PIN = 22

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Reading GPIO 22 with ONLY internal pull-up, nothing connected...")
try:
    while True:
        print(GPIO.input(PIN))
        time.sleep(0.2)
except KeyboardInterrupt:
    GPIO.cleanup()
    print("Done.")
