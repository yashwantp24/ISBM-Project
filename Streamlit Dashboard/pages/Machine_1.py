import streamlit as st

# ---------- MACHINE STATUS ----------

machine_status = 0  

def temperature_bar(label: str, present_value: float, set_value: float):
    
    
    if set_value == 0:
        percent = 0
        diff = 0
    else:
        percent = present_value / set_value
        percent = max(0, min(percent, 1))
        diff = (set_value - present_value) / set_value * 100

    # bar color
    if diff <= 5:
        color = "#00c853"        # green
    elif diff <= 10:
        color = "#ffd600"        # yellow
    else:
        color = "#d50000"        # red

    
    st.markdown(
        f"""
        <div style="background-color:#1b1b1c;padding:20px;border-radius:10px;margin-top:10px;border: 4px solid #283347;">
            <div style="color:white;font-size:18px;margin-bottom:8px;">
                {label}
                <span style="float:right;">{present_value}°C / {set_value}°C</span>
            </div>
            <div style="background-color:#0f172a;border-radius:10px;height:12px;">
                <div style="
                    width:{percent*100}%;
                    background:{color};
                    height:12px;
                    border-radius:10px;">
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
# ---------- CSS ----------
st.markdown("""
<link href="https://fonts.googleapis.com/icon?family=Material+Icons+Outlined" rel="stylesheet">

<style>

[data-testid="stAppViewContainer"] {
    background-color: #111;
}

/* Dashboard Title */
.dashboard-bar{
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.dashboard-title {
    font-size: 28px;
    font-weight: 700;
    color: white;
    margin-bottom: 4px;
    
}

/* Subtitle */
.dashboard-subtitle {
    font-size: 16px;
    color: #b8c6d1;
    margin-bottom: 25px;
}

/* Header row */
.top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
}



/* Machine ID pill */
.machine-id-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 10px;
    background-color: #1b263b;
    border: 4px solid #415a77;
    color: #e0e6ed;
    font-size: 15px;
}

.mold-id-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 10px;
    background-color: #ed750c;
    border: 4px solid #415a77;
    color: #e0e6ed;
    font-size: 15px;
}

.cycle-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 10px;
    background-color: blue;
    border: 4px solid #415a77;
    color: #e0e6ed;
    font-size: 15px;
}

/* Status badge (base class) */
.status-badge {
    padding: 6px 14px;
    border-radius: 10px;
    border: 4px solid #415a77;
    font-size: 15px;
    color: white;
    text-align: center;
}

/* Running */
.status-running {
    background-color: #1DB954;
}

/* Stopped */
.status-stopped {
    background-color: #FF4B4B;
}

.card-title {
    font-size: 28px;  /* Increase from original 22px */
    font-weight: 700;
    color: white;
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 18px;
}

/* ---- Slimmer rectangular cards ---- */
.metric-card {
    font-size: 20px;  /* Increase from original 22px */
    font-weight: 700;
    color: #c8d3df;
    background-color: #1b1b1c;
    padding: 14px 18px;
    border-radius: 10px;
    width: 100%;
    border: 4px solid #283347;
    margin-bottom: 18px;
    min-height: 110px;
}



/* Smaller icons */
.metric-icon {
    font-size: 20px;
    color: #4ea8de;
    margin-bottom: 4px;
}

/* general icons */
.general-icon {
    font-size: 28px;
    color: #4ea8de;
    margin-bottom: 4px;
}

/* Title */
.metric-title {
    font-size: 18px;
    color: #c8d3df;
    margin-bottom: 2px;
}

/* Value */
.metric-value {
    font-size: 28px;
    font-weight: 700;
    color: white;
    margin: 0;
}

/* Description */
.metric-desc {
    font-size: 12px;
    color: #9db2c4;
    margin-top: -3px;
}

</style>
""", unsafe_allow_html=True)

def metric_card(name: str, value):
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">{name}</div>
            <div class="metric-value">{value}</div>
        </div>
    """, unsafe_allow_html=True)






# ---------- STATUS LOGIC ----------
if machine_status == 1:
    status_html = '<div class="status-badge status-running">Running</div>'
else:
    status_html = '<div class="status-badge status-stopped">Stopped</div>'

col1,col2 = st.columns([9,1])
# ---------- TOP BAR ----------
with col2:
    with st.popover(""):
        st.markdown("Hello")
    

with col1:
    st.markdown(f"""
    <div class="top-bar">
        <div class="dashboard-title">
        Machine 1
        </div>
        <div class="machine-id-pill">
            #389A61816
        </div>
        <div class="mold-id-pill">
            8oz Bottle
        </div>
        <div class="cycle-pill">
            20s
        </div>
        {status_html}
    </div>
    """, unsafe_allow_html=True)




st.write("")  # spacing
tab1, tab2, tab3,tab4,tab5,tab6,tab7 = st.tabs(["General Metrics", "Temperatures", "Injection","Blow","Pressures","Production Quantity","Downtime Chart"])


