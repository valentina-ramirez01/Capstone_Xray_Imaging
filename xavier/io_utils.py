import os
import glob
from typing import Tuple
import cv2
import numpy as np


def capture_and_save_frame(frame_bgr: np.ndarray, save_dir: str = "captures") -> Tuple[str, np.ndarray]:
    """Save a BGR frame to disk as PNG. Returns (path, copy_of_frame)."""
    os.makedirs(save_dir, exist_ok=True)
    count = len(glob.glob(os.path.join(save_dir, "capture_*.png")))
    path = os.path.join(save_dir, f"capture_{count:04d}.png")
    ok = cv2.imwrite(path, frame_bgr)
    if not ok:
        raise RuntimeError("Failed to save image")
    return path, frame_bgr.copy()
