"""
Home.py — Landing page for the Geotechnical Analysis Platform
"""

import re
from pathlib import Path

import streamlit as st
from utils.constants import init_session_state

st.set_page_config(
    page_title="Geotechnical Analysis Platform",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_session_state()

# ── Module registry ───────────────────────────────────────────────────────────
# Update `page` to match the filenames in your /pages folder.
MODULES = [
    {
        "id": "P1", "title": "Soil Profile Editor",
        "page": "pages/1_Soil_Profile_Editor.py",
        "does": "Define borehole stratigraphy: layer depths, IS 1498 classification, "
                "unit weights, strength parameters and water table.",
        "tags": ["IS 1498", "Water table"],
        "in": "Borehole log", "out": "Shared soil profile",
    },
    {
        "id": "P2", "title": "SPT Corrections & Strength",
        "page": "pages/2_SPT_Corrections.py",
        "does": "Correct field SPT N values to N₆₀ and correlate to friction angle φ′ "
                "and undrained strength cᵤ.",
        "tags": ["IS 2131", "Skempton", "Mohr–Coulomb"],
        "in": "Field N values", "out": "N₆₀, φ′, cᵤ",
    },
    {
        "id": "P3", "title": "Bearing Capacity",
        "page": "pages/3_Bearing_Capacity.py",
        "does": "Net ultimate and net safe bearing capacity, with isolated and strip "
                "footings sized to a target factor of safety.",
        "tags": ["IS 6403", "Meyerhof", "Hansen"],
        "in": "φ′, cᵤ, target FoS", "out": "Footing size, load",
    },
    {
        "id": "P4", "title": "Stress Increase",
        "page": "pages/4_Stress_Increase.py",
        "does": "Vertical stress increment Δσᵥ with depth beneath the footing, "
                "with interactive isobar diagrams.",
        "tags": ["Boussinesq", "Strip", "Rectangular"],
        "in": "Footing geometry, load", "out": "Δσᵥ profile",
    },
    {
        "id": "P5", "title": "Settlement Analysis",
        "page": "pages/5_Settlement_Analysis.py",
        "does": "Immediate and primary consolidation settlement, and settlement–time "
                "curves from Terzaghi 1-D theory.",
        "tags": ["IS 8009", "Terzaghi 1-D"],
        "in": "Δσᵥ, clay parameters", "out": "Total and time-dependent settlement",
    },
]

for i, m in enumerate(MODULES, start=1):
    matches = list(Path("pages").glob(f"{i}_*.py"))

    if len(matches) == 1:
        m["page"] = matches[0].as_posix()
    else:
        st.error(f"Cannot uniquely locate module P{i}")


def page_url(path: str) -> str:
    """Streamlit URL slug for a file in /pages (number prefix is dropped)."""
    stem = re.sub(r"^\d+[_\- ]*", "", Path(path).stem)
    return "/" + stem


# ── Styling ───────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600&family=Sora:wght@500;600;700&display=swap');

:root{
  --ink:#0d1b2a; --ink2:#15293d; --paper:#f5f6f8; --card:#ffffff;
  --line:#e0e5eb; --text:#1b2733; --muted:#5a6b7b;
  --water:#1f7ab8; --water-lt:#e6f1f9; --ochre:#b7862f;
}

/* strip Streamlit chrome so the page behaves like a website */
header[data-testid="stHeader"], footer, #MainMenu, [data-testid="stToolbar"],
[data-testid="stDecoration"] { display:none !important; }
.stApp { background: var(--paper); color: var(--text); }
.block-container { padding:0 !important; max-width:100% !important; }
[data-testid="stVerticalBlock"] { gap:0 !important; }
[data-testid="stMarkdownContainer"] { color: var(--text); }

.ce, .ce * { box-sizing:border-box; font-family:'Public Sans',system-ui,sans-serif; }
.ce h1,.ce h2,.ce h3,.ce .brand-name { font-family:'Sora',system-ui,sans-serif; letter-spacing:-0.015em; margin:0; padding:0; }
.ce a { text-decoration:none; }
.ce a:focus-visible { outline:2px solid var(--water); outline-offset:3px; border-radius:4px; }
.wrap { max-width:1140px; margin:0 auto; padding:0 28px; }

/* top bar */
.topbar { background:#fff; border-bottom:1px solid var(--line); }
.topbar .wrap { display:flex; align-items:center; justify-content:space-between; height:64px; }
.brand { display:flex; align-items:center; gap:12px; color:var(--ink); }
.brand-mark { width:32px; height:32px; border-radius:7px; overflow:hidden; display:flex; flex-direction:column; }
.brand-mark i { flex:1; display:block; }
.brand-name { font-size:1.02rem; font-weight:600; color:var(--ink); }
.brand-sub { font-size:.74rem; color:var(--muted); display:block; font-family:'Public Sans',sans-serif; font-weight:400; letter-spacing:0; }
.topnav { display:flex; gap:4px; }
.topnav a { color:var(--muted); font-size:.88rem; font-weight:500; padding:8px 12px; border-radius:6px; }
.topnav a:hover { background:var(--paper); color:var(--ink); }

/* hero */
.hero { background:var(--ink); color:#fff; overflow:hidden; }
.hero .wrap { display:grid; grid-template-columns:1.05fr 1fr; gap:48px; align-items:center; padding-top:72px; padding-bottom:72px; }
.hero h1 { font-size:2.9rem; line-height:1.08; font-weight:700; color:#fff; }
.hero p { color:#b9c7d6; font-size:1.06rem; line-height:1.65; max-width:50ch; margin:20px 0 0 0; }
.actions { display:flex; gap:12px; margin-top:32px; flex-wrap:wrap; }
.btn { display:inline-block; font-weight:600; font-size:.95rem; padding:13px 22px; border-radius:7px; }
.btn-primary { background:#3a9be0; color:#06192a !important; }
.btn-primary:hover { background:#5ab0ee; }
.btn-ghost { border:1px solid #3b5368; color:#dbe6f0 !important; }
.btn-ghost:hover { border-color:#7d97ad; }
.hero-art { width:100%; height:auto; display:block; border-radius:10px; border:1px solid #243b52; }

/* standards band */
.band { background:#fff; border-bottom:1px solid var(--line); }
.band .wrap { display:flex; align-items:center; gap:28px; padding-top:20px; padding-bottom:20px; flex-wrap:wrap; }
.band-label { font-size:.85rem; color:var(--muted); }
.band-list { display:flex; gap:10px; flex-wrap:wrap; }
.chip { font-size:.85rem; font-weight:500; color:var(--ink2); background:var(--paper); border:1px solid var(--line); padding:6px 12px; border-radius:999px; }

/* sections */
.section { padding:64px 0 8px 0; }
.section h2 { font-size:1.75rem; font-weight:600; color:var(--ink); }
.section .lede { color:var(--muted); font-size:1rem; line-height:1.6; max-width:60ch; margin:10px 0 32px 0; }

/* module grid */
.grid { display:grid; grid-template-columns:repeat(3,1fr); gap:20px; }
.mod { display:flex; flex-direction:column; background:var(--card); border:1px solid var(--line); border-radius:12px; padding:24px; color:var(--text) !important; transition:border-color .15s, box-shadow .15s; }
.mod:hover { border-color:var(--water); box-shadow:0 6px 24px rgba(13,27,42,.08); }
.mod-top { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.mod-id { font-family:'Sora',sans-serif; font-weight:600; font-size:.82rem; color:var(--water); background:var(--water-lt); padding:4px 10px; border-radius:6px; }
.mod h3 { font-size:1.12rem; font-weight:600; color:var(--ink); margin-bottom:8px; }
.mod p { font-size:.92rem; line-height:1.6; color:var(--muted); margin:0 0 16px 0; }
.tags { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:18px; }
.tag { font-size:.76rem; color:var(--ink2); background:var(--paper); border:1px solid var(--line); padding:3px 9px; border-radius:5px; }
.io { margin-top:auto; border-top:1px solid var(--line); padding-top:14px; font-size:.84rem; color:var(--muted); display:grid; grid-template-columns:auto 1fr; gap:4px 12px; }
.io b { color:var(--ink2); font-weight:600; }
.open { margin-top:16px; font-weight:600; font-size:.9rem; color:var(--water); }

.mod-data { background:var(--ink); border-color:var(--ink); color:#fff !important; cursor:default; }
.mod-data:hover { border-color:var(--ink); box-shadow:none; }
.mod-data h3 { color:#fff; }
.mod-data p { color:#b9c7d6; }
.mod-data .mod-id { background:#223a52; color:#8ec9f5; }
.mini-strata { display:flex; flex-direction:column; border-radius:6px; overflow:hidden; margin-top:auto; }
.mini-strata i { display:block; height:14px; }

/* data flow */
.flow { display:flex; align-items:stretch; gap:0; background:#fff; border:1px solid var(--line); border-radius:12px; overflow:hidden; }
.flow div { flex:1; padding:18px 20px; font-size:.88rem; color:var(--muted); line-height:1.5; border-right:1px solid var(--line); }
.flow div:last-child { border-right:0; }
.flow b { display:block; color:var(--ink); font-family:'Sora',sans-serif; font-weight:600; font-size:.95rem; margin-bottom:4px; }

/* footer */
.foot { margin-top:72px; background:var(--ink); color:#9fb1c3; }
.foot .wrap { display:flex; justify-content:space-between; gap:24px; padding-top:28px; padding-bottom:28px; font-size:.85rem; flex-wrap:wrap; }
.foot b { color:#fff; font-family:'Sora',sans-serif; font-weight:600; }

@media (max-width:960px){
  .hero .wrap{ grid-template-columns:1fr; padding-top:48px; padding-bottom:48px; }
  .hero h1{ font-size:2.2rem; }
  .grid{ grid-template-columns:1fr 1fr; }
  .flow{ flex-direction:column; }
  .flow div{ border-right:0; border-bottom:1px solid var(--line); }
  .topnav{ display:none; }
}
@media (max-width:620px){
  .grid{ grid-template-columns:1fr; }
  .wrap{ padding:0 18px; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ── Hero illustration: footing, pressure bulbs, strata, water table ──────────
HERO_SVG = (
    '<svg class="hero-art" viewBox="0 0 520 380" xmlns="http://www.w3.org/2000/svg" role="img" '
    'aria-label="Cross-section of a footing on layered soil with stress isobars and a water table">'
    '<rect width="520" height="380" fill="#10263a"/>'
    '<rect x="0" y="110" width="520" height="60" fill="#6b5238"/>'
    '<rect x="0" y="170" width="520" height="80" fill="#b99b66"/>'
    '<rect x="0" y="250" width="520" height="130" fill="#5d7577"/>'
    '<line x1="0" y1="205" x2="520" y2="205" stroke="#5db7ff" stroke-width="2" stroke-dasharray="7 5"/>'
    '<path d="M 15 205 l 7 -10 l 7 10 z" fill="#5db7ff"/>'
    '<g fill="none" stroke="#ffffff" stroke-width="1.4" opacity=".85">'
    '<path d="M 215 110 A 45 70 0 0 0 305 110"/>'
    '<path d="M 185 110 A 75 130 0 0 0 335 110" stroke-dasharray="5 4"/>'
    '<path d="M 150 110 A 110 195 0 0 0 370 110" stroke-dasharray="2 4"/>'
    '</g>'
    '<rect x="205" y="92" width="100" height="18" rx="2" fill="#e8edf2"/>'
    '<rect x="245" y="40" width="20" height="52" fill="#c6d0da"/>'
    '<g stroke="#8ec9f5" stroke-width="2" fill="#8ec9f5">'
    '<line x1="255" y1="12" x2="255" y2="36"/><path d="M 247 30 L 255 40 L 263 30 z" stroke="none"/>'
    '</g>'
    '<g font-family="Public Sans, sans-serif" font-size="12" fill="#ffffff">'
    '<text x="16" y="146" opacity=".9">Fill</text>'
    '<text x="16" y="226" fill="#2b2418">Sand</text>'
    '<text x="16" y="276">Clay</text>'
    '<text x="44" y="200" fill="#9fd3ff" font-size="11">GWT</text>'
    '<text x="318" y="140" fill="#cfe3f3" font-size="11">0.5 q</text>'
    '<text x="340" y="190" fill="#cfe3f3" font-size="11">0.2 q</text>'
    '<text x="372" y="250" fill="#cfe3f3" font-size="11">0.1 q</text>'
    '<text x="272" y="24" fill="#8ec9f5" font-size="11">Q</text>'
    '</g></svg>'
)

nav_links = "".join(
    f'<a href="{page_url(m["page"])}" target="_self">{m["id"]}</a>' for m in MODULES
)

st.markdown(
    '<div class="ce">'
    '<div class="topbar"><div class="wrap">'
    '<a class="brand" href="/" target="_self">'
    '<span class="brand-mark"><i style="background:#6b5238"></i><i style="background:#b99b66"></i><i style="background:#5d7577"></i></span>'
    '<span class="brand-name">Geotechnical Analysis Platform<span class="brand-sub">Foundation design toolkit</span></span></a>'
    f'<nav class="topnav">{nav_links}</nav>'
    '</div></div>'
    '<div class="hero"><div class="wrap">'
    '<div>'
    '<h1>Foundation analysis, from borehole to settlement</h1>'
    '<p>Take a borehole log through SPT correction, bearing capacity, stress distribution and settlement. '
    'All five modules share one soil profile, so each result feeds the next.</p>'
    '<div class="actions">'
    f'<a class="btn btn-primary" href="{page_url(MODULES[0]["page"])}" target="_self">Start with the soil profile</a>'
    '<a class="btn btn-ghost" href="#modules" target="_self">See all modules</a>'
    '</div></div>'
    f'<div>{HERO_SVG}</div>'
    '</div></div>'
    '<div class="band"><div class="wrap">'
    '<span class="band-label">Design basis</span>'
    '<div class="band-list">'
    '<span class="chip">IS 1498 soil classification</span>'
    '<span class="chip">IS 2131 SPT</span>'
    '<span class="chip">IS 6403 bearing capacity</span>'
    '<span class="chip">IS 8009 settlement</span>'
    '<span class="chip">Terzaghi 1-D consolidation</span>'
    '</div></div></div>'
    '</div>',
    unsafe_allow_html=True,
)

# ── Modules ───────────────────────────────────────────────────────────────────
cards = []
for m in MODULES:
    tags = "".join(f'<span class="tag">{t}</span>' for t in m["tags"])
    cards.append(
        f'<a class="mod" href="{page_url(m["page"])}" target="_self">'
        f'<div class="mod-top"><span class="mod-id">{m["id"]}</span></div>'
        f'<h3>{m["title"]}</h3><p>{m["does"]}</p>'
        f'<div class="tags">{tags}</div>'
        f'<div class="io"><b>Needs</b><span>{m["in"]}</span><b>Gives</b><span>{m["out"]}</span></div>'
        '<span class="open">Open module</span></a>'
    )

cards.append(
    '<div class="mod mod-data">'
    '<div class="mod-top"><span class="mod-id">Shared</span></div>'
    '<h3>One soil profile</h3>'
    '<p>Layers, strength parameters and the water table live in a single data model. '
    'Edit them in P1 or P2 and every later module picks up the change.</p>'
    '<div class="mini-strata"><i style="background:#6b5238"></i><i style="background:#b99b66"></i><i style="background:#5d7577"></i></div>'
    '</div>'
)

st.markdown(
    '<div class="ce" id="modules"><div class="wrap section">'
    '<h2>Analysis modules</h2>'
    '<p class="lede">Work through P1 to P5 in order. Each module lists what it needs and what it passes on.</p>'
    f'<div class="grid">{"".join(cards)}</div>'
    '</div></div>',
    unsafe_allow_html=True,
)

# ── Data flow ─────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="ce"><div class="wrap section">'
    '<h2>How results flow</h2>'
    '<p class="lede">Each step writes its output back so the next step starts from your latest numbers.</p>'
    '<div class="flow">'
    '<div><b>Profile</b>Layers, unit weights and water table are set in P1.</div>'
    '<div><b>Strength</b>P2 turns N values into N₆₀, φ′ and cᵤ for each layer.</div>'
    '<div><b>Footing</b>P3 sizes the footing and gives the applied load.</div>'
    '<div><b>Stress</b>P4 returns Δσᵥ with depth under that load.</div>'
    '<div><b>Settlement</b>P5 combines Δσᵥ with clay parameters over time.</div>'
    '</div></div></div>',
    unsafe_allow_html=True,
)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="ce"><div class="foot"><div class="wrap">'
    '<div><b>Geotechnical Analysis Platform</b><br>Soil profiling, bearing capacity and settlement</div>'
    '<div>Version 1.0.0<br>Academic use only</div>'
    '</div></div></div>',
    unsafe_allow_html=True,
)
