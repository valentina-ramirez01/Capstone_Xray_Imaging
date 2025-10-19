from typing import Tuple
import cv2
import numpy as np


def apply_contrast_brightness(img: np.ndarray, alpha: float = 1.0, beta: float = 0.0) -> np.ndarray:
    """
    Adjust contrast and brightness using:
      output = alpha * img + beta
    Typical ranges: alpha (0.1..5.0), beta (-100..+100).
    """
    return cv2.convertScaleAbs(img, alpha=alpha, beta=beta)


def apply_zoom(img: np.ndarray, zoom: float = 1.0) -> np.ndarray:
    """Center zoom. For zoom>=1.0: crop the center and resize back to original size."""
    if zoom <= 1.0:
        return img
    h, w = img.shape[:2]
    nh, nw = int(h / zoom), int(w / zoom)
    y1 = max((h - nh) // 2, 0)
    x1 = max((w - nw) // 2, 0)
    crop = img[y1:y1 + nh, x1:x1 + nw]
    return cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)


def fit_in_window(img: np.ndarray, max_w: int = 1280, max_h: int = 720) -> np.ndarray:
    """Shrink to fit inside a window without upscaling."""
    h, w = img.shape[:2]
    scale = min(max_w / w, max_h / h, 1.0)
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img
