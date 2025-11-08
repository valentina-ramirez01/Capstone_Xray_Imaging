# xavier/xray_controller_core/safety/leds.py
import RPi.GPIO as GPIO
#from gpiozero import Button

class LedPanel:
    """
    LED policy:
      - RED   : HV alarm OR FAULT state
      - AMBER : Interlocks NOT OK (but not in FAULT)
      - GREEN : ARMED and interlocks OK
      - BLUE  : X-ray ON (EXPOSE or PREVIEW)
    """
    def __init__(self, red: int, amber: int, green: int, blue: int):
        self.red, self.amber, self.green, self.blue = red, amber, green, blue
        for p in (red, amber, green, blue):
            gpio.setup_output(p)

    def apply(self, *, alarm: bool, interlocks_ok: bool, state: str):
        red   = alarm or (state == "FAULT")
        amber = (not interlocks_ok) and (state != "FAULT")
        green = (state == "ARMED") and interlocks_ok
        blue  = state in ("EXPOSE", "PREVIEW")
        gpio.write(self.red,   red)
        gpio.write(self.amber, amber)
        gpio.write(self.green, green)
        gpio.write(self.blue,  blue)
