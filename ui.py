# Look and feel: "Crimson Glass" design system (light + dark) and small HTML helpers. All user text is escaped.
import math
import os
from datetime import datetime
from html import escape
from urllib.parse import quote
import pandas as pd
import streamlit as st

FONT = ("@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700;9..144,800"
        "&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');")

LIGHT_VARS = """
:root{--text:#2A1517;--muted:#7A5C5F;--card:rgba(255,255,255,.74);--solid:#FFFFFF;--border:rgba(168,40,56,.14);
--soft:#FFF1EF;--th:#FDE9E7;--stripe:rgba(255,241,239,.55);--accent:#D7263D;--accent2:#FF6B6B;--title:#7A0F1E;
--red-bg:#FDE4E4;--red:#B3162B;--green-bg:#E3F5EA;--green:#1B7D45;--orange-bg:#FFEBD6;--orange:#B35A00;
--blue-bg:#E4ECFD;--blue:#2756B8;--gray-bg:#EDE7E7;--gray:#4B4143;--shadow:rgba(122,15,30,.07);--shadow2:rgba(215,38,61,.28);
--app-bg:radial-gradient(1000px 520px at 6% -8%,#FFD6D6 0%,transparent 60%),radial-gradient(900px 520px at 100% 0%,#FFE6D1 0%,transparent 55%),
radial-gradient(800px 600px at 50% 110%,#FFE0E6 0%,transparent 60%),#FFF8F5;--glow:rgba(215,38,61,.18)}
"""

DARK_VARS = """
:root{--text:#F8ECEE;--muted:#BBA5AA;--card:rgba(36,22,29,.72);--solid:#24161D;--border:rgba(255,120,134,.16);
--soft:#1B1015;--th:#2E1A22;--stripe:rgba(255,255,255,.025);--accent:#FF4D63;--accent2:#FF8A8A;--title:#FF9AA6;
--red-bg:#40181F;--red:#FF9AA6;--green-bg:#14331F;--green:#7FE0A3;--orange-bg:#3B2812;--orange:#FFB765;
--blue-bg:#1B2A47;--blue:#9DBBFF;--gray-bg:#2D2428;--gray:#D6CDD0;--shadow:rgba(0,0,0,.45);--shadow2:rgba(255,77,99,.30);
--app-bg:radial-gradient(900px 520px at 4% -10%,#4A1220 0%,transparent 60%),radial-gradient(800px 500px at 100% 0%,#2D1230 0%,transparent 55%),
radial-gradient(800px 600px at 50% 115%,#3A0F1C 0%,transparent 60%),#0E080B;--glow:rgba(255,77,99,.22)}
"""

