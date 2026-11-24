# Smart features: donor reliability, response forecast, smart donor picking, SLA timers,
# hero tiers, coordinator copilot, certificates. No Streamlit in here, so it can be tested on its own.
import math
from datetime import datetime, date
from html import escape
import pandas as pd
import matcher

# ---------------------------------------------------------------- hero tiers
TIERS = [  # (min confirmed donations, name, icon, colour)
    (0, "Newcomer", "🌱", "#7A9E7E"),
    (1, "Bronze", "🥉", "#B9770E"),
    (3, "Silver", "🥈", "#7F8C9B"),
    (5, "Gold", "🥇", "#D4A017"),
    (10, "Lifesaver", "💎", "#D7263D"),
]
LIVES_PER_DONATION = 3      # one whole-blood donation can help up to three patients


def tier_for(donations):
    donations = int(donations or 0)
    best = TIERS[0]
    for t in TIERS:
        if donations >= t[0]:
            best = t
    return best


def next_tier(donations):
    """(tier tuple, donations still needed) or None if already at the top."""
    donations = int(donations or 0)
    for t in TIERS:
        if t[0] > donations:
            return t, t[0] - donations
    return None


def public_name(name):
    """'Asha Rao' -> 'Asha R.'  (the public Hall of Fame never shows full names)."""
    parts = str(name or "").strip().split()
    if not parts:
        return "Donor"
    return parts[0].title() + (f" {parts[-1][0].upper()}." if len(parts) > 1 else "")


# ---------------------------------------------------------------- reliability + forecast
def yes_rate(emailed, accepted):
    """Smoothed share of alerts a donor says yes to (a new donor starts at about 1 in 3)."""
    return (int(accepted) + 1) / (int(emailed) + 3)


def reliability(emailed, accepted, donations):
    """0-100. Mixes how often the donor says yes with how often a yes ends in a real donation."""
    follow = min(1.0, (int(donations) + 1) / (int(accepted) + 1))
    return int(round(100 * (0.65 * yes_rate(emailed, accepted) + 0.35 * follow)))


def donor_profiles(donors_df, stats_df):
    """Adds emailed / accepted / donations / reliability / tier / lives to the donor table."""
    if donors_df is None or donors_df.empty:
        return donors_df
    df = donors_df.merge(stats_df, on="id", how="left") if stats_df is not None else donors_df.copy()
    for c in ("emailed", "accepted", "donations"):
        df[c] = df.get(c, 0)
        df[c] = df[c].fillna(0).astype(int)
    df["reliability"] = [reliability(e, a, d) for e, a, d in zip(df["emailed"], df["accepted"], df["donations"])]
    df["tier"] = [tier_for(d)[1] for d in df["donations"]]
    df["lives"] = df["donations"] * LIVES_PER_DONATION
    return df


def add_forecast(donors, profiles, urgency="Planned", radius=50):
    """For a list of matched donors: probability each says yes ('yes_chance', 0-1) and a 'priority'
    that blends match score and that probability. Returns a copy sorted by priority."""
    if donors is None or donors.empty:
        return donors
    df = donors.copy()
    rate = {}
    if profiles is not None and not profiles.empty:
        rate = {int(r.id): yes_rate(r.emailed, r.accepted) for r in profiles.itertuples()}
    boost = 1.1 if urgency == "Critical" else 1.0
    chances = []
    for did, dist in zip(df["id"], df["distance_km"]):
        prox = max(0.0, 1 - float(dist) / max(radius, 1))
        base = rate.get(int(did), 1 / 3)
        chances.append(round(min(0.9, max(0.05, 0.75 * (0.75 * base + 0.25 * prox) * boost)), 3))
    df["yes_chance"] = chances
    df["priority"] = (0.5 * df["score"] / 100 + 0.5 * df["yes_chance"]).round(3)
    return df.sort_values("priority", ascending=False)


def prob_at_least(probs, k):
    """Probability that at least k donors say yes (each with its own chance). Poisson-binomial."""
    k = int(k)
    if k <= 0:
        return 1.0
    dist = [1.0]
    for p in probs:
        nxt = [0.0] * (len(dist) + 1)
        for i, q in enumerate(dist):
            nxt[i] += q * (1 - p)
            nxt[i + 1] += q * p
        dist = nxt
    return float(sum(dist[k:])) if k < len(dist) else 0.0


