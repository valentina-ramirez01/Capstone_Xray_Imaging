# xavier/gpio_estop.py
import time
import threading
import RPi.GPIO as GPIO

PIN_ESTOP = 26   # your NO switch on GPIO 26
DEBOUNCE_S = 0.02

_GPIO_READY = False
_RUN = False
_THREAD = None

_ON_FAULT = None
_ON_RELEASE = None

_FAULT_LATCH = False


def _read_stable() -> int:
    v1 = GPIO.input(PIN_ESTOP)
    time.sleep(DEBOUNCE_S)
    v2 = GPIO.input(PIN_ESTOP)
    return 1 if (v1 == v2 == 1) else 0


def setup() -> None:
    global _GPIO_READY
    if _GPIO_READY:
        return

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(PIN_ESTOP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    _GPIO_READY = True


def cleanup() -> None:
    global _GPIO_READY
    if _GPIO_READY:
        GPIO.cleanup()
        _GPIO_READY = False


def faulted() -> bool:
    return _FAULT_LATCH


def estop_ok_now() -> bool:
    return bool(_read_stable())


def clear_fault() -> bool:
    global _FAULT_LATCH
    if not _FAULT_LATCH:
        return True
    if _read_stable() == 1:
        _FAULT_LATCH = False
        return True
    return False


def _monitor_loop():
    global _RUN, _FAULT_LATCH, _ON_FAULT, _ON_RELEASE

    while _RUN:
        val = _read_stable()

        if val == 0:     # PRESSED
            if not _FAULT_LATCH:
                _FAULT_LATCH = True
                if _ON_FAULT:
                    try:
                        _ON_FAULT()
                    except Exception as e:
                        print(f"[E-STOP] fault callback error: {e}")

        else:            # RELEASED
            if _FAULT_LATCH:
                _FAULT_LATCH = False
                if _ON_RELEASE:
                    try:
                        _ON_RELEASE()
                    except Exception as e:
                        print(f"[E-STOP] release callback error: {e}")

        time.sleep(0.05)


def start_monitor(on_fault, on_release=None) -> None:
    global _RUN, _THREAD, _ON_FAULT, _ON_RELEASE

    setup()
    _ON_FAULT = on_fault
    _ON_RELEASE = on_release
