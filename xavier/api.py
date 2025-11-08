# xavier/api.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from config import load_config
from controller import Controller

# Singleton-ish controller so the GUI can import these helpers safely.
_controller: Optional[Controller] = None

def init_controller(settings_path: str | Path,
                    gui_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Controller:
    """
    Initialize (or reuse) the backend. Call once at app startup.
    """
    global _controller
    if _controller is not None:
        if gui_callback:
            _controller.set_gui_callback(gui_callback)
        return _controller

    cfg = load_config(settings_path)
    _controller = Controller(cfg)
    if gui_callback:
        _controller.set_gui_callback(gui_callback)
    return _controller

def set_gui_callback(cb: Optional[Callable[[Dict[str, Any]], None]]) -> None:
    if _controller:
        _controller.set_gui_callback(cb)

def start_preview(max_seconds: float | None = None) -> bool:
    if not _controller:
        raise RuntimeError("Controller not initialized. Call init_controller().")
    return _controller.start_preview(max_seconds=max_seconds)

def stop_preview() -> None:
    if _controller:
        _controller.stop_preview()

def expose(shutter_s: float, fire_camera_gpio: bool = True) -> bool:
    if not _controller:
        raise RuntimeError("Controller not initialized. Call init_controller().")
    return _controller.expose(shutter_s=shutter_s, fire_camera_gpio=fire_camera_gpio)

def disarm() -> None:
    if _controller:
        _controller.disarm()

def reset_fault() -> bool:
    if not _controller:
        return False
    return _controller.reset_fault()
