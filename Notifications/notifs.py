from datetime import datetime


WATCH_PAIRS = [
    ("Barrel Rear Front PV","Barrel Rear Front SV"),
    ("Barrel Middle PV","Barrel Middle SV"),
    ("Barrel Front PV","Barrel Front SV"),
    ("Barrel Nozzle PV","Barrel Nozzle SV"),
    ("Barrel Rear Rear PV","Barrel Rear Rear SV"),
    ("HR Block 1 PV","HR Block 1 SV"),
    ("HR Block 2 PV","HR Block 2 SV"),
    ("HR Block 3 PV","HR Block 3 SV"),
    ("HR Block 4 PV","HR Block 4 SV"),
    ("HR Sprue PV","HR Sprue SV"),
    ("HR Nozzle 1 PV","HR Nozzle 1 SV"),
    ("HR Nozzle 2 PV","HR Nozzle 2 SV"),
    ("HR Nozzle 3 PV","HR Nozzle 3 SV"),
    ("HR Nozzle 4 PV","HR Nozzle 4 SV"),
    ("HR Nozzle 5 PV","HR Nozzle 5 SV"),
    ("HR Nozzle 6 PV","HR Nozzle 6 SV"),
    ("HR Nozzle 7 PV","HR Nozzle 7 SV"),
    ("HR Nozzle 8 PV","HR Nozzle 8 SV"),
    ("HR Nozzle 9 PV","HR Nozzle 9 SV"),
    ("HR Nozzle 10 PV","HR Nozzle 10 SV"),
    ("HR Nozzle 11 PV","HR Nozzle 11 SV"),
    ("HR Nozzle 12 PV","HR Nozzle 12 SV"),
    ("HR Nozzle 13 PV","HR Nozzle 13 SV"),
    ("HR Nozzle 14 PV","HR Nozzle 14 SV"),
    ("HR Nozzle 15 PV","HR Nozzle 15 SV"),
    ("HR Nozzle 16 PV","HR Nozzle 16 SV"),
    ("HR Nozzle 17 PV","HR Nozzle 17 SV"),
    ("HR Nozzle 18 PV","HR Nozzle 18 SV"),
    ("HR Nozzle 19 PV","HR Nozzle 19 SV"),
    ("HR Nozzle 20 PV","HR Nozzle 20 SV"),
    ("HR Nozzle 21 PV","HR Nozzle 21 SV"),
    ("HR Nozzle 22 PV","HR Nozzle 22 SV"),
    ("HR Nozzle 23 PV","HR Nozzle 23 SV"),
    ("HR Nozzle 24 PV","HR Nozzle 24 SV"),
    ("H Pot 1 PV","H Pot 1 SV"),
    ("H Pot 2 PV","H Pot 2 SV"),
    ("H Pot 3 PV","H Pot 3 SV"),
    ("H Pot 4 PV","H Pot 4 SV"),
    ("H Pot 5 PV","H Pot 5 SV"),
    ("H Pot 6 PV","H Pot 6 SV"),
    ("H Pot 7 PV","H Pot 7 SV"),
    ("H Pot 8 PV","H Pot 8 SV"),
    ("H Pot 9 PV","H Pot 9 SV"),
    ("H Pot 10 PV","H Pot 10 SV"),
    ("H Pot 11 PV","H Pot 11 SV"),
    ("H Pot 12 PV","H Pot 12 SV"),
    ("H Pot 13 PV","H Pot 13 SV"),
    ("H Pot 14 PV","H Pot 14 SV"),
    ("H Pot 15 PV","H Pot 15 SV"),
    ("H Pot 16 PV","H Pot 16 SV"),
    ("H Pot 17 PV","H Pot 17 SV"),
    ("H Pot 18 PV","H Pot 18 SV"),
    ("H Pot 19 PV","H Pot 19 SV"),
    ("H Pot 20 PV","H Pot 20 SV"),
    ("H Pot 21 PV","H Pot 21 SV"),
    ("H Pot 22 PV","H Pot 22 SV"),
    ("H Pot 23 PV","H Pot 23 SV"),
    ("H Pot 24 PV","H Pot 24 SV"),
    ("H Pot 25 PV","H Pot 25 SV"),
    ("H Pot 26 PV","H Pot 26 SV"),
    ("H Pot 27 PV","H Pot 27 SV"),
    ("H Pot 28 PV","H Pot 28 SV"),
    ("H Pot 29 PV","H Pot 29 SV"),
    ("H Pot 30 PV","H Pot 30 SV"),
    ("H Pot 31 PV","H Pot 31 SV"),
    ("H Pot 32 PV","H Pot 32 SV"),
    ("H Pot 33 PV","H Pot 33 SV"),
    ("H Pot 34 PV","H Pot 34 SV"),
    ("H Pot 35 PV","H Pot 35 SV"),
    ("H Pot 36 PV","H Pot 36 SV"),
    ("H Pot 37 PV","H Pot 37 SV"),
    ("H Pot 38 PV","H Pot 38 SV"),
    ("H Pot 39 PV","H Pot 39 SV"),
    ("H Pot 40 PV","H Pot 40 SV")
    
]

def check_notifications(machine_id, values, cycle_limits):

    alerts = []

    # --- check PV / SV pairs ---
    for pv_tag, sv_tag in WATCH_PAIRS:

        pv = values.get(pv_tag)
        sv = values.get(sv_tag)

        # ignore if either missing
        if pv is None or sv is None:
            continue

        
        percent = abs(pv - sv) / sv * 100
        if percent > 5:
            alerts.append(
                f"Machine {machine_id}: {pv_tag} is at {pv} deviated >5% ({percent:.2f}%), the {sv_tag} is set at {sv}"
            )

    # --- cycle time comparison ---
    cycle_val = values.get("Cycle Time")
    cycle_limit = cycle_limits.get(str(machine_id))

    if cycle_val and cycle_limit:
        if cycle_val > cycle_limit:
            alerts.append(
                f"Machine {machine_id}: Cycle time exceeded {cycle_val} > {cycle_limit}"
            )
            
    # oil temperature comparison
    oil_temperature_sv = values.get("Oil Temperature SV")
    oil_temperature_pv = values.get("Oil Temperature PV")
    diff = oil_temperature_sv - oil_temperature_pv
    if diff <= 1.5:
        alerts.append(
            f"Machine {machine_id}:Oil Temperature is high,the Oil Temperature PV is at {oil_temperature_pv}.The Oil Temperature SV is set at {oil_temperature_sv} "
        )

    return alerts