BASE_CSS = """
.stApp,[data-testid="stAppViewContainer"]{background:var(--app-bg) !important;background-attachment:fixed !important}
[data-testid="stHeader"]{background:transparent !important}
.stApp{font-family:'Plus Jakarta Sans','Inter',sans-serif;color:var(--text)}
.block-container{padding-top:1.3rem;max-width:1220px}
footer{visibility:hidden}
.stApp p,.stApp li{font-weight:500}
.stApp h1,.stApp h2,.stApp h3{font-family:'Fraunces',serif;color:var(--title);letter-spacing:-.01em}
[data-testid="stWidgetLabel"] p{font-weight:700 !important;font-size:.9rem;color:var(--text)}
input,textarea{font-weight:600 !important;color:var(--text)}
[data-baseweb="select"] *{font-weight:600 !important}
[data-testid="stCaptionContainer"]{font-weight:600}
[data-testid="stExpander"] summary p{font-weight:700}
[role="tab"] p,.stTabs [data-baseweb="tab"] p{font-weight:700}
.stButton>button p,.stDownloadButton>button p,[data-testid="stFormSubmitButton"]>button p{font-weight:700}
::selection{background:var(--accent);color:#fff}
/* ---------- inputs / buttons ---------- */
[data-baseweb="input"],[data-baseweb="base-input"],[data-baseweb="select"]>div,[data-baseweb="textarea"]{border-radius:12px !important}
[data-baseweb="input"]:focus-within,[data-baseweb="select"]>div:focus-within{box-shadow:0 0 0 3px var(--glow) !important;border-color:var(--accent) !important}
.stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button,.stLinkButton>a{
  border-radius:12px;padding:.5rem 1.1rem;border:1px solid var(--border);background:var(--card);backdrop-filter:blur(8px);
  transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease}
.stButton>button:hover,.stDownloadButton>button:hover,[data-testid="stFormSubmitButton"]>button:hover{
  transform:translateY(-2px);box-shadow:0 10px 22px var(--shadow2);border-color:var(--accent)}
.stButton>button:active{transform:translateY(0)}
.stButton>button[kind="primary"],[data-testid="stBaseButton-primary"],[data-testid="stFormSubmitButton"]>button[kind="primaryFormSubmit"],
[data-testid="stBaseButton-primaryFormSubmit"]{background:linear-gradient(135deg,var(--accent),var(--accent2)) !important;border:0 !important;
  box-shadow:0 8px 20px var(--shadow2);color:#fff !important}
.stButton>button[kind="primary"] p,[data-testid="stBaseButton-primary"] p,[data-testid="stBaseButton-primaryFormSubmit"] p{color:#fff !important}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:18px;background:var(--card);backdrop-filter:blur(10px);
  box-shadow:0 4px 18px var(--shadow);border-color:var(--border) !important}
[data-testid="stExpander"] details{border-radius:18px;background:var(--card);backdrop-filter:blur(10px);border-color:var(--border) !important;
  box-shadow:0 4px 18px var(--shadow)}
[data-testid="stMetric"]{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:12px 16px;box-shadow:0 4px 18px var(--shadow)}
[data-testid="stMetricValue"]{font-family:'Fraunces',serif;font-weight:700}
[data-testid="stAlert"]{border-radius:16px}
[data-testid="stForm"]{border-radius:20px;background:var(--card);backdrop-filter:blur(10px);border:1px solid var(--border);padding:1.2rem 1.3rem}
[data-testid="stProgress"] > div > div > div{background:linear-gradient(90deg,var(--accent),var(--accent2)) !important}
hr{border-color:var(--border) !important}
/* ---------- tabs ---------- */
[role="tablist"],[data-baseweb="tab-list"]{gap:4px;background:var(--card);border:1px solid var(--border);border-radius:18px;padding:6px;
  backdrop-filter:blur(12px);flex-wrap:wrap;box-shadow:0 6px 22px var(--shadow)}
[role="tab"],.stTabs [data-baseweb="tab"]{background:transparent;border-radius:13px;padding:8px 11px;white-space:nowrap;height:auto;transition:background .15s}
[role="tab"]:hover,.stTabs [data-baseweb="tab"]:hover{background:var(--th)}
[role="tab"][aria-selected="true"],.stTabs [aria-selected="true"]{background:linear-gradient(135deg,var(--accent),var(--accent2)) !important;box-shadow:0 6px 16px var(--shadow2)}
[role="tab"][aria-selected="true"] p,.stTabs [aria-selected="true"] p{color:#fff !important}
[role="tablist"]>:not([role="tab"]),[data-testid="stTabs"]>div:first-child,[role="tablist"]+div,[role="tablist"]::after{border-bottom:0 !important;box-shadow:none !important}
[role="tablist"]>:not([role="tab"]){display:none !important}
[data-baseweb="tab-highlight"],[data-baseweb="tab-border"]{display:none !important;height:0 !important}
[data-testid="stSidebar"]{background:var(--soft);border-right:1px solid var(--border)}
/* ---------- hero ---------- */
.hero{position:relative;overflow:hidden;color:#fff;padding:30px 34px 24px;border-radius:26px;margin-bottom:20px;
  background:radial-gradient(600px 300px at 90% -20%,rgba(255,170,150,.55),transparent 60%),
             linear-gradient(125deg,#5A0A18 0%,#9B1428 45%,#D7263D 100%);
  box-shadow:0 22px 50px rgba(122,15,30,.33),inset 0 1px 0 rgba(255,255,255,.18)}
.hero:before{content:"";position:absolute;width:340px;height:340px;right:-90px;top:-160px;border-radius:50%;
  border:1px solid rgba(255,255,255,.18);box-shadow:0 0 0 46px rgba(255,255,255,.04),0 0 0 100px rgba(255,255,255,.03)}
.hero-row{display:flex;align-items:center;gap:22px;position:relative;z-index:1}
.drop-wrap{width:74px;height:84px;flex:none;filter:drop-shadow(0 10px 18px rgba(0,0,0,.35));animation:beat 1.9s ease-in-out infinite;transform-origin:50% 70%}
.eyebrow{display:flex;align-items:center;gap:8px;font-size:.72rem;font-weight:800;letter-spacing:.18em;text-transform:uppercase;color:#FFD9D9}
.live{width:9px;height:9px;border-radius:50%;background:#7CFFB0;box-shadow:0 0 0 0 rgba(124,255,176,.7);animation:livepulse 1.8s infinite}
.hero-title{font-family:'Fraunces',serif;font-size:2.35rem;font-weight:700;line-height:1.1;color:#fff;margin-top:4px;letter-spacing:-.02em}
.hero-sub{margin-top:8px;font-size:1.02rem;font-weight:500;color:#FFE4E4;max-width:640px}
.ecg{position:absolute;right:26px;top:26px;width:34%;height:62px;opacity:.5;z-index:0}
.ecg path{fill:none;stroke:#fff;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:.34 .66;
  animation:ecg 3.2s linear infinite;filter:drop-shadow(0 0 5px rgba(255,255,255,.9))}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:20px;position:relative;z-index:1}
.chip{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.26);color:#fff;border-radius:999px;
  padding:5px 14px;font-size:.8rem;font-weight:700;backdrop-filter:blur(8px)}
@keyframes beat{0%,100%{transform:scale(1)}12%{transform:scale(1.12)}24%{transform:scale(1)}36%{transform:scale(1.07)}48%{transform:scale(1)}}
@keyframes ecg{from{stroke-dashoffset:1}to{stroke-dashoffset:-.0}}
@keyframes livepulse{0%{box-shadow:0 0 0 0 rgba(124,255,176,.7)}70%{box-shadow:0 0 0 9px rgba(124,255,176,0)}100%{box-shadow:0 0 0 0 rgba(124,255,176,0)}}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(215,38,61,.55)}70%{box-shadow:0 0 0 12px rgba(215,38,61,0)}100%{box-shadow:0 0 0 0 rgba(215,38,61,0)}}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes marquee{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@keyframes wave{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
/* ---------- ticker ---------- */
.ticker{overflow:hidden;white-space:nowrap;border:1px solid var(--border);background:var(--card);backdrop-filter:blur(10px);
  border-radius:999px;margin:-4px 0 16px;padding:8px 0;box-shadow:0 4px 16px var(--shadow)}
.ticker .tr{display:inline-block;animation:marquee 38s linear infinite;padding-left:100%}
.ticker:hover .tr{animation-play-state:paused}
.ticker .ti{display:inline-block;margin:0 26px;font-size:.82rem;font-weight:700;color:var(--text)}
.ticker .ti small{color:var(--muted);font-weight:700;margin-left:6px}
/* ---------- stat cards (bento) ---------- */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:6px 0 16px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:16px 18px;position:relative;
  box-shadow:0 6px 22px var(--shadow);animation:rise .5s ease both;overflow:hidden;backdrop-filter:blur(10px);
  transition:transform .2s ease,box-shadow .2s ease}
.stat:hover{transform:translateY(-3px);box-shadow:0 14px 30px var(--shadow2)}
.stat:nth-child(2){animation-delay:.05s}.stat:nth-child(3){animation-delay:.1s}.stat:nth-child(4){animation-delay:.15s}.stat:nth-child(5){animation-delay:.2s}
.stat:before{content:"";position:absolute;inset:0;background:radial-gradient(180px 110px at 100% 0%,color-mix(in srgb,var(--c) 22%,transparent),transparent 70%);pointer-events:none}
.stat .ic{width:38px;height:38px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.15rem;
  background:color-mix(in srgb,var(--c) 16%,transparent);margin-bottom:10px}
.stat .n{font-family:'Fraunces',serif;font-size:2.15rem;font-weight:700;color:var(--text);line-height:1}
.stat .l{font-size:.82rem;font-weight:700;color:var(--muted);margin-top:6px}
.stat .s{font-size:.74rem;font-weight:800;color:var(--c);margin-top:4px}
/* ---------- pills, badges ---------- */
.pill{display:inline-block;padding:2px 11px;border-radius:999px;font-size:.76rem;font-weight:800;margin-right:4px;white-space:nowrap}
.pill.red{background:var(--red-bg);color:var(--red)}.pill.green{background:var(--green-bg);color:var(--green)}
.pill.orange{background:var(--orange-bg);color:var(--orange)}.pill.blue{background:var(--blue-bg);color:var(--blue)}
.pill.gray{background:var(--gray-bg);color:var(--gray)}
.bg-badge{display:inline-block;background:linear-gradient(135deg,#9B1428,#FF4D63);color:#fff;border-radius:10px;
  padding:2px 11px;font-weight:800;margin-left:4px;box-shadow:0 4px 10px rgba(215,38,61,.32);letter-spacing:.02em}
.tier{display:inline-flex;align-items:center;gap:5px;border-radius:999px;padding:2px 11px 2px 8px;font-size:.76rem;font-weight:800;
  background:color-mix(in srgb,var(--tc) 16%,transparent);color:var(--tc);border:1px solid color-mix(in srgb,var(--tc) 38%,transparent)}
/* ---------- cards ---------- */
.card{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:18px 20px;margin:8px 0;
  box-shadow:0 6px 22px var(--shadow);backdrop-filter:blur(10px);animation:rise .4s ease both}
.card .t{font-family:'Fraunces',serif;font-size:1.3rem;font-weight:700;margin-bottom:10px;color:var(--text)}
.card .row{color:var(--text);margin:5px 0;font-weight:600}
.card.u-Critical{border-left:6px solid #FF4D63}.card.u-Within24{border-left:6px solid #F08A24}.card.u-Planned{border-left:6px solid #2E9E5B}
.alert-banner{background:linear-gradient(90deg,#9B1428,#FF4D63);color:#fff;border-radius:16px;padding:13px 20px;
  font-weight:800;margin:4px 0 14px;animation:pulse 2s infinite;display:flex;align-items:center;gap:10px}
.empty{text-align:center;border:2px dashed var(--border);border-radius:20px;padding:30px 14px;margin:8px 0;color:var(--muted);background:var(--card)}
.empty .ei{font-size:2.2rem}.empty .et{font-family:'Fraunces',serif;font-size:1.15rem;font-weight:700;color:var(--text);margin-top:4px}
.section{margin:10px 0 2px;font-family:'Fraunces',serif;font-size:1.55rem;font-weight:700;color:var(--title);letter-spacing:-.01em}
.section-sub{color:var(--muted);font-size:.93rem;font-weight:600;margin-bottom:10px}
.glass{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:16px 20px;margin:8px 0;box-shadow:0 6px 22px var(--shadow);backdrop-filter:blur(10px)}
.glass h4{font-family:'Fraunces',serif;margin:0 0 6px;color:var(--title);font-size:1.15rem}
.glass p{margin:4px 0;color:var(--text)}
/* ---------- stepper ---------- */
.steps{display:flex;gap:0;margin:8px 0 14px}
.step{flex:1;text-align:center;position:relative;font-size:.74rem;font-weight:800;color:var(--muted)}
.step .dot{width:28px;height:28px;border-radius:50%;margin:0 auto 5px;display:flex;align-items:center;justify-content:center;
  background:var(--gray-bg);color:var(--gray);font-size:.8rem;position:relative;z-index:1}
.step:not(:last-child):after{content:"";position:absolute;top:13px;left:50%;width:100%;height:3px;background:var(--gray-bg);border-radius:3px}
.step.done .dot{background:#2E9E5B;color:#fff}.step.done:not(:last-child):after{background:#2E9E5B}
.step.now .dot{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;animation:pulse 2s infinite}
.step.done,.step.now{color:var(--text)}
/* ---------- contact links ---------- */
a.cl{display:inline-block;text-decoration:none !important;font-weight:800;font-size:.8rem;border-radius:999px;
  padding:3px 13px;margin:2px 6px 2px 0;border:1px solid var(--border);color:var(--text) !important;background:var(--soft);transition:all .15s}
a.cl:hover{border-color:var(--accent);color:var(--accent) !important;transform:translateY(-1px)}
a.cl.wa{background:var(--green-bg);color:var(--green) !important;border-color:transparent}
/* ---------- compatibility matrix ---------- */
.mx-wrap{overflow-x:auto}
.mx{border-collapse:separate;border-spacing:5px;margin:6px 0;font-size:.85rem}
.mx th{font-weight:800;color:var(--title);padding:4px 8px;text-align:center}
.mx td{width:46px;height:38px;text-align:center;border-radius:11px;font-weight:800;background:var(--gray-bg);color:var(--muted)}
.mx td.y{background:linear-gradient(135deg,#2E9E5B,#5BC98A);color:#fff}
.mx td.sel{outline:3px solid var(--accent);outline-offset:1px}
/* ---------- tables ---------- */
.tbl-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:18px;margin:8px 0 12px;background:var(--card);
  box-shadow:0 6px 22px var(--shadow);backdrop-filter:blur(10px)}
.tbl{border-collapse:collapse;width:100%;font-size:.9rem}
.tbl th{background:var(--th);color:var(--title);text-align:left;padding:12px 14px;font-weight:800;white-space:nowrap;font-size:.76rem;
  letter-spacing:.06em;text-transform:uppercase}
.tbl td{padding:10px 14px;font-weight:600;color:var(--text);border-top:1px solid var(--border);white-space:nowrap}
.tbl tr:nth-child(even) td{background:var(--stripe)}
.tbl tr:hover td{background:var(--th)}
.tbl td.bgc{font-weight:800;color:var(--accent)}
.feed{border-left:3px solid var(--accent);padding-left:11px;margin:0 0 9px;font-size:.82rem;font-weight:600;color:var(--text)}
.feed small{color:var(--muted);font-weight:700;display:block}
/* ---------- sidebar brand ---------- */
.brand{display:flex;align-items:center;gap:10px;margin:2px 0 8px}
.brand .bm{width:38px;height:44px}.brand b{font-family:'Fraunces',serif;font-size:1.2rem;color:var(--title);line-height:1.1;display:block}
.brand span{font-size:.72rem;font-weight:700;color:var(--muted);letter-spacing:.08em;text-transform:uppercase}
/* ---------- copilot ---------- */
.tip{display:flex;gap:12px;align-items:flex-start;background:var(--card);border:1px solid var(--border);border-left:5px solid var(--tc);
  border-radius:16px;padding:11px 15px;margin:7px 0;font-weight:600;animation:rise .4s ease both;backdrop-filter:blur(8px)}
.tip .ti{font-size:1.25rem;line-height:1.3}
.tip.bad{--tc:#FF4D63}.tip.warn{--tc:#F08A24}.tip.info{--tc:#3B6FD4}.tip.good{--tc:#2E9E5B}
/* ---------- SLA ring ---------- */
.sla{display:flex;align-items:center;gap:12px;margin:4px 0 8px}
.ring{--p:0;--rc:#2E9E5B;width:54px;height:54px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;
  background:conic-gradient(var(--rc) calc(var(--p)*1%),var(--gray-bg) 0)}
.ring span{width:42px;height:42px;border-radius:50%;background:var(--solid);display:flex;align-items:center;justify-content:center;
  font-size:.74rem;font-weight:800;color:var(--text)}
.ring.warn{--rc:#F08A24}.ring.late{--rc:#FF4D63;animation:pulse 2s infinite}
.sla b{display:block;font-size:.92rem}.sla small{color:var(--muted);font-weight:700}
/* ---------- blood bags ---------- */
.bags{display:grid;grid-template-columns:repeat(auto-fit,minmax(92px,1fr));gap:12px;margin:8px 0 14px}
.bag{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:12px 10px 12px;text-align:center;
  backdrop-filter:blur(10px);box-shadow:0 6px 22px var(--shadow);transition:transform .2s;animation:rise .5s ease both}
.bag:hover{transform:translateY(-4px)}
.bag svg{width:64px;height:92px}
.bag .g{font-family:'Fraunces',serif;font-weight:700;font-size:1.25rem;color:var(--text)}
.bag .m{font-size:.74rem;font-weight:700;color:var(--muted)}
.bag.Shortage{border-color:#FF4D63;box-shadow:0 0 0 3px var(--glow),0 6px 22px var(--shadow)}
.bag.Low{border-color:#F08A24}
.wave{animation:wave 3.5s linear infinite}
/* ---------- podium / hall of fame ---------- */
.podium{display:flex;align-items:flex-end;justify-content:center;gap:14px;margin:14px 0 8px}
.pod{flex:1;max-width:210px;text-align:center}
.pod .av{width:62px;height:62px;border-radius:50%;margin:0 auto -14px;position:relative;z-index:2;display:flex;align-items:center;justify-content:center;
  font-size:1.9rem;background:var(--solid);border:3px solid var(--tc);box-shadow:0 8px 20px var(--shadow2)}
.pod .bl{background:linear-gradient(180deg,color-mix(in srgb,var(--tc) 38%,var(--solid)),var(--card));border:1px solid var(--border);
  border-radius:20px 20px 8px 8px;padding:22px 8px 12px;height:var(--h);backdrop-filter:blur(8px)}
.pod .nm{font-family:'Fraunces',serif;font-weight:700;font-size:1.05rem;color:var(--text)}
.pod .ds{font-size:.78rem;font-weight:700;color:var(--muted)}
.pod .big{font-family:'Fraunces',serif;font-size:1.9rem;font-weight:700;color:var(--tc)}
.lb{display:flex;align-items:center;gap:12px;padding:9px 14px;border:1px solid var(--border);border-radius:14px;margin:6px 0;background:var(--card)}
.lb .rk{width:28px;font-family:'Fraunces',serif;font-weight:700;color:var(--muted)}
.lb .nm{flex:1;font-weight:700}
.meter{height:10px;border-radius:99px;background:var(--gray-bg);overflow:hidden;margin:6px 0}
.meter i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,var(--accent),var(--accent2))}
.fc{display:flex;gap:14px;flex-wrap:wrap;margin:6px 0 4px}
.fc .k{flex:1;min-width:150px;background:var(--card);border:1px solid var(--border);border-radius:16px;padding:10px 14px}
.fc .k b{font-family:'Fraunces',serif;font-size:1.6rem;display:block;color:var(--text)}
.fc .k span{font-size:.75rem;font-weight:700;color:var(--muted)}
@media (max-width:640px){.ecg{display:none}.hero{padding:22px 20px}.hero-title{font-size:1.65rem}.drop-wrap{width:54px;height:62px}.pod .big{font-size:1.4rem}}
@media (prefers-reduced-motion:reduce){.drop-wrap,.alert-banner,.step.now .dot,.stat,.live,.ticker .tr,.ecg path,.wave,.ring.late,.card,.tip,.bag{animation:none}}
"""

