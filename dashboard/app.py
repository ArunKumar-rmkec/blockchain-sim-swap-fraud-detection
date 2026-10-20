from pathlib import Path
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

API = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Blockchain-Secured SIM Swap Fraud Detection",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🛡️ Blockchain-Secured SIM Swap Fraud Detection System")
st.caption("College Capstone Project 2 • Hybrid XGBoost & Rule Engine • Solidity Smart Contract (SimSwapAudit.sol) • Virtual ESP32 Hardware Bridge")

# --- Backend Health Check ---
backend_online = False
try:
    health_resp = requests.get(f"{API}/health", timeout=2)
    if health_resp.ok:
        backend_online = True
except requests.RequestException:
    backend_online = False

if not backend_online:
    st.error("⚠️ Backend API is offline. Start it in PowerShell using: `uvicorn backend.main:app --reload`")
    st.info("Tip: From the project directory, run:\n```powershell\n..\\.venv\\Scripts\\python.exe -m uvicorn backend.main:app --port 8000\n```")
    st.stop()

# --- Initialize Session State ---
if "req_id_input" not in st.session_state:
    st.session_state["req_id_input"] = "REQ00001"
if "uid_input" not in st.session_state:
    st.session_state["uid_input"] = "A1B2C3D4"
if "hw_state" not in st.session_state:
    try:
        ts = requests.get(f"{API}/hardware/terminal-state", timeout=3).json()
        st.session_state["hw_state"] = {
            "lcd": ts["lcd"],
            "led": ts["led"],
            "buzzer": ts["buzzer"],
        }
    except Exception:
        st.session_state["hw_state"] = {
            "lcd": {"line1": "READY: TAP CARD", "line2": "SIM SWAP SYSTEM"},
            "led": {"color": "OFF"},
            "buzzer": {"mode": "SILENT", "beeps": 0},
        }

def set_preset(req_id: str, card_uid: str):
    st.session_state["req_id_input"] = req_id
    st.session_state["uid_input"] = card_uid
    st.session_state["do_eval"] = True

# --- Sidebar Controls ---
with st.sidebar:
    st.header("🎮 Simulation Controls")
    uid = st.selectbox(
        "Agent RFID Card UID",
        ["A1B2C3D4", "11223344", "DEMO1234", "INVALID_CARD_99"],
        key="uid_input",
        help="A1B2C3D4, 11223344, and DEMO1234 are authorized telecom agents. Any other UID will trigger hardware security rejection.",
    )
    request_id = st.text_input(
        "SIM Swap Request ID",
        key="req_id_input",
        help="e.g., REQ00001 (Clean), REQ00002 (Borderline), REQ00701 (High Risk Fraud)",
    ).strip().upper()
    
    col_sb1, col_sb2 = st.columns(2)
    with col_sb1:
        run_eval = st.button("🚀 Evaluate", type="primary", use_container_width=True)
    with col_sb2:
        reset_term = st.button("🔄 Reset HW", use_container_width=True)

    st.markdown("---")
    st.subheader("⚡ Quick Test Presets")
    st.button("🟢 REQ00001: Clean / Low Risk", on_click=set_preset, args=("REQ00001", "A1B2C3D4"), use_container_width=True)
    st.button("🟡 REQ00002: Borderline / Review", on_click=set_preset, args=("REQ00002", "A1B2C3D4"), use_container_width=True)
    st.button("🔴 REQ00701: High-Risk Fraud", on_click=set_preset, args=("REQ00701", "A1B2C3D4"), use_container_width=True)
    st.button("⛔ Rogue Card Test", on_click=set_preset, args=("REQ00001", "INVALID_CARD_99"), use_container_width=True)

    st.markdown("---")
    st.caption("Hardware: **Virtual ESP32 Bridge Active**")
    st.caption("Blockchain: **SimSwapAudit.sol (EVM)**")

# Handle Reset Terminal
if reset_term:
    try:
        r_reset = requests.post(f"{API}/hardware/terminal-reset", timeout=5)
        if r_reset.ok:
            st.session_state["hw_state"] = r_reset.json()
            st.toast("ESP32 Terminal reset to Standby!", icon="🔄")
    except Exception as e:
        st.sidebar.error(f"Reset failed: {e}")

