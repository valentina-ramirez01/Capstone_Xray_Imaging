import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Testing GPIO22... Press/release the E-stop.")
print("Expect: 1 = released, 0 = pressed")
print("Ctrl+C to exit\n")

try:
    while True:
        val = GPIO.input(22)
        print("GPIO22 =", val)
        time.sleep(0.3)

except KeyboardInterrupt:
    GPIO.cleanup()
    print("\nExit & cleanup complete.")
