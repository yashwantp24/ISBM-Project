import { useState, useEffect, useCallback, useMemo } from "react";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid, Brush, ReferenceArea } from "recharts";

// ─── Config ──────────────────────────────────────────────────────────────────
const API = import.meta.env.VITE_API_URL || "http://10.20.0.19:8000";
const POLL_FLEET = 10000;
const POLL_MACHINE = 5000;
const SIDEBAR_W = 220;
const SIDEBAR_COLLAPSED_W = 56;

const SHIFT_LABELS = {
  1: { name: "Shift 1", hours: "00:00 – 08:00" },
  2: { name: "Shift 2", hours: "08:00 – 16:00" },
  3: { name: "Shift 3", hours: "16:00 – 00:00" },
};

// ─── Fetch helper ────────────────────────────────────────────────────────────
async function api(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ─── Color helpers ───────────────────────────────────────────────────────────
const dtColor = (min) => min < 30 ? "#00c853" : min < 90 ? "#ffd600" : "#d50000";
const availColor = (pct) => pct >= 95 ? "#00c853" : pct >= 85 ? "#ffd600" : "#d50000";

function tempBarColor(pv, sv) {
  if (!sv || sv === 0) return { pct: 0, color: "#555" };
  const pct = Math.max(0, Math.min(1, pv / sv));
  const diff = Math.abs(sv - pv) / sv * 100;
  return { pct, color: diff <= 5 ? "#00c853" : diff <= 10 ? "#ffd600" : "#d50000" };
}

const STATUS_MAP = {
  0: { label: "Stopped", dot: "#FF4B4B", bg: "#FF4B4B", text: "#fff" },
  1: { label: "Running", dot: "#1DB954", bg: "#1DB954", text: "#fff" },
  2: { label: "Alerts", dot: "#ffd600", bg: "#ffd600", text: "#000" },
  running: { label: "Running", dot: "#1DB954", bg: "#1DB954", text: "#fff" },
  stopped: { label: "Stopped", dot: "#FF4B4B", bg: "#FF4B4B", text: "#fff" },
  alerts: { label: "Alerts", dot: "#ffd600", bg: "#ffd600", text: "#000" },
};

// ─── Shared Styles ───────────────────────────────────────────────────────────
const S = {
  page: { minHeight: "100vh", background: "#0a0a0b", color: "#e0e6ed", fontFamily: "'Montserrat', sans-serif" },
  grid: { display: "flex", flexWrap: "wrap", gap: 14 },
  card: { background: "#131316", border: "1px solid #1e2030", borderRadius: 12, padding: "16px 20px", flex: 1, minWidth: 200 },
  cardTitle: { fontSize: 11, color: "#8899aa", fontWeight: 600, marginBottom: 4, textTransform: "uppercase", letterSpacing: 1.2 },
  cardValue: { fontSize: 28, fontWeight: 700, color: "#fff", margin: 0 },
  cardDesc: { fontSize: 11, color: "#667788", marginTop: 2 },
  pill: (bg) => ({ display: "inline-block", padding: "4px 12px", borderRadius: 8, background: bg, color: "#fff", fontSize: 12, fontWeight: 600, letterSpacing: 0.3 }),
  tab: (active) => ({
    padding: "10px 18px", cursor: "pointer", fontSize: 13, fontWeight: 600,
    color: active ? "#4ea8de" : "#667788",
    borderBottom: active ? "2px solid #4ea8de" : "2px solid transparent",
    background: "transparent", border: "none", borderBottomStyle: "solid",
    letterSpacing: 0.3, transition: "all 0.2s", fontFamily: "'Montserrat', sans-serif",
  }),
  btn: {
    padding: "8px 18px", borderRadius: 8, border: "1px solid #2a2e3e",
    background: "#181a24", color: "#c8d3df", cursor: "pointer", fontSize: 13,
    fontWeight: 600, transition: "all 0.15s", fontFamily: "'Montserrat', sans-serif",
  },
  btnPrimary: {
    padding: "8px 18px", borderRadius: 8, border: "none", background: "#4ea8de",
    color: "#000", cursor: "pointer", fontSize: 13, fontWeight: 700,
    fontFamily: "'Montserrat', sans-serif",
  },
  input: {
    padding: "10px 12px", borderRadius: 8, border: "1px solid #2a2e3e",
    background: "#0f1019", color: "#e0e6ed", fontSize: 14, width: "100%",
    outline: "none", fontFamily: "'Montserrat', sans-serif",
  },
  sectionTitle: { fontSize: 16, fontWeight: 700, color: "#fff", display: "flex", alignItems: "center", gap: 8, margin: "28px 0 14px 0" },
  icon: { fontSize: 18, color: "#4ea8de" },
};

// ─── Reusable Components ─────────────────────────────────────────────────────

function MetricCard({ title, value, desc, color, style }) {
  return (
    <div style={{ ...S.card, ...style }}>
      <div style={S.cardTitle}>{title}</div>
      <div style={{ ...S.cardValue, color: color || "#fff" }}>{value ?? "—"}</div>
      {desc && <div style={S.cardDesc}>{desc}</div>}
    </div>
  );
}

function TempBar({ label, pv, sv }) {
  const { pct, color } = tempBarColor(pv, sv);
  return (
    <div style={{ ...S.card, minWidth: 280 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
        <span style={{ fontSize: 14, color: "#c8d3df", fontWeight: 600 }}>{label}</span>
        <span style={{ fontSize: 13, color: "#8899aa" }}>{pv ?? "—"}°C / {sv ?? "—"}°C</span>
      </div>
      <div style={{ background: "#0f172a", borderRadius: 8, height: 10, overflow: "hidden" }}>
        <div style={{ width: `${pct * 100}%`, background: color, height: 10, borderRadius: 8, transition: "width 0.6s ease" }} />
      </div>
    </div>
  );
}

function ShiftCard({ shift, seconds, events, isActive }) {
  const min = (seconds / 60).toFixed(1);
  const hr = (seconds / 3600).toFixed(2);
  const info = SHIFT_LABELS[shift] || {};
  return (
    <div style={{ ...S.card, borderColor: isActive ? "#4ea8de" : "#1e2030", minWidth: 200 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: "#c8d3df" }}>{info.name}</span>
        <span style={{ fontSize: 11, color: "#667788" }}>{info.hours}</span>
        {isActive && <span style={{ ...S.pill("#4ea8de"), color: "#000", fontSize: 10, padding: "2px 8px" }}>ACTIVE</span>}
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color: dtColor(parseFloat(min)) }}>{min} min</div>
      <div style={S.cardDesc}>{hr} hrs · {events} event{events !== 1 ? "s" : ""}</div>
    </div>
  );
}

function StatusBadge({ status }) {
  const cfg = STATUS_MAP[status] || STATUS_MAP[0];
  return <span style={{ ...S.pill(cfg.bg), color: cfg.text }}>{cfg.label}</span>;
}

function EditModal({ machine_id, current, onClose, onSave }) {
  const [mold, setMold] = useState(current?.mold || 0);
  const [cycLimit, setCycLimit] = useState(current?.cycle_limit || 0);
  const [saving, setSaving] = useState(false);
  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch(`${API}/api/machines/${machine_id}/info?mold=${mold}&cycle_limit=${cycLimit}`, { method: "PUT" });
      onSave();
    } catch (e) { console.error(e); }
    setSaving(false);
  };
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 999 }} onClick={onClose}>
      <div style={{ background: "#181a24", borderRadius: 16, padding: 28, width: 340, border: "1px solid #2a2e3e" }} onClick={e => e.stopPropagation()}>
        <div style={{ fontSize: 18, fontWeight: 700, color: "#fff", marginBottom: 20 }}>Edit Machine {machine_id}</div>
        <label style={{ fontSize: 12, color: "#8899aa", display: "block", marginBottom: 4 }}>Mold Number</label>
        <input type="number" value={mold} onChange={e => setMold(Number(e.target.value))} style={{ ...S.input, marginBottom: 14 }} />
        <label style={{ fontSize: 12, color: "#8899aa", display: "block", marginBottom: 4 }}>Cycle Limit (s)</label>
        <input type="number" value={cycLimit} onChange={e => setCycLimit(Number(e.target.value))} style={{ ...S.input, marginBottom: 20 }} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button style={S.btn} onClick={onClose}>Cancel</button>
          <button style={S.btnPrimary} onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Save"}</button>
        </div>
      </div>
    </div>
  );
}

