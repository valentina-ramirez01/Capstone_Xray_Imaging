import serial
import time
import RPi.GPIO as GPIO

# -----------------------------
# GPIO SETUP
# -----------------------------
GPIO.setmode(GPIO.BCM)

SW1 = 17   # OPEN limit switch
SW2 = 18   # CLOSE limit switch

GPIO.setup(SW1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(SW2, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# -----------------------------
# ARDUINO SERIAL
# -----------------------------
ser = serial.Serial('/dev/ttyACM1', 115200, timeout=1)
time.sleep(2)

print("=== MOTOR 1 TEST ===")
print("Commands:")
print("   o → OPEN  (backwards until SW1)")
print("   c → CLOSE (forward until SW2)")
print("   q → quit")

# -----------------------------
# MOTOR MOVEMENT FUNCTIONS
# -----------------------------
def motor_open_until_sw1():
    print("Opening (BACKWARD)…")
    while GPIO.input(SW1) == 1:     # 1 = NOT pressed
        ser.write(b"M1B\n")
        time.sleep(0.002)
    print("SW1 reached! (OPEN LIMIT)")


def motor_close_until_sw2():
    print("Closing (FORWARD)…")
    while GPIO.input(SW2) == 1:
        ser.write(b"M1F\n")
        time.sleep(0.002)
    print("SW2 reached! (CLOSE LIMIT)")


# -----------------------------
# MAIN LOOP
# -----------------------------
while True:
    cmd = input(">> ").strip().lower()

    if cmd == "o":
        motor_open_until_sw1()

    elif cmd == "c":
        motor_close_until_sw2()

    elif cmd == "q":
        print("Exiting.")
        break

    else:
        print("Unknown command. Use o/c/q.")
