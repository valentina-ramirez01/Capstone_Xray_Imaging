# xavier/xray_controller_core/hw/gpio.py
import time
import RPi.GPIO as GPIO

# Configure BCM numbering once
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)


def sleep_s(t: float) -> None:
    """Precise sleep helper used for debouncing and timing."""
    end = time.time() + t
    while time.time() < end:
        time.sleep(min(0.005, end - time.time()))


def setup_input(pin: int) -> None:
    """Configure a GPIO pin as input with pull-up (for Normally-Open switches)."""
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)


def setup_output(pin: int, *, initial_low: bool = True) -> None:
    """Configure a GPIO pin as output."""
    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW if initial_low else GPIO.HIGH)


def read(pin: int, debounce_s: float) -> int:
    """Read a digital input with simple debounce. Returns 1 (HIGH) or 0 (LOW)."""
    v1 = GPIO.input(pin)
    sleep_s(debounce_s)
    v2 = GPIO.input(pin)
    return 1 if (v1 == v2 == 1) else 0


def write(pin: int, high: bool) -> None:
    """Set a digital output HIGH or LOW."""
    GPIO.output(pin, GPIO.HIGH if high else GPIO.LOW)


def cleanup() -> None:
    """Release all GPIO resources (call on exit)."""
    GPIO.cleanup()
