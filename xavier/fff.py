# adc_reader.py
import smbus
import time

ADS1115_ADDR = 0x48
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

MUX_A0         = 0x4000
PGA_4_096V     = 0x0200
MODE_CONT      = 0x0000
DR_860SPS      = 0x00E0
COMP_DISABLE   = 0x0003
OS_START       = 0x8000

CONFIG = (
    OS_START |
    MUX_A0 |
    PGA_4_096V |
    MODE_CONT |
    DR_860SPS |
    COMP_DISABLE
)

bus = smbus.SMBus(1)
bus.write_word_data(ADS1115_ADDR, REG_CONFIG, 
    ((CONFIG & 0xFF) << 8) | (CONFIG >> 8)
)

ADC_FULL_SCALE = 4.096
HV_FULL_SCALE  = 50000.0

LOW_LIMIT  = 1.485
HIGH_LIMIT = 1.815

def read_voltage():
    """Returns voltage on A0 in volts."""
    raw_swap = bus.read_word_data(ADS1115_ADDR, REG_CONVERSION)
    raw = ((raw_swap & 0xFF) << 8) | (raw_swap >> 8)

    if raw > 0x7FFF:
        raw -= 0x10000

    voltage = raw * (ADC_FULL_SCALE / 32767.0)
    return voltage

def hv_status():
    """
    Returns tuple: (status_string, voltage)
    status_string ∈ {"LOW", "OK", "HIGH"}
    """
    v = read_voltage()

    if v < LOW_LIMIT:
        return ("LOW", v)
    if v > HIGH_LIMIT:
        return ("HIGH", v)
    return ("OK", v)
