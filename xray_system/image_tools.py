
# image_tools.py — editor with persistent params (--auto-load / --params)

import sys, json, argparse
from pathlib import Path
import cv2
import numpy as np

def load_gray(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"Cannot load image: {path}")
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img

def ensure_edits_dir(original: Path) -> Path:
    if original.parent.name.lower() == "raw":
        ed = original.parent.parent / "edits"
    else:
        ed = original.parent / "edits"
    ed.mkdir(parents=True, exist_ok=True)
    return ed

class Editor:
    def __init__(self, path: Path):
        self.path = path
        self.base = load_gray(path)
        self.h, self.w = self.base.shape[:2]
        # Defaults
        self.zoom = 1.0
        self.cx, self.cy = self.w // 2, self.h // 2
        self.contrast = 1.0
        self.sharpness = 0.0
        self.gamma = 1.0
        self.filter_idx = 0
        self.filters = ["none", "invert", "equalize", "clahe", "edges", "magma"]

    # ----- params I/O -----
    def to_dict(self):
        return {
            "zoom": self.zoom,
            "center": [self.cx, self.cy],
            "contrast": self.contrast,
            "sharpness": self.sharpness,
            "gamma": self.gamma,
            "filter": self.filters[self.filter_idx],
        }

    def apply_dict(self, d: dict):
        self.zoom = float(d.get("zoom", self.zoom))
        c = d.get("center", [self.cx, self.cy])
        if isinstance(c, (list, tuple)) and len(c) == 2:
            self.cx, self.cy = int(c[0]), int(c[1])
        self.contrast = float(d.get("contrast", self.contrast))
        self.sharpness = float(d.get("sharpness", self.sharpness))
        self.gamma = float(d.get("gamma", self.gamma))
        filt = d.get("filter", self.filters[self.filter_idx])
        if filt in self.filters:
            self.filter_idx = self.filters.index(filt)

    def default_sidecar_candidates(self) -> list[Path]:
        # 1) same folder: file.ext.json
        a = self.path.with_suffix(self.path.suffix + ".json")
        # 2) edits folder with same name: edits/file.ext.json
        ed = ensure_edits_dir(self.path) / (self.path.name + ".json")
        return [a, ed]

    def try_autoload(self, explicit_params: Path | None):
        if explicit_params:
            if explicit_params.exists():
                with open(explicit_params, "r") as f:
                    self.apply_dict(json.load(f))
                print(f"Loaded params from {explicit_params}")
            else:
                print(f"Param file not found: {explicit_params}")
            return
        # Search defaults
        for cand in self.default_sidecar_candidates():
            if cand.exists():
                try:
                    with open(cand, "r") as f:
                        self.apply_dict(json.load(f))
                    print(f"Auto-loaded params from {cand}")
                    return
                except Exception as e:
                    print(f"Failed to load {cand}: {e}")

    # ----- editing ops -----
    def reset(self):
        self.zoom = 1.0
        self.cx, self.cy = self.w // 2, self.h // 2
        self.contrast = 1.0
        self.sharpness = 0.0
        self.gamma = 1.0
        self.filter_idx = 0

    def render(self) -> np.ndarray:
        img = self.base

        # Zoom & pan
        if self.zoom > 1.0:
            half_w = int((self.w / self.zoom) / 2)
            half_h = int((self.h / self.zoom) / 2)
            x1 = max(0, self.cx - half_w)
            y1 = max(0, self.cy - half_h)
            x2 = min(self.w, self.cx + half_w)
            y2 = min(self.h, self.cy + half_h)
            crop = img[y1:y2, x1:x2]
            img = cv2.resize(crop, (self.w, self.h), interpolation=cv2.INTER_CUBIC)

        # Contrast (alpha)
        if self.contrast != 1.0:
            img = cv2.convertScaleAbs(img, alpha=self.contrast, beta=(1 - self.contrast) * 128)

        # Gamma
        if abs(self.gamma - 1.0) > 1e-3:
            inv = 1.0 / max(self.gamma, 1e-6)
            lut = np.array([((i / 255.0) ** inv) * 255.0 for i in range(256)]).astype(np.uint8)
            img = cv2.LUT(img, lut)

        # Sharpness (unsharp mask)
        if self.sharpness > 0:
            blur = cv2.GaussianBlur(img, (0, 0), sigmaX=1.0 + self.sharpness)
            img = cv2.addWeighted(img, 1 + self.sharpness, blur, -self.sharpness, 0)

        # Filters / tints
        f = self.filters[self.filter_idx]
        if f == "invert":
            img = 255 - img
        elif f == "equalize":
            img = cv2.equalizeHist(img)
        elif f == "clahe":
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img = clahe.apply(img)
        elif f == "edges":
            img = cv2.Canny(img, 50, 150)
        elif f == "magma":
            img = cv2.applyColorMap(img, cv2.COLORMAP_MAGMA)
            return img  # 3-channel

        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    def save(self):
        edits_dir = ensure_edits_dir(self.path)
        out_path = edits_dir / self.path.name
        cv2.imwrite(str(out_path), self.render())
        with open(str(out_path) + ".json", "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"Saved edited → {out_path}")
        return out_path

    def save_params_only(self):
        edits_dir = ensure_edits_dir(self.path)
        out_path = edits_dir / (self.path.name + ".json")
        with open(out_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"Saved params → {out_path}")

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def parse_args():
    ap = argparse.ArgumentParser(description="Mono image editor with persistent params.")
    ap.add_argument("image", help="Path to the image to edit")
    ap.add_argument("--auto-load", action="store_true",
                    help="Auto-load previous JSON params if found (sidecar or edits/)")
    ap.add_argument("--params", type=str, default=None,
                    help="Explicit JSON params file to load")
    return ap.parse_args()

def main():
    args = parse_args()
    path = Path(args.image).expanduser().resolve()
    ed = Editor(path)

    if args.auto_load or args.params:
        explicit = Path(args.params).expanduser().resolve() if args.params else None
        ed.try_autoload(explicit)

    cv2.namedWindow("Editor", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Editor", 1280, 720)

    while True:
        view = ed.render()
        hud = view.copy()
        txt = f"zoom:{ed.zoom:.2f}  ctr:({ed.cx},{ed.cy})  C:{ed.contrast:.2f}  S:{ed.sharpness:.2f}  G:{ed.gamma:.2f}  F:{ed.filters[ed.filter_idx]}"
        cv2.rectangle(hud, (0, 0), (hud.shape[1], 32), (0, 0, 0), -1)
        cv2.putText(hud, txt, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        cv2.imshow("Editor", hud)
        k = cv2.waitKey(0) & 0xFF

        if k in (ord('q'), 27):  # q or ESC
            break
        elif k == ord('z'):
            ed.zoom = clamp(ed.zoom * 1.15, 1.0, 10.0)
        elif k == ord('x'):
            ed.zoom = clamp(ed.zoom / 1.15, 1.0, 10.0)
        elif k in (81,):  # left
            ed.cx = clamp(ed.cx - int(50 / ed.zoom), 0, ed.w - 1)
        elif k in (83,):  # right
            ed.cx = clamp(ed.cx + int(50 / ed.zoom), 0, ed.w - 1)
        elif k in (82,):  # up
            ed.cy = clamp(ed.cy - int(50 / ed.zoom), 0, ed.h - 1)
        elif k in (84,):  # down
            ed.cy = clamp(ed.cy + int(50 / ed.zoom), 0, ed.h - 1)
        elif k == ord('['):
            ed.contrast = clamp(ed.contrast - 0.05, 0.2, 3.0)
        elif k == ord(']'):
            ed.contrast = clamp(ed.contrast + 0.05, 0.2, 3.0)
        elif k == ord('-'):
            ed.sharpness = clamp(ed.sharpness - 0.1, 0.0, 3.0)
        elif k == ord('='):
            ed.sharpness = clamp(ed.sharpness + 0.1, 0.0, 3.0)
        elif k == ord('g'):
            ed.gamma = clamp(ed.gamma - 0.05, 0.2, 3.0)
        elif k == ord('h'):
            ed.gamma = clamp(ed.gamma + 0.05, 0.2, 3.0)
        elif k == ord('f'):
            ed.filter_idx = (ed.filter_idx + 1) % len(ed.filters)
        elif k == ord('r'):
            ed.reset()
        elif k == ord('s'):
            ed.save()
        elif k == ord('p'):
            ed.save_params_only()

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