DARK_CSS = """
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp h6{color:var(--title) !important}
.stApp p:not([data-testid="stAlert"] *),.stApp li:not([data-testid="stAlert"] *),
.stApp label,.stApp [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stMetricValue"],.stApp [data-testid="stMetricLabel"],
.stApp [data-testid="stExpander"] summary,.stApp [data-testid="stCheckbox"] span,.stApp [data-testid="stRadio"] label{color:#F8ECEE !important}
.stApp [data-testid="stCaptionContainer"]{color:#BBA5AA !important}
[data-testid="stSidebar"]{background:#150C10 !important}
input,textarea,[data-baseweb="select"]>div,[data-baseweb="base-input"],[data-baseweb="input"]{
  background:#2A1A21 !important;color:#F8ECEE !important;border-color:rgba(255,120,134,.22) !important}
[data-baseweb="select"] *{color:#F8ECEE !important}
[data-baseweb="popover"] *,[data-baseweb="menu"] *{color:#F8ECEE !important}
[data-baseweb="popover"],[data-baseweb="menu"],[data-baseweb="popover"] ul{background:#2A1A21 !important}
.stButton>button p,.stDownloadButton>button p,[data-testid="stFormSubmitButton"]>button p{color:#F8ECEE !important}
.stButton>button[kind="primary"] p,[data-testid="stBaseButton-primary"] p,[data-testid="stBaseButton-primaryFormSubmit"] p{color:#fff !important}
.stButton>button:disabled{opacity:.45}
[role="tab"] p,.stTabs [data-baseweb="tab"] p{color:#F8ECEE}
[role="tab"]:hover{background:rgba(255,255,255,.06)}
.mx td{background:#2D2428}
.tbl tr:hover td{background:rgba(255,255,255,.05)}
.hero{box-shadow:0 22px 50px rgba(0,0,0,.55),inset 0 1px 0 rgba(255,255,255,.12)}
"""

