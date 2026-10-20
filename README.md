# 🛡️ Blockchain-Secured SIM Swap Fraud Detection System
## Capstone Project 2 — Complete Hardware & Software Integration Guide

Welcome to the **Blockchain-Secured SIM Swap Fraud Detection System**! This repository contains the complete codebase, Solidity smart contracts, machine learning models, virtual simulators, and physical **ESP32 hardware firmware** for our college capstone project.

This guide provides everything you need to set up the software environment, wire the physical hardware, flash the ESP32 microcontroller, and run the complete system end-to-end.

---

## 🏛️ System Architecture Overview

```
                      +---------------------------------------+
                      |         Physical ESP32 Terminal       |
                      |  - RC522 RFID Card Reader (Agent Auth)|
                      |  - 4x4 Matrix Keypad (Request ID)     |
                      |  - 16x2 I2C LCD Display               |
                      |  - Tri-Color LEDs (Green/Yellow/Red)  |
                      |  - 5V Active Piezo Alarm Buzzer       |
                      +-------------------+-------------------+
                                          |
                               [Wi-Fi / HTTP POST]
                                          v
                      +---------------------------------------+
                      |       FastAPI Backend Server          |
                      |       (Runs on Laptop Port 8000)      |
                      +-------------------+-------------------+
                                          |
                 +------------------------+------------------------+
                 |                                                 |
                 v                                                 v
  +-------------------------------+             +-----------------------------------+
  |   Hybrid Fraud Risk Engine    |             |    Dual-Layer Audit Architecture  |
  |  - XGBoost ML Classifier      |             |  1. Local SHA-256 Hash Chain      |
  |  - 5 Heuristic Rule Checks    |             |  2. SimSwapAudit.sol Smart        |
  |  - Real-time SHAP Force Plots |             |     Contract on Local EVM Node    |
  +---------------+---------------+             +-----------------+-----------------+
                  |                                               |
                  +-----------------------+-----------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |     Streamlit Real-Time Dashboard     |
                      |       (Runs on Laptop Port 8501)      |
                      |  - Live Risk & SHAP Explainability    |
                      |  - Virtual ESP32 Hardware Simulator   |
                      |  - Smart Contract On-Chain Receipts   |
                      |  - Model Metrics & Confusion Matrix   |
                      +---------------------------------------+
```

---

## 💻 Part 1: Software Installation & Setup Guide