# Handle Evaluation (syncs with API, blockchain anchor, and hardware terminal)
if run_eval or st.session_state.pop("do_eval", False):
    eval_req = st.session_state["req_id_input"]
    eval_card = st.session_state["uid_input"]
    try:
        r = requests.post(
            f"{API}/hardware/terminal-evaluate",
            json={"request_id": eval_req, "agent_uid": eval_card, "terminal_id": "ESP32_TERM_01"},
            timeout=20,
        )
        if r.ok:
            data = r.json()
            st.session_state["result"] = data
            st.session_state["hw_state"] = data.get("hardware", {}).get("hardware_commands", {})
            st.session_state["hw_last_resp"] = data.get("hardware", {})
        else:
            err_data = r.json()
            st.session_state["result"] = None
            if "detail" in err_data and isinstance(err_data["detail"], dict) and "hardware" in err_data["detail"]:
                st.session_state["hw_state"] = err_data["detail"]["hardware"].get("hardware_commands", {})
                st.session_state["hw_last_resp"] = err_data["detail"]["hardware"]
            st.error(f"⛔ Evaluation Rejected ({r.status_code}): {err_data.get('detail', {}).get('message', r.text)}")
    except requests.RequestException as e:
        st.error(f"API request failed: {e}")

# --- Main Dashboard Tabs ---
tab_eval, tab_hw, tab_audit, tab_perf = st.tabs([
    "🛡️ Risk Engine & SHAP",
    "📟 Hardware Terminal (ESP32)",
    "⛓️ Blockchain & Smart Contract",
    "📊 Model Performance & Data",
])

# ==============================================================================
# TAB 1: RISK ENGINE & SHAP EXPLAINABILITY
# ==============================================================================
with tab_eval:
    result = st.session_state.get("result")
    if result:
        st.subheader(f"Evaluation Decision: {result['request_id']}")
        
        # Decision Banner
        dec = result["decision"]
        if dec == "LOW RISK":
            st.success(f"### ✅ APPROVED: {dec} ({result['risk_percent']}%)")
        elif dec == "REVIEW":
            st.warning(f"### ⚠️ FLAGGED FOR REVIEW: {dec} ({result['risk_percent']}%)")
        else:
            st.error(f"### 🚨 BLOCKED: {dec} ({result['risk_percent']}%)")

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Risk Score", f"{result['risk_percent']}%")
        col_m2.metric("Decision", result["decision"])
        col_m3.metric("ML (XGBoost) Score", f"{result.get('ml_score', 0.0):.3f}")
        col_m4.metric("Rule Score", f"{result.get('rule_score', 0.0):.2f}")
        
        st.progress(float(result["risk_score"]))
        if result.get("model_used"):
            st.caption(f"Active Classifier: **{result['model_used']}** • Evaluated via ESP32 Hardware Bridge & Anchored to Smart Contract")

        # Blockchain Anchor Summary
        if result.get("blockchain"):
            bc = result["blockchain"]
            with st.container():
                st.markdown("#### ⛓️ On-Chain Smart Contract Receipt")
                col_b1, col_b2, col_b3, col_b4 = st.columns(4)
                col_b1.metric("On-Chain Status", bc.get("status", "CONFIRMED"))
                col_b2.metric("Block Height", f"#{bc.get('block_number', 'N/A')}")
                col_b3.metric("Gas Consumed", f"{bc.get('gas_used', 68420):,} gas")
                col_b4.metric("Smart Contract", "SimSwapAudit.sol")
                
                st.caption(f"**Transaction Hash**: `{bc.get('tx_hash', 'N/A')}`")
                st.caption(f"**Contract Address**: `{bc.get('contract_address', 'N/A')}` • **Validator**: `{bc.get('recorded_by', 'N/A')}`")

        st.markdown("#### 📋 Risk Analysis & Rule Triggers")
        for reason in result["reasons"]:
            st.write("- " + reason)

        # SHAP Model Explainability
        if result.get("shap") and isinstance(result["shap"], dict):
            shap_data = result["shap"]
            st.markdown("---")
            st.subheader("🔍 Model Explainability (SHAP Force Plot)")
            st.caption(
                "SHAP (SHapley Additive exPlanations) visualizes how each feature pushes the XGBoost "
                "risk prediction toward **High Risk (red / higher)** or toward **Legitimate (blue / lower)** "
                f"relative to the base log-odds (`{shap_data.get('base_value', 'N/A')}`)."
            )
            if shap_data.get("force_plot_html"):
                components.html(shap_data["force_plot_html"], height=140, scrolling=False)

            if shap_data.get("contributions"):
                with st.expander("📊 Feature Importance Breakdown (SHAP Impact Table)", expanded=True):
                    contrib_rows = []
                    for feat, impact in shap_data["contributions"].items():
                        direction = "Increases Risk (Fraud)" if impact > 0 else ("Decreases Risk (Legitimate)" if impact < 0 else "Neutral")
                        contrib_rows.append({
                            "Feature": feat,
                            "SHAP Impact (Log-Odds)": f"{impact:+.4f}",
                            "Direction": direction,
                        })
                    st.dataframe(pd.DataFrame(contrib_rows), use_container_width=True, hide_index=True)

        # Cryptographic Audit Record Details
        with st.expander("📜 Dual-Layer Audit Cryptographic Metadata", expanded=False):
            st.json({
                "local_hash_chain": result["audit"],
                "blockchain_smart_contract": result.get("blockchain", {}),
            })
    else:
        st.info("👈 Enter a Request ID and Agent RFID Card in the sidebar and click **'🚀 Evaluate'** or select a **Quick Test Preset**.")

