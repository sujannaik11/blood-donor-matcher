import os, re, hmac
from html import escape as _esc
from urllib.parse import quote
from datetime import datetime, date
import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import db, matcher, mailer, cities, replies, ui, insights

load_dotenv()
st.set_page_config(page_title="Blood Donor Matcher · Every drop counts", page_icon="🩸", layout="wide",
                   initial_sidebar_state="expanded")
db.init()

GROUPS = list(matcher.COMPAT.keys())
URGENCIES = ["Critical", "Within 24 hours", "Planned"]
URGENCY_ICON = {"Critical": "🔴", "Within 24 hours": "🟠", "Planned": "🟢"}
URGENCY_PILL = {"Critical": "red", "Within 24 hours": "orange", "Planned": "green"}
URGENCY_RANK = {"Critical": 0, "Within 24 hours": 1, "Planned": 2}
ADMIN_PIN = os.getenv("ADMIN_PIN", "").strip()          # optional: protects the coordinator tabs
CANCEL_REASONS = ["Patient recovered / no longer needed", "Arranged elsewhere", "Duplicate request", "Other"]


# ---------- small helpers ----------
def valid_email(e):
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e.strip()) is not None


def valid_phone(p):
    return re.fullmatch(r"\d{10}", p.strip()) is not None


def flash(kind, msg, key="flash"):
    """Show a message after st.rerun() (normal messages vanish on rerun)."""
    st.session_state.setdefault(key, []).append((kind, msg))


def show_flash(key="flash"):
    for kind, msg in st.session_state.pop(key, []):
        getattr(st, kind)(msg)


def show_errors(errors):
    for e in errors:
        st.error(e)


def urgency_pill(u):
    return ui.pill(f"{URGENCY_ICON.get(u, '')} {u}", URGENCY_PILL.get(u, "gray"))


def is_admin():
    return (not ADMIN_PIN) or st.session_state.get("admin", False)


def wide_editor(df, **kw):
    """data_editor that fills the page width on every Streamlit version."""
    try:
        return st.data_editor(df, width="stretch", **kw)
    except Exception:
        return st.data_editor(df, use_container_width=True, **kw)


def show_chart(chart):
    """Altair chart that fills the width on every Streamlit version."""
    try:
        st.altair_chart(chart, width="stretch")
    except Exception:
        st.altair_chart(chart, use_container_width=True)


# =====================================================================
# DONOR RESPONSE PAGE  (opened from the link inside the email)
# =====================================================================
def donor_page(rid, did, token):
    ui.hero("Someone needs your help", "It takes one tap to answer. Your reply is shared only with the coordinator.",
            chips=["⚡ One tap", "🔒 Private link", "❤️ Up to 3 lives per donation"], eyebrow="Blood donation request")
    info = db.get_notified_by_token(rid, did, token)
    req = db.get_request(rid)
    if not info or not req:
        st.error("This link is not valid. Please use the link from your email.")
        return

    st.subheader(f"Hello {info['name']} 👋")
    ui.request_card(req, urgency_pill(req["urgency"]))

    if req["status"] == "Cancelled":
        st.info("This request was cancelled, so you do not need to go. Thank you for being ready to help! ❤️")
        return
    if req["status"] == "Fulfilled":
        st.info("This request has already been fulfilled. Thank you so much for being ready to help! ❤️")
        return

    current = info["response"]
    if current == "Accepted":
        st.success("✅ You said YES. Thank you! Please contact the number above. The coordinator will confirm you shortly.")
    elif current == "Declined":
        st.info("You said NO. Thank you for letting us know. You can still change your answer below.")
    else:
        st.write("**Can you donate?**")

    c1, c2, _ = st.columns([1, 1, 2])
    if c1.button("✅ Yes, I can donate", type="primary", key="yes"):
        if db.set_reply(rid, did, "Accepted", "Accepted using the email link"):
            err = mailer.send_thank_you(rid, {"id": did, "name": info["name"], "email": info["email"]})
            if err:
                flash("warning", err)
        st.rerun()
    if c2.button("❌ No, I cannot", key="no"):
        db.set_reply(rid, did, "Declined", "Declined using the email link")
        st.rerun()
    show_flash()

    ui.glass("Before you donate: quick checklist",
             "<p>✔ You feel healthy today and have eaten a meal</p><p>✔ You are 18–65 years old and weigh at least 45 kg</p>"
             "<p>✔ You have not donated in the last 90 days</p><p>✔ Carry a photo ID and drink plenty of water</p>", "📝")


params = st.query_params
if all(k in params for k in ("r", "d", "t")):
    ui.inject_css(False)
    ui.hide_sidebar()
    try:
        donor_page(int(params["r"]), int(params["d"]), params["t"])
    except ValueError:
        st.error("This link is not valid.")
    st.stop()


# =====================================================================
# THEME + SIDEBAR (top)
# =====================================================================
st.session_state.setdefault("dark_mode", st.query_params.get("theme") == "dark")


def _save_theme():
    if st.session_state["dark_mode"]:
        st.query_params["theme"] = "dark"
    elif "theme" in st.query_params:
        del st.query_params["theme"]


with st.sidebar:
    ui.brand()
    st.toggle("🌙 Dark mode", key="dark_mode", on_change=_save_theme)
    if ADMIN_PIN:
        if st.session_state.get("admin"):
            st.success("🔓 Coordinator mode")
            if st.button("Lock", key="lock_btn"):
                st.session_state["admin"] = False
                st.rerun()
        else:
            with st.form("pin_form", clear_on_submit=True):
                pin = st.text_input("Coordinator PIN", type="password")
                if st.form_submit_button("🔐 Unlock"):
                    if hmac.compare_digest(pin.encode(), ADMIN_PIN.encode()):
                        st.session_state["admin"] = True
                        st.rerun()
                    else:
                        st.error("Wrong PIN")
ui.inject_css(st.session_state["dark_mode"])


