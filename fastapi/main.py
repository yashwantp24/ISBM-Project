# main.py
"""
FastAPI backend for the ISBM SCADA dashboard.

OPC reads now use subscriptions:
  - Connect once at startup
  - Subscribe to all tags for all machines
  - Cache is updated in background by OPC server push
  - All API reads hit in-memory cache (zero network latency)
  - Single uvicorn worker (default)

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import date, datetime, timedelta
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ─── Path setup (must come before database.* imports) ───────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.connection import get_conn

# ─── Imports: your existing modules (unchanged) ─────────────────────────────

from tracking.dashboard_queries import (
    get_live_downtime,
    get_live_production,
    get_today_downtime_events,
    get_archive_range,
    get_multi_machine_live_summary,
)

from database.opc_client import OPCClient
from database.tags import MACHINES, OPC_SERVER_URL, MACHINE_REGISTRY, get_machine_type
from Dashboard.mold_map import MOLD_MAP, get_bottle_type
from Dashboard import information
from Notifications.notifs import check_notifications


# ─── Configuration ───────────────────────────────────────────────────────────

TRACKED_MACHINES = [1, 22, 23, 25, 26, 59, 60, 61, 62, 68]
SUBSCRIPTION_INTERVAL_MS = 250
WARMUP_SEC = 3
ALERT_SWEEP_INTERVAL = 20  # seconds between alert sweeps (replaces alert_collector.py)

# ── Machine Type Dashboard Layouts ───────────────────────────────────────────
# Tells the React frontend what tabs/metrics/charts to render per machine type.
# The frontend reads this config and dynamically builds the dashboard.

MACHINE_TYPE_LAYOUTS = {
    "70DPW": {
        "label": "70DPW V4 — ISBM",
        "tabs": [
            {
                "key": "general",
                "label": "General",
                "sections": [
                    {
                        "type": "metrics",
                        "items": [
                            {"tag": "Production Quantity", "title": "Production Count", "desc": "PLC register"},
                            {"tag": "Cycle Time", "title": "Cycle Time", "desc": "Current cycle", "unit": "s"},
                            {"tag": "Dry Cycle Time", "title": "Dry Cycle Time", "desc": "No-load time", "unit": "s"},
                            {"tag": "Charge Time", "title": "Charge Time", "desc": "Screw charge", "unit": "s"},
                        ],
                    },
                    {
                        "type": "live_production",
                    },
                    {
                        "type": "charts",
                        "items": [
                            {
                                "kind": "cycle",
                                "title": "Cycle Time / Dry Cycle Time / Charge Time",
                                "dataKeys": ["Cycle Time", "Dry Cycle Time", "Charge Time"],
                                "colors": ["#4ea8de", "#ffd600", "#00c853"],
                            },
                            {"kind": "production_rate"},
                        ],
                    },
                ],
            },
            {
                "key": "temps",
                "label": "Temperatures",
                "sections": [
                    {
                        "type": "temp_bars",
                        "items": [
                            {"label": "Nozzle", "pvTag": "Barrel Nozzle PV", "svTag": "Barrel Nozzle SV"},
                            {"label": "Front", "pvTag": "Barrel Front PV", "svTag": "Barrel Front SV"},
                            {"label": "Middle", "pvTag": "Barrel Middle PV", "svTag": "Barrel Middle SV"},
                            {"label": "Rear Front", "pvTag": "Barrel Rear Front PV", "svTag": "Barrel Rear Front SV"},
                            {"label": "Rear Rear", "pvTag": "Barrel Rear Rear PV", "svTag": "Barrel Rear Rear SV"},
                            {"label": "Oil", "pvTag": "Oil Temperature PV", "svTag": "Oil Temperature SV"},
                        ],
                    },
                ],
            },
            {
                "key": "injection",
                "label": "Injection",
                "sections": [
                    {
                        "type": "metrics",
                        "items": [
                            {"tag": "Injection Time", "title": "Injection Time"},
                            {"tag": "Cooling Time", "title": "Cooling Time"},
                            {"tag": "Charge Time", "title": "Screw Charge Time"},
                            {"tag": "Shot Size SV", "title": "Shot Size"},
                            {"tag": "P-V SV", "title": "P-V Time"},
                            {"tag": "V-P Time PV", "title": "V-P"},
                        ],
                    },
                    {
                        "type": "charts",
                        "items": [
                            {
                                "kind": "cycle",
                                "title": "Cycle Time / Charge Time / V-P Time",
                                "dataKeys": ["Cycle Time", "Charge Time", "V-P Time PV"],
                                "colors": ["#4ea8de", "#00c853", "#c084fc"],
                            },
                        ],
                    },
                ],
            },
            {
                "key": "blow",
                "label": "Blow",
                "sections": [
                    {
                        "type": "metrics",
                        "items": [
                            {"tag": "Blow Time", "title": "Blow Time"},
                            {"tag": "Stretch Time", "title": "Stretch Time"},
                            {"tag": "Primary Blow Time A", "title": "Primary Blow A"},
                            {"tag": "Primary Blow Time B", "title": "Primary Blow B"},
                            {"tag": "Secondary Blow Time A", "title": "Secondary Blow A"},
                            {"tag": "Secondary Blow Time B", "title": "Secondary Blow B"},
                        ],
                    },
                ],
            },
            {
                "key": "pressures",
                "label": "Pressures",
                "sections": [
                    {
                        "type": "metrics",
                        "items": [
                            {"tag": "Screw Pressure Monitor", "title": "Screw Charge"},
                            {"tag": "Screw Set Data 1 Pressure", "title": "Screw Set 1"},
                            {"tag": "Screw Set Data 2 Pressure", "title": "Screw Set 2"},
                            {"tag": "Main Ram FW Pressure", "title": "Main RAM"},
                            {"tag": "Blow Mold CL FA Pressure", "title": "Blow Mold CL"},
                            {"tag": "Stretch Unit UP FA Pressure", "title": "Stretch Unit UP"},
                        ],
                    },
                ],
            },
            {
                "key": "cycle_monitor",
                "label": "Cycle Monitor",
                "sections": [
                    {
                        "type": "metric_group",
                        "title": "Injection",
                        "items": [
                            {"tag": "Injection Mold CL FA", "title": "Injection Mold CL FA"},
                            {"tag": "Injection Mold OP FA", "title": "Injection Mold OP FA"},
                            {"tag": "Lip Mold CL FA", "title": "Lip Mold CL FA"},
                            {"tag": "Lip Mold OP FA", "title": "Lip Mold OP FA"},
                            {"tag": "Injection Mold CL", "title": "Injection Mold CL"},
                            {"tag": "Injection Mold OP", "title": "Injection Mold OP"},
                        ],
                    },
                    {
                        "type": "metric_group",
                        "title": "Blow",
                        "items": [
                            {"tag": "Blow Mold CL FA", "title": "Blow Mold CL FA"},
                            {"tag": "Blow Mold OP FA", "title": "Blow Mold OP FA"},
                            {"tag": "Blow Core DW", "title": "Blow Core DW"},
                            {"tag": "Blow Core UP", "title": "Blow Core UP"},
                            {"tag": "Bottom DW", "title": "Bottom DW"},
                            {"tag": "Bottom UP", "title": "Bottom UP"},
                            {"tag": "Blow Mold CL", "title": "Blow Mold CL"},
                            {"tag": "Blow Mold OP", "title": "Blow Mold OP"},
                            {"tag": "Blow Core Hold FW", "title": "Blow Core Hold FW"},
                            {"tag": "Stretch Unit DW FA", "title": "Stretch Unit DW FA"},
                            {"tag": "Stretch Unit UP FA", "title": "Stretch Unit UP FA"},
                            {"tag": "Stretch Unit DW", "title": "Stretch Unit DW"},
                            {"tag": "Stretch Unit UP", "title": "Stretch Unit UP"},
                            {"tag": "Blow Mold M", "title": "Blow Mold M"},
                            {"tag": "Blow Mold C", "title": "Blow Mold C"},
                        ],
                    },
                ],
            },
            {
                "key": "production",
                "label": "Production",
                "sections": [
                    {"type": "production_dashboard"},
                ],
            },
        ],
    },

    "150DP": {
        "label": "150DP — ISBM",
        "tabs": [
            {
                "key": "general",
                "label": "General",
                "sections": [
                    {
                        "type": "metrics",
                        "items": [
                            {"tag": "Production Quantity", "title": "Production Count", "desc": "PLC register"},
                            {"tag": "Cycle Time", "title": "Cycle Time", "desc": "Current cycle", "unit": "s"},
                        ],
                    },
                    {"type": "live_production"},
                ],
            },
            {
                "key": "temps",
                "label": "Temperatures",
                "sections": [{"type": "temp_bars", "items": []}],
            },
            {
                "key": "production",
                "label": "Production",
                "sections": [{"type": "production_dashboard"}],
            },
        ],
    },

    "Chiller": {
        "label": "Chiller",
        "tabs": [
            {
                "key": "general",
                "label": "Overview",
                "sections": [
                    {
                        "type": "metrics",
                        "items": [
                            {"tag": "Supply Temp", "title": "Supply Temp", "unit": "\u00b0C"},
                            {"tag": "Return Temp", "title": "Return Temp", "unit": "\u00b0C"},
                            {"tag": "Flow Rate", "title": "Flow Rate", "unit": "L/min"},
                            {"tag": "Pressure", "title": "System Pressure", "unit": "bar"},
                        ],
                    },
                ],
            },
            {
                "key": "temps",
                "label": "Temperatures",
                "sections": [
                    {
                        "type": "temp_bars",
                        "items": [
                            {"label": "Supply", "pvTag": "Supply Temp", "svTag": "Supply Temp SV"},
                            {"label": "Return", "pvTag": "Return Temp", "svTag": "Return Temp SV"},
                        ],
                    },
                ],
            },
        ],
    },

    "Compressor": {
        "label": "Compressor",
        "tabs": [
            {
                "key": "general",
                "label": "Overview",
                "sections": [
                    {
                        "type": "metrics",
                        "items": [
                            {"tag": "Discharge Pressure", "title": "Discharge Pressure", "unit": "bar"},
                            {"tag": "Motor Current", "title": "Motor Current", "unit": "A"},
                            {"tag": "Oil Temp", "title": "Oil Temperature", "unit": "\u00b0C"},
                            {"tag": "Run Hours", "title": "Run Hours", "unit": "hrs"},
                        ],
                    },
                ],
            },
        ],
    },

    "Dryer": {
        "label": "Dryer",
        "tabs": [
            {
                "key": "general",
                "label": "Overview",
                "sections": [
                    {
                        "type": "metrics",
                        "items": [
                            {"tag": "Dew Point", "title": "Dew Point", "unit": "\u00b0C"},
                            {"tag": "Regen Temp", "title": "Regen Temperature", "unit": "\u00b0C"},
                            {"tag": "Tower Pressure", "title": "Tower Pressure", "unit": "bar"},
                        ],
                    },
                ],
            },
        ],
    },
}

# Same pattern as data.py: one global client, connect once
_opc_client: OPCClient | None = None
_alert_sweep_task: asyncio.Task | None = None


# ─── Alert sweep (merged from alert_collector.py) ───────────────────────────

def _create_alert_table():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alert_status (
                    machine_id   INT PRIMARY KEY,
                    alert_flag   INT NOT NULL DEFAULT 0,
                    alert_count  INT NOT NULL DEFAULT 0,
                    alerts       TEXT NOT NULL DEFAULT '[]',
                    updated_at   TIMESTAMP NOT NULL DEFAULT NOW()
                );
            """)