function AlertsModal({ alerts, onClose }) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 999 }} onClick={onClose}>
      <div style={{ background: "#181a24", borderRadius: 16, padding: 28, width: 520, maxHeight: "70vh", overflow: "auto", border: "1px solid #2a2e3e" }} onClick={e => e.stopPropagation()}>
        <div style={{ fontSize: 18, fontWeight: 700, color: "#ffd600", marginBottom: 16 }}>⚠ Alerts ({alerts.length})</div>
        {alerts.length === 0
          ? <div style={{ color: "#667788" }}>No active alerts.</div>
          : alerts.map((a, i) => (
            <div key={i} style={{ padding: "10px 14px", background: "#0f1019", borderRadius: 8, marginBottom: 8, fontSize: 13, color: "#e0e6ed", borderLeft: "3px solid #ffd600" }}>{a}</div>
          ))}
        <div style={{ textAlign: "right", marginTop: 16 }}>
          <button style={S.btn} onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

// ─── Scrolling Alert Strip ───────────────────────────────────────────────────

function AlertStrip({ alerts }) {
  if (!alerts || alerts.length === 0) return null;

  // Build the text content — duplicate for seamless loop
  const items = alerts.map((a, i) => (
    <span key={i} style={{ display: "inline-flex", alignItems: "center", whiteSpace: "nowrap" }}>
      <span style={{ color: "#ffd600", fontWeight: 700, marginRight: 6 }}>⚠ M{a.machine_id}</span>
      <span style={{ color: "#e0e6ed" }}>{a.message}</span>
      <span style={{
        display: "inline-block", width: 6, height: 6, borderRadius: "50%",
        background: "#ffd60050", margin: "0 24px", flexShrink: 0,
      }} />
    </span>
  ));

  // CSS keyframes via inline style tag
  const animDuration = Math.max(40, alerts.length * 18);

  return (
    <>
      <style>{`
        @keyframes alertScroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
      <div style={{
        background: "#1a1008", borderBottom: "1px solid #ffd60030",
        overflow: "hidden", height: 36, display: "flex", alignItems: "center",
        position: "relative",
      }}>
        <div style={{
          display: "inline-flex", alignItems: "center",
          animation: `alertScroll ${animDuration}s linear infinite`,
          fontSize: 12, fontFamily: "'Montserrat', sans-serif",
        }}>
          {/* Render twice for seamless loop */}
          {items}{items}
        </div>
      </div>
    </>
  );
}

// ─── Cycle Chart Component ───────────────────────────────────────────────────

const CHART_COLORS = ["#4ea8de", "#ffd600", "#00c853", "#FF4B4B", "#c084fc", "#f97316"];

const CYCLE_COUNTS = [10, 30, 60, 90, 150, 300, 500];

function CycleChart({ title, cycles, dataKeys, colors }) {
  const [cycleLimit, setCycleLimit] = useState(60);
  // Zoom state: user drags on chart to select a range
  const [zoomLeft, setZoomLeft] = useState(null);
  const [zoomRight, setZoomRight] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [viewStart, setViewStart] = useState(null); // null = show all (within cycleLimit)
  const [viewEnd, setViewEnd] = useState(null);

  // Build full chart data from last N cycles (reversed: oldest on left)
  const allData = useMemo(() => {
    if (!cycles || cycles.length === 0) return [];
    const sliced = cycles.slice(0, cycleLimit);
    return sliced
      .slice()
      .reverse()
      .map((c, i) => {
        const row = {
          cycle: i + 1,
          time: c.timestamp
            ? new Date(c.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
            : `#${i + 1}`,
        };
        for (const key of dataKeys) {
          const val = c.data?.[key];
          row[key] = typeof val === "number" ? val : null;
        }
        return row;
      })
      .filter(r => dataKeys.some(k => r[k] !== null));
  }, [cycles, cycleLimit, dataKeys]);

  // Apply zoom window
  const chartData = (viewStart !== null && viewEnd !== null)
    ? allData.slice(viewStart, viewEnd + 1)
    : allData;

  // Reset zoom when cycle limit changes
  const handleCycleLimitChange = (count) => {
    setCycleLimit(count);
    setViewStart(null);
    setViewEnd(null);
  };

  // Drag-to-zoom handlers
  const handleMouseDown = (e) => {
    if (e && e.activeLabel) {
      const idx = allData.findIndex(d => d.time === e.activeLabel);
      setZoomLeft(idx >= 0 ? idx : null);
      setDragging(true);
    }
  };
  const handleMouseMove = (e) => {
    if (dragging && e && e.activeLabel) {
      const idx = allData.findIndex(d => d.time === e.activeLabel);
      setZoomRight(idx >= 0 ? idx : null);
    }
  };
  const handleMouseUp = () => {
    if (zoomLeft !== null && zoomRight !== null && zoomLeft !== zoomRight) {
      const left = Math.min(zoomLeft, zoomRight);
      const right = Math.max(zoomLeft, zoomRight);
      setViewStart(left);
      setViewEnd(right);
    }
    setZoomLeft(null);
    setZoomRight(null);
    setDragging(false);
  };

  const resetZoom = () => {
    setViewStart(null);
    setViewEnd(null);
  };

  if (!cycles || cycles.length === 0) {
    return (
      <div style={{ ...S.card, minWidth: "100%" }}>
        <div style={S.cardTitle}>{title}</div>
        <div style={{ color: "#667788", fontSize: 13, padding: "20px 0" }}>No cycle data available</div>
      </div>
    );
  }

  // Dynamic Y-axis from visible data
  let allVals = [];
  for (const row of chartData) {
    for (const key of dataKeys) {
      if (row[key] !== null && row[key] !== undefined) allVals.push(row[key]);
    }
  }
  const dataMin = allVals.length > 0 ? Math.min(...allVals) : 0;
  const dataMax = allVals.length > 0 ? Math.max(...allVals) : 1;
  const pad = (dataMax - dataMin) * 0.15 || 1;
  const yMin = Math.max(0, parseFloat((dataMin - pad).toFixed(2)));
  const yMax = parseFloat((dataMax + pad).toFixed(2));

  const lineColors = colors || CHART_COLORS;
  const isZoomed = viewStart !== null && viewEnd !== null;

  // Highlight area during drag
  const showRefArea = dragging && zoomLeft !== null && zoomRight !== null && zoomLeft !== zoomRight;
  const refLeftIdx = showRefArea ? Math.min(zoomLeft, zoomRight) : 0;
  const refRightIdx = showRefArea ? Math.max(zoomLeft, zoomRight) : 0;

  return (
    <div style={{ ...S.card, minWidth: "100%", flex: "1 1 100%" }}>
      {/* Header row: title + cycle count buttons + zoom reset */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={S.cardTitle}>{title}</div>
          {isZoomed && (
            <button onClick={resetZoom} style={{
              padding: "2px 10px", borderRadius: 6, fontSize: 10, fontWeight: 700,
              border: "1px solid #4ea8de", background: "transparent", color: "#4ea8de",
              cursor: "pointer", fontFamily: "'Montserrat', sans-serif",
            }}>
              Reset Zoom
            </button>
          )}
        </div>
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <span style={{ fontSize: 10, color: "#556677", marginRight: 4 }}>CYCLES:</span>
          {CYCLE_COUNTS.filter(c => c <= (cycles?.length || 500)).map(count => (
            <button
              key={count}
              onClick={() => handleCycleLimitChange(count)}
              style={{
                padding: "3px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600,
                border: "none", cursor: "pointer",
                fontFamily: "'Montserrat', sans-serif",
                background: cycleLimit === count ? "#4ea8de" : "#1e2030",
                color: cycleLimit === count ? "#000" : "#667788",
                transition: "all 0.15s",
              }}
            >
              {count}
            </button>
          ))}
        </div>
      </div>

      {/* Zoom hint */}
      {!isZoomed && chartData.length > 10 && (
        <div style={{ fontSize: 10, color: "#445566", marginBottom: 6 }}>
          Drag on the chart to zoom into a range
        </div>
      )}

      {chartData.length === 0 ? (
        <div style={{ color: "#667788", fontSize: 13, padding: "20px 0" }}>No data for selected range</div>
      ) : (
        <div style={{ width: "100%", height: 270, userSelect: "none" }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 5, right: 20, bottom: 5, left: 10 }}
              onMouseDown={!isZoomed ? handleMouseDown : undefined}
              onMouseMove={!isZoomed ? handleMouseMove : undefined}
              onMouseUp={!isZoomed ? handleMouseUp : undefined}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2030" />
              <XAxis
                dataKey="time"
                tick={{ fill: "#667788", fontSize: 10 }}
                tickLine={{ stroke: "#333" }}
                axisLine={{ stroke: "#333" }}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[yMin, yMax]}
                tick={{ fill: "#667788", fontSize: 11 }}
                tickLine={{ stroke: "#333" }}
                axisLine={{ stroke: "#333" }}
                width={50}
              />
              <Tooltip
                contentStyle={{ background: "#181a24", border: "1px solid #2a2e3e", borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: "#8899aa" }}
                itemStyle={{ color: "#e0e6ed" }}
              />
              {dataKeys.length > 1 && (
                <Legend wrapperStyle={{ fontSize: 11, color: "#8899aa" }} />
              )}
              {dataKeys.map((key, i) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={lineColors[i % lineColors.length]}
                  strokeWidth={2}
                  dot={chartData.length <= 30}
                  activeDot={{ r: 4 }}
                  connectNulls
                  name={key}
                />
              ))}
              {showRefArea && (
                <ReferenceArea
                  x1={allData[refLeftIdx]?.time}
                  x2={allData[refRightIdx]?.time}
                  strokeOpacity={0.3}
                  fill="#4ea8de"
                  fillOpacity={0.15}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Showing info */}
      <div style={{ fontSize: 10, color: "#445566", marginTop: 6, textAlign: "right" }}>
        Showing {chartData.length} of {allData.length} cycles
        {isZoomed && ` (zoomed: cycle ${viewStart + 1}–${viewEnd + 1})`}
      </div>
    </div>
  );
}


