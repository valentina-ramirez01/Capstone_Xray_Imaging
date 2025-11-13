# xavier/gpio_estop.py
import time
import threading
import RPi.GPIO as GPIO

PIN_ESTOP = 17
DEBOUNCE_S = 0.02

_GPIO_READY = False
_RUN = False
_THREAD = None
_ON_FAULT = None
_FAULT_LATCH = False


def _read_high_stable() -> int:
    v1 = GPIO.input(PIN_ESTOP)
    time.sleep(DEBOUNCE_S)
    v2 = GPIO.input(PIN_ESTOP)
    return 1 if (v1 == v2 == 1) else 0  # 1 = HIGH (safe), 0 = LOW (pressed)


def setup() -> None:
    global _GPIO_READY
    if _GPIO_READY:
        return
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(PIN_ESTOP, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # NO→HIGH safe
    _GPIO_READY = True


def cleanup() -> None:
    global _GPIO_READY
    if _GPIO_READY:
        GPIO.cleanup()
        _GPIO_READY = False


def faulted() -> bool:
    """Return True if FAULT is latched."""
    return _FAULT_LATCH


def clear_fault() -> bool:
    """
    Attempt to clear the latched fault.  Only clears if the input is HIGH
    (button released) and we are currently faulted.
    Returns True if cleared.
    """
    global _FAULT_LATCH
    if not _FAULT_LATCH:
        return True
    if _read_high_stable() == 1:
        _FAULT_LATCH = False
        return True
    return False


def estop_ok_now() -> bool:
    """Return True if the E-Stop input is HIGH (safe)."""
    return bool(_read_high_stable())


def _monitor_loop():
    global _RUN, _FAULT_LATCH, _ON_FAULT
    while _RUN:
        safe = (_read_high_stable() == 1)
        if not safe:
            if not _FAULT_LATCH:
                _FAULT_LATCH = True
                cb = _ON_FAULT
                if cb:
                    try:
                        cb()
                    except Exception as e:
                        print(f"[E-STOP] fault callback error: {e}")
            time.sleep(0.05)
        else:
            time.sleep(0.02)


def start_monitor(on_fault) -> None:
    global _RUN, _THREAD, _ON_FAULT
    setup()
    _ON_FAULT = on_fault
    if _RUN:
        return
    _RUN = True
    _THREAD = threading.Thread(target=_monitor_loop, daemon=True)
    _THREAD.start()


def stop_monitor() -> None:
    global _RUN, _THREAD
    _RUN = False
    if _THREAD and _THREAD.is_alive():
        _THREAD.join(timeout=0.5)
    _THREAD = None
