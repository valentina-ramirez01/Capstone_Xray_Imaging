# xavier/gpio_estop.py
import time
import threading
import RPi.GPIO as GPIO

# ============================================================
# CONFIG — Your E-STOP is Normally Open (NO)
# ============================================================
PIN_ESTOP = 26             # NO Switch → GPIO22 → GND
DEBOUNCE_S = 0.02           # debounce for stable reads

# ============================================================
# INTERNAL STATE
# ============================================================
_GPIO_READY = False
_RUN = False
_THREAD = None
_ON_FAULT = None
_FAULT_LATCH = False


# ============================================================
# READ STABLE VALUE
# Returns:
#   1 = released  (HIGH)
#   0 = PRESSED   (LOW)
# ============================================================
def _read_stable() -> int:
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

    # NO switch → normally HIGH (released)
    # Press = connect to GND → LOW
    GPIO.setup(PIN_ESTOP, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    _GPIO_READY = True


def cleanup() -> None:
    global _GPIO_READY
    if _GPIO_READY:
        GPIO.cleanup()
        _GPIO_READY = False


# ============================================================
# BASIC STATUS CHECKS — MATCHES LIMIT SWITCH LOGIC
# ============================================================
def faulted() -> bool:
    """Returns True if fault latch is active."""
    return _FAULT_LATCH


def estop_ok_now() -> bool:
    """
    Returns:
        True  = released (HIGH)
        False = pressed  (LOW)
    """
    return bool(_read_stable())


# ============================================================
# CLEAR FAULT (if released)
# ============================================================
def clear_fault() -> bool:
    global _FAULT_LATCH
    if not _FAULT_LATCH:
        return True

    if _read_stable() == 1:   # released
        _FAULT_LATCH = False
        return True

    return False


# ============================================================
# BACKGROUND MONITOR — Like limit switch, but threaded
# Called when PRESSED (LOW)
# Auto-clear when released (HIGH)
# ============================================================
def _monitor_loop():
    global _RUN, _FAULT_LATCH, _ON_FAULT

    while _RUN:
        val = _read_stable()

        if val == 0:  # ----- PRESSED -----
            if not _FAULT_LATCH:
                _FAULT_LATCH = True
                cb = _ON_FAULT
                if cb:
                    try:
                        cb()
                    except Exception as e:
                        print(f"[E-STOP] callback error: {e}")

        else:         # ----- RELEASED -----
            if _FAULT_LATCH:
                _FAULT_LATCH = False

        time.sleep(0.05)


# ============================================================
# START / STOP MONITOR
# ============================================================
def start_monitor(on_fault) -> None:
    """
    Starts background E-STOP monitoring.
    Calls on_fault() when button is PRESSED (LOW).
    Auto-clears latch when released.
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
    global _RUN, _THREAD
    _RUN = False

    if _THREAD and _THREAD.is_alive():
        _THREAD.join(timeout=0.5)

    _THREAD = None
