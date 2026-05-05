from datetime import datetime
from database.tags import get_machine_type


# PV/SV pairs to monitor for deviation, keyed by machine type.
WATCH_PAIRS_BY_TYPE = {
    "70DPW": [
        ("Barrel Rear Front PV", "Barrel Rear Front SV"),
        ("Barrel Middle PV", "Barrel Middle SV"),
        ("Barrel Front PV", "Barrel Front SV"),
        ("Barrel Nozzle PV", "Barrel Nozzle SV"),
        ("Barrel Rear Rear PV", "Barrel Rear Rear SV"),
        *[(f"HR Block {i} PV", f"HR Block {i} SV") for i in range(1, 5)],
        *[(f"HR Nozzle {i} PV", f"HR Nozzle {i} SV") for i in range(1, 25)],
        *[(f"H Pot {i} PV", f"H Pot {i} SV") for i in range(1, 41)],
    ],
    "70DPW-V4-Vision": [
        ("Barrel Rear Front PV", "Barrel Rear Front SV"),
        ("Barrel Middle PV", "Barrel Middle SV"),
        ("Barrel Front PV", "Barrel Front SV"),
        ("Barrel Nozzle PV", "Barrel Nozzle SV"),
        ("Barrel Rear Rear PV", "Barrel Rear Rear SV"),
        *[(f"HR Block PV {i}", f"HR Block SV {i}") for i in range(1, 5)],
        *[(f"Nozzle 1{c} PV", f"Nozzle 1{c} SV") for c in "ABCDEFGHIJKL"],
        *[(f"Nozzle 2{c} PV", f"Nozzle 2{c} SV") for c in "ABCDEFGHIJKL"],
        *[(f"H Pot PV {i}", f"H Pot SV {i}") for i in range(1, 19)],
    ],
}

# Backward-compat: legacy import expects flat WATCH_PAIRS (70DPW pairs).
WATCH_PAIRS = WATCH_PAIRS_BY_TYPE["70DPW"]


def _get_watch_pairs(machine_id: int) -> list[tuple[str, str]]:
    try:
        mtype = get_machine_type(machine_id)
    except KeyError:
        return WATCH_PAIRS_BY_TYPE["70DPW"]
    return WATCH_PAIRS_BY_TYPE.get(mtype, WATCH_PAIRS_BY_TYPE["70DPW"])


def check_notifications(machine_id, values, cycle_limits):

    alerts = []
    auto_cycle = values.get("Auto Cycle")
    blow_time = values.get("Blow Time")

    if auto_cycle == 1 and (blow_time or 0) > 1:
        # --- check PV / SV pairs for this machine's type ---
        for pv_tag, sv_tag in _get_watch_pairs(machine_id):

            pv = values.get(pv_tag)
            sv = values.get(sv_tag)

            # ignore if either missing or SV is zero (can't compute % deviation)
            if pv is None or sv is None or sv == 0:
                continue

            percent = abs(pv - sv) / sv * 100
            if percent > 5:
                alerts.append(
                    f"Machine {machine_id}: {pv_tag} deviated by {percent:.2f}%, the {sv_tag} is set at {sv} and the {pv_tag} is at {pv}"
                )

        # --- cycle time comparison ---
        cycle_val = values.get("Cycle Time")
        cycle_limit = cycle_limits.get(str(machine_id))

        if cycle_val and cycle_limit:
            if cycle_val > cycle_limit:
                alerts.append(
                    f"Machine {machine_id}: Cycle time exceeded {cycle_val} > {cycle_limit}"
                )

        # oil temperature comparison — alert when actual (PV) exceeds setpoint (SV) by 10°+
        oil_temperature_sv = values.get("Oil Temperature SV")
        oil_temperature_pv = values.get("Oil Temperature PV")
        if oil_temperature_sv is not None and oil_temperature_pv is not None:
            diff = oil_temperature_pv - oil_temperature_sv
            if diff >= 10:
                alerts.append(
                    f"Machine {machine_id}:Oil Temperature is high,the Oil Temperature PV is at {oil_temperature_pv}.The Oil Temperature SV is set at {oil_temperature_sv} "
                )
    alert_flag = 1 if alerts else 0
    return alerts, alert_flag