# colours for charts
RED, GREEN, ORANGE, BLUE, GRAY = "#D7263D", "#2E9E5B", "#F08A24", "#3B6FD4", "#9AA3B2"


def inject_css(dark=False):
    css = FONT + (DARK_VARS if dark else LIGHT_VARS) + BASE_CSS + (DARK_CSS if dark else "")
    st.markdown("<style>" + css.replace("\n\n", "\n") + "</style>", unsafe_allow_html=True)


def hide_sidebar():
    """Donor response page: public visitors do not need the coordinator sidebar."""
    st.markdown("<style>[data-testid='stSidebar'],[data-testid='collapsedControl'],"
                "[data-testid='stSidebarCollapsedControl']{display:none !important}</style>", unsafe_allow_html=True)


# ---------- logo / hero ----------
DROP_SVG = ("<svg viewBox='0 0 64 76' xmlns='http://www.w3.org/2000/svg'><defs>"
            "<linearGradient id='dg' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#FFB4B4'/>"
            "<stop offset='.45' stop-color='#FF4D63'/><stop offset='1' stop-color='#8E0F22'/></linearGradient></defs>"
            "<path d='M32 3C32 3 8 32 8 48a24 24 0 0 0 48 0C56 32 32 3 32 3Z' fill='url(#dg)'/>"
            "<path d='M20 46a12 12 0 0 0 7 11' fill='none' stroke='#fff' stroke-opacity='.75' stroke-width='4' stroke-linecap='round'/></svg>")