def smart_pick(donors, units, target=0.9):
    """Smallest set of top-priority donors whose combined chance of covering all units reaches the target.
    Returns (list of donor ids, achieved confidence)."""
    if donors is None or donors.empty:
        return [], 0.0
    ordered = donors.sort_values("priority", ascending=False)
    chosen, probs = [], []
    for did, p in zip(ordered["id"], ordered["yes_chance"]):
        chosen.append(int(did)); probs.append(float(p))
        if prob_at_least(probs, units) >= target:
            break
    return chosen, prob_at_least(probs, units)


# ---------------------------------------------------------------- SLA timers
SLA_MINUTES = {"Critical": 60, "Within 24 hours": 24 * 60, "Planned": 72 * 60}


def _parse(ts):
    try:
        return datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def fmt_duration(minutes):
    minutes = int(abs(minutes))
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 48 * 60:
        h, m = divmod(minutes, 60)
        return f"{h} h {m:02d} min" if h < 10 else f"{h} h"
    return f"{minutes // 1440} d"


def sla(urgency, created, now=None):
    """How much of the response window is used. state: ok (<60%), warn (60-100%), late (>100%)."""
    target = SLA_MINUTES.get(urgency, SLA_MINUTES["Planned"])
    t = _parse(created)
    if t is None:
        return {"pct": 0, "state": "ok", "label": "—", "elapsed": 0, "target": target}
    elapsed = ((now or datetime.now()) - t).total_seconds() / 60
    pct = max(0, round(100 * elapsed / target))
    state = "late" if pct >= 100 else ("warn" if pct >= 60 else "ok")
    left = target - elapsed
    label = f"{fmt_duration(left)} left" if left > 0 else f"{fmt_duration(left)} over"
    return {"pct": min(pct, 100), "raw_pct": pct, "state": state, "label": label, "elapsed": elapsed, "target": target}


# ---------------------------------------------------------------- re-engagement
def due_soon(donors_df, days=14):
    """Donors who finish their 90-day break within the next N days (good people to message)."""
    if donors_df is None or donors_df.empty:
        return pd.DataFrame(columns=["name", "blood_group", "city", "days_left"])
    df = donors_df.copy()
    df["days_left"] = df["last_donation"].apply(matcher.days_until_eligible)
    if "available" in df.columns:
        df = df[df["available"].fillna(1).astype(int) == 1]
    df = df[(df["days_left"] > 0) & (df["days_left"] <= days)].sort_values("days_left")
    return df[["name", "blood_group", "city", "days_left"]]


# ---------------------------------------------------------------- coordinator copilot
def copilot(stats, approvals, supply, donors_df, now=None):
    """Plain-language suggestions for the coordinator. Returns a list of {level, icon, text}."""
    tips = []
    if stats is not None and not stats.empty:
        for r in stats[stats["status"].isin(("Pending", "Notified", "Partial"))].itertuples():
            s = sla(r.urgency, r.created, now)
            who = f"Request #{r.id} ({r.blood_group}, {str(r.city).title()})"
            if r.emailed == 0:
                tips.append({"level": "bad", "icon": "📭", "text": f"{who} has no donors alerted yet. Widen the radius or contact blood banks."})
            elif r.accepted + r.confirmed == 0 and s["state"] != "ok":
                tips.append({"level": "bad" if s["state"] == "late" else "warn", "icon": "⏱️",
                             "text": f"{who} has {r.emailed} alert{'s' if r.emailed != 1 else ''} but no YES and its timer shows {s['label']}. Press Alert more donors."})
            elif s["state"] == "late" and r.confirmed < r.units:
                tips.append({"level": "warn", "icon": "⌛", "text": f"{who} is past its target response time with {r.confirmed}/{r.units} units."})
    if approvals is not None and not approvals.empty:
        n = len(approvals)
        tips.append({"level": "warn", "icon": "🙋", "text": f"{n} donor{'s' if n != 1 else ''} said YES and "
                                                           f"{'are' if n != 1 else 'is'} waiting for your confirmation."})
    if supply is not None and not supply.empty:
        short = supply[supply["supply"] == "Shortage"]["blood_group"].tolist()
        if short:
            tips.append({"level": "bad", "icon": "🩸", "text": "Shortage of eligible donors for " + ", ".join(short) + ". Run a recruitment drive."})
    soon = due_soon(donors_df, 7)
    if len(soon):
        tips.append({"level": "info", "icon": "📅", "text": f"{len(soon)} donor{'s' if len(soon) != 1 else ''} finish their 90-day break within a week. "
                                                           "A friendly reminder now keeps your pool full."})
    if not tips:
        tips.append({"level": "good", "icon": "✨", "text": "All clear. No open problems right now."})
    order = {"bad": 0, "warn": 1, "info": 2, "good": 3}
    return sorted(tips, key=lambda t: order[t["level"]])


