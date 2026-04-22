import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from opcua import Client, ua
from datetime import datetime
from threading import Lock
from database.scaling import SCALING_MAP


class SubHandler:
    """Handles incoming OPC UA subscription data changes and updates cache."""

    def __init__(self, cache, lock, nodemap, scale_map):
        self.cache = cache
        self.lock = lock
        self.nodemap = nodemap      # {node_id_str: (machine_id, tag_name)}
        self.scale_map = scale_map

    def datachange_notification(self, node, val, data):
        nid = node.nodeid.to_string()
        mapping = self.nodemap.get(nid)
        if mapping is None:
            return

        machine_id, tag_name = mapping

        # Apply scaling
        factor = self.scale_map.get(tag_name, 1)
        if isinstance(val, (int, float)):
            val = val / factor

        with self.lock:
            if machine_id not in self.cache:
                self.cache[machine_id] = {}
            self.cache[machine_id][tag_name] = val
            self.cache[machine_id]["_last_update"] = datetime.now()


class OPCClient:
    def __init__(self, url: str, scale_map: dict = None):
        self.url = url
        self.client = Client(url)
        self.connected = False
        self.scale_map = scale_map or SCALING_MAP

        # Shared cache: {machine_id: {tag_name: value, ...}}
        self.cache = {}
        self.lock = Lock()
        self.nodemap = {}       # {node_id_str: (machine_id, tag_name)}
        self.subscriptions = []

    # ── Connection ────────────────────────────────────────────

    def connect(self):
        """Connect only if not already connected."""
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
        """Gracefully close subscriptions and session."""
        for sub in self.subscriptions:
            try:
                sub.delete()
            except Exception:
                pass
        self.subscriptions.clear()

        if self.client and self.connected:
            try:
                self.client.disconnect()
            finally:
                self.connected = False
                print("OPC UA Disconnected")

    # ── Subscriptions (primary data path) ─────────────────────

    def subscribe_machines(self, machine_ids: list, tag_map: dict,
                           interval_ms: int = 250):
        """
        Subscribe to all tags for the given machines in a single
        OPC UA subscription. The server pushes value changes into
        the in-memory cache via SubHandler.
        """
        self.connect()

        handler = SubHandler(self.cache, self.lock, self.nodemap,
                             self.scale_map)
        sub = self.client.create_subscription(interval_ms, handler)

        all_nodes = []
        for mid in machine_ids:
            tags = tag_map.get(mid, {})
            for tag_name, node_id in tags.items():
                self.nodemap[node_id] = (mid, tag_name)
                all_nodes.append(self.client.get_node(node_id))

        # Bulk subscribe — one request
        sub.subscribe_data_change(all_nodes)
        self.subscriptions.append(sub)
        print(f"Subscribed: {len(machine_ids)} machines, "
              f"{len(all_nodes)} tags")

    # ── Cache read ────────────────

    def read_machine(self, machine_id: int, tag_map: dict) -> dict | None:
        """Read latest values from the in-memory cache"""
        with self.lock:
            data = self.cache.get(machine_id)
            if data is None:
                return None
            # Shallow copy so caller can mutate safely
            values = {k: v for k, v in data.items()
                      if not k.startswith("_")}

        # PV/SV Cleaning — same logic as original
        for tag in list(values.keys()):
            if tag.endswith("PV") and values[tag] == 660:
                values[tag] = None
                sv_tag = tag.replace("PV", "SV")
                if sv_tag in values:
                    values[sv_tag] = None

        # Metadata
        values["machine_id"] = machine_id
        values["timestamp"] = datetime.now()
        return values

    # ── Batch read (fallback / on-demand snapshot) ────────────

    def batch_read_machine(self, machine_id: int, tag_map: dict,
                           chunk_size: int = 50) -> dict:
        """
        One-shot batch read in chunks to avoid server timeout.
        Useful for initial cache seeding or diagnostics.
        """
        self.connect()
        self.client.uaclient.timeout = 30  # seconds

        tags = tag_map.get(machine_id, {})
        tag_names = list(tags.keys())
        node_ids = list(tags.values())

        values = {}
        for i in range(0, len(node_ids), chunk_size):
            chunk_names = tag_names[i:i + chunk_size]
            chunk_ids = node_ids[i:i + chunk_size]

            params = ua.ReadParameters()
            for nid in chunk_ids:
                rv = ua.ReadValueId()
                rv.NodeId = ua.NodeId.from_string(nid)
                rv.AttributeId = ua.AttributeIds.Value
                params.NodesToRead.append(rv)

            results = self.client.uaclient.read(params)

            for tag_name, result in zip(chunk_names, results):
                val = (result.Value.Value
                       if result.StatusCode.is_good() else None)
                factor = self.scale_map.get(tag_name, 1)
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

        values["machine_id"] = machine_id
        values["timestamp"] = datetime.now()
        return values