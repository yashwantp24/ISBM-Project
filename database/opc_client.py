import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


from opcua import Client
from datetime import datetime
from database.scaling import SCALING_MAP

class OPCClient:
    def __init__(self, url: str, scale_map: dict = None):
        self.url = url
        self.client = Client(url)
        self.connected = False
        self.scale_map = scale_map or {}

        self.connect()  # connect once

    def connect(self):
        """Connect only if not already connected"""
        if self.connected:
            return

        try:
            self.client.connect()
            self.connected = True
            print("OPC UA Connected")
        except Exception as e:
            self.connected = False
            raise RuntimeError(f"OPC UA connection failed: {e}")

    def disconnect(self):
        """Gracefully close session"""
        if self.client and self.connected:
            try:
                self.client.disconnect()
            finally:
                self.connected = False
                self.client = None

    def read_machine(self, machine_id: int, tag_map: dict):
        """Reads all tags for one machine, applies scaling, and cleans PV/SV if idle."""
        try:
            tags = tag_map[machine_id]
        except KeyError:
            raise ValueError(f"Machine {machine_id} missing in tag_map")

        values = {}
        for tag_name, node_id in tags.items():
            try:
                node = self.client.get_node(node_id)
                val = node.get_value()
            except:
                val = None

            
            factor = SCALING_MAP.get(tag_name, 1)
            if isinstance(val, (int, float)):
                val = val / factor

            values[tag_name] = val

        # PV/SV Cleaning
        for tag in list(values.keys()):
            if tag.endswith("PV") and values[tag] == 660:
                values[tag] = None
                sv_tag = tag.replace("PV", "SV")
                if sv_tag in values:
                    values[sv_tag] = None

        # Auto add metadata
        values["machine_id"] = machine_id
        values["timestamp"] = datetime.now()

        # return if condition met
        if values.get("Auto Cycle") != 1 or values.get("Blow Time", 0) <= 0:
            return None

        return values
