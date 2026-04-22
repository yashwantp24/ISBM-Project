import streamlit as st
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from streamlit_autorefresh import st_autorefresh

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from Notifications.notifs import check_notifications
from database.opc_client import OPCClient
from database.tags import MACHINES, OPC_SERVER_URL

st.set_page_config(page_title="Plant TV", layout="wide", initial_sidebar_state="collapsed")

if "opc_client" not in st.session_state:
    try:
        st.session_state.opc_client = OPCClient(OPC_SERVER_URL)
        st.session_state.opc_error = None
    except Exception as e:
        st.session_state.opc_client = None
        st.session_state.opc_error = str(e)

client = st.session_state.opc_client
opc_error = st.session_state.get("opc_error")

MACHINE_LIST = [58, 59, 60, 61]

CHILLER_TEMPS = {"Chiller 1": 12.4, "Chiller 2": 11.8, "Chiller 3": 13.1}
CHILLER_LEVELS = {"Chiller 1": 82, "Chiller 2": 76, "Chiller 3": 88}
COMPRESSORS = {"HP Compressor": ("28.6", "bar"), "LP Compressor": ("7.2", "bar")}


st.markdown("""
<style>
header[data-testid="stHeader"] {display: none;}
[data-testid="stSidebar"] {display: none;}
[data-testid="collapsedControl"] {display: none;}
.block-container {padding: 1rem 1.5rem !important; max-width: 100% !important;}
#MainMenu, footer {visibility: hidden;}
body {background: #0E1117;}

.kiosk-title {
    text-align: center;
    color: #FFFFFF;
    font-size: 2.2rem;
    font-weight: 700;
    margin: 0 0 0.6rem 0;
    letter-spacing: 2px;
}

.alerts-panel {
    background: #161B22;
    border-radius: 14px;
    padding: 1rem;
    height: 88vh;
    overflow: hidden;
    position: relative;
    border: 2px solid #FF4B4B;
}
.alerts-header {
    color: #FF4B4B;
    font-size: 1.8rem;
    font-weight: 700;
    text-align: center;
    margin-bottom: 0.8rem;
    text-transform: uppercase;
}
.alerts-scroll {
    height: calc(88vh - 4rem);
    overflow: hidden;
    position: relative;
    mask-image: linear-gradient(to bottom, transparent 0%, black 5%, black 95%, transparent 100%);
}
.alerts-track {
    animation: scrollUp linear infinite;
}
@keyframes scrollUp {
    0%   { transform: translateY(0); }
    100% { transform: translateY(-50%); }
}
.alert-card {
    background: rgba(255, 75, 75, 0.12);
    border-left: 6px solid #FF4B4B;
    border-radius: 10px;
    padding: 0.9rem 1rem;
    margin-bottom: 0.8rem;
    color: #FFFFFF;
    font-size: 1.25rem;
}
.alert-machine {
    color: #FFC107;
    font-weight: 700;
    font-size: 1.4rem;
    margin-bottom: 0.2rem;
}
.alert-msg { color: #EAEAEA; line-height: 1.3; }
.alert-empty {
    color: #1DB954;
    font-size: 1.8rem;
    text-align: center;
    padding-top: 30vh;
    font-weight: 700;
}

.tile-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1rem;
}
.tile {
    background: #161B22;
    border-radius: 14px;
    padding: 1.2rem 1rem;
    border: 2px solid #1DB954;
    text-align: center;
    color: #FFFFFF;
}
.tile.amber { border-color: #FFC107; }
.tile.red { border-color: #FF4B4B; }
.tile-label {
    font-size: 1.1rem;
    color: #9BA3AF;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 0.4rem;
}
.tile-value {
    font-size: 3rem;
    font-weight: 800;
    color: #1DB954;
    line-height: 1;
}
.tile.amber .tile-value { color: #FFC107; }
.tile.red .tile-value { color: #FF4B4B; }
.tile-unit {
    font-size: 1.3rem;
    color: #9BA3AF;
    margin-left: 0.3rem;
}
.section-label {
    color: #9BA3AF;
    font-size: 1.2rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin: 0.3rem 0 0.6rem 0.2rem;
}
</style>
""", unsafe_allow_html=True)


