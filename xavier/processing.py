from typing import Dict, Any
import numpy as np
from xavier.tools import apply_contrast_brightness, apply_zoom


def apply_pipeline(img_bgr: np.ndarray, cfg: Dict[str, Any]) -> np.ndarray:
    """
    Example pipeline applying zoom and contrast/brightness based on a config dict.
    cfg keys (all optional):
      - zoom: float >= 1.0
      - alpha: contrast multiplier
      - beta: brightness offset
    """
    z = float(cfg.get("zoom", 1.0))
    a = float(cfg.get("alpha", 1.0))
    b = float(cfg.get("beta", 0.0))

    out = apply_zoom(img_bgr, z)
    out = apply_contrast_brightness(out, a, b)
    return out



