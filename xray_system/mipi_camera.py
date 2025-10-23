
# mipi_camera.py — IMX415 mono: preview (AE on) + photo (manual or AE-metered)
# No video recording in this build.

from __future__ import annotations
import time
from datetime import datetime
from typing import Optional, Tuple

import cv2
import numpy as np
from picamera2 import Picamera2

class CameraController:
    def __init__(
        self,
        preview_size: Tuple[int, int] = (1280, 720),
        still_size: Tuple[int, int] = (3840, 2160),
    ):
        self.preview_size = preview_size
        self.still_size = still_size

        self.picam = Picamera2()
        self.preview_cfg = self.picam.create_preview_configuration(main={"size": self.preview_size})
        self.still_cfg   = self.picam.create_still_configuration(main={"size": self.still_size})

        self.picam.configure(self.preview_cfg)
        self._mode = "preview"

        # Photo-only settings (used when capturing stills)
        self._photo_shutter_us: Optional[int] = 200_000  # sensible default for dim rooms
        self._photo_gain: Optional[float] = 4.0

    # ---------- lifecycle ----------
    def start(self):
        self.picam.start()
        time.sleep(0.1)
        self.picam.set_controls({"AeEnable": True})  # AE for preview

    def stop(self):
        try:
            self.picam.stop()
        except Exception:
            pass

    # ---------- safe mode switching ----------
    def _switch_mode(self, cfg, to_mode: str):
        try:
            self.picam.switch_mode(cfg)  # fast mode change while running
        except AttributeError:
            # Fallback if switch_mode not in your Picamera2
            need_restart = False
            try:
                self.picam.stop()
                need_restart = True
            except Exception:
                pass
            self.picam.configure(cfg)
            if need_restart:
                self.picam.start()
                time.sleep(0.05)
        self._mode = to_mode

    def _ensure_preview(self):
        if self._mode != "preview":
            self._switch_mode(self.preview_cfg, "preview")
            self.picam.set_controls({"AeEnable": True})
            time.sleep(0.01)

    def _ensure_still(self):
        if self._mode != "still":
            self._switch_mode(self.still_cfg, "still")
            time.sleep(0.01)

    # ---------- AE helpers ----------
    def set_ae_limits(
        self,
        exposure_min_us: int | None = None,
        exposure_max_us: int | None = None,
        gain_min: float | None = None,
        gain_max: float | None = None,
    ):
        ctl = {}
        if exposure_min_us is not None or exposure_max_us is not None:
            lo = 1 if exposure_min_us is None else int(exposure_min_us)
            hi = 1_000_000 if exposure_max_us is None else int(exposure_max_us)
            ctl["ExposureTimeRange"] = (lo, hi)
        if gain_min is not None or gain_max is not None:
            lo = 1.0 if gain_min is None else float(gain_min)
            hi = 32.0 if gain_max is None else float(gain_max)
            ctl["AnalogueGainRange"] = (lo, hi)
        if ctl:
            try:
                self.picam.set_controls(ctl)
            except Exception as e:
                print("AE limit warning:", e)

    def auto_meter(self, settle_s: float = 1.0, samples: int = 3):
        """Let AE settle, read metadata a few times, return (exp_us, gain, frame_duration, mean_level)."""
        import numpy as np
        self._ensure_preview()
        try:
            self.picam.set_controls({"AeEnable": True})
        except Exception:
            pass

        t0 = time.time()
        while time.time() - t0 < max(0.0, settle_s):
            time.sleep(0.05)

        exps, gains, fds, means = [], [], [], []
        for _ in range(max(1, samples)):
            frame = self.picam.capture_array("main")
            if frame.ndim == 3 and frame.shape[2] == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            means.append(float(np.mean(frame)))
            md = self.picam.capture_metadata()
            exps.append(float(md.get("ExposureTime", 0.0)))
            gains.append(float(md.get("AnalogueGain", 0.0)))
            fds.append(float(md.get("FrameDuration", 0.0)))
            time.sleep(0.02)

        return int(np.mean(exps)), float(np.mean(gains)), int(np.mean(fds)), float(np.mean(means))

    # ---------- photo settings ----------
    def set_photo_shutter_us(self, shutter_us: Optional[int]):
        self._photo_shutter_us = shutter_us

    def set_photo_gain(self, gain: Optional[float]):
        self._photo_gain = gain

    # ---------- preview frame ----------
    def grab_gray(self):
        self._ensure_preview()
        frame = self.picam.capture_array("main")
        if frame.ndim == 3 and frame.shape[2] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return frame

    # ---------- still capture ----------
    def capture_photo(self, path: Optional[str] = None) -> str:
        if path is None:
            path = datetime.now().strftime("mono_%Y%m%d_%H%M%S.png")

        self._ensure_still()

        # apply manual settings (or AE if both None)
        try:
            ctl = {}
            if self._photo_shutter_us is None and self._photo_gain is None:
                ctl["AeEnable"] = True
            else:
                ctl["AeEnable"] = False
                if self._photo_shutter_us is not None:
                    ctl["ExposureTime"] = int(self._photo_shutter_us)
                if self._photo_gain is not None:
                    ctl["AnalogueGain"] = float(self._photo_gain)
            if ctl:
                self.picam.set_controls(ctl)
        except Exception as e:
            print("Photo control warning:", e)

        img = self.picam.capture_array("main")
        if img.ndim == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cv2.imwrite(path, img)
        print(f"Saved photo → {path}")

        # back to preview AE
        self._ensure_preview()
        self.picam.set_controls({"AeEnable": True})
        return path
