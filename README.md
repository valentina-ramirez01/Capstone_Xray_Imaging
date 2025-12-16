# Capstone_Xray_Imaging

A low-cost, non-destructive X-ray imaging system for integrated circuit (IC) inspection, developed as a senior capstone project at the University of Puerto Rico – Mayagüez (UPRM).

This repository contains the **control software, graphical user interface (GUI), and image-processing tools** used to operate a custom-built X-ray imaging prototype designed for semiconductor inspection and failure analysis.

---

## 📌 Project Overview

Integrated Circuits (ICs) are increasingly complex, making internal defects difficult to detect using optical inspection methods. Commercial non-destructive X-ray inspection systems are effective but often prohibitively expensive.

This project addresses that gap by developing a **compact, affordable X-ray imaging system** capable of visualizing internal IC structures without destructive testing. The system integrates:

- Custom high-voltage power electronics  
- A Raspberry Pi–based control system  
- A PyQt-based graphical user interface  
- Python image-processing pipelines  

---

## 🧠 Key Features

- **Non-destructive X-ray inspection** of ICs and small electronic assemblies  
- **Custom GUI** for system control, safety monitoring, and image visualization  
- **Real-time safety interlocks**, including:
  - Emergency Stop (E-Stop)
  - High-voltage watchdog via ADC monitoring
  - Door/interlock logic
- **Image processing tools** for:
  - Contrast and brightness adjustment
  - Zoom and inspection enhancement
- **Modular software architecture** for maintainability and expansion

---

## 🖥️ System Architecture

### Hardware (High-Level)
- Raspberry Pi (main controller)
- Custom high-voltage generation stage (ZVS + flyback + multiplier)
- X-ray tube and scintillation screen
- Pi Camera (via Picamera2)
- Emergency stop and safety interlocks
- ADC-based high-voltage monitoring
- Relay-controlled HV enable/disable

### Software
- Python 3
- PyQt6 (GUI)
- OpenCV (image processing)
- Picamera2 (camera interface)
- GPIO & I2C interfaces for hardware control

---


