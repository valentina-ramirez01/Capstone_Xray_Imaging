import numpy as np
from camera import start_camera


def handle_capture(filepath: str, frame: np.ndarray) -> None:
    print(f"Captured to {filepath} | frame shape: {frame.shape}")


def main():
    # Use cam_index=1 to prefer external USB camera (adjust as needed).
    start_camera(cam_index=1, on_capture=handle_capture, save_dir="captures")


if __name__ == "__main__":
    main()