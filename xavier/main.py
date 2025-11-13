# xavier/main.py
# --- sys.path bootstrap (as you already added) ---
import sys, time
from pathlib import Path
_here = Path(__file__).resolve()
_project_root = _here.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# -------------------------------------------------

import numpy as np
from xavier.camera_picam2 import start_camera, capture_still, shutdown_cam, stop_windows
from xavier.relay import hv_on, hv_off
import xavier.gpio_estop as gpio_estop

PRE_ROLL_S = 0.5
POST_HOLD_S = 0.5

_FAULT_TRIPPED = False

def handle_capture(filepath: str, frame: np.ndarray) -> None:
    print(f"[Capture] Saved to {filepath} | shape={frame.shape}")

def _on_estop_fault():
    """Asynchronous trip: cut everything *immediately* and show hold guidance."""
    print("\n[E-STOP] TRIPPED — shutting down camera & HV, entering Emergency Hold.")
    try: hv_off()
    except Exception: pass
    shutdown_cam()
    stop_windows()

    # 👇 Show the instructions *right now*, even if input() is waiting
    print("\n=== EMERGENCY HOLD ===")
    print("E-Stop is ACTIVE. Release the button, then press 'r' to reset latch, or 'q' to quit.")
    sys.stdout.flush()   # make sure it appears immediately

def should_stop_preview() -> bool:
    """Checked inside the preview loop to exit gracefully when E-Stop trips."""
    return gpio_estop.faulted()

def banner():
    ok_now = gpio_estop.estop_ok_now()
    latched = gpio_estop.faulted()
    state = "OK" if ok_now else "PRESSED"
    latch = "FAULT LATCHED" if latched else "no fault"
    print("\n=== XRAY MENU ===")
    print(f"E-STOP: {state} | Latch: {latch}")

    if latched:
        if ok_now:
            print("→ E-Stop released — press 'r' to reset latch and return to normal.")
        else:
            print("→ E-Stop is still PRESSED. Release it to allow reset.")

def menu() -> str:
    while True:
        banner()
        if gpio_estop.faulted():
            if gpio_estop.estop_ok_now():
                print("[r] Reset E-Stop latch (button released)")
            else:
                print("[r] Reset E-Stop latch (blocked: button still pressed)")
            print("[q] Quit")

            choice = input("Select: ").strip().lower()
            # Only allow r/q while faulted; keep prompting otherwise
            if choice in ("r", "q"):
                return choice
            print("Emergency active — only 'r' or 'q' are valid. ")
            continue

        # Normal (no fault) menu
        print("[1] Preview (live)")
        print("[2] Photo (one-shot)")
        print("[q] Quit")
        return input("Select: ").strip().lower()

def emergency_hold_blocking():
    """Hard-stop state: do nothing until user resets the latched FAULT."""
    print("\n=== EMERGENCY HOLD ===")
    print("E-Stop is ACTIVE. System is halted.")
    print("Release the E-Stop, then press 'r' to reset latch and return to menu.")
    while True:
        # Ensure we are safe every loop
        try: hv_off()
        except Exception: pass
        shutdown_cam()
        stop_windows()

        cmd = input("[r]=reset latch, [q]=quit: ").strip().lower()
        if cmd == "q":
            sys.exit(1)
        if cmd == "r":
            if gpio_estop.clear_fault():
                print("E-Stop latch cleared.")
                global _FAULT_TRIPPED
                _FAULT_TRIPPED = False
                return
            else:
                print("Cannot clear: E-Stop still pressed. Release it first.")

def run_preview():
    if gpio_estop.faulted():
        print("Cannot start preview: FAULT latched. Reset first.")
        return
    hv_on()
    print("[HV] ON (preview mode)")
    try:
        start_camera(on_capture=handle_capture, save_dir="captures", should_stop=should_stop_preview)
    finally:
        hv_off()
        print("[HV] OFF")

def run_photo():
    if gpio_estop.faulted():
        print("Cannot take photo: FAULT latched. Reset first.")
        return

    print("\nPhoto mode (no preview). Press ENTER to shoot; 'b'+ENTER to go back.")
    while True:
        if gpio_estop.faulted():
            emergency_hold_blocking()
            return

        cmd = input("[ENTER]=shoot, [b]=back: ").strip().lower()
        if cmd == "b":
            return

        # Arm + capture with pre/post; abort immediately on E-Stop at any point.
        try:
            if gpio_estop.faulted():
                raise RuntimeError("E-Stop before arming.")

            hv_on()
            print("[HV] ON — pre-roll...")

            t0 = time.time()
            while time.time() - t0 < PRE_ROLL_S:
                if gpio_estop.faulted():
                    raise RuntimeError("E-Stop during pre-roll.")
                time.sleep(0.01)

            if gpio_estop.faulted():
                raise RuntimeError("E-Stop before capture.")

            path, _ = capture_still(still_size=(1920, 1080), save_dir="captures")
            print(f"[Photo] Saved: {path}")

            print("[HV] post-hold...")
            t1 = time.time()
            while time.time() - t1 < POST_HOLD_S:
                if gpio_estop.faulted():
                    raise RuntimeError("E-Stop during post-hold.")
                time.sleep(0.01)

        except Exception as e:
            # Any failure/E-Stop → ensure safe state and enter Emergency Hold
            print(f"[Photo] Aborted: {e}")
            try: hv_off()
            except Exception: pass
            shutdown_cam()
            stop_windows()
            emergency_hold_blocking()
            return

        finally:
            # Always ensure HV is OFF when the cycle ends or aborts
            try:
                hv_off()
                print("[HV] OFF")
            except Exception:
                pass

        again = input("Take another? [y/N]: ").strip().lower()
        if again != "y":
            return


def main():
    gpio_estop.start_monitor(_on_estop_fault)
    try:
        while True:
            # Global guard: if fault latched, block here until reset
            if gpio_estop.faulted():
                emergency_hold_blocking()
                continue

            choice = menu()

            if choice == "1" and not gpio_estop.faulted():
                run_preview()
            elif choice == "2" and not gpio_estop.faulted():
                run_photo()
            elif choice == "r":
                # Only offered when faulted(), but keep graceful behavior:
                if gpio_estop.clear_fault():
                    print("E-Stop latch cleared.")
                else:
                    print("Cannot clear: E-Stop still pressed.")
            elif choice == "q":
                print("Bye.")
                break
            else:
                print("Invalid choice.")
    except KeyboardInterrupt:
        print("\n[Main] KeyboardInterrupt — exiting.")
    finally:
        try: hv_off()
        except Exception: pass
        shutdown_cam()
        stop_windows()
        gpio_estop.stop_monitor()
        gpio_estop.cleanup()

if __name__ == "__main__":
    main()