ECG_SVG = ("<svg class='ecg' viewBox='0 0 800 54' preserveAspectRatio='none'><path pathLength='1' "
           "d='M0 28H230l12-6 10 6h28l10-4 8 4h50l14-22 18 46 16-34 10 10h40l12-6 12 6H800'/></svg>")


def hero(title, subtitle="", chips=None, eyebrow="Live emergency coordination"):
    chips_html = "".join(f"<span class='chip'>{escape(c)}</span>" for c in (chips or []))
    st.markdown(f"<div class='hero'>{ECG_SVG}<div class='hero-row'><div class='drop-wrap'>{DROP_SVG}</div><div>"
                f"<div class='eyebrow'><span class='live'></span>{escape(eyebrow)}</div>"
                f"<div class='hero-title'>{escape(title)}</div><div class='hero-sub'>{escape(subtitle)}</div></div></div>"
                f"<div class='chips'>{chips_html}</div></div>", unsafe_allow_html=True)


def brand():
    st.markdown(f"<div class='brand'><div class='bm'>{DROP_SVG}</div><div><b>Blood Donor Matcher</b>"
                f"<span>Every drop counts</span></div></div>", unsafe_allow_html=True)


def ticker(items):
    """Scrolling strip of recent events. items: list of short strings (already plain text)."""
    if not items:
        return
    one = "".join(f"<span class='ti'>{escape(t)}</span>" for t in items)
    st.markdown(f"<div class='ticker'><div class='tr'>{one}{one}</div></div>", unsafe_allow_html=True)


def section(title, sub=""):
    html = f"<div class='section'>{escape(title)}</div>"
    if sub:
        html += f"<div class='section-sub'>{escape(sub)}</div>"
    st.markdown(html, unsafe_allow_html=True)


def pill(text, kind="gray"):
    return f"<span class='pill {kind}'>{escape(str(text))}</span>"


def bg_badge(group):
    return f"<span class='bg-badge'>{escape(str(group))}</span>"


def tier_pill(name):
    """Hero level badge, e.g. 🥇 Gold."""
    import insights
    for _, n, icon, col in insights.TIERS:
        if n == name:
            return f"<span class='tier' style='--tc:{col}'>{icon} {escape(n)}</span>"
    return escape(str(name))


