# xavier/gpio_estop.py
import time
import threading
import RPi.GPIO as GPIO

# ============================================================
# CONFIG
# ============================================================

# E-STOP pin (updated to GPIO26)
PIN_ESTOP = 26

# Debounce time
DEBOUNCE_S = 0.02


# ============================================================
# INTERNAL STATE
# ============================================================
_GPIO_READY = False
_RUN = False
_THREAD = None
_ON_FAULT = None
_FAULT_LATCH = False


# ============================================================
# LOW-LEVEL INPUT (debounced)
# ============================================================
def _read_high_stable() -> int:
    """
    Reads the E-STOP pin twice with a delay (debounce).
    Returns:
        1 = HIGH (safe)
        0 = LOW  (pressed)
    """
    v1 = GPIO.input(PIN_ESTOP)
    time.sleep(DEBOUNCE_S)
    v2 = GPIO.input(PIN_ESTOP)
    return 1 if (v1 == v2 == 1) else 0


# ============================================================
# SETUP / CLEANUP
# ============================================================
def setup() -> None:
    global _GPIO_READY
    if _GPIO_READY:
        return

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # E-STOP is normally closed → input should normally read HIGH
    GPIO.setup(PIN_ESTOP, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    _GPIO_READY = True


def cleanup() -> None:
    global _GPIO_READY
    if _GPIO_READY:
        GPIO.cleanup()
        _GPIO_READY = False


# ============================================================
# USER-FACING QUERY FUNCTIONS
# ============================================================
def faulted() -> bool:
    """Returns True if the E-STOP latch is active."""
    return _FAULT_LATCH


def estop_ok_now() -> bool:
    """
    Returns realtime state of E-STOP:
    True  = safe (HIGH)
    False = pressed (LOW)
    """
    return bool(_read_high_stable())


# ============================================================
# AUTO-CLEARING LATCH (NEW LOGIC)
# ============================================================
def clear_fault() -> bool:
    """
    Clears latched fault if E-STOP is physically released.
    (Not usually needed with auto-clear enabled.)
    """
    global _FAULT_LATCH
    if not _FAULT_LATCH:
        return True
    if _read_high_stable() == 1:
        _FAULT_LATCH = False
        return True
    return False


# ============================================================
# BACKGROUND MONITOR LOOP (handles fault AND auto-clear)
# ============================================================
def _monitor_loop():
    global _RUN, _FAULT_LATCH, _ON_FAULT

    while _RUN:
        safe = (_read_high_stable() == 1)

        if not safe:
            # ----- E-STOP pressed -----
            if not _FAULT_LATCH:
                _FAULT_LATCH = True
                cb = _ON_FAULT
                if cb:
                    try:
                        cb()
                    except Exception as e:
                        print(f"[E-STOP] fault callback error: {e}")

        else:
            # ----- E-STOP physically released — auto-clear -----
            if _FAULT_LATCH:
                _FAULT_LATCH = False

        time.sleep(0.05)


# ============================================================
# START / STOP MONITOR
# ============================================================
def start_monitor(on_fault) -> None:
    """
    Starts background thread to continuously monitor the E-STOP.
    Calls on_fault() WHEN IT IS PRESSED.
    Auto-clears the latch when released.
    """
    global _RUN, _THREAD, _ON_FAULT

    setup()
    _ON_FAULT = on_fault

    if _RUN:
        return

    _RUN = True
    _THREAD = threading.Thread(target=_monitor_loop, daemon=True)
    _THREAD.start()


def stop_monitor() -> None:
    """
    Safely stops the monitor thread.
    """
    global _RUN, _THREAD
    _RUN = False

    if _THREAD and _THREAD.is_alive():
        _THREAD.join(timeout=0.5)

    _THREAD = None
