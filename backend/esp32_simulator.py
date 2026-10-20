"""
Virtual ESP32 Hardware Simulator
================================
Simulates an ESP32 micro-controller board equipped with:
- RC522 RFID Card Reader (SPI)
- 4x4 Matrix Keypad
- 16x2 I2C Character LCD with backlight
- Tri-color Status LEDs (Green, Yellow, Red)
- Active Piezo Buzzer

Runs 100% in software on Windows, connecting to the FastAPI backend
via HTTP or direct protocol bridge.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import json
import sys
import time
import requests

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_API_URL = "http://127.0.0.1:8000"


@dataclass
class SimulatedTerminalClient:
    api_url: str = DEFAULT_API_URL
    terminal_id: str = "ESP32_SIMULATOR_01"

    def tap_and_evaluate(
        self,
        agent_uid: str,
        request_id: str,
        timeout: int = 5,
    ) -> Dict[str, Any]:
        """
        Simulates tapping an RFID card and entering a Request ID on the keypad,
        sending the event to the backend and receiving hardware control signals.
        """
        payload = {
            "terminal_id": self.terminal_id,
            "agent_uid": agent_uid,
            "request_id": request_id,
        }

        try:
            resp = requests.post(
                f"{self.api_url}/hardware/terminal-evaluate",
                json=payload,
                timeout=timeout,
            )
            if resp.ok:
                data = resp.json()
                return {"success": True, "status_code": resp.status_code, "data": data}
            else:
                err_detail = resp.json().get("detail", {})
                return {"success": False, "status_code": resp.status_code, "error": err_detail}
        except requests.RequestException as e:
            return {"success": False, "status_code": 0, "error": f"Connection error: {e}"}

    def reset_display(self) -> Dict[str, Any]:
        """Resets the terminal state back to standby."""
        try:
            resp = requests.post(f"{self.api_url}/hardware/terminal-reset", timeout=3)
            return resp.json() if resp.ok else {}
        except Exception:
            return {}

    def get_current_display(self) -> Dict[str, Any]:
        """Queries the current virtual LCD and LED state."""
        try:
            resp = requests.get(f"{self.api_url}/hardware/terminal-state", timeout=3)
            return resp.json() if resp.ok else {}
        except Exception:
            return {}


def render_ascii_terminal(
    line1: str,
    line2: str,
    led_color: str,
    buzzer_mode: str,
    request_id: str = "",
    agent_uid: str = "",
) -> str:
    """Formats a visual ASCII rendering of the ESP32 physical terminal."""
    l1 = line1[:16].ljust(16)
    l2 = line2[:16].ljust(16)

    led_icon = {
        "GREEN": "🟢 [GREEN: APPROVED]",
        "YELLOW": "🟡 [YELLOW: REVIEW]",
        "RED": "🔴 [RED: BLOCKED/ALERT]",
        "OFF": "⚪ [LED: OFF]",
    }.get(led_color.upper(), "⚪ [LED: OFF]")

    buzzer_icon = {
        "SUCCESS": "🔊 2 Quick Beeps (Approved)",
        "WARN": "⚠️ 3 Warning Pulses (Review Required)",
        "ALERT": "🚨 Siren Pulsing (High-Risk Fraud Blocked)",
        "SILENT": "🔇 Silent",
    }.get(buzzer_mode.upper(), "🔇 Silent")

    return f"""
    ┌───────────────────────────────────────────┐
    │       ESP32 SIM SWAP FRAUD TERMINAL       │
    ├───────────────────────────────────────────┤
    │  Agent RFID : {agent_uid.ljust(26)}  │
    │  Keypad REQ : {request_id.ljust(26)}  │
    ├───────────────────────────────────────────┤
    │  I2C LCD 16x2 Display:                    │
    │  ┌────────────────────┐                   │
    │  │ {l1}   │  [Blue Backlight]  │
    │  │ {l2}   │                   │
    │  └────────────────────┘                   │
    ├───────────────────────────────────────────┤
    │  LED Indicator : {led_icon.ljust(24)} │
    │  Buzzer Output : {buzzer_icon.ljust(24)} │
    └───────────────────────────────────────────┘
    """


def run_interactive_simulation():
    """CLI interactive test runner for the simulated hardware terminal."""
    client = SimulatedTerminalClient()
    print("=" * 60)
    print("ESP32 SIM Swap Hardware Terminal Simulator")
    print("Connecting to backend at:", DEFAULT_API_URL)
    print("=" * 60)

    # Test health first
    try:
        r = requests.get(f"{DEFAULT_API_URL}/health", timeout=3)
        if not r.ok:
            print("ERROR: FastAPI backend is not running at", DEFAULT_API_URL)
            sys.exit(1)
    except Exception as e:
        print("ERROR: Could not connect to backend:", e)
        print("Please start the backend with: uvicorn backend.main:app --port 8000")
        sys.exit(1)

    print("\nBackend connected successfully!")
    print("\nPreset Test Scenarios:")
    print("  1. Normal Customer Request (REQ00001, Agent: A1B2C3D4)")
    print("  2. Suspicious SIM Storm Attack (REQ00701, Agent: A1B2C3D4)")
    print("  3. Borderline Phone Upgrade (REQ00901, Agent: DEMO1234)")
    print("  4. Unauthorized Agent Card (REQ00001, Agent: UNKNOWN_CARD)")
    print("  5. Unknown Request ID (REQ99999, Agent: 11223344)")

    choice = input("\nSelect scenario (1-5) or enter 'custom' [1]: ").strip() or "1"

    if choice == "1":
        agent, req = "A1B2C3D4", "REQ00001"
    elif choice == "2":
        agent, req = "A1B2C3D4", "REQ00701"
    elif choice == "3":
        agent, req = "DEMO1234", "REQ00901"
    elif choice == "4":
        agent, req = "UNKNOWN_CARD", "REQ00001"
    elif choice == "5":
        agent, req = "11223344", "REQ99999"
    else:
        agent = input("Enter Agent UID [A1B2C3D4]: ").strip() or "A1B2C3D4"
        req = input("Enter Request ID [REQ00001]: ").strip() or "REQ00001"

    print(f"\n[ESP32] Simulating RC522 RFID Card Scan: UID '{agent}'")
    time.sleep(0.4)
    print(f"[ESP32] Simulating 4x4 Keypad Entry: ID '{req}'")
    time.sleep(0.4)
    print("[ESP32] Transmitting HTTP POST to backend...")

    res = client.tap_and_evaluate(agent_uid=agent, request_id=req)

    if res["success"]:
        data = res["data"]
        hw = data.get("hardware", {}).get("hardware_commands", {})
        l1 = hw.get("lcd", {}).get("line1", "")
        l2 = hw.get("lcd", {}).get("line2", "")
        led = hw.get("led", {}).get("color", "OFF")
        buzzer = hw.get("buzzer", {}).get("mode", "SILENT")

        print(render_ascii_terminal(l1, l2, led, buzzer, request_id=req, agent_uid=agent))
        print("Decision:", data["decision"], f"({data['risk_percent']}%)")
        print("Reasons:")
        for r in data["reasons"]:
            print(f"  - {r}")
        print("Audit Record Hash:", data.get("audit", {}).get("record_hash"))
    else:
        err = res.get("error", {})
        hw = err.get("hardware", {}).get("hardware_commands", {})
        l1 = hw.get("lcd", {}).get("line1", "ERROR")
        l2 = hw.get("lcd", {}).get("line2", "DENIED")
        led = hw.get("led", {}).get("color", "RED")
        buzzer = hw.get("buzzer", {}).get("mode", "ALERT")

        print(render_ascii_terminal(l1, l2, led, buzzer, request_id=req, agent_uid=agent))
        print(f"FAILED ({res['status_code']}):", err.get("message", err))


if __name__ == "__main__":
    run_interactive_simulation()
