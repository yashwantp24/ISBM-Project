import numpy as np

from database.tags import get_machine_type


class CycleLogger:
    def __init__(self, client, machine_id, tag_map):
        self.client = client
        self.machine_id = machine_id
        self.tag_map = tag_map

        try:
            self.machine_type = get_machine_type(machine_id)
        except KeyError:
            self.machine_type = "70DPW"

        self.prev_cycle_time = None
        self.cycle_buffer = []

    def poll(self):
        values = self.client.read_machine(self.machine_id, self.tag_map)
        if values is None:
            return None

        auto = values.get("Auto Cycle")
        cycle_time = values.get("Cycle Time")
        blow_time = values.get("Blow Time")

        # Ignore invalid states
        if auto != 1 or blow_time is None or blow_time <= 2:
            return None

        # Buffer valid samples
        self.cycle_buffer.append(values)

        # First valid sample
        if self.prev_cycle_time is None:
            self.prev_cycle_time = cycle_time
            return None

        # Cycle end detected
        if cycle_time != self.prev_cycle_time:
            cycle_data = self.aggregate_cycle()
            self.cycle_buffer.clear()
            self.prev_cycle_time = cycle_time
            return cycle_data

        # Cycle still running
        self.prev_cycle_time = cycle_time
        return None

    def aggregate_cycle(self):
        buf = self.cycle_buffer
        if not buf:
            return None

        agg = _AGGREGATORS.get(self.machine_type, _aggregate_70dpw)
        return agg(buf)


# ── per-type aggregation helpers ─────────────────────────────────────────────

def _safe_mean(buf, key):
    vals = [v[key] for v in buf if v.get(key) is not None]
    return float(np.mean(vals)) if vals else None


def _safe_max(buf, key):
    vals = [v[key] for v in buf if v.get(key) is not None]
    return float(max(vals)) if vals else None


def _aggregate_70dpw(buf):
    last = buf[-1]
    return {
        "timestamp": last["timestamp"],

        # Time SV
        "Injection Time": last.get("Injection Time"),
        "Cooling Time": last.get("Cooling Time"),
        "Stretch Time": last.get("Stretch Time"),
        "Blow Time": last.get("Blow Time"),

        # Time PV
        "Cycle Time": _safe_max(buf, "Cycle Time"),
        "V-P Time PV": _safe_max(buf, "V-P Time PV"),
        "Charge Time": _safe_max(buf, "Charge Time"),
        "Injection Mold CL FA": _safe_max(buf, "Injection Mold CL FA"),
        "Injection Mold OP FA": _safe_max(buf, "Injection Mold OP FA"),
        "Lip Mold CL FA": _safe_max(buf, "Lip Mold CL FA"),
        "Lip Mold OP FA": _safe_max(buf, "Lip Mold OP FA"),
        "Blow Mold CL FA": _safe_max(buf, "Blow Mold CL FA"),
        "Blow Mold OP FA": _safe_max(buf, "Blow Mold OP FA"),
        "Dry Cycle Time": _safe_max(buf, "Dry Cycle Time"),
        "Injection Mold CL": _safe_max(buf, "Injection Mold CL"),
        "Injection Mold OP": _safe_max(buf, "Injection Mold OP"),
        "Blow Core DW": _safe_max(buf, "Blow Core DW"),
        "Blow Core UP": _safe_max(buf, "Blow Core UP"),
        "Bottom UP": _safe_max(buf, "Bottom UP"),
        "Bottom DW": _safe_max(buf, "Bottom DW"),
        "Blow Mold CL": _safe_max(buf, "Blow Mold CL"),
        "Blow Mold OP": _safe_max(buf, "Blow Mold OP"),
        "Blow Core Hold FW": _safe_max(buf, "Blow Core Hold FW"),
        "Stretch Unit DW FA": _safe_max(buf, "Stretch Unit DW FA"),
        "Stretch Unit UP FA": _safe_max(buf, "Stretch Unit UP FA"),
        "Stretch Unit DW": _safe_max(buf, "Stretch Unit DW"),
        "Stretch Unit UP": _safe_max(buf, "Stretch Unit UP"),
        "Blow Mold M": _safe_max(buf, "Blow Mold M"),
        "Blow Mold C": _safe_max(buf, "Blow Mold C"),

        # Pressure
        "Main RAM Pressure": _safe_max(buf, "Main Ram FW Pressure"),
        "Screw Pressure": _safe_max(buf, "Screw Pressure Monitor"),

        # Temperature
        "Barrel Nozzle": _safe_mean(buf, "Barrel Nozzle PV"),
        "Barrel Front": _safe_mean(buf, "Barrel Front PV"),
        "Barrel Middle": _safe_mean(buf, "Barrel Middle PV"),
        "Barrel Rear Front": _safe_mean(buf, "Barrel Rear Front PV"),
        "Barrel Rear Rear": _safe_mean(buf, "Barrel Rear Rear PV"),
        "Oil Temperature": _safe_mean(buf, "Oil Temperature PV"),

        # Position
        "Shot Size PV": _safe_max(buf, "Screw Position"),
    }


