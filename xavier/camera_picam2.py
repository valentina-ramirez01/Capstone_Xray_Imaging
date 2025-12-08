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
from .gallery import GalleryWindow     # ✅ NEW — replace old Gallery
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
#  LIVE PREVIEW WINDOW
# ============================================================
def start_camera(
    preview_size: tuple[int, int] = (1280, 720),
    window_name: str = "Picamera2 Preview",
    on_capture: Optional[Callable[[str, np.ndarray], None]] = None,
    save_dir: str = "captures",
    should_stop: Optional[Callable[[], bool]] = None,
) -> None:
    """
    Live preview using OpenCV.
    Press:
        'c' — capture
        'g' — open PyQt gallery window
        'q' / ESC — quit preview
    """
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    cam = get_cam()

    props = cam.camera_properties or {}
    sensor_model = (props.get("Model") or props.get("SensorModel") or "").strip()

    main_cfg = _pick_config(sensor_model, preview_size)

    cfg = cam.create_preview_configuration(main=main_cfg)
    cam.configure(cfg)
    cam.set_controls({"AeEnable": True})
    cam.start()
    time.sleep(0.1)

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, main_cfg["size"][0], main_cfg["size"][1])

    print("[Picamera2] Press 'c' to capture, 'g' gallery, 'q' to quit.")

    try:
        while True:
            # Safety hook — check E-STOP
            if should_stop and should_stop():
                break

            rgb = cam.capture_array("main")
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            cv2.imshow(window_name, bgr)

            k = cv2.waitKey(1) & 0xFF

            # Quit preview
            if k in (27, ord('q')):
                break

            # Capture
            elif k == ord('c'):
                path, _ = capture_and_save_frame(bgr, save_dir=save_dir)
                print(f"[Picamera2] Captured: {path}")
                if on_capture:
                    try:
                        on_capture(path, bgr)
                    except Exception as e:
                        print("[Picamera2] on_capture callback error:", e)

            # Open PyQt gallery window
            elif k == ord('g'):
                paths = (
                    sorted(str(p) for p in Path(save_dir).glob("*.jpg"))
                    + sorted(str(p) for p in Path(save_dir).glob("*.png"))
                )

                if not paths:
                    print("[Gallery] No images in", save_dir)
                else:
                    print("[Gallery] Opening PyQt gallery window…")
                    gal = GalleryWindow(paths)
                    gal.show()
                    # NOTE: Returning to OpenCV preview after PyQt window closes
                    # is not supported. This is correct behavior.

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

    # Stop live preview before reconfiguring
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

    # Warm-up check loop
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

    # Capture
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
#  STANDALONE TEST
# ============================================================
if __name__ == "__main__":
    try:
        start_camera()
    except KeyboardInterrupt:
        shutdown_cam()
        stop_windows()