# =====================================================================
# TAB: REGISTER
# =====================================================================
def register_form():
    with st.form("donor"):
        a1, a2 = st.columns(2)
        name = a1.text_input("Name")
        email = a2.text_input("Email")
        b1, b2 = st.columns(2)
        phone = b1.text_input("Phone (10 digits)")
        bg = b2.selectbox("Blood group", GROUPS)
        c1_, c2_ = st.columns(2)
        city = c1_.selectbox("City", cities.TOWNS)
        area = c2_.text_input("Area")
        d1_, d2_ = st.columns(2)
        never = d1_.checkbox("Never donated before", value=True)
        last = d2_.date_input("Last donation date", max_value=date.today())
        consent = st.checkbox("I agree to be contacted by email when someone nearby needs my blood group.", value=False)
        ok = st.form_submit_button("❤️ Register", type="primary")
    if not ok:
        return
    if not (name.strip() and email.strip() and city):
        st.error("Name, email and city are required.")
    elif not valid_email(email):
        st.error("Enter a valid email like name@gmail.com")
    elif not valid_phone(phone):
        st.error("Phone number must be exactly 10 digits.")
    elif db.email_exists(email):
        st.error("This email is already registered as a donor.")
    elif not consent:
        st.error("Please tick the consent box so we can contact you.")
    else:
        last_str = None if never else str(last)
        did = db.add_donor(name, email, phone, bg, city, area, last_str)
        st.success("✅ Registered. Thank you for being a donor! ❤️")
        st.balloons()
        ui.glass(f"Welcome, {name.strip().split()[0].title()}!",
                 f"<p>Your group {ui.bg_badge(bg)} can give to: " + " ".join(ui.bg_badge(x) for x in matcher.can_donate_to(bg)) +
                 f"</p><p>Your hero level: {ui.tier_pill('Newcomer')}. Every confirmed donation moves you up.</p>", "🎉")
        if last_str and not matcher.is_eligible(last_str):
            st.info(f"You can donate again from {matcher.next_eligible_date(last_str):%d %b %Y} (90-day rule).")

        # waiting requests: email this new donor if a pending request fits (compatible, in range, eligible)
        if matcher.is_eligible(last_str):
            reqs = db.table("requests")
            waiting = reqs[reqs.status.isin(["Pending", "Partial"])] if not reqs.empty else pd.DataFrame()
            for _, r in waiting.iterrows():
                dist = matcher.haversine(city, r["city"])
                radius = int(r["radius"]) if pd.notna(r["radius"]) else matcher.MAX_RADIUS_KM
                if bg in matcher.COMPAT.get(r["blood_group"], []) and dist is not None and dist <= radius:
                    new = pd.DataFrame([{"id": did, "name": name.strip(), "email": email.strip(),
                                         "distance_km": round(dist, 1)}])
                    sent, errors = mailer.alert_donors(new, r, request_id=int(r["id"]))
                    show_errors(errors)
                    if sent:
                        if r["status"] == "Pending":
                            db.set_status(int(r["id"]), "Notified")
                        st.info(f"A waiting request for {r['blood_group']} matched you. Email sent.")


TEMPLATE_CSV = ("name,email,phone,blood_group,city,area,last_donation\n"
                "Asha Rao,asha@example.com,9876543210,O+,Mangaluru,Kadri,2025-01-15\n"
                "Ravi Kumar,ravi@example.com,9123456780,A-,Udupi,,\n")


def bulk_import():
    st.caption("Add many donors at once. Required columns: name, email, phone, blood_group, city. "
               "Optional: area, last_donation (YYYY-MM-DD).")
    st.download_button("⬇️ Download CSV template", TEMPLATE_CSV, "donor_template.csv", "text/csv")
    up = st.file_uploader("Upload your CSV", type=["csv"], key="bulk_csv")
    if not up:
        return
    try:
        raw = pd.read_csv(up, dtype=str).fillna("")
    except Exception as e:
        st.error(f"Could not read the file: {e}")
        return
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    missing = [c for c in ("name", "email", "phone", "blood_group", "city") if c not in raw.columns]
    if missing:
        st.error("Missing column(s): " + ", ".join(missing))
        return

    town_map = {t.lower(): t for t in cities.TOWNS}
    good, problems, seen = [], [], set()
    for i, row in raw.iterrows():
        get = lambda k: str(row[k]).strip() if k in raw.columns else ""
        name, email = get("name"), get("email")
        phone = re.sub(r"\D", "", get("phone"))[-10:]
        bg, city, last = get("blood_group").upper(), town_map.get(get("city").lower()), get("last_donation")
        errs = []
        if not name:
            errs.append("name missing")
        if not valid_email(email):
            errs.append("bad email")
        elif email.lower() in seen or db.email_exists(email):
            errs.append("email already registered")
        if not valid_phone(phone):
            errs.append("phone must be 10 digits")
        if bg not in GROUPS:
            errs.append("unknown blood group")
        if not city:
            errs.append("city not in town list")
        if last:
            try:
                datetime.strptime(last, "%Y-%m-%d")
            except ValueError:
                errs.append("last_donation must be YYYY-MM-DD")
        if errs:
            problems.append({"row": i + 2, "name": name, "problem": "; ".join(errs)})
        else:
            seen.add(email.lower())
            good.append((name, email, phone, bg, city, get("area"), last or None))

    k1, k2 = st.columns(2)
    k1.metric("Ready to import", len(good))
    k2.metric("Rows with problems", len(problems))
    if problems:
        ui.table(pd.DataFrame(problems))
    if good and st.button(f"📥 Import {len(good)} donor(s)", type="primary", key="bulk_go"):
        for g in good:
            db.add_donor(*g)
        flash("success", f"✅ Imported {len(good)} donor(s).", "flash_reg")
        st.rerun()


def register_side():
    ui.glass("Why it matters", "<p>🩸 One donation can help up to <b>3 patients</b>.</p><p>⏱️ It takes about <b>10 minutes</b> of your time.</p>"
             "<p>🔁 You can give again after <b>90 days</b>.</p><p>📍 We only alert you when someone <b>near you</b> needs your group.</p>", "💡")
    lv = "".join(f"<p>{ui.tier_pill(n)} &nbsp;{('from ' + str(m) + ' donation' + ('s' if m != 1 else '')) if m else 'on joining'}</p>"
                 for m, n, _i, _c in insights.TIERS)
    ui.glass("Earn your hero level", lv, "🏅")


def tab_register():
    show_flash("flash_reg")
    ui.section("Become a donor", "Takes a minute and can save a life.")
    form_col, side_col = st.columns([1.75, 1])
    with side_col:
        register_side()
    with form_col:
        if is_admin():
            single, bulk = st.tabs(["✍️ Single donor", "📥 Bulk import (CSV)"])
            with single:
                register_form()
            with bulk:
                bulk_import()
        else:
            register_form()


# =====================================================================
# TAB: REQUEST BLOOD  (search -> preview -> choose donors -> send)
# =====================================================================
def banks_near(city, radius):
    banks = db.table("blood_banks")
    if banks.empty:
        return banks
    banks["distance_km"] = banks["city"].apply(lambda c: matcher.haversine(c, city))
    banks = banks[banks["distance_km"].notna() & (banks["distance_km"] <= radius)].copy()
    banks["distance_km"] = banks["distance_km"].round(1)
    return banks.sort_values("distance_km")


