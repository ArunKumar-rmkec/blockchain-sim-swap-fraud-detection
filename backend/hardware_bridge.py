"""
Hardware Bridge & Protocol Adapter for ESP32 Terminal
=====================================================
Translates SIM swap fraud evaluation decisions into physical/simulated
ESP32 hardware control signals:
- I2C 16x2 / 20x4 LCD Display lines
- Tri-color status LEDs (Green, Yellow/Amber, Red)
- Piezo Buzzer tone patterns
- Serial UART and Network REST protocol handling
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import json
import logging

logger = logging.getLogger("hardware_bridge")


@dataclass
class LCDDisplayState:
    line1: str = "READY: TAP CARD"
    line2: str = "SIM SWAP SYSTEM"


@dataclass
class LEDState:
    color: str = "OFF"  # GREEN, YELLOW, RED, OFF
    green: int = 0
    yellow: int = 0
    red: int = 0


@dataclass
class BuzzerState:
    mode: str = "SILENT"  # SUCCESS, WARN, ALERT, KEYPRESS, SILENT
    beeps: int = 0
    duration_ms: int = 0


@dataclass
class TerminalHardwareState:
    terminal_id: str = "ESP32_TERM_01"
    lcd: LCDDisplayState = field(default_factory=LCDDisplayState)
    led: LEDState = field(default_factory=LEDState)
    buzzer: BuzzerState = field(default_factory=BuzzerState)
    last_event_time: Optional[str] = None
    last_request_id: Optional[str] = None
    last_decision: Optional[str] = None


# Global in-memory state of the active terminal
_ACTIVE_TERMINAL = TerminalHardwareState()


def get_terminal_state() -> Dict[str, Any]:
    """Returns the current simulated hardware terminal state."""
    return {
        "terminal_id": _ACTIVE_TERMINAL.terminal_id,
        "lcd": {
            "line1": _ACTIVE_TERMINAL.lcd.line1,
            "line2": _ACTIVE_TERMINAL.lcd.line2,
        },
        "led": {
            "color": _ACTIVE_TERMINAL.led.color,
            "green": _ACTIVE_TERMINAL.led.green,
            "yellow": _ACTIVE_TERMINAL.led.yellow,
            "red": _ACTIVE_TERMINAL.led.red,
        },
        "buzzer": {
            "mode": _ACTIVE_TERMINAL.buzzer.mode,
            "beeps": _ACTIVE_TERMINAL.buzzer.beeps,
            "duration_ms": _ACTIVE_TERMINAL.buzzer.duration_ms,
        },
        "last_event_time": _ACTIVE_TERMINAL.last_event_time,
        "last_request_id": _ACTIVE_TERMINAL.last_request_id,
        "last_decision": _ACTIVE_TERMINAL.last_decision,
    }


def reset_terminal_state(terminal_id: str = "ESP32_TERM_01") -> Dict[str, Any]:
    """Resets the hardware terminal to idle standby."""
    global _ACTIVE_TERMINAL
    _ACTIVE_TERMINAL = TerminalHardwareState(terminal_id=terminal_id)
    return get_terminal_state()


def format_hardware_response(
    decision: str,
    risk_percent: float,
    request_id: str,
    audit_hash: str = "",
    status_override: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Translates an evaluation decision or error into concrete ESP32 hardware signals.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    req_trunc = request_id[:8].upper()

    if error_message:
        status = status_override or "ERROR"
        line1 = "ERROR / DENIED"[:16]
        line2 = error_message[:16]
        led = LEDState(color="RED", red=1)
        buzzer = BuzzerState(mode="ALERT", beeps=3, duration_ms=250)

    elif decision == "LOW RISK":
        status = "APPROVED"
        line1 = f"{req_trunc}: LOW"[:16].ljust(16)
        line2 = f"APPROVED {risk_percent:.1f}%"[:16].ljust(16)
        led = LEDState(color="GREEN", green=1)
        buzzer = BuzzerState(mode="SUCCESS", beeps=2, duration_ms=100)

    elif decision == "REVIEW":
        status = "FLAGGED_REVIEW"
        line1 = f"{req_trunc}: REVIEW"[:16].ljust(16)
        line2 = f"HOLD {risk_percent:.1f}%"[:16].ljust(16)
        led = LEDState(color="YELLOW", yellow=1)
        buzzer = BuzzerState(mode="WARN", beeps=3, duration_ms=150)

    elif decision == "HIGH RISK":
        status = "REJECTED_FRAUD"
        line1 = f"{req_trunc}: FRAUD"[:16].ljust(16)
        line2 = f"BLOCKED {risk_percent:.1f}%"[:16].ljust(16)
        led = LEDState(color="RED", red=1)
        buzzer = BuzzerState(mode="ALERT", beeps=5, duration_ms=400)

    else:
        status = "UNKNOWN"
        line1 = f"{req_trunc}: {decision[:8]}"[:16]
        line2 = f"RISK {risk_percent:.1f}%"[:16]
        led = LEDState(color="YELLOW", yellow=1)
        buzzer = BuzzerState(mode="WARN", beeps=1, duration_ms=100)

    # Update global active terminal state
    _ACTIVE_TERMINAL.lcd = LCDDisplayState(line1=line1.strip(), line2=line2.strip())
    _ACTIVE_TERMINAL.led = led
    _ACTIVE_TERMINAL.buzzer = buzzer
    _ACTIVE_TERMINAL.last_event_time = now_iso
    _ACTIVE_TERMINAL.last_request_id = request_id
    _ACTIVE_TERMINAL.last_decision = decision

    return {
        "status": status,
        "decision": decision,
        "risk_percent": risk_percent,
        "request_id": request_id,
        "audit_hash": audit_hash,
        "hardware_commands": {
            "lcd": {
                "line1": line1.strip(),
                "line2": line2.strip(),
            },
            "led": {
                "color": led.color,
                "pin_green": led.green,
                "pin_yellow": led.yellow,
                "pin_red": led.red,
            },
            "buzzer": {
                "mode": buzzer.mode,
                "beeps": buzzer.beeps,
                "duration_ms": buzzer.duration_ms,
            },
        },
        "timestamp": now_iso,
    }


def list_serial_ports() -> List[Dict[str, str]]:
    """Returns a list of detected physical or virtual COM serial ports on Windows."""
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        return [{"device": p.device, "description": p.description, "hwid": p.hwid} for p in ports]
    except Exception as e:
        return [{"device": "NONE", "description": f"Failed to list COM ports: {e}", "hwid": ""}]
