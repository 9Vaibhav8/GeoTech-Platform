"""
pages/3_🏗️_Bearing_Capacity.py
IS 6403:1981 — Bearing Capacity of Shallow Foundations
GeoForge — Geotechnical Analysis & Foundation Design
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.demo_data import demo_notice
from utils.constants import init_session_state
from utils.bearing_capacity import (
    net_ultimate_bearing_capacity,
    net_safe_bearing_capacity,
    effective_overburden_pressure,
    effective_area,
    required_footing_size,
    validate_profile,
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
demo_notice(st)

st.title("🏗️ P3 — Bearing Capacity (IS 6403:1981)")
st.caption("Shallow foundation design per IS 6403:1981 | GeoForge")

# ---------------------------------------------------------------------------
# Helper: detect layer containing a given depth
# ---------------------------------------------------------------------------

def get_layer_at_depth(depth_m: float, layers=None):
    """Use the layer immediately below the base at a shared boundary."""
    ordered = validate_profile(st.session_state.layers if layers is None else layers, depth_m)
    for lyr in ordered:
        if float(lyr["depth_top"]) <= depth_m < float(lyr["depth_bot"]):
            return lyr
    raise ValueError("Founding depth is at or beyond the end of the known profile. Enter soil below the footing base in P1.")


def section_error(exc):
    st.error(f"Cannot calculate: {exc}")


def net_pressure(input_pressure, q_eff, load_is_net):
    """Use the same effective-surcharge convention as the calculation utility."""
    return input_pressure if load_is_net else input_pressure - q_eff


with st.sidebar:
    st.header("⚙️ Footing Parameters")
    Df = st.number_input(
        "Founding depth Df (m bgl)", min_value=0.0,
        value=float(st.session_state.foundation_depth), step=0.1,
        help="Uses the P1 preview depth as the initial value; edits update shared state.",
    )
    st.session_state.foundation_depth = Df
    footing_shape = st.selectbox("Footing shape", ["Square", "Rectangular", "Circular", "Strip"]).lower()
    if footing_shape == "rectangular":
        col_b, col_l = st.columns(2)
        with col_b:
            B_sidebar = st.number_input("Width B (m)", min_value=0.001, value=1.5, step=0.1, key="p3_rect_b")
        with col_l:
            L_sidebar = st.number_input("Length L (m)", min_value=0.001, value=2.0, step=0.1, key="p3_rect_l")
    elif footing_shape == "strip":
        B_sidebar = st.number_input("Width B (m)", min_value=0.001, value=1.0, step=0.1, key="p3_strip_b")
        L_sidebar = 1.0  # unit-length basis
    else:
        B_sidebar = st.number_input("Width / Diameter B (m)", min_value=0.001, value=2.5 if st.session_state.get("demo_project") else 1.5, step=0.1, key="p3_equal_b")
        L_sidebar = B_sidebar
    failure_mode = "general" if st.radio("Failure mode", ["General shear", "Local shear"]) == "General shear" else "local"
    alpha_deg = st.number_input("Load inclination α (°)", min_value=0.0, max_value=90.0, value=0.0, step=1.0)
    FOS = st.number_input("Factor of Safety (FOS)", min_value=1.0, value=3.0, step=0.5,
                          help="Applied to net ultimate capacity. Verify the required factor of safety for your project.")
    st.divider()
    wt_bgl = float(st.session_state.wt_design_bgl)
    if st.checkbox("Override P1 design water table for P3 only"):
        wt_bgl = st.number_input("Design WT depth (m bgl)", min_value=0.0, value=wt_bgl, step=0.1)
    else:
        st.metric("Design WT from P1 (m bgl)", f"{wt_bgl:.2f}")
    st.caption("Eccentricity inputs and results are in Section F.")

# ---------------------------------------------------------------------------
# SECTION B — Soil Parameters at Founding Level
# ---------------------------------------------------------------------------
st.header("🪨 Section B — Soil Parameters at Founding Level")

try:
    layers_profile = validate_profile(st.session_state.get("layers", []), Df)
    detected_layer = get_layer_at_depth(Df, layers_profile)
except ValueError as exc:
    section_error(exc)
    st.stop()

st.caption(f"Profile: {st.session_state.borehole_name}")
st.warning("Bearing capacity uses the selected founding-layer strength and layered surcharge. "
           "It does not model punching through a strong layer into weak soil below or verify settlement. "
           "Confirm the method is applicable to the actual profile before design use.")

with st.expander("📋 Detected layer at Df = {:.2f} m".format(Df), expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Symbol", detected_layer.get("symbol", "—"))
    col2.metric("c′ (kPa)", f"{detected_layer['c_prime']:.1f}")
    col3.metric("φ′ (°)", f"{detected_layer['phi_prime']:.1f}")
    col4.metric("cu (kPa)", f"{detected_layer['cu']:.1f}")

    col5, col6, col7 = st.columns(3)
    col5.metric("γ_moist (kN/m³)", f"{detected_layer['gamma_moist']:.1f}")
    col6.metric("γ_sat (kN/m³)", f"{detected_layer['gamma_sat']:.1f}")
    col7.metric("Is undrained?", "Yes" if detected_layer.get("is_undrained", False) else "No")

override = st.checkbox("🔧 Override soil parameters manually")

if override:
    st.markdown("**Manual founding-layer parameters only (overburden still uses P1):**")
    oc1, oc2, oc3 = st.columns(3)
    with oc1:
        c_prime = st.number_input("c′ (kPa)", min_value=0.0,
                                   value=float(detected_layer["c_prime"]), step=0.5)
        phi_prime = st.number_input("φ′ (°)", min_value=0.0, max_value=89.9,
                                     value=float(detected_layer["phi_prime"]), step=0.5)
    with oc2:
        cu_val = st.number_input("cu (kPa)", min_value=0.0,
                                  value=float(detected_layer["cu"]), step=0.5)
        is_undrained = st.checkbox("Use undrained (φ=0) analysis",
                                    value=bool(detected_layer.get("is_undrained", False)))
    with oc3:
        gamma_moist = st.number_input("γ_moist (kN/m³)", min_value=0.001,
                                       value=float(detected_layer["gamma_moist"]), step=0.1)
        gamma_sat = st.number_input("γ_sat (kN/m³)", min_value=0.001,
                                     value=float(detected_layer["gamma_sat"]), step=0.1)
else:
    c_prime      = float(detected_layer["c_prime"])
    phi_prime    = float(detected_layer["phi_prime"])
    cu_val       = float(detected_layer["cu"])
    is_undrained = bool(detected_layer.get("is_undrained", False))
    gamma_moist  = float(detected_layer["gamma_moist"])
    gamma_sat    = float(detected_layer["gamma_sat"])

# Manual override changes the base material only, not the soil above the base.
active_layers = layers_profile
try:
    q_eff_display, q_steps = effective_overburden_pressure(
        layers=active_layers, Df=Df, wt_bgl=wt_bgl,
        fallback_gamma_moist=gamma_moist, fallback_gamma_sat=gamma_sat,
    )
except ValueError as exc:
    section_error(exc)
    st.stop()
st.info(f"**Effective overburden q at founding level:** {q_eff_display:.2f} kPa  \n_" + " | ".join(q_steps) + "_")

# Shared calculation arguments, reused by all sections.
common = dict(c_prime=c_prime, phi_prime_deg=phi_prime,
              gamma_moist=gamma_moist, gamma_sat=gamma_sat, Df=Df,
              wt_bgl=wt_bgl, failure_mode=failure_mode, alpha_deg=alpha_deg,
              is_undrained=is_undrained, cu=cu_val, layers=active_layers)

def capacity(B, L, shape, water_depth=None):
    args = dict(common)
    if water_depth is not None:
        args["wt_bgl"] = float(water_depth)
    return net_ultimate_bearing_capacity(B=B, L=L, footing_shape=shape, **args)


def coverage_warning(width):
    # Screening warning only; B is not a universal investigation-depth criterion.
    if Df + width > float(layers_profile[-1]["depth_bot"]):
        st.warning("Known profile ends within one footing width below the base. "
                   "Investigate deeper soil and verify the bearing model before relying on this result.")
    elif Df + width > float(detected_layer["depth_bot"]):
        st.warning("A layer boundary lies within one footing width below the base. "
                   "Check whether the single founding-layer bearing model is applicable.")

st.header("📊 Section C — Concentric Bearing Capacity Results")
B_calc, L_calc = B_sidebar, L_sidebar
try:
    result = capacity(B_calc, L_calc, footing_shape)
    qf, qnu = result["qf"], result["qnu"]
    qns = net_safe_bearing_capacity(qnu, FOS)
except ValueError as exc:
    section_error(exc)
    st.stop()
coverage_warning(result["B"])
if qnu <= 0:
    st.warning("No positive net ultimate bearing capacity for these inputs.")

# Results card
c_res1, c_res2, c_res3, c_res4 = st.columns(4)
c_res1.metric("qf — Gross Ultimate", f"{qf:.2f} kPa")
c_res2.metric("qnu — Net Ultimate", f"{qnu:.2f} kPa")
c_res3.metric("qns — Net Safe", f"{qns:.2f} kPa")
c_res4.metric("FOS (applied)", f"{FOS:.1f}")

# Intermediate values expander
with st.expander("🔍 Intermediate Values (IS 6403:1981 Factors)", expanded=False):
    factors_data = {
        "Parameter": [
            "Nc", "Nq", "Nγ",
            "sc (shape, c-term)", "sq (shape, q-term)", "sγ (shape, γ-term)",
            "dc (depth, c-term)", "dq (depth, q-term)", "dγ (depth, γ-term)",
            "ic (incl., c-term)", "iq (incl., q-term)", "iγ (incl., γ-term)",
            "W′ (WT factor)",
            "q_eff (overburden)",
            "γ·W′ for Nγ term",
            "B (width)", "L (length)",
            "c used", "φ used",
        ],
        "Value": [
            f"{result['Nc']:.4f}", f"{result['Nq']:.4f}", f"{result['Ngamma']:.4f}",
            f"{result['sc']:.4f}", f"{result['sq']:.4f}", f"{result['sgamma']:.4f}",
            f"{result['dc']:.4f}", f"{result['dq']:.4f}", f"{result['dgamma']:.4f}",
            f"{result['ic']:.4f}", f"{result['iq']:.4f}", f"{result['igamma']:.4f}",
            f"{result['W_prime']:.4f}",
            f"{result['q_eff']:.3f} kPa",
            f"{result['gamma_ngamma']:.3f} kN/m³",
            f"{result['B']:.3f} m", "1 m (unit-length basis)" if footing_shape == "strip" else f"{result['L']:.3f} m",
            f"{result['c_used']:.2f} kPa", f"{result['phi_used']:.2f} °",
        ],
        "IS 6403:1981 Reference": [
            "Table 1", "Table 1", "Table 1",
            "Cl. 5.1", "Cl. 5.1", "Cl. 5.1",
            "Cl. 5.1", "Cl. 5.1", "Cl. 5.1",
            "Cl. 5.1", "Cl. 5.1", "Cl. 5.1",
            "Cl. 5.2",
            "Cl. 5.1", "Cl. 5.2",
            "—", "—",
            "Cl. 5.3" if failure_mode == "local" else "Cl. 5.1",
            "Cl. 5.3" if failure_mode == "local" else "Cl. 5.1",
        ],
    }
    st.dataframe(pd.DataFrame(factors_data), use_container_width=True, hide_index=True)

    if failure_mode == "local":
        st.warning(
            "⚠️ **Local shear mode active** (IS 6403:1981 Cl. 5.3): "
            f"c reduced to {result['c_used']:.2f} kPa (= 2/3·c′), "
            f"φ reduced to {result['phi_used']:.2f}° (= arctan(2/3·tan φ′))."
        )

# ---------------------------------------------------------------------------
# SECTION D — Footing Sizing for Column Types
# ---------------------------------------------------------------------------
st.header("📐 Section D — Concentric Footing Sizing")
st.caption("Uses the selected footing shape and service load cases. Enter loads on the chosen basis, including any appropriate load multiplier before entry.")
load_basis = st.radio("Load basis for sizing", ["Gross contact load", "Net applied load"],
    help="Gross: input includes applicable foundation/backfill weights; the utility subtracts effective surcharge q_eff. Net: input already represents net load on the trial area.")
load_is_net = load_basis == "Net applied load"
st.caption("Gross conversion follows the utility's effective-surcharge convention: q_net = P/A − q_eff. Confirm the load and stress basis, especially for undrained total-stress design. Column load alone may not equal gross contact load.")
load_unit = "kN/m" if footing_shape == "strip" else "kN"
if footing_shape == "strip":
    st.info("Strip footing: enter service load per metre of footing length, not a total column load.")
    defaults = ["Strip case 1", "Strip case 2", "Strip case 3"]
else:
    defaults = ["Corner", "Edge", "Interior"]
demo = st.session_state.get("demo_project")
initial_loads = [demo["loads"][k] * demo["factor"] for k in defaults] if demo and footing_shape != "strip" else [400.0, 600.0, 900.0]
load_cases = st.data_editor(pd.DataFrame({"Load case": defaults, "P": initial_loads}),
    num_rows="dynamic", hide_index=True, use_container_width=True, key=f"p3_loads_{footing_shape}",
    column_config={"P": st.column_config.NumberColumn(f"Service load P ({load_unit})", min_value=0.0, required=True)})
aspect_ratio = max(B_sidebar, L_sidebar) / min(B_sidebar, L_sidebar) if footing_shape == "rectangular" else 1.0
if footing_shape == "rectangular":
    st.caption(f"Sizing preserves the selected long/short side ratio = {aspect_ratio:.3f}.")
width_step = st.number_input("Width rounding increment (m)", min_value=0.001, value=0.05, step=0.01)
sizing_rows = []
for _, case in load_cases.iterrows():
    name = str(case["Load case"])
    row = {"Load case": name, f"P ({load_unit})": case["P"]}
    try:
        sz = required_footing_size(P_kN=float(case["P"]), FOS=FOS, footing_shape=footing_shape,
            aspect_ratio=aspect_ratio, width_step=width_step, load_is_net=load_is_net, **common)
        row.update({"Required B (m)": round(sz["B"], 4),
                    "L (m)": "1 (unit basis)" if footing_shape == "strip" else round(sz["L"], 4),
                    "qnu (kPa)": round(sz["qnu"], 3), "qns (kPa)": round(sz["qns"], 3),
                    "Net applied (kPa)": round(sz["net_applied_pressure"], 3),
                    "Actual FOS": round(sz["actual_FOS"], 3),
                    "Status": "Bearing criterion met"})
        if Df + sz["B"] > float(detected_layer["depth_bot"]):
            row["Status"] = "Bearing model applicability needs review"
    except (ValueError, TypeError, OverflowError) as exc:
        row["Status"] = f"Not sized: {exc}"
    sizing_rows.append(row)
if sizing_rows:
    st.dataframe(pd.DataFrame(sizing_rows), use_container_width=True, hide_index=True)
else:
    st.info("Add at least one load case to calculate footing sizes.")
st.caption("Sizes are for concentric bearing only; check eccentricity, settlement, geometry and structural requirements separately.")

# ---------------------------------------------------------------------------
# SECTION E — Water Table Effect
# ---------------------------------------------------------------------------
st.header("💧 Section E — Water Table Effect on qnu")

W_prime_current = result["W_prime"]
st.metric("W′ (current WT position)", f"{W_prime_current:.3f}")
if W_prime_current == 0.5:
    st.info("WT at or above footing base → W′ = 0.5 (fully reduced Nγ term). The Nγ contribution is reduced; the undrained φ=0 result may not change.")
elif W_prime_current == 1.0:
    st.info("WT deeper than B below footing → W′ = 1.0 (no WT correction). The Nγ correction is inactive.")
else:
    st.warning(f"WT between footing base and B below → W′ = {W_prime_current:.3f} (interpolated).")

# Plot qnu vs WT depth
wt_range = np.unique(np.r_[np.linspace(0.0, max(wt_bgl, Df + result["B"] * 2.0), 60), wt_bgl, Df, Df + result["B"]])
qnu_values = []
for wt_i in wt_range:
    res_i = capacity(B_calc, L_calc, footing_shape, wt_i)
    qnu_values.append(res_i["qnu"])

fig_wt = go.Figure()
fig_wt.add_trace(go.Scatter(
    x=wt_range, y=qnu_values,
    mode="lines+markers",
    name="qnu (kPa)",
    line=dict(color="#1f4e79", width=2),
    marker=dict(size=4),
))
fig_wt.add_vline(
    x=wt_bgl, line_dash="dash", line_color="blue",
    annotation_text=f"Current WT = {wt_bgl:.1f} m",
    annotation_position="top right",
)
fig_wt.add_vline(
    x=Df, line_dash="dot", line_color="orange",
    annotation_text=f"Footing base Df = {Df:.1f} m",
    annotation_position="top left",
)
fig_wt.update_layout(
    title="Net Ultimate Bearing Capacity vs Water Table Depth (IS 6403:1981 Cl. 5.2)",
    xaxis_title="Water Table Depth (m bgl)",
    yaxis_title="qnu (kPa)",
    template="plotly_white",
    height=420,
    legend=dict(orientation="h", y=-0.2),
)
st.plotly_chart(fig_wt, use_container_width=True)

st.markdown(
    """
    **Interpretation (IS 6403:1981 Cl. 5.2):**
    - If WT rises to footing base: Nγ term is halved (W′ = 0.5) — significant reduction in qnu.
    - If WT is deeper than *B* below footing base: no correction needed (W′ = 1.0).
    - The Nq term uses effective overburden pressure q, which also reduces as WT rises.
    """
)

# ---------------------------------------------------------------------------
# SECTION F — Eccentric Loading
# ---------------------------------------------------------------------------
st.header("📏 Section F — Eccentric Loading")
if footing_shape not in ("square", "rectangular"):
    st.info("This effective-rectangle method is implemented for square and rectangular footings only; circular and strip eccentricity are not evaluated here.")
else:
    st.caption("Enter gross vertical contact load and either signed moments or signed eccentricities. The applied net pressure is calculated using the same surcharge convention as Section D.")
    P_eccentric = st.number_input("Gross vertical contact load P (kN)", min_value=0.001, value=600.0, step=10.0)
    method = st.radio("Eccentricity input method", ["From moments", "Direct eccentricities"])
    ef_col1, ef_col2 = st.columns(2)
    with ef_col1:
        if method == "From moments":
            Mx = st.number_input("Moment Mx (kN·m), producing ey", value=0.0, step=1.0)
            My = st.number_input("Moment My (kN·m), producing ex", value=0.0, step=1.0)
            # Eccentricity from moment equilibrium: e = M/P.
            ex, ey = My / P_eccentric, Mx / P_eccentric
        else:
            ex = st.number_input("Signed eccentricity ex along B (m)", value=0.0, step=0.01)
            ey = st.number_input("Signed eccentricity ey along L (m)", value=0.0, step=0.01)
    with ef_col2:
        st.write(f"ex = {ex:.3f} m; ey = {ey:.3f} m")
        try:
            B_eff, L_eff, A_eff = effective_area(B_sidebar, L_sidebar, ex, ey)
            # Utility sorts effective dimensions for bearing factors; show original axes separately.
            bx = B_sidebar - 2 * abs(ex)
            ly = L_sidebar - 2 * abs(ey)
            st.write(f"Effective dimension along B: {bx:.3f} m; along L: {ly:.3f} m")
            st.write(f"Effective area: {A_eff:.3f} m²")
            eff_shape = "square" if footing_shape == "square" and np.isclose(B_eff, L_eff) else "rectangular"
            res_eff = capacity(B_eff, L_eff, eff_shape)
            qns_eff = net_safe_bearing_capacity(res_eff["qnu"], FOS)
            q_gross = P_eccentric / A_eff
            q_net = net_pressure(q_gross, res_eff["q_eff"], False)
            st.metric("Net safe capacity (kPa)", f"{qns_eff:.3f}")
            st.metric("Gross applied pressure (kPa)", f"{q_gross:.3f}")
            st.metric("Net applied pressure (kPa)", f"{q_net:.3f}")
            if q_net <= 0:
                st.error("Net applied pressure is nonpositive. Check load basis and geometry; no bearing pass reported.")
            elif q_net <= qns_eff:
                st.success("Net bearing-pressure criterion met for this calculation (not a complete foundation design).")
            else:
                st.error("Net applied pressure exceeds net safe capacity.")
            coverage_warning(B_eff)
            if 6 * abs(ex) / B_sidebar + 6 * abs(ey) / L_sidebar > 1:
                st.warning("Resultant lies outside the rectangular kern; partial contact is possible. Check contact, uplift and structural design separately.")
            with st.expander("Effective-footing bearing factors"):
                factor_keys = ["Nc", "Nq", "Ngamma", "sc", "sq", "sgamma", "dc", "dq", "dgamma", "ic", "iq", "igamma", "W_prime"]
                st.dataframe(pd.DataFrame({"Factor": factor_keys, "Value": [res_eff[k] for k in factor_keys]}), hide_index=True)
        except (ValueError, OverflowError) as exc:
            section_error(exc)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "IS 6403:1981 — Code of Practice for Determination of Bearing Capacity of Shallow Foundations. "
    "GeoForge · All calculations in SI units (kN, kPa, m)."
)
