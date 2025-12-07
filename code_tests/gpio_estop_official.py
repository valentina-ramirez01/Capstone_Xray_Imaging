# estop_test.py
import time
import gpio_estop   # your updated module

gpio_estop.setup()  # initialize GPIO

print("Monitoring E-STOP in real time. Press CTRL+C to stop.\n")

try:
    while True:
        state = "PRESSED" if not gpio_estop.estop_ok_now() else "released"
        print(f"E-STOP: {state}", end="\r")
        time.sleep(0.05)

except KeyboardInterrupt:
    gpio_estop.cleanup()
    print("\nExiting... GPIO cleaned up.")
