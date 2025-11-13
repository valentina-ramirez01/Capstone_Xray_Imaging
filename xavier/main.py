import sys, time
from pathlib import Path

_here = Path(__file__).resolve()
_project_root = _here.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
from xavier.camera_picam2 import start_camera, capture_still, shutdown_cam, stop_windows
from xavier.relay import hv_on, hv_off
import xavier.gpio_estop as gpio_estop
from xavier.leds import LedPanel

#PLACEHOLDER PINS — UPDATE THESE
leds = LedPanel(red=1, amber=2, green=3, blue=4)

PRE_ROLL_S = 0.5
POST_HOLD_S = 0.5

def update_leds(*, hv=False, fault=False, preview=False, armed=False):
    """
    Maps system states to LED panel policy.
    """
    state = "IDLE"
    if fault:
        state = "FAULT"
    elif preview:
        state = "PREVIEW"
    elif hv:
        state = "EXPOSE"
    elif armed:
        state = "ARMED"

    leds.apply(
        alarm=fault,
        interlocks_ok=not fault,
        state=state
    )

def handle_capture(filepath: str, frame: np.ndarray) -> None:
    print(f"[Capture] Saved to {filepath} | shape={frame.shape}")

def _on_estop_fault():
    print("\n[E-STOP] TRIPPED — shutting down camera & HV, entering Emergency Hold.")
    try:
        hv_off()
    except Exception:
        pass

    update_leds(fault=True)

    shutdown_cam()
    stop_windows()

    print("\n=== EMERGENCY HOLD ===")
    print("E-Stop is ACTIVE. Release the button, then press 'r' to reset latch, or 'q' to quit.")
    sys.stdout.flush()

def should_stop_preview() -> bool:
    return gpio_estop.faulted()

def banner():
    ok_now = gpio_estop.estop_ok_now()
    latched = gpio_estop.faulted()
    state = "OK" if ok_now else "PRESSED"
    latch = "FAULT LATCHED" if latched else "no fault"

    print("\n=== XRAY MENU ===")
    print(f"E-STOP: {state} | Latch: {latch}")

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
            if choice in ("r", "q"):
                return choice
            print("Emergency active — only 'r' or 'q' allowed.")
            continue

        print("[1] Preview (live)")
        print("[2] Photo (one-shot)")
        print("[q] Quit")
        return input("Select: ").strip().lower()

def emergency_hold_blocking():
    print("\n=== EMERGENCY HOLD ===")
    print("E-Stop is ACTIVE. System halted.")
    print("Release the E-Stop, then press 'r' to reset.")

    while True:
        try:
            hv_off()
        except Exception:
            pass

        update_leds(fault=True)

        shutdown_cam()
        stop_windows()

        cmd = input("[r]=reset, [q]=quit: ").strip().lower()

        if cmd == "q":
            sys.exit(1)

        if cmd == "r":
            if gpio_estop.clear_fault():
                print("E-Stop latch cleared.")
                update_leds()
                return
            else:
                print("Cannot clear: button still pressed.")

def run_preview():
    if gpio_estop.faulted():
        print("Cannot start preview: FAULT latched.")
        update_leds(fault=True)
        return

    hv_on()
    update_leds(hv=True, preview=True)
    print("[HV] ON (preview mode)")

    try:
        start_camera(
            on_capture=handle_capture,
            save_dir="captures",
            should_stop=should_stop_preview
        )
    finally:
        hv_off()
        update_leds()
        print("[HV] OFF")

def run_photo():
    if gpio_estop.faulted():
        print("Cannot take photo: FAULT latched.")
        update_leds(fault=True)
        return

    print("\nPhoto mode. Press ENTER to shoot; 'b'+ENTER to go back.")
    update_leds(armed=True)

    while True:
        if gpio_estop.faulted():
            emergency_hold_blocking()
            return

        cmd = input("[ENTER]=shoot, [b]=back: ").strip().lower()
        if cmd == "b":
            update_leds()
            return

        try:
            if gpio_estop.faulted():
                raise RuntimeError("E-Stop before arming.")

            hv_on()
            update_leds(hv=True)
            print("[HV] ON — pre-roll...")

            t0 = time.time()
            while time.time() - t0 < PRE_ROLL_S:
                if gpio_estop.faulted():
                    raise RuntimeError("E-stop during pre-roll.")
                time.sleep(0.01)

            if gpio_estop.faulted():
                raise RuntimeError("E-stop before capture.")

            path, _ = capture_still(still_size=(1920, 1080), save_dir="captures")
            print(f"[Photo] Saved: {path}")

            print("[HV] post-hold...")
            t1 = time.time()
            while time.time() - t1 < POST_HOLD_S:
                if gpio_estop.faulted():
                    raise RuntimeError("E-stop during post-hold.")
                time.sleep(0.01)

        except Exception as e:
            print(f"[Photo] Aborted: {e}")
            try: hv_off()
            except: pass
            update_leds(fault=True)

            shutdown_cam()
            stop_windows()
            emergency_hold_blocking()
            return

        finally:
            try:
                hv_off()
                print("[HV] OFF")
            except:
                pass

            update_leds()

        again = input("Take another? [y/N]: ").strip().lower()
        if again != "y":
            update_leds()
            return

def main():
    gpio_estop.start_monitor(_on_estop_fault)

    try:
        while True:
            if gpio_estop.faulted():
                emergency_hold_blocking()
                continue

            update_leds()

            choice = menu()
            if choice == "1":
                run_preview()
            elif choice == "2":
                run_photo()
            elif choice == "r":
                if gpio_estop.clear_fault():
                    print("E-Stop latch cleared.")
                    update_leds()
                else:
                    print("Cannot clear: button still pressed.")
            elif choice == "q":
                print("Bye.")
                break
            else:
                print("Invalid choice.")

    except KeyboardInterrupt:
        print("\n[Main] KeyboardInterrupt — exiting.")

    finally:
        try: hv_off()
        except: pass

        update_leds()

        shutdown_cam()
        stop_windows()
        gpio_estop.stop_monitor()
        gpio_estop.cleanup()
        leds.cleanup()

if __name__ == "__main__":
    main()