with tab1:
    st.markdown("""<div class="card">
    <div class="card-title">
        <span class="material-icons-outlined general-icon">dashboard</span>
        General Metrics
    </div>
    <div class="machine-grid">
""", unsafe_allow_html=True)

    # ---------- CARDS ROWS ----------
    row1 = st.columns(2)
    row2 = st.columns(2)



    # Card 1: Production Count
    with row1[0]:
        st.markdown("""
        <div class="metric-card">
            <span class="material-icons-outlined metric-icon">inventory_2</span>
            Production Count
            <div class="metric-value">12,854</div>
            <div class="metric-desc">Total bottles today</div>
        </div>
        """, unsafe_allow_html=True)

    # Card 2: Efficiency
    with row1[1]:
        st.markdown("""
        <div class="metric-card">
            <span class="material-icons-outlined metric-icon">show_chart</span>
            Cycle Time
            <div class="metric-value">21.2s</div>
            <div class="metric-desc">Overall equipment effectiveness</div>
        </div>
        """, unsafe_allow_html=True)

    # Card 3: Uptime
    with row2[0]:
        st.markdown("""
        <div class="metric-card">
            <span class="material-icons-outlined metric-icon">schedule</span>
            Dry Cycle Time
            <div class="metric-value">6s</div>
            <div class="metric-desc">Today's runtime</div>
        </div>
        """, unsafe_allow_html=True)

    # Card 4: Cycle Rate
    with row2[1]:
        st.markdown("""
        <div class="metric-card">
            <span class="material-icons-outlined metric-icon">monitor_heart</span>
            Cycle Rate
            <div class="metric-value">439</div>
            <div class="metric-desc">Bottles per hour</div>
        </div>
        """, unsafe_allow_html=True)
        
#Temperature--------------------------------------------------------------------------------------        
with tab2:
    st.markdown("""<div class="card">
    <div class="card-title">
        <span class="material-icons-outlined general-icon">device_thermostat</span>
        Temperature
    </div>
    <div class="machine-grid">
""", unsafe_allow_html=True)
    
    row1 = st.columns(2)
    row2 = st.columns(2)
    row3 = st.columns(2)
    with row1[0]:
        temperature_bar("Nozzle", present_value=285, set_value=285)
        
    with row1[1]:
        temperature_bar("Front", present_value=285, set_value=285)
    
    with row2[0]:
        temperature_bar("Middle", present_value=285, set_value=285)
    
    with row2[1]:
        temperature_bar("Rear Front", present_value=285, set_value=285)
    
    with row3[0]:
        temperature_bar("Rear Rear", present_value=285, set_value=285)
    
    with row3[1]:
        temperature_bar("Oil", present_value=285, set_value=285)
    
#Injection-------------------------------------------------------------------------    
with tab3:
    st.markdown("""<div class="card">
    <div class="card-title">
        <span class="material-icons-outlined general-icon">vaccines</span>
        Injection
    </div>
    <div class="machine-grid">
""", unsafe_allow_html=True)
    
    
    row1 = st.columns(3)
    row2 = st.columns(3)

    with row1[0]:
        metric_card("Injection Time", 10)

    
    with row1[1]:
        metric_card("Cooling Time", 10)

    with row1[2]:
        metric_card("Screw Charge Time", 10)

    with row2[0]:
        metric_card("Shot Size", 10)
        
    with row2[1]:
        metric_card("P-V Time", 10)
        
    with row2[2]:
        metric_card("V-P", 10)
        
#Blow-------------------------------------------------------------------------------------------------       
with tab4:
    st.markdown("""<div class="card">
    <div class="card-title">
        <span class="material-icons-outlined general-icon">air</span>
        Blow
    </div>
    <div class="machine-grid">
""", unsafe_allow_html=True)
    
    
    row1 = st.columns(3)
    row2 = st.columns(3)



    
    with row1[0]:
        metric_card("Blow Time", 10)

    
    with row1[1]:
        metric_card("Stretch Time", 10)

    
    with row1[2]:
        metric_card("Primary Blow A", 10)

    
    with row2[0]:
        metric_card("Primary Blow B", 10)
        
    with row2[1]:
        metric_card("Secondary Blow A", 10)
        
    with row2[2]:
        metric_card("Secondary Blow B", 10)
    

#Pressures------------------------------------------------------------------------------------------------
with tab5:
    st.markdown("""<div class="card">
    <div class="card-title">
        <span class="material-icons-outlined general-icon">compress</span>
        Pressure
    </div>
    <div class="machine-grid">
""", unsafe_allow_html=True)
    
    
    row1 = st.columns(3)
    row2 = st.columns(3)



    
    with row1[0]:
        metric_card("Screw Charge", 10)

    # Card 2: Efficiency
    with row1[1]:
        metric_card("Screw Set 1", 10)

    # Card 3: Uptime
    with row1[2]:
        metric_card("Screw Set 2", 10)

    # Card 4: Cycle Rate
    with row2[0]:
        metric_card("Main RAM", 10)
        
    with row2[1]:
        metric_card("Blow Mold CL", 10)
        
    with row2[2]:
        metric_card("Stretch Unit UP", 10)


#Production Quantity--------------------------------------------------------------------------------------------
with tab6:
    st.markdown("""<div class="card">
    <div class="card-title">
        <span class="material-icons-outlined general-icon">inventory_2</span>
        Production Quantity
    </div>
    <div class="machine-grid">
""", unsafe_allow_html=True)
    
    
#Downtime----------------------------------------------------------------------------------------------------
    
with tab7:
    st.markdown("""<div class="card">
    <div class="card-title">
        <span class="material-icons-outlined general-icon">trending_down</span>
        Downtime Graph
    </div>
    <div class="machine-grid">
""", unsafe_allow_html=True)