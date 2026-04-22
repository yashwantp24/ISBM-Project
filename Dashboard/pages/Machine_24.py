import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent.parent  
sys.path.insert(0, str(project_root))
from Notifications.notifs import check_notifications
from database.opc_client import OPCClient
from database.tags import MACHINES, OPC_SERVER_URL
from mold_map import get_bottle_type
import information

m=24

data = information.get_machine(m)


if "OPCClient" not in st.session_state:
    st.session_state.OPCClient = OPCClient(OPC_SERVER_URL)
    st.session_state.OPCClient.connect()

client = st.session_state.OPCClient


values = client.read_machine(m,MACHINES)
Prod_qty=values.get("Production Quantity")

# ---------- MACHINE STATUS ----------
machine_status = values.get("Auto Cycle")  

st.write()
#-------------Temperature----------------------
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

/* Alerts */
.status-alerts {
    background-color: Yellow;
    color: Black;
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


# Initialize once
if "mold_num" not in st.session_state:
    st.session_state.mold_num = 0
if "cycle_lim" not in st.session_state:
    st.session_state.cycle_lim = 0




col1,col2,col3,col4 = st.columns([7.5,1.7,1.9,2.5])
# ---------- TOP BAR ----------


with col2:
    with st.popover("Edit"):
        st.write("Enter the values")

        with st.form("edit_form"):
            mold_num= st.number_input(
                "Mold Number"
            )
            cycle_lim = st.number_input(
                "Cycle Limit",
            )

            submitted = st.form_submit_button("Save")
        if submitted:
            information.update_machine(
                number=m,   
                mold=mold_num,
                cyc_limit=cycle_lim
            )
        
            

            
with col3:
    with st.popover("Alerts"):
        st.markdown("Alerts")
        cycle_limits = {
                m: data["cyc_limit"]
            }
        alerts,alert_flag = check_notifications(m, values, cycle_limits)
        for a in alerts:
            
            st.write("ALERT:", a)

with col1:
    st.markdown(f"""
    <div class="top-bar">
        <div class="dashboard-title">
        Machine {m} - 70DPW V4
        </div>
    """, unsafe_allow_html=True)

bottle_type = get_bottle_type(int(data["mold"])) or "Unknown"


# ---------- STATUS LOGIC ----------
if alert_flag == 1:
    status_html = '<div class="status-badge status-alerts">Alerts</div>'
elif machine_status == 1:
    status_html = '<div class="status-badge status-running">Running</div>'
else:
    status_html = '<div class="status-badge status-stopped">Stopped</div>'


st.markdown(f"""
    <div class="top-bar">
        <div class="machine-id-pill">
            #389A61816
        </div>
        <div class="mold-id-pill">
            {bottle_type}
        </div>
        <div class="cycle-pill">
            Cycle Limit:{data["cyc_limit"]}s
        </div>
        {status_html}
    </div>
    """, unsafe_allow_html=True)


st.write("")  # spacing
tab1, tab2, tab3,tab4,tab5,tab6,tab7 = st.tabs(["General Metrics", "Temperatures", "Injection","Blow","Pressures","Production Quantity","Anomaly Prediction"])


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
        st.markdown(f"""
        <div class="metric-card">
            <span class="material-icons-outlined metric-icon">inventory_2</span>
            Production Count
            <div>
            <div class="metric-value">{values.get("Production Quantity")}</div>
            <div class="metric-desc">Total bottles today</div>
        </div>
        """, unsafe_allow_html=True)

    # Card 2: Efficiency
    with row1[1]:
        st.markdown(f"""
        <div class="metric-card">
            <span class="material-icons-outlined metric-icon">show_chart</span>
            Cycle Time
            <div class="metric-value">{values.get("Cycle Time")}</div>
            <div class="metric-desc">Overall equipment effectiveness</div>
        </div>
        """, unsafe_allow_html=True)

    # Card 3: Dry Cycle
    with row2[0]:
        st.markdown(f"""
        <div class="metric-card">
            <span class="material-icons-outlined metric-icon">schedule</span>
            Dry Cycle Time
            <div class="metric-value">{values.get("Dry Cycle Time")}</div>
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
        temperature_bar("Nozzle", present_value=values.get("Barrel Nozzle PV"), set_value=values.get("Barrel Nozzle SV"))
        
    with row1[1]:
        temperature_bar("Front", present_value=values.get("Barrel Front PV"), set_value=values.get("Barrel Front SV"))
    
    with row2[0]:
        temperature_bar("Middle", present_value=values.get("Barrel Middle PV"), set_value=values.get("Barrel Middle SV"))
    
    with row2[1]:
        temperature_bar("Rear Front", present_value=values.get("Barrel Rear Front PV"), set_value=values.get("Barrel Rear Front SV"))
    
    with row3[0]:
        temperature_bar("Rear Rear", present_value=values.get("Barrel Rear Rear PV"), set_value=values.get("Barrel Rear Rear SV"))
    
    with row3[1]:
        temperature_bar("Oil", present_value=values.get("Oil Temperature PV"), set_value=values.get("Oil Temperature SV"))
    
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
        metric_card("Injection Time", values.get("Injection Time"))

    
    with row1[1]:
        metric_card("Cooling Time", values.get("Cooling Time"))

    with row1[2]:
        metric_card("Screw Charge Time", values.get("Charge Time"))

    with row2[0]:
        metric_card("Shot Size", values.get("Shot Size SV"))
        
    with row2[1]:
        metric_card("P-V Time", values.get("P-V SV"))
        
    with row2[2]:
        metric_card("V-P", values.get("V-P Time PV"))
        
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
        metric_card("Blow Time", values.get("Blow Time"))

    
    with row1[1]:
        metric_card("Stretch Time", values.get("Stretch Time"))

    
    with row1[2]:
        metric_card("Primary Blow A", values.get("Primary Blow Time A"))

    
    with row2[0]:
        metric_card("Primary Blow B", values.get("Primary Blow Time B"))
        
    with row2[1]:
        metric_card("Secondary Blow A", values.get("Secondary Blow Time A"))
        
    with row2[2]:
        metric_card("Secondary Blow B", values.get("Secondary Blow Time B"))
    

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
        metric_card("Screw Charge", values.get("Screw Pressure Monitor"))

    # Card 2: Efficiency
    with row1[1]:
        metric_card("Screw Set 1", values.get("Screw Set Data 1 Pressure"))

    # Card 3: Uptime
    with row1[2]:
        metric_card("Screw Set 2", values.get("Screw Set Data 2 Pressure"))

    # Card 4: Cycle Rate
    with row2[0]:
        metric_card("Main RAM", values.get("Main Ram FW Pressure"))
        
    with row2[1]:
        metric_card("Blow Mold CL", values.get("Blow Mold CL FA Pressure"))
        
    with row2[2]:
        metric_card("Stretch Unit UP", values.get("Stretch Unit UP FA Pressure"))


#Production Quantity--------------------------------------------------------------------------------------------
with tab6:
    st.markdown("""<div class="card">
    <div class="card-title">
        <span class="material-icons-outlined general-icon">inventory_2</span>
        Production &amp; Downtime
    </div>
    <div class="machine-grid">
""", unsafe_allow_html=True)

    # ── DB helpers (read-only, no trackers needed) ─────────────────────────────
    def _get_live_production(machine_id):
        from database.db import get_connection
        from datetime import date
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """SELECT COALESCE(total_bottles, 0), mold_id
                   FROM production_live
                   WHERE machine_id = %s AND date = %s""",
                (machine_id, date.today())
            )
            row = cur.fetchone()
            return {"bottles": int(row[0]) if row else 0,
                    "mold_id": row[1] if row else None}
        except Exception:
            return {"bottles": 0, "mold_id": None}
        finally:
            cur.close(); conn.close()

    def _get_live_downtime(machine_id):
        from database.db import get_connection
        from datetime import date
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """SELECT COALESCE(total_downtime_seconds, 0)
                   FROM daily_downtime_live
                   WHERE machine_id = %s AND date = %s""",
                (machine_id, date.today())
            )
            row = cur.fetchone()
            total_sec = float(row[0]) if row else 0.0

            cur.execute(
                """SELECT COUNT(*) FROM downtime_events
                   WHERE machine_id = %s AND DATE(start_time) = %s""",
                (machine_id, date.today())
            )
            event_count = cur.fetchone()[0]
            return {"total_sec": total_sec, "event_count": event_count}
        except Exception:
            return {"total_sec": 0.0, "event_count": 0}
        finally:
            cur.close(); conn.close()

    def _get_shift_downtime(machine_id):
        """
        Return downtime seconds and event count for all three shifts today.
        - Active shift → shift_downtime_live  (live, updating)
        - Past shifts  → daily_archive columns (written at shift boundary, permanent)
        """
        from database.db import get_connection
        from datetime import date, datetime
        conn = get_connection()
        cur = conn.cursor()
        try:
            today = date.today()
            now_h = datetime.now().hour
            cur_shift = 1 if now_h < 8 else 2 if now_h < 16 else 3

            result = {1: (0.0, 0), 2: (0.0, 0), 3: (0.0, 0)}

            # Pull completed shifts from daily_archive
            cur.execute(
                """SELECT
                       shift_1_downtime_seconds, shift_1_events,
                       shift_2_downtime_seconds, shift_2_events,
                       shift_3_downtime_seconds, shift_3_events
                   FROM daily_archive
                   WHERE machine_id = %s AND date = %s""",
                (machine_id, today)
            )
            row = cur.fetchone()
            if row:
                result[1] = (float(row[0]), int(row[1]))
                result[2] = (float(row[2]), int(row[3]))
                result[3] = (float(row[4]), int(row[5]))

            # Override active shift with live value (more up-to-date)
            cur.execute(
                """SELECT total_downtime_seconds, event_count
                   FROM shift_downtime_live
                   WHERE machine_id = %s AND date = %s AND shift = %s""",
                (machine_id, today, cur_shift)
            )
            live_row = cur.fetchone()
            if live_row:
                result[cur_shift] = (float(live_row[0]), int(live_row[1]))

            return result
        except Exception:
            return {1: (0.0, 0), 2: (0.0, 0), 3: (0.0, 0)}
        finally:
            cur.close(); conn.close()

    def _get_live_rate(machine_id):
        """Bottles/hr from production_live — approximated from today's count
        vs elapsed time since midnight, as a simple fallback.
        For the rolling 1-hr rate use the in-process ProductionCounter instead."""
        from database.db import get_connection
        from datetime import date, datetime
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """SELECT COALESCE(total_bottles, 0)
                   FROM production_live
                   WHERE machine_id = %s AND date = %s""",
                (machine_id, date.today())
            )
            row = cur.fetchone()
            bottles = int(row[0]) if row else 0
            now = datetime.now()
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elapsed_hr = (now - midnight).total_seconds() / 3600
            rate = round(bottles / elapsed_hr, 1) if elapsed_hr > 0 else 0.0
            return rate
        except Exception:
            return 0.0
        finally:
            cur.close(); conn.close()

    def _get_archive(machine_id, limit=30):
        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """SELECT date, mold_id, total_bottles,
                          total_downtime_seconds, downtime_event_count,
                          shift_1_downtime_seconds, shift_1_events,
                          shift_2_downtime_seconds, shift_2_events,
                          shift_3_downtime_seconds, shift_3_events
                   FROM daily_archive
                   WHERE machine_id = %s
                   ORDER BY date DESC
                   LIMIT %s""",
                (machine_id, limit)
            )
            rows = cur.fetchall()
            return rows
        except Exception:
            return []
        finally:
            cur.close(); conn.close()

    # ── Fetch data ─────────────────────────────────────────────────────────────
    prod_live    = _get_live_production(m)
    dt_live      = _get_live_downtime(m)
    rate_live    = _get_live_rate(m)
    archive      = _get_archive(m, limit=30)
    shift_dt     = _get_shift_downtime(m)

    bottles_today = prod_live["bottles"]
    total_sec     = dt_live["total_sec"]
    event_count   = dt_live["event_count"]

    dt_min  = round(total_sec / 60, 1)
    dt_hr   = round(total_sec / 3600, 2)

    # Availability vs elapsed time today
    from datetime import datetime as _dt
    _now       = _dt.now()
    _midnight  = _now.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed_sec = (_now - _midnight).total_seconds()
    avail_pct   = round(max(0.0, (elapsed_sec - total_sec) / elapsed_sec * 100), 1) if elapsed_sec > 0 else 100.0

    # Status colour for downtime card
    dt_color = "#00c853" if dt_min < 30 else "#ffd600" if dt_min < 90 else "#d50000"
    avail_color = "#00c853" if avail_pct >= 95 else "#ffd600" if avail_pct >= 85 else "#d50000"

    # ── Live metric cards ──────────────────────────────────────────────────────
    row1 = st.columns(2)
    row2 = st.columns(2)

    with row1[0]:
        st.markdown(f"""
        <div class="metric-card">
            <span class="material-icons-outlined metric-icon">inventory_2</span>
            Bottles Produced Today
            <div class="metric-value">{bottles_today:,}</div>
            <div class="metric-desc">Total since midnight</div>
        </div>
        """, unsafe_allow_html=True)

    with row1[1]:
        st.markdown(f"""
        <div class="metric-card">
            <span class="material-icons-outlined metric-icon">speed</span>
            Production Rate
            <div class="metric-value">{rate_live:,.0f}</div>
            <div class="metric-desc">Bottles per hour (today avg)</div>
        </div>
        """, unsafe_allow_html=True)

    with row2[0]:
        st.markdown(f"""
        <div class="metric-card">
            <span class="material-icons-outlined metric-icon">timer_off</span>
            Downtime Today
            <div class="metric-value" style="color:{dt_color};">{dt_min} min</div>
            <div class="metric-desc">{dt_hr} hrs &nbsp;|&nbsp; {event_count} event{'s' if event_count != 1 else ''}</div>
        </div>
        """, unsafe_allow_html=True)

    with row2[1]:
        st.markdown(f"""
        <div class="metric-card">
            <span class="material-icons-outlined metric-icon">check_circle</span>
            Availability
            <div class="metric-value" style="color:{avail_color};">{avail_pct}%</div>
            <div class="metric-desc">Based on elapsed time today</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    # ── Shift downtime breakdown ───────────────────────────────────────────────
    from datetime import datetime as _dt2
    _now2       = _dt2.now()
    _cur_shift  = 1 if _now2.hour < 8 else 2 if _now2.hour < 16 else 3
    SHIFT_LABELS = {
        1: ("Shift 1", "00:00 – 08:00"),
        2: ("Shift 2", "08:00 – 16:00"),
        3: ("Shift 3", "16:00 – 00:00"),
    }

    st.markdown("""
    <div style="color:white; font-size:20px; font-weight:700; margin:16px 0 12px 0;">
        <span class="material-icons-outlined" style="vertical-align:middle;color:#4ea8de;">schedule</span>
        &nbsp;Downtime by Shift
    </div>
    """, unsafe_allow_html=True)

    shift_cols = st.columns(3)
    for idx, shift_num in enumerate([1, 2, 3]):
        secs, ev = shift_dt[shift_num]
        s_min    = round(secs / 60, 1)
        s_hr     = round(secs / 3600, 2)
        lbl, hrs = SHIFT_LABELS[shift_num]
        is_active = (shift_num == _cur_shift)

        s_color = "#00c853" if s_min < 30 else "#ffd600" if s_min < 90 else "#d50000"
        border  = "#4ea8de" if is_active else "#283347"
        ev_label = "events" if ev != 1 else "event"

        active_badge = (
            '<span style="font-size:11px;background:#4ea8de;color:#000;'
            'border-radius:4px;padding:2px 6px;margin-left:8px;font-weight:700;">ACTIVE</span>'
            if is_active else ""
        )

        card_html = (
            '<div class="metric-card" style="border-color:' + border + ';">'
            '<div style="display:flex;align-items:center;margin-bottom:6px;">'
            '<span class="material-icons-outlined metric-icon">timer_off</span>'
            '&nbsp;<span style="font-size:16px;color:#c8d3df;">' + lbl +
            ' &nbsp;<span style="color:#9db2c4;">' + hrs + '</span></span>'
            + active_badge +
            '</div>'
            '<div class="metric-value" style="color:' + s_color + ';">' + str(s_min) + ' min</div>'
            '<div class="metric-desc">' + str(s_hr) + ' hrs &nbsp;|&nbsp; ' + str(ev) + ' ' + ev_label + '</div>'
            '</div>'
        )

        with shift_cols[idx]:
            st.markdown(card_html, unsafe_allow_html=True)

    st.write("")

    # ── History table ──────────────────────────────────────────────────────────
    st.markdown("""
    <div style="color:white; font-size:20px; font-weight:700; margin-bottom:12px;">
        <span class="material-icons-outlined" style="vertical-align:middle;color:#4ea8de;">table_chart</span>
        &nbsp;Daily History
    </div>
    """, unsafe_allow_html=True)

    if archive:
        archive_df = pd.DataFrame(archive, columns=[
            "Date", "Mold ID", "Bottles Produced",
            "Downtime (sec)", "Downtime Events",
            "S1 Downtime (sec)", "S1 Events",
            "S2 Downtime (sec)", "S2 Events",
            "S3 Downtime (sec)", "S3 Events",
        ])

        # Derived columns
        archive_df["Downtime (min)"]    = (archive_df["Downtime (sec)"] / 60).round(1)
        archive_df["Availability (%)"]  = archive_df["Downtime (sec)"].apply(
            lambda s: round(max(0, (86400 - s) / 86400 * 100), 1)
        )
        archive_df["S1 DT (min)"] = (archive_df["S1 Downtime (sec)"] / 60).round(1)
        archive_df["S2 DT (min)"] = (archive_df["S2 Downtime (sec)"] / 60).round(1)
        archive_df["S3 DT (min)"] = (archive_df["S3 Downtime (sec)"] / 60).round(1)

        archive_df["Date"]             = pd.to_datetime(archive_df["Date"]).dt.strftime("%Y-%m-%d")
        archive_df["Bottles Produced"] = archive_df["Bottles Produced"].apply(lambda x: f"{int(x):,}")

        display_df = archive_df[[
            "Date", "Mold ID", "Bottles Produced",
            "Downtime (min)", "Downtime Events", "Availability (%)",
            "S1 DT (min)", "S1 Events",
            "S2 DT (min)", "S2 Events",
            "S3 DT (min)", "S3 Events",
        ]]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date":             st.column_config.TextColumn("Date"),
                "Mold ID":          st.column_config.NumberColumn("Mold ID"),
                "Bottles Produced": st.column_config.TextColumn("Bottles"),
                "Downtime (min)":   st.column_config.NumberColumn("DT Total (min)", format="%.1f"),
                "Downtime Events":  st.column_config.NumberColumn("Events"),
                "Availability (%)": st.column_config.ProgressColumn(
                                        "Availability",
                                        format="%.1f%%",
                                        min_value=0, max_value=100,
                                    ),
                "S1 DT (min)":      st.column_config.NumberColumn("S1 DT (min)", format="%.1f",
                                        help="Shift 1  00:00–08:00"),
                "S1 Events":        st.column_config.NumberColumn("S1 Events",
                                        help="Shift 1  00:00–08:00"),
                "S2 DT (min)":      st.column_config.NumberColumn("S2 DT (min)", format="%.1f",
                                        help="Shift 2  08:00–16:00"),
                "S2 Events":        st.column_config.NumberColumn("S2 Events",
                                        help="Shift 2  08:00–16:00"),
                "S3 DT (min)":      st.column_config.NumberColumn("S3 DT (min)", format="%.1f",
                                        help="Shift 3  16:00–00:00"),
                "S3 Events":        st.column_config.NumberColumn("S3 Events",
                                        help="Shift 3  16:00–00:00"),
            }
        )
    else:
        st.info("No archive data yet. Daily records are written at midnight.")

    st.markdown("</div></div>", unsafe_allow_html=True)

    
#Downtime----------------------------------------------------------------------------------------------------
    
with tab7:
    st.markdown("""<div class="card">
    <div class="card-title">
        <span class="material-icons-outlined general-icon">trending_down</span>
        Anomaly Prediction
    </div>
    <div class="machine-grid">
""", unsafe_allow_html=True)
    
    st.write("Coming Soon")

    
    
st_autorefresh(interval=10000, key="refresh")