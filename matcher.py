# Matching logic: who can donate to whom, how far, and how good a match each donor is.
import math
from datetime import date, datetime, timedelta
import pandas as pd
import db, cities

MAX_RADIUS_KM = 50
COOLDOWN_DAYS = 90

# recipient group -> donor groups who can give
COMPAT = {
    "O-": ["O-"], "O+": ["O+", "O-"],
    "A-": ["A-", "O-"], "A+": ["A+", "A-", "O+", "O-"],
    "B-": ["B-", "O-"], "B+": ["B+", "B-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": ["AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"],
}


def can_donate_to(donor_group):
    """Blood groups that a donor of this group can give to."""
    return [r for r, donors in COMPAT.items() if donor_group in donors]


def haversine(town1, town2):
    """Distance in km between two towns (Haversine formula). None if a town is unknown."""
    c1 = cities.get_coords(town1)
    c2 = cities.get_coords(town2)
    if not c1 or not c2:
        return None
    if isinstance(town1, str) and isinstance(town2, str) and town1.strip().lower() == town2.strip().lower():
        return 0.0
    lat1, lon1 = c1
    lat2, lon2 = c2
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _last_date(last):
    if not isinstance(last, str) or not last.strip():
        return None
    try:
        return datetime.strptime(last.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def days_until_eligible(last):
    """0 if the donor can donate today, otherwise the number of days left in the 90-day rule."""
    d = _last_date(last)
    if d is None:
        return 0
    return max(0, COOLDOWN_DAYS - (date.today() - d).days)


def next_eligible_date(last):
    d = _last_date(last)
    return (d + timedelta(days=COOLDOWN_DAYS)) if d else date.today()


def is_eligible(last):
    """True if the donor never donated, or donated 90+ days ago. Handles None / NaN / bad values."""
    return days_until_eligible(last) == 0


def eligibility_label(last, available=1):
    """Text shown in the donor directory."""
    if available is not None and not pd.isna(available) and int(available) == 0:
        return "Paused"
    n = days_until_eligible(last)
    return "Eligible" if n == 0 else f"Eligible in {n}d"


def _score(distance, exact, radius):
    """0-100. Closer is better, and the exact blood group beats a compatible one."""
    base = 100 - (distance / max(radius, 1)) * 60
    if not exact:
        base -= 15
    return round(max(0.0, min(100.0, base)), 0)


def find_donors(bg, city, area=None, *args, radius=MAX_RADIUS_KM, **kwargs):
    """Search wider step by step. Returns (stage_name, donors_dataframe).
    The dataframe has distance_km, match ('Exact' / 'Compatible') and score (0-100)."""
    empty = pd.DataFrame()
    df = db.table("donors")
    if df.empty:
        return None, df
    radius = int(radius or MAX_RADIUS_KM)

    exclude_ids = kwargs.get("exclude_ids") or kwargs.get("exclude_donor_ids")
    if exclude_ids:
        df = df[~df["id"].isin(list(exclude_ids))]
        if df.empty:
            return None, df

    # donors who paused themselves are never contacted
    if "available" in df.columns:
        df = df[df["available"].fillna(1).astype(int) == 1]
    # 90-day rule
    df = df[df["last_donation"].apply(is_eligible)].copy()
    if df.empty:
        return None, df

    if not cities.get_coords(city):
        return None, df.iloc[0:0]

    # donors whose city is not in the town list are ignored
    df["distance_km"] = df["city"].apply(lambda c: haversine(c, city))
    df = df[df["distance_km"].notna() & (df["distance_km"] <= radius)].copy()
    if df.empty:
        return None, df

    df["distance_km"] = df["distance_km"].round(1)
    req_city = city.strip().lower()
    same_town = df["city"].astype(str).str.strip().str.lower() == req_city
    exact = df["blood_group"] == bg
    compat = df["blood_group"].isin(COMPAT.get(bg, []))
    df["match"] = exact.map({True: "Exact", False: "Compatible"})
    df["score"] = [_score(d, e, radius) for d, e in zip(df["distance_km"], exact)]

    steps = sorted({s for s in (10, 25, radius) if s <= radius})
    stages = [("Same blood group, same town", exact & same_town)]
    stages += [(f"Same blood group within {s} km", exact & (df["distance_km"] <= s)) for s in steps]
    stages += [("Compatible blood groups, same town", compat & same_town)]
    stages += [(f"Compatible blood groups within {s} km", compat & (df["distance_km"] <= s)) for s in steps if s >= 25]
    if not any(s >= 25 for s in steps):
        stages += [(f"Compatible blood groups within {radius} km", compat & (df["distance_km"] <= radius))]

    for name, mask in stages:
        found = df[mask]
        if not found.empty:
            return name, found.sort_values(["score", "distance_km"], ascending=[False, True])
    return None, df.iloc[0:0]


def supply_demand(donors_df, requests_df):
    """For each blood group: units still needed vs eligible compatible donors available.
    Used for the shortage warnings on the analytics page."""
    rows = []
    elig = pd.DataFrame()
    if donors_df is not None and not donors_df.empty:
        elig = donors_df[donors_df["last_donation"].apply(is_eligible)]
        if "available" in elig.columns:
            elig = elig[elig["available"].fillna(1).astype(int) == 1]
    for g in COMPAT:
        need = 0
        if requests_df is not None and not requests_df.empty:
            open_r = requests_df[(requests_df["blood_group"] == g) & requests_df["status"].isin(db.OPEN_STATUSES)]
            need = int((open_r["units"] - open_r["confirmed"]).clip(lower=0).sum())
        have = int(elig["blood_group"].isin(COMPAT[g]).sum()) if not elig.empty else 0
        exact_have = int((elig["blood_group"] == g).sum()) if not elig.empty else 0
        if need == 0:
            status = "OK" if have >= 3 else "Low"
        elif have >= need * 3:
            status = "OK"
        elif have >= need:
            status = "Low"
        else:
            status = "Shortage"
        rows.append({"blood_group": g, "needed_units": need, "same_group_donors": exact_have,
                     "compatible_donors": have, "supply": status})
    return pd.DataFrame(rows)
