# xavier/camera_picam2.py
from __future__ import annotations
import time
from typing import Callable, Optional, Tuple
from pathlib import Path
import numpy as np
import cv2
from picamera2 import Picamera2

# local imports
from .io_utils import capture_and_save_frame
from .gallery import Gallery
import xavier.gpio_estop as gpio_estop

# ============================================================
#  GLOBAL CAMERA SINGLETON
# ============================================================
_cam: Picamera2 | None = None

def get_cam() -> Picamera2:
    """Return a shared Picamera2 instance (create once)."""
    global _cam
    if _cam is None:
        _cam = Picamera2()
    return _cam


def shutdown_cam() -> None:
    """Stop and close the camera completely (full release)."""
    global _cam
    if _cam is not None:
        try:
            _cam.stop()
        except Exception:
            pass
        try:
            _cam.close()
        except Exception:
            pass
        _cam = None


def stop_windows() -> None:
    """Force-close all OpenCV windows."""
    try:
        cv2.destroyAllWindows()
    except Exception:
        pass


# ============================================================
#  CONFIG HELPERS
# ============================================================
def _pick_config(sensor_model: str | None, preview_size: Tuple[int, int]) -> dict:
    """Pick preview configuration automatically for OV sensors."""
    sensor = (sensor_model or "").lower()
    if "ov9281" in sensor:
        main = {"size": (1280, 800), "format": "RGB888"}
    elif "ov5647" in sensor:
        w, h = preview_size
        if (w, h) not in [(1296, 972), (1920, 1080), (1280, 720)]:
            w, h = (1280, 720)
        main = {"size": (w, h), "format": "RGB888"}
    else:
        main = {"size": preview_size, "format": "RGB888"}
    return main


# ============================================================
#  LIVE PREVIEW
# ============================================================
def start_camera(
    preview_size: tuple[int, int] = (1280, 720),
    window_name: str = "Picamera2 Preview",
    on_capture: Optional[Callable[[str, np.ndarray], None]] = None,
    save_dir: str = "captures",
    should_stop: Optional[Callable[[], bool]] = None,
) -> None:
    """
    Live preview window with optional E-Stop-aware stop callback.
    Press 'c' to capture, 'g' for gallery, 'q'/ESC to quit.
    """
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    cam = get_cam()

    props = cam.camera_properties or {}
    sensor_model = (props.get("Model") or props.get("SensorModel") or "").strip()
    main = _pick_config(sensor_model, preview_size)

    cfg = cam.create_preview_configuration(main=main)
    cam.configure(cfg)
    cam.set_controls({"AeEnable": True})
    cam.start()
    time.sleep(0.1)

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, main["size"][0], main["size"][1])
    print("[Picamera2] Press 'c' to capture, 'g' gallery, 'q' to quit.")

    try:
        while True:
            # Safety hook (E-Stop)
            if should_stop and should_stop():
                break
            rgb = cam.capture_array("main")
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            cv2.imshow(window_name, bgr)

            k = cv2.waitKey(1) & 0xFF
            if k in (27, ord('q')):  # ESC / q
                break
            elif k == ord('c'):
                path, _ = capture_and_save_frame(bgr, save_dir=save_dir)
                print(f"[Picamera2] Captured: {path}")
                if on_capture:
                    try:
                        on_capture(path, bgr)
                    except Exception as e:
                        print("[Picamera2] on_capture error:", e)
            elif k == ord('g'):
                paths = sorted(str(p) for p in Path(save_dir).glob("capture_*.png"))
                if not paths:
                    print("[Gallery] No images in", save_dir)
                else:
                    gal = Gallery(paths, window_name="Gallery")
                    gal.run()
                    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                    cv2.resizeWindow(window_name, main["size"][0], main["size"][1])
    finally:
        try:
            cam.stop()
        except Exception:
            pass
        stop_windows()


# ============================================================
#  ONE-SHOT STILL CAPTURE (E-STOP SAFE)
# ============================================================
def capture_still(
    still_size: Tuple[int, int] = (1920, 1080),
    save_dir: str = "captures",
) -> tuple[str, np.ndarray]:
    """
    One-shot still capture.
    Safely aborts if the E-Stop latch trips at any point.
    """
    if gpio_estop.faulted():
        raise RuntimeError("E-Stop latched before capture.")

    Path(save_dir).mkdir(parents=True, exist_ok=True)
    cam = get_cam()

    # Stop any previous preview pipeline before reconfiguring
    try:
        cam.stop()
    except Exception:
        pass

    if gpio_estop.faulted():
        raise RuntimeError("E-Stop latched before configure.")

    cfg = cam.create_still_configuration(main={"size": still_size, "format": "RGB888"})
    cam.configure(cfg)
    cam.set_controls({"AeEnable": True})

    if gpio_estop.faulted():
        raise RuntimeError("E-Stop latched before start.")
    cam.start()

    # Short warm-up loop; check for abort
    t0 = time.time()
    while time.time() - t0 < 0.06:
        if gpio_estop.faulted():
            try:
                cam.stop()
            except Exception:
                pass
            raise RuntimeError("E-Stop latched during warm-up.")
        time.sleep(0.005)

    if gpio_estop.faulted():
        try:
            cam.stop()
        except Exception:
            pass
        raise RuntimeError("E-Stop latched before capture.")

    # Perform capture
    try:
        rgb = cam.capture_array("main")
    finally:
        try:
            cam.stop()
        except Exception:
            pass

    if gpio_estop.faulted():
        raise RuntimeError("E-Stop latched after capture.")

    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    path, _ = capture_and_save_frame(bgr, save_dir=save_dir)
    return path, bgr


# ============================================================
#  TEST STANDALONE (OPTIONAL)
# ============================================================
if __name__ == "__main__":
    # Standalone preview for debugging
    try:
        start_camera()
    except KeyboardInterrupt:
        shutdown_cam()
        stop_windows()  