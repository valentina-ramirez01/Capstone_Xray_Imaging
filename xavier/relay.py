# relay.py
# Single-relay controller using GPIO23 (active LOW or HIGH)

import RPi.GPIO as GPIO

RELAY_PIN = 23    # your relay GPIO pin

# Relay type: choose ACTIVE_LOW or ACTIVE_HIGH
# Most Pi relay HATs/modules are ACTIVE LOW (0 = ON)
ACTIVE_LOW = True

GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)

if ACTIVE_LOW:
    RELAY_ON = GPIO.LOW
    RELAY_OFF = GPIO.HIGH
else:
    RELAY_ON = GPIO.HIGH
    RELAY_OFF = GPIO.LOW


def hv_on() -> None:
    """Energize relay connected to GPIO23."""
    GPIO.output(RELAY_PIN, RELAY_ON)
    print("HV Relay ON")


def hv_off() -> None:
    """De-energize relay connected to GPIO23."""
    GPIO.output(RELAY_PIN, RELAY_OFF)
    print("HV Relay OFF")


def hv_cleanup() -> None:
    """Reset GPIO pin safely."""
    GPIO.output(RELAY_PIN, RELAY_OFF)
    GPIO.cleanup(RELAY_PIN)
