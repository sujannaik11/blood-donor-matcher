"""Fills the database with FAKE demo data (fake names, example.com emails, 99999xxxxx phones).
Run once:  python seed_demo.py      (Docker: docker compose run --rm app python seed_demo.py)
Safe to run on an empty database only; it refuses if donors already exist."""
import db

db.init()
if len(db.table("donors")) > 0:
    raise SystemExit("Database already has donors. Delete data/donors.db first if you want a fresh demo.")

DEMO = [
    ("Demo Donor One",   "donor1@example.com", "9999999901", "O+",  "Mangaluru", "Kadri"),
    ("Demo Donor Two",   "donor2@example.com", "9999999902", "A+",  "Udupi",     ""),
    ("Demo Donor Three", "donor3@example.com", "9999999903", "B+",  "Bhatkal",   ""),
    ("Demo Donor Four",  "donor4@example.com", "9999999904", "O-",  "Karwar",    ""),
    ("Demo Donor Five",  "donor5@example.com", "9999999905", "AB+", "Hubballi",  ""),
    ("Demo Donor Six",   "donor6@example.com", "9999999906", "A-",  "Bengaluru", "Indiranagar"),
]
for name, email, phone, bg, city, area in DEMO:
    db.add_donor(name, email, phone, bg, city, area, None)
print(f"Added {len(DEMO)} fake demo donors. Emails use example.com, so no real email is ever sent to anyone.")
