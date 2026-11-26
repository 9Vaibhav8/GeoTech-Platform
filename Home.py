"""
Home.py — Landing page for the CE 402 Geotechnical Engineering Platform
IIT Mandi — Hostel Foundation Design
"""

import streamlit as st
from utils.constants import init_session_state

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CE 402 Geotech Platform | IIT Mandi",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()

# ── Module registry (single source of truth) ──────────────────────────────────
# Update `page` to match the filenames in your /pages folder.
MODULES = [
    {
        "id": "P1",
        "title": "Soil profile",
        "page": "pages/1_Soil_Profile_Editor.py",
        "does": "Define the borehole stratigraphy: layer depths, IS 1498 "
                "classification, unit weights, strength parameters and water table.",
        "in": "Borehole log",
        "out": "Shared soil profile",
    },
    {
        "id": "P2",
        "title": "SPT corrections and strength",
        "page": "pages/2_SPT_Corrections.py",
        "does": "Apply IS 2131 / Skempton corrections to field N values, then "
                "correlate N₆₀ to φ′ and cᵤ.",
        "in": "Field SPT N values",
        "out": "N₆₀, φ′, cᵤ",
    },
    {
        "id": "P3",
        "title": "Bearing capacity",
        "page": "pages/3_Bearing_Capacity.py",
        "does": "Compute net ultimate and net safe bearing capacity "
                "(IS 6403, Meyerhof, Hansen) and size isolated or strip footings.",
        "in": "Strength parameters, target FoS",
        "out": "Footing size, applied load",
    },
    {
        "id": "P4",
        "title": "Stress increase",
        "page": "pages/4_Stress_Increase.py",
        "does": "Find vertical stress increments Δσᵥ with depth using Boussinesq "
                "point, strip or rectangular solutions, and plot isobars.",
        "in": "Footing geometry, load",
        "out": "Δσᵥ profile",
    },
    {
        "id": "P5",
        "title": "Settlement",
        "page": "pages/5_Settlement_Analysis.py",
        "does": "Estimate immediate (IS 8009) and consolidation settlement, "
                "and plot settlement against time using Terzaghi 1-D theory.",
        "in": "Δσᵥ profile, clay parameters",
        "out": "Total and time-dependent settlement",
    },
]

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Source+Serif+4:wght@500;600;700&display=swap');

:root {
  --topsoil: #7a5c3e;
  --sand:    #cdb68a;
  --clay:    #6f8587;
  --water:   #2f6f9f;
  --line:    rgba(128, 128, 128, 0.28);
  --soft:    rgba(128, 128, 128, 0.07);
}

html, body, [class*="css"], .stMarkdown, p, li, label {
  font-family: 'IBM Plex Sans', system-ui, sans-serif;
}
h1, h2, h3, .ce-display {
  font-family: 'Source Serif 4', Georgia, serif !important;
  letter-spacing: -0.01em;
}

.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1100px; }

/* ── Hero: a borehole log is the first thing you see ── */
.ce-hero {
  display: grid;
  grid-template-columns: 1fr 230px;
  gap: 2.5rem;
  align-items: stretch;
  padding-bottom: 1.8rem;
  border-bottom: 1px solid var(--line);
  margin-bottom: 1.8rem;
}
.ce-hero h1 {
  font-size: 2.6rem; line-height: 1.1; margin: 0 0 .6rem 0; padding: 0;
}
.ce-hero .ce-lede {
  font-size: 1.05rem; line-height: 1.6; max-width: 58ch; opacity: .85; margin: 0;
}
.ce-hero .ce-meta { margin-top: 1rem; font-size: .88rem; opacity: .65; }

.ce-log {
  display: flex; flex-direction: column;
  border: 1px solid var(--line); border-radius: 6px; overflow: hidden;
  min-height: 190px; font-size: .78rem; color: #fff;
}
.ce-log div { display: flex; align-items: center; justify-content: space-between; padding: 0 .8rem; }
.ce-log .l1 { flex: 2; background: var(--topsoil); }
.ce-log .wt { flex: 0 0 4px; background: var(--water); padding: 0; }
.ce-log .l2 { flex: 3; background: var(--sand); color: #2b2418; }
.ce-log .l3 { flex: 4; background: var(--clay); }
.ce-log-cap { font-size: .75rem; opacity: .6; margin-top: .4rem; }

/* ── Module cards ── */
.ce-card-head { display: flex; align-items: baseline; gap: .7rem; margin-bottom: .35rem; }
.ce-id {
  font-weight: 600; font-size: .85rem; padding: .1rem .5rem;
  border-radius: 4px; background: var(--water); color: #fff;
}
.ce-card-head h3 { margin: 0; padding: 0; font-size: 1.15rem; }
.ce-card-body { font-size: .93rem; line-height: 1.55; opacity: .88; margin-bottom: .7rem; }
.ce-io { font-size: .82rem; opacity: .7; border-top: 1px dashed var(--line); padding-top: .5rem; }
.ce-io b { font-weight: 600; }

/* Bordered containers: quieter, tighter */
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 8px; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] { border-right: 1px solid var(--line); }

