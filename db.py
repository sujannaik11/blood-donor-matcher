# Database helpers (SQLite). No Streamlit in here, so it can be tested on its own.
import os, sqlite3
from datetime import date, datetime
import pandas as pd

DB = os.getenv("DB_PATH", "data/donors.db")
os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)

OPEN_STATUSES = ("Pending", "Notified", "Partial")
CLOSED_STATUSES = ("Fulfilled", "Cancelled")
_TABLES = {"donors", "requests", "blood_banks", "notified", "responses", "activity"}


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def conn():
    return sqlite3.connect(DB, timeout=10)


def _add_columns(c, table, wanted):
    have = [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
    for col, ddl in wanted:
        if col not in have:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


def init():
    c = conn()
    c.execute("""CREATE TABLE IF NOT EXISTS donors(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, phone TEXT,
        blood_group TEXT, city TEXT, area TEXT, last_donation TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT, patient TEXT, blood_group TEXT,
        hospital TEXT, city TEXT, area TEXT, nearby TEXT, urgency TEXT,
        contact TEXT, status TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS blood_banks(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, city TEXT, email TEXT, phone TEXT)""")
    # which donors were emailed for which request, and what they answered
    c.execute("""CREATE TABLE IF NOT EXISTS notified(
        id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER, donor_id INTEGER,
        response TEXT DEFAULT 'No reply', reply_text TEXT, responded_at TEXT,
        ack_sent INTEGER DEFAULT 0, token TEXT)""")
    # donors confirmed by the coordinator
    c.execute("""CREATE TABLE IF NOT EXISTS responses(
        id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER, donor_id INTEGER,
        responded_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    # Gmail messages already processed (so a reply is never counted twice)
    c.execute("CREATE TABLE IF NOT EXISTS mail_seen(message_id TEXT PRIMARY KEY)")
    # audit trail of everything important that happens
    c.execute("""CREATE TABLE IF NOT EXISTS activity(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, message TEXT)""")

    # safe migrations for databases created by older versions
    _add_columns(c, "notified", [("response", "TEXT DEFAULT 'No reply'"), ("reply_text", "TEXT"),
                                 ("responded_at", "TEXT"), ("ack_sent", "INTEGER DEFAULT 0"), ("token", "TEXT")])
    _add_columns(c, "donors", [("available", "INTEGER DEFAULT 1"), ("created", "TEXT")])
    _add_columns(c, "requests", [("units", "INTEGER DEFAULT 1"), ("radius", "INTEGER DEFAULT 50"),
                                 ("closed_reason", "TEXT")])
    c.execute("CREATE INDEX IF NOT EXISTS ix_notified_req ON notified(request_id, donor_id)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_donors_email ON donors(email)")
    c.commit(); c.close()


def table(name):
    if name not in _TABLES:
        raise ValueError(f"unknown table {name}")
    c = conn(); df = pd.read_sql(f"SELECT * FROM {name}", c); c.close()
    return df


# ---------- activity log ----------
def log_activity(kind, message):
    try:
        c = conn()
        c.execute("INSERT INTO activity(ts, kind, message) VALUES(?,?,?)", (now(), kind, message))
        c.commit(); c.close()
    except Exception:
        pass   # the log must never break the app


def recent_activity(limit=30):
    c = conn()
    df = pd.read_sql("SELECT ts, kind, message FROM activity ORDER BY id DESC LIMIT ?", c, params=(limit,))
    c.close()
    return df


# ---------- donors ----------
def add_donor(name, email, phone, bg, city, area, last, available=1):
    c = conn()
    cur = c.execute("""INSERT INTO donors(name,email,phone,blood_group,city,area,last_donation,available,created)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (name.strip(), email.strip(), phone.strip(), bg, city.strip().lower(),
                     (area or "").strip().lower(), last, int(bool(available)), now()))
    c.commit(); did = cur.lastrowid; c.close()
    log_activity("donor", f"Donor registered: {name.strip()} ({bg}, {city.strip().title()})")
    return did


def email_exists(email, exclude_id=None):
    c = conn()
    row = c.execute("SELECT 1 FROM donors WHERE lower(email)=? AND id IS NOT ?",
                    (email.strip().lower(), exclude_id)).fetchone()
    c.close()
    return row is not None


def get_donor(donor_id):
    c = conn()
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM donors WHERE id=?", (donor_id,)).fetchone()
    res = dict(row) if row else None
    c.close()
    return res


def update_donor(donor_id, name, email, phone, bg, city, area, last, available=1):
    c = conn()
    c.execute("""UPDATE donors SET name=?, email=?, phone=?, blood_group=?, city=?, area=?, last_donation=?,
                 available=? WHERE id=?""",
              (name.strip(), email.strip(), phone.strip(), bg, city.strip().lower(),
               (area or "").strip().lower(), last, int(bool(available)), donor_id))
    c.commit(); c.close()
    log_activity("donor", f"Donor updated: {name.strip()}")


def set_available(donor_id, val):
    c = conn()
    c.execute("UPDATE donors SET available=? WHERE id=?", (int(bool(val)), donor_id))
    c.commit(); c.close()


def delete_donor(donor_id):
    """Remove a donor and their email/confirmation history."""
    d = get_donor(donor_id)
    c = conn()
    c.execute("DELETE FROM notified WHERE donor_id=?", (donor_id,))
    c.execute("DELETE FROM responses WHERE donor_id=?", (donor_id,))
    c.execute("DELETE FROM donors WHERE id=?", (donor_id,))
    c.commit(); c.close()
    if d:
        log_activity("donor", f"Donor deleted: {d['name']}")


def donor_stats():
    """Per donor: how many requests emailed / accepted / confirmed."""
    c = conn()
    df = pd.read_sql("""SELECT d.id,
        (SELECT COUNT(*) FROM notified n WHERE n.donor_id = d.id) AS emailed,
        (SELECT COUNT(*) FROM notified n WHERE n.donor_id = d.id AND n.response = 'Accepted') AS accepted,
        (SELECT COUNT(*) FROM responses x WHERE x.donor_id = d.id) AS donations
        FROM donors d""", c)
    c.close()
    return df


def confirmed_donations():
    """Every confirmed donation with donor and request details (newest first)."""
    c = conn()
    df = pd.read_sql("""SELECT x.id AS donation_id, x.request_id, x.donor_id, x.responded_at AS donated_on,
        d.name, d.blood_group, d.city, r.hospital, r.patient
        FROM responses x JOIN donors d ON d.id = x.donor_id
        LEFT JOIN requests r ON r.id = x.request_id ORDER BY x.id DESC""", c)
    c.close()
    return df


# ---------- blood banks ----------
def add_blood_bank(name, city, email, phone):
    c = conn()
    c.execute("INSERT INTO blood_banks(name,city,email,phone) VALUES(?,?,?,?)",
              (name.strip(), city.strip().lower(), email.strip(), phone.strip()))
    c.commit(); c.close()
    log_activity("bank", f"Blood bank added: {name.strip()}")


def update_blood_bank(bank_id, name, city, email, phone):
    c = conn()
    c.execute("UPDATE blood_banks SET name=?, city=?, email=?, phone=? WHERE id=?",
              (name.strip(), city.strip().lower(), email.strip(), phone.strip(), bank_id))
    c.commit(); c.close()


def delete_blood_bank(bank_id):
    c = conn()
    c.execute("DELETE FROM blood_banks WHERE id=?", (bank_id,))
    c.commit(); c.close()


# ---------- requests ----------
def add_request(patient, bg, hospital, city, area, nearby, urgency, contact, status, units=1, radius=50):
    c = conn()
    cur = c.execute("""INSERT INTO requests(patient,blood_group,hospital,city,area,nearby,urgency,contact,status,
                       units,radius,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (patient.strip(), bg, hospital.strip(), city.strip().lower(), (area or "").strip().lower(),
                     (nearby or "").strip().lower(), urgency, contact.strip(), status, int(units), int(radius), now()))
    c.commit(); rid = cur.lastrowid; c.close()
    log_activity("request", f"Request #{rid} created: {bg} for {patient.strip()} ({urgency}, {int(units)} unit(s))")
    return rid


def set_status(rid, status):
    c = conn(); c.execute("UPDATE requests SET status=? WHERE id=?", (status, rid)); c.commit(); c.close()
    if status == "Fulfilled":
        log_activity("request", f"Request #{rid} marked Fulfilled")


def cancel_request(rid, reason=""):
    c = conn()
    c.execute("UPDATE requests SET status='Cancelled', closed_reason=? WHERE id=?", (reason, rid))
    c.commit(); c.close()
    log_activity("request", f"Request #{rid} cancelled" + (f": {reason}" if reason else ""))


def get_request(request_id):
    c = conn()
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
    res = dict(row) if row else None
    c.close()
    return res


# ---------- notified donors / replies ----------
def log_notified(request_id, donor_id, token):
    """Remember that a donor was emailed (with their private response link token)."""
    c = conn()
    row = c.execute("SELECT id FROM notified WHERE request_id=? AND donor_id=?", (request_id, donor_id)).fetchone()
    if row:
        c.execute("UPDATE notified SET token=? WHERE id=?", (token, row[0]))
    else:
        c.execute("INSERT INTO notified(request_id, donor_id, token) VALUES(?,?,?)", (request_id, donor_id, token))
    c.commit(); c.close()


def notified_donors(request_id):
    c = conn()
    df = pd.read_sql("""SELECT d.id, d.name, d.email, d.blood_group, d.phone,
                        n.response, n.reply_text, n.responded_at, n.ack_sent,
                        EXISTS(SELECT 1 FROM responses x WHERE x.request_id = n.request_id
                               AND x.donor_id = n.donor_id) AS confirmed
                        FROM notified n JOIN donors d ON d.id = n.donor_id
                        WHERE n.request_id = ? ORDER BY n.id""", c, params=(request_id,))
    c.close()
    return df


def get_notified_by_email(request_id, email):
    c = conn()
    c.row_factory = sqlite3.Row
    row = c.execute("""SELECT d.id, d.name, d.email, d.phone, d.blood_group, d.city, d.area
        FROM notified n JOIN donors d ON d.id = n.donor_id
        WHERE n.request_id = ? AND lower(d.email) = ?""", (request_id, email.strip().lower())).fetchone()
    res = dict(row) if row else None
    c.close()
    return res


def get_notified_by_token(request_id, donor_id, token):
    """Used by the link in the email. Returns donor info + current response, or None."""
    if not token:
        return None
    c = conn()
    c.row_factory = sqlite3.Row
    row = c.execute("""SELECT d.id, d.name, d.email, d.phone, d.blood_group, n.response
        FROM notified n JOIN donors d ON d.id = n.donor_id
        WHERE n.request_id=? AND n.donor_id=? AND n.token=?""", (request_id, donor_id, token)).fetchone()
    res = dict(row) if row else None
    c.close()
    return res


def set_reply(request_id, donor_id, response, reply_text=""):
    """Save a donor's answer. Returns False if the request is already closed."""
    c = conn()
    req = c.execute("SELECT status FROM requests WHERE id=?", (request_id,)).fetchone()
    if not req or req[0] in CLOSED_STATUSES:
        c.close()
        return False
    c.execute("""UPDATE notified SET response=?, reply_text=?, responded_at=?
                 WHERE request_id=? AND donor_id=?""", (response, reply_text, now(), request_id, donor_id))
    c.commit()
    d = c.execute("SELECT name FROM donors WHERE id=?", (donor_id,)).fetchone()
    c.close()
    if d:
        log_activity("reply", f"{d[0]} answered {response} for request #{request_id}")
    return True


def is_ack_sent(request_id, donor_id):
    c = conn()
    row = c.execute("SELECT ack_sent FROM notified WHERE request_id=? AND donor_id=?", (request_id, donor_id)).fetchone()
    c.close()
    return bool(row and row[0])


def set_ack_sent(request_id, donor_id, val=1):
    c = conn()
    c.execute("UPDATE notified SET ack_sent=? WHERE request_id=? AND donor_id=?", (val, request_id, donor_id))
    c.commit(); c.close()


def mail_processed(message_id):
    c = conn()
    row = c.execute("SELECT 1 FROM mail_seen WHERE message_id=?", (message_id,)).fetchone()
    c.close()
    return row is not None


def mark_mail(message_id):
    c = conn()
    c.execute("INSERT OR IGNORE INTO mail_seen(message_id) VALUES(?)", (message_id,))
    c.commit(); c.close()


# ---------- confirmation ----------
def confirmed_count(request_id):
    c = conn()
    n = c.execute("SELECT COUNT(*) FROM responses WHERE request_id=?", (request_id,)).fetchone()[0]
    c.close()
    return n


def confirm_donor(request_id, donor_id):
    """Coordinator confirms one accepted donor.
    The request becomes 'Fulfilled' when enough donors are confirmed (units needed), otherwise 'Partial'.
    Returns True if the request is now fulfilled."""
    today = date.today().strftime("%Y-%m-%d")
    c = conn()
    if not c.execute("SELECT 1 FROM responses WHERE request_id=? AND donor_id=?", (request_id, donor_id)).fetchone():
        c.execute("INSERT INTO responses(request_id, donor_id, responded_at) VALUES(?,?,?)",
                  (request_id, donor_id, now()))
    c.execute("UPDATE donors SET last_donation=? WHERE id=?", (today, donor_id))
    units = c.execute("SELECT COALESCE(units,1) FROM requests WHERE id=?", (request_id,)).fetchone()
    units = units[0] if units else 1
    have = c.execute("SELECT COUNT(*) FROM responses WHERE request_id=?", (request_id,)).fetchone()[0]
    fulfilled = have >= units
    c.execute("UPDATE requests SET status=? WHERE id=?", ("Fulfilled" if fulfilled else "Partial", request_id))
    d = c.execute("SELECT name FROM donors WHERE id=?", (donor_id,)).fetchone()
    c.commit(); c.close()
    log_activity("confirm", f"{d[0] if d else 'Donor'} confirmed for request #{request_id} ({have}/{units})"
                 + (" - FULFILLED" if fulfilled else ""))
    return fulfilled


def accepted_donors(request_id, exclude_id=None):
    """Donors who accepted a request (used to tell the others 'no longer needed')."""
    df = notified_donors(request_id)
    if df.empty:
        return df
    df = df[df["response"] == "Accepted"]
    if exclude_id is not None:
        df = df[df["id"] != exclude_id]
    return df


# ---------- dashboard / analytics queries ----------
def request_stats():
    c = conn()
    df = pd.read_sql("""SELECT r.id, r.patient, r.blood_group, r.hospital, r.city, r.urgency, r.status, r.created,
        COALESCE(r.units,1) AS units, COALESCE(r.radius,50) AS radius, r.closed_reason,
        (SELECT COUNT(*) FROM notified n WHERE n.request_id = r.id) AS emailed,
        (SELECT COUNT(*) FROM notified n WHERE n.request_id = r.id AND n.response = 'Accepted') AS accepted,
        (SELECT COUNT(*) FROM notified n WHERE n.request_id = r.id AND n.response = 'Declined') AS declined,
        (SELECT COUNT(*) FROM notified n WHERE n.request_id = r.id AND n.response = 'Needs review') AS needs_review,
        (SELECT COUNT(*) FROM notified n WHERE n.request_id = r.id AND (n.response = 'No reply' OR n.response IS NULL)) AS no_reply,
        (SELECT COUNT(*) FROM responses x WHERE x.request_id = r.id) AS confirmed
        FROM requests r ORDER BY r.id DESC""", c)
    c.close()
    return df


def pending_approvals():
    """Donors who said YES, are not confirmed yet, for requests that are still open."""
    c = conn()
    df = pd.read_sql("""
        SELECT n.request_id, n.donor_id, n.reply_text, n.responded_at,
               d.name AS donor_name, d.phone AS donor_phone, d.blood_group AS donor_blood_group,
               r.patient, r.hospital, r.city, r.urgency, r.blood_group AS needed_group,
               COALESCE(r.units,1) AS units, r.contact
        FROM notified n
        JOIN donors d ON d.id = n.donor_id
        JOIN requests r ON r.id = n.request_id
        WHERE n.response = 'Accepted'
          AND r.status NOT IN ('Fulfilled','Cancelled')
          AND NOT EXISTS (SELECT 1 FROM responses x WHERE x.request_id = n.request_id AND x.donor_id = n.donor_id)
        ORDER BY n.id DESC""", c)
    c.close()
    return df


def funnel():
    """Overall email -> reply -> accepted -> confirmed numbers."""
    c = conn()
    emailed = c.execute("SELECT COUNT(*) FROM notified").fetchone()[0]
    replied = c.execute("SELECT COUNT(*) FROM notified WHERE response IS NOT NULL AND response != 'No reply'").fetchone()[0]
    accepted = c.execute("SELECT COUNT(*) FROM notified WHERE response = 'Accepted'").fetchone()[0]
    confirmed = c.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
    c.close()
    return {"Emailed": emailed, "Replied": replied, "Said yes": accepted, "Confirmed": confirmed}


def response_minutes():
    """Minutes between a request being created and each donor reply."""
    c = conn()
    df = pd.read_sql("""SELECT n.responded_at, r.created FROM notified n JOIN requests r ON r.id = n.request_id
                        WHERE n.responded_at IS NOT NULL""", c)
    c.close()
    if df.empty:
        return pd.Series(dtype=float)
    delta = (pd.to_datetime(df["responded_at"], errors="coerce") - pd.to_datetime(df["created"], errors="coerce"))
    mins = delta.dt.total_seconds() / 60
    return mins[(mins >= 0) & mins.notna()]
