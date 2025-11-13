import RPi.GPIO as GPIO
import time

# --- Setup ---
GPIO.setmode(GPIO.BCM)      # Use BCM pin numbering
GPIO.setup(24, GPIO.OUT)    # Set GPIO 24 as output

# --- Test sequence ---
print("Turning GPIO 24 ON for 2 seconds...")
GPIO.output(24, GPIO.HIGH)  # Activate the pin (3.3V)
time.sleep(2)

print("Turning GPIO 24 OFF")
GPIO.output(24, GPIO.LOW)   # Deactivate the pin (0V)

# --- Cleanup ---
GPIO.cleanup()
print("Test complete, GPIO released.")