/* ── Focus + motion ── */
a:focus-visible, button:focus-visible { outline: 2px solid var(--water); outline-offset: 2px; }

@media (max-width: 800px) {
  .ce-hero { grid-template-columns: 1fr; gap: 1.2rem; }
  .ce-hero h1 { font-size: 2rem; }
  .ce-log { min-height: 120px; }
}
</style>
""",
    unsafe_allow_html=True,
)


def safe_page_link(path: str, label: str, primary: bool = False):
    """Link to a page, degrading gracefully if the file name doesn't match."""
    try:
        st.page_link(path, label=label, icon="➡️", use_container_width=True)
    except Exception:
        st.caption(f"Page not found: `{path}`")


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏗️ CE 402 Platform")
    st.caption("IIT Mandi · Department of Civil Engineering")
    st.divider()
    st.markdown("**Modules**")
    for m in MODULES:
        safe_page_link(m["page"], f'{m["id"]}  {m["title"]}')
    st.divider()
    st.caption("Version 1.0.0 · Academic use only")

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="ce-hero">
  <div>
    <h1>Hostel foundation design, from borehole to settlement</h1>
    <p class="ce-lede">
      Five linked modules for the IIT Mandi hostel foundation. They share one
      soil profile, so whatever you set in one step carries into the next.
    </p>
    <div class="ce-meta">CE 402 Geotechnical Engineering · IIT Mandi</div>
  </div>
  <div>
    <div class="ce-log" role="img" aria-label="Sample borehole log with three soil layers and a water table">
      <div class="l1"><span>Fill</span></div>
      <div class="wt"></div>
      <div class="l2"><span>Sand</span></div>
      <div class="l3"><span>Clay</span></div>
    </div>
    <div class="ce-log-cap">Default 3-layer profile</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Primary action ────────────────────────────────────────────────────────────
cta_col, hint_col = st.columns([1, 2], vertical_alignment="center")
with cta_col:
    safe_page_link(MODULES[0]["page"], "Start with the soil profile")
with hint_col:
    st.caption("Every other module reads from the profile, so begin here.")

st.write("")

# ── Modules, in workflow order ────────────────────────────────────────────────
st.markdown("### Workflow")
st.caption("Work through the modules in order. Each one passes its results to the next.")

# P1–P2 on the first row, P3–P4 on the second, P5 on the third:
# two-column rows keep line lengths readable and cards equal in width.
for row_start in range(0, len(MODULES), 2):
    cols = st.columns(2, gap="medium")
    for col, m in zip(cols, MODULES[row_start:row_start + 2]):
        with col:
            with st.container(border=True):
                st.markdown(
                    f"""
<div class="ce-card-head"><span class="ce-id">{m["id"]}</span><h3>{m["title"]}</h3></div>
<div class="ce-card-body">{m["does"]}</div>
<div class="ce-io"><b>Needs:</b> {m["in"]}<br><b>Gives:</b> {m["out"]}</div>
""",
                    unsafe_allow_html=True,
                )
                safe_page_link(m["page"], f'Open {m["id"]}')

st.write("")

# ── Help, tucked away until needed ────────────────────────────────────────────
with st.expander("How the data flows between modules"):
    st.markdown(
        """
1. **P1** stores the soil layers and water-table depth.
2. **P2** corrects the SPT N values entered in P1 and writes N₆₀, φ′ and cᵤ back to the shared profile.
3. **P3** uses those strength parameters, plus your embedment depth and target factor of safety, to size the footing.
4. **P4** takes the footing size and load from P3 and returns the stress increase with depth.
5. **P5** combines that stress increase with the clay consolidation parameters to give total and time-dependent settlement.
"""
    )

st.divider()
st.caption(
    "CE 402 Geotechnical Engineering · IIT Mandi · "
    "Built for academic foundation-design assignments."
)
