# Dictionary of towns and their latitude/longitude coordinates.
# Easy to add more towns: just add "Town Name": (latitude, longitude)
CITIES = {
    "Bengaluru": (12.9716, 77.5946),
    "Mysuru": (12.2958, 76.6394),
    "Mangaluru": (12.9141, 74.8560),
    "Udupi": (13.3409, 74.7421),
    "Kundapura": (13.6288, 74.6917),
    "Bhatkal": (13.9787, 74.5513),
    "Murdeshwar": (14.0940, 74.4899),
    "Honnavar": (14.2802, 74.4439),
    "Kumta": (14.4259, 74.4172),
    "Gokarna": (14.5479, 74.3188),
    "Karwar": (14.8158, 74.1332),
    "Sirsi": (14.6195, 74.8354),
    "Hubballi": (15.3647, 75.1240),
    "Dharwad": (15.4589, 75.0078),
    "Belagavi": (15.8497, 74.4977),
    "Shivamogga": (13.9299, 75.5681),
}

TOWNS = list(CITIES.keys())

def get_coords(town):
    """Case-insensitive lookup of town coordinates. Returns (lat, lon) or None."""
    if not town or not isinstance(town, str):
        return None
    cleaned = town.strip().lower()
    for name, coords in CITIES.items():
        if name.lower() == cleaned:
            return coords
    return None
