import os
import glob
from typing import List, Optional
import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QMessageBox
)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

from xavier.tools import apply_contrast_brightness, fit_in_window


# =====================================================================
#   IMAGE EDITOR WINDOW  —  FIXED SIZE + PROPER SCALING (NO STRETCH)
# =====================================================================
class ImageEditorWindow(QWidget):
    def __init__(self, img_path: str):
        super().__init__()

        self.setWindowTitle("Edit Image")

        # FIX: safe standalone size (NOT fullscreen)
        self.setMinimumSize(400, 300)
        self.resize(900, 700)

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
        layout.addWidget(self.preview, 1)
        layout.addLayout(controls)

        self.update_preview()

    # ------------------------------------------------------------------
    def update_preview(self):
        edited = apply_contrast_brightness(self.original, self.alpha, self.beta)

        win_w = self.preview.width()
        win_h = self.preview.height()
        if win_w < 50 or win_h < 50:
            win_w, win_h = 200, 200

        disp = fit_in_window(edited, win_w, win_h)

        h, w = disp.shape[:2]
        qimg = QImage(disp.data, w, h, 3*w, QImage.Format.Format_BGR888)
        self.preview.setPixmap(QPixmap.fromImage(qimg))

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
#   **NEW** PYQT6 GALLERY WINDOW — NO STRETCH EVER
# =====================================================================
class GalleryWindow(QWidget):
    def __init__(self, images: List[str]):
        super().__init__()

        self.images = images
        self.idx = 0

        self.setWindowTitle("Gallery Viewer")
        self.resize(1280, 720)

        # Main display area
        self.preview = QLabel("")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background-color:black;")

        # Buttons
        btn_prev = QPushButton("⟵ Previous")
        btn_next = QPushButton("Next ⟶")
        btn_edit = QPushButton("Edit Image")
        btn_close = QPushButton("Close")

        btn_prev.clicked.connect(self.prev_img)
        btn_next.clicked.connect(self.next_img)
        btn_edit.clicked.connect(self.open_editor)
        btn_close.clicked.connect(self.close)

        controls = QHBoxLayout()
        for b in (btn_prev, btn_next, btn_edit, btn_close):
            controls.addWidget(b)

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, 1)
        layout.addLayout(controls)

        self.update_image()

    # ----------------------------------------------------------
    def load_image(self, path):
        img = cv2.imread(path)
        if img is None:
            return None
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # ----------------------------------------------------------
    def update_image(self):
        path = self.images[self.idx]
        img = self.load_image(path)

        if img is None:
            return

        h, w = img.shape[:2]
        qimg = QImage(img.data, w, h, 3*w, QImage.Format.Format_RGB888)

        # EXACTLY THE SAME SCALING LOGIC AS MAIN GUI
        pix = QPixmap.fromImage(qimg).scaled(
            self.preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.preview.setPixmap(pix)

    # ----------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_image()

    # ----------------------------------------------------------
    def prev_img(self):
        self.idx = (self.idx - 1) % len(self.images)
        self.update_image()

    def next_img(self):
        self.idx = (self.idx + 1) % len(self.images)
        self.update_image()

    # ----------------------------------------------------------
    def open_editor(self):
        editor = ImageEditorWindow(self.images[self.idx])
        editor.show()