### 1. Prerequisites
Ensure you have the following installed on your laptop:
- **Python 3.10 – 3.12** ([Download Python](https://www.python.org/downloads/))
- **Node.js v18+ & npm** ([Download Node.js](https://nodejs.org/)) — *Required for local EVM blockchain (Ganache)*
- **Git** ([Download Git](https://git-scm.com/))
- **Arduino IDE v2.0+** ([Download Arduino IDE](https://www.arduino.cc/en/software)) — *For ESP32 firmware*

---

### 2. Clone the Repository & Open Project Directory
Open **Windows PowerShell** (or Terminal on macOS/Linux):
```powershell
git clone https://github.com/ArunKumar-rmkec/blockchain-sim-swap-fraud-detection.git
cd blockchain-sim-swap-fraud-detection
```

---

### 3. Create & Activate Python Virtual Environment

**Windows PowerShell:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### 4. Install Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

### 5. Start the Local EVM Blockchain (Terminal 1)
Start a deterministic local Ethereum blockchain using Ganache on port `8545` (Chain ID: `1337`):
```powershell
npx --yes ganache --port 8545 --chain.chainId 1337 --wallet.deterministic
```
> [!NOTE]
> Keep this terminal window open! Ganache provides 10 pre-funded test accounts with 1,000 ETH each.

---

### 6. Compile & Deploy the Solidity Smart Contract (Terminal 2)
In a new terminal window (activate virtual environment first):

1. **Compile `SimSwapAudit.sol` with Solidity 0.8.20:**
   ```powershell
   python blockchain/compile.py
   ```
2. **Deploy to the running local EVM node:**
   ```powershell
   python blockchain/deploy.py
   ```
   *This deploys the smart contract, verifies the runtime bytecode on-chain, and writes the deployment address and ABI to `blockchain/build/deployment.json` and `data/active_deployment.json`.*

---

### 7. Launch the Backend API & Dashboard

**Start FastAPI Backend (Terminal 2):**
```powershell
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
- Interactive Swagger API Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- API Health Status: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Blockchain Live Status: [http://127.0.0.1:8000/blockchain/status](http://127.0.0.1:8000/blockchain/status)

> [!IMPORTANT]
> Binding to `--host 0.0.0.0` allows the physical ESP32 terminal on your local Wi-Fi network to connect to your laptop's backend!

**Start Streamlit Dashboard (Terminal 3):**
```powershell
streamlit run dashboard/app.py
```
- Open in Browser: [http://localhost:8501](http://localhost:8501)

---

### 8. Run Automated Test Suite (49 Tests)
Verify that everything is working properly:
```powershell
pytest -v
```
- **Emulation / Offline Tests:** `pytest -m "not evm" -v` (40 tests)
- **Live Local EVM Tests:** `pytest -m "evm" -v` (9 tests)
- **Total:** **49 Passed (100% Pass Rate)**

---

## 📟 Part 2: Physical ESP32 Hardware Wiring & Flashing Guide

This section is for the teammate who has the physical hardware components.

### 1. Hardware Bill of Materials (BOM)

| Component | Quantity | Purpose |
|---|:---:|---|
| **ESP32 NodeMCU DevKit V1** (30-pin or 38-pin) | 1 | Core microcontroller with Wi-Fi |
| **MFRC522 RFID Module** (with RFID Card & Keyfob) | 1 | Contactless smart-card authentication (13.56 MHz) |
| **4x4 Membrane Matrix Keypad** | 1 | Request ID numeric input (0-9, *, #) |
| **16x2 LCD Display with I2C Backpack (PCF8574)** | 1 | Real-time decision & risk score display |
| **Tri-Color LEDs** (Green, Yellow, Red) | 3 | Visual status indicators |
| **220Ω Resistors** | 3 | Current limiting for LEDs |
| **5V Active Piezo Buzzer** | 1 | Audio feedback (Success, Warning, Fraud Alarm) |
| **Breadboard & Jumper Wires** | 1 pack | Circuit connections |
| **Micro-USB Cable** | 1 | Connecting ESP32 to laptop |

---

### 2. Complete ESP32 Pinout Wiring Guide

Connect the components to the ESP32 according to this exact pin mapping:

```
+-------------------------------------------------------------------------+
|                        ESP32 GPIO PINOUT TABLE                          |
+----------------------+--------------------+-----------------------------+
| ESP32 Pin            | Connected Module   | Pin on Peripheral Module    |
+----------------------+--------------------+-----------------------------+
| 3.3V  (CAUTION!)     | RC522 RFID         | VCC (DO NOT USE 5V FOR RFID)|
| GND                  | Common Ground      | GND (All Modules)           |
| GPIO 5               | RC522 RFID         | SDA / SS                    |
| GPIO 18              | RC522 RFID         | SCK                         |
| GPIO 23              | RC522 RFID         | MOSI                        |
| GPIO 19              | RC522 RFID         | MISO                        |
| GPIO 17              | RC522 RFID         | RST                         |
+----------------------+--------------------+-----------------------------+
| VIN (5V)             | I2C 16x2 LCD       | VCC                         |
| GND                  | I2C 16x2 LCD       | GND                         |
| GPIO 21              | I2C 16x2 LCD       | SDA                         |
| GPIO 22              | I2C 16x2 LCD       | SCL                         |
+----------------------+--------------------+-----------------------------+
| GPIO 13              | 4x4 Keypad         | Pin 1 (Row 1)               |
| GPIO 12              | 4x4 Keypad         | Pin 2 (Row 2)               |
| GPIO 14              | 4x4 Keypad         | Pin 3 (Row 3)               |
| GPIO 27              | 4x4 Keypad         | Pin 4 (Row 4)               |
| GPIO 26              | 4x4 Keypad         | Pin 5 (Col 1)               |
| GPIO 25              | 4x4 Keypad         | Pin 6 (Col 2)               |
| GPIO 33              | 4x4 Keypad         | Pin 7 (Col 3)               |
| GPIO 32              | 4x4 Keypad         | Pin 8 (Col 4)               |
+----------------------+--------------------+-----------------------------+
| GPIO 2               | Green LED          | Anode (+) through 220Ω res  |
| GPIO 4               | Yellow LED         | Anode (+) through 220Ω res  |
| GPIO 15              | Red LED            | Anode (+) through 220Ω res  |
| GND                  | All LEDs           | Cathode (-) Flat side       |
+----------------------+--------------------+-----------------------------+
| GPIO 16              | Active Buzzer      | Positive (+)                |
| GND                  | Active Buzzer      | Negative (-)                |
+----------------------+--------------------+-----------------------------+
```

> [!CAUTION]
> **CRITICAL POWER WARNING**:
> - The **MFRC522 RFID Reader requires 3.3V**. Connecting it to 5V will permanently burn out the RFID chip!
> - The **I2C 16x2 LCD and Buzzer require 5V (VIN)** for proper contrast and loud audio.

---

### 3. Flashing the ESP32 Firmware via Arduino IDE

#### Step A: Configure Arduino IDE
1. Open **Arduino IDE**.
2. Go to **File -> Preferences**.
3. In **Additional Boards Manager URLs**, paste:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Go to **Tools -> Board -> Boards Manager**, search for `esp32` by **Espressif Systems**, and click **Install**.

#### Step B: Install Required Arduino Libraries
Go to **Tools -> Manage Libraries...** and install the following:
1. `MFRC522` by GithubCommunity
2. `Keypad` by Mark Stanley, Alexander Brevig
3. `LiquidCrystal I2C` by Frank de Brabander
4. `ArduinoJson` (Version 6 or 7) by Benoit Blanchon

#### Step C: Configure Wi-Fi & Laptop IP Address
1. Open [`hardware/esp32_firmware/esp32_sim_swap_terminal.ino`](file:///c:/Users/arunk/Downloads/sim_swap_software_starter/sim_swap_software_starter/hardware/esp32_firmware/esp32_sim_swap_terminal.ino).
2. Find your laptop's Wi-Fi IP address:
   - On Windows, open PowerShell and type: `ipconfig`
   - Look for **IPv4 Address** under your active Wi-Fi adapter (e.g. `192.168.1.15`).
3. Update lines 31-33 in `esp32_sim_swap_terminal.ino`:
   ```cpp
   const char* WIFI_SSID     = "YOUR_HOME_OR_HOTSPOT_WIFI";
   const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
   const char* BACKEND_URL   = "http://192.168.1.15:8000/hardware/terminal-evaluate"; // Replace with your laptop's IP
   ```
   > [!TIP]
   > Both your laptop and the ESP32 must be connected to the **same Wi-Fi network** (or phone hotspot).

#### Step D: Upload Firmware
1. Connect ESP32 to your laptop using a Micro-USB data cable.
2. Under **Tools -> Board**, select **"DOIT ESP32 DEVKIT V1"** (or ESP32 Dev Module).
3. Under **Tools -> Port**, select the active COM port (e.g., `COM3` or `COM5`).
4. Click **Upload** (Arrow icon).
   *(If upload gets stuck on `Connecting......_____`, hold down the **BOOT** button on the ESP32 until the flashing progress percentage begins).*

---

## 🎮 Part 3: Running the Full End-to-End Live Demo

Once software and hardware are set up:

1. **Power on ESP32:**
   - The 16x2 LCD will display:
     ```
     SIM SWAP SYSTEM
     CONNECTING WIFI
     ```
   - Once connected, it displays:
     ```
     READY: TAP CARD
     SIM SWAP SYSTEM
     ```

2. **Step 1: Authenticate Telecom Agent (RFID):**
   - Tap your authorized RFID Smart Card (`A1B2C3D4`, `11223344`, or `DEMO1234`).
   - The buzzer emits a short confirmation beep.
   - The LCD displays:
     ```
     AGENT AUTH OK!
     ENTER REQ ID:
     ```

3. **Step 2: Enter SIM Swap Request ID (Keypad):**
   - Enter the request ID numbers using the 4x4 keypad, followed by `#` to submit:
     - Example: Press `7`, `0`, `1`, `#` (Evaluates `REQ00701`).
     - Example: Press `1`, `#` (Evaluates `REQ00001`).
   - Press `*` at any time to backspace / clear.

4. **Step 3: Instant Fraud Decision & Multi-Modal Actuation:**
   - The ESP32 transmits a JSON payload over Wi-Fi to your laptop's backend:
     ```json
     {"request_id": "REQ00701", "agent_uid": "A1B2C3D4", "terminal_id": "ESP32_PHYSICAL_01"}
     ```
   - **Case A: Clean / Low Risk (`REQ00001`):**
     - LCD: `REQ00001: OK` | `APPROVED 2.5%`
     - LED: **Green LED turns ON**
     - Buzzer: Short pleasant double-beep
     - Blockchain: Confirmed on-chain transaction receipt generated.
   - **Case B: Suspicious Fraud (`REQ00701`):**
     - LCD: `REQ00701: FRAUD` | `BLOCKED 96.7%`
     - LED: **Red LED turns ON**
     - Buzzer: **Pulsing high-frequency alarm (5 beeps)**
     - Blockchain: Immutable fraud record anchored on Ethereum smart contract.

5. **Step 4: Inspect Live On Dashboard:**
   - Open [http://localhost:8501](http://localhost:8501) on your laptop.
   - Watch the transaction hash appear in real time under the **"⛓️ Blockchain & Smart Contract"** tab.
   - Inspect the **SHAP Force Plot** under the **"🛡️ Risk Engine & SHAP"** tab to see which features triggered the fraud flag.

---

## 💻 Part 4: Software-Only Mode (No Hardware Required)

If your teammate wants to test the software while the physical hardware is elsewhere:

1. **Virtual Hardware Simulator in Browser:**
   - Navigate to Tab 2 (**"📟 Hardware Terminal"**) in the Streamlit dashboard ([http://localhost:8501](http://localhost:8501)).
   - It features an exact visual software twin of the 16x2 blue LCD, glowing RGB LEDs, buzzer indicator, and RFID card selector.

2. **CLI Terminal Simulator:**
   ```powershell
   python backend/esp32_simulator.py
   ```

---

## 🔧 Part 5: Teammate Troubleshooting & Common Pitfalls

| Issue | Root Cause | Solution |
|---|---|---|
| **ESP32 COM Port not appearing in Arduino IDE** | Missing USB-to-UART driver | Install the **CP210x** or **CH340** driver depending on your ESP32 board chip. |
| **`Connecting......_____` during upload** | ESP32 bootloader handshake | Hold down the physical **BOOT** button on the ESP32 board until the flashing dots turn into writing percentages. |
| **LCD displays black boxes or blank screen** | Contrast potentiometer not tuned | Turn the small blue potentiometer on the back of the I2C LCD backpack with a screwdriver until text is sharp. |
| **RFID Reader fails to detect cards** | Voltage or SPI pin wiring mismatch | Ensure RFID is wired to **3.3V** (NOT 5V). Verify SPI pins: SDA=5, SCK=18, MOSI=23, MISO=19, RST=17. |
| **ESP32 Wi-Fi connects, but evaluation times out** | Laptop Windows Firewall blocking port 8000 | In Windows Defender Firewall, allow inbound connections for Python / Port 8000, or connect both laptop and ESP32 to your phone's personal hotspot. |
| **`RPC_DISCONNECTED` on Backend** | Ganache local node is not running | Start Ganache in Terminal 1 using `npx ganache --port 8545 --chain.chainId 1337`. |
| **`NO_DEPLOYED_BYTECODE_AT_ADDRESS`** | Contract not deployed to fresh node | Run `python blockchain/deploy.py` to deploy `SimSwapAudit.sol` to the running node. |

---

## 👥 Authors & Capstone Team
- **College Capstone Project 2**
- **Title:** *Blockchain-Secured SIM Swap Fraud Detection System*
- **Technology Stack:** Solidity ^0.8.20, Web3.py, Ganache EVM, FastAPI, XGBoost, SHAP, Streamlit, Arduino C++, ESP32 DevKit.
