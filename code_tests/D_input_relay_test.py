#dry contact relay test as input connecting ground to a GPIO pin as a PULL-UP (worked)

from gpiozero import Button
import smbus
import time

# Relay hat configuration
I2C_BUS = 1
I2C_ADDR = 0x10
RELAY_CH = 1

# Digital input pin (IO12 on breakout)
GPIO_IN = 12

bus = smbus.SMBus(I2C_BUS)

def relay_on(ch):
    bus.write_byte_data(I2C_ADDR, ch, 0xFF)  
    print(f"Relay {ch} ON")

def relay_off(ch):
    bus.write_byte_data(I2C_ADDR, ch, 0x00)
    print(f"Relay {ch} OFF")

# Internal pull-up = input goes LOW when contact closes
contact = Button(GPIO_IN, pull_up=True, bounce_time=0.02)

contact.when_pressed = lambda: relay_on(RELAY_CH)
contact.when_released = lambda: relay_off(RELAY_CH)

print("Watching IO12. Close the contact to activate Relay 1.")
relay_off(RELAY_CH)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    relay_off(RELAY_CH)
    print("Exiting.")
