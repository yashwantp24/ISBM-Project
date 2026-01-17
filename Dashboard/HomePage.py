import streamlit as st
from pathlib import Path
import sys
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def read_machine_status(machine):
    """Read status for a single machine (runs in parallel)"""
    try:
        machine_data = client.read_machine(machine, MACHINES) or {}
        alerts, alert_tag = check_notifications(machine, machine_data, cycle_limits={})
        
        if alert_tag == 1:
            return machine, 2  # Alert status
        else:
            auto_cycle = machine_data.get("Auto Cycle")
            return machine, (1 if auto_cycle == 1 else 0)  
    except Exception as e:
        st.error(f"Error reading machine {machine}: {e}")
        return machine



@st.cache_data(ttl=3)  # Cache
def get_all_machine_statuses(_client, machines_tuple):
    """
    Fetch all machine statuses in parallel with caching
    Note: _client is prefixed with underscore to exclude from hashing
    """
    machine_status = {}
    
    # Read all machines in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(len(machines_tuple), 8)) as executor:
        # Submit all tasks
        futures = {executor.submit(read_machine_status, machine): machine 
                for machine in machines_tuple}
        
        # Collect results as they complete
        for future in as_completed(futures):
            try:
                machine, status = future.result()
                machine_status[machine] = status
            except Exception as e:
                machine = futures[future]
                st.error(f"Failed to get status for machine {machine}: {e}")
                machine_status[machine] = 0  # Default to off
    
    return machine_status


# Define machines
machines = [58,59,60,61]

# Status CSS class mapping
status_class_map = {
    2: "machine-rect alert",   # Alerts exist
    1: "machine-rect",          # Machine running
    0: "machine-rect off"       # Machine off
}

# Get machine statuses with parallel reads and caching
with st.spinner('Loading machine statuses...'):
    machine_status = get_all_machine_statuses(client, tuple(machines))


print(machine_status)
# Build HTML for machine grid
html = """
<div class="card">
    <div class="machine-grid">
"""

for machine in machines:
    css_class = status_class_map.get(machine_status.get(machine, 0), "machine-rect off")
    html += f'<div class="{css_class}">{machine}</div>'

html += """
    </div>
</div>
"""

st.markdown(html, unsafe_allow_html=True)


st_autorefresh(interval=40000, key="refresh")