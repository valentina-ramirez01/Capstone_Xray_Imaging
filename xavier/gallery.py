import os
import glob
from typing import List, Optional
import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox
)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

# Tools used by both editor + gallery
from xavier.tools import apply_contrast_brightness, apply_zoom, fit_in_window


# =====================================================================
#   PYQT6 IMAGE EDITOR WINDOW
# =====================================================================
class ImageEditorWindow(QWidget):
    def __init__(self, img_path: str):
        super().__init__()

        self.setWindowTitle("Edit Image")
        self.setMinimumSize(400, 300)
        self.resize(900, 700)

        self.img_path = img_path
        self.original = cv2.imread(img_path)

        if self.original is None:
            QMessageBox.critical(self, "Error", f"Could not read {img_path}")
            self.close()
            return

        # Working parameters
        self.alpha = 1.0   # contrast
        self.beta = 0      # brightness

        # UI
        self.preview = QLabel("")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background-color:black;")

        # Controls
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

        controls = QHBoxLayout()
        for b in (btn_inc_con, btn_dec_con, btn_inc_bri, btn_dec_bri, btn_save, btn_close):
            controls.addWidget(b)

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, stretch=1)
        layout.addLayout(controls)

        self.update_preview()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview()

    def update_preview(self):
        edited = apply_contrast_brightness(self.original, self.alpha, self.beta)

        win_w = max(self.preview.width(), 50)
        win_h = max(self.preview.height(), 50)

        disp = fit_in_window(edited, win_w, win_h)

        h, w = disp.shape[:2]
        qimg = QImage(disp.data, w, h, 3*w, QImage.Format.Format_BGR888)
        self.preview.setPixmap(QPixmap.fromImage(qimg))

    def adjust_contrast(self, da):
        self.alpha = float(np.clip(self.alpha + da, 0.1, 5.0))
        self.update_preview()

    def adjust_brightness(self, db):
        self.beta = float(np.clip(self.beta + db, -100, 100))
        self.update_preview()

    def save_copy(self):
        base_dir = os.path.dirname(self.img_path)
        n = len(glob.glob(os.path.join(base_dir, "edited_*.png")))
        out_path = os.path.join(base_dir, f"edited_{n:04d}.png")

        edited = apply_contrast_brightness(self.original, self.alpha, self.beta)
        cv2.imwrite(out_path, edited)

        QMessageBox.information(self, "Saved", f"Edited copy saved:\n{out_path}")


# =====================================================================
#   PYQT6 GALLERY WINDOW  — FIXED TO MATCH GUI SCALING
# =====================================================================
class GalleryWindow(QWidget):
    def __init__(self, image_paths: List[str]):
        super().__init__()

        self.setWindowTitle("X-Ray Gallery")
        self.resize(1280, 720)

        self.paths = image_paths
        self.idx = 0

        # Preview label
        self.preview = QLabel("")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background-color:black;")

        # Controls
        btn_prev = QPushButton("Previous")
        btn_next = QPushButton("Next")
        btn_edit = QPushButton("Edit")
        btn_close = QPushButton("Close")

        btn_prev.clicked.connect(self.prev_image)
        btn_next.clicked.connect(self.next_image)
        btn_edit.clicked.connect(self.open_editor)
        btn_close.clicked.connect(self.close)

        controls = QHBoxLayout()
        for b in (btn_prev, btn_next, btn_edit, btn_close):
            controls.addWidget(b)

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, stretch=1)
        layout.addLayout(controls)

        # INITIAL RENDER
        self.update_preview()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview()

    def update_preview(self):
        path = self.paths[self.idx]
        img = cv2.imread(path)

        if img is None:
            return

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        win_w = max(self.preview.width(), 100)
        win_h = max(self.preview.height(), 100)

        h, w = img.shape[:2]
        scale = min(win_w / w, win_h / h)

        new_w = int(w * scale)
        new_h = int(h * scale)

        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        qimg = QImage(resized.data, new_w, new_h, 3*new_w, QImage.Format_RGB888)
        self.preview.setPixmap(QPixmap.fromImage(qimg))

    def prev_image(self):
        self.idx = (self.idx - 1) % len(self.paths)
        self.update_preview()

    def next_image(self):
        self.idx = (self.idx + 1) % len(self.paths)
        self.update_preview()

    def open_editor(self):
        editor = ImageEditorWindow(self.paths[self.idx])
        editor.show()


# =====================================================================
#   LEGACY OPENCV GALLERY (STILL AVAILABLE IF NEEDED)
# =====================================================================
class Gallery:
    def __init__(self, image_paths: List[str], window_name: str = "Gallery"):
        self.files = image_paths
        self.win = window_name
        self.idx = 0
        self.alpha = 1.0
        self.beta = 0.0
        self.zoom = 1.0

    def _load(self, i: int) -> Optional[np.ndarray]:
        return cv2.imread(self.files[i])

    def run(self):
        if not self.files:
            print("No images.")
            return

        cv2.namedWindow(self.win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.win, 1280, 720)

        while True:
            img = self._load(self.idx)
            disp = fit_in_window(img, 1280, 720)

            cv2.imshow(self.win, disp)
            k = cv2.waitKeyEx(0) & 0xFFFFFFFF

            if k in (27, ord('q')):
                cv2.destroyWindow(self.win)
                break
            elif k in (81, 2424832, 65361):  # LEFT
                self.idx = (self.idx - 1) % len(self.files)
            elif k in (83, 2555904, 65363):  # RIGHT
                self.idx = (self.idx + 1) % len(self.files)
            elif k in (ord('e'), ord('E')):
                ImageEditorWindow(self.files[self.idx]).show()
