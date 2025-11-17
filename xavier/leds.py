import RPi.GPIO as GPIO

class LedPanel:
    """
    LED policy:
      - RED   : HV alarm OR FAULT state
      - AMBER : Interlocks NOT OK (but not in FAULT)
      - GREEN : ARMED and interlocks OK
      - BLUE  : X-ray ON (EXPOSE or PREVIEW)
    """

    def __init__(self):
        # Updated pin numbers
        self.red = 26
        self.amber = 13
        self.green = 21
        self.blue = 27

        GPIO.setmode(GPIO.BCM)

        for p in (self.red, self.amber, self.green, self.blue):
            GPIO.setup(p, GPIO.OUT)
            GPIO.output(p, GPIO.LOW)

    def write(self, pin: int, value: bool):
        GPIO.output(pin, GPIO.HIGH if value else GPIO.LOW)

    def apply(self, *, alarm: bool, interlocks_ok: bool, state: str):
        """
        state = one of:
           "FAULT", "ARMED", "PREVIEW", "EXPOSE", "IDLE"
        """
        red   = alarm or (state == "FAULT")
        amber = (not interlocks_ok) and (state != "FAULT")
        green = (state == "ARMED") and interlocks_ok
        blue  = state in ("EXPOSE", "PREVIEW")

        self.write(self.red, red)
        self.write(self.amber, amber)
        self.write(self.green, green)
        self.write(self.blue, blue)

    def cleanup(self):
        GPIO.cleanup()