def render_preview(pv):
    req, donors, stage = pv["req"], pv["donors"], pv["stage"]
    ui.request_card({**req, "units": req["units"]}, urgency_pill(req["urgency"]))

    if donors is None or donors.empty:
        st.warning(f"No eligible donor found within {req['radius']} km. You can save the request as Pending: "
                   "matching donors who register later are emailed automatically, and nearby blood banks are alerted now.")
        banks = banks_near(req["city"], req["radius"])
        if not banks.empty:
            st.caption("Blood banks in range that will be emailed:")
            ui.table(banks[["name", "city", "phone", "distance_km"]])
        c1, c2, _ = st.columns([2, 1, 2])
        if c1.button("💾 Save as Pending & alert blood banks", type="primary", key="pv_save_pending"):
            rid = db.add_request(req["patient"], req["blood_group"], req["hospital"], req["city"], req["area"],
                                 "", req["urgency"], req["contact"], "Pending", req["units"], req["radius"])
            if not banks.empty:
                n, errors = mailer.alert_blood_banks(banks, req)
                for e in errors:
                    flash("error", e, "flash_req")
                flash("info", f"Emailed {n} blood bank(s).", "flash_req")
            flash("warning", f"Request #{rid} saved as Pending. Also check e-Raktkosh (eraktkosh.in) for blood banks.", "flash_req")
            st.session_state.pop("preview", None)
            st.rerun()
        if c2.button("Discard", key="pv_discard_empty"):
            st.session_state.pop("preview", None)
            st.rerun()
        return

    exact_n = int((donors["match"] == "Exact").sum())
    st.success(f"Found **{len(donors)} donor(s)** ({stage}). {exact_n} with the exact group. "
               "Untick anyone you do not want to email.")
    auto_ids, auto_conf = insights.smart_pick(donors, req["units"])
    mode = st.radio("Who should we alert?", [f"✨ Smart pick: {len(auto_ids)} donor(s), about {round(100 * auto_conf)}% sure to cover {req['units']} unit(s)",
                                             f"📢 Everyone matched ({len(donors)})"], key=f"pv_mode_{pv['nonce']}", horizontal=True)
    smart = str(mode).startswith("✨")
    ed = donors[["id", "name", "blood_group", "match", "city", "area", "distance_km", "score"]].copy()
    ed["yes_pct"] = (donors["yes_chance"] * 100).round(0)
    ed["city"] = ed["city"].astype(str).str.title()
    ed["area"] = ed["area"].fillna("").astype(str).str.title()
    ed.insert(0, "Notify", ed["id"].isin(auto_ids) if smart else True)
    edited = wide_editor(
        ed, hide_index=True, key=f"pv_ed_{pv['nonce']}_{int(smart)}", disabled=[c for c in ed.columns if c != "Notify"],
        column_config={
            "id": None,
            "Notify": st.column_config.CheckboxColumn("Notify", default=True),
            "name": "Name", "blood_group": "Group", "match": "Match", "city": "City", "area": "Area",
            "distance_km": st.column_config.NumberColumn("Distance (km)", format="%.1f"),
            "score": st.column_config.ProgressColumn("Match score", min_value=0, max_value=100, format="%d"),
            "yes_pct": st.column_config.ProgressColumn("Likely to say yes", min_value=0, max_value=100, format="%d%%"),
        })
    sel_ids = edited.loc[edited["Notify"], "id"].astype(int).tolist()
    chosen = donors[donors["id"].isin(sel_ids)]
    probs = chosen["yes_chance"].tolist()
    conf = insights.prob_at_least(probs, req["units"]) if probs else 0.0
    ui.forecast_cards([(f"{round(100 * conf)}%", f"chance to cover {req['units']} unit(s)"),
                       (f"{sum(probs):.1f}", "donors expected to say yes"),
                       (len(sel_ids), "alerts that will be sent")])
    ui.meter(100 * conf, "Confidence the request gets covered")
    if conf < 0.8 and len(sel_ids) < len(donors):
        st.caption("Tip: confidence is low. Tick more donors, or widen the search radius.")
    with st.expander("🗺️ See the matched donors on the map", expanded=True):
        ui.radar(donors, pd.DataFrame([{"id": "new", "blood_group": req["blood_group"], "city": req["city"],
                                        "urgency": req["urgency"], "radius": req["radius"]}]),
                 halo_km=req["radius"], picks=sel_ids, dark=st.session_state.get("dark_mode", False), height=360)

    b1, b2, _ = st.columns([2, 1, 2])
    if b1.button(f"📨 Send alerts to {len(sel_ids)} donor(s)", type="primary", disabled=not sel_ids, key="pv_send"):
        rid = db.add_request(req["patient"], req["blood_group"], req["hospital"], req["city"], req["area"],
                             "", req["urgency"], req["contact"], "Pending", req["units"], req["radius"])
        sent, errors = mailer.alert_donors(donors[donors["id"].isin(sel_ids)], req, request_id=rid)
        for e in errors:
            flash("error", e, "flash_req")
        if sent:
            db.set_status(rid, "Notified")
        flash("success", f"✅ Request #{rid} saved. {sent} email(s) sent. Open the 📊 Dashboard to confirm a donor when they say yes.",
              "flash_req")
        st.session_state.pop("preview", None)
        st.rerun()
    if b2.button("Discard", key="pv_discard"):
        st.session_state.pop("preview", None)
        st.rerun()


def tab_request():
    show_flash("flash_req")
    ui.section("Request blood", "We find the best matching donors. You review the list, then we email them.")
    with st.form("req"):
        e1, e2 = st.columns(2)
        patient = e1.text_input("Patient name")
        rbg = e2.selectbox("Blood group needed", GROUPS)
        f1_, f2_ = st.columns(2)
        hospital = f1_.text_input("Hospital")
        contact = f2_.text_input("Contact number (10 digits)")
        g1_, g2_ = st.columns(2)
        rcity = g1_.selectbox("City", cities.TOWNS)
        rarea = g2_.text_input("Area")
        h1_, h2_, h3_ = st.columns(3)
        urgency = h1_.selectbox("Urgency", URGENCIES)
        units = h2_.number_input("Units needed", min_value=1, max_value=20, value=1, step=1)
        radius = h3_.slider("Search radius (km)", 10, 100, matcher.MAX_RADIUS_KM, step=5)
        go = st.form_submit_button("🔍 Find donors", type="primary")
    if go:
        if not (patient.strip() and hospital.strip() and rcity and contact.strip()):
            st.error("Please fill patient, hospital, city and contact.")
        elif not valid_phone(contact):
            st.error("Contact number must be exactly 10 digits.")
        else:
            stage, donors = matcher.find_donors(rbg, rcity, rarea, radius=int(radius))
            donors = insights.add_forecast(donors, insights.donor_profiles(db.table("donors"), db.donor_stats()),
                                           urgency, int(radius))
            st.session_state["pv_nonce"] = st.session_state.get("pv_nonce", 0) + 1
            st.session_state["preview"] = {
                "req": {"patient": patient.strip(), "blood_group": rbg, "hospital": hospital.strip(),
                        "city": rcity.strip().lower(), "area": rarea.strip().lower(), "urgency": urgency,
                        "contact": contact.strip(), "units": int(units), "radius": int(radius)},
                "stage": stage, "donors": donors, "nonce": st.session_state["pv_nonce"]}
    pv = st.session_state.get("preview")
    if pv:
        st.divider()
        render_preview(pv)


