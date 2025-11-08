# xavier/xray_controller_core/hw/adc_mcp3008.py
"""
MCP3008 10-bit Analog-to-Digital Converter (ADC) driver.

Reads one channel over SPI and returns a voltage based on Vref.
Works only on Raspberry Pi with SPI enabled and 'python3-spidev' installed.
"""

class MCP3008:
    def __init__(self, vref: float, bus: int, dev: int, channel: int):
        """
        :param vref: ADC reference voltage (e.g., 3.3 V)
        :param bus: SPI bus index (usually 0)
        :param dev: SPI device index (0 = CE0, 1 = CE1)
        :param channel: ADC input channel (0–7)
        """
        if not (0 <= channel <= 7):
            raise ValueError("MCP3008 channel must be 0–7")

        self.vref = vref
        self.channel = channel

        # Initialize SPI bus
        self.spi = spidev.SpiDev()
        self.spi.open(bus, dev)
        self.spi.max_speed_hz = 1_000_000  # 1 MHz typical
        self.spi.mode = 0  # SPI mode 0

    def read_volts(self) -> float:
        """
        Read the current voltage from the configured ADC channel.
        :return: Measured voltage (float)
        """
        cmd = [1, (1 << 7) | (self.channel << 4), 0]
        resp = self.spi.xfer2(cmd)
        raw = ((resp[1] & 0x03) << 8) | resp[2]  # 10-bit result (0–1023)
        volts = (raw / 1023.0) * self.vref
        return max(0.0, min(self.vref, volts))
