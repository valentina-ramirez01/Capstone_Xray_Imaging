# xavier/xray_controller_core/controller.py
from __future__ import annotations
import time, threading
from enum import Enum
from typing import Optional, Callable, Dict, Any

from .config import Config
from gpio import gpio
from relay import RelayHat
from v_reader import MCP3008
from interlock import Interlocks
from leds import LedPanel

class State(Enum):
    IDLE="IDLE"; ARMED="ARMED"; EXPOSE="EXPOSE"; PREVIEW="PREVIEW"; FAULT="FAULT"

class Controller:
    """
    Orchestrates: interlocks, HV relay, MCP3008, LEDs, preview/expose, GUI push.

    Public API for frontend (via api.py):
      - set_gui_callback(fn)
      - arm() / disarm()
      - expose(shutter_s, fire_camera_gpio=True)
      - start_preview(max_seconds=None) / stop_preview()
      - reset_fault()
    """
    def __init__(self, cfg: Config):
        self.cfg = cfg

        # Outputs
        gpio.setup_output(cfg.pins.hb_out, initial_low=False)   # keep HIGH
        gpio.setup_output(cfg.pins.cam_trigger)                 # LOW
        gpio.setup_output(cfg.pins.cam_preview)                 # LOW

        # Subsystems
        self.relays = RelayHat(cfg.relays.i2c_addr, cfg.relays.i2c_bus)
        self.interlocks = Interlocks(cfg.pins.estop, cfg.pins.door, cfg.pins.hb_in, cfg.timing.debounce_s)
        self.leds = LedPanel(cfg.pins.led_red, cfg.pins.led_amber, cfg.pins.led_green, cfg.pins.led_blue)
        self.adc = MCP3008(cfg.adc.vref, cfg.adc.spi_bus, cfg.adc.spi_dev, cfg.adc.channel)

        self.state = State.IDLE
        self.gui_cb: Optional[Callable[[Dict[str,Any]], None]] = None

        # HV monitor
        self._hv_alarm = False
        self._hv_adc_v: Optional[float] = None
        self._hv_kv: Optional[float] = None

        # Preview watchdog (optional timeout)
        self._preview_deadline: Optional[float] = None

        # Background monitors
        self._th_hb = threading.Thread(target=self._loop_heartbeat, daemon=True); self._th_hb.start()
        self._th_hv = threading.Thread(target=self._loop_hv, daemon=True); self._th_hv.start()
        self._th_prev = threading.Thread(target=self._loop_preview, daemon=True); self._th_prev.start()

        self._apply_leds()
        self._log("Controller ready.")

    # ---- Frontend hooks ----
    def set_gui_callback(self, fn: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        self.gui_cb = fn

    # ---- Public API ----
    def arm(self) -> bool:
        if self.state == State.FAULT: self._log("Cannot arm: FAULT."); return False
        if not self.interlocks.all_ok(): self._log("Interlocks NOT OK."); return False
        self.state = State.ARMED; self._apply_leds(); self._notify("System ARMED"); return True

    def disarm(self) -> None:
        self._hv_off()
        gpio.write(self.cfg.pins.cam_trigger, False)
        gpio.write(self.cfg.pins.cam_preview, False)
        if self.state != State.FAULT:
            self.state = State.IDLE
            self._preview_deadline = None
            self._apply_leds(); self._notify("System DISARMED → IDLE")

    def expose(self, shutter_s: float, fire_camera_gpio: bool = True) -> bool:
        if shutter_s <= 0: raise ValueError("shutter_s must be > 0")
        if self.state == State.FAULT: self._log("Cannot expose: FAULT."); return False
        if self.state not in (State.ARMED, State.IDLE): self._log(f"Bad state {self.state}"); return False
        if not self.interlocks.all_ok(): self._log("Interlocks NOT OK."); return False
        if self.state == State.IDLE and not self.arm(): return False

        self.state = State.EXPOSE; self._apply_leds()
        self._notify(f"Exposure start: {shutter_s:.3f} s")

        if not self._hv_on(): self._fault("HV enable error"); return False
        self._sleep(self.cfg.timing.pre_roll_s)

        t0 = time.time()
        if fire_camera_gpio: gpio.write(self.cfg.pins.cam_trigger, True)
        while (time.time() - t0) < shutter_s:
            if not self.interlocks.all_ok():
                self._hv_off(); gpio.write(self.cfg.pins.cam_trigger, False)
                self._fault("Interlock failure during exposure"); return False
            time.sleep(0.005)

        if fire_camera_gpio: gpio.write(self.cfg.pins.cam_trigger, False)
        self._sleep(self.cfg.timing.post_hold_s)
        self._hv_off()
        self.disarm()
        self._notify("Exposure complete")
        return True

    def start_preview(self, max_seconds: Optional[float] = None) -> bool:
        if self.state == State.FAULT: self._log("Cannot preview: FAULT."); return False
        if self.state not in (State.ARMED, State.IDLE): self._log(f"Bad state {self.state}"); return False
        if not self.interlocks.all_ok(): self._log("Interlocks NOT OK."); return False
        if self.state == State.IDLE and not self.arm(): return False
        if not self._hv_on(): self._fault("HV enable error (preview)"); return False
        gpio.write(self.cfg.pins.cam_preview, True)
        self.state = State.PREVIEW; self._apply_leds()
        self._preview_deadline = time.time() + max_seconds if max_seconds else None
        self._notify("Preview started")
        return True

    def stop_preview(self) -> None:
        if self.state != State.PREVIEW: return
        gpio.write(self.cfg.pins.cam_preview, False)
        self._hv_off()
        self.disarm()
        self._preview_deadline = None
        self._notify("Preview stopped")

    def reset_fault(self) -> bool:
        if self.state != State.FAULT: self._log("Not in FAULT."); return False
        if not self.interlocks.all_ok(): self._log("Interlocks still NOT OK."); return False
        self.state = State.IDLE; self._apply_leds(); self._notify("FAULT cleared → IDLE"); return True

    # ---- Internals ----
    def _hv_on(self) -> bool:
        if not self.interlocks.all_ok(): return False
        self.relays.write_channel(self.cfg.relays.hv_channel, True)
        return True

    def _hv_off(self):
        self.relays.write_channel(self.cfg.relays.hv_channel, False)
        self._sleep(0.2)

    def _loop_heartbeat(self):
        while True:
            gpio.write(self.cfg.pins.hb_out, True)  # keep asserted
            if self.state != State.FAULT and not self.interlocks.heartbeat_ok():
                self._fault("Heartbeat lost")
            self._apply_leds()
            self._sleep(self.cfg.timing.heartbeat_period_s)

    def _loop_hv(self):
        prev_alarm = None
        while True:
            v = self.adc.read_volts()
            self._hv_adc_v = v
            hv_volts = v * self.cfg.adc.hv_volts_per_adc_volt
            self._hv_kv = hv_volts / 1000.0
            alarm = v >= self.cfg.adc.hv_alarm_threshold_adc_v
            self._hv_alarm = alarm
            self._apply_leds()

            if alarm and self.cfg.adc.cut_hv_on_alarm and self.state in (State.EXPOSE, State.PREVIEW):
                self._hv_off(); self._fault("HV alarm while X-ray ON")

            if prev_alarm is None or alarm != prev_alarm:
                self._notify("DANGER: HV ≥ threshold" if alarm else "HV below threshold")
                prev_alarm = alarm

            self._sleep(self.cfg.adc.sample_period_s)

    def _loop_preview(self):
        while True:
            if self.state == State.PREVIEW and self._preview_deadline:
                if time.time() >= self._preview_deadline:
                    self.stop_preview()
            time.sleep(0.05)

    def _apply_leds(self):
        self.leds.apply(
            alarm=self._hv_alarm,
            interlocks_ok=self.interlocks.all_ok(),
            state=self.state.value
        )

    def _notify(self, msg: str):
        if self.gui_cb:
            self.gui_cb({
                "state": self.state.value,
                "interlocks_ok": self.interlocks.all_ok(),
                "hv_adc_volts": self._hv_adc_v,
                "hv_kv": self._hv_kv,
                "hv_alarm": self._hv_alarm,
                "message": msg
            })

    def _fault(self, msg: str):
        self.relays.write_channel(self.cfg.relays.hv_channel, False)
        gpio.write(self.cfg.pins.cam_trigger, False)
        gpio.write(self.cfg.pins.cam_preview, False)
        self.state = State.FAULT
        self._apply_leds()
        self._notify(f"FAULT: {msg}")

    def _sleep(self, t: float): gpio.sleep_s(t)
    def _log(self, s: str): print(time.strftime("[%H:%M:%S]"), s)
