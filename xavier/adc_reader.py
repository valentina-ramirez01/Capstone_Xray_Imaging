import smbus
import time

# ======================================================
# ADS1115 REGISTER MAP
# ======================================================
ADS1115_ADDR = 0x48
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

# ======================================================
# ADS1115 CONFIG — YOUR EXACT SETTINGS
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
# ADC LSB VALUE (your configuration)
# ======================================================
ADC_FS = 6.144          # ±6.144V full-scale
LSB = ADC_FS / 32767.0  # ADS1115 output step size

# ======================================================
# HV DIVIDER & SAFE WINDOW (customize if needed)
# ======================================================
DIVIDER_RATIO = 50000 / 5.0   # 50kV → 5V at ADC (10,000 V per volt)

HV_MIN_SAFE = 35_000   # 35 kV minimum
HV_MAX_SAFE = 55_000   # 55 kV maximum


# ======================================================
# INTERNAL: READ RAW VOLTAGE FROM ADC (A0)
# ======================================================
_bus = smbus.SMBus(1)

def _read_adc_voltage():
    """
    Reads ADS1115 A0 using your config word.
    Returns:
        float (raw voltage at ADC pin)
    """
    try:
        # Write configuration
        _bus.write_word_data(
            ADS1115_ADDR,
            REG_CONFIG,
            ((CONFIG_WORD >> 8) & 0xFF) | ((CONFIG_WORD & 0xFF) << 8)
        )

        time.sleep(0.003)  # settle time for continuous mode

        # Read conversion register (swap byte order!)
        raw = _bus.read_word_data(ADS1115_ADDR, REG_CONVERSION)
        raw = ((raw & 0xFF) << 8) | (raw >> 8)

        # Convert to voltage
        voltage = raw * LSB

        return voltage

    except Exception as e:
        print(f"[ADC ERROR] {e}")
        return -1.0


# ======================================================
# PUBLIC: READ HV IN VOLTS
# ======================================================
def read_hv_voltage():
    """
    Reads HV using your resistor divider.
    Returns:
        HV in volts (NOT kV)
    """
    raw_v = _read_adc_voltage()

    if raw_v < 0:
        return -1

    hv = raw_v * DIVIDER_RATIO
    return hv


# ======================================================
# PUBLIC: HV SAFETY LOGIC
# ======================================================
def hv_status_ok(hv):
    """
    Validates HV range.
    Returns:
        (bool, message)
    """
    if hv < 0:
        return (False, "ADC READ ERROR")

    if hv < HV_MIN_SAFE:
        return (False, f"HV TOO LOW ({hv/1000:.2f} kV)")

    if hv > HV_MAX_SAFE:
        return (False, f"HV TOO HIGH ({hv/1000:.2f} kV)")

    return (True, "OK")