def stat_cards(items):
    """items: list of (label, value, color[, icon[, subtext]])"""
    out = ""
    for it in items:
        l, v, c = it[0], it[1], it[2]
        icon = it[3] if len(it) > 3 else ""
        sub = it[4] if len(it) > 4 else ""
        out += (f"<div class='stat' style='--c:{c}'><div class='ic'>{escape(icon)}</div>"
                f"<div class='n'>{escape(str(v))}</div><div class='l'>{escape(l)}</div>"
                f"{f'<div class=s>{escape(sub)}</div>' if sub else ''}</div>")
    st.markdown(f"<div class='stats'>{out}</div>", unsafe_allow_html=True)


def empty_state(icon, title, text=""):
    st.markdown(f"<div class='empty'><div class='ei'>{escape(icon)}</div><div class='et'>{escape(title)}</div>"
                f"<div>{escape(text)}</div></div>", unsafe_allow_html=True)


def alert_banner(text):
    st.markdown(f"<div class='alert-banner'><span style='font-size:1.3rem'>🚨</span>{escape(text)}</div>", unsafe_allow_html=True)


def glass(title, body_html="", icon=""):
    """A soft info panel. body_html must already be safe/escaped by the caller."""
    st.markdown(f"<div class='glass'><h4>{escape(icon)} {escape(title)}</h4>{body_html}</div>", unsafe_allow_html=True)


def request_card(req, urgency_pill_html):
    u = {"Within 24 hours": "Within24"}.get(req["urgency"], req["urgency"])
    units = req.get("units") or 1
    st.markdown(
        f"<div class='card u-{escape(str(u))}'><div class='t'>{bg_badge(req['blood_group'])} blood needed &nbsp;{urgency_pill_html}</div>"
        f"<div class='row'>🧑 <b>Patient:</b> {escape(str(req['patient']))}</div>"
        f"<div class='row'>🏥 <b>Hospital:</b> {escape(str(req['hospital']))}, {escape(str(req['city']).title())}</div>"
        f"<div class='row'>🩸 <b>Units needed:</b> {escape(str(units))}</div>"
        f"<div class='row'>📞 <b>Contact:</b> {escape(str(req['contact']))} {contact_links(req['contact'], '')}</div></div>",
        unsafe_allow_html=True)


def stepper(labels, current):
    """labels: list of step names; current: index of the active step (len(labels) = all done)."""
    html = ""
    for i, lab in enumerate(labels):
        cls = "done" if i < current else ("now" if i == current else "")
        dot = "✓" if i < current else str(i + 1)
        html += f"<div class='step {cls}'><div class='dot'>{dot}</div>{escape(lab)}</div>"
    st.markdown(f"<div class='steps'>{html}</div>", unsafe_allow_html=True)


# ---------- smart-feature widgets ----------
def sla_ring(s):
    """s = insights.sla(...) dict."""
    cls = {"ok": "", "warn": "warn", "late": "late"}[s["state"]]
    st.markdown(f"<div class='sla'><div class='ring {cls}' style='--p:{s['pct']}'><span>{s['pct']}%</span></div>"
                f"<div><b>{escape(s['label'])}</b><small>of the response window used</small></div></div>", unsafe_allow_html=True)


def copilot_panel(tips):
    html = "".join(f"<div class='tip {escape(t['level'])}'><div class='ti'>{escape(t['icon'])}</div><div>{escape(t['text'])}</div></div>"
                   for t in tips)
    st.markdown(html, unsafe_allow_html=True)


def forecast_cards(items):
    """items: list of (value, caption)."""
    html = "".join(f"<div class='k'><b>{escape(str(v))}</b><span>{escape(c)}</span></div>" for v, c in items)
    st.markdown(f"<div class='fc'>{html}</div>", unsafe_allow_html=True)


def meter(pct, label=""):
    pct = max(0, min(100, int(pct)))
    st.markdown(f"<div style='font-weight:700;font-size:.85rem'>{escape(label)}</div>"
                f"<div class='meter'><i style='width:{pct}%'></i></div>", unsafe_allow_html=True)


def blood_bags(sd):
    """Blood-bag inventory. sd = matcher.supply_demand() DataFrame."""
    out = ""
    for i, r in enumerate(sd.itertuples()):
        need = int(r.needed_units)
        target = max(6, need * 3)
        fill = max(0.04, min(1.0, r.compatible_donors / target))
        y = 78 - 56 * fill
        tone = {"OK": "#2E9E5B", "Low": "#F08A24", "Shortage": "#FF4D63"}[r.supply]
        cid = f"bc{i}"
        svg = (f"<svg viewBox='0 0 64 92'><defs><clipPath id='{cid}'><path d='M14 22h36a6 6 0 0 1 6 6v46a8 8 0 0 1-8 8H16a8 8 0 0 1-8-8V28a6 6 0 0 1 6-6Z'/></clipPath>"
               f"<linearGradient id='{cid}g' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#FF6B6B'/><stop offset='1' stop-color='#9B1428'/></linearGradient></defs>"
               f"<path d='M26 4h12v10H26z' fill='{tone}' opacity='.8'/><rect x='29' y='12' width='6' height='10' fill='{tone}' opacity='.8'/>"
               f"<g clip-path='url(#{cid})'><rect x='0' y='0' width='64' height='92' fill='rgba(150,150,160,.16)'/>"
               f"<g class='wave'><path d='M-64 {y:.1f} q16 -7 32 0 t32 0 t32 0 t32 0 t32 0 V92 H-64Z' fill='url(#{cid}g)'/></g></g>"
               f"<path d='M14 22h36a6 6 0 0 1 6 6v46a8 8 0 0 1-8 8H16a8 8 0 0 1-8-8V28a6 6 0 0 1 6-6Z' fill='none' stroke='{tone}' stroke-width='2.5'/></svg>")
        out += (f"<div class='bag {escape(r.supply)}' style='animation-delay:{i * 0.05:.2f}s'>{svg}<div class='g'>{escape(r.blood_group)}</div>"
                f"<div class='m'>{int(r.compatible_donors)} can give</div>"
                f"<div class='m'>{'needs ' + str(need) + ' unit(s)' if need else 'no open need'}</div>"
                f"<div style='margin-top:5px'>{pill(r.supply, {'OK': 'green', 'Low': 'orange', 'Shortage': 'red'}[r.supply])}</div></div>")
    st.markdown(f"<div class='bags'>{out}</div>", unsafe_allow_html=True)


