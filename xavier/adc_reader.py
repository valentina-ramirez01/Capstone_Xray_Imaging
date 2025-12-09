import smbus
import time
import math

# ======================================================
# ADS1115 REGISTER MAP
# ======================================================
ADS1115_ADDR = 0x48
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

# ======================================================
# ADS1115 CONFIG — SAME AS YOUR WORKING TEST SCRIPT
# ======================================================
MUX_AIN0       = 0x4000   # Read A0
PGA_6_144V     = 0x0000   # ±6.144V range
MODE_CONT      = 0x0000   # Continuous mode
DR_860SPS      = 0x00E0   # Fastest sample rate
COMP_DISABLE   = 0x0003   # Disable comparator
START_OS       = 0x8000   # Start conversion

CONFIG_WORD = (
    START_OS |
    MUX_AIN0 |
    PGA_6_144V |
    MODE_CONT |
    DR_860SPS |
    COMP_DISABLE
)

# ======================================================
# ADC LSB VALUE
# ======================================================
ADC_FS = 6.144
LSB = ADC_FS / 32767.0

NOISE_THRESHOLD = 0.01  # 10mV noise filter

HV_MIN_SAFE = 5_000
HV_MAX_SAFE = 55_000

# ======================================================
# I2C BUS
# ======================================================
_bus = smbus.SMBus(1)


# ======================================================
# INTERNAL ADC READ — FIXED BYTE ORDER
# ======================================================
def _read_adc_voltage():
    try:
        # Correct byte swap (matching your working script)
        cfg_swapped = ((CONFIG_WORD & 0xFF) << 8) | (CONFIG_WORD >> 8)

        _bus.write_word_data(ADS1115_ADDR, REG_CONFIG, cfg_swapped)
        time.sleep(0.005)

        # Read conversion register (swap bytes)
        raw_swapped = _bus.read_word_data(ADS1115_ADDR, REG_CONVERSION)
        raw = ((raw_swapped & 0xFF) << 8) | (raw_swapped >> 8)

        # Signed conversion
        if raw > 0x7FFF:
            raw -= 0x10000

        v0 = raw * LSB

        if abs(v0) < NOISE_THRESHOLD:
            v0 = 0.0

        return v0

    except Exception as e:
        print(f"[ADC ERROR] {e}")
        return -1.0


# ======================================================
# CORRECT HV FORMULA
# ======================================================
K = 2 * math.sqrt(2) * 400 * 12  # ≈ 13576.45


def compute_voltage(V0: float) -> float:
    return (2 * V0 + 0.7) * K


# ======================================================
# PUBLIC HV READER
# ======================================================
def read_hv_voltage():
    v0 = _read_adc_voltage()
    if v0 < 0:
        return -1
    return compute_voltage(v0)


# ======================================================
# HV SAFETY LOGIC
# ======================================================
def hv_status_ok(hv):
    if hv < 0:
        return (False, "ADC READ ERROR")

    if hv < HV_MIN_SAFE:
        return (False, f"HV TOO LOW ({hv/1000:.2f} kV)")

    if hv > HV_MAX_SAFE:
        return (False, f"HV TOO HIGH ({hv/1000:.2f} kV)")

    return (True, "OK")
