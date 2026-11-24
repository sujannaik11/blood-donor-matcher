"""Finds out why emails fail. Run from the project folder:  python mail_check.py
(In Docker:  docker compose run --rm app python mail_check.py)"""
import os, socket, smtplib
from dotenv import load_dotenv

load_dotenv()
user = (os.getenv("EMAIL") or "").strip().strip("\"'")
pw = (os.getenv("APP_PASSWORD") or "").replace(" ", "").strip().strip("\"'")
print(f"EMAIL: {user or 'MISSING'}")
print(f"APP_PASSWORD: {len(pw)} characters {'(OK, 16 expected)' if len(pw) == 16 else '(WRONG: an app password has exactly 16 letters)'}")

try:
    print("DNS smtp.gmail.com ->", socket.gethostbyname("smtp.gmail.com"))
except OSError as e:
    print("DNS FAILED:", e, "\n=> No internet or DNS inside this environment.")
    raise SystemExit(1)

for port, ssl in ((465, True), (587, False)):
    try:
        s = smtplib.SMTP_SSL("smtp.gmail.com", port, timeout=15) if ssl else smtplib.SMTP("smtp.gmail.com", port, timeout=15)
        if not ssl:
            s.starttls()
        print(f"port {port}: connected")
        try:
            s.login(user, pw)
            print(f"port {port}: LOGIN OK  <- emails will work")
        except smtplib.SMTPAuthenticationError as e:
            print(f"port {port}: connected but Gmail REJECTED the login ->", e.smtp_code, "\n=> Make a new app password for this exact Gmail account.")
        s.quit()
    except (smtplib.SMTPException, OSError) as e:
        print(f"port {port}: FAILED ->", type(e).__name__, e)
print("\nIf both ports FAILED: your network/VPN/firewall/antivirus blocks email. Try a phone hotspot.")
