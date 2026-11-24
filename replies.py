# Reads donor replies (YES / NO) from Gmail over IMAP. Optional: donors can also use the link in the email.
import os, re, imaplib, email, email.utils
from datetime import date, timedelta
from email.header import decode_header
from dotenv import load_dotenv
import db, mailer

load_dotenv()

ACCEPT = {"yes", "yeah", "yep", "yup", "ya", "ok", "okay", "sure", "haan", "accept", "accepted", "confirmed"}
DECLINE = {"no", "nope", "sorry", "cannot", "not", "illa", "decline", "declined"}


def decode_mime_words(value):
    if not value:
        return ""
    out = []
    for part, enc in decode_header(value):
        out.append(part.decode(enc or "utf-8", errors="replace") if isinstance(part, bytes) else str(part))
    return "".join(out)


def _decode_part(part):
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")


def get_email_body(msg):
    """Plain-text body (falls back to HTML with tags removed)."""
    if msg.is_multipart():
        text = html = None
        for part in msg.walk():
            if "attachment" in str(part.get("Content-Disposition", "")):
                continue
            ctype = part.get_content_type()
            if ctype == "text/plain" and text is None:
                text = part
            elif ctype == "text/html" and html is None:
                html = part
        if text is not None:
            return _decode_part(text)
        if html is not None:
            return re.sub(r"<[^>]+>", " ", _decode_part(html))
        return ""
    body = _decode_part(msg)
    return re.sub(r"<[^>]+>", " ", body) if msg.get_content_type() == "text/html" else body


def strip_quoted_text(body):
    """Keep only what the donor typed, not the quoted original email."""
    keep = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith(">") or re.match(r"^On\s+.*wrote\s*:?", s, re.I) or s.lower().startswith("from:") \
                or re.match(r"^-+\s*original message", s, re.I):
            break
        keep.append(line)
    return "\n".join(keep).strip()


def classify_reply(text):
    """Returns 'Accepted', 'Declined' or 'Needs review' from the first two lines of the reply."""
    lines = [l.strip().lower() for l in text.splitlines() if l.strip()][:2]
    if not lines:
        return "Needs review"
    t = " ".join(lines).replace("\u2019", "'")
    t = re.sub(r"\b(can't|cant|can not)\b", "cannot", t)
    if t.startswith("no problem") or t.startswith("no issue"):
        return "Accepted"
    tokens = re.findall(r"[a-z0-9']+", t)
    yes = any(w in ACCEPT for w in tokens) or re.search(r"\bi can\b", t) is not None
    no = any(w in DECLINE for w in tokens)
    if yes and not no:
        return "Accepted"
    if no and not yes:
        return "Declined"
    return "Needs review"


def check_replies(days=14):
    """Read recent '[REQ-n]' replies from Gmail. Returns a summary dict (with 'error' if something failed)."""
    summary = {"checked": 0, "accepted": 0, "declined": 0, "review": 0, "error": None}
    user, pw = os.getenv("EMAIL"), os.getenv("APP_PASSWORD")
    if not user or not pw:
        summary["error"] = "EMAIL or APP_PASSWORD is missing in .env"
        return summary
    imap = None
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        imap.login(user, pw)
        imap.select("INBOX")
        since = (date.today() - timedelta(days=days)).strftime("%d-%b-%Y")
        status, data = imap.search(None, "SINCE", since, "SUBJECT", "[REQ-")
        if status != "OK" or not data or not data[0]:
            return summary
        for mid in data[0].split():
            res, msg_data = imap.fetch(mid, "(BODY.PEEK[])")   # PEEK: does not mark the mail as read
            if res != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subject = decode_mime_words(msg.get("Subject", ""))
            # only real replies ("Re: ...") - our own outgoing emails are skipped
            if not re.match(r"^\s*(re|aw|sv)\s*:", subject, re.I):
                continue
            m = re.search(r"\[REQ-(\d+)\]", subject, re.I)
            message_id = (msg.get("Message-ID") or "").strip()
            if not m or not message_id or db.mail_processed(message_id):
                continue
            request_id = int(m.group(1))
            _, sender = email.utils.parseaddr(msg.get("From", ""))
            donor = db.get_notified_by_email(request_id, sender)
            if not donor:
                db.mark_mail(message_id)
                continue
            text = strip_quoted_text(get_email_body(msg))
            result = classify_reply(text)
            saved = db.set_reply(request_id, donor["id"], result, text[:300])
            db.mark_mail(message_id)
            if not saved:        # request already fulfilled
                continue
            summary["checked"] += 1
            if result == "Accepted":
                summary["accepted"] += 1
                err = mailer.send_thank_you(request_id, donor)
                if err:
                    summary["error"] = err
            elif result == "Declined":
                summary["declined"] += 1
            else:
                summary["review"] += 1
    except Exception as e:
        summary["error"] = str(e)
    finally:
        if imap:
            try:
                imap.logout()
            except Exception:
                pass
    return summary
