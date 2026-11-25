"""
pages/3_🏗️_Bearing_Capacity.py
IS 6403:1981 — Bearing Capacity of Shallow Foundations
IIT Mandi CE 402 Geotechnical Engineering Platform
All units strictly SI: m, kN, kPa, kN/m³, deg.
"""

import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.constants import init_session_state
from utils.bearing_capacity import (
    net_ultimate_bearing_capacity,
    effective_overburden_at_depth,
    required_footing_size,
)

# ---------------------------------------------------------------------------
# Page config & session state
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="P3 · Bearing Capacity — IS 6403:1981",
    page_icon="🏗️",
    layout="wide",
)
init_session_state()

st.title("🏗️ P3 — Bearing Capacity (IS 6403:1981)")
st.caption("Shallow foundation design strictly per IS 6403:1981 | SI units: m, kN, kPa, kN/m³, deg")


# ---------------------------------------------------------------------------
# Helper: detect layer containing a given depth
# ---------------------------------------------------------------------------
def get_layer_at_depth(depth_m: float):
    """Return the layer dict that contains depth_m (m bgl)."""
    layers = st.session_state.get("layers", [])
    for lyr in layers:
        if lyr["depth_top"] <= depth_m <= lyr["depth_bot"]:
            return lyr
    if layers:
        return layers[-1]
    return None


