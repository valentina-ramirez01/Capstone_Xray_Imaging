import os
import glob
from typing import List, Optional
import cv2
import numpy as np

from xavier.tools import apply_contrast_brightness, apply_zoom, fit_in_window


class Gallery:
    """
    Simple stateful image gallery with callable controls.

    Controls (keys):
      ←/→ : previous/next image (also supports OS-specific keycodes)
      z/x : zoom in/out (±10%)  [zoom clamped to 1.0..4.0]
      [/]: contrast down/up (±0.1)  [alpha clamped to 0.1..5.0]
      ;/' : brightness down/up (±5)  [beta clamped to -100..100]
      r   : reset view (zoom=1, alpha=1, beta=0)
      e   : export processed copy to captures/edited_XXXX.png
      q/ESC : quit
    """

    def __init__(self, image_paths: List[str], window_name: str = "Gallery"):
        self.files = image_paths
        self.win = window_name
        self.idx = 0

        # Editable viewer state
        self.alpha: float = 1.0   # contrast
        self.beta: float = 0.0    # brightness
        self.zoom: float = 1.0    # zoom factor

        self._last_processed: Optional[np.ndarray] = None

    # ----- public callable methods -----
    def set_contrast(self, alpha: float) -> None:
        self.alpha = float(np.clip(alpha, 0.1, 5.0))

    def adjust_contrast(self, d_alpha: float) -> None:
        self.set_contrast(self.alpha + d_alpha)

    def set_brightness(self, beta: float) -> None:
        self.beta = float(np.clip(beta, -100.0, 100.0))

    def adjust_brightness(self, d_beta: float) -> None:
        self.set_brightness(self.beta + d_beta)

    def set_zoom(self, z: float) -> None:
        self.zoom = float(np.clip(z, 1.0, 4.0))

    def adjust_zoom(self, step: float) -> None:
        # step is fractional: +0.10 => +10%
        self.set_zoom(self.zoom * (1.0 + step))

    def reset_view(self) -> None:
        self.alpha, self.beta, self.zoom = 1.0, 0.0, 1.0

    # ----- internal helpers -----
    def _load(self, i: int) -> Optional[np.ndarray]:
        path = self.files[i]
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        return img

    def _render_current(self) -> np.ndarray:
        path = self.files[self.idx]
        img = self._load(self.idx)
        if img is None:
            canvas = np.zeros((240, 960, 3), dtype=np.uint8)
            cv2.putText(canvas, f"Couldn't read: {os.path.basename(path)}", (20, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
            self._last_processed = canvas
            return canvas

        # Apply operations: zoom -> contrast/brightness
        proc = apply_zoom(img, self.zoom)
        proc = apply_contrast_brightness(proc, self.alpha, self.beta)

        # Compose a display frame and draw HUD
        disp = fit_in_window(proc, 1280, 720)
        hud = (
            f"{self.idx+1}/{len(self.files)}  {os.path.basename(path)}  |  "
            f"zoom {self.zoom:.2f}x  alpha {self.alpha:.2f}  beta {self.beta:.0f}"
        )
        cv2.putText(disp, hud, (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(disp, hud, (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

        self._last_processed = proc
        return disp

    def _export_current(self, out_dir: str = "captures") -> Optional[str]:
        if self._last_processed is None:
            return None
        os.makedirs(out_dir, exist_ok=True)
        n = len(glob.glob(os.path.join(out_dir, "edited_*.png")))
        out_path = os.path.join(out_dir, f"edited_{n:04d}.png")
        return out_path if cv2.imwrite(out_path, self._last_processed) else None

    # ----- event loop -----
    def run(self, start_at: Optional[str] = None) -> None:
        if not self.files:
            print("No images to show.")
            return
        if start_at and start_at in self.files:
            self.idx = self.files.index(start_at)

        cv2.namedWindow(self.win, cv2.WINDOW_AUTOSIZE)
        while True:
            cv2.imshow(self.win, self._render_current())
            k = cv2.waitKeyEx(0) & 0xFFFFFFFF

            # Quit
            if k in (27, ord('q')):
                cv2.destroyWindow(self.win)
                break

            # Prev / Next (support common codes across OSes)
            elif k in (81, 2424832):   # left arrow
                self.idx = (self.idx - 1) % len(self.files)
            elif k in (83, 2555904):   # right arrow
                self.idx = (self.idx + 1) % len(self.files)

            # Zoom
            elif k == ord('z'):
                self.adjust_zoom(+0.10)   # +10%
            elif k == ord('x'):
                self.adjust_zoom(-0.10)   # -10%

            # Contrast
            elif k == ord(']'):
                self.adjust_contrast(+0.10)
            elif k == ord('['):
                self.adjust_contrast(-0.10)

            # Brightness
            elif k == ord("'"):
                self.adjust_brightness(+5.0)
            elif k == ord(';'):
                self.adjust_brightness(-5.0)

            # Reset
            elif k == ord('r'):
                self.reset_view()

            # Export processed copy
            elif k == ord('e'):
                out = self._export_current("captures")
                print(f"Exported: {out}" if out else "Export failed.")
