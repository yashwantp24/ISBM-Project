import numpy as np

class CycleLogger:
    def __init__(self, client, machine_id, tag_map):
        self.client = client
        self.machine_id = machine_id
        self.tag_map = tag_map

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

        def safe_mean(key):
            vals = [v[key] for v in buf if v.get(key) is not None]
            return float(np.mean(vals)) if vals else None

        def safe_max(key):
            vals = [v[key] for v in buf if v.get(key) is not None]
            return float(max(vals)) if vals else None

        last = buf[-1]

        return {
            "timestamp": last["timestamp"],

            # Time SV
            "Injection Time": last.get("Injection Time"),
            "Cooling Time": last.get("Cooling Time"),
            "Stretch Time": last.get("Stretch Time"),
            "Blow Time": last.get("Blow Time"),

            # Time PV
            "Cycle Time":safe_max("Cycle Time"),
            "V-P Time PV":safe_max("V-P Time PV"),
            "Charge Time":safe_max("Charge Time"),
            "Injection Mold CL FA":safe_max("Injection Mold CL FA"),
            "Injection Mold OP FA":safe_max("Injection Mold OP FA"),
            "Lip Mold CL FA":safe_max("Lip Mold CL FA"),
            "Lip Mold OP FA":safe_max("Lip Mold OP FA"),
            "Blow Mold CL FA":safe_max("Blow Mold CL FA"),
            "Blow Mold OP FA":safe_max("Blow Mold OP FA"),
            "Dry Cycle Time":safe_max("Dry Cycle Time"),
            "Injection Mold CL":safe_max("Injection Mold CL"),
            "Injection Mold OP":safe_max("Injection Mold OP"),
            "Blow Core DW":safe_max("Blow Core DW"),
            "Blow Core UP":safe_max("Blow Core UP"),
            "Bottom UP":safe_max("Bottom UP"),
            "Bottom DW":safe_max("Bottom DW"),
            "Blow Mold CL":safe_max("Blow Mold CL"),
            "Blow Mold OP":safe_max("Blow Mold OP"),
            "Blow Core Hold FW":safe_max("Blow Core Hold FW"),
            "Stretch Unit DW FA":safe_max("Stretch Unit DW FA"),
            "Stretch Unit UP FA":safe_max("Stretch Unit UP FA"),
            "Stretch Unit DW":safe_max("Stretch Unit DW"),
            "Stretch Unit UP":safe_max("Stretch Unit UP"),
            "Blow Mold M":safe_max("Blow Mold M"),
            "Blow Mold C":safe_max("Blow Mold C"),           

            # Pressure
            "Main RAM Pressure": safe_max("Main Ram FW Pressure"),
            "Screw Pressure": safe_max("Screw Pressure Monitor"),

            # Temperature
            "Barrel Nozzle": safe_mean("Barrel Nozzle PV"),
            "Barrel Front": safe_mean("Barrel Front PV"),
            "Barrel Middle": safe_mean("Barrel Middle PV"),
            "Barrel Rear Front": safe_mean("Barrel Rear Front PV"),
            "Barrel Rear Rear": safe_mean("Barrel Rear Rear PV"),
            "Oil Temperature": safe_mean("Oil Temperature PV"),

            # Position
            "Shot Size PV": safe_max("Screw Position")
        }
