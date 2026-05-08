import os
import re
import time
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Plant TV", layout="wide", initial_sidebar_state="collapsed")

API_URL = os.environ.get("FASTAPI_URL", "http://10.20.0.19:8000")

# ─── Side configuration ──────────────────────────────────────────────────────
# Each kiosk shows alerts/cycle data only for machines on its side of the plant.
# Pick the side via:  ?side=east  OR  ?side=west  in the URL,
# or set the SIDE env var ("east" / "west") when launching streamlit.
EAST_MACHINES = [1, 18, 19, 20, 21, 22, 23, 24, 25, 26, 68]
WEST_MACHINES = [43, 48, 49, 50, 51, 52, 57, 58, 59, 60, 61, 62, 65]

def _resolve_side() -> str:
    qp = st.query_params.get("side")
    if isinstance(qp, list):
        qp = qp[0] if qp else None
    side = (qp or os.environ.get("SIDE") or "east").strip().lower()
    return "west" if side == "west" else "east"

SIDE = _resolve_side()
SIDE_MACHINES = EAST_MACHINES if SIDE == "east" else WEST_MACHINES
SIDE_SET = set(SIDE_MACHINES)
SIDE_LABEL = "EAST" if SIDE == "east" else "WEST"

# ─── Slide rotation ──────────────────────────────────────────────────────────
SLIDE_SECONDS = 20
SLIDE_NAMES = ["alerts", "chillers", "cycles"]
slide_idx = int(time.time() // SLIDE_SECONDS) % len(SLIDE_NAMES)
slide = SLIDE_NAMES[slide_idx]

# Static demo data for the chiller slide (kept from the previous dashboard).
CHILLER_TEMPS = {"Chiller 1": 12.4, "Chiller 2": 11.8, "Chiller 3": 13.1}
CHILLER_LEVELS = {"Chiller 1": 82, "Chiller 2": 76, "Chiller 3": 88}
COMPRESSORS = {"HP Compressor": ("28.6", "bar"), "LP Compressor": ("7.2", "bar")}


st.markdown("""
<style>
header[data-testid="stHeader"] {display: none;}
[data-testid="stSidebar"] {display: none;}
[data-testid="collapsedControl"] {display: none;}
.block-container {padding: 0.8rem 1.2rem !important; max-width: 100% !important;}
#MainMenu, footer {visibility: hidden;}
body {background: #0E1117;}

.kiosk-title {
    text-align: center;
    color: #FFFFFF;
    font-size: 2.2rem;
    font-weight: 700;
    margin: 0 0 0.3rem 0;
    letter-spacing: 2px;
}
.side-pill {
    display: inline-block;
    background: #1F2937;
    color: #FFC107;
    border: 2px solid #FFC107;
    padding: 0.15rem 0.9rem;
    border-radius: 999px;
    font-weight: 700;
    letter-spacing: 3px;
    font-size: 1.1rem;
}
.slide-dots {
    text-align: center;
    margin: 0.3rem 0 0.6rem 0;
}
.slide-dots span {
    display: inline-block;
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 999px;
    background: #2B3138;
    margin: 0 0.25rem;
}
.slide-dots span.active { background: #1DB954; }

.slide {
    background: #161B22;
    border-radius: 16px;
    padding: 1.1rem 1.3rem;
    height: 86vh;
    overflow: hidden;
    border: 2px solid #232a33;
}
.slide-title {
    color: #FFFFFF;
    font-size: 1.9rem;
    font-weight: 800;
    text-align: center;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 0.8rem;
}
.slide.alerts { border-color: #FF4B4B; }
.slide.alerts .slide-title { color: #FF4B4B; }
.slide.cycles { border-color: #4DA3FF; }
.slide.cycles .slide-title { color: #4DA3FF; }
.slide.chillers { border-color: #1DB954; }
.slide.chillers .slide-title { color: #1DB954; }

/* ── Alerts slide ────────────────────────────────────────────────── */
.alerts-scroll {
    height: calc(86vh - 5rem);
    overflow: hidden;
    position: relative;
    mask-image: linear-gradient(to bottom, transparent 0%, black 5%, black 95%, transparent 100%);
}
.alerts-track { animation: scrollUp linear infinite; }
@keyframes scrollUp {
    0%   { transform: translateY(0); }
    100% { transform: translateY(-50%); }
}
.alert-card {
    background: rgba(255, 75, 75, 0.12);
    border-left: 6px solid #FF4B4B;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.9rem;
    color: #FFFFFF;
    font-size: 1.4rem;
}
.alert-machine {
    color: #FFC107;
    font-weight: 700;
    font-size: 1.6rem;
    margin-bottom: 0.2rem;
}
.alert-msg { color: #EAEAEA; line-height: 1.3; }
.alert-empty {
    color: #1DB954;
    font-size: 2.4rem;
    text-align: center;
    padding-top: 28vh;
    font-weight: 700;
}

/* ── Tile grids (chillers + cycles) ──────────────────────────────── */
.tile-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1rem;
}
.tile {
    background: #1B2128;
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

/* ── Cycle slide tiles ───────────────────────────────────────────── */
.cycle-grid {
    display: grid;
    gap: 0.9rem;
    height: calc(86vh - 5rem);
    overflow: hidden;
    align-content: start;
}
.cycle-grid.cols-2 { grid-template-columns: 1fr 1fr; }
.cycle-grid.cols-1 { grid-template-columns: 1fr; }
.cycle-tile {
    background: #1B2128;
    border-radius: 12px;
    padding: 0.7rem 1rem;
    border: 2px solid #2B3138;
    color: #FFFFFF;
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    column-gap: 1rem;
}
.cycle-tile .ct-mid {
    font-size: 1.6rem;
    font-weight: 800;
    color: #FFC107;
    min-width: 4.5rem;
}
.cycle-tile .ct-mid small {
    display: block;
    font-size: 0.7rem;
    font-weight: 600;
    color: #9BA3AF;
    letter-spacing: 1px;
}
.cycle-tile .ct-bar {
    height: 0.55rem;
    background: #0E1117;
    border-radius: 999px;
    overflow: hidden;
    position: relative;
}
.cycle-tile .ct-bar > div {
    height: 100%;
    background: #1DB954;
    transition: width 0.3s linear;
}
.cycle-tile .ct-vals {
    text-align: right;
    line-height: 1.1;
}
.cycle-tile .ct-vals .now {
    font-size: 1.7rem;
    font-weight: 800;
    color: #FFFFFF;
}
.cycle-tile .ct-vals .lim {
    font-size: 0.95rem;
    color: #9BA3AF;
}
.cycle-tile.ok      { border-color: #1DB954; }
.cycle-tile.warn    { border-color: #FFC107; }
.cycle-tile.warn .ct-bar > div   { background: #FFC107; }
.cycle-tile.idle    { border-color: #2B3138; }
.cycle-tile.idle .ct-vals .now,
.cycle-tile.idle .ct-mid { color: #6B7280; }
.cycle-tile.over {
    border-color: #FF4B4B;
    animation: flashRed 0.8s infinite;
}
.cycle-tile.over .ct-bar > div { background: #FF4B4B; }
.cycle-tile.over .ct-vals .now { color: #FF4B4B; }
@keyframes flashRed {
    0%, 100% { background: #1B2128; box-shadow: 0 0 0 rgba(255,75,75,0); }
    50%      { background: rgba(255,75,75,0.35); box-shadow: 0 0 24px rgba(255,75,75,0.7); }
}

.cycle-empty {
    color: #9BA3AF;
    font-size: 1.6rem;
    text-align: center;
    padding-top: 25vh;
}
</style>
""", unsafe_allow_html=True)


def _clean_alert(machine, msg):
    prefix = f"Machine {machine}:"
    text = msg[len(prefix):].strip() if msg.startswith(prefix) else msg
    text = re.sub(r"(\d+\.\d{3,})%", lambda m: f"{float(m.group(1)):.1f}%", text)
    return text


@st.cache_data(ttl=5)
def fetch_alerts():
    try:
        r = requests.get(f"{API_URL}/api/fleet/alerts", timeout=4)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("alerts", []):
            mid = item.get("machine_id")
            msg = item.get("message", "")
            results.append((mid, _clean_alert(mid, str(msg))))
        return results, None
    except Exception as e:
        return [], str(e)


@st.cache_data(ttl=5)
def fetch_cycles():
    try:
        r = requests.get(f"{API_URL}/api/fleet/cycles", timeout=4)
        r.raise_for_status()
        return r.json().get("machines", []), None
    except Exception as e:
        return [], str(e)


# ─── Header ──────────────────────────────────────────────────────────────────
st.markdown(
    f"<div class='kiosk-title'>AXIUM PACKAGING — PLANT 1 "
    f"<span class='side-pill'>{SIDE_LABEL} SIDE</span></div>",
    unsafe_allow_html=True,
)

dots_html = "".join(
    f"<span class='{'active' if i == slide_idx else ''}'></span>"
    for i in range(len(SLIDE_NAMES))
)
st.markdown(f"<div class='slide-dots'>{dots_html}</div>", unsafe_allow_html=True)


# ─── Slide 1: Alerts ─────────────────────────────────────────────────────────
def render_alerts_slide():
    alerts, api_error = fetch_alerts()
    filtered = [(m, msg) for (m, msg) in alerts if m in SIDE_SET]

    if api_error:
        st.markdown(
            f"<div class='slide alerts'>"
            f"<div class='slide-title'>Active Alerts</div>"
            f"<div class='alert-empty' style='color:#FF4B4B;'>⚠ API UNREACHABLE<br>"
            f"<span style='font-size:1rem;color:#9BA3AF;'>{api_error}</span></div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        return

    if not filtered:
        st.markdown(
            f"<div class='slide alerts'>"
            f"<div class='slide-title'>Active Alerts ({SIDE_LABEL})</div>"
            f"<div class='alert-empty'>✓ All Systems Normal</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        return

    cards = ""
    for machine, msg in filtered:
        cards += (
            f"<div class='alert-card'>"
            f"<div class='alert-machine'>Machine {machine}</div>"
            f"<div class='alert-msg'>{msg}</div>"
            f"</div>"
        )
    needs_scroll = len(filtered) >= 4
    duration = max(12, len(filtered) * 4)
    track_style = (
        f"animation-duration: {duration}s;" if needs_scroll else "animation: none;"
    )
    inner = (cards + cards) if needs_scroll else cards
    st.markdown(
        f"<div class='slide alerts'>"
        f"<div class='slide-title'>Active Alerts ({SIDE_LABEL}) — {len(filtered)}</div>"
        f"<div class='alerts-scroll'>"
        f"<div class='alerts-track' style='{track_style}'>{inner}</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )


# ─── Slide 2: Chillers ───────────────────────────────────────────────────────
def render_chillers_slide():
    parts = ["<div class='slide chillers'><div class='slide-title'>Chillers & Compressors</div>"]

    parts.append("<div class='section-label'>Chiller Temperatures (°C)</div>")
    tiles = ""
    for name, val in CHILLER_TEMPS.items():
        tiles += (
            f"<div class='tile'>"
            f"<div class='tile-label'>{name}</div>"
            f"<div class='tile-value'>{val}<span class='tile-unit'>°C</span></div>"
            f"</div>"
        )
    parts.append(f"<div class='tile-grid'>{tiles}</div>")

    parts.append("<div class='section-label'>Compressor Pressure</div>")
    tiles = ""
    for name, (val, unit) in COMPRESSORS.items():
        tiles += (
            f"<div class='tile'>"
            f"<div class='tile-label'>{name}</div>"
            f"<div class='tile-value'>{val}<span class='tile-unit'>{unit}</span></div>"
            f"</div>"
        )
    parts.append(
        f"<div class='tile-grid' style='grid-template-columns: 1fr 1fr;'>{tiles}</div>"
    )

    parts.append("<div class='section-label'>Chiller Water Level (%)</div>")
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
    parts.append(f"<div class='tile-grid'>{tiles}</div>")
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


# ─── Slide 3: Cycle time limits ──────────────────────────────────────────────
def render_cycles_slide():
    machines, api_error = fetch_cycles()
    by_id = {m["machine_id"]: m for m in machines}
    rows = [by_id.get(mid, {"machine_id": mid, "cycle_time": None,
                            "cycle_limit": 0, "over_limit": False})
            for mid in SIDE_MACHINES]

    if api_error:
        st.markdown(
            f"<div class='slide cycles'>"
            f"<div class='slide-title'>Cycle Time Limits ({SIDE_LABEL})</div>"
            f"<div class='cycle-empty' style='color:#FF4B4B;'>⚠ API UNREACHABLE<br>"
            f"<span style='font-size:1rem;'>{api_error}</span></div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        return

    cols_cls = "cols-2" if len(rows) > 6 else "cols-1"

    tiles = ""
    over_count = 0
    for r in rows:
        mid = r["machine_id"]
        ct = r.get("cycle_time")
        lim = r.get("cycle_limit") or 0
        over = bool(r.get("over_limit"))

        if ct is None or ct <= 0:
            cls = "idle"
            now_txt = "—"
            pct = 0
        elif over:
            cls = "over"
            now_txt = f"{ct:.1f}s"
            pct = 100
            over_count += 1
        elif lim and ct >= 0.85 * lim:
            cls = "warn"
            now_txt = f"{ct:.1f}s"
            pct = min(100, ct / lim * 100) if lim else 0
        else:
            cls = "ok"
            now_txt = f"{ct:.1f}s"
            pct = min(100, ct / lim * 100) if lim else 0

        lim_txt = f"limit {lim:.0f}s" if lim else "no limit set"

        tiles += (
            f"<div class='cycle-tile {cls}'>"
            f"<div class='ct-mid'>M{mid}<small>MACHINE</small></div>"
            f"<div class='ct-bar'><div style='width:{pct:.0f}%'></div></div>"
            f"<div class='ct-vals'><div class='now'>{now_txt}</div>"
            f"<div class='lim'>{lim_txt}</div></div>"
            f"</div>"
        )

    title_extra = f" — {over_count} OVER LIMIT" if over_count else ""
    st.markdown(
        f"<div class='slide cycles'>"
        f"<div class='slide-title'>Cycle Time Limits ({SIDE_LABEL}){title_extra}</div>"
        f"<div class='cycle-grid {cols_cls}'>{tiles}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ─── Render the active slide ─────────────────────────────────────────────────
if slide == "alerts":
    render_alerts_slide()
elif slide == "chillers":
    render_chillers_slide()
else:
    render_cycles_slide()


# Refresh often enough that the slide flips on time and over-limit machines
# pick up new readings quickly. CSS handles the actual flashing animation.
st_autorefresh(interval=2000, key=f"tv_kiosk_refresh_{SIDE}")