# ---------------------------------------------------------------------------
# SIDEBAR — Section A: Footing, Shear Mode, Eccentricity & WT Parameters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Footing Parameters")

    Df = st.number_input(
        "Founding depth Df (m)",
        min_value=0.0,
        max_value=15.0,
        value=1.5,
        step=0.1,
        help="Depth of footing base below existing ground level (m bgl).",
    )

    shape_opts = ["Square", "Rectangular", "Circular", "Strip"]
    footing_shape_label = st.selectbox("Footing shape", shape_opts, index=0)
    footing_shape = footing_shape_label.lower()

    if footing_shape == "rectangular":
        col_b, col_l = st.columns(2)
        with col_b:
            B_input = st.number_input("Width B (m)", min_value=0.2, max_value=25.0, value=1.5, step=0.1)
        with col_l:
            L_input = st.number_input("Length L (m)", min_value=0.2, max_value=50.0, value=2.5, step=0.1)
        B_sidebar, L_sidebar = B_input, L_input
    elif footing_shape == "strip":
        B_sidebar = st.number_input("Strip width B (m)", min_value=0.2, max_value=15.0, value=1.5, step=0.1)
        L_sidebar = 1e6
    elif footing_shape == "circular":
        B_sidebar = st.number_input("Diameter D (m)", min_value=0.2, max_value=25.0, value=2.0, step=0.1)
        L_sidebar = B_sidebar
    else:
        B_sidebar = st.number_input("Width B (m)", min_value=0.2, max_value=25.0, value=2.0, step=0.1)
        L_sidebar = B_sidebar

    shear_mode_label = st.radio(
        "Shear failure mode (IS 6403 Cl. 5.2.1 & 5.2.2)",
        ["Auto (IS 6403 Cl. 5.2.1)", "General Shear", "Local Shear"],
        index=0,
        help=(
            "Auto: φ ≤ 28° → Local; φ ≥ 36° or φ = 0° → General; "
            "28° < φ < 36° → linear interpolation."
        ),
    )
    failure_mode = shear_mode_label

    alpha_deg = st.number_input(
        "Load inclination α (deg)",
        min_value=0.0,
        max_value=89.0,
        value=0.0,
        step=1.0,
        help="IS 6403:1981 Cl. 5.1.2.3 — Angle of resultant load from vertical (deg).",
    )

    FOS = st.number_input(
        "Factor of Safety on q_nu (FOS)",
        min_value=1.0,
        max_value=10.0,
        value=3.0,
        step=0.5,
        help="IS 6403:1981 Cl. 6 — Factor of safety applied to net ultimate bearing capacity q_nu.",
    )

    st.divider()
    st.subheader("📐 Eccentric Loading (Cl. 5.1.2.1)")
    ecc_mode = st.radio(
        "Eccentricity input mode",
        ["Concentric (e = 0)", "Direct (ex, ey)", "From Moments (Mx, My / P)"],
        index=0,
    )

    ex_input = 0.0
    ey_input = 0.0
    P_ecc_sidebar = 1000.0
    Mx_sidebar = 0.0
    My_sidebar = 0.0

    if ecc_mode == "Direct (ex, ey)":
        if footing_shape == "strip":
            ex_input = st.number_input("Eccentricity ex along B (m)", min_value=0.0, value=0.0, step=0.01)
            ey_input = 0.0
        elif footing_shape == "circular":
            ex_input = st.number_input("Eccentricity ex (m)", min_value=0.0, value=0.0, step=0.01)
            ey_input = st.number_input("Eccentricity ey (m)", min_value=0.0, value=0.0, step=0.01)
            st.caption(f"Resultant e = √(ex² + ey²) = **{math.hypot(ex_input, ey_input):.3f} m**")
        else:
            ex_input = st.number_input("Eccentricity ex along B (m)", min_value=0.0, value=0.0, step=0.01)
            ey_input = st.number_input("Eccentricity ey along L (m)", min_value=0.0, value=0.0, step=0.01)
    elif ecc_mode == "From Moments (Mx, My / P)":
        p_label = "Line load P (kN/m)" if footing_shape == "strip" else "Column load P (kN)"
        P_ecc_sidebar = st.number_input(p_label, min_value=1.0, value=1000.0, step=10.0)
        if footing_shape == "strip":
            my_label = "Moment My about strip axis (kN·m/m)"
            My_sidebar = st.number_input(my_label, min_value=0.0, value=0.0, step=1.0)
            ex_input = My_sidebar / P_ecc_sidebar
            ey_input = 0.0
            st.caption(f"Computed ex = My / P = **{ex_input:.4f} m**")
        else:
            Mx_sidebar = st.number_input("Moment Mx about X-axis → ey (kN·m)", min_value=0.0, value=0.0, step=1.0)
            My_sidebar = st.number_input("Moment My about Y-axis → ex (kN·m)", min_value=0.0, value=0.0, step=1.0)
            ex_input = My_sidebar / P_ecc_sidebar
            ey_input = Mx_sidebar / P_ecc_sidebar
            st.caption(f"Computed ex = **{ex_input:.4f} m**, ey = **{ey_input:.4f} m**")

    st.divider()
    wt_bgl_session = float(st.session_state.get("wt_design_bgl", 1.0))
    wt_bgl = st.number_input(
        "Design WT depth (m bgl)",
        min_value=0.0,
        max_value=50.0,
        value=wt_bgl_session,
        step=0.1,
        help="Design groundwater table depth below ground level (m bgl).",
    )


# ---------------------------------------------------------------------------
# SECTION B — Soil Parameters at Founding Level
# ---------------------------------------------------------------------------
st.header("🪨 Section B — Soil Parameters at Founding Level")

layers_state = st.session_state.get("layers", [])
detected_layer = get_layer_at_depth(Df)

if detected_layer is None:
    st.error("⚠️ No soil layers defined in session state. Please define layers in P1 — Soil Profile first.")
    st.stop()

