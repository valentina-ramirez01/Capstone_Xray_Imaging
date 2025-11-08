# xavier/xray_controller_core/config.py
from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass
class Pins:
    estop: int
    door: int
    hb_out: int
    hb_in: int
    cam_trigger: int
    cam_preview: int
    led_red: int
    led_amber: int
    led_green: int
    led_blue: int

@dataclass
class Relays:
    i2c_addr: int     # relay HAT addr (0x10 = 16)
    i2c_bus: int
    hv_channel: int   # ONLY HV used

@dataclass
class Adc:
    vref: float
    spi_bus: int
    spi_dev: int
    channel: int
    sample_period_s: float
    hv_volts_per_adc_volt: float
    hv_alarm_threshold_adc_v: float
    cut_hv_on_alarm: bool

@dataclass
class Timing:
    debounce_s: float
    heartbeat_period_s: float
    pre_roll_s: float
    post_hold_s: float

@dataclass
class Config:
    pins: Pins
    relays: Relays
    adc: Adc
    timing: Timing

def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text())
    return Config(
        pins=Pins(**data["pins"]),
        relays=Relays(**data["relays"]),
        adc=Adc(**data["adc"]),
        timing=Timing(**data["timing"]),
    )
