import RPi.GPIO as GPIO
import time

PIN = 22  # your estop pin

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Press your NO button...")

try:
    while True:
        v = GPIO.input(PIN)
        print(v)   # 1 = not pressed, 0 = pressed
        time.sleep(0.1)
except KeyboardInterrupt:
    GPIO.cleanup()
