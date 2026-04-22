# ISBM SCADA Project — Technical Documentation

Real-time monitoring, tracking, alerting, and reporting platform for an Injection Stretch Blow Molding (ISBM) plant. Reads live tags from PLCs via OPC UA, persists cycle-level history in PostgreSQL, exposes the data through a FastAPI service, and renders it on a React dashboard.

> Scope of this document: OPC layer, database, tracking services, notifications, FastAPI backend, React frontend, and the weekly PDF report. The Streamlit dashboard (`Dashboard/`) and ML components (`ML/`, `database/ml.py`, `database/trainml.py`, `database/testml.py`, `database/scaling.py`, `database/plot.py`, `*.pkl`) are intentionally excluded.

---

## 1. System Architecture

```
┌───────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   PLCs /      │ OPC │  OPC UA      │     │  PostgreSQL  │     │   React      │
│   Machines    │────►│  Server      │◄────│              │◄────│   Dashboard  │
│  (1, 22–68)   │ UA  │ 52250        │     │  postgres    │     │  (Vite 5173) │
└───────────────┘     └───────┬──────┘     └──────┬───────┘     └──────┬───────┘
                              │                    ▲                     ▲
                              ▼                    │                     │
                      ┌───────────────┐            │                     │
                      │ tracking_     │────────────┤                     │
                      │ runner.py     │            │                     │
                      │ (downtime +   │            │                     │
                      │  production)  │            │                     │
                      └───────────────┘            │                     │
                              │                    │                     │
                              ▼                    │                     │
                      ┌───────────────┐            │                     │
                      │ FastAPI       │────────────┴─────────────────────┘
                      │ (uvicorn 8000)│     HTTP / JSON, polling
                      └───────┬───────┘
                              │
                              ▼
                      ┌───────────────┐
                      │ Notifications │───► WhatsApp (Twilio)
                      │  + Weekly PDF │
                      └───────────────┘
```

**Data flow per cycle:**
1. PLC publishes tag values → OPC UA server (`opc.tcp://localhost:52250`).
2. FastAPI subscribes on startup (250 ms); all reads hit an in-memory cache.
3. `tracking_runner.py` polls the cache every 0.5 s and commits state transitions to Postgres.
4. React polls FastAPI (10 s fleet view, 5 s machine view) and renders.

---

## 2. Repository Layout

```
ISBM Project/
├── database/                 OPC client, DB schema, cycle logger
│   ├── opc_client.py         python-opcua wrapper + scaling + idle filter
│   ├── tags.py               MACHINES dict, OPC_SERVER_URL, SCALING_MAP
│   ├── cycle_logger.py       Buffers reads, writes on cycle-end to machine_data
│   ├── db.py                 Low-level connection helpers
│   ├── setup_db.py           Table creation
│   ├── data.py               Raw-data read helpers
│   └── auto.py               Auto-cycle production config
├── tracking/                 Downtime + production microservices
│   ├── tracking_runner.py    Main loop (13 machines, 0.5 s)
│   ├── downtime_tracker.py   DowntimeTracker class, shift rollover
│   ├── production_counter.py ProductionCounter class
│   ├── dashboard_queries.py  Read APIs for the dashboard
│   ├── live_display.py       Terminal UI (debug only)
│   └── setup_tracking_tables.py
├── Notifications/            Alert generation + delivery
│   ├── notifs.py             check_notifications() — thresholds
│   ├── alert_collector.py    Writes alert_status table
│   ├── notifis_collector.py  Terminal collector
│   ├── whatsapp.py           Twilio WhatsApp sender
│   └── limits.py             CYCLE time limits per machine
├── fastapi/
│   └── main.py               All REST endpoints + OPC lifespan
├── scada-dashboard/          React + Vite frontend
│   ├── src/App.jsx           Single-file app
│   ├── vite.config.js        host: true (0.0.0.0:5173)
│   └── .env                  VITE_API_URL
├── report/
│   └── weekly_report.py      ReportLab PDF generator
└── requirements.txt
```

---

## 3. OPC UA Layer

### 3.1 Server & connection

