# relay.py
# Single-relay controller (Relay 1 only) for I²C Relay HAT at 0x10

import smbus

I2C_BUS = 1
I2C_ADDR = 0x10
RELAY_CH = 1  # hard-coded: use Relay 1 only

_bus = smbus.SMBus(I2C_BUS)

def hv_on() -> None:
    """Energize Relay 1 (HV enable)."""
    _bus.write_byte_data(I2C_ADDR, RELAY_CH, 0xFF)

def hv_off() -> None:
    
    """De-energize Relay 1 (HV disable)."""
    _bus.write_byte_data(I2C_ADDR, RELAY_CH, 0x00)
