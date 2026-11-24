# Gmail sending. No Streamlit here: functions return (sent, errors) and the app shows the errors.
import os, secrets, smtplib, time
from html import escape
from email.message import EmailMessage
from dotenv import load_dotenv
import pandas as pd
import db

load_dotenv()

URGENCY_COLOR = {"Critical": "#C62828", "Within 24 hours": "#EF6C00", "Planned": "#2E7D32"}


def app_url():
    """Public address of this app. Put APP_URL=... in .env if donors open the link on another device."""
    return os.getenv("APP_URL", "http://localhost:8501").strip().rstrip("/")


def send_email(to, subject, body, html=None):
    user, pw = (os.getenv("EMAIL") or "").strip().strip("\"'"), (os.getenv("APP_PASSWORD") or "").strip().strip("\"'")
    if not user or not pw:
        raise ValueError("EMAIL or APP_PASSWORD is missing in .env")
    msg = EmailMessage()
    msg["From"] = f"Blood Donor Matcher <{user}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    pw = pw.replace(" ", "").strip()       # Google shows app passwords in 4 groups with spaces; they must be removed
    _deliver(user, pw, msg)


def _deliver(user, pw, msg):
    """Try Gmail on port 465 (SSL), then port 587 (STARTTLS), twice each time. Raises a readable error."""
    attempts = [("smtp.gmail.com", 465, True), ("smtp.gmail.com", 587, False)] * 2
    last = None
    for host, port, ssl in attempts:
        try:
            if ssl:
                with smtplib.SMTP_SSL(host, port, timeout=30) as s:
                    s.login(user, pw)
                    s.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=30) as s:
                    s.starttls()
                    s.login(user, pw)
                    s.send_message(msg)
            return
        except smtplib.SMTPAuthenticationError:
            raise RuntimeError("Gmail rejected the login. Create a NEW 16-letter app password "
                               "(Google Account > Security > 2-Step Verification > App passwords) and put it in .env as APP_PASSWORD.")
        except (smtplib.SMTPException, OSError) as e:      # disconnects, timeouts, blocked ports, DNS problems
            last = e
            time.sleep(1)
    raise RuntimeError(f"Could not reach Gmail on ports 465 or 587 ({last}). Check your internet, VPN, firewall or antivirus, "
                       "and that Docker has internet access.")


def _get(req, key, default=""):
    try:
        v = req[key]
    except (KeyError, IndexError):
        return default
    return default if v is None or (not isinstance(v, str) and pd.isna(v)) else v


def _dist_text(row):
    if "distance_km" in row and pd.notna(row["distance_km"]):
        d = row["distance_km"]
        return f" (about {int(d) if d == int(d) else d} km from the hospital)"
    return ""


def _layout(title, color, rows, button=None, footer=""):
    """Simple, mobile-friendly HTML email card. All values are escaped."""
    items = "".join(
        f"<tr><td style='padding:6px 0;color:#6b7280;width:110px;font-size:14px'>{escape(k)}</td>"
        f"<td style='padding:6px 0;color:#111827;font-size:15px;font-weight:600'>{escape(str(v))}</td></tr>"
        for k, v in rows)
    btn = ""
    if button:
        label, link = button
        btn = (f"<p style='margin:22px 0 6px'><a href='{escape(link)}' style='background:#C62828;color:#ffffff;"
               f"padding:14px 28px;border-radius:10px;text-decoration:none;font-weight:700;font-size:16px;"
               f"display:inline-block'>{escape(label)}</a></p>"
               f"<p style='color:#6b7280;font-size:13px;margin:6px 0'>Or simply reply to this email with YES or NO.</p>")
    return (f"<div style='background:#f6f7f9;padding:24px;font-family:Segoe UI,Arial,sans-serif'>"
            f"<div style='max-width:520px;margin:auto;background:#ffffff;border-radius:16px;overflow:hidden;"
            f"border:1px solid #e5e7eb'>"
            f"<div style='background:{color};padding:20px 24px;color:#ffffff;font-size:20px;font-weight:800'>"
            f"&#129656; {escape(title)}</div>"
            f"<div style='padding:20px 24px'><table style='border-collapse:collapse;width:100%'>{items}</table>"
            f"{btn}<p style='color:#6b7280;font-size:13px;margin-top:20px'>{escape(footer or 'Thank you for being a donor.')}</p>"
            f"</div></div></div>")