# =====================================================================
# TAB: DASHBOARD
# =====================================================================
def tab_dashboard():
    show_flash()
    donors_df, reqs_df = db.table("donors"), db.table("requests")
    stats, approvals = db.request_stats(), db.pending_approvals()

    open_stats = stats[stats.status.isin(db.OPEN_STATUSES)] if not stats.empty else pd.DataFrame()
    open_count = len(open_stats)
    fulfilled_count = int((reqs_df.status == "Fulfilled").sum()) if not reqs_df.empty else 0
    crit = int((open_stats.urgency == "Critical").sum()) if not open_stats.empty else 0
    emailed, accepted = (int(stats.emailed.sum()), int(stats.accepted.sum() + stats.confirmed.sum())) if not stats.empty else (0, 0)
    eligible_now = int(donors_df["last_donation"].apply(matcher.is_eligible).sum()) if not donors_df.empty else 0

    if crit:
        ui.alert_banner(f"{crit} critical request(s) open right now")
    ui.ticker([m for m in db.recent_activity(10)["message"].tolist()])
    ui.stat_cards([("Open requests", open_count, "#C62828", "🆘", f"{crit} critical" if crit else ""),
                   ("Waiting for you", len(approvals), "#EF6C00", "⏳", "donors said yes" if len(approvals) else ""),
                   ("Fulfilled", fulfilled_count, "#2E7D32", "✅", ""),
                   ("Total donors", len(donors_df), "#1A56B0", "🧑", f"{eligible_now} eligible today"),
                   ("Reply rate", f"{round(100 * accepted / emailed) if emailed else 0}%", "#6A1B9A", "📬", "said yes of emailed")])

    ui.section("🧭 Coordinator copilot", "Plain-language suggestions based on what is happening right now.")
    _tips = insights.copilot(stats, approvals, matcher.supply_demand(donors_df, stats), donors_df)
    ui.copilot_panel(_tips[:4])
    if len(_tips) > 4:
        with st.expander(f"Show {len(_tips) - 4} more suggestion(s)"):
            ui.copilot_panel(_tips[4:])
    c1, c2 = st.columns([1, 3])
    if c1.button("🔄 Check Gmail replies", key="gmail_check"):
        with st.spinner("Checking Gmail..."):
            res = replies.check_replies()
        st.session_state["last_check"] = datetime.now().strftime("%H:%M")
        if res["error"]:
            flash("error", f"Gmail check problem: {res['error']}")
        flash("info", f"{res['checked']} new repl{'y' if res['checked'] == 1 else 'ies'}: "
                      f"{res['accepted']} accepted, {res['declined']} declined, {res['review']} need review.")
        st.rerun()
    c2.caption(f"Last Gmail check: {st.session_state['last_check']}" if "last_check" in st.session_state
               else "Donors can answer with the link in the email (instant) or by replying YES / NO (click Check Gmail replies).")
    st.divider()

    # --- donors waiting for confirmation ---
    ui.section("✅ Donors waiting for your confirmation", "Confirm a donor to lock them in. A request closes when all units are covered.")
    if approvals.empty:
        ui.empty_state("🕊️", "Nobody is waiting", "When a donor says YES, they appear here.")
    else:
        approvals = approvals.assign(_r=approvals["urgency"].map(URGENCY_RANK)).sort_values(["_r", "request_id"])
        for _, a in approvals.iterrows():
            rid, did = int(a["request_id"]), int(a["donor_id"])
            have, units = db.confirmed_count(rid), int(a["units"])
            with st.container(border=True):
                col_info, col_act = st.columns([3, 1.4])
                with col_info:
                    st.markdown(f"**{_esc(str(a['donor_name']))}** {ui.bg_badge(a['donor_blood_group'])} &nbsp; "
                                f"**📞 {_esc(str(a['donor_phone']))}** "
                                + ui.contact_links(a["donor_phone"], f"Hello {a['donor_name']}, thank you for offering to donate "
                                                   f"{a['needed_group']} blood for {a['patient']} at {a['hospital']}. "
                                                   f"Contact: {a['contact']}"), unsafe_allow_html=True)
                    if pd.notna(a["reply_text"]) and a["reply_text"]:
                        st.write(f"💬 *\"{a['reply_text']}\"*")
                    st.markdown(f"Request #{rid}: {a['patient']} needs {ui.bg_badge(a['needed_group'])} • "
                                f"{a['hospital']}, {a['city'].title()} {urgency_pill(a['urgency'])} "
                                f"{ui.pill(f'{have}/{units} units confirmed', 'blue')}", unsafe_allow_html=True)
                with col_act:
                    if st.button("✅ Confirm donor", key=f"confirm_{rid}_{did}", type="primary"):
                        fulfilled = db.confirm_donor(rid, did)
                        errors = mailer.send_confirmation(rid, did, fulfilled)
                        flash("success", f"{a['donor_name']} confirmed. " +
                              (f"Request #{rid} is Fulfilled." if fulfilled else f"{have + 1} of {units} units covered for request #{rid}.")
                              + " The donor has been emailed.")
                        for e in errors:
                            flash("warning", e)
                        st.rerun()
                    if st.button("Not coming", key=f"notcoming_{rid}_{did}"):
                        db.set_reply(rid, did, "Declined", a["reply_text"] or "")
                        st.rerun()
    st.divider()

    # --- active requests ---
    ui.section("🩸 Active requests", "Most urgent first. Open one to see who was emailed and what they answered.")
    if open_stats.empty:
        ui.empty_state("🎉", "No active requests", "New requests appear here.")
    else:
        badge_map = {"Accepted": ("Accepted", "green"), "Declined": ("Declined", "red"), "Needs review": ("Needs review", "orange")}
        open_stats = open_stats.assign(_r=open_stats["urgency"].map(URGENCY_RANK)).sort_values(["_r", "id"], ascending=[True, False])
        for _, r in open_stats.iterrows():
            rid, units = int(r["id"]), int(r["units"])
            emailed_n, accepted_n, confirmed_n = int(r["emailed"]), int(r["accepted"]), int(r["confirmed"])
            title = (f"{URGENCY_ICON.get(r['urgency'], '')} #{rid} {r['patient']} · {r['blood_group']} · "
                     f"{r['city'].title()} · {r['status']} · {confirmed_n}/{units} units")
            with st.expander(title):
                cur = 1
                if emailed_n > 0:
                    cur = 2
                if accepted_n > 0 or confirmed_n > 0:
                    cur = 3
                ui.sla_ring(insights.sla(r["urgency"], r["created"]))
                ui.stepper(["Request", "Emailed", "Accepted", "Confirmed", "Fulfilled"], cur)
                radius_txt = f"{int(r['radius'])} km radius"
                units_txt = f"{units} unit(s)"
                st.markdown(f"{urgency_pill(r['urgency'])} {ui.pill(units_txt, 'blue')} "
                            f"{ui.pill(radius_txt, 'gray')} "
                            f"<span style='opacity:.7'>🏥 {r['hospital']} · created {ui.time_ago(r['created'])}</span>",
                            unsafe_allow_html=True)
                st.progress(min(1.0, confirmed_n / units) if units else 0.0,
                            text=f"{confirmed_n} of {units} unit(s) confirmed · {accepted_n} waiting · {emailed_n} emailed")
                notified_df = db.notified_donors(rid)
                if notified_df.empty:
                    st.caption("No donors emailed yet.")
                for _, d in notified_df.iterrows():
                    resp = d["response"] if pd.notna(d["response"]) else "No reply"
                    label, kind = ("Confirmed", "blue") if d["confirmed"] else badge_map.get(resp, ("No reply", "gray"))
                    said = f" — *\"{_esc(str(d['reply_text']))}\"*" if pd.notna(d["reply_text"]) and d["reply_text"] else ""
                    line = f"{ui.pill(label, kind)} **{_esc(str(d['name']))} • {_esc(str(d['phone']))}**{said}"
                    if resp == "Needs review":
                        ci, cy, cn = st.columns([3, 1, 1])
                        ci.markdown(line, unsafe_allow_html=True)
                        if cy.button("Yes", key=f"rev_yes_{rid}_{d['id']}"):
                            db.set_reply(rid, int(d["id"]), "Accepted", d["reply_text"] or "")
                            err = mailer.send_thank_you(rid, d)
                            if err:
                                flash("warning", err)
                            st.rerun()
                        if cn.button("No", key=f"rev_no_{rid}_{d['id']}"):
                            db.set_reply(rid, int(d["id"]), "Declined", d["reply_text"] or "")
                            st.rerun()
                    else:
                        st.markdown(line, unsafe_allow_html=True)

                st.write("")
                b1, b2, b3, b4 = st.columns(4)
                if b1.button("📢 Alert more donors", key=f"more_{rid}"):
                    req_row = db.get_request(rid)
                    already = set(int(x) for x in notified_df["id"].tolist()) if not notified_df.empty else set()
                    radius = int(req_row.get("radius") or matcher.MAX_RADIUS_KM)
                    stage, new_donors = matcher.find_donors(req_row["blood_group"], req_row["city"],
                                                            req_row.get("area", ""), radius=radius, exclude_ids=already)
                    if new_donors is None or new_donors.empty:
                        st.info(f"No additional donors found within {radius} km.")
                    else:
                        sent, errors = mailer.alert_donors(new_donors, req_row, request_id=rid)
                        for e in errors:
                            flash("error", e)
                        if sent and req_row["status"] == "Pending":
                            db.set_status(rid, "Notified")
                        flash("success", f"Emailed {sent} new donor(s) ({stage}).")
                        st.rerun()
                if b2.button("Mark fulfilled (blood bank helped)", key=f"bank_{rid}"):
                    db.set_status(rid, "Fulfilled")
                    st.rerun()
                with b4.popover("📣 Share message"):
                    msg = insights.broadcast_text(db.get_request(rid), mailer.app_url())
                    st.code(msg, language=None)
                    st.markdown(f"<a class='cl wa' target='_blank' rel='noopener' href='https://wa.me/?text={quote(msg)}'>💬 Open in WhatsApp</a>",
                                unsafe_allow_html=True)
                with b3.popover("🛑 Cancel request"):
                    reason = st.selectbox("Reason", CANCEL_REASONS, key=f"cr_{rid}")
                    sure = st.checkbox("Yes, cancel this request", key=f"cs_{rid}")
                    if st.button("Cancel request", key=f"cx_{rid}", disabled=not sure):
                        db.cancel_request(rid, reason)
                        errors = mailer.send_cancellation(rid)
                        flash("success", f"Request #{rid} cancelled. Donors who said yes were told.")
                        for e in errors:
                            flash("warning", e)
                        st.rerun()
    st.divider()

    with st.expander("🗺️ Live radar: donors and open requests"):
        ui.radar(donors_df, open_stats if not open_stats.empty else None, dark=st.session_state.get("dark_mode", False))
    st.divider()

    # --- history + export ---
    with st.expander("📁 All requests, history and export"):
        if stats.empty:
            st.caption("No requests yet.")
        else:
            y1, y2, y3 = st.columns(3)
            rg = y1.multiselect("Blood group", GROUPS, key="more_rg")
            rc = y2.multiselect("City", sorted(stats["city"].dropna().unique()), key="more_rc")
            rs = y3.multiselect("Status", ["Pending", "Notified", "Partial", "Fulfilled", "Cancelled"], key="more_rs")
            rview = stats.drop(columns=["radius"]).copy()
            if rg:
                rview = rview[rview["blood_group"].isin(rg)]
            if rc:
                rview = rview[rview["city"].isin(rc)]
            if rs:
                rview = rview[rview["status"].isin(rs)]
            ui.table(rview)
            st.download_button("⬇️ Download requests CSV", rview.to_csv(index=False).encode("utf-8"), "requests.csv", "text/csv")