- **URL:** `opc.tcp://localhost:52250` (constant in `database/tags.py`).
- **Client library:** `opcua==0.98.13`.
- **Node ID format:** `ns=2;s=Machine {id}.{tag_name}` (e.g. `ns=2;s=Machine 60.Cycle Time`).

### 3.2 `MACHINES` dict

- Keys: integer machine IDs (`1, 18, 22–68`).
- Values: `{tag_name: node_id}` mapping per machine — ~170 tags each.

Representative tag groups:

| Group | Example tags |
|---|---|
| Cycle state | `Auto Cycle`, `Cycle Time`, `V-P Time PV`, `Charge Time`, `Dry Cycle Time` |
| Injection / blow | `Main Ram FW Pressure`, `Blow Mold CL FA Pressure`, `Injection Time`, `Cooling Time`, `Stretch Time`, `Blow Time` |
| Screw | `Shot Size SV`, `Screw Set Data 1–2 Pressure`, `Screw Position`, `Screw Pressure Monitor` |
| Temperatures | `Barrel Rear/Middle/Front/Nozzle PV/SV` (4 pairs), `HR Block 1–4 PV/SV`, `HR Nozzle 1–24 PV/SV`, `H Pot 1–40 PV/SV`, `Oil Temperature PV/SV` |
| Production | `Production Quantity` (cumulative, cavity-weighted by the PLC) |

`SCALING_MAP` divides raw integer values into engineering units (`tags.py`).

### 3.3 `OPCClient` (`database/opc_client.py`)

| Method | Returns | Notes |
|---|---|---|
| `__init__(url, scale_map)` | — | Raises `RuntimeError` if the server is unreachable. |
| `connect()` | — | Idempotent; flips `self.connected`. |
| `disconnect()` | — | Graceful close. |
| `read_machine(machine_id, tag_map)` | `dict` | Reads all tags; applies scaling; maps idle-state sentinel (`PV == 660`) to `None` for both PV and SV; appends `machine_id` and `timestamp`. |
| `subscribe_machines(ids, tag_map, interval_ms)` | — | OPC UA server-push subscription; updates an internal cache. Used by FastAPI. |

The subscription cache eliminates OPC round-trips from the REST path — every `/api/...` call is an in-process dict read.

---

## 4. PostgreSQL Database

### 4.1 Connection parameters

Hardcoded across modules:

```
host=localhost, dbname=postgres, user=postgres, password=admin, port=5432
```

`database/db.py` legacy helper uses port `54321`; prefer the tracking/FastAPI values.

### 4.2 Tables

| Table | Purpose | Key columns |
|---|---|---|
| `machine_data` | One row per completed cycle; raw + aggregated tags. | `id` PK, `machine_id`, `timestamp`, `mold_id`, `data JSONB` |
| `downtime_events` | Closed downtime intervals. | `id` PK, `machine_id`, `mold_id`, `start_time`, `end_time`, `duration_seconds` |
| `daily_downtime_live` | Running daily total while day is in progress. | `(machine_id, date)` PK, `mold_id`, `total_downtime_seconds` |
| `shift_downtime_live` | Running per-shift total (shift = 1/2/3 on 8-hour boundaries). | `(machine_id, date, shift)` PK, `mold_id`, `total_downtime_seconds`, `event_count` |
| `production_live` | Running daily bottle count. | `(machine_id, date)` PK, `mold_id`, `total_bottles` |
| `daily_archive` | End-of-day snapshot. | `(machine_id, date)` PK, `mold_id`, `total_bottles`, `total_downtime_seconds`, `downtime_event_count`, `shift_{1,2,3}_downtime_seconds`, `shift_{1,2,3}_events` |
| `alert_status` | Active alert list per machine. | `machine_id` PK, `alert_flag`, `alert_count`, `alerts JSONB` |

### 4.3 `cycle_logger.py`

- Buffers every OPC read for a machine in memory.
- Detects **cycle end** when `Cycle Time` changes value.
- `aggregate_cycle()` computes max/mean over the buffer across ~30 fields (times, pressures, temperatures, positions) and inserts one row into `machine_data`.
- Driven from the 0.5 s OPC poll.