def _upsert_alert(machine_id: int, alert_flag: int, alert_count: int, alerts: list):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alert_status (machine_id, alert_flag, alert_count, alerts, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (machine_id) DO UPDATE SET
                    alert_flag  = EXCLUDED.alert_flag,
                    alert_count = EXCLUDED.alert_count,
                    alerts      = EXCLUDED.alerts,
                    updated_at  = EXCLUDED.updated_at
                """,
                (machine_id, alert_flag, alert_count, json.dumps(alerts), datetime.now()),
            )


def _sweep_alerts_sync():
    """One pass over TRACKED_MACHINES, reusing the FastAPI OPC cache."""
    if _opc_client is None:
        return
    for mid in TRACKED_MACHINES:
        try:
            info = information.get_machine(mid) or {"mold": 0, "cyc_limit": 0}
            values = _opc_client.read_machine(mid, MACHINES)
            if values:
                cycle_limits = {str(mid): info["cyc_limit"]}
                alerts, alert_flag = check_notifications(mid, values, cycle_limits)
                _upsert_alert(mid, alert_flag, len(alerts), alerts)
            else:
                _upsert_alert(mid, 0, 0, [])
        except Exception as e:
            print(f"Alert sweep error M{mid}: {e}")
            try:
                _upsert_alert(mid, 0, 0, [])
            except Exception:
                pass


async def _alert_sweep_loop():
    """Background task: alert sweep every ALERT_SWEEP_INTERVAL seconds."""
    try:
        while True:
            await asyncio.to_thread(_sweep_alerts_sync)
            await asyncio.sleep(ALERT_SWEEP_INTERVAL)
    except asyncio.CancelledError:
        raise


# ─── App setup ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _opc_client, _alert_sweep_task
    print("SCADA API starting up...")

    # 1. Connect
    print("Connecting to OPC server...")
    _opc_client = OPCClient(OPC_SERVER_URL)
    _opc_client.connect()
    print("OPC UA connected.")

    # 2. Subscribe to all tags for all tracked machines
    _opc_client.subscribe_machines(
        TRACKED_MACHINES, MACHINES,
        interval_ms=SUBSCRIPTION_INTERVAL_MS,
    )

    # 3. Warm up cache
    print(f"Warming up subscription cache ({WARMUP_SEC}s)...")
    time.sleep(WARMUP_SEC)

    for mid in TRACKED_MACHINES:
        with _opc_client.lock:
            count = len([k for k in _opc_client.cache.get(mid, {})
                         if not k.startswith("_")])
        print(f"  Machine {mid}: {count} tags cached")

    # 4. Start background alert sweep (replaces standalone alert_collector.py)
    _create_alert_table()
    _alert_sweep_task = asyncio.create_task(_alert_sweep_loop())
    print(f"Alert sweep started (every {ALERT_SWEEP_INTERVAL}s).")

    print("SCADA API ready.")
    yield

    # Shutdown
    if _alert_sweep_task:
        _alert_sweep_task.cancel()
        try:
            await _alert_sweep_task
        except (asyncio.CancelledError, Exception):
            pass

    if _opc_client:
        _opc_client.disconnect()
    print("SCADA API shut down.")


app = FastAPI(
    title="ISBM SCADA API",
    description="REST API for ISBM bottle manufacturing SCADA system.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═════════════════════════════════════════════════════════════════════════════════
# HEALTH / CONFIG
# ═════════════════════════════════════════════════════════════════════════════════

@app.get("/api/health", tags=["system"])
def health_check():
    return {
        "status": "ok",
        "opc_connected": _opc_client is not None and _opc_client.connected,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/config/machines", tags=["system"])
def get_tracked_machines():
    machines = []
    for mid in TRACKED_MACHINES:
        info = information.get_machine(mid)
        mold = info["mold"] if info else 0
        cyc_limit = info["cyc_limit"] if info else 0
        machines.append({
            "machine_id": mid,
            "mold": mold,
            "cycle_limit": cyc_limit,
            "bottle_type": get_bottle_type(int(mold)) if mold else None,
        })
    return {"machines": machines, "count": len(machines)}


@app.get("/api/config/mold-map", tags=["system"])
def get_mold_map():
    return {"mold_map": {str(k): v for k, v in MOLD_MAP.items()}}


@app.get("/api/machine-types", tags=["system"])
def get_machine_types():
    """Return dashboard layout config for all machine types."""
    return {"types": MACHINE_TYPE_LAYOUTS}


@app.get("/api/machine-types/{machine_type}", tags=["system"])
def get_machine_type_layout(machine_type: str):
    """Return dashboard layout config for a specific machine type."""
    layout = MACHINE_TYPE_LAYOUTS.get(machine_type)
    if not layout:
        raise HTTPException(status_code=404, detail=f"Unknown machine type: {machine_type}")
    return layout


# ═════════════════════════════════════════════════════════════════════════════════
# FLEET OVERVIEW
# ═════════════════════════════════════════════════════════════════════════════════

# No longer need _AUTO_CYCLE_TAGS — subscriptions cache ALL tags,
# so reading "Auto Cycle" is just a dict lookup now.


def _get_alert_flags() -> dict:
    """Read alert flags from DB. Returns {machine_id: {alert_flag, alert_count}}."""

    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT machine_id, alert_flag, alert_count FROM alert_status")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {r[0]: {"alert_flag": r[1], "alert_count": r[2]} for r in rows}
    except Exception:
        return {}


@app.get("/api/fleet/status", tags=["fleet"])
def fleet_status():
    """
    Live status for ALL tracked machines.
    - Auto Cycle from subscription cache (instant, no OPC round trips)
    - Alert flags from PostgreSQL (written by alert_collector.py)
    """
    alert_flags = _get_alert_flags()

    results = []
    for mid in TRACKED_MACHINES:
        try:
            info = information.get_machine(mid) or {"mold": 0, "cyc_limit": 0}

            # Read from subscription cache — no network call
            values = _opc_client.read_machine(mid, MACHINES)
            auto = values.get("Auto Cycle") if values else None

            # Get alert flag from DB (written by alert_collector.py)
            af = alert_flags.get(mid, {"alert_flag": 0, "alert_count": 0})

            if af["alert_flag"] == 1:
                status = 2
            elif auto == 1:
                status = 1
            else:
                status = 0

            # Determine machine type
            machine_type = MACHINE_REGISTRY.get(mid, {}).get("type", "70DPW")

            results.append({
                "machine_id":   mid,
                "machine_type": machine_type,
                "status":       status,
                "auto_cycle":   auto,
                "mold":         info["mold"],
                "cycle_limit":  info["cyc_limit"],
                "bottle_type":  get_bottle_type(int(info["mold"])) if info["mold"] else None,
                "alert_count":  af["alert_count"],
            })
        except Exception as e:
            machine_type = MACHINE_REGISTRY.get(mid, {}).get("type", "70DPW")
            results.append({
                "machine_id": mid, "machine_type": machine_type,
                "status": 0, "auto_cycle": None,
                "mold": 0, "cycle_limit": 0, "bottle_type": None,
                "alert_count": 0, "error": str(e),
            })

    return {"machines": results, "count": len(results)}


@app.get("/api/fleet/summary", tags=["fleet"])
def fleet_summary():
    try:
        data = get_multi_machine_live_summary(TRACKED_MACHINES)
        return {"machines": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fleet/alerts", tags=["fleet"])
def fleet_alerts():
    """
    All active alert messages across all machines.
    Read from alert_status table (written by alert_collector.py).
    Used by the scrolling alert strip on the dashboard.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT machine_id, alert_flag, alerts FROM alert_status WHERE alert_flag = 1"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        all_alerts = []
        for r in rows:
            machine_id = r[0]
            alerts = json.loads(r[2]) if r[2] else []
            for a in alerts:
                all_alerts.append({"machine_id": machine_id, "message": a})

        return {"alerts": all_alerts, "count": len(all_alerts)}
    except Exception:
        return {"alerts": [], "count": 0}


# ═════════════════════════════════════════════════════════════════════════════════
# OPC LIVE READS (now from subscription cache)
# ═════════════════════════════════════════════════════════════════════════════════

@app.get("/api/machines/{machine_id}/opc", tags=["opc"])
def machine_opc_all(machine_id: int):
    """
    Read ALL OPC tags for a single machine from subscription cache.
    Alert data comes from the alert_status DB table (written by alert_collector.py).
    """
    _validate_machine(machine_id)

    # Now reads from cache — was 200 network round trips, now instant
    values = _opc_client.read_machine(machine_id, MACHINES)
    if values is None:
        raise HTTPException(status_code=502, detail=f"No data from OPC for machine {machine_id}")

    values.pop("timestamp", None)
    values.pop("machine_id", None)

    info = information.get_machine(machine_id) or {"mold": 0, "cyc_limit": 0}
    mold = info["mold"]

    # Read alerts from DB (written by alert_collector.py)
    alerts, alert_flag = [], 0
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT alert_flag, alerts FROM alert_status WHERE machine_id = %s",
            (machine_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            alert_flag = row[0]
            alerts = json.loads(row[1]) if row[1] else []
    except Exception:
        pass

    auto = values.get("Auto Cycle")
    if alert_flag == 1:
        status = "alerts"
    elif auto == 1:
        status = "running"
    else:
        status = "stopped"

    # Determine machine type and layout for the frontend
    machine_type = MACHINE_REGISTRY.get(machine_id, {}).get("type", "70DPW")
    layout = MACHINE_TYPE_LAYOUTS.get(machine_type, MACHINE_TYPE_LAYOUTS["70DPW"])

    return {
        "machine_id":   machine_id,
        "machine_type": machine_type,
        "type_label":   layout["label"],
        "layout":       layout,
        "status":       status,
        "mold":         mold,
        "cycle_limit":  info["cyc_limit"],
        "bottle_type":  get_bottle_type(int(mold)) if mold else None,
        "alerts":       alerts,
        "alert_count":  len(alerts),
        "tags":         values,
    }


# ═════════════════════════════════════════════════════════════════════════════════
# MACHINE INFO
# ═════════════════════════════════════════════════════════════════════════════════

@app.get("/api/machines/{machine_id}/info", tags=["config"])
def machine_info(machine_id: int):
    _validate_machine(machine_id)
    info = information.get_machine(machine_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not in info DB")
    mold = info["mold"]
    return {
        "machine_id":  machine_id,
        "mold":        mold,
        "cycle_limit": info["cyc_limit"],
        "bottle_type": get_bottle_type(int(mold)) if mold else None,
    }


@app.put("/api/machines/{machine_id}/info", tags=["config"])
def update_machine_info(machine_id: int, mold: int, cycle_limit: int):
    _validate_machine(machine_id)
    try:
        information.update_machine(number=machine_id, mold=mold, cyc_limit=cycle_limit)
        return {
            "machine_id":  machine_id,
            "mold":        mold,
            "cycle_limit": cycle_limit,
            "bottle_type": get_bottle_type(mold),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═════════════════════════════════════════════════════════════════════════════════
# LIVE DB ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════════

@app.get("/api/machines/{machine_id}/live", tags=["live"])
def machine_live(machine_id: int):
    _validate_machine(machine_id)
    try:
        prod = get_live_production(machine_id)
        dt = get_live_downtime(machine_id)

        elapsed_today = _elapsed_today_seconds()
        avail_pct = round(
            max(0, (elapsed_today - dt["total_downtime_seconds"]) / elapsed_today * 100), 2
        ) if elapsed_today > 0 else 100.0

        return {
            "machine_id":             machine_id,
            "mold_id":                dt["mold_id"] or prod["mold_id"],
            "date":                   dt["date"],
            "total_bottles":          prod["total_bottles"],
            "total_downtime_seconds": dt["total_downtime_seconds"],
            "total_downtime_minutes": dt["total_downtime_minutes"],
            "total_downtime_hours":   dt["total_downtime_hours"],
            "event_count":            dt["event_count"],
            "availability_pct":       avail_pct,
            "elapsed_today_seconds":  round(elapsed_today, 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/machines/{machine_id}/live/production", tags=["live"])
def machine_live_production(machine_id: int):
    _validate_machine(machine_id)
    try:
        return get_live_production(machine_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/machines/{machine_id}/live/downtime", tags=["live"])
def machine_live_downtime(machine_id: int):
    _validate_machine(machine_id)
    try:
        return get_live_downtime(machine_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═════════════════════════════════════════════════════════════════════════════════
# DOWNTIME EVENTS
# ═════════════════════════════════════════════════════════════════════════════════

@app.get("/api/machines/{machine_id}/downtime-events", tags=["downtime"])
def machine_downtime_events(
    machine_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
):
    _validate_machine(machine_id)
    try:
        events = get_today_downtime_events(machine_id, limit=limit)
        return {"machine_id": machine_id, "events": events, "count": len(events)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═════════════════════════════════════════════════════════════════════════════════
# SHIFT DOWNTIME
# ═════════════════════════════════════════════════════════════════════════════════

@app.get("/api/machines/{machine_id}/shifts/today", tags=["shifts"])
def machine_shift_downtime(machine_id: int):
    _validate_machine(machine_id)
    try:

        today = date.today()
        now_h = datetime.now().hour
        cur_shift = 1 if now_h < 8 else 2 if now_h < 16 else 3

        conn = get_conn()
        cur = conn.cursor()

        result = {1: (0.0, 0), 2: (0.0, 0), 3: (0.0, 0)}

        cur.execute(
            """SELECT shift_1_downtime_seconds, shift_1_events,
                      shift_2_downtime_seconds, shift_2_events,
                      shift_3_downtime_seconds, shift_3_events
               FROM daily_archive
               WHERE machine_id = %s AND date = %s""",
            (machine_id, today),
        )
        row = cur.fetchone()
        if row:
            result[1] = (float(row[0]), int(row[1]))
            result[2] = (float(row[2]), int(row[3]))
            result[3] = (float(row[4]), int(row[5]))

        cur.execute(
            """SELECT total_downtime_seconds, event_count
               FROM shift_downtime_live
               WHERE machine_id = %s AND date = %s AND shift = %s""",
            (machine_id, today, cur_shift),
        )
        live_row = cur.fetchone()
        if live_row:
            result[cur_shift] = (float(live_row[0]), int(live_row[1]))

        cur.close()
        conn.close()

        shifts = []
        for s in [1, 2, 3]:
            secs, ev = result[s]
            shifts.append({
                "shift":                  s,
                "total_downtime_seconds": round(secs, 1),
                "total_downtime_minutes": round(secs / 60, 2),
                "event_count":            ev,
                "is_active":              s == cur_shift,
            })

        return {"machine_id": machine_id, "date": today.isoformat(), "shifts": shifts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═════════════════════════════════════════════════════════════════════════════════
# ARCHIVE / HISTORICAL
# ═════════════════════════════════════════════════════════════════════════════════

@app.get("/api/machines/{machine_id}/archive", tags=["archive"])
def machine_archive(
    machine_id: int,
    start: Optional[str] = Query(default=None, description="Start date YYYY-MM-DD"),
    end: Optional[str] = Query(default=None, description="End date YYYY-MM-DD"),
    days: int = Query(default=30, ge=1, le=365, description="Lookback days (if start/end omitted)"),
):
    _validate_machine(machine_id)
    try:
        if start and end:
            start_date = date.fromisoformat(start)
            end_date = date.fromisoformat(end)
        else:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT date, mold_id, total_bottles,
                      total_downtime_seconds, downtime_event_count,
                      shift_1_downtime_seconds, shift_1_events,
                      shift_2_downtime_seconds, shift_2_events,
                      shift_3_downtime_seconds, shift_3_events
               FROM daily_archive
               WHERE machine_id = %s AND date BETWEEN %s AND %s
               ORDER BY date DESC""",
            (machine_id, start_date, end_date),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        data = []
        for r in rows:
            dt_sec = float(r[3])
            data.append({
                "date":                     r[0].isoformat(),
                "mold_id":                  r[1],
                "total_bottles":            r[2],
                "total_downtime_seconds":   round(dt_sec, 1),
                "total_downtime_minutes":   round(dt_sec / 60, 2),
                "downtime_event_count":     r[4],
                "availability_pct":         round(max(0, (86400 - dt_sec) / 86400 * 100), 2),
                "shift_1_downtime_seconds": round(float(r[5]), 1),
                "shift_1_events":           int(r[6]),
                "shift_2_downtime_seconds": round(float(r[7]), 1),
                "shift_2_events":           int(r[8]),
                "shift_3_downtime_seconds": round(float(r[9]), 1),
                "shift_3_events":           int(r[10]),
            })

        return {
            "machine_id": machine_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": data,
            "count": len(data),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═════════════════════════════════════════════════════════════════════════════════
# CYCLE DATA
# ═════════════════════════════════════════════════════════════════════════════════

@app.get("/api/machines/{machine_id}/cycles", tags=["cycles"])
def machine_cycles(
    machine_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    mold_id: Optional[int] = Query(default=None),
):
    _validate_machine(machine_id)
    try:

        from psycopg2.extras import RealDictCursor

        conn = get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        query = "SELECT id, machine_id, timestamp, mold_id, data FROM machine_data WHERE machine_id = %s"
        params = [machine_id]

        if mold_id is not None:
            query += " AND mold_id = %s"
            params.append(mold_id)

        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        results = [{
            "id":         r["id"],
            "machine_id": r["machine_id"],
            "timestamp":  r["timestamp"].isoformat(),
            "mold_id":    r["mold_id"],
            "data":       r["data"],
        } for r in rows]

        return {"machine_id": machine_id, "cycles": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═════════════════════════════════════════════════════════════════════════════════
# WEEKLY REPORT PDF
# ═════════════════════════════════════════════════════════════════════════════════

@app.get("/api/report/weekly", tags=["report"])
def weekly_report_pdf(
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
):
    """
    Generate a weekly production report PDF and stream it back.

    The PDF is built in memory (no temp files) from daily_archive
    and machine_data tables, then returned as application/pdf.
    The browser can display it inline or the user can download it.
    """
    import io
    import os

    from fastapi.responses import StreamingResponse

    # ── Validate dates ───────────────────────────────────────────────────
    try:
        start_date = date.fromisoformat(start)
        end_date   = date.fromisoformat(end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end must be >= start")
    if (end_date - start_date).days > 31:
        raise HTTPException(status_code=400, detail="Max range is 31 days")

    # ── Import report module ─────────────────────────────────────────────
    from report.weekly_report import WeeklyData, DailyRecord, CycleRecord, build_report

    # ── Pull data from DB ────────────────────────────────────────────────
    conn = get_conn()

    daily_records = []
    machine_id_set = set()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT machine_id, mold_id, date,
                   total_bottles, total_downtime_seconds, downtime_event_count,
                   shift_1_downtime_seconds, shift_1_events,
                   shift_2_downtime_seconds, shift_2_events,
                   shift_3_downtime_seconds, shift_3_events
            FROM daily_archive
            WHERE date BETWEEN %s AND %s
            ORDER BY machine_id, date
        """, (start_date, end_date))

        for row in cur.fetchall():
            machine_id_set.add(row[0])
            daily_records.append(DailyRecord(
                machine_id=row[0], mold_id=row[1], date=row[2],
                total_bottles=row[3] or 0,
                total_downtime_seconds=row[4] or 0.0,
                downtime_event_count=row[5] or 0,
                shift_1_downtime_sec=row[6] or 0.0,
                shift_1_events=row[7] or 0,
                shift_2_downtime_sec=row[8] or 0.0,
                shift_2_events=row[9] or 0,
                shift_3_downtime_sec=row[10] or 0.0,
                shift_3_events=row[11] or 0,
            ))

    cycle_records = []

    with conn.cursor() as cur:
        cur.execute("""
            SELECT machine_id, mold_id, timestamp::date AS day,
                   data->>'Cycle Time'     AS cycle_time,
                   data->>'Dry Cycle Time' AS dry_cycle_time,
                   data->>'V-P Time PV'    AS vp_time
            FROM machine_data
            WHERE timestamp >= %s
              AND timestamp <  %s + INTERVAL '1 day'
            ORDER BY machine_id, timestamp
        """, (start_date, end_date))

        def _to_float(v):
            if v is None:
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        for row in cur.fetchall():
            machine_id_set.add(row[0])
            cycle_records.append(CycleRecord(
                machine_id=row[0], mold_id=row[1], timestamp=row[2],
                cycle_time=_to_float(row[3]),
                dry_cycle_time=_to_float(row[4]),
                vp_time=_to_float(row[5]),
            ))

    conn.close()

    if not daily_records and not cycle_records:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {start} to {end}",
        )

    data = WeeklyData(
        week_start=start_date, week_end=end_date,
        daily_records=daily_records, cycle_records=cycle_records,
        machine_ids=sorted(machine_id_set),
    )

    # ── Generate PDF into memory ─────────────────────────────────────────
    buf = io.BytesIO()
    build_report(data, buf)
    buf.seek(0)

    filename = f"weekly_report_{start}_to_{end}.pdf"

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ═════════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════════

def _validate_machine(machine_id: int):
    if machine_id not in TRACKED_MACHINES:
        raise HTTPException(
            status_code=404,
            detail=f"Machine {machine_id} not tracked. Available: {TRACKED_MACHINES}",
        )


def _elapsed_today_seconds() -> float:
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return (now - midnight).total_seconds()