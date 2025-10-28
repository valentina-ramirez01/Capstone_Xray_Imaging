import os
import glob
from typing import Callable, Optional
import numpy as np
import cv2

from xavier.gallery import Gallery
from xavier.io_utils import capture_and_save_frame


def start_camera(
    cam_index: int = 1,
    window_name: str = "Webcam Feed",
    on_capture: Optional[Callable[[str, np.ndarray], None]] = None,
    save_dir: str = "captures",
) -> None:
    """
    Live preview + capture + open gallery.
    Keys (in live view):
      - 's': save current frame to disk
      - 'g': open gallery with current session's images
      - 'G': open gallery with ALL images in save_dir
      - 'q': quit
    """
    cap = cv2.VideoCapture(cam_index)
    if not cap.isOpened():
        print(f"Could not open camera at index {cam_index}")
        return

    os.makedirs(save_dir, exist_ok=True)
    session_paths: list[str] = []
    last_path: Optional[str] = None

    print("Camera running. Keys: 's' save, 'g' session gallery, 'G' all, 'q' quit.")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            break

        cv2.imshow(window_name, frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('s'):
            try:
                path, frame_np = capture_and_save_frame(frame, save_dir=save_dir)
                session_paths.append(path)
                last_path = path
                print(f"Saved: {path}")
                if on_capture is not None:
                    on_capture(path, frame_np)
            except Exception as e:
                print(f"Capture error: {e}")

        elif key == ord('g'):
            # Gallery for images captured this session
            gal = Gallery(session_paths, window_name="Gallery (session)")
            gal.run(start_at=last_path)
            cv2.imshow(window_name, frame)  # restore live window

        elif key == ord('G'):
            # Gallery for ALL images in save_dir
            all_paths = sorted(glob.glob(os.path.join(save_dir, "capture_*.png")))
            gal = Gallery(all_paths, window_name="Gallery (all)")
            gal.run(start_at=last_path)
            cv2.imshow(window_name, frame)

        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