### 4.4 `database/auto.py`

- Declares `PRODUCTION` — a small subset of machines (`1, 58–61`) with the `Auto Cycle` tag mapping.
- Used as a lightweight config import by production-counting utilities; not a runnable script.

---

## 5. Tracking Services

### 5.1 `tracking_runner.py` (main entrypoint)

- Tracks machines `[1, 22, 23, 24, 25, 26, 57, 58, 59, 60, 61, 62, 68]`.
- On startup:
  - Subscribes to OPC tags via `OPCClient`.
  - Reconciles `daily_archive` and `production_archive` against live state.
  - Spins up one `DowntimeTracker` and one `ProductionCounter` per machine.
- Loop (every 0.5 s):
  - `downtime_trackers[m].update(auto_cycle, mold, timestamp)`
  - `production_counters[m].notify_cycle(delta, mold, ts)` on cycle completion.
- Flushes state on `Ctrl+C`.

### 5.2 `downtime_tracker.py` — `DowntimeTracker`

State machine driven by the `Auto Cycle` tag:

| Event | Action |
|---|---|
| `auto_cycle` 1 → 0 | Open a downtime event (`_is_down=True`, record `downtime_start`). |
| `auto_cycle` 0 → 1 | Close event, insert into `downtime_events`, increment `daily_downtime_live` + `shift_downtime_live`. |
| **Midnight rollover** | Write full `daily_archive` row (with all 3 shifts), reset daily counters. |
| **Shift rollover** (every 8 h) | Close any open event at the boundary, flush `shift_downtime_live`, reset shift counter. |

`live_state()` returns: `machine_id`, `mold_id`, `is_down`, `downtime_start`, `current_event_sec`, `total_downtime_sec/min/hr`, `shift`, `shift_downtime_sec/min`, `shift_event_count`.

### 5.3 `production_counter.py` — `ProductionCounter`

- Reads the PLC's `Production Quantity` (already cavity-weighted by the machine).
- Upserts to `production_live` every 10 bottles (crash-resilient).
- Full flush to `daily_archive` at midnight.
- `bottles_per_hour()` — rolling 1-hour ring-buffer rate.
- `live_state()` returns `machine_id`, `date`, `bottles_today`, `bottles_per_hour`.

### 5.4 `dashboard_queries.py` — read APIs

| Function | Returns |
|---|---|
| `get_live_downtime(machine_id)` | Today's committed downtime seconds + event count. |
| `get_live_production(machine_id)` | Today's bottle count. |
| `get_today_downtime_events(machine_id, limit)` | Completed downtime intervals, newest first. |
| `get_archive_range(machine_id, start, end)` | Daily archive rows for the range (availability/OEE). |

### 5.5 `live_display.py`

Curses-style terminal dashboard for a single machine (default 60). Polls the OPC cache every 0.5 s, repaints every 1 s. Used for on-box debugging; not part of the production data path.

---

## 6. Notifications

### 6.1 `notifs.py` — `check_notifications(data)`

Rule engine. Returns `(alerts_list, alert_flag)` where `alert_flag ∈ {0, 1}`.

| Rule | Trigger |
|---|---|
| Temperature deviation | Any PV/SV pair (across ~70 sensors) with relative deviation > 5%. |
| Cycle overrun | `Cycle Time` exceeds the per-machine limit in `limits.CYCLE`. |
| Oil temperature | `Oil Temperature PV` vs `SV` difference ≤ 30 °C. |

### 6.2 `alert_collector.py`

Runs alerts through `check_notifications()` and upserts `alert_status` (`alert_flag`, `alert_count`, `alerts JSONB`). Consumed by `/api/machines/{id}/opc` and `/api/fleet/alerts`.

### 6.3 `notifis_collector.py`

Terminal log collector — polls machine 60 every 20 s via `OPCClient`, prints alerts. No DB writes or messaging.

### 6.4 `whatsapp.py`