# =====================================================================
# TAB: DONORS
# =====================================================================
def tab_donors():
    show_flash("flash_donors")
    ui.section("Donor directory", "Search, filter, fix mistakes, pause or remove a donor.")
    all_donors = db.table("donors")
    if all_donors.empty:
        ui.empty_state("🧑", "No donors yet", "Register one in the Register tab, or bulk-import a CSV.")
        return
    all_donors["eligibility"] = [matcher.eligibility_label(l, a) for l, a in zip(all_donors["last_donation"], all_donors["available"])]
    all_donors = insights.donor_profiles(all_donors, db.donor_stats())

    n_el = int((all_donors.eligibility == "Eligible").sum())
    n_pa = int((all_donors.eligibility == "Paused").sum())
    ui.stat_cards([("Donors", len(all_donors), "#1A56B0", "🧑"), ("Eligible today", n_el, "#2E7D32", "✅"),
                   ("On 90-day break", len(all_donors) - n_el - n_pa, "#EF6C00", "⏳"), ("Paused", n_pa, "#757575", "⏸️")])

    soon = insights.due_soon(all_donors, 14)
    if len(soon):
        with st.expander(f"📅 {len(soon)} donor(s) become eligible within 14 days. Send them a reminder."):
            ui.table(soon)
    x1, x2, x3, x4 = st.columns(4)
    search = x1.text_input("Search name, email or phone", key="dir_search")
    dg = x2.multiselect("Blood group", GROUPS, key="dir_bg")
    dc = x3.multiselect("City", sorted(all_donors["city"].dropna().unique()), key="dir_city")
    ds = x4.selectbox("Availability", ["All", "Eligible today", "On 90-day break", "Paused"], key="dir_stat")
    view = all_donors.copy()
    if search:
        q = search.strip().lower()
        view = view[view["name"].fillna("").str.lower().str.contains(q, regex=False)
                    | view["email"].fillna("").str.lower().str.contains(q, regex=False)
                    | view["phone"].fillna("").astype(str).str.contains(q, regex=False)]
    if dg:
        view = view[view["blood_group"].isin(dg)]
    if dc:
        view = view[view["city"].isin(dc)]
    if ds == "Eligible today":
        view = view[view["eligibility"] == "Eligible"]
    elif ds == "Paused":
        view = view[view["eligibility"] == "Paused"]
    elif ds == "On 90-day break":
        view = view[~view["eligibility"].isin(["Eligible", "Paused"])]
    st.caption(f"{len(view)} of {len(all_donors)} donors")
    cols = ["id", "name", "email", "phone", "blood_group", "city", "area", "last_donation", "eligibility", "tier", "reliability", "emailed", "donations"]
    ui.table(view[cols].rename(columns={"emailed": "times_emailed", "donations": "donations_confirmed"}))
    st.download_button("⬇️ Download donors CSV", view[cols].to_csv(index=False).encode("utf-8"), "donors.csv", "text/csv")

    st.divider()
    ui.section("✏️ Edit a donor")
    options = {f"#{int(r['id'])} · {r['name']} · {r['blood_group']} · {str(r['city']).title()}": int(r["id"])
               for _, r in all_donors.iterrows()}
    pick = st.selectbox("Choose a donor", list(options.keys()), key="edit_pick")
    did = options[pick]
    donor = db.get_donor(did)
    if not donor:
        return
    towns_lower = [t.lower() for t in cities.TOWNS]
    city_idx = towns_lower.index(str(donor["city"]).lower()) if str(donor["city"]).lower() in towns_lower else 0
    bg_idx = GROUPS.index(donor["blood_group"]) if donor["blood_group"] in GROUPS else 0
    try:
        last_val = datetime.strptime(donor["last_donation"], "%Y-%m-%d").date() if donor["last_donation"] else date.today()
    except ValueError:
        last_val = date.today()
    with st.form(f"edit_donor_{did}"):
        f1, f2 = st.columns(2)
        n_name = f1.text_input("Name", value=donor["name"] or "", key=f"e_name_{did}")
        n_email = f2.text_input("Email", value=donor["email"] or "", key=f"e_email_{did}")
        f3, f4 = st.columns(2)
        n_phone = f3.text_input("Phone (10 digits)", value=str(donor["phone"] or ""), key=f"e_phone_{did}")
        n_bg = f4.selectbox("Blood group", GROUPS, index=bg_idx, key=f"e_bg_{did}")
        f5, f6 = st.columns(2)
        n_city = f5.selectbox("City", cities.TOWNS, index=city_idx, key=f"e_city_{did}")
        n_area = f6.text_input("Area", value=donor["area"] or "", key=f"e_area_{did}")
        f7, f8 = st.columns(2)
        n_never = f7.checkbox("Never donated before", value=not donor["last_donation"], key=f"e_never_{did}")
        n_last = f8.date_input("Last donation date", value=last_val, key=f"e_last_{did}")
        n_avail = st.checkbox("Available for requests (untick to pause this donor)",
                              value=bool(donor.get("available", 1) if donor.get("available") is not None else 1),
                              key=f"e_avail_{did}")
        save = st.form_submit_button("💾 Save changes", type="primary")
    if save:
        if not (n_name.strip() and n_email.strip()):
            st.error("Name and email are required.")
        elif not valid_email(n_email):
            st.error("Enter a valid email like name@gmail.com")
        elif not valid_phone(n_phone):
            st.error("Phone number must be exactly 10 digits.")
        elif db.email_exists(n_email, exclude_id=did):
            st.error("Another donor already uses this email.")
        else:
            db.update_donor(did, n_name, n_email, n_phone, n_bg, n_city, n_area,
                            None if n_never else str(n_last), n_avail)
            flash("success", f"✅ Saved changes for {n_name.strip()}.", "flash_donors")
            st.rerun()

    with st.expander("🗑️ Delete this donor"):
        st.warning(f"This permanently removes {donor['name']} and their email history. This cannot be undone.")
        sure = st.checkbox("Yes, I want to delete this donor", key=f"del_sure_{did}")
        if st.button("Delete donor", key=f"del_{did}", disabled=not sure):
            db.delete_donor(did)
            st.session_state.pop("edit_pick", None)
            flash("success", f"🗑️ Deleted {donor['name']}.", "flash_donors")
            st.rerun()


