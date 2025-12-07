#!/bin/bash
set -e

echo "=== XRay Project Setup  ==="
echo ""

# ----------------------------------------------------
# 1. Update system
# ----------------------------------------------------
echo "[1/6] Updating system packages..."
sudo apt update && sudo apt upgrade -y


# ----------------------------------------------------
# 2. Install apt dependencies (system libs only)
# ----------------------------------------------------
echo "[2/6] Installing system dependencies..."

sudo apt install -y \
    python3 \
    python3-pip \
    python3-libcamera \
    python3-libcamera-apps \
    libcamera-tools \
    python3-opencv \
    python3-numpy \
    python3-smbus \
    python3-serial \
    python3-gpiozero \
    rpi.gpio-common \
    python3-rpi.gpio \
    git \
    build-essential


# ----------------------------------------------------
# 3. Enable Pi interfaces
# ----------------------------------------------------
echo "[3/6] Enabling Pi interfaces (I2C, SPI, Camera)..."
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_camera 0


# ----------------------------------------------------
# 4. Python packages (pip-only packages)
# ----------------------------------------------------
echo "[4/6] Installing Python pip dependencies..."

pip3 install --upgrade pip

pip3 install \
    pyqt6 \
    opencv-python \
    numpy \
    pillow \
    scipy \
    matplotlib \
    smbus2 \
    pyserial \
    requests \
    python-dateutil


# ----------------------------------------------------
# 5. Picamera2 (Bookworm)
# ----------------------------------------------------
echo "[5/6] Ensuring Picamera2 is installed..."

sudo apt install -y python3-picamera2


# ----------------------------------------------------
# 6. Done
# ----------------------------------------------------
echo ""
echo "=== SETUP COMPLETE ==="
echo "   python3 ~/Capstone_Xray_Imaging/Interface_Capstone/Interface.py"
