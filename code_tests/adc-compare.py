import time
import math
import smbus
import RPi.GPIO as GPIO

# ===========================================
# IMPORT THE GUI ADC READER
# ===========================================

from xavier.adc_reader import read_hv_voltage, _read_v0, compute_voltage

print("✅ Imported adc_reader:")
print("  read_hv_voltage =", read_hv_voltage)
print("  _read_v0 =", _read_v0)
print("  compute_voltage =", compute_voltage)
print("--------------------------------------------------")


# ===========================================
# ADS1115 RAW TEST (your standalone code)
# ===========================================
ADS1115_ADDR = 0x48
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

MUX_AIN0       = 0x4000
PGA_6_144V     = 0x0000
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
LSB = ADC_FS / 32767.0
NOISE_THRESHOLD = 0.01

K = 2 * math.sqrt(2) * 400 * 12

bus = smbus.SMBus(1)
bus.write_word_data(
    ADS1115_ADDR,
    REG_CONFIG,
    ((CONFIG_WORD & 0xFF) << 8) | (CONFIG_WORD >> 8)
)

# ===========================================
# MAIN LOOP
# ===========================================
print("\n⚡ Starting ADC comparison test...\n")

try:
    while True:

        # ---------------------
        # RAW ADS1115 READ
        # ---------------------
        raw_swapped = bus.read_word_data(ADS1115_ADDR, REG_CONVERSION)
        raw = ((raw_swapped & 0xFF) << 8) | (raw_swapped >> 8)

        if raw > 0x7FFF:
            raw -= 0x10000

        V0_raw = raw * LSB
        if abs(V0_raw) < NOISE_THRESHOLD:
            V0_raw = 0.0

        HV_raw = (2*V0_raw + 0.7) * K

        # ---------------------
        # GUI ADC READER VALUES
        # ---------------------
        V0_mod = _read_v0()
        HV_mod = read_hv_voltage()

        # ---------------------
        # PRINT BOTH
        # ---------------------
        print(
            f"[RAW ]  V0={V0_raw:.5f} V | HV={HV_raw:10.2f} V   ||   "
            f"[adc_reader] V0={V0_mod:.5f} V | HV={HV_mod:10.2f} V"
        )

        time.sleep(0.2)

except KeyboardInterrupt:
    print("\nTest stopped.")