with st.expander(f"📋 Detected founding layer at Df = {Df:.2f} m bgl", expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Symbol", detected_layer.get("symbol", "—"))
    col2.metric("c′ (kPa)", f"{detected_layer.get('c_prime', 0.0):.2f}")
    col3.metric("φ′ (deg)", f"{detected_layer.get('phi_prime', 0.0):.2f}")
    col4.metric("cu (kPa)", f"{detected_layer.get('cu', 0.0):.2f}")

    col5, col6, col7 = st.columns(3)
    col5.metric("γ_moist (kN/m³)", f"{detected_layer.get('gamma_moist', 18.0):.2f}")
    col6.metric("γ_sat (kN/m³)", f"{detected_layer.get('gamma_sat', 20.0):.2f}")
    col7.metric("Undrained (φ=0)?", "Yes" if detected_layer.get("is_undrained", False) else "No")

override = st.checkbox("🔧 Override founding layer soil parameters manually")

if override:
    st.markdown("**Manual founding-layer soil parameters:**")
    oc1, oc2, oc3 = st.columns(3)
    with oc1:
        c_prime = st.number_input(
            "c′ (kPa)", min_value=0.0, max_value=500.0,
            value=float(detected_layer.get("c_prime", 0.0)), step=0.5,
        )
        phi_prime = st.number_input(
            "φ′ (deg)", min_value=0.0, max_value=50.0,
            value=float(detected_layer.get("phi_prime", 30.0)), step=0.5,
        )
    with oc2:
        cu_val = st.number_input(
            "cu (kPa)", min_value=0.0, max_value=500.0,
            value=float(detected_layer.get("cu", 0.0)), step=0.5,
        )
        is_undrained = st.checkbox(
            "Use undrained (φ = 0) analysis",
            value=bool(detected_layer.get("is_undrained", False)),
        )
    with oc3:
        gamma_moist = st.number_input(
            "γ_moist (kN/m³)", min_value=10.0, max_value=25.0,
            value=float(detected_layer.get("gamma_moist", 18.0)), step=0.1,
        )
        gamma_sat = st.number_input(
            "γ_sat (kN/m³)", min_value=10.0, max_value=25.0,
            value=float(detected_layer.get("gamma_sat", 20.0)), step=0.1,
        )
    use_layered_overburden = st.checkbox(
        "Integrate overlying layers from P1 for q_eff = σ′v0(Df)",
        value=False,
        help="Uncheck when testing a uniform single-layer soil profile with manual γ_moist / γ_sat.",
    )
else:
    c_prime = float(detected_layer.get("c_prime", 0.0))
    phi_prime = float(detected_layer.get("phi_prime", 30.0))
    cu_val = float(detected_layer.get("cu", 0.0))
    is_undrained = bool(detected_layer.get("is_undrained", False))
    gamma_moist = float(detected_layer.get("gamma_moist", 18.0))
    gamma_sat = float(detected_layer.get("gamma_sat", 20.0))
    use_layered_overburden = True

layers_for_qeff = layers_state if use_layered_overburden else None

q_eff_display = effective_overburden_at_depth(
    Df=Df,
    wt_bgl=wt_bgl,
    layers=layers_for_qeff,
    gamma_moist=gamma_moist,
    gamma_sat=gamma_sat,
)
q_source_note = (
    "integrated across all overlying layers in P1 (moist above WT, γ_sat − γ_w below WT)"
    if use_layered_overburden
    else "computed from manual single-layer γ_moist / γ_sat"
)
st.info(
    f"**Effective overburden stress at founding level:** `q_eff = σ′v0(Df) = {q_eff_display:.2f} kPa`  \n"
    f"_Source: IS 6403:1981 Cl. 5.1.2.4 ({q_source_note}; design WT = {wt_bgl:.2f} m bgl)._"
)


# ---------------------------------------------------------------------------
# SECTION C — Bearing Capacity Results & Every Factor
# ---------------------------------------------------------------------------
st.header("📊 Section C — Bearing Capacity Results (IS 6403:1981)")

result = net_ultimate_bearing_capacity(
    c_prime=c_prime,
    phi_prime_deg=phi_prime,
    gamma_moist=gamma_moist,
    gamma_sat=gamma_sat,
    Df=Df,
    B=B_sidebar,
    L=L_sidebar,
    wt_bgl=wt_bgl,
    footing_shape=footing_shape,
    failure_mode=failure_mode,
    alpha_deg=alpha_deg,
    is_undrained=is_undrained,
    cu=cu_val,
    ex=ex_input,
    ey=ey_input,
    FOS=FOS,
    layers=layers_for_qeff,
)

# Guard invalid eccentricity
if result["A_eff"] <= 0.0:
    st.error(
        f"⚠️ Eccentricity is outside the footing base (`B_eff = {result['B_eff']:.3f} m`, "
        f"`L_eff = {result['L_eff']:.3f} m`). Reduce eccentricity or increase footing dimensions."
    )
    st.stop()

q_nu = result["q_nu"]
q_ns = result["q_ns"]
q_s_gross = result["q_s_gross"]
q_f = result["qf"]

c_res1, c_res2, c_res3, c_res4, c_res5 = st.columns(5)
c_res1.metric("q_nu — Net Ultimate", f"{q_nu:.2f} kPa")
c_res2.metric("q_ns — Net Safe", f"{q_ns:.2f} kPa")
c_res3.metric("q_s_gross — Gross Safe", f"{q_s_gross:.2f} kPa")
c_res4.metric("q_f — Gross Ultimate", f"{q_f:.2f} kPa")
c_res5.metric("Resolved Shear Mode", result["resolved_mode"])

# Kern status banner when eccentric
if result["is_eccentric"]:
    if footing_shape == "circular":
        kern_txt = (
            f"{result['kern_expression']}: e = {result['kern_value']:.4f} m "
            f"vs D/8 = {result['kern_limit']:.4f} m"
        )
    else:
        kern_txt = (
            f"{result['kern_expression']}: {result['kern_value']:.4f} "
            f"vs {result['kern_limit']:.4f} (1/6)"
        )
    if result["within_kern"]:
        st.success(f"✅ **Kern Check PASS** — Full base in compression ({kern_txt}).")
    else:
        st.warning(
            f"⚠️ **Kern Check FAIL (partial uplift)** — Resultant outside middle kern ({kern_txt}). "
            "Meyerhof effective area B′ × L′ is applied per IS 6403:1981 Cl. 5.1.2.1."
        )

# Every factor table with SI unit & IS 6403 clause
with st.expander("🔍 Complete Factors & Equation Breakdown (IS 6403:1981)", expanded=True):
    L_disp = "∞ (strip)" if footing_shape == "strip" else f"{result['L']:.3f}"
    L_eff_disp = "∞ (strip)" if footing_shape == "strip" else f"{result['L_eff']:.3f}"
    A_eff_disp = f"{result['B_eff']:.3f} (per m)" if footing_shape == "strip" else f"{result['A_eff']:.3f}"

    factors_rows = [
        ("Cohesion used", "c", f"{result['c_used']:.3f}", "kPa", "Cl. 5.2.1 / 5.2.2"),
        ("Friction angle used", "φ", f"{result['phi_used']:.3f}", "deg", "Cl. 5.2.1 / 5.2.2"),
        ("Nominal width / diameter", "B", f"{result['B']:.3f}", "m", "Cl. 5.1.2"),
        ("Nominal length", "L", L_disp, "m", "Cl. 5.1.2"),
        ("Eccentricity along B", "e_x", f"{result['ex']:.4f}", "m", "Cl. 5.1.2.1"),
        ("Eccentricity along L", "e_y", f"{result['ey']:.4f}", "m", "Cl. 5.1.2.1"),
        ("Effective width", "B_eff", f"{result['B_eff']:.3f}", "m", "Cl. 5.1.2.1 (Meyerhof)"),
        ("Effective length", "L_eff", L_eff_disp, "m", "Cl. 5.1.2.1 (Meyerhof)"),
        ("Effective area", "A_eff", A_eff_disp, "m²" if footing_shape != "strip" else "m²/m", "Cl. 5.1.2.1"),
        ("Bearing capacity factor (cohesion)", "Nc", f"{result['Nc']:.4f}", "—", "Cl. 5.1.2, Table 1"),
        ("Bearing capacity factor (overburden)", "Nq", f"{result['Nq']:.4f}", "—", "Cl. 5.1.2, Table 1"),
        ("Bearing capacity factor (unit weight)", "Nγ", f"{result['Ngamma']:.4f}", "—", "Cl. 5.1.2, Table 1"),
        ("Shape factor (c term)", "sc", f"{result['sc']:.4f}", "—", "Cl. 5.1.2.1, Table 2"),
        ("Shape factor (q term)", "sq", f"{result['sq']:.4f}", "—", "Cl. 5.1.2.1, Table 2"),
        ("Shape factor (γ term)", "sγ", f"{result['sgamma']:.4f}", "—", "Cl. 5.1.2.1, Table 2"),
        ("Depth factor (c term)", "dc", f"{result['dc']:.4f}", "—", "Cl. 5.1.2.2"),
        ("Depth factor (q term)", "dq", f"{result['dq']:.4f}", "—", "Cl. 5.1.2.2"),
        ("Depth factor (γ term)", "dγ", f"{result['dgamma']:.4f}", "—", "Cl. 5.1.2.2"),
        ("Inclination factor (c term)", "ic", f"{result['ic']:.4f}", "—", "Cl. 5.1.2.3"),
        ("Inclination factor (q term)", "iq", f"{result['iq']:.4f}", "—", "Cl. 5.1.2.3"),
        ("Inclination factor (γ term)", "iγ", f"{result['igamma']:.4f}", "—", "Cl. 5.1.2.3"),
        ("Water table factor", "W′", f"{result['W_prime']:.4f}", "—", "Cl. 5.1.2.4"),
        ("Effective overburden at Df", "q_eff", f"{result['q_eff']:.3f}", "kPa", "Cl. 5.1.2.4"),
        ("Moist unit weight (Nγ term)", "γ_moist", f"{result['gamma_moist']:.3f}", "kN/m³", "Cl. 5.1.2 Eq. 1 & Cl. 5.1.2.4"),
        ("Cohesion term: c·Nc·sc·dc·ic", "Term 1", f"{result['c_term']:.3f}", "kPa", "Cl. 5.1.2 Eq. 1"),
        ("Overburden term: q_eff·(Nq−1)·sq·dq·iq", "Term 2", f"{result['q_term']:.3f}", "kPa", "Cl. 5.1.2 Eq. 1"),
        ("Self-weight term: 0.5·B_eff·γ·Nγ·sγ·dγ·iγ·W′", "Term 3", f"{result['gamma_term']:.3f}", "kPa", "Cl. 5.1.2 Eq. 1"),
        ("Net ultimate bearing capacity", "q_nu", f"{q_nu:.3f}", "kPa", "Cl. 5.1.2 Eq. 1"),
        ("Net safe bearing capacity (q_nu / FOS)", "q_ns", f"{q_ns:.3f}", "kPa", "Cl. 6"),
        ("Gross safe bearing capacity (q_ns + q_eff)", "q_s_gross", f"{q_s_gross:.3f}", "kPa", "Cl. 6"),
        ("Gross ultimate bearing capacity (q_nu + q_eff)", "q_f", f"{q_f:.3f}", "kPa", "Cl. 5.1.2"),
    ]
    df_factors = pd.DataFrame(
        factors_rows,
        columns=["Parameter", "Symbol", "Value", "Unit", "IS 6403:1981 Clause"],
    )
    st.dataframe(df_factors, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# SECTION D — Concentric Footing Sizing for Column Types
# ---------------------------------------------------------------------------
st.header("📐 Section D — Concentric Footing Sizing (IS 6403:1981 Cl. 6)")
st.markdown(
    "> Enter unfactored or amplified service column loads $P$ (kN). "
    "Sizing iterates on square footings so that applied net pressure $P/B^2 \\le q_{ns} = q_{nu}/\\text{FOS}$."
)

sizing_col1, sizing_col2, sizing_col3 = st.columns(3)
with sizing_col1:
    P_corner = st.number_input("Corner column P (kN)", min_value=10.0, max_value=20000.0, value=669.5, step=10.0)
with sizing_col2:
    P_edge = st.number_input("Edge column P (kN)", min_value=10.0, max_value=20000.0, value=1030.0, step=10.0)
with sizing_col3:
    P_interior = st.number_input("Interior column P (kN)", min_value=10.0, max_value=20000.0, value=1493.5, step=10.0)

sizing_rows = []
for col_type, P_val in [("Corner", P_corner), ("Edge", P_edge), ("Interior", P_interior)]:
    sz = required_footing_size(
        P_kN=P_val,
        c_prime=c_prime,
        phi_prime_deg=phi_prime,
        gamma_moist=gamma_moist,
        gamma_sat=gamma_sat,
        Df=Df,
        wt_bgl=wt_bgl,
        FOS=FOS,
        footing_shape="square",
        failure_mode=failure_mode,
        alpha_deg=alpha_deg,
        is_undrained=is_undrained,
        cu=cu_val,
        layers=layers_for_qeff,
    )
    actual_fos = sz["actual_FOS"]
    fos_ok = actual_fos >= FOS
    sizing_rows.append({
        "Column Type": col_type,
        "Load P (kN)": f"{P_val:.1f}",
        "Required B (m)": f"{sz['B']:.2f}",
        "q_nu (kPa)": f"{sz['qnu']:.2f}",
        "q_ns (kPa)": f"{sz['qns']:.2f}",
        "q_s_gross (kPa)": f"{sz['q_s_gross']:.2f}",
        "Actual FOS": f"{actual_fos:.2f}",
        "Status": "✅ OK" if fos_ok else "❌ NG",
    })

sizing_df = pd.DataFrame(sizing_rows)


def color_status(val):
    if "✅" in str(val):
        return "background-color: #d4edda; color: #155724;"
    if "❌" in str(val):
        return "background-color: #f8d7da; color: #721c24;"
    return ""


styled_df = sizing_df.style.map(color_status, subset=["Status"])
st.dataframe(styled_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# SECTION E — Water Table Effect on q_nu (IS 6403:1981 Cl. 5.1.2.4)
# ---------------------------------------------------------------------------
st.header("💧 Section E — Water Table Effect on q_nu (IS 6403:1981 Cl. 5.1.2.4)")

W_prime_current = result["W_prime"]
st.metric("Current water table factor W′", f"{W_prime_current:.3f}")
if W_prime_current == 0.5:
    st.info("WT at or above footing base (`wt ≤ Df`) → `W′ = 0.500`.")
elif W_prime_current == 1.0:
    st.info("WT at or deeper than `Df + B_eff` → `W′ = 1.000` (no Nγ water-table reduction).")
else:
    st.warning(
        f"WT between `Df` and `Df + B_eff` → `W′ = {W_prime_current:.3f}` "
        "(linearly interpolated per Cl. 5.1.2.4)."
    )

wt_range = np.linspace(0.0, Df + max(result["B_eff"], 1.0) * 2.0, 60)
qnu_values = []
for wt_i in wt_range:
    res_i = net_ultimate_bearing_capacity(
        c_prime=c_prime,
        phi_prime_deg=phi_prime,
        gamma_moist=gamma_moist,
        gamma_sat=gamma_sat,
        Df=Df,
        B=B_sidebar,
        L=L_sidebar,
        wt_bgl=float(wt_i),
        footing_shape=footing_shape,
        failure_mode=failure_mode,
        alpha_deg=alpha_deg,
        is_undrained=is_undrained,
        cu=cu_val,
        ex=ex_input,
        ey=ey_input,
        FOS=FOS,
        layers=layers_for_qeff,
    )
    qnu_values.append(res_i["q_nu"])

fig_wt = go.Figure()
fig_wt.add_trace(go.Scatter(
    x=wt_range,
    y=qnu_values,
    mode="lines+markers",
    name="q_nu (kPa)",
    line=dict(color="#1f4e79", width=2),
    marker=dict(size=4),
))
fig_wt.add_vline(
    x=wt_bgl,
    line_dash="dash",
    line_color="blue",
    annotation_text=f"Design WT = {wt_bgl:.2f} m",
    annotation_position="top right",
)
fig_wt.add_vline(
    x=Df,
    line_dash="dot",
    line_color="orange",
    annotation_text=f"Base Df = {Df:.2f} m",
    annotation_position="top left",
)
fig_wt.update_layout(
    title="Net Ultimate Bearing Capacity q_nu vs Water Table Depth (IS 6403:1981 Cl. 5.1.2.4)",
    xaxis_title="Water Table Depth (m bgl)",
    yaxis_title="q_nu (kPa)",
    template="plotly_white",
    height=420,
    legend=dict(orientation="h", y=-0.2),
)
st.plotly_chart(fig_wt, use_container_width=True)


# ---------------------------------------------------------------------------
# SECTION F — Eccentricity, Kern Check & Applied Load Verification
# ---------------------------------------------------------------------------
st.header("📏 Section F — Eccentricity & Applied Load Check (IS 6403:1981 Cl. 5.1.2.1)")

ef_col1, ef_col2 = st.columns(2)
with ef_col1:
    load_unit = "kN/m" if footing_shape == "strip" else "kN"
    default_P_check = P_ecc_sidebar if ecc_mode == "From Moments (Mx, My / P)" else 1030.0
    P_check = st.number_input(
        f"Applied vertical load P ({load_unit}) for bearing check",
        min_value=1.0,
        value=float(default_P_check),
        step=10.0,
    )
    L_nom_str = "∞" if footing_shape == "strip" else f"{result['L']:.3f} m"
    L_eff_str = "∞" if footing_shape == "strip" else f"{result['L_eff']:.3f} m"
    st.markdown(
        f"- **Footing shape**: `{footing_shape_label}`  \n"
        f"- **Nominal dimensions**: `B = {result['B']:.3f} m`, `L = {L_nom_str}`  \n"
        f"- **Eccentricities**: `e_x = {result['ex']:.4f} m`, `e_y = {result['ey']:.4f} m`"
    )
    if footing_shape == "circular":
        e_rad = math.hypot(result["ex"], result["ey"])
        st.markdown(f"- **Radial eccentricity**: `e = √(e_x² + e_y²) = {e_rad:.4f} m`")

with ef_col2:
    q_applied = P_check / result["A_eff"]
    st.markdown(
        f"- **Effective width `B_eff`**: `{result['B_eff']:.3f} m`  \n"
        f"- **Effective length `L_eff`**: `{L_eff_str}`  \n"
        f"- **Effective area `A_eff`**: `{result['A_eff']:.3f} {'m²/m' if footing_shape == 'strip' else 'm²'}`  \n"
        f"- **Kern condition**: `{result['kern_expression']}` → "
        f"`{result['kern_value']:.4f}` vs `{result['kern_limit']:.4f}` "
        f"({'✅ PASS' if result['within_kern'] else '⚠️ FAIL'})"
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Applied q (P / A_eff)", f"{q_applied:.2f} kPa")
    m2.metric("Net safe q_ns", f"{q_ns:.2f} kPa")
    m3.metric("Gross safe q_s_gross", f"{q_s_gross:.2f} kPa")

    if q_applied <= q_ns:
        st.success(f"✅ **Bearing PASS (Net)** — `q_applied = {q_applied:.2f} kPa ≤ q_ns = {q_ns:.2f} kPa`.")
    else:
        st.error(f"❌ **Bearing FAIL (Net)** — `q_applied = {q_applied:.2f} kPa > q_ns = {q_ns:.2f} kPa`.")


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "IS 6403:1981 — Code of Practice for Determination of Bearing Capacity of Shallow Foundations. "
    "IIT Mandi CE 402 · All computations in SI units (m, kN, kPa, kN/m³, deg)."
)
