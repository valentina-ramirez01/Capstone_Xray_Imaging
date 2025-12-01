#!/bin/bash
set -e

echo "=== XRay Project Setup (NO AUTOBOOT) ==="
echo ""

# ----------------------------
# 1. Update system
# ----------------------------
echo "[1/6] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# ----------------------------
# 2. Install dependencies
# ----------------------------
echo "[2/6] Installing dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-pyqt6 \
    python3-opencv \
    python3-numpy \
    python3-picamera2 \
    git \
    build-essential

# ----------------------------
# 3. Enable required interfaces
# ----------------------------
echo "[3/6] Enabling Pi interfaces (I2C, SPI, Camera)..."
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_camera 0

# ----------------------------
# 4. Install Python packages
# ----------------------------
echo "[4/6] Installing Python package dependencies..."
pip3 install --upgrade pip
pip3 install \
    pyqt6 \
    numpy \
    opencv-python \
    pillow \
    RPi.GPIO

# ----------------------------
# 6. Finished
# ----------------------------
echo ""
echo "=== SETUP COMPLETE ==="
echo "No autostart or boot-time scripts were created."
echo "You can start your GUI manually using:"
echo "   python3 /home/xray/Xray/Capstone_Xray_Imaging/Interface_Capstone/Interface.py"
echo ""
