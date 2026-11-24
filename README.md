
 🩸 Blood Donor Matcher

An emergency blood-donor coordination app. When a patient needs blood, it finds the nearest compatible donors,
emails them a one-tap **Yes / No** link, and helps the coordinator confirm donors until every unit is covered.

Built with **Streamlit + SQLite + Gmail (SMTP/IMAP) + Docker**.

> ⚠️ **Not medical advice.** The compatibility checker and "Am I ready to donate?" self-check are informational only.
> Donor eligibility must always be decided by a doctor or licensed blood bank.

---

## Features
<img width="1767" height="970" alt="Screenshot 2026-11-24 181518" src="https://github.com/user-attachments/assets/ca151f47-4ee9-4e56-9b65-f7ba6c92d3f4" />
**Requests**
- Preview matched donors (match score, untick anyone) before sending alerts
- Multiple **units needed**; request stays *Partial* until enough donors are confirmed
- Adjustable search radius (10-100 km), urgency levels with SLA timers (Critical 1 h, 24 h, Planned 72 h)
- Cancel with a reason (donors who said yes are notified automatically)
- No donor found? Save as *Pending*: nearby blood banks are emailed, and new matching donors are alerted when they register

**Matching**
- Same blood group first, then compatible groups, nearest first
- **Response forecast + Smart pick**: estimated chance each donor says yes, and auto-selection of the fewest donors for ~90% confidence
- 90-day donation break respected; donors can be paused without deleting

**Donors**
- Registration with consent checkbox, 10-digit phone validation
- Bulk **CSV import** with row-by-row validation report
- One-click Call and WhatsApp links
- Hero levels (Newcomer → Lifesaver), public Hall of Fame (shortened names), printable certificates

**Coordinator tools**
- Copilot to-do list, live radar map, blood-bag inventory, analytics (supply vs demand, funnel, reply times)
- Reply checking from Gmail (donors can also just click the link in the email)
- Database backup and CSV export, activity log
- Optional **coordinator PIN**

## Screenshots
Add your own screenshots here (use **fake data only**), e.g. `docs/dashboard.png`.

## Quick start

### 1. Configure
```bash
cp .env.example .env        # Windows: copy .env.example .env
```
Edit `.env`:

| Variable | Required | Meaning |
|---|---|---|
| `EMAIL` | yes | Gmail address used to send and read emails |
| `APP_PASSWORD` | yes | 16-letter Gmail **App Password** (Google Account → Security → 2-Step Verification → App passwords) |
| `APP_URL` | no | Public address put in donor emails. Set it if donors open the link on another device |
| `ADMIN_PIN` | no, **strongly recommended when public** | Locks the coordinator tabs. If empty, everything is open |
| `COUNTRY_CODE` | no | Used for call / WhatsApp links (default `91`) |

### 2a. Run with Docker
```bash
docker compose up --build
```
Open http://localhost:8501. Data is stored in `./data` and survives restarts.

### 2b. Run without Docker
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

### 3. (Optional) Try it with fake demo data
```bash
python seed_demo.py
```
Adds 6 fake donors using `example.com` emails, so no real email is ever sent.

### Email not working?
```bash
python mail_check.py
```
Tests DNS, the SMTP ports, and your Gmail login, and tells you what is wrong.

## How it works
1. **Register** donors, or bulk-import a CSV.
2. **Request Blood**: review the matches, then send alerts.
3. **Donors answer** via the email link (instant), or reply YES / NO and press **Check Gmail replies**.
4. **Dashboard → Donors waiting for your confirmation → Confirm donor.** When all units are covered the request becomes *Fulfilled*,
   the donor gets a confirmation email, and other donors who said yes are told they are no longer needed.

## Project structure
| File | Purpose |
|---|---|
| `app.py` | Streamlit pages and flow |
| `ui.py` | Styling, cards, charts, components |
| `db.py` | SQLite access and automatic migrations |
| `matcher.py` | Blood compatibility, ranking, response forecast |
| `mailer.py` | Sends alert / confirmation / cancellation emails |
| `replies.py` | Reads YES/NO replies from Gmail via IMAP |
| `insights.py` | Analytics and public Hall of Fame |
| `cities.py` | Town → latitude/longitude table. **Add your own towns here** |
| `mail_check.py` | Email troubleshooting script |
| `seed_demo.py` | Fake demo data |
| `tests/` | Unit tests and offline UI smoke test |

## Tests
```bash
python -m unittest discover -s tests -v    # logic
python tests/smoke_ui.py                   # offline UI smoke test
```

## Customising for your region
The town list in `cities.py` currently covers Karnataka, India. Add towns as `"Name": (latitude, longitude)`.
Set `COUNTRY_CODE` in `.env` for your country's phone prefix. Phone validation expects 10-digit numbers.

## Security and privacy
- **Never commit `.env` or anything in `data/`.** The database contains donors' names, emails and phone numbers.
  `.gitignore` already excludes them. Run `git status` before every push.
- If an app password was ever shared or committed, delete it in your Google account and create a new one.
- Set `ADMIN_PIN` for any deployment others can reach, and serve the app over **HTTPS** (response links carry a private token).
- Handle real donor data according to your local privacy law (consent is collected at registration).
- Use a dedicated Gmail account for the app, not your personal one.

## Limitations
- Gmail daily sending limits apply; this is built for small communities and coordinators, not mass messaging.
- SQLite is single-file storage, ideal for one instance, not for multiple servers.
- Distances are straight-line between town centres, not road distance.

## License
MIT, see [LICENSE](LICENSE). Replace `SUJAN NAIK` in the license before publishing.