def alert_donors(donors_df, req, request_id=None):
    """Email each donor a personal Accept/Decline link. Returns (sent_count, error_list)."""
    sent, errors = 0, []
    tag = f" [REQ-{request_id}]" if request_id is not None else ""
    urgency = _get(req, "urgency", "")
    units = int(_get(req, "units", 1) or 1)
    subject = f"URGENT: {req['blood_group']} blood needed{tag}" if urgency == "Critical" \
        else f"{req['blood_group']} blood needed{tag}"
    for _, d in donors_df.iterrows():
        token = secrets.token_urlsafe(8)
        link = f"{app_url()}/?r={request_id}&d={int(d['id'])}&t={token}"
        dist = _dist_text(d)
        details = (f"Patient: {req['patient']}\n"
                   f"Hospital: {req['hospital']}, {str(req['city']).title()}{dist}\n"
                   f"Units needed: {units}\nUrgency: {urgency}\nContact: {req['contact']}")
        body = (f"Hi {d['name']},\n\n{req['blood_group']} blood is needed.\n\n{details}\n\n"
                f"Can you donate? Tap this link and press Yes or No:\n{link}\n\n"
                f"(Or simply reply to this email with YES or NO.)\n\nThank you!")
        rows = [("Blood group", req["blood_group"]), ("Patient", req["patient"]),
                ("Hospital", f"{req['hospital']}, {str(req['city']).title()}{dist}"),
                ("Units", units), ("Urgency", urgency), ("Contact", req["contact"])]
        html = _layout(f"{req['blood_group']} blood needed", URGENCY_COLOR.get(urgency, "#C62828"), rows,
                       ("Respond: Yes / No", link), f"Hi {d['name']}, can you help? It takes one tap.")
        try:
            send_email(d["email"], subject, body, html)
            sent += 1
            if request_id is not None:
                db.log_notified(int(request_id), int(d["id"]), token)
        except Exception as e:
            errors.append(f"Mail failed for {d['email']}: {e}")
    if sent and request_id is not None:
        db.log_activity("email", f"{sent} donor(s) emailed for request #{request_id}")
    return sent, errors


def alert_blood_banks(banks_df, req):
    sent, errors = 0, []
    for _, b in banks_df.iterrows():
        body = (f"Hello {b['name']},\n\nWe need {req['blood_group']} blood urgently "
                f"({int(_get(req, 'units', 1) or 1)} unit(s)).\n"
                f"Hospital: {req['hospital']}, {str(req['city']).title()}{_dist_text(b)}\n"
                f"Contact: {req['contact']}\nPlease reply if you have stock.")
        try:
            send_email(b["email"], f"Need {req['blood_group']} blood", body)
            sent += 1
        except Exception as e:
            errors.append(f"Mail failed for {b['email']}: {e}")
    return sent, errors


def _request_block(req):
    return (f"- Patient: {req['patient']}\n- Hospital: {req['hospital']}\n"
            f"- City: {str(req['city']).title()}\n- Units needed: {_get(req, 'units', 1)}\n"
            f"- Urgency: {req['urgency']}\n- Contact number: {req['contact']}")


def _request_rows(req):
    return [("Patient", req["patient"]), ("Hospital", req["hospital"]), ("City", str(req["city"]).title()),
            ("Urgency", req["urgency"]), ("Contact", req["contact"])]


def send_thank_you(request_id, donor):
    """Sent once when a donor says YES. Returns an error string or None."""
    if db.is_ack_sent(request_id, int(donor["id"])):
        return None
    req = db.get_request(request_id)
    if not req:
        return None
    body = (f"Dear {donor['name']},\n\nThank you for agreeing to donate blood!\n\n"
            f"{_request_block(req)}\n\n"
            f"Please contact the person above as soon as possible. "
            f"You will get another email once the coordinator confirms you.\n\n"
            f"With gratitude,\nBlood Donor Matcher")
    html = _layout("Thank you for saying YES", "#2E7D32", _request_rows(req),
                   footer="Please call the contact number above. You will get another email once confirmed.")
    try:
        send_email(donor["email"], f"Thank you for accepting to donate blood [REQ-{request_id}]", body, html)
        db.set_ack_sent(request_id, int(donor["id"]), 1)
        return None
    except Exception as e:
        return f"Could not send thank-you email to {donor['email']}: {e}"


def send_confirmation(request_id, donor_id, fulfilled=True):
    """Email the donor the coordinator confirmed. If the request is now fully covered, other donors who
    said YES (and are not confirmed) get a 'no longer needed' email."""
    errors = []
    req = db.get_request(request_id)
    if not req:
        return errors
    donors = db.notified_donors(request_id)
    for _, d in donors.iterrows():
        if d["response"] != "Accepted":
            continue
        html = None
        if int(d["id"]) == int(donor_id):
            subject = f"CONFIRMED: please go to {req['hospital']}"
            body = (f"Dear {d['name']},\n\nYou are confirmed as the donor for this request.\n\n"
                    f"{_request_block(req)}\n\nPlease reach the hospital as soon as you can. Thank you for saving a life!\n\n"
                    f"Blood Donor Matcher")
            html = _layout("You are confirmed", "#2E7D32", _request_rows(req),
                           footer="Please reach the hospital as soon as you can. Thank you for saving a life!")
        elif fulfilled and not d["confirmed"]:
            subject = "Blood request fulfilled - thank you"
            body = (f"Dear {d['name']},\n\nThank you for offering to donate. Enough donors have been confirmed "
                    f"for this request, so you are no longer needed this time. We may contact you again in future.\n\n"
                    f"Blood Donor Matcher")
        else:
            continue
        try:
            send_email(d["email"], subject, body, html)
        except Exception as e:
            errors.append(f"Could not email {d['email']}: {e}")
    return errors


def send_cancellation(request_id):
    """Tell donors who said YES that the request was cancelled."""
    errors = []
    req = db.get_request(request_id)
    if not req:
        return errors
    for _, d in db.accepted_donors(request_id).iterrows():
        body = (f"Dear {d['name']},\n\nThe blood request for {req['patient']} at {req['hospital']} has been "
                f"cancelled, so you do not need to go. Thank you so much for being ready to help.\n\n"
                f"Blood Donor Matcher")
        try:
            send_email(d["email"], f"Request cancelled [REQ-{request_id}]", body)
        except Exception as e:
            errors.append(f"Could not email {d['email']}: {e}")
    return errors
