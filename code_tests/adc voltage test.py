import time
import smbus

# ------------------------------------------------------
# ADS1115 Register Map
# ------------------------------------------------------
ADS1115_ADDR = 0x48       # Default address when ADDR pin is GND or floating
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

# ------------------------------------------------------
# ADS1115 Config: A0, ±4.096V, Continuous mode, 860SPS
# ------------------------------------------------------
MUX_AIN0       = 0x4000
PGA_4_096V     = 0x0200
MODE_CONT      = 0x0000
DR_860SPS      = 0x00E0
COMP_DISABLE   = 0x0003
START_OS       = 0x8000

CONFIG_WORD = (
    START_OS |
    MUX_AIN0 |
    PGA_4_096V |
    MODE_CONT |
    DR_860SPS |
    COMP_DISABLE
)
    DR_860SPS |
    COMP_DISABLE
)

# ------------------------------------------------------
#   HV Scaling: 3.3V → 50,000V
# ------------------------------------------------------
ADC_FULL_SCALE = 4.096
HV_FULL_SCALE  = 50000.0

# ------------------------------------------------------
#   HV Scaling: 3.3V → 50,000V
# ------------------------------------------------------
ADC_FULL_SCALE = 4.096
HV_FULL_SCALE  = 50000.0

# ------------------------------------------------------
# Init I2C
# ------------------------------------------------------
bus = smbus.SMBus(1)

# Write config (swap bytes because ADS1115 expects low-high)
bus.write_word_data(ADS1115_ADDR, REG_CONFIG,
    ((CONFIG_WORD & 0xFF) << 8) | (CONFIG_WORD >> 8)
)

print("Reading ADS1115 A0 pin...")
print("Voltage threshold: 3.3V ≈ 50 kV\n")

# ------------------------------------------------------
# Main Loop
# ------------------------------------------------------
while True:
    # Read conversion register (swap byte order)
    raw_swapped = bus.read_word_data(ADS1115_ADDR, REG_CONVERSION)
    raw = ((raw_swapped & 0xFF) << 8) | (raw_swapped >> 8)

    # Convert signed 16-bit
    if raw > 0x7FFF:
        raw -= 0x10000

    # Convert to voltage
    voltage = raw * (ADC_FULL_SCALE / 32767.0)

    # Calculate HV equivalent
    hv = (voltage / 3.3) * HV_FULL_SCALE

    print(f"Raw={raw:6d}, Voltage={voltage:.4f} V, HV={hv:8.1f} V", end=" ")

    # Detect approx 3.3V (±10% tolerance)
    if 2.97 <= voltage <= 3.63:
        print(" --> 50 kV DETECTED ⚡")
    else:
        print("")

    time.sleep(0.25)
