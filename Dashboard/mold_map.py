MOLD_MAP = {
    10: "1 Litre Bottle",
    11: "500 ml Bottle",
    12: "5 Litre Jar",
    20: "200 ml Bottle",
    30: "Spray Bottle",
}

def get_bottle_type(mold_number: int):
    """Return bottle type if exists, else None."""
    return MOLD_MAP.get(mold_number)