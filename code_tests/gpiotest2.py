import RPi.GPIO as GPIO
import time
import subprocess

GPIO.setmode(GPIO.BCM) # Use Broadcom pin numbering
BUTTON_PIN = 22
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Input with pull-up

def button_callback(channel):
    print("E-STOP ACTIVATED! (RPi.GPIO) Shutting down...")
    subprocess.call(['sudo', 'shutdown', '-h', 'now'])

# Add event detection for falling edge (when released for NC button)
# bouncetime handles button bounce
GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200)

print("E-Stop monitoring started (RPi.GPIO)...")
try:
    while True:
        time.sleep(1) # Keep main loop alive
except KeyboardInterrupt:
    print("Exiting...")
finally:
    GPIO.cleanup() # Clean up GPIO on exit