def podium(top):
    """top: list of up to 3 dicts: name, donations, tier, blood_group (already public-safe)."""
    if not top:
        return
    order = [1, 0, 2] if len(top) >= 3 else list(range(len(top)))
    heights = {0: 190, 1: 160, 2: 140}
    cols = {0: "#D4A017", 1: "#8E9BAA", 2: "#B9770E"}
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    html = ""
    for pos in order:
        if pos >= len(top):
            continue
        d = top[pos]
        html += (f"<div class='pod' style='--tc:{cols[pos]};--h:{heights[pos]}px'><div class='av'>{medals[pos]}</div>"
                 f"<div class='bl'><div class='nm'>{escape(d['name'])}</div><div class='ds'>{escape(d['blood_group'])} · {escape(d['tier'])}</div>"
                 f"<div class='big'>{int(d['donations'])}</div><div class='ds'>donation(s) · {int(d['lives'])} lives</div></div></div>")
    st.markdown(f"<div class='podium'>{html}</div>", unsafe_allow_html=True)


def leaderboard_row(rank, name, group_html, tier_html, value):
    st.markdown(f"<div class='lb'><div class='rk'>{rank}</div><div class='nm'>{escape(name)} {group_html}</div>"
                f"<div>{tier_html}</div><div style='font-weight:800'>{escape(str(value))}</div></div>", unsafe_allow_html=True)


def radar(donors=None, reqs=None, halo_km=None, picks=None, dark=False, height=430):
    """Live map. donors: DataFrame (id, name, blood_group, city, last_donation, available).
    reqs: DataFrame of requests (id, blood_group, city, urgency, radius). picks: donor ids to highlight."""
    try:
        import pydeck as pdk
        import cities, matcher
    except ImportError:
        st.caption("Map needs the pydeck package (pip install pydeck).")
        return

    def spot(city, key):                       # a stable little offset so donors in one town do not stack
        co = cities.get_coords(city)
        if not co:
            return None
        k = int(key)
        return co[0] + (((k * 37) % 100) / 100 - .5) * .10, co[1] + (((k * 53) % 100) / 100 - .5) * .10

    drows, picks = [], set(picks or [])
    if donors is not None and not donors.empty:
        for r in donors.itertuples():
            p = spot(r.city, r.id)
            if not p:
                continue
            avail = 1 if pd.isna(getattr(r, "available", 1)) else int(getattr(r, "available", 1))
            if int(r.id) in picks:
                col = [215, 38, 61, 235]
            elif avail == 0:
                col = [150, 150, 160, 170]
            elif matcher.is_eligible(getattr(r, "last_donation", None)):
                col = [46, 158, 91, 225]
            else:
                col = [240, 138, 36, 225]
            drows.append({"lat": p[0], "lon": p[1], "label": f"{str(r.name).title()} · {r.blood_group}", "color": col})
    rrows, halos = [], []
    if reqs is not None and not reqs.empty:
        for r in reqs.itertuples():
            co = cities.get_coords(r.city)
            if not co:
                continue
            rrows.append({"lat": co[0], "lon": co[1], "label": f"Request #{r.id} · {r.blood_group} · {r.urgency}"})
            km = halo_km or (int(r.radius) if pd.notna(getattr(r, "radius", None)) else 50)
            halos.append({"lat": co[0], "lon": co[1], "r": km * 1000})
    pts = [(d["lat"], d["lon"]) for d in drows] + [(d["lat"], d["lon"]) for d in rrows]
    if not pts:
        st.caption("Nothing to show on the map yet.")
        return
    lat = sum(p[0] for p in pts) / len(pts)
    lon = sum(p[1] for p in pts) / len(pts)
    if halo_km:
        zoom = 8 - math.log2(max(halo_km, 5) / 50)
    else:
        span = max(max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts), .25)
        zoom = max(5.2, min(9, 8.2 - math.log2(span / 1.2)))
    layers = []
    if halos:
        layers.append(pdk.Layer("ScatterplotLayer", pd.DataFrame(halos), get_position="[lon, lat]", get_radius="r",
                                get_fill_color=[215, 38, 61, 26], get_line_color=[215, 38, 61, 170], stroked=True,
                                line_width_min_pixels=2, pickable=False))
    if drows:
        layers.append(pdk.Layer("ScatterplotLayer", pd.DataFrame(drows), get_position="[lon, lat]", get_fill_color="color",
                                get_radius=1500, radius_min_pixels=5, radius_max_pixels=13, stroked=True,
                                get_line_color=[255, 255, 255, 230], line_width_min_pixels=1.5, pickable=True))
    if rrows:
        layers.append(pdk.Layer("ScatterplotLayer", pd.DataFrame(rrows), get_position="[lon, lat]", get_fill_color=[255, 255, 255, 255],
                                get_radius=3200, radius_min_pixels=10, radius_max_pixels=20, stroked=True,
                                get_line_color=[215, 38, 61, 255], line_width_min_pixels=5, pickable=True))
    deck = pdk.Deck(layers=layers, initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom, pitch=0),
                    map_style="dark" if dark else "light", tooltip={"text": "{label}"})
    for kw in ({"height": height, "width": "stretch"}, {"height": height, "use_container_width": True}, {"use_container_width": True}, {}):
        try:
            st.pydeck_chart(deck, **kw)
            break
        except TypeError:
            continue
    st.markdown("<span class='pill green'>● eligible</span><span class='pill orange'>● 90-day break</span>"
                "<span class='pill gray'>● paused</span><span class='pill red'>◎ request</span>", unsafe_allow_html=True)


