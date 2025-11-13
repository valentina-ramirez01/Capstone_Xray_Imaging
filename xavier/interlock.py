# xavier/xray_controller_core/safety/interlocks.py
import xavier.gpio_estop as gpio_estop

class Interlocks:
    """
    Normally-Open → HIGH = SAFE
      - E-Stop: HIGH = not pressed (SAFE), LOW = pressed (NOT SAFE)
      - Door:   HIGH = OK per your policy, LOW = activated (NOT SAFE)
      - Heartbeat: hb_out is held HIGH elsewhere; hb_in must read HIGH
    """
    def __init__(self, estop: int, door: int, hb_in: int, debounce_s: float):
        self.estop = estop
        self.door = door
        self.hb_in = hb_in
        self.debounce = debounce_s
        for p in (estop, door, hb_in):
            gpio_estop.setup_input(p)

    def estop_ok(self) -> bool:     return bool(gpio_estop.read(self.estop, self.debounce))
    def door_ok(self) -> bool:      return bool(gpio_estop.read(self.door,  self.debounce))
    def heartbeat_ok(self) -> bool: return bool(gpio_estop.read(self.hb_in, self.debounce))
    def all_ok(self) -> bool:       return self.estop_ok() and self.door_ok() and self.heartbeat_ok()
