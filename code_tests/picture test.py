import RPi.GPIO as GPIO
import time
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from picamera2 import Picamera2
import libcamera

# ===== CONFIGURATION =====
CAPTURE_TRIGGER = 23       # Single relay GPIO
IMAGE_DIR = "/home/xray_juanito"
IMAGE_PREFIX = "capture_"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SIZE = 32
TEXT_COLOR = "white"
TEXT_POSITION = (10, 10)
# =========================

# === MENU: Set Gain and Shutter ===
def get_user_input():
    try:
        gain = int(input("Enter gain (e.g. 1 to 16): "))
        shutter_sec = float(input("Enter shutter time in seconds (e.g. 3.0): "))
        if gain < 1 or shutter_sec <= 0:
            raise ValueError
        return gain, int(shutter_sec * 1_000_000), shutter_sec
    except ValueError:
        print("⚠️ Invalid input. Please enter positive numbers.")
        return get_user_input()

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(CAPTURE_TRIGGER, GPIO.OUT)
GPIO.output(CAPTURE_TRIGGER, GPIO.HIGH)  # Idle state (relay OFF)

try:
    # Get user settings
    GAIN, SHUTTER_US, SHUTTER_SEC = get_user_input()

    # Create filename + overlay text
    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    display_time = now.strftime("%Y-%m-%d %H:%M:%S")
    overlay_text = f"{display_time}  Gain: {GAIN}  Shutter: {SHUTTER_SEC:.1f}s"
    jpg_file = os.path.join(IMAGE_DIR, f"{IMAGE_PREFIX}{timestamp_str}.jpg")

    print(f"\n📷 Capturing -> {jpg_file}")

    # ===== Activate Relay =====
    GPIO.output(CAPTURE_TRIGGER, GPIO.LOW)
    print("⚡ Relay activated (X-ray ON)")

    # ===== Setup Camera =====
    picam2 = Picamera2()

    config = picam2.create_still_configuration(
        main={"size": (2592, 1944)},   # OV5647 max resolution
        controls={
            "AnalogueGain": float(GAIN),
            "ExposureTime": SHUTTER_US,
            "AeEnable": False,
            "AwbEnable": False
        }
    )

    picam2.configure(config)
    picam2.start()

    # Allow camera to stabilize exposure settings
    time.sleep(0.3)

    # OV5647 exposure limit warning
    if SHUTTER_SEC > 1:
        print("⚠️ WARNING: OV5647 real exposure limit is ~1 second.")
        print("   The system will wait but sensor will not expose longer.")

    # Wait for requested exposure + readout time
    time.sleep(SHUTTER_SEC + 0.4)

    # Capture image
    picam2.capture_file(jpg_file)
    print("📥 Image captured")

    # Turn relay OFF
    GPIO.output(CAPTURE_TRIGGER, GPIO.HIGH)
    print("⚡ Relay deactivated (X-ray OFF)")

    # ===== Add Overlay Text =====
    print("🖊️ Adding timestamp, gain, and shutter overlay...")
    image = Image.open(jpg_file)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    draw.text(TEXT_POSITION, overlay_text, font=font, fill=TEXT_COLOR)
    image.save(jpg_file)

    print("✅ Capture complete with overlay.")

finally:
    GPIO.output(CAPTURE_TRIGGER, GPIO.HIGH)
    time.sleep(0.5)
    GPIO.cleanup()
    print("🧹 GPIO cleaned up. Relay forced HIGH.")
