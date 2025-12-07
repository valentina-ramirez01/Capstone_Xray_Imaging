import RPi.GPIO as GPIO
import time

# Limit switch pins (BCM)
SW1 = 17
SW2 = 18
SW3 = 22

GPIO.setmode(GPIO.BCM)

# Setup limit switches with internal pull-ups
for pin in (SW1, SW2, SW3):
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Monitoring limit switches in real time. Press CTRL+C to exit.\n")

try:
    while True:
        s1 = "PRESSED" if GPIO.input(SW1) == 0 else "released"
        s2 = "PRESSED" if GPIO.input(SW2) == 0 else "released"
        s3 = "PRESSED" if GPIO.input(SW3) == 0 else "released"
        
        print(f"SW17: {s1}   |   SW18: {s2}   |   SW24: {s3}", end="\r")
        time.sleep(0.05)   # fast update rate

except KeyboardInterrupt:
    GPIO.cleanup()
    print("\nExiting... GPIO cleaned up.")