# =====================================================================
# TAB: BLOOD BANKS
# =====================================================================
def tab_banks():
    show_flash("flash_banks")
    ui.section("Blood banks", "Banks in range are emailed when no donor is found.")
    with st.form("bank"):
        i1, i2 = st.columns(2)
        bn = i1.text_input("Blood bank name")
        bc = i2.selectbox("City", cities.TOWNS)
        j1, j2 = st.columns(2)
        be = j1.text_input("Email")
        bp = j2.text_input("Phone (10 digits)")
        add = st.form_submit_button("➕ Add blood bank", type="primary")
    if add:
        if not (bn.strip() and bc):
            st.error("Name and city are required.")
        elif not valid_email(be):
            st.error("Enter a valid email like bank@gmail.com")
        elif not valid_phone(bp):
            st.error("Phone number must be exactly 10 digits.")
        else:
            db.add_blood_bank(bn, bc, be, bp)
            flash("success", "✅ Blood bank added.", "flash_banks")
            st.rerun()
    banks = db.table("blood_banks")
    if banks.empty:
        ui.empty_state("🏥", "No blood banks yet", "Add one above. They are emailed when no donor can be found.")
        return
    ui.table(banks)
    with st.expander("✏️ Edit or delete a blood bank"):
        opts = {f"#{int(b['id'])} · {b['name']} · {str(b['city']).title()}": int(b["id"]) for _, b in banks.iterrows()}
        pk = st.selectbox("Choose a blood bank", list(opts.keys()), key="bank_pick")
        bid = opts[pk]
        row = banks[banks["id"] == bid].iloc[0]
        tl = [t.lower() for t in cities.TOWNS]
        with st.form(f"edit_bank_{bid}"):
            k1, k2 = st.columns(2)
            nn = k1.text_input("Name", value=str(row["name"]), key=f"bn_{bid}")
            nc = k2.selectbox("City", cities.TOWNS, index=tl.index(str(row["city"]).lower()) if str(row["city"]).lower() in tl else 0,
                              key=f"bc_{bid}")
            k3, k4 = st.columns(2)
            ne = k3.text_input("Email", value=str(row["email"]), key=f"be_{bid}")
            np_ = k4.text_input("Phone", value=str(row["phone"]), key=f"bp_{bid}")
            if st.form_submit_button("💾 Save", type="primary"):
                if not nn.strip() or not valid_email(ne) or not valid_phone(np_):
                    st.error("Check the name, email and 10-digit phone.")
                else:
                    db.update_blood_bank(bid, nn, nc, ne, np_)
                    flash("success", "✅ Blood bank updated.", "flash_banks")
                    st.rerun()
        sure = st.checkbox("Yes, delete this blood bank", key=f"bd_sure_{bid}")
        if st.button("Delete blood bank", key=f"bd_{bid}", disabled=not sure):
            db.delete_blood_bank(bid)
            st.session_state.pop("bank_pick", None)
            flash("success", "🗑️ Blood bank deleted.", "flash_banks")
            st.rerun()