# ---------- contact links (call / WhatsApp). No API needed. ----------
def contact_links(phone, message=""):
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    if len(digits) < 10:
        return ""
    cc = os.getenv("COUNTRY_CODE", "91").strip()
    html = f"<a class='cl' href='tel:+{cc}{digits[-10:]}'>📞 Call</a>"
    if message is not None:
        html += (f"<a class='cl wa' target='_blank' rel='noopener' "
                 f"href='https://wa.me/{cc}{digits[-10:]}?text={quote(message)}'>💬 WhatsApp</a>")
    return html


# ---------- time ----------
def time_ago(ts):
    try:
        t = datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ""
    s = int((datetime.now() - t).total_seconds())
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{s // 60} min ago"
    if s < 86400:
        return f"{s // 3600} h ago"
    return f"{s // 86400} d ago"


def feed(df):
    """Recent activity list (sidebar / tools)."""
    icons = {"request": "🆘", "email": "📧", "reply": "💬", "confirm": "✅", "donor": "🧑", "bank": "🏥"}
    if df is None or df.empty:
        st.caption("No activity yet.")
        return
    html = "".join(f"<div class='feed'><small>{icons.get(r.kind, '•')} {escape(time_ago(r.ts))}</small>{escape(r.message)}</div>"
                   for r in df.itertuples())
    st.markdown(html, unsafe_allow_html=True)


# ---------- blood compatibility matrix ----------
def compat_matrix(compat, highlight=None):
    """Rows = donor group, columns = recipient group. Green = can donate."""
    groups = list(compat.keys())
    head = "".join(f"<th>{g}</th>" for g in groups)
    rows = ""
    for dg in groups:
        cells = ""
        for rg in groups:
            ok = dg in compat[rg]
            cls = ("y" if ok else "") + (" sel" if highlight in (dg, rg) and ok else "")
            cells += f"<td class='{cls.strip()}'>{'✓' if ok else ''}</td>"
        rows += f"<tr><th>{dg}</th>{cells}</tr>"
    st.markdown(f"<div class='mx-wrap'><table class='mx'><tr><th>Donor ↓ / Patient →</th>{head}</tr>{rows}</table></div>",
                unsafe_allow_html=True)


# ---------- bold, readable tables (replaces st.dataframe) ----------
_STATUS_KIND = {"Pending": "orange", "Notified": "blue", "Partial": "blue", "Fulfilled": "green", "Cancelled": "gray"}
_URGENCY_KIND = {"Critical": "red", "Within 24 hours": "orange", "Planned": "green"}
_SUPPLY_KIND = {"OK": "green", "Low": "orange", "Shortage": "red"}
_TITLE_COLS = {"city", "area", "name", "patient", "hospital"}
MAX_ROWS = 300


def _cell(col, v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return "<td>—</td>"
    if isinstance(v, float) and v == int(v):
        v = int(v)
    text = str(v)
    if col == "status":
        return f"<td>{pill(text, _STATUS_KIND.get(text, 'gray'))}</td>"
    if col == "urgency":
        return f"<td>{pill(text, _URGENCY_KIND.get(text, 'gray'))}</td>"
    if col == "supply":
        return f"<td>{pill(text, _SUPPLY_KIND.get(text, 'gray'))}</td>"
    if col == "tier":
        return f"<td>{tier_pill(text)}</td>"
    if col == "reliability":
        return (f"<td><div style='display:flex;align-items:center;gap:8px;min-width:96px'><div class='meter' style='flex:1;margin:0'>"
                f"<i style='width:{max(0, min(100, int(float(text))))}%'></i></div><b>{escape(text)}</b></div></td>")
    if col == "eligibility":
        kind = "green" if text == "Eligible" else ("gray" if text == "Paused" else "orange")
        return f"<td>{pill(text, kind)}</td>"
    if col == "blood_group":
        return f"<td class='bgc'>{escape(text)}</td>"
    if col in _TITLE_COLS and text.islower():
        text = text.title()
    return f"<td>{escape(text)}</td>"


def table(df, empty="Nothing to show yet."):
    """Bold, striped HTML table that also works in dark mode."""
    if df is None or df.empty:
        st.caption(empty)
        return
    shown = df.head(MAX_ROWS)
    head = "".join(f"<th>{escape(str(c).replace('_', ' ').title())}</th>" for c in shown.columns)
    body = "".join("<tr>" + "".join(_cell(c, v) for c, v in zip(shown.columns, row)) + "</tr>"
                   for row in shown.itertuples(index=False, name=None))
    st.markdown(f"<div class='tbl-wrap'><table class='tbl'><thead><tr>{head}</tr></thead>"
                f"<tbody>{body}</tbody></table></div>", unsafe_allow_html=True)
    if len(df) > MAX_ROWS:
        st.caption(f"Showing the first {MAX_ROWS} of {len(df)} rows. Use the filters or download the CSV.")


# ---------- charts (Altair, themed for light / dark) ----------
def style_chart(chart, dark=False, height=260):
    text = "#F1E4E7" if dark else "#4A2A2E"
    grid = "#3A2A31" if dark else "#F0DEDC"
    return (chart.properties(height=height, background="transparent")
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor=text, titleColor=text, gridColor=grid, domainColor=grid,
                            labelFontWeight=600, titleFontWeight=700, labelFont="Plus Jakarta Sans", titleFont="Plus Jakarta Sans")
            .configure_legend(labelColor=text, titleColor=text)
            .configure_title(color=text))
