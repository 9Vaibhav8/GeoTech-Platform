"""
pages/3_🏗️_Bearing_Capacity.py
IS 6403:1981 — Bearing Capacity of Shallow Foundations
IIT Mandi CE 402 Geotechnical Engineering Platform
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.constants import init_session_state
from utils.bearing_capacity import (
    bearing_capacity_factors,
    net_ultimate_bearing_capacity,
    net_safe_bearing_capacity,
    water_table_factor,
    effective_area,
    required_footing_size,
    GAMMA_W,
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
st.caption("Shallow foundation design per IS 6403:1981 | IIT Mandi CE 402")

# ---------------------------------------------------------------------------
# Helper: detect layer containing a given depth
# ---------------------------------------------------------------------------

def get_layer_at_depth(depth_m: float):
    """Return the layer dict that contains depth_m (m bgl)."""
    layers = st.session_state.get("layers", [])
    for lyr in layers:
        if lyr["depth_top"] <= depth_m <= lyr["depth_bot"]:
            return lyr
    # If depth below all layers, return the last layer
    if layers:
        return layers[-1]
    return None


# ---------------------------------------------------------------------------
# SIDEBAR — Section A: Footing Parameters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Footing Parameters")

    Df = st.number_input(
        "Founding depth Df (m)", min_value=0.3, max_value=10.0,
        value=1.5, step=0.1,
        help="Depth of footing base below ground level (m bgl).",
    )

    shape_opts = ["Square", "Rectangular", "Circular", "Strip"]
    footing_shape_label = st.selectbox("Footing shape", shape_opts, index=0)
    footing_shape = footing_shape_label.lower()

    if footing_shape == "rectangular":
        col_b, col_l = st.columns(2)
        with col_b:
            B_input = st.number_input("Width B (m)", min_value=0.3, max_value=20.0, value=1.5, step=0.1)
        with col_l:
            L_input = st.number_input("Length L (m)", min_value=0.3, max_value=40.0, value=2.0, step=0.1)
        B_sidebar, L_sidebar = B_input, L_input
    elif footing_shape == "strip":
        B_sidebar = st.number_input("Width B (m)", min_value=0.3, max_value=10.0, value=1.0, step=0.1)
        L_sidebar = 1e6
    else:
        B_sidebar = st.number_input(
            "Width / Diameter B (m)", min_value=0.3, max_value=20.0, value=1.5, step=0.1
        )
        L_sidebar = B_sidebar

    failure_mode_label = st.radio(
        "Failure mode",
        ["General shear", "Local shear"],
        help="IS 6403:1981 Cl. 5.3 — Use local shear for loose/soft soils.",
    )
    failure_mode = "general" if failure_mode_label == "General shear" else "local"

    alpha_deg = st.number_input(
        "Load inclination α (°)", min_value=0.0, max_value=45.0, value=0.0, step=1.0,
        help="IS 6403:1981 Cl. 5.1 — Angle of resultant load from vertical.",
    )

    FOS = st.number_input(
        "Factor of Safety (FOS)", min_value=1.0, max_value=10.0, value=3.0, step=0.5,
        help="IS 6403:1981 Cl. 6 recommends FOS ≥ 3.0 for gross capacity.",
    )

    st.divider()
    st.subheader("📐 Eccentric Loading")
    show_eccentric = footing_shape == "rectangular"
    if show_eccentric:
        ex_input = st.number_input("Eccentricity ex along B (m)", min_value=0.0, value=0.0, step=0.01)
        ey_input = st.number_input("Eccentricity ey along L (m)", min_value=0.0, value=0.0, step=0.01)
    else:
        ex_input, ey_input = 0.0, 0.0
        st.info("Eccentric loading available for Rectangular footings.")

    st.divider()
    wt_bgl_sidebar = st.session_state.get("wt_design_bgl", 2.0)
    wt_display = st.number_input(
        "Design WT depth (m bgl)", min_value=0.0, max_value=50.0,
        value=float(wt_bgl_sidebar), step=0.1,
        help="Water table depth used for bearing capacity; override session value here.",
    )
    wt_bgl = wt_display

# ---------------------------------------------------------------------------
# SECTION B — Soil Parameters at Founding Level
# ---------------------------------------------------------------------------
st.header("🪨 Section B — Soil Parameters at Founding Level")

detected_layer = get_layer_at_depth(Df)

if detected_layer is None:
    st.error("⚠️ No soil layers defined in session state. Please define layers in P1 — Soil Profile first.")
    st.stop()

with st.expander("📋 Detected layer at Df = {:.2f} m".format(Df), expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Symbol", detected_layer.get("symbol", "—"))
    col2.metric("c′ (kPa)", f"{detected_layer.get('c_prime', 0.0):.1f}")
    col3.metric("φ′ (°)", f"{detected_layer.get('phi_prime', 0.0):.1f}")
    col4.metric("cu (kPa)", f"{detected_layer.get('cu', 0.0):.1f}")

    col5, col6, col7 = st.columns(3)
    col5.metric("γ_moist (kN/m³)", f"{detected_layer.get('gamma_moist', 18.0):.1f}")
    col6.metric("γ_sat (kN/m³)", f"{detected_layer.get('gamma_sat', 20.0):.1f}")
    col7.metric("Is undrained?", "Yes" if detected_layer.get("is_undrained", False) else "No")

override = st.checkbox("🔧 Override soil parameters manually")

if override:
    st.markdown("**Manual soil parameters:**")
    oc1, oc2, oc3 = st.columns(3)
    with oc1:
        c_prime = st.number_input("c′ (kPa)", min_value=0.0, max_value=500.0,
                                   value=float(detected_layer.get("c_prime", 0.0)), step=0.5)
        phi_prime = st.number_input("φ′ (°)", min_value=0.0, max_value=50.0,
                                     value=float(detected_layer.get("phi_prime", 30.0)), step=0.5)
    with oc2:
        cu_val = st.number_input("cu (kPa)", min_value=0.0, max_value=500.0,
                                  value=float(detected_layer.get("cu", 0.0)), step=0.5)
        is_undrained = st.checkbox("Use undrained (φ=0) analysis",
                                    value=bool(detected_layer.get("is_undrained", False)))
    with oc3:
        gamma_moist = st.number_input("γ_moist (kN/m³)", min_value=10.0, max_value=24.0,
                                       value=float(detected_layer.get("gamma_moist", 18.0)), step=0.1)
        gamma_sat = st.number_input("γ_sat (kN/m³)", min_value=10.0, max_value=24.0,
                                     value=float(detected_layer.get("gamma_sat", 20.0)), step=0.1)
else:
    c_prime     = float(detected_layer.get("c_prime", 0.0))
    phi_prime   = float(detected_layer.get("phi_prime", 30.0))
    cu_val      = float(detected_layer.get("cu", 0.0))
    is_undrained = bool(detected_layer.get("is_undrained", False))
    gamma_moist  = float(detected_layer.get("gamma_moist", 18.0))
    gamma_sat    = float(detected_layer.get("gamma_sat", 20.0))

# Effective overburden at founding level
if wt_bgl >= Df:
    q_eff_display = gamma_moist * Df
    q_note = f"WT below footing base → q = γ_moist × Df = {gamma_moist:.1f} × {Df:.2f}"
else:
    q_eff_display = gamma_moist * wt_bgl + (gamma_sat - GAMMA_W) * (Df - wt_bgl)
    q_note = (
        f"WT above footing → q = γ_moist·{wt_bgl:.2f} + (γ_sat−γw)·{(Df - wt_bgl):.2f}"
    )

st.info(f"**Effective overburden q at founding level:** {q_eff_display:.2f} kPa  \n_{q_note}_")

# ---------------------------------------------------------------------------
# SECTION C — Results
# ---------------------------------------------------------------------------
st.header("📊 Section C — Bearing Capacity Results")

B_calc = B_sidebar
L_calc = L_sidebar

result = net_ultimate_bearing_capacity(
    c_prime=c_prime,
    phi_prime_deg=phi_prime,
    gamma_moist=gamma_moist,
    gamma_sat=gamma_sat,
    Df=Df,
    B=B_calc,
    L=L_calc,
    wt_bgl=wt_bgl,
    footing_shape=footing_shape,
    failure_mode=failure_mode,
    alpha_deg=alpha_deg,
    is_undrained=is_undrained,
    cu=cu_val,
)

qf   = result["qf"]
qnu  = result["qnu"]
qns  = net_safe_bearing_capacity(qnu, FOS)

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
            "γ_eff for Nγ term",
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
            f"{B_calc:.3f} m", f"{L_calc:.3f} m" if footing_shape not in ('square', 'circular', 'strip') else f"{B_calc:.3f} m",
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
st.header("📐 Section D — Footing Sizing for Column Types")
st.markdown(
    "> **Note:** Loads are service loads. For wind/seismic combinations multiply by λ = 1 + g/100."
)

sizing_col1, sizing_col2, sizing_col3 = st.columns(3)
with sizing_col1:
    P_corner = st.number_input("Corner column P (kN)", min_value=10.0, max_value=10000.0, value=400.0, step=10.0)
with sizing_col2:
    P_edge   = st.number_input("Edge column P (kN)",   min_value=10.0, max_value=10000.0, value=600.0, step=10.0)
with sizing_col3:
    P_interior = st.number_input("Interior column P (kN)", min_value=10.0, max_value=10000.0, value=900.0, step=10.0)

sizing_rows = []
for col_type, P in [("Corner", P_corner), ("Edge", P_edge), ("Interior", P_interior)]:
    sz = required_footing_size(
        P_kN=P,
        c_prime=c_prime, phi_prime_deg=phi_prime,
        gamma_moist=gamma_moist, gamma_sat=gamma_sat,
        Df=Df, wt_bgl=wt_bgl,
        FOS=FOS,
        footing_shape="square",
        failure_mode=failure_mode,
        alpha_deg=alpha_deg,
        is_undrained=is_undrained,
        cu=cu_val,
    )
    actual_fos = sz["actual_FOS"]
    fos_ok = actual_fos >= FOS
    sizing_rows.append({
        "Column Type": col_type,
        "P (kN)": f"{P:.0f}",
        "Required B (m)": f"{sz['B']:.2f}",
        "qnu (kPa)": f"{sz['qnu']:.2f}",
        "qns (kPa)": f"{sz['qns']:.2f}",
        "Actual FOS": f"{actual_fos:.2f}",
        "Status": "✅ OK" if fos_ok else "❌ NG",
    })

sizing_df = pd.DataFrame(sizing_rows)

def color_status(val):
    if "✅" in str(val):
        return "background-color: #d4edda; color: #155724;"
    elif "❌" in str(val):
        return "background-color: #f8d7da; color: #721c24;"
    return ""

styled_df = sizing_df.style.map(color_status, subset=["Status"])
st.dataframe(styled_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# SECTION E — Water Table Effect
# ---------------------------------------------------------------------------
st.header("💧 Section E — Water Table Effect on qnu")

W_prime_current = result["W_prime"]
st.metric("W′ (current WT position)", f"{W_prime_current:.3f}")
if W_prime_current == 0.5:
    st.info("WT at or above footing base → W′ = 0.5 (fully reduced Nγ term). qnu is at minimum.")
elif W_prime_current == 1.0:
    st.info("WT deeper than B below footing → W′ = 1.0 (no WT correction). qnu is at maximum.")
else:
    st.warning(f"WT between footing base and B below → W′ = {W_prime_current:.3f} (interpolated).")

# Plot qnu vs WT depth
wt_range = np.linspace(0.0, Df + B_calc * 2.0, 60)
qnu_values = []
for wt_i in wt_range:
    res_i = net_ultimate_bearing_capacity(
        c_prime=c_prime, phi_prime_deg=phi_prime,
        gamma_moist=gamma_moist, gamma_sat=gamma_sat,
        Df=Df, B=B_calc, L=L_calc, wt_bgl=wt_i,
        footing_shape=footing_shape, failure_mode=failure_mode,
        alpha_deg=alpha_deg, is_undrained=is_undrained, cu=cu_val,
    )
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
st.header("📏 Section F — Eccentric Loading (IS 6403:1981 Cl. 5.4)")

if footing_shape != "rectangular":
    st.info("Eccentric loading effective area applies to rectangular footings. Select Rectangular in the sidebar.")
else:
    st.markdown("Compute effective dimensions B_eff and L_eff for eccentric column loading.")

    ef_col1, ef_col2 = st.columns(2)
    with ef_col1:
        P_eccentric = st.number_input("Column load P (kN) for eccentricity calc", min_value=10.0, value=600.0, step=10.0)
        Mx = st.number_input("Moment Mx (kN·m) about X-axis (→ ey)", min_value=0.0, value=0.0, step=1.0)
        My = st.number_input("Moment My (kN·m) about Y-axis (→ ex)", min_value=0.0, value=0.0, step=1.0)

    # Recompute ex, ey from moments if entered
    ex_from_moment = My / P_eccentric if P_eccentric > 0 else 0.0
    ey_from_moment = Mx / P_eccentric if P_eccentric > 0 else 0.0

    # Use larger of sidebar input or moment-derived eccentricity
    ex_final = max(ex_input, ex_from_moment)
    ey_final = max(ey_input, ey_from_moment)

    B_eff, L_eff, A_eff = effective_area(B_sidebar, L_sidebar, ex_final, ey_final)

    with ef_col2:
        st.markdown("**Effective dimensions (IS 6403:1981 Cl. 5.4):**")
        st.markdown(f"- **ex** = max(sidebar, My/P) = **{ex_final:.3f} m**")
        st.markdown(f"- **ey** = max(sidebar, Mx/P) = **{ey_final:.3f} m**")
        st.markdown(f"- **B_eff** = B − 2·ex = {B_sidebar:.2f} − {2*ex_final:.3f} = **{B_eff:.3f} m**")
        st.markdown(f"- **L_eff** = L − 2·ey = {L_sidebar:.2f} − {2*ey_final:.3f} = **{L_eff:.3f} m**")
        st.markdown(f"- **A_eff** = B_eff × L_eff = **{A_eff:.3f} m²**")

        if B_eff <= 0 or L_eff <= 0:
            st.error("⚠️ Eccentricity too large — effective area is zero or negative. Redesign footing.")
        else:
            # Recompute bearing capacity with effective dimensions
            res_eff = net_ultimate_bearing_capacity(
                c_prime=c_prime, phi_prime_deg=phi_prime,
                gamma_moist=gamma_moist, gamma_sat=gamma_sat,
                Df=Df, B=B_eff, L=L_eff, wt_bgl=wt_bgl,
                footing_shape="rectangular", failure_mode=failure_mode,
                alpha_deg=alpha_deg, is_undrained=is_undrained, cu=cu_val,
            )
            qnu_eff  = res_eff["qnu"]
            qns_eff  = net_safe_bearing_capacity(qnu_eff, FOS)
            q_applied = P_eccentric / A_eff

            st.metric("qns with effective area", f"{qns_eff:.2f} kPa")
            st.metric("Applied pressure (P/A_eff)", f"{q_applied:.2f} kPa")
            if q_applied <= qns_eff:
                st.success(f"✅ OK — Applied pressure {q_applied:.2f} kPa ≤ qns {qns_eff:.2f} kPa")
            else:
                st.error(f"❌ NG — Applied pressure {q_applied:.2f} kPa > qns {qns_eff:.2f} kPa. Increase footing size.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "IS 6403:1981 — Code of Practice for Determination of Bearing Capacity of Shallow Foundations. "
    "IIT Mandi CE 402 · All calculations in SI units (kN, kPa, m)."
)
