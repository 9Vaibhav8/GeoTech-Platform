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

# ── Initialize shared session state ───────────────────────────────────────────
init_session_state()

# ── Sidebar branding ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏗️ CE 402 Platform")
    st.markdown("**IIT Mandi**  \nDepartment of Civil Engineering")
    st.markdown("---")
    st.caption("Version 1.0.0")
    st.caption("Academic use only")
    st.markdown("---")
    st.info(
        "👈 Use the sidebar links above to navigate between analysis modules."
    )

# ── Main header ───────────────────────────────────────────────────────────────
st.title("🏗️ CE 402 Geotechnical Engineering Platform")
st.subheader("IIT Mandi — Hostel Foundation Design")
st.markdown(
    """
This interactive platform supports the geotechnical analysis and design workflow
for the **IIT Mandi hostel foundation** project. Each module corresponds to a
distinct analytical step — from soil profiling through to final settlement
predictions — and all modules share a common soil-layer data model so that
results flow seamlessly from one stage to the next.
"""
)

st.markdown("---")

# ── Module summary cards ──────────────────────────────────────────────────────
st.markdown("### 📦 Platform Modules")

col1, col2, col3 = st.columns(3)

with col1:
    st.success(
        "**P1 · Soil Profile Editor**\n\n"
        "Define borehole stratigraphy: layer boundaries, IS 1498 soil "
        "classifications, unit weights, strength parameters, and water-table "
        "depth. All downstream modules read from this profile."
    )
    st.success(
        "**P2 · SPT Corrections & Strength Fitting**\n\n"
        "Apply IS 2131 / Skempton corrections to field SPT N values. "
        "Correlate corrected N₆₀ to friction angle (φ′) and undrained "
        "shear strength (cᵤ); view the fitted Mohr-Coulomb envelope."
    )

with col2:
    st.info(
        "**P3 · Bearing Capacity Design**\n\n"
        "Compute net ultimate and net safe bearing capacity using "
        "IS 6403 / Meyerhof / Hansen formulations. Size isolated and "
        "strip footings for a user-specified factor of safety."
    )
    st.info(
        "**P4 · Stress Increase beneath Footing**\n\n"
        "Calculate vertical stress increments (Δσᵥ) at any depth using "
        "Boussinesq point-load, strip, or rectangular-load solutions. "
        "Plot isobar diagrams interactively."
    )

with col3:
    st.warning(
        "**P5 · Settlement Analysis**\n\n"
        "Estimate immediate elastic settlement (IS 8009) and primary "
        "consolidation settlement for clay layers. Compute degree of "
        "consolidation vs. time using Terzaghi 1-D theory and plot "
        "settlement–time curves."
    )

st.markdown("---")

# ── Quick-start workflow ──────────────────────────────────────────────────────
st.markdown("### 🚀 Quick Start — Recommended Workflow")

steps = [
    ("P1 — Define the Soil Profile",
     "Open **P1 · Soil Profile Editor** and confirm or edit the default "
     "3-layer stratigraphy. Set the water-table depth. All other modules "
     "depend on this data."),
    ("P2 — SPT Corrections & Strength Parameters",
     "Open **P2** to review automatic IS 2131 corrections to the field "
     "SPT N values entered in P1. Adjust correlation coefficients if needed; "
     "the corrected N₆₀ and fitted φ′ / cᵤ are written back to the shared "
     "soil profile."),
    ("P3 — Bearing Capacity Design",
     "Open **P3** to select a footing type, embedment depth, and target "
     "factor of safety. The module computes bearing capacity factors and "
     "returns the required footing dimensions."),
    ("P4 — Stress Increase Computation",
     "Open **P4**, specify the footing geometry and applied load from P3, "
     "and inspect the vertical stress distribution with depth. Results feed "
     "directly into the settlement calculation in P5."),
    ("P5 — Settlement Analysis",
     "Open **P5** to combine the stress increments from P4 with the "
     "consolidation parameters of each clay layer and obtain total and "
     "time-dependent settlements."),
]

for i, (title, body) in enumerate(steps, start=1):
    with st.expander(f"Step {i} · {title}", expanded=(i == 1)):
        st.markdown(body)

st.markdown("---")
st.caption(
    "CE 402 Geotechnical Engineering · IIT Mandi · "
    "Platform developed for academic foundation-design assignments."
)
