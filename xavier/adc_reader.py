
import smbus
import math
import time

# ======================================================
# ADS1115 REGISTER MAP
# ======================================================
ADS1115_ADDR = 0x48
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

# ======================================================
# ADS1115 CONFIG — USING ±6.144V RANGE FOR 3.3V INPUTS
# (from your adc voltage test.py)
# ======================================================
MUX_AIN0       = 0x4000   # Read A0
PGA_6_144V     = 0x0000   # Correct for 3.3V logic
MODE_CONT      = 0x0000
DR_860SPS      = 0x00E0
COMP_DISABLE   = 0x0003
START_OS       = 0x8000

CONFIG_WORD = (
    START_OS |
    MUX_AIN0 |
    PGA_6_144V |
    MODE_CONT |
    DR_860SPS |
    COMP_DISABLE
)

# Voltage per bit (LSB)
ADC_FS = 6.144
LSB = ADC_FS / 32767.0

# Remove ADC noise below 10mV
NOISE_THRESHOLD = 0.01

# ======================================================
# HV FORMULA CONSTANT — from your V0→HV formula
# ======================================================
K = 2 * math.sqrt(2) * 400 * 12     # ≈ 13576.45


def compute_voltage(V0: float) -> float:
    """Fast HV formula."""
    return (2 * V0 + 0.7) * K


# ======================================================
# INIT I2C BUS
# ======================================================
bus = smbus.SMBus(1)
bus.write_word_data(
    ADS1115_ADDR,
    REG_CONFIG,
    ((CONFIG_WORD & 0xFF) << 8) | (CONFIG_WORD >> 8)
)


# ======================================================
# Core ADC Function
# ======================================================
def read_v0() -> float:
    """Reads ADS1115 A0 input and returns scaled voltage."""
    raw_swap = bus.read_word_data(ADS1115_ADDR, REG_CONVERSION)

    # Swap byte order
    raw = ((raw_swap & 0xFF) << 8) | (raw_swap >> 8)

    # Convert to signed
    if raw > 0x7FFF:
        raw -= 0x10000

    V0 = raw * LSB

    # Remove noise
    if abs(V0) < NOISE_THRESHOLD:
        V0 = 0.0

    return V0


# ======================================================
# Main public API for your interface: hv_status()
# ======================================================
LOW_LIMIT  = 1.485
HIGH_LIMIT = 1.815

def hv_status():
    """
    Returns:
        ("LOW", hv_voltage)
        ("OK", hv_voltage)
        ("HIGH", hv_voltage)
    where hv_voltage is the computed HV_OUT using your formula.
    """
    V0 = read_v0()
    HV = compute_voltage(V0)

    if V0 < LOW_LIMIT:
        return ("LOW", HV)

    if V0 > HIGH_LIMIT:
        return ("HIGH", HV)

    return ("OK", HV)
