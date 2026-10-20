# ESP32 Hardware Terminal Specification & Wiring Guide
## Capstone Project 2 — Blockchain-Secured SIM Swap Fraud Detection

This directory contains the physical firmware and wiring diagrams for the ESP32 Telecom Agent Terminal. When physical hardware is present, this terminal reads agent RFID smart cards, accepts request IDs via 4x4 keypad, queries the laptop backend, and actuates physical 16x2 LCD, tri-color LEDs, and audio buzzers.

---

## 1. Hardware Bill of Materials (BOM)

| Component | Interface | Description |
|---|---|---|
| **ESP32 NodeMCU / DevKit V1** | Micro-USB / Type-C | Core 240MHz dual-core microcontroller with Wi-Fi & Bluetooth |
| **MFRC522 RFID Reader** | SPI | 13.56MHz contactless smart card / tag reader |
| **4x4 Matrix Keypad** | Digital GPIO | Membrane/Tactile keypad for entering request IDs |
| **I2C 16x2 LCD Display** | I2C (PCF8574 at `0x27`) | Real-time status, agent welcome, and decision display |
| **Tri-Color Indicator LEDs** | Digital GPIO | Green (Approved), Yellow (Review), Red (Fraud Alert) |
| **Active 5V Buzzer** | Digital GPIO | Audio tone patterns for scan, approval, and sirens |

---

## 2. Pinout Wiring Diagram

```
ESP32 Pin       Connected Peripheral Component
─────────       ──────────────────────────────
GPIO 21 (SDA)   I2C LCD SDA
GPIO 22 (SCL)   I2C LCD SCL
GPIO 5  (SS)    MFRC522 RFID SDA / SS
GPIO 18 (SCK)   MFRC522 RFID SCK
GPIO 23 (MOSI)  MFRC522 RFID MOSI
GPIO 19 (MISO)  MFRC522 RFID MISO
GPIO 17 (RST)   MFRC522 RFID RST
3.3V            MFRC522 VCC (DO NOT USE 5V FOR RFID)
GND             Common Ground (All Modules)

GPIO 13 (Row 1) 4x4 Keypad Pin 1
GPIO 12 (Row 2) 4x4 Keypad Pin 2
GPIO 14 (Row 3) 4x4 Keypad Pin 3
GPIO 27 (Row 4) 4x4 Keypad Pin 4
GPIO 26 (Col 1) 4x4 Keypad Pin 5
GPIO 25 (Col 2) 4x4 Keypad Pin 6
GPIO 33 (Col 3) 4x4 Keypad Pin 7
GPIO 32 (Col 4) 4x4 Keypad Pin 8

GPIO 2          Green LED (with 220Ω resistor)
GPIO 4          Yellow LED (with 220Ω resistor)
GPIO 15         Red LED (with 220Ω resistor)
GPIO 16         Active Buzzer Positive (+)
VIN (5V)        LCD VCC & Buzzer VCC
```

---

## 3. Flashing Instructions (For Teammate / Hardware Setup)

1. Open **Arduino IDE** (or VS Code + PlatformIO).
2. Install the **ESP32 Board Package** via Boards Manager (`esp32 by Espressif Systems`).
3. Install required libraries from Library Manager:
   - `MFRC522` by GithubCommunity
   - `Keypad` by Mark Stanley, Alexander Brevig
   - `LiquidCrystal I2C` by Frank de Brabander
   - `ArduinoJson` by Benoit Blanchon (Version 6 or 7)
4. Open [`hardware/esp32_firmware/esp32_sim_swap_terminal.ino`](file:///c:/Users/arunk/Downloads/sim_swap_software_starter/sim_swap_software_starter/hardware/esp32_firmware/esp32_sim_swap_terminal.ino).
5. Configure your Wi-Fi credentials and laptop local IP address:
   ```cpp
   const char* WIFI_SSID     = "YOUR_WIFI_NAME";
   const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
   const char* BACKEND_URL   = "http://192.168.1.X:8000/hardware/terminal-evaluate";
   ```
6. Select Board **"DOIT ESP32 DEVKIT V1"** and your COM Port.
7. Click **Upload**.

---

## 4. Software-Only Simulation (No Hardware Needed)

When testing without physical hardware, run the Python virtual simulator:
```powershell
python -m backend.esp32_simulator
```
Or interact with the **📟 Hardware Terminal** visual tab in the Streamlit web dashboard.