// ─── Production Rate Chart (Rolling Hourly) ─────────────────────────────────
// Groups cycles into 1-hour buckets and counts bottles per hour.
// Shows a bar chart of hourly production rate through the day.

function ProductionRateChart({ cycles }) {
  const chartData = useMemo(() => {
    if (!cycles || cycles.length === 0) return [];

    // Group cycles by hour
    const hourBuckets = {};
    for (const c of cycles) {
      const ts = new Date(c.timestamp);
      const hourKey = ts.getHours();
      const hourLabel = `${String(hourKey).padStart(2, "0")}:00`;
      if (!hourBuckets[hourKey]) {
        hourBuckets[hourKey] = { hour: hourKey, label: hourLabel, count: 0 };
      }
      hourBuckets[hourKey].count += 1;
    }

    // Sort by hour and return
    return Object.values(hourBuckets).sort((a, b) => a.hour - b.hour);
  }, [cycles]);

  if (!cycles || cycles.length === 0) {
    return (
      <div style={{ ...S.card, minWidth: "100%" }}>
        <div style={S.cardTitle}>Production Rate (Hourly)</div>
        <div style={{ color: "#667788", fontSize: 13, padding: "20px 0" }}>No cycle data available</div>
      </div>
    );
  }

  // Dynamic Y-axis
  const vals = chartData.map(d => d.count);
  const dataMax = vals.length > 0 ? Math.max(...vals) : 1;
  const yMax = Math.ceil(dataMax * 1.15);

  // Average and total
  const totalBottles = vals.reduce((a, b) => a + b, 0);
  const avgRate = chartData.length > 0 ? Math.round(totalBottles / chartData.length) : 0;

  return (
    <div style={{ ...S.card, minWidth: "100%", flex: "1 1 100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={S.cardTitle}>Production Rate (Hourly)</div>
          <span style={{ fontSize: 11, color: "#1DB954", fontWeight: 600 }}>Avg: {avgRate} /hr</span>
          <span style={{ fontSize: 11, color: "#667788" }}>Total: {totalBottles}</span>
        </div>
      </div>

      {chartData.length === 0 ? (
        <div style={{ color: "#667788", fontSize: 13, padding: "20px 0" }}>No hourly data</div>
      ) : (
        <div style={{ width: "100%", height: 270, userSelect: "none" }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2030" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: "#667788", fontSize: 11 }}
                tickLine={{ stroke: "#333" }}
                axisLine={{ stroke: "#333" }}
              />
              <YAxis
                domain={[0, yMax]}
                tick={{ fill: "#667788", fontSize: 11 }}
                tickLine={{ stroke: "#333" }}
                axisLine={{ stroke: "#333" }}
                width={50}
                label={{ value: "bottles/hr", angle: -90, position: "insideLeft", fill: "#556677", fontSize: 10, dx: -5 }}
              />
              <Tooltip
                contentStyle={{ background: "#181a24", border: "1px solid #2a2e3e", borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: "#8899aa" }}
                itemStyle={{ color: "#e0e6ed" }}
                formatter={(val) => [`${val} bottles`, "Count"]}
                labelFormatter={(label) => `Hour: ${label}`}
              />
              <Bar
                dataKey="count"
                fill="#1DB954"
                radius={[4, 4, 0, 0]}
                maxBarSize={40}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div style={{ fontSize: 10, color: "#445566", marginTop: 6, textAlign: "right" }}>
        {chartData.length} hours with production data
      </div>
    </div>
  );
}


// ─── Timing Chart (Overlay + Heatmap) ───────────────────────────────────────
// Per-cycle phase durations rendered as a Gantt-style overlay (last N cycles
// stacked translucent, golden median outlined) + a deviation heatmap.
//
// `phases` config item shape:
//   { name, color, tag }                     ← direct lookup in cycle.data
//   { name, color, subtract: [a, b] }        ← computed as data[a] - data[b]
//   { name, color, tag, fixed: true }        ← fixed/setpoint, drawn the same

function deriveDuration(data, phase) {
  if (phase.subtract) {
    const a = Number(data?.[phase.subtract[0]]);
    const b = Number(data?.[phase.subtract[1]]);
    if (!isFinite(a) || !isFinite(b)) return null;
    return Math.max(0, a - b);
  }
  const v = Number(data?.[phase.tag]);
  return isFinite(v) ? v : null;
}

function TimingOverlay({ rows, phases, golden, windowN, setWindowN, totalCycles }) {
  const W = 1200;
  const rowH = 32;
  const bandH = 18;            // each cycle-time band height
  const bandGapInner = 4;      // gap between actual band and computed band
  const bandGap = 6;           // gap between bands and first phase row
  const bandTM = 12;           // top margin above bands
  const actualBandY = bandTM;
  const computedBandY = bandTM + bandH + bandGapInner;
  const TM = computedBandY + bandH + bandGap; // top of phase area
  const BM = 26, LM = 140, RM = 20;
  const plotH = phases.length * rowH;
  const H = TM + plotH + BM;
  const plotW = W - LM - RM;

  const tMax = Math.max(
    (golden._total || 1) * 1.35,
    (golden._actualTotal || 0) * 1.1,
    ...rows.map(r => r._cycleTotal || 0),
    ...rows.map(r => r._cycleTimeActual || 0)
  );
  const xs = (t) => LM + (t / tMax) * plotW;

  // x-axis ticks every ~1s, capped to ~10 labels
  const step = Math.max(1, Math.ceil(tMax / 10));
  const ticks = [];
  for (let s = 0; s <= Math.floor(tMax); s += step) ticks.push(s);

  return (
    <div style={{ marginBottom: 22 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, flexWrap: "wrap", gap: 8 }}>
        <div style={{ fontSize: 11, color: "#8899aa", fontWeight: 600, letterSpacing: 0.5 }}>
          OVERLAY · last {rows.length} cycle{rows.length !== 1 ? "s" : ""} stacked · golden = median of last 50
        </div>
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <span style={{ fontSize: 10, color: "#556677", marginRight: 4 }}>WINDOW:</span>
          {[10, 20, 50, 100, 300, 500].filter(n => n <= totalCycles).map(n => (
            <button
              key={n}
              onClick={() => setWindowN(n)}
              style={{
                padding: "3px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600,
                border: "none", cursor: "pointer", fontFamily: "'Montserrat', sans-serif",
                background: windowN === n ? "#4ea8de" : "#1e2030",
                color: windowN === n ? "#000" : "#667788",
              }}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }} preserveAspectRatio="none">
        {/* actual machine Cycle Time band (PV from PLC) */}
        <g>
          <rect x={LM} y={actualBandY} width={plotW} height={bandH} fill="#1a2233" />
          <text x={LM - 8} y={actualBandY + bandH / 2 + 4} textAnchor="end" fill="#5ee2c0" fontSize="11" fontFamily="ui-monospace,Menlo,monospace">
            Cycle Time (actual)
          </text>
          {rows.map((r, ri) => {
            const total = r._cycleTimeActual || 0;
            if (total <= 0) return null;
            const x0 = xs(0), x1 = xs(total);
            return (
              <rect
                key={ri}
                x={x0} y={actualBandY + 3}
                width={Math.max(1, x1 - x0)}
                height={bandH - 6}
                fill="#5ee2c0"
                opacity={0.16}
              />
            );
          })}
          {golden._actualTotal > 0 && (
            <rect
              x={xs(0)} y={actualBandY + 3}
              width={Math.max(1, xs(golden._actualTotal) - xs(0))}
              height={bandH - 6}
              fill="none"
              stroke="#ffd166"
              strokeWidth="1.8"
            />
          )}
        </g>

        {/* computed cycle-time band (sum of phases) */}
        <g>
          <rect x={LM} y={computedBandY} width={plotW} height={bandH} fill="#161927" />
          <text x={LM - 8} y={computedBandY + bandH / 2 + 4} textAnchor="end" fill="#9fb4ff" fontSize="11" fontFamily="ui-monospace,Menlo,monospace">
            Cycle Time (sum)
          </text>
          {rows.map((r, ri) => {
            const total = r._cycleTotal || 0;
            if (total <= 0) return null;
            const x0 = xs(0), x1 = xs(total);
            return (
              <rect
                key={ri}
                x={x0} y={computedBandY + 3}
                width={Math.max(1, x1 - x0)}
                height={bandH - 6}
                fill="#9fb4ff"
                opacity={0.14}
              />
            );
          })}
          {golden._total > 0 && (
            <rect
              x={xs(0)} y={computedBandY + 3}
              width={Math.max(1, xs(golden._total) - xs(0))}
              height={bandH - 6}
              fill="none"
              stroke="#ffd166"
              strokeWidth="1.8"
            />
          )}
        </g>

        {phases.map((p, i) => {
          const y = TM + i * rowH;
          return (
            <g key={p.name}>
              <rect x={LM} y={y + 2} width={plotW} height={rowH - 6} fill="#0f1019" />
              <text x={LM - 8} y={y + rowH / 2 + 4} textAnchor="end" fill="#c8d3df" fontSize="11" fontFamily="ui-monospace,Menlo,monospace">
                {p.name}
              </text>
            </g>
          );
        })}

        {/* translucent cycles */}
        {rows.map((r, ri) => (
          <g key={ri}>
            {r._phases.map((ph, i) => {
              if (!ph.dur || ph.dur <= 0) return null;
              const y = TM + i * rowH + 5;
              const x0 = xs(ph.t0), x1 = xs(ph.t1);
              return (
                <rect
                  key={i}
                  x={x0} y={y}
                  width={Math.max(1, x1 - x0)}
                  height={rowH - 12}
                  fill={ph.color}
                  opacity={0.18}
                />
              );
            })}
          </g>
        ))}

        {/* golden outline */}
        {(() => {
          let cum = 0;
          const out = [];
          phases.forEach((p, i) => {
            const dur = golden[p.name] || 0;
            if (dur > 0) {
              const y = TM + i * rowH + 5;
              const x0 = xs(cum), x1 = xs(cum + dur);
              out.push(
                <rect
                  key={p.name}
                  x={x0} y={y}
                  width={Math.max(1, x1 - x0)}
                  height={rowH - 12}
                  fill="none"
                  stroke="#ffd166"
                  strokeWidth="1.8"
                />
              );
            }
            cum += dur;
          });
          return out;
        })()}

        {/* x-axis */}
        {ticks.map(s => {
          const x = xs(s);
          return (
            <g key={s}>
              <line x1={x} y1={TM + plotH} x2={x} y2={TM + plotH + 4} stroke="#2a3040" />
              <text x={x} y={TM + plotH + 16} textAnchor="middle" fill="#667788" fontSize="10">{s}s</text>
            </g>
          );
        })}
        <text x={LM + plotW} y={TM + plotH + 16} textAnchor="end" fill="#445566" fontSize="10">
          t since cycle-start (s)
        </text>
      </svg>
    </div>
  );
}

function TimingHeatmap({ rows, phases, golden, heatmapN, setHeatmapN, totalCycles, metric, setMetric }) {
  // Precompute golden cumulative end-time per phase index
  const goldenEnds = [];
  {
    let cum = 0;
    for (const p of phases) {
      cum += golden[p.name] || 0;
      goldenEnds.push(cum);
    }
  }
  const W = 1200;
  const rowH = 22;
  const TM = 8, BM = 22, LM = 140, RM = 10;
  const plotH = phases.length * rowH;
  const H = TM + plotH + BM;
  const plotW = W - LM - RM;
  const N = rows.length;
  const cellW = N > 0 ? plotW / N : 0;

  // Single source of truth: ordered low -> high. dev falls in [min, max).
  // Cells and legend swatches both render from this list.
  const HEATMAP_BANDS = [
    { min: -Infinity, max: -0.25, color: "#1d4ed8", label: "≤ -25%" },
    { min: -0.25,     max: -0.10, color: "#3b82f6", label: "-25 to -10%" },
    { min: -0.10,     max:  0.10, color: "#4b5563", label: "on-spec ±10%" },
    { min:  0.10,     max:  0.20, color: "#f59e0b", label: "+10 to +20%" },
    { min:  0.20,     max:  0.35, color: "#f97316", label: "+20 to +35%" },
    { min:  0.35,     max:  Infinity, color: "#dc2626", label: "≥ +35%" },
  ];
  const cellColor = (dev) => {
    if (dev == null || isNaN(dev)) return "#1a1d28";
    for (const b of HEATMAP_BANDS) if (dev >= b.min && dev < b.max) return b.color;
    return "#1a1d28";
  };

  // x-axis tick positions
  const tickIdxs = N > 0
    ? Array.from(new Set([0, Math.floor(N * 0.25), Math.floor(N * 0.5), Math.floor(N * 0.75), N - 1]))
    : [];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, flexWrap: "wrap", gap: 8 }}>
        <div style={{ fontSize: 11, color: "#8899aa", fontWeight: 600, letterSpacing: 0.5 }}>
          HEATMAP · {metric === "endOffset" ? "phase-end offset vs golden" : "phase duration vs golden"} · {N} cycle{N !== 1 ? "s" : ""} (oldest → newest)
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <span style={{ fontSize: 10, color: "#556677", marginRight: 4 }}>METRIC:</span>
            {[["endOffset", "End offset"], ["duration", "Duration"]].map(([k, l]) => (
              <button
                key={k}
                onClick={() => setMetric(k)}
                style={{
                  padding: "3px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600,
                  border: "none", cursor: "pointer", fontFamily: "'Montserrat', sans-serif",
                  background: metric === k ? "#4ea8de" : "#1e2030",
                  color: metric === k ? "#000" : "#667788",
                }}
              >
                {l}
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <span style={{ fontSize: 10, color: "#556677", marginRight: 4 }}>RANGE:</span>
          {[100, 300, 500].filter(n => n <= totalCycles).map(n => (
            <button
              key={n}
              onClick={() => setHeatmapN(n)}
              style={{
                padding: "3px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600,
                border: "none", cursor: "pointer", fontFamily: "'Montserrat', sans-serif",
                background: heatmapN === n ? "#4ea8de" : "#1e2030",
                color: heatmapN === n ? "#000" : "#667788",
              }}
            >
              {n}
            </button>
          ))}
          </div>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }} preserveAspectRatio="none">
        {phases.map((p, i) => {
          const y = TM + i * rowH;
          const g = golden[p.name] || 0;
          return (
            <g key={p.name}>
              <text x={LM - 8} y={y + rowH / 2 + 4} textAnchor="end" fill="#c8d3df" fontSize="11" fontFamily="ui-monospace,Menlo,monospace">
                {p.name}
              </text>
              {rows.map((r, c) => {
                const v = r[p.name];
                const phaseEnd = r._phases && r._phases[i] ? r._phases[i].t1 : null;
                const gEnd = goldenEnds[i];
                let dev = null;
                if (metric === "endOffset") {
                  dev = (phaseEnd != null && gEnd > 0) ? (phaseEnd - gEnd) / gEnd : null;
                } else {
                  dev = (v != null && g > 0) ? (v - g) / g : null;
                }
                const x = LM + c * cellW;
                return (
                  <rect
                    key={c}
                    x={x} y={y + 1}
                    width={cellW + 0.5}
                    height={rowH - 2}
                    fill={cellColor(dev)}
                  >
                    <title>
                      {`#${c + 1} · ${p.name}` +
                        (metric === "endOffset"
                          ? `\nend ${phaseEnd != null ? phaseEnd.toFixed(2) + "s" : "—"} · golden end ${gEnd.toFixed(2)}s`
                          : `\ndur ${v != null ? v.toFixed(2) + "s" : "—"} · golden ${g.toFixed(2)}s`) +
                        (dev != null ? `  (${(dev * 100).toFixed(0)}%)` : "")}
                    </title>
                  </rect>
                );
              })}
            </g>
          );
        })}

        {tickIdxs.map((c, i) => {
          const x = LM + c * cellW;
          return (
            <g key={i}>
              <line x1={x} y1={TM + plotH} x2={x} y2={TM + plotH + 3} stroke="#2a3040" />
              <text x={x} y={TM + plotH + 14} textAnchor="middle" fill="#667788" fontSize="10">#{c + 1}</text>
            </g>
          );
        })}
      </svg>

      <div style={{ display: "flex", gap: 14, marginTop: 8, fontSize: 10, color: "#8899aa", flexWrap: "wrap" }}>
        {HEATMAP_BANDS.map(b => (
          <span key={b.label} style={{ display: "inline-flex", alignItems: "center" }}>
            <i style={{ display: "inline-block", width: 10, height: 10, background: b.color, borderRadius: 2, marginRight: 5 }} />
            {b.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function TimingChart({ title, cycles, phases }) {
  const [windowN, setWindowN] = useState(20);
  const [heatmapN, setHeatmapN] = useState(300);
  const [metric, setMetric] = useState("endOffset");

  // cycles arrives newest-first; reverse to chronological
  const rows = useMemo(() => {
    if (!cycles || !phases || cycles.length === 0 || phases.length === 0) return [];
    const ordered = cycles.slice().reverse();
    return ordered.map((c, idx) => {
      const data = c.data || {};
      const row = { _idx: idx, _timestamp: c.timestamp };
      for (const p of phases) row[p.name] = deriveDuration(data, p);

      let cum = 0;
      row._phases = phases.map(p => {
        const dur = row[p.name] ?? 0;
        const ph = { name: p.name, color: p.color, t0: cum, t1: cum + dur, dur };
        cum += dur;
        return ph;
      });
      row._cycleTotal = cum;
      // Actual machine Cycle Time PV (vs computed sum-of-phases above)
      const ct = data["Cycle Time"];
      row._cycleTimeActual = (typeof ct === "number" && ct > 0) ? ct : null;
      return row;
    });
  }, [cycles, phases]);

  const golden = useMemo(() => {
    const window = rows.slice(-50);
    const g = {};
    for (const p of phases || []) {
      const vals = window.map(r => r[p.name]).filter(v => v != null && v > 0).sort((a, b) => a - b);
      g[p.name] = vals.length ? vals[Math.floor(vals.length / 2)] : 0;
    }
    g._total = (phases || []).reduce((s, p) => s + (g[p.name] || 0), 0);
    // golden actual cycle time = median of last 50 actual Cycle Time PVs
    const actuals = window.map(r => r._cycleTimeActual).filter(v => v != null && v > 0).sort((a, b) => a - b);
    g._actualTotal = actuals.length ? actuals[Math.floor(actuals.length / 2)] : 0;
    return g;
  }, [rows, phases]);

  const totalCycles = rows.length;
  const overlayRows = rows.slice(-Math.min(windowN, totalCycles));
  const heatmapRows = rows.slice(-Math.min(heatmapN, totalCycles));

  if (!cycles || cycles.length === 0 || !phases || phases.length === 0) {
    return (
      <div style={{ ...S.card, minWidth: "100%" }}>
        <div style={S.cardTitle}>{title || "Timing Chart"}</div>
        <div style={{ color: "#667788", fontSize: 13, padding: "20px 0" }}>No cycle data available</div>
      </div>
    );
  }

  return (
    <div style={{ ...S.card, minWidth: "100%", flex: "1 1 100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 12 }}>
        <div style={S.cardTitle}>{title || "Timing Chart"}</div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {phases.map(p => (
            <span key={p.name} style={{ fontSize: 10, color: "#c8d3df", display: "inline-flex", alignItems: "center" }}>
              <i style={{ display: "inline-block", width: 10, height: 10, background: p.color, borderRadius: 2, marginRight: 5 }} />
              {p.name}{p.fixed ? " (SV)" : ""}
            </span>
          ))}
          <span style={{ fontSize: 10, color: "#ffd166", display: "inline-flex", alignItems: "center" }}>
            <i style={{ display: "inline-block", width: 14, height: 2, background: "#ffd166", marginRight: 5 }} />
            golden
          </span>
        </div>
      </div>

      <TimingOverlay
        rows={overlayRows}
        phases={phases}
        golden={golden}
        windowN={windowN}
        setWindowN={setWindowN}
        totalCycles={totalCycles}
      />
      <TimingHeatmap
        rows={heatmapRows}
        phases={phases}
        golden={golden}
        heatmapN={heatmapN}
        setHeatmapN={setHeatmapN}
        totalCycles={totalCycles}
        metric={metric}
        setMetric={setMetric}
      />
    </div>
  );
}


// ═════════════════════════════════════════════════════════════════════════════════
// SIDEBAR
// ═════════════════════════════════════════════════════════════════════════════════

function Sidebar({ fleet, selectedMachine, onSelectMachine, onGoHome, collapsed, onToggle }) {
  const w = collapsed ? SIDEBAR_COLLAPSED_W : SIDEBAR_W;

  return (
    <div style={{
      width: w, minWidth: w, height: "100vh", position: "fixed", left: 0, top: 0,
      background: "#0e0e12", borderRight: "1px solid #1e2030",
      display: "flex", flexDirection: "column", transition: "width 0.2s ease",
      zIndex: 100, overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{
        padding: collapsed ? "16px 10px" : "20px 16px",
        borderBottom: "1px solid #1e2030", display: "flex", alignItems: "center",
        justifyContent: collapsed ? "center" : "space-between", minHeight: 64,
      }}>
        {!collapsed && (
          <div style={{ cursor: "pointer" }} onClick={onGoHome}>
            <div style={{ fontSize: 14, fontWeight: 800, color: "#fff", letterSpacing: -0.5 }}>AXIUM</div>
            <div style={{ fontSize: 9, color: "#4ea8de", fontWeight: 600, letterSpacing: 2, textTransform: "uppercase" }}>Plant 1</div>
          </div>
        )}
        <button
          onClick={onToggle}
          style={{
            background: "none", border: "none", color: "#667788", cursor: "pointer",
            fontSize: 18, padding: 4, lineHeight: 1, fontFamily: "'Montserrat', sans-serif",
          }}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? "▸" : "◂"}
        </button>
      </div>

      {/* Home link */}
      <div
        onClick={onGoHome}
        style={{
          padding: collapsed ? "12px 0" : "12px 16px",
          cursor: "pointer", display: "flex", alignItems: "center", gap: 10,
          color: selectedMachine === null ? "#4ea8de" : "#667788",
          background: selectedMachine === null ? "#4ea8de10" : "transparent",
          borderLeft: selectedMachine === null ? "3px solid #4ea8de" : "3px solid transparent",
          fontSize: 13, fontWeight: 600, transition: "all 0.15s",
          justifyContent: collapsed ? "center" : "flex-start",
        }}
      >
        <span style={{ fontSize: 16 }}>⌂</span>
        {!collapsed && "Overview"}
      </div>

      {/* Divider + label */}
      {!collapsed && (
        <div style={{ padding: "14px 16px 6px", fontSize: 10, color: "#556677", fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase" }}>
          Machines
        </div>
      )}
      {collapsed && <div style={{ height: 1, background: "#1e2030", margin: "8px 0" }} />}

      {/* Machine list */}
      <div style={{ flex: 1, overflowY: "auto", overflowX: "hidden" }}>
        {(fleet || []).map(m => {
          const active = selectedMachine === m.machine_id;
          const dotColor = (STATUS_MAP[m.status] || STATUS_MAP[0]).dot;

          return (
            <div
              key={m.machine_id}
              onClick={() => onSelectMachine(m.machine_id)}
              style={{
                padding: collapsed ? "10px 0" : "10px 16px",
                cursor: "pointer", display: "flex", alignItems: "center", gap: 10,
                background: active ? "#4ea8de10" : "transparent",
                borderLeft: active ? "3px solid #4ea8de" : "3px solid transparent",
                transition: "all 0.15s",
                justifyContent: collapsed ? "center" : "flex-start",
              }}
              onMouseEnter={e => { if (!active) e.currentTarget.style.background = "#ffffff06"; }}
              onMouseLeave={e => { if (!active) e.currentTarget.style.background = "transparent"; }}
            >
              {/* Status dot */}
              <div style={{
                width: 8, height: 8, borderRadius: "50%", background: dotColor,
                flexShrink: 0, boxShadow: `0 0 6px ${dotColor}60`,
              }} />

              {!collapsed && (
                <>
                  <span style={{
                    fontSize: 13, fontWeight: active ? 700 : 500,
                    color: active ? "#fff" : "#b0bcc8", flex: 1,
                  }}>
                    M{m.machine_id}
                  </span>
                  {m.alert_count > 0 && (
                    <span style={{
                      fontSize: 10, background: "#ffd60030", color: "#ffd600",
                      padding: "1px 6px", borderRadius: 4, fontWeight: 700,
                    }}>
                      {m.alert_count}
                    </span>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer */}
      {!collapsed && (
        <div style={{ padding: "12px 16px", borderTop: "1px solid #1e2030", fontSize: 10, color: "#445566" }}>
          SCADA v1.0
        </div>
      )}
    </div>
  );
}


// ─── Report Viewer Modal ────────────────────────────────────────────────────

function ReportViewerModal({ pdfUrl, filename, onClose }) {
  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)",
        display: "flex", flexDirection: "column", zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "14px 24px", background: "#131316", borderBottom: "1px solid #2a2e3e",
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: "#fff" }}>Weekly Report</span>
          <span style={{ fontSize: 12, color: "#667788" }}>{filename}</span>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <a
            href={pdfUrl}
            download={filename}
            style={{
              ...S.btnPrimary, textDecoration: "none", display: "inline-flex",
              alignItems: "center", gap: 6, padding: "8px 20px",
            }}
          >
            ↓ Download PDF
          </a>
          <button style={S.btn} onClick={onClose}>✕ Close</button>
        </div>
      </div>
      <div style={{ flex: 1, padding: 0 }} onClick={e => e.stopPropagation()}>
        <iframe
          src={pdfUrl}
          title="Weekly Report"
          style={{ width: "100%", height: "100%", border: "none", background: "#fff" }}
        />
      </div>
    </div>
  );
}


// ─── Report Section (date picker + generate) ────────────────────────────────

function ReportSection() {
  // Default to last 7 days
  const today = new Date();
  const weekAgo = new Date(today);
  weekAgo.setDate(weekAgo.getDate() - 7);

  const fmt = (d) => d.toISOString().split("T")[0];

  const [startDate, setStartDate] = useState(fmt(weekAgo));
  const [endDate, setEndDate] = useState(fmt(today));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [filename, setFilename] = useState("");

  // Quick-select presets
  const setPreset = (label) => {
    const now = new Date();
    let s, e;
    if (label === "last7") {
      e = new Date(now); e.setDate(e.getDate() - 1);
      s = new Date(e); s.setDate(s.getDate() - 6);
    } else if (label === "lastWeek") {
      // Mon-Sun of previous week
      const dow = now.getDay() || 7;
      e = new Date(now); e.setDate(e.getDate() - dow);
      s = new Date(e); s.setDate(s.getDate() - 6);
    } else if (label === "last30") {
      e = new Date(now); e.setDate(e.getDate() - 1);
      s = new Date(e); s.setDate(s.getDate() - 29);
    }
    setStartDate(fmt(s));
    setEndDate(fmt(e));
  };

  const handleGenerate = async () => {
    // Clean up previous blob URL
    if (pdfUrl) { URL.revokeObjectURL(pdfUrl); setPdfUrl(null); }

    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API}/api/report/weekly?start=${startDate}&end=${endDate}`
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const fname = `weekly_report_${startDate}_to_${endDate}.pdf`;
      setPdfUrl(url);
      setFilename(fname);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  };

  // Cleanup blob URL on unmount
  useEffect(() => {
    return () => { if (pdfUrl) URL.revokeObjectURL(pdfUrl); };
  }, [pdfUrl]);

  const presetBtn = (label, text) => (
    <button
      onClick={() => setPreset(label)}
      style={{
        padding: "5px 14px", borderRadius: 6, fontSize: 11, fontWeight: 600,
        border: "1px solid #2a2e3e", background: "#0f1019", color: "#8899aa",
        cursor: "pointer", fontFamily: "'Montserrat', sans-serif",
        transition: "all 0.15s",
      }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = "#4ea8de"; e.currentTarget.style.color = "#4ea8de"; }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = "#2a2e3e"; e.currentTarget.style.color = "#8899aa"; }}
    >
      {text}
    </button>
  );

  return (
    <>
      <div style={{ ...S.sectionTitle, marginTop: 40 }}>
        <span style={S.icon}>◈</span> Weekly Report
      </div>

      <div style={{
        ...S.card, display: "flex", flexDirection: "column", gap: 16,
        maxWidth: 600, padding: "20px 24px",
      }}>
        {/* Presets */}
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, color: "#556677", marginRight: 4 }}>QUICK:</span>
          {presetBtn("last7", "Last 7 Days")}
          {presetBtn("lastWeek", "Last Full Week")}
          {presetBtn("last30", "Last 30 Days")}
        </div>

        {/* Date pickers */}
        <div style={{ display: "flex", gap: 14, alignItems: "flex-end", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 150 }}>
            <label style={{ fontSize: 11, color: "#667788", display: "block", marginBottom: 4, fontWeight: 600 }}>
              Start Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={e => setStartDate(e.target.value)}
              max={endDate}
              style={{
                ...S.input, colorScheme: "dark", cursor: "pointer",
                padding: "10px 14px",
              }}
            />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <label style={{ fontSize: 11, color: "#667788", display: "block", marginBottom: 4, fontWeight: 600 }}>
              End Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={e => setEndDate(e.target.value)}
              min={startDate}
              max={fmt(new Date())}
              style={{
                ...S.input, colorScheme: "dark", cursor: "pointer",
                padding: "10px 14px",
              }}
            />
          </div>
          <button
            onClick={handleGenerate}
            disabled={loading || !startDate || !endDate}
            style={{
              ...S.btnPrimary,
              padding: "11px 28px",
              opacity: loading ? 0.6 : 1,
              cursor: loading ? "wait" : "pointer",
              minWidth: 160,
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            }}
          >
            {loading ? (
              <>
                <span style={{
                  display: "inline-block", width: 14, height: 14,
                  border: "2px solid #000", borderTopColor: "transparent",
                  borderRadius: "50%", animation: "spin 0.8s linear infinite",
                }} />
                Generating...
              </>
            ) : (
              "Generate Report"
            )}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div style={{
            padding: "10px 14px", background: "#2a1015",
            border: "1px solid #FF4B4B40", borderRadius: 8,
            color: "#FF4B4B", fontSize: 12,
          }}>
            {error}
          </div>
        )}

        {/* Date range info */}
        {startDate && endDate && (
          <div style={{ fontSize: 11, color: "#556677" }}>
            Report period: {startDate} to {endDate} ({
              Math.round((new Date(endDate) - new Date(startDate)) / 86400000) + 1
            } days)
          </div>
        )}
      </div>

      {/* Spinner animation */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* PDF Viewer Modal */}
      {pdfUrl && (
        <ReportViewerModal
          pdfUrl={pdfUrl}
          filename={filename}
          onClose={() => { URL.revokeObjectURL(pdfUrl); setPdfUrl(null); }}
        />
      )}
    </>
  );
}


// ═════════════════════════════════════════════════════════════════════════════════
// HOME PAGE
// ═════════════════════════════════════════════════════════════════════════════════

function HomePage({ fleet, onSelectMachine }) {
  const error = !fleet ? null : fleet.length === 0 ? "No machines loaded" : null;

  return (
    <>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 40, paddingTop: 16 }}>
        <div style={{ fontSize: 11, letterSpacing: 4, color: "#4ea8de", fontWeight: 700, marginBottom: 8, textTransform: "uppercase" }}>SCADA Monitoring System</div>
        <h1 style={{ fontSize: 38, fontWeight: 800, letterSpacing: -2, color: "#fff", margin: 0 }}>Axium Packaging</h1>
        <p style={{ fontSize: 16, color: "#8899aa", margin: "4px 0 0 0", fontWeight: 400 }}>Plant 1 — ISBM Line Overview</p>
      </div>

      {error && <div style={{ padding: "12px 16px", background: "#2a1015", border: "1px solid #FF4B4B40", borderRadius: 10, color: "#FF4B4B", fontSize: 13, marginBottom: 20 }}>{error}</div>}

      {/* Machine Grid */}
      <div style={S.sectionTitle}><span style={S.icon}>●</span> Machine Fleet</div>

      {!fleet ? (
        <div style={{ color: "#667788", padding: 40, textAlign: "center" }}>Loading machine statuses...</div>
      ) : (
        <>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
            {fleet.map(m => {
              const map = {
                0: { border: "#FF4B4B", color: "#FF4B4B", bg: "rgba(255,75,75,0.08)" },
                1: { border: "#1DB954", color: "#1DB954", bg: "rgba(29,185,84,0.08)" },
                2: { border: "#ffd600", color: "#ffd600", bg: "rgba(255,214,0,0.15)" },
              };
              const c = map[m.status] || map[0];
              return (
                <div
                  key={m.machine_id}
                  onClick={() => onSelectMachine(m.machine_id)}
                  style={{
                    width: 72, height: 48, borderRadius: 10, border: `2px solid ${c.border}`,
                    display: "flex", justifyContent: "center", alignItems: "center",
                    color: c.color, fontWeight: 700, fontSize: 18, cursor: "pointer",
                    background: c.bg, transition: "all 0.2s",
                  }}
                  onMouseEnter={e => { e.currentTarget.style.transform = "scale(1.08)"; e.currentTarget.style.boxShadow = `0 0 20px ${c.border}30`; }}
                  onMouseLeave={e => { e.currentTarget.style.transform = "scale(1)"; e.currentTarget.style.boxShadow = "none"; }}
                >
                  {m.machine_id}
                </div>
              );
            })}
          </div>

          {/* Legend */}
          <div style={{ display: "flex", gap: 24, marginTop: 18, fontSize: 12, color: "#667788" }}>
            {[["#1DB954", "Running"], ["#ffd600", "Alerts"], ["#FF4B4B", "Stopped"]].map(([c, l]) => (
              <div key={l} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{ width: 10, height: 10, borderRadius: 3, background: c }} /> {l}
              </div>
            ))}
          </div>

          {/* Summary Table */}
          <div style={{ ...S.sectionTitle, marginTop: 36 }}><span style={S.icon}>◆</span> Today's Summary</div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: "0 4px", fontSize: 13 }}>
              <thead>
                <tr style={{ color: "#667788", textTransform: "uppercase", fontSize: 11, letterSpacing: 1 }}>
                  {["Machine", "Type", "Status", "Mold", "Bottle Type", "Alerts"].map(h => (
                    <th key={h} style={{ padding: "8px 14px", textAlign: "left", fontWeight: 600 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {fleet.map(m => (
                  <tr
                    key={m.machine_id}
                    style={{ background: "#131316", cursor: "pointer", transition: "background 0.15s" }}
                    onClick={() => onSelectMachine(m.machine_id)}
                    onMouseEnter={e => e.currentTarget.style.background = "#1a1c26"}
                    onMouseLeave={e => e.currentTarget.style.background = "#131316"}
                  >
                    <td style={{ padding: "10px 14px", borderRadius: "8px 0 0 8px", fontWeight: 700, color: "#fff" }}>M{m.machine_id}</td>
                    <td style={{ padding: "10px 14px", color: "#8899aa" }}>{m.machine_type || "—"}</td>
                    <td style={{ padding: "10px 14px" }}><StatusBadge status={m.status} /></td>
                    <td style={{ padding: "10px 14px", color: "#c8d3df" }}>{m.mold || "—"}</td>
                    <td style={{ padding: "10px 14px", color: "#8899aa" }}>{m.bottle_type || "—"}</td>
                    <td style={{ padding: "10px 14px", borderRadius: "0 8px 8px 0", color: m.alert_count > 0 ? "#ffd600" : "#667788" }}>
                      {m.alert_count > 0 ? `${m.alert_count} alert${m.alert_count > 1 ? "s" : ""}` : "None"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Weekly Report Section */}
      <ReportSection />
    </>
  );
}


// ═════════════════════════════════════════════════════════════════════════════════
// SECTION RENDERER (config-driven)
// ═════════════════════════════════════════════════════════════════════════════════

function SectionRenderer({ section, tags, cycles, live, shifts, archive }) {
  const t = tags || {};

  if (section.type === "metrics") {
    return (
      <div style={{ ...S.grid, gap: 14 }}>
        {section.items.map(m => (
          <MetricCard
            key={m.tag}
            title={m.title}
            value={t[m.tag] != null ? `${t[m.tag]}${m.unit || ""}` : null}
            desc={m.desc}
          />
        ))}
      </div>
    );
  }

  if (section.type === "temp_bars") {
    return (
      <div style={{ ...S.grid, gap: 14 }}>
        {section.items.map(tb => (
          <TempBar key={tb.label} label={tb.label} pv={t[tb.pvTag]} sv={t[tb.svTag]} />
        ))}
      </div>
    );
  }

  if (section.type === "charts") {
    if (!cycles || cycles.length === 0) return null;
    return (
      <>
        <div style={S.sectionTitle}><span style={S.icon}>◈</span> Trends</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {section.items.map((ch, i) => {
            if (ch.kind === "production_rate") return <ProductionRateChart key={i} cycles={cycles} />;
            if (ch.kind === "cycle") return <CycleChart key={i} title={ch.title} cycles={cycles} dataKeys={ch.dataKeys} colors={ch.colors} />;
            return null;
          })}
        </div>
      </>
    );
  }

  if (section.type === "timing_chart") {
    if (!cycles || cycles.length === 0) return null;
    return (
      <>
        <div style={S.sectionTitle}><span style={S.icon}>◈</span> {section.title || "Timing Chart"}</div>
        <TimingChart title={section.title} cycles={cycles} phases={section.phases || []} />
      </>
    );
  }

  if (section.type === "live_production") {
    if (!live) return null;
    return (
      <div style={{ ...S.grid, gap: 14, marginTop: 14 }}>
        <MetricCard
          title="Bottles Produced Today"
          value={live.total_bottles?.toLocaleString()}
          desc="Total since midnight"
        />
        <MetricCard
          title="Production Rate"
          value={live.elapsed_today_seconds > 0 ? `${Math.round(live.total_bottles / (live.elapsed_today_seconds / 3600)).toLocaleString()} /hr` : "—"}
          desc="Avg bottles per hour today"
        />
      </div>
    );
  }

  if (section.type === "metric_group") {
    return (
      <>
        <div style={S.sectionTitle}><span style={S.icon}>◈</span> {section.title}</div>
        <div style={{ ...S.grid, gap: 14 }}>
          {section.items.map(m => (
            <MetricCard key={m.tag} title={m.title} value={t[m.tag]} />
          ))}
        </div>
      </>
    );
  }

  if (section.type === "production_dashboard") {
    if (!live) return null;
    return (
      <>
        <div style={{ ...S.grid, gap: 14 }}>
          <MetricCard title="Bottles Produced Today" value={live.total_bottles?.toLocaleString()} desc="Total since midnight" />
          <MetricCard
            title="Production Rate"
            value={live.elapsed_today_seconds > 0 ? Math.round(live.total_bottles / (live.elapsed_today_seconds / 3600)).toLocaleString() : "—"}
            desc="Bottles per hour (avg today)"
          />
          <MetricCard
            title="Downtime Today"
            value={`${live.total_downtime_minutes} min`}
            color={dtColor(live.total_downtime_minutes)}
            desc={`${live.total_downtime_hours} hrs · ${live.event_count} event${live.event_count !== 1 ? "s" : ""}`}
          />
          <MetricCard
            title="Availability"
            value={`${live.availability_pct}%`}
            color={availColor(live.availability_pct)}
            desc="Based on elapsed time today"
          />
        </div>

        {shifts && (
          <>
            <div style={S.sectionTitle}><span style={S.icon}>◷</span> Downtime by Shift</div>
            <div style={{ ...S.grid, gap: 14 }}>
              {shifts.map(s => <ShiftCard key={s.shift} shift={s.shift} seconds={s.total_downtime_seconds} events={s.event_count} isActive={s.is_active} />)}
            </div>
          </>
        )}

        {archive && archive.length > 0 && (
          <>
            <div style={S.sectionTitle}><span style={S.icon}>◫</span> Daily History</div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: "0 3px", fontSize: 12 }}>
                <thead>
                  <tr style={{ color: "#667788", textTransform: "uppercase", fontSize: 10, letterSpacing: 1 }}>
                    {["Date", "Mold", "Bottles", "DT (min)", "Events", "Avail %", "S1 DT", "S1 Ev", "S2 DT", "S2 Ev", "S3 DT", "S3 Ev"].map(h => (
                      <th key={h} style={{ padding: "6px 10px", textAlign: "left", fontWeight: 600 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {archive.map((d, i) => (
                    <tr key={i} style={{ background: i % 2 === 0 ? "#131316" : "#0f1019" }}>
                      <td style={{ padding: "8px 10px", color: "#c8d3df", borderRadius: "6px 0 0 6px" }}>{d.date}</td>
                      <td style={{ padding: "8px 10px", color: "#8899aa" }}>{d.mold_id ?? "—"}</td>
                      <td style={{ padding: "8px 10px", color: "#fff", fontWeight: 600 }}>{d.total_bottles?.toLocaleString()}</td>
                      <td style={{ padding: "8px 10px", color: dtColor(d.total_downtime_minutes) }}>{d.total_downtime_minutes}</td>
                      <td style={{ padding: "8px 10px", color: "#8899aa" }}>{d.downtime_event_count}</td>
                      <td style={{ padding: "8px 10px", color: availColor(d.availability_pct) }}>{d.availability_pct}%</td>
                      <td style={{ padding: "8px 10px", color: "#8899aa" }}>{Math.round(d.shift_1_downtime_seconds / 60)}</td>
                      <td style={{ padding: "8px 10px", color: "#8899aa" }}>{d.shift_1_events}</td>
                      <td style={{ padding: "8px 10px", color: "#8899aa" }}>{Math.round(d.shift_2_downtime_seconds / 60)}</td>
                      <td style={{ padding: "8px 10px", color: "#8899aa" }}>{d.shift_2_events}</td>
                      <td style={{ padding: "8px 10px", color: "#8899aa" }}>{Math.round(d.shift_3_downtime_seconds / 60)}</td>
                      <td style={{ padding: "8px 10px", color: "#8899aa", borderRadius: "0 6px 6px 0" }}>{d.shift_3_events}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </>
    );
  }

  return null;
}


// ═════════════════════════════════════════════════════════════════════════════════
// MACHINE DETAIL PAGE
// ═════════════════════════════════════════════════════════════════════════════════

function MachinePage({ machineId, onBack }) {
  const [opc, setOpc] = useState(null);
  const [live, setLive] = useState(null);
  const [shifts, setShifts] = useState(null);
  const [archive, setArchive] = useState(null);
  const [cycles, setCycles] = useState(null);
  const [tab, setTab] = useState("general");
  const [showEdit, setShowEdit] = useState(false);
  const [showAlerts, setShowAlerts] = useState(false);
  const [error, setError] = useState(null);

  const loadAll = useCallback(async () => {
    // 1. OPC first — this blocks FastAPI's single worker, so do it alone
    try {
      const opcData = await api(`/api/machines/${machineId}/opc`);
      setOpc(opcData);
    } catch (e) { console.error("OPC fetch failed:", e); }

    // 2. All DB queries in parallel — these are fast and independent
    const [liveRes, shiftRes, archiveRes, cyclesRes] = await Promise.allSettled([
      api(`/api/machines/${machineId}/live`),
      api(`/api/machines/${machineId}/shifts/today`),
      api(`/api/machines/${machineId}/archive?days=30`),
      api(`/api/machines/${machineId}/cycles?limit=500`),
    ]);

    if (liveRes.status === "fulfilled") setLive(liveRes.value);
    if (shiftRes.status === "fulfilled") setShifts(shiftRes.value.shifts);
    if (archiveRes.status === "fulfilled") setArchive(archiveRes.value.days);
    if (cyclesRes.status === "fulfilled") setCycles(cyclesRes.value.cycles);

    setError(null);
  }, [machineId]);

  useEffect(() => {
    setOpc(null); setLive(null); setShifts(null); setArchive(null); setCycles(null); setTab("general");
    loadAll();
    const id = setInterval(loadAll, POLL_MACHINE);
    return () => clearInterval(id);
  }, [loadAll]);

  const t = opc?.tags || {};
  const info = opc || {};

  const layout = opc?.layout || null;
  const TABS = layout?.tabs || [{ key: "general", label: "General" }];

  return (
    <>
      {/* Top bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, paddingTop: 4 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <button onClick={onBack} style={{ ...S.btn, padding: "6px 14px", fontSize: 16, lineHeight: 1 }}>←</button>
          <div>
            <h1 style={{ fontSize: 26, fontWeight: 800, color: "#fff", margin: 0, letterSpacing: -0.5 }}>Machine {machineId}</h1>
            <div style={{ fontSize: 11, color: "#667788", marginTop: 2 }}>{opc?.type_label || "Unknown Type"}</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span style={S.pill("#1b263b")}>{info.bottle_type || "Unknown"}</span>
          <span style={S.pill("#2a4a8a")}>Limit: {info.cycle_limit ?? "—"}s</span>
          <StatusBadge status={info.status || "stopped"} />
          <button style={S.btn} onClick={() => setShowEdit(true)}>Edit</button>
          <button
            style={{ ...S.btn, ...(info.alert_count > 0 ? { borderColor: "#ffd600", color: "#ffd600" } : {}) }}
            onClick={() => setShowAlerts(true)}
          >
            Alerts{info.alert_count > 0 && ` (${info.alert_count})`}
          </button>
        </div>
      </div>

      {error && <div style={{ padding: "10px 14px", background: "#2a1015", border: "1px solid #FF4B4B40", borderRadius: 10, color: "#FF4B4B", fontSize: 13, marginTop: 14 }}>{error}</div>}

      {/* Tabs */}
      <div style={{ display: "flex", gap: 0, borderBottom: "1px solid #1e2030", marginTop: 20, overflowX: "auto" }}>
        {TABS.map(tb => (
          <button key={tb.key} style={S.tab(tab === tb.key)} onClick={() => setTab(tb.key)}>{tb.label}</button>
        ))}
      </div>

      <div style={{ marginTop: 20 }}>
        {TABS.map(tb => tab === tb.key && (
          <div key={tb.key}>
            {(tb.sections || []).map((section, i) => (
              <SectionRenderer
                key={i}
                section={section}
                tags={t}
                cycles={cycles}
                live={live}
                shifts={shifts}
                archive={archive}
              />
            ))}
          </div>
        ))}
      </div>

      {showEdit && (
        <EditModal
          machine_id={machineId}
          current={{ mold: info.mold, cycle_limit: info.cycle_limit }}
          onClose={() => setShowEdit(false)}
          onSave={() => { setShowEdit(false); loadAll(); }}
        />
      )}
      {showAlerts && <AlertsModal alerts={info.alerts || []} onClose={() => setShowAlerts(false)} />}
    </>
  );
}


// ═════════════════════════════════════════════════════════════════════════════════
// LOGIN SCREEN  (validates against FastAPI, not hardcoded)
// ═════════════════════════════════════════════════════════════════════════════════


// ═════════════════════════════════════════════════════════════════════════════════
// APP ROOT  (sidebar + page layout)
// ═════════════════════════════════════════════════════════════════════════════════

export default function App() {
  const [selectedMachine, setSelectedMachine] = useState(null);
  const [fleet, setFleet] = useState(null);
  const [allAlerts, setAllAlerts] = useState([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const loadFleet = useCallback(async () => {
    try {
      const data = await api("/api/fleet/status");
      setFleet(data.machines);
    } catch (e) { console.error("Fleet load error:", e); }

    try {
      const alertData = await api("/api/fleet/alerts");
      setAllAlerts(alertData.alerts || []);
    } catch (e) { console.error("Alerts load error:", e); }
  }, []);

  useEffect(() => {
    loadFleet();
    const id = setInterval(loadFleet, POLL_FLEET);
    return () => clearInterval(id);
  }, [loadFleet]);

  const sidebarW = sidebarCollapsed ? SIDEBAR_COLLAPSED_W : SIDEBAR_W;

  return (
    <div style={S.page}>
      <Sidebar
        fleet={fleet}
        selectedMachine={selectedMachine}
        onSelectMachine={setSelectedMachine}
        onGoHome={() => setSelectedMachine(null)}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(p => !p)}
      />

      <div style={{ marginLeft: sidebarW, transition: "margin-left 0.2s ease", minHeight: "100vh" }}>
        {/* Scrolling alert strip at the top */}
        <AlertStrip alerts={allAlerts} />

        <div style={{ padding: "20px 28px" }}>
          {selectedMachine ? (
            <MachinePage
              machineId={selectedMachine}
              onBack={() => setSelectedMachine(null)}
            />
          ) : (
            <HomePage fleet={fleet} onSelectMachine={setSelectedMachine} />
          )}
        </div>
      </div>
    </div>
  );
}