# ---------------------------------------------------------------- sharing + eligibility quiz
def broadcast_text(req, link=""):
    """Ready-to-paste WhatsApp / SMS message for a request."""
    lines = [f"🆘 *{req['blood_group']} blood needed* ({req['urgency']})",
             f"Patient: {req['patient']}",
             f"Hospital: {req['hospital']}, {str(req['city']).title()}",
             f"Units: {req.get('units') or 1}",
             f"Contact: {req['contact']}"]
    if link:
        lines.append(f"Reply here: {link}")
    lines.append("Please share. Every minute counts. ❤️")
    return "\n".join(lines)


def readiness(age, weight, feeling_well, last_donation_days, tattoo_recent=False):
    """Quick pre-donation self check. Returns (ok, [reasons it is not ok])."""
    why = []
    if not 18 <= age <= 65:
        why.append("Donors must be 18 to 65 years old.")
    if weight < 45:
        why.append("Minimum weight is 45 kg.")
    if not feeling_well:
        why.append("Wait until you feel completely well (no fever, cold or infection).")
    if last_donation_days is not None and last_donation_days < matcher.COOLDOWN_DAYS:
        why.append(f"Wait {matcher.COOLDOWN_DAYS - last_donation_days} more day(s) since your last donation.")
    if tattoo_recent:
        why.append("Wait 6 months after a tattoo or piercing.")
    return (not why), why


def certificate_html(name, blood_group, when, donations, hospital=""):
    """Printable, self-contained certificate (open the file and press Ctrl+P to save as PDF)."""
    n, bg, wh, hs = escape(str(name)), escape(str(blood_group)), escape(str(when)), escape(str(hospital))
    tier = escape(tier_for(donations)[1])
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Certificate - {n}</title>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,600;1,500&family=Plus+Jakarta+Sans:wght@500;700&display=swap" rel="stylesheet">
<style>
@page{{size:A4 landscape;margin:0}}
body{{margin:0;background:#fff7f4;font-family:'Plus Jakarta Sans',sans-serif;color:#2a1517;display:flex;justify-content:center;padding:24px}}
.c{{width:1040px;height:700px;box-sizing:border-box;padding:46px 64px;text-align:center;position:relative;
background:radial-gradient(circle at 12% 8%,#ffd9d9,transparent 38%),radial-gradient(circle at 92% 95%,#ffe5cf,transparent 40%),#fff;
border:3px solid #7a0f1e;border-radius:26px;box-shadow:inset 0 0 0 10px #fff,inset 0 0 0 12px #d7263d33}}
.drop{{font-size:54px}}
h1{{font-family:'Fraunces',serif;font-size:46px;margin:6px 0 2px;color:#7a0f1e;letter-spacing:.5px}}
.k{{letter-spacing:5px;font-size:13px;font-weight:700;color:#d7263d;text-transform:uppercase}}
.n{{font-family:'Fraunces',serif;font-style:italic;font-size:58px;margin:26px 0 8px;border-bottom:2px solid #d7263d55;display:inline-block;padding:0 30px}}
p{{font-size:17px;line-height:1.7;margin:8px auto;max-width:720px}}
.row{{display:flex;justify-content:center;gap:34px;margin-top:26px}}
.b{{background:#fff;border:1px solid #d7263d44;border-radius:16px;padding:12px 24px}}
.b b{{display:block;font-size:26px;color:#d7263d}}.b span{{font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#7a5c5f}}
.f{{position:absolute;bottom:34px;left:0;right:0;font-size:13px;color:#7a5c5f}}
</style></head><body><div class="c"><div class="drop">🩸</div><div class="k">Certificate of Gratitude</div>
<h1>A Life-Saving Hero</h1><p>This certificate is proudly presented to</p><div class="n">{n}</div>
<p>for the generous gift of blood{(' at ' + hs) if hs else ''} on <b>{wh}</b>. Your act of kindness gives someone
another day with the people they love. Thank you.</p>
<div class="row"><div class="b"><b>{bg}</b><span>Blood group</span></div>
<div class="b"><b>{int(donations)}</b><span>Donations</span></div>
<div class="b"><b>{int(donations) * LIVES_PER_DONATION}</b><span>Lives touched</span></div>
<div class="b"><b>{tier}</b><span>Hero level</span></div></div>
<div class="f">Blood Donor Matcher · Every drop counts</div></div></body></html>"""
