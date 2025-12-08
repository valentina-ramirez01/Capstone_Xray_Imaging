import os
import glob
from typing import List, Optional
import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QSlider
)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

from xavier.tools import apply_contrast_brightness, apply_zoom, fit_in_window


# =====================================================================
#   PYQT6 IMAGE EDITOR WINDOW  —  FIXED SIZE + PROPER SCALING
# =====================================================================
class ImageEditorWindow(QWidget):
    def __init__(self, img_path: str):
        super().__init__()

        self.setWindowTitle("Edit Image")

        # FIX: start at a reasonable size
        self.setMinimumSize(400, 300)
        self.resize(900, 700)       # safe size, not fullscreen

        self.img_path = img_path
        self.original = cv2.imread(img_path)

        if self.original is None:
            QMessageBox.critical(self, "Error", f"Could not read {img_path}")
            self.close()
            return

        # Working parameters
        self.alpha = 1.0
        self.beta = 0

        # UI
        self.preview = QLabel("")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background-color:black;")

        # Buttons
        btn_inc_con = QPushButton("Contrast +")
        btn_dec_con = QPushButton("Contrast -")
        btn_inc_bri = QPushButton("Brightness +")
        btn_dec_bri = QPushButton("Brightness -")
        btn_save    = QPushButton("Save Edited Copy")
        btn_close   = QPushButton("Close")

        btn_inc_con.clicked.connect(lambda: self.adjust_contrast(+0.1))
        btn_dec_con.clicked.connect(lambda: self.adjust_contrast(-0.1))
        btn_inc_bri.clicked.connect(lambda: self.adjust_brightness(+5))
        btn_dec_bri.clicked.connect(lambda: self.adjust_brightness(-5))
        btn_save.clicked.connect(self.save_copy)
        btn_close.clicked.connect(self.close)

        # Layout
        controls = QHBoxLayout()
        for b in (btn_inc_con, btn_dec_con, btn_inc_bri, btn_dec_bri, btn_save, btn_close):
            controls.addWidget(b)

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, stretch=1)
        layout.addLayout(controls)

        # Render for first time
        self.update_preview()

    # ------------------------------------------------------------------
    def update_preview(self):
        """
        Apply edits and scale image using the SAME method as gallery: fit_in_window.
        """
        edited = apply_contrast_brightness(self.original, self.alpha, self.beta)

        # SCALE using fit_in_window() just like gallery
        win_w = self.preview.width()
        win_h = self.preview.height()
        if win_w < 50 or win_h < 50:
            win_w, win_h = 200, 200

        disp = fit_in_window(edited, win_w, win_h)

        h, w = disp.shape[:2]
        qimg = QImage(disp.data, w, h, 3*w, QImage.Format.Format_BGR888)
        self.preview.setPixmap(QPixmap.fromImage(qimg))

    # FIX: Update preview live when window is resized
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview()

    # ------------------------------------------------------------------
    def adjust_contrast(self, da):
        self.alpha = float(np.clip(self.alpha + da, 0.1, 5.0))
        self.update_preview()

    def adjust_brightness(self, db):
        self.beta = float(np.clip(self.beta + db, -100, 100))
        self.update_preview()

    # ------------------------------------------------------------------
    def save_copy(self):
        base_dir = os.path.dirname(self.img_path)
        n = len(glob.glob(os.path.join(base_dir, "edited_*.png")))
        out_path = os.path.join(base_dir, f"edited_{n:04d}.png")

        edited = apply_contrast_brightness(self.original, self.alpha, self.beta)
        cv2.imwrite(out_path, edited)
        QMessageBox.information(self, "Saved", f"Edited copy saved:\n{out_path}")

# =====================================================================
#   MAIN GALLERY (OpenCV Window)
# =====================================================================
class Gallery:
    """
    Extended gallery plus optional PyQt6 editor window.
    """

    def __init__(self, image_paths: List[str], window_name: str = "Gallery"):
        self.files = image_paths
        self.win = window_name
        self.idx = 0

        # Viewer state
        self.alpha: float = 1.0
        self.beta: float = 0.0
        self.zoom: float = 1.0

        self._last_processed: Optional[np.ndarray] = None

    # ---------------- USER ACTION HOOK ----------------
    def open_in_editor(self):
        """
        Launch PyQt6 editor for the current image.
        """
        path = self.files[self.idx]
        editor = ImageEditorWindow(path)
        editor.show()

    # ---------------- Viewer Internals ----------------
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
        self.set_zoom(self.zoom * (1.0 + step))

    def reset_view(self) -> None:
        self.alpha, self.beta, self.zoom = 1.0, 0.0, 1.0

    def _load(self, i: int) -> Optional[np.ndarray]:
        path = self.files[i]
        return cv2.imread(path, cv2.IMREAD_COLOR)

    def _render_current(self) -> np.ndarray:
        path = self.files[self.idx]
        img = self._load(self.idx)

        if img is None:
            canvas = np.zeros((240, 960, 3), dtype=np.uint8)
            cv2.putText(canvas, f"Couldn't read: {os.path.basename(path)}",
                        (20,140), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (0,255,255), 2)
            self._last_processed = canvas
            return canvas

        proc = apply_zoom(img, self.zoom)
        proc = apply_contrast_brightness(proc, self.alpha, self.beta)
        disp = fit_in_window(proc, 1280, 720)

        hud = (
            f"{self.idx+1}/{len(self.files)}  {os.path.basename(path)}  |  "
            f"zoom {self.zoom:.2f}x  alpha {self.alpha:.2f}  beta {self.beta:.0f}"
        )
        cv2.putText(disp, hud, (12, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3)
        cv2.putText(disp, hud, (12, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)

        self._last_processed = proc
        return disp

    # =================================================================
    # FIXED KEYBOARD HANDLING — RASPBERRY PI + OPENCV COMPATIBLE
    # =================================================================
    def run(self):
        if not self.files:
            print("No images.")
            return

        cv2.namedWindow(self.win, cv2.WINDOW_AUTOSIZE)

        while True:
            cv2.imshow(self.win, self._render_current())
            k = cv2.waitKeyEx(0) & 0xFFFFFFFF

            # Quit
            if k in (27, ord('q')):
                cv2.destroyWindow(self.win)
                break

            # -------------------------------
            # LEFT ARROW (all possible keycodes)
            # -------------------------------
            elif k in (81, 2424832, 65361):
                self.idx = (self.idx - 1) % len(self.files)

            # -------------------------------
            # RIGHT ARROW (all possible keycodes)
            # -------------------------------
            elif k in (83, 2555904, 65363):
                self.idx = (self.idx + 1) % len(self.files)

            # Optional: Zoom with Up/Down arrows
            elif k in (82, 65362):   # UP
                self.adjust_zoom(+0.1)
            elif k in (84, 65364):   # DOWN
                self.adjust_zoom(-0.1)

            # Edit (E key)
            elif k in (ord('e'), ord('E')):
                self.open_in_editor() 