# test_estop.py
import time
import RPi.GPIO as GPIO
import xavier.gpio_estop as estop

# -------------------------------------------------------
# Callback when E-STOP is pressed
# -------------------------------------------------------
def on_fault():
    print(">>> [TEST] E-STOP PRESSED (callback fired!) <<<")

# -------------------------------------------------------
# Setup & start monitor
# -------------------------------------------------------
print("[TEST] Starting monitor thread…")
estop.start_monitor(on_fault)

# -------------------------------------------------------
# Main loop: show raw pin, debounced, and latch
# -------------------------------------------------------
GPIO.setmode(GPIO.BCM)
GPIO.setup(26, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("[TEST] Running live E-STOP test.")
print("[TEST] Press and release your E-STOP button.")
print("[TEST] Ctrl+C to quit.\n")

try:
    while True:
        raw_pin = GPIO.input(26)
        debounced_ok = estop.estop_ok_now()   # True = safe (HIGH)
        latch = estop.faulted()

        print(f"RAW={raw_pin}   DEBOUNCED={debounced_ok}   LATCH={latch}")
        time.sleep(0.2)

except KeyboardInterrupt:
    print("\n[TEST] Stopping monitor…")
    estop.stop_monitor()
    GPIO.cleanup()
    print("[TEST] EXITED CLEANLY.")
