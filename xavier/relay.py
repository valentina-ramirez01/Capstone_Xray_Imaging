# xavier/xray_controller_core/hw/relay.py
"""
Single-relay controller for Raspberry Pi Relay HAT (I²C, address 0x10).
This version is hard-coded for Relay 1 only (HV enable).
"""

import smbus

I2C_BUS = 1
I2C_ADDR = 0x10
RELAY_CH = 1  # hard-coded: only relay 1 is used

# Initialize I²C bus once
bus = smbus.SMBus(I2C_BUS)

def relay_on() -> None:
    """Energize relay 1 (HV ON)."""
    bus.write_byte_data(I2C_ADDR, RELAY_CH, 0xFF)

def relay_off() -> None:
    """De-energize relay 1 (HV OFF)."""
    bus.write_byte_data(I2C_ADDR, RELAY_CH, 0x00)
