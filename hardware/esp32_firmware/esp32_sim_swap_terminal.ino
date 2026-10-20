/*
 * ESP32 Hardware Terminal: Blockchain-Secured SIM Swap Fraud Detection
 * ====================================================================
 * Capstone Project 2
 * 
 * Hardware Peripherals:
 * - Microcontroller: ESP32 NodeMCU / DevKit V1
 * - RFID Reader: MFRC522 (SPI) for Telecom Agent Card Authentication
 * - Keypad: 4x4 Matrix Keypad for entering Request ID (e.g. 00001#)
 * - Display: I2C 16x2 LiquidCrystal LCD (PCF8574 adapter at 0x27)
 * - Visual Indicators: Tri-color LEDs (Green = Approved, Yellow = Review, Red = Fraud Alert)
 * - Audio: Active 5V Piezo Buzzer
 * 
 * Communication:
 * - Wi-Fi HTTP Client communicating with FastAPI Backend on Windows Laptop
 *   Endpoint: POST http://<LAPTOP_IP>:8000/hardware/terminal-evaluate
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Keypad.h>

// ==========================================
// 1. Wi-Fi & Backend Configuration
// ==========================================
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* BACKEND_URL   = "http://192.168.1.100:8000/hardware/terminal-evaluate"; // Update to your laptop's local IP
const char* TERMINAL_ID   = "ESP32_PHYSICAL_01";

// ==========================================
// 2. Hardware Pin Definitions (ESP32 DevKit)
// ==========================================
// RC522 RFID SPI Pins
#define SS_PIN    5
#define RST_PIN   22 // Note: If I2C uses 22 for SCL, use GPIO 17 for RST
#define BUZZER_PIN 16
#define LED_GREEN  2
#define LED_YELLOW 4
#define LED_RED    15

// Keypad Configuration (4x4 Matrix)
const byte ROWS = 4;
const byte COLS = 4;
char keys[ROWS][COLS] = {
  {'1','2','3','A'},
  {'4','5','6','B'},
  {'7','8','9','C'},
  {'*','0','#','D'}
};
byte rowPins[ROWS] = {13, 12, 14, 27};
byte colPins[COLS] = {26, 25, 33, 32};

// ==========================================
// 3. Peripheral Instances
// ==========================================
LiquidCrystal_I2C lcd(0x27, 16, 2);
MFRC522 rfid(SS_PIN, RST_PIN);
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

// State Variables
String scannedAgentUID = "";
String enteredRequestID = "";

void setup() {
  Serial.begin(115200);
  delay(500);

  // Pin Modes
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  setAllLEDs(LOW, LOW, LOW);

  // Initialize I2C LCD
  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("SIM SWAP SYSTEM");
  lcd.setCursor(0, 1);
  lcd.print("CONNECTING WIFI");

  // Connect to Wi-Fi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 20) {
    delay(500);
    Serial.print(".");
    retry++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[ESP32] Wi-Fi Connected. IP: " + WiFi.localIP().toString());
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("WIFI CONNECTED");
    lcd.setCursor(0, 1);
    lcd.print(WiFi.localIP().toString());
  } else {
    Serial.println("\n[ESP32] Wi-Fi Failed. Offline Standby.");
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("WIFI FAILED");
  }
  delay(1500);

  // Initialize RFID Reader (SPI)
  SPI.begin(18, 19, 23, SS_PIN); // SCK=18, MISO=19, MOSI=23, SS=5
  rfid.PCD_Init();

  beep(1, 100);
  resetToStandby();
}

void loop() {
  // 1. Check for RFID Card Scan
  if (scannedAgentUID == "") {
    if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
      scannedAgentUID = "";
      for (byte i = 0; i < rfid.uid.size; i++) {
        if (rfid.uid.uidByte[i] < 0x10) scannedAgentUID += "0";
        scannedAgentUID += String(rfid.uid.uidByte[i], HEX);
      }
      scannedAgentUID.toUpperCase();
      rfid.PICC_HaltA();
      rfid.PCD_StopCrypto1();

      Serial.println("[ESP32] Agent Card Tapped: " + scannedAgentUID);
      beep(1, 80);

      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("AGENT: " + scannedAgentUID.substring(0, 8));
      lcd.setCursor(0, 1);
      lcd.print("ENTER REQ ID:#");
      enteredRequestID = "";
    }
  }

  // 2. Check Keypad Entry (when card is scanned)
  if (scannedAgentUID != "") {
    char key = keypad.getKey();
    if (key) {
      beep(1, 40);
      if (key == '#') {
        // Submit Request
        if (enteredRequestID.length() > 0) {
          sendEvaluationRequest();
          resetToStandby();
        }
      } else if (key == '*') {
        // Cancel / Backspace
        resetToStandby();
      } else {
        if (enteredRequestID.length() < 10) {
          enteredRequestID += key;
          lcd.setCursor(0, 1);
          lcd.print("ID: " + enteredRequestID + "   ");
        }
      }
    }
  }
}

void sendEvaluationRequest() {
  // Format formatted request ID e.g. "REQ00001"
  String formattedReq = enteredRequestID;
  if (!formattedReq.startsWith("REQ") && !formattedReq.startsWith("req")) {
    int num = enteredRequestID.toInt();
    char buf[12];
    sprintf(buf, "REQ%05d", num);
    formattedReq = String(buf);
  }

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("EVALUATING...");
  lcd.setCursor(0, 1);
  lcd.print(formattedReq);

  if (WiFi.status() != WL_CONNECTED) {
    showError("NO WIFI LINK");
    return;
  }

  HTTPClient http;
  http.begin(BACKEND_URL);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<256> doc;
  doc["terminal_id"] = TERMINAL_ID;
  doc["agent_uid"]   = scannedAgentUID;
  doc["request_id"]  = formattedReq;

  String requestBody;
  serializeJson(doc, requestBody);

  Serial.println("[ESP32] Sending: " + requestBody);
  int httpCode = http.POST(requestBody);

  if (httpCode > 0) {
    String response = http.getString();
    Serial.println("[ESP32] Response (" + String(httpCode) + "): " + response);

    StaticJsonDocument<1024> resDoc;
    DeserializationError error = deserializeJson(resDoc, response);

    if (!error) {
      if (httpCode == 200) {
        String decision = resDoc["decision"] | "UNKNOWN";
        float riskPct   = resDoc["risk_percent"] | 0.0;
        JsonObject hw   = resDoc["hardware"]["hardware_commands"];
        String l1       = hw["lcd"]["line1"] | (formattedReq + ": " + decision);
        String l2       = hw["lcd"]["line2"] | (String(riskPct, 1) + "%");
        String ledColor = hw["led"]["color"] | "OFF";
        String buzzerMod = hw["buzzer"]["mode"] | "SILENT";

        // Display results
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print(l1.substring(0, 16));
        lcd.setCursor(0, 1);
        lcd.print(l2.substring(0, 16));

        // Actuate LEDs and Buzzer
        if (ledColor == "GREEN") {
          setAllLEDs(HIGH, LOW, LOW);
          beep(2, 100);
        } else if (ledColor == "YELLOW") {
          setAllLEDs(LOW, HIGH, LOW);
          beep(3, 150);
        } else if (ledColor == "RED") {
          setAllLEDs(LOW, LOW, HIGH);
          alarmBuzzer();
        }

        delay(4000);
      } else {
        // Error response (e.g. 403 or 404)
        JsonObject errHw = resDoc["detail"]["hardware"]["hardware_commands"];
        String l1 = errHw["lcd"]["line1"] | "DENIED";
        String l2 = errHw["lcd"]["line2"] | "ERROR";
        setAllLEDs(LOW, LOW, HIGH);
        lcd.clear();
        lcd.setCursor(0, 0); lcd.print(l1);
        lcd.setCursor(0, 1); lcd.print(l2);
        alarmBuzzer();
        delay(3000);
      }
    } else {
      showError("JSON PARSE ERR");
    }
  } else {
    showError("HTTP COMM ERR");
  }

  http.end();
}

void resetToStandby() {
  scannedAgentUID = "";
  enteredRequestID = "";
  setAllLEDs(LOW, LOW, LOW);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("TAP AGENT CARD");
  lcd.setCursor(0, 1);
  lcd.print("SYSTEM: READY");
}

void showError(String msg) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("ERROR / DENIED");
  lcd.setCursor(0, 1);
  lcd.print(msg);
  setAllLEDs(LOW, LOW, HIGH);
  beep(3, 200);
  delay(3000);
  resetToStandby();
}

void setAllLEDs(int g, int y, int r) {
  digitalWrite(LED_GREEN, g);
  digitalWrite(LED_YELLOW, y);
  digitalWrite(LED_RED, r);
}

void beep(int count, int ms) {
  for (int i = 0; i < count; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(ms);
    digitalWrite(BUZZER_PIN, LOW);
    if (i < count - 1) delay(ms);
  }
}

void alarmBuzzer() {
  for (int i = 0; i < 4; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(200);
    digitalWrite(BUZZER_PIN, LOW);
    delay(100);
  }
}
