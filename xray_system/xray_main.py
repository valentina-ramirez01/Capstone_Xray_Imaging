
# main.py — top-level menu + live preview (AE) + manual/AE-metered photos
# Keys in camera mode:
#   p/s = photo   m = meter AE→photo (print once)   g = open Gallery
#   b = preview boost (display only)   f = fullscreen   q = quit

import sys
import subprocess
import cv2
import numpy as np

from mipi_camera import CameraController

DEFAULT_PHOTO_SHUTTER_US = 200_000  # 200 ms
DEFAULT_PHOTO_GAIN       = 16

WIN = "Mono Live — p/s:photo  m:meter  g:gallery  b:boost  f:fullscreen  q:quit"

# ---------- launch Gallery (blocking; returns when gallery closes) ----------
def launch_gallery(start_path="workspace/raw"):
    target = "xray_gallery.py"  # renamed gallery file
    try:
        subprocess.run([sys.executable, target, start_path], check=False)
    except FileNotFoundError:
        print(f"Could not find {target}. Make sure {target} is next to main.py.")
    except Exception as e:
        print(f"Failed to open gallery: {e}")

# ---------- Camera Mode ----------
def run_camera_mode():
    print("\n--- CAMERA MODE (no video record) ---")
    try:
        s_str = input(f"Photo shutter (µs) or 'auto' [{DEFAULT_PHOTO_SHUTTER_US}]: ").strip()
        g_str = input(f"Photo gain (1.0–16.0) or 'auto' [{DEFAULT_PHOTO_GAIN}]: ").strip()
    except EOFError:
        s_str, g_str = "", ""

    # Parse shutter
    if s_str == "" or s_str.lower() == "auto":
        photo_shutter = DEFAULT_PHOTO_SHUTTER_US
    else:
        try:
            photo_shutter = int(s_str)
        except ValueError:
            print(f"Invalid shutter; using default {DEFAULT_PHOTO_SHUTTER_US} µs")
            photo_shutter = DEFAULT_PHOTO_SHUTTER_US

    # Parse gain
    if g_str == "" or g_str.lower() == "auto":
        photo_gain = DEFAULT_PHOTO_GAIN
    else:
        try:
            photo_gain = float(g_str)
        except ValueError:
            print(f"Invalid gain; using default {DEFAULT_PHOTO_GAIN}")
            photo_gain = DEFAULT_PHOTO_GAIN

    cam = CameraController(preview_size=(1280, 720), still_size=(3840, 2160))
    cam.start()

    # Optional: smoother preview AE cap
    cam.set_ae_limits(exposure_max_us=33_333, gain_min=1.0, gain_max=16.0)

    # Apply photo settings
    cam.set_photo_shutter_us(photo_shutter)
    cam.set_photo_gain(photo_gain)

    # Window
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, 1280, 720)
    fullscreen = False
    preview_boost = False

    print("\nLive preview (AE on):")
    print("  p/s = take photo (uses current photo shutter/gain)")
    print("  m   = AE meter once, copy AE → photo settings (prints once)")
    print("  g   = open Gallery (camera pauses, resumes after closing)")
    print("  b   = toggle preview brightness boost (display only)")
    print("  f   = toggle fullscreen")
    print("  q   = quit\n")

    try:
        while True:
            frame = cam.grab_gray()  # AE-on preview

            # Optional display-only boost
            disp = frame
            if preview_boost:
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                disp = clahe.apply(disp)

            # Fit window nicely
            h, w = disp.shape[:2]
            scale = min(1280 / w, 720 / h)
            if scale != 1.0:
                disp = cv2.resize(disp, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

            cv2.imshow(WIN, disp)
            k = cv2.waitKey(1) & 0xFF

            if k in (ord("p"), ord("s")):
                cam.capture_photo()
            elif k == ord("m"):
                exp_us, gain, fd, mean = cam.auto_meter(settle_s=1.0, samples=3)
                cam.set_photo_shutter_us(int(exp_us))
                cam.set_photo_gain(float(gain))
                print(f"[Meter] Copied AE → photo settings: shutter={int(exp_us)} µs, gain={gain:.2f}")
            elif k == ord("b"):
                preview_boost = not preview_boost
                print(f"Preview boost: {'ON' if preview_boost else 'OFF'}")
            elif k == ord("f"):
                fullscreen = not fullscreen
                cv2.setWindowProperty(
                    WIN,
                    cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL,
                )
            elif k == ord("g"):
                # Pause camera, open gallery, resume after
                cv2.destroyWindow(WIN)
                cam.stop()
                launch_gallery("workspace/raw")
                cam.start()
                cam.set_ae_limits(exposure_max_us=33_333, gain_min=1.0, gain_max=16.0)
                cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(WIN, 1280, 720)
                cv2.setWindowProperty(
                    WIN,
                    cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL,
                )
                print("Returned from Gallery. Preview resumed.")
            elif k == ord("q"):
                break

    finally:
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        cam.stop()

# ---------- Gallery Mode (from menu) ----------
def run_gallery_mode():
    launch_gallery("workspace/raw")

# ---------- Main Menu ----------
def main_menu():
    print("\n====== MAIN ======")
    print("1) Camera")
    print("2) Gallery")
    print("q) Quit")
    return input("Select: ").strip().lower()

def main():
    while True:
        choice = main_menu()
        if choice == "1":
            run_camera_mode()
        elif choice == "2":
            run_gallery_mode()
        elif choice in ("q", "quit"):
            break
        else:
            print("Invalid choice. Try 1 / 2 / q.")

if __name__ == "__main__":
    main()