- Library: `twilio.rest.Client(account_sid, auth_token)`.
- Endpoint: `client_w.messages.create(body=..., from_='whatsapp:+14155238886', to='whatsapp:+12176932291')`.
- Sends the alerts list as the message body. No rate limiting or deduplication — wrap calls in your own dedupe logic before enabling in production.

### 6.5 `limits.py`

`CYCLE: dict[str, float]` — per-machine cycle-time ceilings, e.g. `"1": 15.0`, `"60": 10.0`. Keys are stringified machine IDs.

---

## 7. FastAPI Backend (`fastapi/main.py`)

### 7.1 Lifespan

- `@asynccontextmanager` startup:
  1. Instantiate `OPCClient`, connect to `opc.tcp://localhost:52250`.
  2. `subscribe_machines(TRACKED_MACHINES, interval_ms=250)`.
  3. Sleep ~3 s to let the subscription cache warm up.
- All endpoint reads hit the cache — no OPC round-trips on the request path.

### 7.2 CORS

Configured via `allow_origin_regex` for localhost and all RFC 1918 ranges (10/8, 172.16/12, 192.168/16). Credentials enabled.

### 7.3 Endpoints

**System / config**

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | OPC connection status + timestamp. |
| GET | `/api/config/machines` | Tracked machines with mold, cycle_limit, bottle_type. |
| GET | `/api/config/mold-map` | Mold ID → bottle-type lookup. |
| GET | `/api/machine-types` | Layout configs for all machine types (70DPW, 150DP, Chiller, Compressor). |
| GET | `/api/machine-types/{type}` | Layout config for a single type. |

**Fleet**

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/fleet/status` | Status (0 stopped / 1 running / 2 alerts), auto_cycle, mold, bottle_type, alert_count per machine. |
| GET | `/api/fleet/summary` | Multi-machine live totals (bottles, downtime, availability). |
| GET | `/api/fleet/alerts` | Active alerts across all machines (ticker strip). |

**Machine detail**

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/machines/{id}/opc` | All OPC tags + layout + alerts for one machine. |
| GET | `/api/machines/{id}/info` | Mold, cycle_limit, bottle_type. |
| PUT | `/api/machines/{id}/info` | Update mold and cycle_limit (`?mold=&cycle_limit=`). |
| GET | `/api/machines/{id}/live` | Today's bottles + downtime + availability %. |
| GET | `/api/machines/{id}/live/production` | Today's bottle count only. |
| GET | `/api/machines/{id}/live/downtime` | Today's downtime + event count only. |
| GET | `/api/machines/{id}/downtime-events` | Today's completed downtime intervals. |
| GET | `/api/machines/{id}/shifts/today` | Per-shift downtime + event count; active shift flagged. |
| GET | `/api/machines/{id}/archive` | Daily archive rows (default 30 days); includes shift split + availability. |
| GET | `/api/machines/{id}/cycles` | Recent `machine_data` cycles (`?limit=&mold_id=`). |

**Report**

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/report/weekly` | Stream `application/pdf` for `?start=&end=` (max 31 days). |

### 7.4 Runtime

```bash
cd fastapi
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Host on `0.0.0.0` for LAN access. Windows Firewall rule required — see §10.

---

## 8. React Frontend (`scada-dashboard/`)

### 8.1 Stack

- React 19 + Vite 8.
- Charts: `recharts`.
- Single-file app in `src/App.jsx`.

### 8.2 Configuration

- `vite.config.js`: `server: { host: true, port: 5173 }` — binds to `0.0.0.0`.
- `src/App.jsx`: `const API = import.meta.env.VITE_API_URL || "http://10.20.0.19:8000";`
- `.env`: `VITE_API_URL=http://10.20.0.19:8000` — change when the backend host/IP changes and restart `npm run dev`.

### 8.3 Polling intervals

| Constant | Value | Scope |
|---|---|---|
| `POLL_FLEET` | 10 000 ms | Fleet overview |
| `POLL_MACHINE` | 5 000 ms | Single-machine detail |

### 8.4 Screens and endpoint usage

**HomePage (fleet overview)**
- Grid of machine status cards, scrolling alert ticker, sidebar.
- Calls (every 10 s): `/api/fleet/status`, `/api/fleet/alerts`.