# =====================================================================
# TAB: ANALYTICS
# =====================================================================
def _fmt_minutes(m):
    if m is None or pd.isna(m):
        return "—"
    return f"{m:.0f} min" if m < 90 else f"{m / 60:.1f} h"


def tab_analytics():
    dark = st.session_state["dark_mode"]
    donors_df, stats = db.table("donors"), db.request_stats()
    ui.section("Insights", "Where blood is needed, who can give it, and how fast people respond.")

    f = db.funnel()
    mins = db.response_minutes()
    total_req = len(stats)
    ful = int((stats.status == "Fulfilled").sum()) if total_req else 0
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Requests so far", total_req)
    m2.metric("Fulfilment rate", f"{round(100 * ful / total_req) if total_req else 0}%")
    m3.metric("Yes rate", f"{round(100 * f['Said yes'] / f['Emailed']) if f['Emailed'] else 0}%")
    m4.metric("Median reply time", _fmt_minutes(mins.median() if len(mins) else None))

    sd = matcher.supply_demand(donors_df, stats)
    short, low = sd[sd.supply == "Shortage"], sd[(sd.supply == "Low") & (sd.needed_units > 0)]
    if not short.empty:
        st.error("🚨 Shortage: not enough eligible donors for " + ", ".join(short.blood_group) +
                 ". Recruit donors of these groups or alert blood banks.")
    if not low.empty:
        st.warning("⚠️ Running low for " + ", ".join(low.blood_group) + ". Few donors compared to open demand.")
    ui.section("Supply vs demand", "Each bag shows how many eligible donors can give that group, against open demand.")
    ui.blood_bags(sd)
    with st.expander("See the numbers"):
        ui.table(sd)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Donors by blood group**")
        gdf = pd.DataFrame({"blood_group": GROUPS, "donors": [int((donors_df["blood_group"] == g).sum()) if not donors_df.empty else 0 for g in GROUPS]})
        ch = alt.Chart(gdf).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color=ui.RED).encode(
            x=alt.X("blood_group:N", sort=GROUPS, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("donors:Q", title=None), tooltip=["blood_group", "donors"])
        show_chart(ui.style_chart(ch, dark))
    with c2:
        st.markdown("**Requests by status**")
        if total_req:
            sdf = stats.groupby("status").size().reset_index(name="count")
            order = ["Pending", "Notified", "Partial", "Fulfilled", "Cancelled"]
            colors = [ui.ORANGE, ui.BLUE, "#5C9DFF", ui.GREEN, ui.GRAY]
            ch = alt.Chart(sdf).mark_arc(innerRadius=55).encode(
                theta="count:Q", color=alt.Color("status:N", scale=alt.Scale(domain=order, range=colors), title=None),
                tooltip=["status", "count"])
            show_chart(ui.style_chart(ch, dark))
        else:
            st.caption("No requests yet.")

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("**Requests over time**")
        if total_req:
            days = pd.to_datetime(stats["created"], errors="coerce").dt.normalize()
            daily = days.value_counts().sort_index().rename_axis("day").reset_index(name="requests")
            ch = alt.Chart(daily).mark_line(point=True, color=ui.RED, strokeWidth=3).encode(
                x=alt.X("day:T", title=None), y=alt.Y("requests:Q", title=None, axis=alt.Axis(tickMinStep=1)),
                tooltip=["day:T", "requests"])
            show_chart(ui.style_chart(ch, dark))
        else:
            st.caption("No requests yet.")
    with c4:
        st.markdown("**Response funnel**")
        fdf = pd.DataFrame({"stage": list(f.keys()), "count": list(f.values())})
        ch = alt.Chart(fdf).mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6, color=ui.RED).encode(
            y=alt.Y("stage:N", sort=list(f.keys()), title=None), x=alt.X("count:Q", title=None, axis=alt.Axis(tickMinStep=1)),
            tooltip=["stage", "count"])
        show_chart(ui.style_chart(ch, dark))

    ui.section("Where donors live", "Green donors can give today, orange are on their 90-day break.")
    ui.radar(donors_df, None, dark=dark)


# =====================================================================
# TAB: HALL OF FAME
# =====================================================================
def tab_fame():
    prof = insights.donor_profiles(db.table("donors"), db.donor_stats())
    ui.section("Hall of Fame", "The people who showed up. Names are shortened to protect privacy.")
    if prof is None or prof.empty or int(prof["donations"].sum()) == 0:
        ui.empty_state("🏆", "The podium is waiting", "Once a donor is confirmed on the Dashboard, they appear here.")
        return
    total, lives = int(prof["donations"].sum()), int(prof["lives"].sum())
    heroes = int((prof["donations"] > 0).sum())
    ui.stat_cards([("Donations", total, "#D7263D", "🩸"), ("Lives touched", lives, "#2E9E5B", "💚", "up to 3 per donation"),
                   ("Heroes", heroes, "#3B6FD4", "🦸"), ("Lifesavers", int((prof["donations"] >= 10).sum()), "#D4A017", "💎", "10+ donations")])
    top = prof[prof["donations"] > 0].sort_values(["donations", "reliability"], ascending=False).reset_index(drop=True)
    ui.podium([{"name": insights.public_name(r["name"]), "donations": r["donations"], "tier": r["tier"],
                "blood_group": r["blood_group"], "lives": r["lives"]} for _, r in top.head(3).iterrows()])
    for i, r in top.iloc[3:10].iterrows():
        ui.leaderboard_row(i + 1, insights.public_name(r["name"]), ui.bg_badge(r["blood_group"]), ui.tier_pill(r["tier"]),
                           f"{int(r['donations'])} 🩸")
    st.divider()
    ui.section("Donors by hero level")
    order = [t[1] for t in insights.TIERS]
    cnt = prof["tier"].value_counts().reindex(order).fillna(0).astype(int).reset_index()
    cnt.columns = ["tier", "donors"]
    ch = alt.Chart(cnt).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8, color=ui.RED).encode(
        x=alt.X("tier:N", sort=order, title=None, axis=alt.Axis(labelAngle=0)), y=alt.Y("donors:Q", title=None, axis=alt.Axis(tickMinStep=1)),
        tooltip=["tier", "donors"])
    show_chart(ui.style_chart(ch, st.session_state.get("dark_mode", False), 220))

    if is_admin():
        st.divider()
        ui.section("🎓 Certificates", "Download a printable thank-you certificate for a confirmed donation.")
        dn = db.confirmed_donations()
        if dn.empty:
            st.caption("No confirmed donations yet.")
            return
        opts = {f"{r['name']} · {r['blood_group']} · request #{int(r['request_id'])}": i for i, r in dn.iterrows()}
        pick = st.selectbox("Choose a donation", list(opts.keys()), key="cert_pick")
        row = dn.loc[opts[pick]]
        n_don = int(prof.loc[prof["id"] == row["donor_id"], "donations"].iloc[0])
        st.download_button("⬇️ Download certificate (open and press Ctrl+P for PDF)",
                           insights.certificate_html(row["name"], row["blood_group"], str(row["donated_on"])[:10], n_don,
                                                     str(row["hospital"] or "").title()),
                           f"certificate_{int(row['donation_id'])}.html", "text/html")


