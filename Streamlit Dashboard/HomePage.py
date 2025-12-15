import streamlit as st
from pathlib import Path
import sys
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from Notifications.notifs import check_notifications
from database.opc_client import OPCClient
from database.tags import MACHINES, OPC_SERVER_URL

if "opc_client" not in st.session_state:
    st.session_state.opc_client = OPCClient(OPC_SERVER_URL)

client = st.session_state.opc_client


st.markdown("""
<style>
.card-title .material-icons { 
    font-size: 30px; 
    color: #1DB954; 
}

.machine-grid { 
    display: flex; 
    flex-wrap: wrap; 
    gap: 12px 18px; 
}

.machine-rect { 
    width: 60px; 
    height: 40px; 
    border-radius: 10px; 
    border: 2px solid #1DB954; 
    display: flex; 
    justify-content: center; 
    align-items: center; 
    color: #1DB954; 
    font-weight: bold; 
    font-size: 18px; 
    cursor: pointer; 
    background-color: rgba(29, 185, 84, 0.1); 
    transition: all 0.3s ease; 
}

.machine-rect.alert { 
    border-color: #FFC107; 
    color: #FFC107; 
    background-color: rgba(255, 193, 7, 0.3); 
}

.machine-rect.off { 
    border-color: #FF4B4B; 
    color: #FF4B4B; 
    background-color: rgba(255, 75, 75, 0.1); 
}

.machine-rect:hover { 
    transform: scale(1.1); 
}
</style>
""", unsafe_allow_html=True)



st.markdown("<h1 style='text-align:center;'>Axium Packaging</h1>", unsafe_allow_html=True)
st.markdown("<h2 style='text-align:center;'>Plant 1</h2>", unsafe_allow_html=True)


machines = [60]


status_class_map = {
    2: "machine-rect alert",   # Alerts exist
    1: "machine-rect",         # Machine running
    0: "machine-rect off"      # Machine off
}


machine_status = {}

for machine in machines:

    machine_data = client.read_machine(machine, MACHINES) or {}

    
    alerts,alert_tag = check_notifications(machine, machine_data, cycle_limits={})

    if alert_tag==1:
        status = 2 
    else:
        auto_cycle = machine_data.get("Auto Cycle", 0)
        status = 1 if auto_cycle == 1 else 0

    machine_status[machine] = status


html = """
<div class="card">
    </div>
    <div class="machine-grid">
"""

for machine in machines:
    css_class = status_class_map[machine_status[machine]]
    html += f'<div class="{css_class}">{machine}</div>'

html += """
    </div>
</div>
"""

st.markdown(html, unsafe_allow_html=True)
st_autorefresh(interval=5000, key="refresh")