**MachinePage (machine detail)**
- Tabs per layout (General / Temps / Injection / Blow / Pressures / Cycle Monitor / Production).
- Charts: Cycle Time, Production Rate, Downtime trend, 30-day availability.
- Edit modal: mold + cycle_limit.
- Calls (every 5 s): `/api/machines/{id}/opc`, `/api/machines/{id}/live`, `/api/machines/{id}/shifts/today`, `/api/machines/{id}/archive?days=30`, `/api/machines/{id}/cycles?limit=500`.
- On save: `PUT /api/machines/{id}/info?mold=&cycle_limit=`.

**ReportSection**
- Date range picker; fetches `/api/report/weekly?start=&end=`, displays inline or downloads.

### 8.5 Build vs dev

- `npm run dev` — Vite dev server (HMR, source maps). Dev/staging only.
- `npm run build` — minified static bundle in `dist/`. Serve with nginx/IIS for production.
- `npm run preview` — quick static preview of `dist/`.

---

## 9. Weekly Report (`report/weekly_report.py`)

- **Engine:** ReportLab.
- **Output:** PDF containing:
  - Title + date range.
  - Daily production summary table (bottles, downtime, events per shift).
  - Cycle time / dry cycle time / V-P time charts (LinePlot).
  - Availability / OEE metrics.
  - Shift-level breakdowns.
  - Threshold colors: green (>95% availability), yellow (85–95%), red (<85%).
- **Triggers:**
  - HTTP: `GET /api/report/weekly?start=YYYY-MM-DD&end=YYYY-MM-DD` (max 31 days).
  - CLI: `python report/weekly_report.py [--week DATE] [--sample] [--output FILE]`.
- **Sources:** `daily_archive` + `machine_data`.

---

## 10. Deployment Notes

### 10.1 Prerequisites

- Python 3.11+, `pip install -r requirements.txt`.
- Node 20+ for the frontend, `npm install` in `scada-dashboard/`.
- PostgreSQL reachable on `localhost:5432` with the credentials in §4.1.
- OPC UA server reachable on `opc.tcp://localhost:52250`.

### 10.2 First-time DB setup

```bash
python database/setup_db.py
python tracking/setup_tracking_tables.py
```

### 10.3 Running on a LAN

1. **Backend:** `uvicorn main:app --host 0.0.0.0 --port 8000` from `fastapi/`.
2. **Frontend:** `npm run dev` from `scada-dashboard/` (already `--host`).
3. **Tracking service:** `python tracking/tracking_runner.py`.
4. **Firewall** (Administrator PowerShell):
   ```powershell
   New-NetFirewallRule -DisplayName "FastAPI 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Any
   New-NetFirewallRule -DisplayName "Vite 5173"    -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow -Profile Any
   ```
5. Access from any LAN device: `http://<host-ip>:5173`.

### 10.4 Known gotchas

- **Hardcoded DB password** (`admin`) — move to an env var before exposing beyond the plant network.
- **Hardcoded host IP** in `.env` — DHCP changes will break the React app; prefer a static lease or DNS name.
- **Twilio credentials** in `whatsapp.py` — must come from env vars, never commit them.
- **OPC idle sentinel** — a `PV == 660` reading is treated as "idle" and nulled in `OPCClient.read_machine`; don't change this without auditing the notification rules in `notifs.py`.
- **Cycle-end detection** depends on the `Cycle Time` tag value actually changing — if a machine reports a steady value mid-cycle, the logger will hold the buffer open. Monitor `machine_data` row rate per machine as a health check.
- **Background tracker vs FastAPI** both subscribe to OPC independently — if you scale out, consolidate to one subscriber and let others read from a shared cache or Redis.

---

## 11. Quick Reference — Ports & Services

| Service | Port | Host |
|---|---|---|
| OPC UA server | 52250 | localhost |
| PostgreSQL | 5432 | localhost |
| FastAPI (uvicorn) | 8000 | 0.0.0.0 |
| Vite dev server | 5173 | 0.0.0.0 |