def _aggregate_70dpw_v4_vision(buf):
    last = buf[-1]
    row = {
        "timestamp": last["timestamp"],

        # Time SV
        "Injection Time": last.get("Injection Time"),
        "Cooling Time": last.get("Cooling Time"),
        "Blow Time": last.get("Blow Time"),
        "Decomp Time": last.get("Decomp Time"),

        # Time PV
        "Cycle Time": _safe_max(buf, "Cycle Time"),
        "V-P Time PV": _safe_max(buf, "V-P Time PV"),

        # Mold action timings
        "Injection Mold CL": _safe_max(buf, "Injection Mold CL"),
        "Injection Mold OP": _safe_max(buf, "Injection Mold OP"),
        "Injection Mold CL Start": _safe_max(buf, "Injection Mold CL Start"),
        "Injection Mold OP Start": _safe_max(buf, "Injection Mold OP Start"),
        "Lip Mold CL": _safe_max(buf, "Lip Mold CL"),
        "Lip Mold OP": _safe_max(buf, "Lip Mold OP"),
        "Blow Mold C": _safe_max(buf, "Blow Mold C"),
        "Blow Mold OP": _safe_max(buf, "Blow Mold OP"),
        "Blow Mold M": _safe_max(buf, "Blow Mold M"),
        "Blow Core DW": _safe_max(buf, "Blow Core DW"),
        "Blow Core UP": _safe_max(buf, "Blow Core UP"),
        "Blow Core Hold FW": _safe_max(buf, "Blow Core Hold FW"),
        "Blow Core Hold BW": _safe_max(buf, "Blow Core Hold BW"),
        "Bottom UP": _safe_max(buf, "Bottom UP"),
        "Bottom DW": _safe_max(buf, "Bottom DW"),
        "Stretch Unit UP": _safe_max(buf, "Stretch Unit UP"),
        "Stretch Unit DW": _safe_max(buf, "Stretch Unit DW"),
        "S Plate FW": _safe_max(buf, "S Plate FW"),
        "S Plate BW": _safe_max(buf, "S Plate BW"),
        "H Pot UP": _safe_max(buf, "H Pot UP"),
        "H Pot DW": _safe_max(buf, "H Pot DW"),
        "H Core UP": _safe_max(buf, "H Core UP"),
        "H Core DW": _safe_max(buf, "H Core DW"),
        "Lock Pin UP": _safe_max(buf, "Lock Pin UP"),
        "Lock Pin DW": _safe_max(buf, "Lock Pin DW"),
        "Eject UP": _safe_max(buf, "Eject UP"),
        "Eject DW": _safe_max(buf, "Eject DW"),
        "Main RAM FW": _safe_max(buf, "Main RAM FW"),
        "Main RAM BW": _safe_max(buf, "Main RAM BW"),
        "Rotart Table FWD": _safe_max(buf, "Rotart Table FWD"),

        # Blow waveforms
        "Primary Blow A": _safe_max(buf, "Primary Blow A"),
        "Primary Blow B": _safe_max(buf, "Primary Blow B"),
        "Secondary Blow A": _safe_max(buf, "Secondary Blow A"),
        "Secondary Blow B": _safe_max(buf, "Secondary Blow B"),

        # Pressures
        "Injection Pressure": _safe_max(buf, "Injection Pressure"),
        "Air Pressure": _safe_mean(buf, "Air Pressure"),
        "Screw Charge Pressure": _safe_max(buf, "Screw Charge Pressure"),

        # Barrel temperatures (mean)
        "Barrel Nozzle": _safe_mean(buf, "Barrel Nozzle PV"),
        "Barrel Front": _safe_mean(buf, "Barrel Front PV"),
        "Barrel Middle": _safe_mean(buf, "Barrel Middle PV"),
        "Barrel Rear Front": _safe_mean(buf, "Barrel Rear Front PV"),
        "Barrel Rear Rear": _safe_mean(buf, "Barrel Rear Rear PV"),
        "Oil Temperature": _safe_mean(buf, "Oil Temperature PV"),
        "Rotation Table Temperature": _safe_mean(buf, "Rotation Table Temperature"),

        # Position / counts
        "Shot Size": _safe_max(buf, "Shot Size"),
        "Screw Position": _safe_max(buf, "Screw Position"),
        "Screw RPM": _safe_mean(buf, "Screw RPM"),
        "Bottle Quantity": last.get("Bottle Quantity"),

        # Pumps
        "Pump 1 Monitor": _safe_mean(buf, "Pump 1 Monitor"),
        "Pump 2 Monitor": _safe_mean(buf, "Pump 2 Monitor"),
        "Pump 3 Monitor": _safe_mean(buf, "Pump 3 Monitor"),
    }

    # HR Block / Nozzle / H Pot temp means (per-channel)
    for i in range(1, 5):
        row[f"HR Block {i}"] = _safe_mean(buf, f"HR Block PV {i}")
    for c in "ABCDEFGHIJKL":
        row[f"Nozzle 1{c}"] = _safe_mean(buf, f"Nozzle 1{c} PV")
        row[f"Nozzle 2{c}"] = _safe_mean(buf, f"Nozzle 2{c} PV")
    for i in range(1, 19):
        row[f"H Pot {i}"] = _safe_mean(buf, f"H Pot PV {i}")

    return row


_AGGREGATORS = {
    "70DPW": _aggregate_70dpw,
    "70DPW-V4-Vision": _aggregate_70dpw_v4_vision,
}
