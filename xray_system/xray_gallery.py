
# gallery.py — keyboard-driven viewer & organizer with Burst Export

import sys
import os
from pathlib import Path
import shutil
import cv2
import numpy as np
import subprocess

SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

def list_images(root: Path) -> list[Path]:
    if root.is_file() and root.suffix.lower() in SUPPORTED_EXT:
        return [root]
    files = []
    for p in root.rglob("*"):
        if p.suffix.lower() in SUPPORTED_EXT:
            files.append(p)
    files.sort()
    return files

def imread_gray(path: Path):
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img

def put_hud(frame, text):
    hud = frame.copy()
    cv2.rectangle(hud, (0, 0), (hud.shape[1], 32), (0, 0, 0), -1)
    cv2.putText(hud, text, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return hud

def edited_path_for(original: Path) -> Path:
    """
    Map .../raw/name.png -> .../edits/name.png (or sibling edits/ when not in raw/)
    """
    p = original.resolve()
    parts = list(p.parts)
    try:
        idx = parts.index("raw")
        parts[idx] = "edits"
        return Path(*parts)
    except ValueError:
        # fallback: ../edits/name
        return p.parent.parent / "edits" / p.name if p.parent.name.lower() == "raw" else p.parent / "edits" / p.name

def export_one(src: Path, samples_root: Path, sample_name: str | None = None):
    if not sample_name:
        sample_name = input("Sample name (folder under samples/): ").strip()
        if not sample_name:
            print("Canceled.")
            return
    is_edit = "edits" in src.parts
    dest_dir = samples_root / sample_name / ("edits" if is_edit else "raw")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    sidecar = src.with_suffix(src.suffix + ".json")
    if sidecar.exists():
        shutil.copy2(sidecar, dest.with_suffix(dest.suffix + ".json"))
    print(f"Exported → {dest}")

def export_burst(imgs: list[Path], center_idx: int, N: int, samples_root: Path):
    """
    Export current ±N images to a chosen sample folder.
    Keeps raw/edits separation for each source path.
    """
    if N < 0:
        print("N must be >= 0")
        return
    sample = input("Sample name (folder under samples/): ").strip()
    if not sample:
        print("Canceled.")
        return
    start = max(0, center_idx - N)
    end = min(len(imgs) - 1, center_idx + N)
    count = 0
    for i in range(start, end + 1):
        src = imgs[i]
        # If the gallery is toggled to show edited versions, users typically select the edited file path.
        # We export exactly the shown path, but here we export the original path; user can re-open with 't' toggle if needed.
        export_one(src, samples_root, sample_name=sample)
        count += 1
    print(f"Burst exported {count} files to samples/{sample}/raw|edits.")

def open_in_editor(img_path: Path):
    try:
        subprocess.run([sys.executable, "image_tools.py", str(img_path)], check=False)
    except Exception as e:
        print("Failed to open editor:", e)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 gallery.py <folder_or_image> [samples_root]")
        print("Keys: ←/→ prev/next | ↑/↓ ±10 | Enter: edit | e: export one | b: burst export ±N | r: reset edit | t: toggle raw/edited | i: info | q: quit")
        sys.exit(1)

    root = Path(sys.argv[1]).expanduser().resolve()
    samples_root = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) >= 3 else Path("samples").resolve()
    imgs = list_images(root)
    if not imgs:
        print("No images found.")
        sys.exit(0)

    idx = 0
    show_edited_if_available = False

    cv2.namedWindow("Gallery", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Gallery", 1280, 720)

    while True:
        src = imgs[idx]
        show_path = src
        edp = edited_path_for(src)
        if show_edited_if_available and edp.exists():
            show_path = edp

        img = imread_gray(show_path)
        if img is None:
            disp = np.zeros((400, 800), np.uint8)
            disp = put_hud(disp, f"Failed to load: {show_path.name}")
        else:
            h, w = img.shape[:2]
            scale = min(1280 / w, 720 / h)
            img_resized = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1.0 else img
            status = f"[{idx+1}/{len(imgs)}] {'EDIT' if show_path==edp and edp.exists() else 'RAW'}  {show_path.name}"
            disp = put_hud(cv2.cvtColor(img_resized, cv2.COLOR_GRAY2BGR), status)

        cv2.imshow("Gallery", disp)
        k = cv2.waitKey(0) & 0xFF

        if k in (ord('q'), 27):  # q or ESC
            break
        elif k in (81, ord('a')):  # left
            idx = (idx - 1) % len(imgs)
        elif k in (83, ord('d')):  # right
            idx = (idx + 1) % len(imgs)
        elif k in (82,):  # up
            idx = (idx - 10) % len(imgs)
        elif k in (84,):  # down
            idx = (idx + 10) % len(imgs)
        elif k in (10, 13):  # Enter: open editor
            open_in_editor(show_path)
        elif k == ord('e'):  # export one
            export_one(show_path, samples_root)
        elif k == ord('b'):  # burst export
            try:
                N = int(input("Export range N (current ±N): ").strip() or "0")
            except ValueError:
                print("Invalid N.")
                continue
            export_burst(imgs, idx, N, samples_root)
        elif k == ord('r'):  # reset editing (delete edited counterpart)
            ed = edited_path_for(src)
            if ed.exists():
                try:
                    ed.unlink()
                    sc = ed.with_suffix(ed.suffix + ".json")
                    if sc.exists():
                        sc.unlink()
                    print(f"Removed edited version: {ed.name}")
                except Exception as e:
                    print("Failed to remove edited file:", e)
            else:
                print("No edited version found to reset.")
        elif k == ord('i'):
            try:
                size = show_path.stat().st_size
                print(f"File: {show_path}  size={size/1024:.1f} KiB")
            except Exception:
                print(f"File: {show_path}")
        elif k == ord('t'):  # toggle raw/edited view
            show_edited_if_available = not show_edited_if_available

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