# =====================================================================
# TAB: TOOLS
# =====================================================================
def tab_tools():
    ui.section("Blood compatibility checker", "Who can give to whom. Pick a group to highlight it.")
    g = st.selectbox("Blood group", GROUPS, index=GROUPS.index("O+"), key="tool_group")
    st.markdown(f"**{g} can receive from:** " + " ".join(ui.bg_badge(x) for x in matcher.COMPAT[g]), unsafe_allow_html=True)
    st.markdown(f"**{g} can donate to:** " + " ".join(ui.bg_badge(x) for x in matcher.can_donate_to(g)), unsafe_allow_html=True)
    ui.compat_matrix(matcher.COMPAT, highlight=g)

    st.divider()
    ui.section("When can I donate again?", "Whole blood donors wait 90 days between donations.")
    ld = st.date_input("Last donation date", value=date.today(), max_value=date.today(), key="tool_last")
    left = matcher.days_until_eligible(str(ld))
    if left == 0:
        st.success("✅ You can donate today.")
    else:
        st.info(f"⏳ You can donate again on **{matcher.next_eligible_date(str(ld)):%d %b %Y}** ({left} days from now).")

    st.divider()
    ui.section("Am I ready to donate?", "A quick self-check before you go. The centre will do the final health screening.")
    q1, q2, q3 = st.columns(3)
    age = q1.number_input("Age", min_value=10, max_value=90, value=25, key="rd_age")
    wt = q2.number_input("Weight (kg)", min_value=20, max_value=200, value=60, key="rd_wt")
    days_since = q3.number_input("Days since last donation (0 = never)", min_value=0, max_value=3650, value=0, key="rd_days")
    w1, w2 = st.columns(2)
    well = w1.checkbox("I feel completely well today", value=True, key="rd_well")
    tat = w2.checkbox("I had a tattoo or piercing in the last 6 months", value=False, key="rd_tat")
    ok, why = insights.readiness(int(age), int(wt), well, int(days_since) or None, tat)
    if ok:
        st.success("✅ You look ready to donate. Eat well, drink water and carry a photo ID.")
    else:
        for w in why:
            st.warning(w)

    if not is_admin():
        return
    st.divider()
    ui.section("Recent activity", "Everything important that happened, newest first.")
    ui.feed(db.recent_activity(40))

    st.divider()
    ui.section("Backup and export", "Download your data. Keep a copy of the database file safe.")
    b1, b2, b3 = st.columns(3)
    try:
        with open(db.DB, "rb") as fh:
            b1.download_button("💾 Database backup (.db)", fh.read(), "donors_backup.db", "application/octet-stream")
    except OSError:
        b1.caption("Database file not found.")
    b2.download_button("⬇️ Donors CSV", db.table("donors").to_csv(index=False).encode("utf-8"), "donors_all.csv", "text/csv")
    b3.download_button("⬇️ Requests CSV", db.request_stats().to_csv(index=False).encode("utf-8"), "requests_all.csv", "text/csv")


# =====================================================================
# MAIN LAYOUT
# =====================================================================
_donors_n, _reqs = len(db.table("donors")), db.table("requests")
_open_n = int(_reqs.status.isin(db.OPEN_STATUSES).sum()) if not _reqs.empty else 0
ui.hero("Blood Donor Matcher", "Find matching blood donors in an emergency and email them instantly.",
        chips=[f"🧑 {_donors_n} donors", f"🆘 {_open_n} open request(s)", "🔮 Response forecast", "📍 Nearest donors first", "🏆 Hero levels"])

if not os.getenv("EMAIL") or not os.getenv("APP_PASSWORD"):
    st.error("⚠️ EMAIL or APP_PASSWORD is missing in .env. Emails will not be sent.")

if is_admin():
    TABS = [("📊 Dashboard", tab_dashboard), ("🆘 Request Blood", tab_request), ("🧑 Register", tab_register),
            ("👥 Donors", tab_donors), ("🏥 Blood Banks", tab_banks), ("📈 Analytics", tab_analytics),
            ("🏆 Hall of Fame", tab_fame), ("🧰 Tools", tab_tools)]
else:
    st.info("🔒 Coordinator tools are locked. Donors can register below. Enter the PIN in the sidebar to unlock.")
    TABS = [("🧑 Register", tab_register), ("🏆 Hall of Fame", tab_fame), ("🧰 Tools", tab_tools)]

for _tab, (_label, _fn) in zip(st.tabs([l for l, _ in TABS]), TABS):
    with _tab:
        _fn()

# ---------- sidebar (bottom) and footer ----------
with st.sidebar:
    st.divider()
    st.markdown("**How it works**\n\n1. Register donors\n2. Add blood banks\n3. Request blood in an emergency\n"
                "4. Review the matches, send alerts\n5. Donor answers from the email link\n6. Confirm the donor on the Dashboard")
    if is_admin():
        st.divider()
        _d, _r = db.table("donors"), db.table("requests")
        s1, s2 = st.columns(2)
        s1.metric("Donors", len(_d))
        s2.metric("Open", int(_r.status.isin(db.OPEN_STATUSES).sum()) if not _r.empty else 0)
        st.markdown("**Live activity**")
        ui.feed(db.recent_activity(6))
    st.caption("Donors who gave blood in the last 90 days, or who paused themselves, are skipped automatically.")

st.divider()
st.caption("Built with Streamlit, SQLite, Gmail and Docker · Every drop counts 🩸")
