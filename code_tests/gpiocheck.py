import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(24, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Testing GPIO24 with nothing connected...")

for i in range(20):
    print(GPIO.input(24))  # should be 1 every time
    time.sleep(0.2)

GPIO.cleanup()