# ==============================================================================
# TAB 2: HARDWARE TERMINAL (ESP32 LIVE SIMULATOR)
# ==============================================================================
with tab_hw:
    st.subheader("📟 Virtual ESP32 Hardware Terminal & Peripheral Emulation")
    st.caption("Emulates the physical ESP32 terminal (RC522 RFID, 4x4 Matrix Keypad, 16x2 HD44780 LCD, Tri-Color LEDs, and Piezo Buzzer).")

    hw_info = st.session_state.get("hw_state", {})
    lcd_info = hw_info.get("lcd", {"line1": "READY: TAP CARD", "line2": "SIM SWAP SYSTEM"})
    led_info = hw_info.get("led", {"color": "OFF"})
    buzzer_info = hw_info.get("buzzer", {"mode": "SILENT", "beeps": 0, "duration_ms": 0})

    line1_text = (lcd_info.get("line1", "READY: TAP CARD")[:16]).ljust(16)
    line2_text = (lcd_info.get("line2", "SIM SWAP SYSTEM")[:16]).ljust(16)
    active_color = led_info.get("color", "OFF")
    buzzer_mode = buzzer_info.get("mode", "SILENT")
    buzzer_beeps = buzzer_info.get("beeps", 0)

    # Styling helper for LEDs
    green_glow = "background: radial-gradient(circle, #00ff66 20%, #008833 70%); box-shadow: 0 0 25px #00ff66, 0 0 50px #00ff66;" if active_color == "GREEN" else "background: #003311; opacity: 0.35;"
    yellow_glow = "background: radial-gradient(circle, #ffdd00 20%, #bb9900 70%); box-shadow: 0 0 25px #ffdd00, 0 0 50px #ffdd00;" if active_color in ("YELLOW", "AMBER") else "background: #332b00; opacity: 0.35;"
    red_glow = "background: radial-gradient(circle, #ff2222 20%, #aa0000 70%); box-shadow: 0 0 25px #ff2222, 0 0 50px #ff2222;" if active_color == "RED" else "background: #330000; opacity: 0.35;"

    col_hw_left, col_hw_right = st.columns([1.3, 1])

    with col_hw_left:
        st.markdown("#### 🖥️ Physical Terminal Enclosure")
        
        terminal_html = f"""
        <div style="
            background: #1e222b;
            border: 6px solid #11141a;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.6);
            max-width: 540px;
            margin: 0 auto;
        ">
            <!-- Header Badge -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <span style="color: #8fa0b5; font-family: sans-serif; font-weight: bold; font-size: 13px; letter-spacing: 1px;">ESP32 SIM SWAP TERMINAL v1.0</span>
                <span style="background: #2a3342; color: #64ffda; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-family: monospace;">STATUS: {active_color}</span>
            </div>

            <!-- 16x2 Blue Backlit LCD Display -->
            <div style="
                background: #041936;
                border: 6px solid #0a0d14;
                border-radius: 8px;
                padding: 18px 22px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-weight: 900;
                font-size: 26px;
                color: #e0f4ff;
                text-shadow: 0 0 10px #38bdf8, 0 0 20px #0284c7;
                letter-spacing: 4px;
                line-height: 1.5;
                box-shadow: inset 0 0 25px rgba(2, 132, 199, 0.4), 0 4px 12px rgba(0,0,0,0.5);
                white-space: pre;
            ">
<div>{line1_text}</div>
<div>{line2_text}</div>
            </div>

            <!-- LED Indicator Lights & Buzzer Row -->
            <div style="display: flex; justify-content: space-around; align-items: center; margin-top: 24px; padding-top: 18px; border-top: 1px solid #2d3748;">
                <!-- GREEN LED -->
                <div style="text-align: center;">
                    <div style="width: 34px; height: 34px; border-radius: 50%; margin: auto; border: 2px solid #000; {green_glow}"></div>
                    <span style="font-size: 11px; font-weight: bold; color: {'#48bb78' if active_color == 'GREEN' else '#718096'}; font-family: monospace; display: block; margin-top: 6px;">APPROVED<br>(GPIO 25)</span>
                </div>
                <!-- YELLOW LED -->
                <div style="text-align: center;">
                    <div style="width: 34px; height: 34px; border-radius: 50%; margin: auto; border: 2px solid #000; {yellow_glow}"></div>
                    <span style="font-size: 11px; font-weight: bold; color: {'#ecc94b' if active_color in ('YELLOW', 'AMBER') else '#718096'}; font-family: monospace; display: block; margin-top: 6px;">REVIEW<br>(GPIO 26)</span>
                </div>
                <!-- RED LED -->
                <div style="text-align: center;">
                    <div style="width: 34px; height: 34px; border-radius: 50%; margin: auto; border: 2px solid #000; {red_glow}"></div>
                    <span style="font-size: 11px; font-weight: bold; color: {'#f56565' if active_color == 'RED' else '#718096'}; font-family: monospace; display: block; margin-top: 6px;">FRAUD<br>(GPIO 27)</span>
                </div>
                <!-- BUZZER -->
                <div style="text-align: center;">
                    <div style="
                        width: 38px;
                        height: 38px;
                        background: #2b303c;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 19px;
                        margin: auto;
                        border: 2px solid #1a202c;
                        color: {'#64ffda' if buzzer_mode != 'SILENT' else '#718096'};
                    ">🔊</div>
                    <span style="font-size: 11px; font-weight: bold; color: #a0aec0; font-family: monospace; display: block; margin-top: 6px;">BUZZER<br>({buzzer_mode})</span>
                </div>
            </div>
        </div>
        """
        components.html(terminal_html, height=400)
        st.markdown(f"**Acoustic Signal**: `{buzzer_mode}` • **Pulses**: `{buzzer_beeps} beeps` • **Pulse Duration**: `{buzzer_info.get('duration_ms', 0)} ms`")

    with col_hw_right:
        st.markdown("#### 🔌 Hardware Peripherals & Serial Ports")
        try:
            ports = requests.get(f"{API}/hardware/ports", timeout=3).json()
            if ports and ports[0]["device"] != "NONE":
                st.success(f"Detected {len(ports)} Active COM Port(s):")
                for p in ports:
                    st.code(f"{p['device']}: {p['description']}")
            else:
                st.info("ℹ️ No physical ESP32 USB COM port attached. Operating in **Virtual Serial Bridge Mode**.")
        except Exception:
            st.warning("Could not scan serial ports.")

        st.markdown("#### 📡 Protocol Exchange Inspector")
        last_hw = st.session_state.get("hw_last_resp")
        if last_hw:
            st.json(last_hw)
        else:
            st.caption("Evaluate a request to inspect the live JSON hardware payload transmitted to the ESP32.")

    with st.expander("📌 View Physical ESP32 Wiring Diagram & Pinouts"):
        st.markdown("""
        | Component | Interface / Pins | ESP32 GPIO Pin | Function |
        |---|---|---|---|
        | **RC522 RFID** | SPI (SDA, SCK, MOSI, MISO) | GPIO 5 (SS), 18 (SCK), 23 (MOSI), 19 (MISO), 22 (RST) | Telecom Agent Smart Card Authentication |
        | **4x4 Matrix Keypad** | Digital Rows & Columns | Rows: GPIO 13, 12, 14, 27 • Cols: GPIO 26, 25, 33, 32 | Customer SIM Swap Request ID Entry |
        | **I2C 16x2 LCD** | I2C (SDA, SCL) | GPIO 21 (SDA), GPIO 22 (SCL) | Real-time Decision & Risk Display |
        | **Tri-Color LEDs** | Digital Outputs | GPIO 25 (Green), GPIO 26 (Yellow), GPIO 27 (Red) | Instant Visual Risk Indicator |
        | **Piezo Buzzer** | PWM / Digital | GPIO 4 | Audio feedback (Success, Warning, Fraud Alarm) |
        """)

