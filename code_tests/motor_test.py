import serial
import time
import RPi.GPIO as GPIO

# ----- GPIO SETUP -----
GPIO.setmode(GPIO.BCM)

LIMIT_FWD = 17   # your wiring
LIMIT_BACK = 25  # your wiring

GPIO.setup(LIMIT_FWD, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(LIMIT_BACK, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ----- SERIAL TO ARDUINO -----
arduino = serial.Serial('/dev/ttyACM0', 115200, timeout=0.1)
time.sleep(2)  # wait for Arduino reset

def send(cmd):
    arduino.write(cmd.encode())

# ----- MAIN PROGRAM -----
print("Press S to start forward movement")
print("Press R to start backward movement")

while True:
    key = input("Enter command (S=forward, R=reverse, Q=quit): ").strip().upper()

    if key == "Q":
        send("S")
        break

    # -------- MOVE FORWARD --------
    if key == "S":
        print("Moving forward...")
        send("F")
        while True:
            if GPIO.input(LIMIT_FWD) == 0:   # limit reached
                print("FORWARD limit reached!")
                send("S")
                break
            time.sleep(0.001)

    # -------- MOVE BACKWARD --------
    if key == "R":
        print("Moving backward...")
        send("B")
        while True:
            if GPIO.input(LIMIT_BACK) == 0:
                print("BACKWARD limit reached!")
                send("S")
                break
            time.sleep(0.001)

send("S")
GPIO.cleanup()