def read_machine_alerts(machine):
    try:
        data = client.read_machine(machine, MACHINES) or {}
        alerts, _ = check_notifications(machine, data, cycle_limits={})
        return machine, alerts or []
    except Exception:
        return machine, []


@st.cache_data(ttl=3)
def get_all_alerts(_client, machines_tuple):
    results = []
    if _client is None:
        return results
    with ThreadPoolExecutor(max_workers=min(len(machines_tuple), 8)) as ex:
        futures = {ex.submit(read_machine_alerts, m): m for m in machines_tuple}
        for fut in as_completed(futures):
            try:
                machine, alerts = fut.result()
                for a in alerts:
                    results.append((machine, str(a)))
            except Exception:
                pass
    return results


st.markdown("<div class='kiosk-title'>AXIUM PACKAGING — PLANT 1</div>", unsafe_allow_html=True)

if opc_error:
    st.markdown(
        f"<div style='background:#FF4B4B;color:#fff;padding:0.6rem 1rem;"
        f"border-radius:8px;text-align:center;font-weight:700;margin-bottom:0.6rem;'>"
        f"⚠ OPC UA DISCONNECTED — {OPC_SERVER_URL} — {opc_error}</div>",
        unsafe_allow_html=True,
    )
elif client is not None:
    st.markdown(
        f"<div style='color:#1DB954;text-align:center;font-size:0.9rem;"
        f"margin-bottom:0.4rem;'>● OPC UA connected — {OPC_SERVER_URL}</div>",
        unsafe_allow_html=True,
    )

left, right = st.columns([40, 60], gap="small")

with left:
    alerts = get_all_alerts(client, tuple(MACHINE_LIST))

    if not alerts:
        st.markdown(
            "<div class='alerts-panel'>"
            "<div class='alerts-header'>Active Alerts</div>"
            "<div class='alert-empty'>✓ All Systems Normal</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        cards = ""
        for machine, msg in alerts:
            cards += (
                f"<div class='alert-card'>"
                f"<div class='alert-machine'>Machine {machine}</div>"
                f"<div class='alert-msg'>{msg}</div>"
                f"</div>"
            )
        duration = max(12, len(alerts) * 4)
        doubled = cards + cards
        needs_scroll = len(alerts) >= 4
        track_style = (
            f"animation-duration: {duration}s;" if needs_scroll else "animation: none;"
        )
        inner = doubled if needs_scroll else cards
        st.markdown(
            f"<div class='alerts-panel'>"
            f"<div class='alerts-header'>Active Alerts ({len(alerts)})</div>"
            f"<div class='alerts-scroll'>"
            f"<div class='alerts-track' style='{track_style}'>{inner}</div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

with right:
    st.markdown("<div class='section-label'>Chiller Temperatures (°C)</div>", unsafe_allow_html=True)
    tiles = ""
    for name, val in CHILLER_TEMPS.items():
        tiles += (
            f"<div class='tile'>"
            f"<div class='tile-label'>{name}</div>"
            f"<div class='tile-value'>{val}<span class='tile-unit'>°C</span></div>"
            f"</div>"
        )
    st.markdown(f"<div class='tile-grid'>{tiles}</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-label'>Compressor Pressure</div>", unsafe_allow_html=True)
    tiles = ""
    for name, (val, unit) in COMPRESSORS.items():
        tiles += (
            f"<div class='tile' style='grid-column: span 1;'>"
            f"<div class='tile-label'>{name}</div>"
            f"<div class='tile-value'>{val}<span class='tile-unit'>{unit}</span></div>"
            f"</div>"
        )
    st.markdown(
        f"<div class='tile-grid' style='grid-template-columns: 1fr 1fr;'>{tiles}</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='section-label'>Chiller Water Level (%)</div>", unsafe_allow_html=True)
    tiles = ""
    for name, val in CHILLER_LEVELS.items():
        cls = "tile"
        if val < 50: cls = "tile red"
        elif val < 70: cls = "tile amber"
        tiles += (
            f"<div class='{cls}'>"
            f"<div class='tile-label'>{name}</div>"
            f"<div class='tile-value'>{val}<span class='tile-unit'>%</span></div>"
            f"</div>"
        )
    st.markdown(f"<div class='tile-grid'>{tiles}</div>", unsafe_allow_html=True)


st_autorefresh(interval=10000, key="tv_kiosk_refresh")
