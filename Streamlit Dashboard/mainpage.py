import streamlit as st

# --- CSS ---
st.markdown("""
<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">

<style>

.card {
    background: #111;
    border-radius: 15px;
    padding: 25px;
    margin-top: 25px;
    box-shadow: 0px 0px 12px rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.1);
    width: fit-content;
}

.card-title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 26px;
    font-weight: 700;
    color: white;
    margin-bottom: 20px;
}

.card-title .material-icons {
    font-size: 30px;
    color: #1DB954;
}

/* Machine grid layout */
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
    background-color: rgba(255, 193, 7, 0.1);
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

# Data
machines = [1, 18, 19, 22, 23, 24, 25, 26, 43, 48, 49, 50, 51, 57, 58, 59, 60, 61, 62, 67, 68]

machine_status = {
    1: "1", 18: "alert", 19: "0", 22: "0", 23: "1",
    24: "1", 25: "alert", 26: "1", 43: "0", 48:"1", 49: "1",
    50: "alert", 51: "1", 57: "1", 58: "0", 59: "1",
    60: "alert", 61: "1", 62: "1", 67: "0", 68: "1"
}

status_class_map = {
    "1": "machine-rect",
    "alert": "machine-rect alert",
    "0": "machine-rect off"
}

# Headers
st.markdown("<h1 style='text-align:center;'>Axium Packaging</h1>", unsafe_allow_html=True)
st.markdown("<h2 style='text-align:center;'>Plant 1</h2>", unsafe_allow_html=True)

# --- FULL CARD BLOCK ---
html = """
<div class="card">
    <div class="card-title">
        <span class="material-icons">factory</span>
        Machine Status
    </div>
    <div class="machine-grid">
"""

# Add machines
for machine in machines:
    css_class = status_class_map[machine_status[machine]]
    html += f'<div class="{css_class}">{machine}</div>'

# Close HTML
html += """
    </div>
</div>
"""

st.markdown(html, unsafe_allow_html=True)
