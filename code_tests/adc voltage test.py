import time
import math
import smbus

# ======================================================
# ADS1115 REGISTER MAP
# ======================================================
ADS1115_ADDR = 0x48
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

# ======================================================
# ADS1115 CONFIG (YOUR WORKING SETTINGS)
# ======================================================
MUX_AIN0       = 0x4000   # Read A0
PGA_6_144V     = 0x0000   # Input range ±6.144V (correct for 3.3V logic)
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

ADC_FS = 6.144
LSB = ADC_FS / 32767.0     # LSB size

NOISE_THRESHOLD = 0.01      # Filter 0–10 mV noise

# ======================================================
# HV CONSTANT (from your formula)
# ======================================================
K = 2 * math.sqrt(2) * 400 * 12   # ≈ 13,576.45


# ======================================================
# INIT I2C
# ======================================================
bus = smbus.SMBus(1)
bus.write_word_data(
    ADS1115_ADDR,
    REG_CONFIG,
    ((CONFIG_WORD & 0xFF) << 8) | (CONFIG_WORD >> 8)
)



# ======================================================
# MAIN LOOP
# ======================================================
while True:
    # Read ADC (swap byte order)
    raw_swapped = bus.read_word_data(ADS1115_ADDR, REG_CONVERSION)
    raw = ((raw_swapped & 0xFF) << 8) | (raw_swapped >> 8)

    # Convert to signed integer
    if raw > 0x7FFF:
        raw -= 0x10000

    # Convert to volts
    V0 = raw * LSB

    # Noise filter
    if abs(V0) < NOISE_THRESHOLD:
        V0 = 0.0

    # Apply HV multiplier formula
    HV = (2 * V0 + 0.7) * K

    print(f"V0 = {V0:6.4f} V | HV Multiplier Output = {HV:9.2f} V")

    time.sleep(0.2)
