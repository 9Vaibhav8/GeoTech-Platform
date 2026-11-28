"""GeoForge landing page — site-independent geotechnical analysis workspace."""

from pathlib import Path

import streamlit as st
from utils.constants import init_session_state
from utils.demo_data import BOREHOLES, DIRECT_SHEAR, UU, ASSUMPTIONS, load_demo, reset_generic


st.set_page_config(
    page_title="GeoForge | Geotechnical Analysis & Foundation Design",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_session_state()


ROOT = Path(__file__).resolve().parent

# Paths match the project's existing Streamlit pages directory.
MODULES = (
    {
        "id": "P1",
        "title": "Soil Profile",
        "icon": "🗺️",
        "page": "pages/1_🗺️_Soil_Profile.py",
        "description": "Build a layered soil profile with groundwater levels, unit weights, strength, stiffness and consolidation properties.",
        "output": "Editable soil data and a depth-based profile diagram.",
        "reference": "Soil classification · IS 1498",
    },
    {
        "id": "P2",
        "title": "Soil Parameters",
        "icon": "⚙️",
        "page": "pages/2_⚙️_Parameters.py",
        "description": "Correct field SPT N values for overburden and dilatancy where applicable. Fit drained strength parameters from direct shear tests and estimate undrained strength from UU data.",
        "output": "Corrected N values, c′, φ′, cu and fitted strength envelope.",
        "reference": "IS 2131:1981 · Mohr–Coulomb · UU triaxial",
    },
    {
        "id": "P3",
        "title": "Bearing Capacity",
        "icon": "🏗️",
        "page": "pages/3_🏗️_Bearing_Capacity.py",
        "description": "Estimate net ultimate and net safe bearing capacity for shallow footings, including general and local shear, groundwater effects and applicable eccentric loading checks.",
        "output": "Capacity factors, footing sizes and bearing-pressure checks.",
        "reference": "IS 6403:1981",
    },
    {
        "id": "P4",
        "title": "Stress Distribution",
        "icon": "📊",
        "page": "pages/4_📊_Stress_Increase.py",
        "description": "Calculate vertical stress increments below rectangular loaded areas using Boussinesq centre and corner solutions, superposition and the approximate 2:1 method.",
        "output": "Stress–depth curves, influence depth and numerical tables.",
        "reference": "Boussinesq · 2:1 method",
    },
    {
        "id": "P5",
        "title": "Settlement Analysis",
        "icon": "📐",
        "page": "pages/5_📐_Settlement.py",
        "description": "Estimate granular-soil settlement and one-dimensional clay consolidation. Review time-dependent settlement and isolated-footing settlement criteria across a column grid.",
        "output": "Settlement components, time curves and differential settlement checks.",
        "reference": "Schmertmann (1978) · Terzaghi · IS 8009 / IS 1904",
    },
)


def module_link(module, label=None):
    """Use native Streamlit navigation to retain the current session state."""
    if not (ROOT / module["page"]).is_file():
        st.caption("Module file not found. Check the pages directory.")
        return
    if hasattr(st, "page_link"):
        st.page_link(
            module["page"],
            label=label or f"Open {module['id']} — {module['title']}",
            icon=module["icon"],
        )
    elif hasattr(st, "switch_page"):
        if st.button(label or f"Open {module['id']}", key=f"home_open_{module['id']}_{'hero' if label else 'card'}"):
            st.switch_page(module["page"])
    else:
        st.caption(f"Open {module['id']} from the sidebar navigation.")


def module_card(module):
    # Native containers respect the user's light/dark theme and mobile layout.
    try:
        card = st.container(border=True)
    except TypeError:  # Older Streamlit versions do not support border.
        card = st.container()
    with card:
        st.caption(f"{module['id']}  /  ANALYSIS MODULE")
        st.subheader(f"{module['icon']} {module['title']}")
        st.markdown(module["description"])
        st.markdown(f"**Outputs:** {module['output']}")
        st.caption(module["reference"])
        module_link(module)


with st.sidebar:
    st.markdown("## 🏗️ GeoForge")
    st.caption("Geotechnical analysis workspace")
    st.markdown("---")
    st.markdown("**Analysis scope**")
    st.caption("Shallow foundations · Layered soils · SI units")
    st.markdown("**Standards basis**")
    st.caption("Indian Standards and classical geotechnical methods")
    st.markdown("---")
    st.caption("For learning and preliminary analysis. Verify inputs, assumptions and applicable standards before design use.")


st.caption("GEOTECHNICAL ENGINEERING  /  SHALLOW FOUNDATIONS")
st.title("GeoForge")
st.markdown("### Geotechnical Analysis & Foundation Design")
st.write(
    "Analyze soil conditions, assess shallow foundation capacity and estimate "
    "settlement in one integrated workspace. Configure the soil profile, "
    "groundwater, footing geometry and loads for your own site."
)

st.warning(
    "Before running an analysis, replace any illustrative soil properties, "
    "groundwater levels and load values with verified project data. "
    "Starter values are not site investigation results."
)
st.header("Choose your workspace")
active = st.session_state.get("demo_project")
if active:
    st.info(f"Demo active: {active['active']} · load multiplier {active['factor']:.2f}. Loaded profiles are editable; reloading discards edits.")
left, right = st.columns(2)
with left:
    st.subheader("Explore assignment demo")
    st.write("Optional CE 402 hostel example: three boreholes, SPT records, laboratory data and the column grid. The platform remains independent of this case.")
    bh = st.selectbox("Active borehole for P1–P4", list(BOREHOLES), key="home_demo_bh")
    group = st.number_input("Assignment group number", min_value=0, value=0, step=1, key="home_demo_group", help="Enter your group number; zero uses the unmodified loads.")
    shear = st.selectbox("BH-1 direct shear dataset", list(DIRECT_SHEAR), index=1, key="home_demo_shear")
    uu = st.selectbox("BH-1 UU dataset", list(UU), key="home_demo_uu")
    with st.expander("Source gaps and illustrative assumptions", expanded=False):
        for item in ASSUMPTIONS:
            st.markdown("- " + item)
        st.caption("Assignment pp. 1–6; all supplied field and lab data are hypothetical. All additional inputs are illustrative, not reported results.")
    accept = st.checkbox("I understand the assumptions and that loading replaces current analysis inputs.", key="home_demo_confirm")
    if st.button("Load / reload assignment demo", disabled=not accept, key="home_load_demo"):
        try:
            load_demo(st.session_state, bh, group, shear, uu)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
with right:
    st.subheader("New project")
    st.write("Start with an empty soil profile and enter your own borehole, soil and laboratory data.")
    reset_confirm = st.checkbox("Replace current analysis inputs", key="home_new_confirm")
    if st.button("Start new project", disabled=not reset_confirm, key="home_new"):
        reset_generic(st.session_state)
        st.rerun()
    module_link(MODULES[0], "Open soil profile")
if active:
    with st.expander("Current demo assumptions and source data"):
        for item in st.session_state.get("demo_assumptions", []):
            st.markdown("- " + item)
        st.table([{"Borehole": k, "RL (m)": v['rl'], "Measured WT (m bgl)": v['measured'], "Design WT (m bgl)": v['design'], "Lowest WT (m bgl)": v['lowest']} for k,v in BOREHOLES.items()])
        st.caption("P5 uses three saved profile snapshots; after editing P1, save the revised active profile in P5. To switch the active borehole without keeping edits, reload the demo from this page.")

st.markdown("---")
st.header("Analysis modules")
st.caption("Choose a tool to begin or follow the recommended sequence from P1 to P5.")

for start in range(0, len(MODULES), 2):
    left, right = st.columns(2)
    with left:
        module_card(MODULES[start])
    with right:
        if start + 1 < len(MODULES):
            module_card(MODULES[start + 1])
        else:
            try:
                guide = st.container(border=True)
            except TypeError:
                guide = st.container()
            with guide:
                st.caption("WORKSPACE  /  GETTING STARTED")
                st.subheader("📋 Input checklist")
                st.markdown(
                    "- Borehole logs and layer boundaries\n"
                    "- Measured and design groundwater levels\n"
                    "- Field and laboratory soil test results\n"
                    "- Footing dimensions, depth and service loads\n"
                    "- Design criteria and drainage assumptions"
                )
                st.caption("Confirm units and the load/pressure basis before comparing results.")

st.markdown("---")
st.header("Recommended workflow")
with st.expander("How to work across the five modules", expanded=False):
    st.markdown(
        "1. **Define site conditions (P1).** Enter the actual number of soil layers, "
        "their boundaries and the measured and design water tables.\n"
        "2. **Determine soil parameters (P2).** Enter test data, review the calculations "
        "and explicitly apply accepted results to the appropriate soil layers.\n"
        "3. **Assess foundation capacity (P3).** Select the footing geometry, "
        "founding depth, load conditions and factor of safety.\n"
        "4. **Review stress distribution (P4).** Confirm footing dimensions and net "
        "load or pressure, then inspect stress variation below the footing.\n"
        "5. **Evaluate settlement (P5).** Confirm the selected profile, dimensions, "
        "loads, stiffness, consolidation properties and drainage conditions before "
        "reviewing settlement results."
    )
    st.caption(
        "Modules share soil information through the current session. P2 provides "
        "explicit transfer controls; verify foundation inputs in each module. "
        "P5 calculates its own stress increments rather than importing P4's plot."
    )

with st.expander("Methods, applicability and limitations"):
    st.markdown(
        "GeoForge supports preliminary shallow-foundation analysis with selected "
        "Indian Standard methods and classical soil mechanics models. The methods "
        "use simplifying assumptions and are not a substitute for site-specific "
        "geotechnical design. Users outside India should check their local codes.\n\n"
        "The platform is not a complete structural design, deep-foundation, "
        "raft or coupled soil–structure interaction solver. Confirm the adequacy "
        "of the investigation depth, soil parameters and model assumptions, and "
        "have engineering decisions independently reviewed by a qualified professional."
    )

st.markdown("---")
st.caption("GeoForge · Geotechnical analysis toolkit · SI units: m, kN, kPa, mm and seconds/years as indicated")