# ==============================================================================
# TAB 3: BLOCKCHAIN & SMART CONTRACT AUDIT LEDGER
# ==============================================================================
with tab_audit:
    st.subheader("⛓️ Blockchain Smart Contract & Cryptographic Audit Ledger")
    st.caption("Dual-Layer Integrity: Solidity Smart Contract (SimSwapAudit.sol) on EVM + Local SHA-256 Tamper-Evident Hash Chain.")

    # Network Status Ribbon
    try:
        bc_status = requests.get(f"{API}/blockchain/status", timeout=4).json()
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("Network Mode", bc_status.get("network_name", "EVM Emulation"))
        col_s2.metric("Contract Block Height", f"#{bc_status.get('current_block', 1000)}")
        col_s3.metric("On-Chain Records", bc_status.get("total_records", 0))
        col_s4.metric("EVM Node Status", "🟢 Connected" if bc_status.get("is_live_node") else "🟡 Emulation (Standby)")
        
        st.caption(f"**Contract Address**: `{bc_status.get('contract_address', 'N/A')}` • **Validator Node**: `{bc_status.get('validator_address', 'N/A')}`")
    except Exception as e:
        st.warning(f"Could not load blockchain status: {e}")

    # Sub-tabs for On-Chain, Local Chain, and Contract Source
    subtab_bc, subtab_local, subtab_sol = st.tabs([
        "📜 On-Chain Transactions",
        "🔗 Local SHA-256 Hash Chain",
        "💻 SimSwapAudit.sol Contract Source",
    ])

    with subtab_bc:
        st.markdown("#### 📜 Confirmed Smart Contract Audit Transactions")
        try:
            bc_records = requests.get(f"{API}/blockchain/records", timeout=5).json()
            if bc_records:
                bc_df = pd.DataFrame(bc_records)[::-1]
                cols_to_show = [c for c in ["record_index", "block_number", "request_id", "decision", "risk_percent", "tx_hash", "explanation_hash", "timestamp"] if c in bc_df.columns]
                st.dataframe(bc_df[cols_to_show], use_container_width=True, hide_index=True)
            else:
                st.info("No on-chain transactions yet. Evaluate a request to anchor the first block!")
        except Exception as e:
            st.error(f"Failed to fetch on-chain records: {e}")

        st.markdown("---")
        st.markdown("##### 🔍 On-Chain Cryptographic Digest Verification")
        st.caption("Verifies that the stored bytes32 explanation hash inside the SimSwapAudit smart contract matches the computed feature explanation.")
        
        v_col1, v_col2, v_col3 = st.columns([1, 2, 1])
        with v_col1:
            rec_count = len(bc_records) if 'bc_records' in locals() and bc_records else 1
            verify_idx = st.number_input("Record Index to Verify", min_value=0, max_value=max(0, rec_count - 1), value=0, step=1)
        with v_col2:
            default_h = bc_records[verify_idx].get("explanation_hash", "") if 'bc_records' in locals() and bc_records and verify_idx < len(bc_records) else ""
            input_hash = st.text_input("Expected Explanation Hash (SHA-256)", value=default_h)
        with v_col3:
            st.write("")
            st.write("")
            check_bc_btn = st.button("Verify On-Chain", type="primary", use_container_width=True)

        if check_bc_btn:
            try:
                v_res = requests.post(f"{API}/blockchain/verify", json={"record_index": verify_idx, "expected_hash": input_hash}, timeout=5).json()
                if v_res.get("verified"):
                    st.success(f"✅ VERIFIED ON-CHAIN: Record #{verify_idx} explanation digest matches smart contract storage exactly!")
                else:
                    st.error(f"❌ TAMPER DETECTED: Digest does NOT match on-chain record at index #{verify_idx}!")
            except Exception as e:
                st.error(f"Verification request failed: {e}")

    with subtab_local:
        st.markdown("#### 🔗 Off-Chain High-Speed SHA-256 Hash Chain")
        st.caption("Local tamper-evident cryptographic ledger with block-to-block previous hash linkage.")
        col_aud1, col_aud2 = st.columns([1, 3])
        with col_aud1:
            verify_btn = st.button("🔍 Verify Hash Chain Integrity", type="primary", use_container_width=True)

        try:
            audit_data = requests.get(f"{API}/audit", timeout=5).json()
            if verify_btn:
                if audit_data["valid"]:
                    st.success(f"✅ Hash Chain Verified! {audit_data['message']} (Total Blocks: {audit_data['count']})")
                else:
                    st.error(f"❌ TAMPER DETECTED: {audit_data['message']}")

            st.metric("Total Immutable Blocks", audit_data["count"])
            records = audit_data.get("records", [])
            if records:
                audit_df = pd.DataFrame(records)[::-1]
                st.dataframe(
                    audit_df[["index", "timestamp", "request_id", "decision", "risk_score", "agent_uid", "record_hash", "prev_hash"]],
                    use_container_width=True,
                    hide_index=True,
                )
        except Exception as e:
            st.error(f"Failed to load audit ledger: {e}")

    with subtab_sol:
        st.markdown("#### 📄 Solidity Smart Contract: `SimSwapAudit.sol`")
        st.caption("Solidity ^0.8.20 • Deployable to Ethereum, Polygon, Arbitrum, or local Anvil/Ganache nodes.")
        sol_file = Path(__file__).resolve().parent.parent / "blockchain" / "contracts" / "SimSwapAudit.sol"
        if sol_file.exists():
            st.code(sol_file.read_text(encoding="utf-8"), language="solidity")
        else:
            st.info("Contract file path not found.")

