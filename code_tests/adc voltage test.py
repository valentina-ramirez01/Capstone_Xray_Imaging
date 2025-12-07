import time
import math
import smbus
import RPi.GPIO as GPIO

# ======================================================
# ADS1115 REGISTER MAP
# ======================================================
ADS1115_ADDR = 0x48
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

# ======================================================
# ADS1115 CONFIG — USE ±6.144V RANGE FOR 3.3V INPUTS
# ======================================================
MUX_AIN0       = 0x4000   # Read A0
PGA_6_144V     = 0x0000   # << Correct for 3.3V logic
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
LSB = ADC_FS / 32767.0      # ADS1115 LSB size

# ======================================================
# NOISE THRESHOLD — remove ADC noise below 10mV
# ======================================================
NOISE_THRESHOLD = 0.01

# ======================================================
# HV FORMULA CONSTANT
# ======================================================
K = 2 * math.sqrt(2) * 400 * 12     # ~ 13576.45


# ======================================================
# DEBUG FORMULA (prints all steps once)
# ======================================================
def compute_voltage_debug(V0):
    a = 2 * V0
    b = a + 0.7
    c = b * 2
    d = math.sqrt(2)
    e = c * d
    f = e * 400
    g = f * 12
    print("\n================ FORMULA DEBUG ================")
    print(f"  V0         = {V0}")
    print(f"  2*V0       = {a}")
    print(f"  2*V0+0.7   = {b}")
    print(f"  (*)2       = {c}")
    print(f"  sqrt(2)    = {d}")
    print(f"  *sqrt(2)   = {e}")
    print(f"  *400       = {f}")
    print(f"  *12        = {g}")
    print("================================================\n")
    return g

# ======================================================
# FAST FORMULA AFTER DEBUG
# ======================================================
def compute_voltage(V0):
    return (2*V0 + 0.7) * K


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
# SETUP RELAY
# ======================================================
RELAY = 23
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY, GPIO.OUT)
GPIO.output(RELAY, GPIO.HIGH)   # idle OFF

print("⚡ Turning RELAY ON and reading ADC in real-time...\n")
GPIO.output(RELAY, GPIO.LOW)    # turn relay ON


# ======================================================
# MAIN LOOP
# ======================================================
first = True

try:
    while True:

        # Read ADC (byte swap)
        raw_swapped = bus.read_word_data(ADS1115_ADDR, REG_CONVERSION)
        raw = ((raw_swapped & 0xFF) << 8) | (raw_swapped >> 8)

        # Convert to signed
        if raw > 0x7FFF:
            raw -= 0x10000

        # Convert ADC raw → V0
        V0 = raw * LSB

        # Remove tiny noise
        if abs(V0) < NOISE_THRESHOLD:
            V0 = 0.0

        # Debug first measurement only
        if first:
            HV = compute_voltage_debug(V0)
            first = False
        else:
            HV = compute_voltage(V0)

        print(f"V0={V0:.4f} V   |   HV_out={HV:.2f} V")
        time.sleep(0.1)

except KeyboardInterrupt:
    print(