# ==============================================================================
# TAB 4: MODEL PERFORMANCE & SYNTHETIC DATA
# ==============================================================================
with tab_perf:
    st.subheader("📊 Machine Learning Performance & Synthetic Dataset")
    
    col_p1, col_p2 = st.columns([1.2, 1])

    with col_p1:
        st.markdown("#### 🎯 Held-out Test Set Metrics")
        try:
            m = requests.get(f"{API}/metrics", timeout=20).json()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Accuracy", f"{m['accuracy'] * 100:.1f}%")
            c2.metric("Precision", f"{m['precision'] * 100:.1f}%")
            c3.metric("Recall", f"{m['recall'] * 100:.1f}%")
            c4.metric("F1 Score", f"{m['f1'] * 100:.1f}%")
            
            st.caption(f"Model: **{m.get('model_name', 'Classifier')}** (Train Records: {m.get('train_records', 'N/A')}, Test Records: {m.get('test_records', 'N/A')})")

            if "confusion_matrix" in m:
                cm = m["confusion_matrix"]
                cm_df = pd.DataFrame(
                    [[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]],
                    columns=["Pred: Legitimate (0)", "Pred: Fraud (1)"],
                    index=["Actual: Legitimate (0)", "Actual: Fraud (1)"],
                )
                st.markdown("**Confusion Matrix (Held-out Test Set)**")
                st.dataframe(cm_df, use_container_width=True)
            st.caption(f"ℹ️ {m.get('note', '')}")
        except Exception as e:
            st.warning(f"Could not load metrics: {e}")

    with col_p2:
        st.markdown("#### 🔬 Telecom Risk Feature Weights")
        st.markdown("""
        | Feature Name | Description | Evaluation Weight |
        |---|---|---|
        | `repeat_requests_24h` | Number of previous swap requests in 24 hours | High (Rule + ML) |
        | `device_change` | Subscriber device IMEI changed | High (Rule + ML) |
        | `location_mismatch` | Current cell tower differs from home location | Medium-High |
        | `subscriber_mismatch` | ID / KYC name / DOB mismatch | Critical (Immediate Rule Override) |
        | `hours_since_last_request` | Elapsed time since last SIM modification | Dynamic Decay |
        """)

    st.markdown("---")
    st.markdown("#### 📂 Synthetic Telecom Dataset Records (First 100)")
    try:
        req_df = pd.DataFrame(requests.get(f"{API}/requests", timeout=10).json())
        st.dataframe(req_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"Could not load requests: {e}")
