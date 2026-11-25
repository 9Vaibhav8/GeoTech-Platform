"""
pages/3_🏗️_Bearing_Capacity.py
P3 — Bearing Capacity of Shallow Foundations (Strict IS 6403:1981 Compliance)
IIT Mandi CE 402 Geotechnical Engineering Platform

Design Principle (SRP):
  Handles strictly Streamlit layout and widget binding; all geotechnical
  computations reside in `utils/bearing_capacity.py` and all Plotly charts /
  formatted tables reside in `utils/bearing_capacity_presenter.py`.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.bearing_capacity import (
    FootingSpec,
    IS6403Solver,
    SoilFoundingState,
    compute_effective_overburden,
)
from utils.bearing_capacity_presenter import BearingCapacityPresenter
from utils.constants import init_session_state

# ---------------------------------------------------------------------------
# Page Config & Session State
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="P3 · Bearing Capacity — IS 6403:1981",
    page_icon="🏗️",
    layout="wide",
)
init_session_state()

SOLVER = IS6403Solver()
PRESENTER = BearingCapacityPresenter()

st.title("🏗️ P3 — Bearing Capacity (IS 6403:1981)")
st.caption("Shallow foundation design strictly per IS 6403:1981 | SI units (kN, kPa, m, °)")


def get_layer_at_depth(depth_m: float) -> dict | None:
    """Return the session-state layer dict containing depth_m (m bgl)."""
    layers = st.session_state.get("layers", [])
    for lyr in layers:
        if lyr["depth_top"] <= depth_m < lyr["depth_bot"]:
            return lyr
    return layers[-1] if layers else None


# ---------------------------------------------------------------------------
# SIDEBAR — Section A: Footing & Loading Parameters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Footing Parameters")

    Df = st.number_input(
        "Founding depth Df (m bgl)",
        min_value=0.0,
        max_value=15.0,
        value=1.5,
        step=0.1,
        help="Depth of footing base below existing ground level (m).",
    )

    shape_opts = ["Square", "Rectangular", "Circular", "Strip"]
    footing_shape_label = st.selectbox("Footing shape", shape_opts, index=0)
    footing_shape = footing_shape_label.lower()

    if footing_shape == "rectangular":
        col_b, col_l = st.columns(2)
        with col_b:
            B_sidebar = st.number_input(
                "Width B (m)", min_value=0.2, max_value=30.0, value=2.0, step=0.1
            )
        with col_l:
            L_sidebar = st.number_input(
                "Length L (m)", min_value=0.2, max_value=50.0, value=2.5, step=0.1
            )
    elif footing_shape == "strip":
        B_sidebar = st.number_input(
            "Width B (m)", min_value=0.2, max_value=20.0, value=1.5, step=0.1
        )
        L_sidebar = 1.0e6
    else:
        dim_label = "Diameter B (m)" if footing_shape == "circular" else "Width B = L (m)"
        B_sidebar = st.number_input(
            dim_label, min_value=0.2, max_value=30.0, value=2.0, step=0.1
        )
        L_sidebar = B_sidebar

    failure_mode_label = st.radio(
        "Shear failure mode",
        ["General shear", "Local shear"],
        help="IS 6403:1981 Cl. 5.1.2 (General) vs. Cl. 5.1.2.2 (Local shear reduction).",
    )
    failure_mode = "general" if failure_mode_label == "General shear" else "local"

    alpha_deg = st.number_input(
        "Load inclination α (°)",
        min_value=0.0,
        max_value=45.0,
        value=0.0,
        step=1.0,
        help="IS 6403:1981 Cl. 5.1.2.1 — Angle of resultant load from vertical (°).",
    )

    FOS = st.number_input(
        "Factor of Safety FOS (—)",
        min_value=1.0,
        max_value=10.0,
        value=3.0,
        step=0.5,
        help="IS 6403:1981 Cl. 6 — Factor of safety applied to net ultimate capacity qnu.",
    )

    st.divider()
    st.subheader("📐 Eccentric Loading (Cl. 5.4)")
    supports_eccentric = footing_shape in ("square", "rectangular")
    if supports_eccentric:
        ex_input = st.number_input(
            "Eccentricity ex along B (m)", min_value=0.0, value=0.0, step=0.01, format="%.3f"
        )
        ey_input = st.number_input(
            "Eccentricity ey along L (m)", min_value=0.0, value=0.0, step=0.01, format="%.3f"
        )
    else:
        ex_input, ey_input = 0.0, 0.0
        st.info("Biaxial eccentricity applies to Square and Rectangular footings.")

    st.divider()
    wt_bgl_session = float(st.session_state.get("wt_design_bgl", 1.0))
    wt_bgl = st.number_input(
        "Design WT depth (m bgl)",
        min_value=0.0,
        max_value=50.0,
        value=wt_bgl_session,
        step=0.1,
        help="Highest seasonal water-table depth for design (m bgl).",
    )

# ---------------------------------------------------------------------------
# SECTION B — Soil Parameters & Multi-layer Overburden at Founding Level
# ---------------------------------------------------------------------------
st.header("🪨 Section B — Soil Parameters & Overburden at Founding Level")

layers = st.session_state.get("layers", [])
detected_layer = get_layer_at_depth(Df)
if detected_layer is None:
    st.error("⚠️ No soil layers defined. Define strata in P1 — Soil Profile first.")
    st.stop()

with st.expander(f"📋 Bearing stratum at Df = {Df:.2f} m: {detected_layer.get('name', '')}", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("IS 1498 Symbol", detected_layer.get("symbol", "—"))
    c2.metric("c′ (kPa)", f"{detected_layer.get('c_prime', 0.0):.1f} kPa")
    c3.metric("φ′ (°)", f"{detected_layer.get('phi_prime', 0.0):.1f} °")
    c4.metric("cu (kPa)", f"{detected_layer.get('cu', 0.0):.1f} kPa")

    c5, c6, c7 = st.columns(3)
    c5.metric("γ_moist (kN/m³)", f"{detected_layer.get('gamma_moist', 18.0):.1f} kN/m³")
    c6.metric("γ_sat (kN/m³)", f"{detected_layer.get('gamma_sat', 20.0):.1f} kN/m³")
    c7.metric("Analysis mode", "Undrained (φ=0)" if detected_layer.get("is_undrained", False) else "Drained (c′–φ′)")

override = st.checkbox("🔧 Override bearing stratum parameters manually")
if override:
    oc1, oc2, oc3 = st.columns(3)
    with oc1:
        c_prime = st.number_input(
            "c′ (kPa)", min_value=0.0, max_value=500.0,
            value=float(detected_layer.get("c_prime", 0.0)), step=0.5,
        )
        phi_prime = st.number_input(
            "φ′ (°)", min_value=0.0, max_value=55.0,
            value=float(detected_layer.get("phi_prime", 30.0)), step=0.5,
        )
    with oc2:
        cu_val = st.number_input(
            "cu (kPa)", min_value=0.0, max_value=500.0,
            value=float(detected_layer.get("cu", 0.0)), step=0.5,
        )
        is_undrained = st.checkbox(
            "Use undrained (φ = 0°) analysis — Cl. 5.1.3",
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
else:
    c_prime = float(detected_layer.get("c_prime", 0.0))
    phi_prime = float(detected_layer.get("phi_prime", 30.0))
    cu_val = float(detected_layer.get("cu", 0.0))
    is_undrained = bool(detected_layer.get("is_undrained", False))
    gamma_moist = float(detected_layer.get("gamma_moist", 18.0))
    gamma_sat = float(detected_layer.get("gamma_sat", 20.0))

# Multi-layer effective overburden integration above Df
q_eff_integrated = compute_effective_overburden(layers, Df, wt_bgl)
st.info(
    f"**Effective overburden pressure q at Df = {Df:.2f} m:** `{q_eff_integrated:.2f} kPa`  \n"
    f"*(Integrated across all soil layers from 0.00 m to {Df:.2f} m bgl using "
    f"γ_moist above WT = {wt_bgl:.2f} m and γ_sat − γw below WT.)*"
)

# ---------------------------------------------------------------------------
# SECTION C — IS 6403:1981 Bearing Capacity Results
# ---------------------------------------------------------------------------
st.header("📊 Section C — Bearing Capacity Results")

footing_spec = FootingSpec(
    B=B_sidebar,
    L=L_sidebar,
    Df=Df,
    footing_shape=footing_shape,  # type: ignore[arg-type]
    ex=ex_input,
    ey=ey_input,
    alpha_deg=alpha_deg,
)
soil_state = SoilFoundingState(
    c_prime=c_prime,
    phi_prime_deg=phi_prime,
    gamma_moist=gamma_moist,
    gamma_sat=gamma_sat,
    wt_bgl=wt_bgl,
    q_eff=q_eff_integrated,
    is_undrained=is_undrained,
    cu=cu_val,
)

try:
    result = SOLVER.solve(footing_spec, soil_state, FOS=FOS, failure_mode=failure_mode)
except ValueError as exc:
    st.error(f"Input error: {exc}")
    st.stop()

if result.kern_warning:
    st.warning(
        f"⚠️ **Kern / Tension Lift-off Warning (IS 6403:1981 Cl. 5.4):** "
        f"Eccentricity exceeds the middle-third limit "
        f"(ex = {ex_input:.3f} m vs. B/6 = {result.B/6:.3f} m; "
        f"ey = {ey_input:.3f} m vs. L/6 = {result.L/6:.3f} m). "
        f"Partial footing lift-off may occur; design relies on reduced effective area "
        f"B′ × L′ = {result.B_prime:.3f} m × {result.L_prime:.3f} m."
    )

m1, m2, m3, m4 = st.columns(4)
m1.metric("qf — Gross Ultimate (kPa)", f"{result.qf:.2f} kPa")
m2.metric("qnu — Net Ultimate (kPa)", f"{result.qnu:.2f} kPa")
m3.metric("qns — Net Safe (kPa)", f"{result.qns:.2f} kPa")
m4.metric("Applied FOS (—)", f"{result.FOS:.2f}")

st.caption(f"**Active Strategy:** {result.strategy_name}")

with st.expander("🔍 All IS 6403:1981 Factors & Intermediate Values", expanded=True):
    col_tbl, col_chart = st.columns([1.2, 1.0])
    with col_tbl:
        st.dataframe(
            PRESENTER.build_factors_dataframe(result),
            use_container_width=True,
            hide_index=True,
        )
    with col_chart:
        st.plotly_chart(
            PRESENTER.create_term_contribution_figure(result),
            use_container_width=True,
        )

    if result.failure_mode == "local":
        st.warning(
            f"⚠️ **Local Shear Reduction (IS 6403:1981 Cl. 5.1.2.2):** "
            f"cm = (2/3)·c′ = `{result.c_used:.2f} kPa`, "
            f"φm = arctan((2/3)·tan φ′) = `{result.phi_used:.2f}°`."
        )

# ---------------------------------------------------------------------------
# SECTION D — Iterative Footing Sizing for Service Loads
# ---------------------------------------------------------------------------
st.header("📐 Section D — Footing Sizing for Column Loads")
st.caption("Service column loads P (kN) at founding level; square footing sizing rounded up to 0.05 m.")

sc1, sc2, sc3 = st.columns(3)
with sc1:
    P_corner = st.number_input("Corner column P (kN)", min_value=10.0, max_value=20000.0, value=650.0, step=10.0)
with sc2:
    P_edge = st.number_input("Edge column P (kN)", min_value=10.0, max_value=20000.0, value=1000.0, step=10.0)
with sc3:
    P_interior = st.number_input("Interior column P (kN)", min_value=10.0, max_value=20000.0, value=1450.0, step=10.0)

sizing_rows = []
for col_type, P_val in [("Corner", P_corner), ("Edge", P_edge), ("Interior", P_interior)]:
    sz = SOLVER.required_footing_size(
        P_kN=P_val,
        soil=soil_state,
        Df=Df,
        FOS=FOS,
        footing_shape="square",
        failure_mode=failure_mode,
        alpha_deg=alpha_deg,
    )
    fos_ok = sz["actual_FOS"] >= FOS
    sizing_rows.append({
        "Column Type": col_type,
        "Service Load P (kN)": f"{P_val:.1f}",
        "Required B = L (m)": f"{sz['B']:.2f}",
        "qnu (kPa)": f"{sz['qnu']:.2f}",
        "qns (kPa)": f"{sz['qns']:.2f}",
        "Actual FOS (—)": f"{sz['actual_FOS']:.2f}",
        "Status": "✅ OK" if fos_ok else "❌ NG",
    })

sizing_df = pd.DataFrame(sizing_rows)
st.dataframe(
    sizing_df.style.map(
        lambda v: "background-color: #d4edda; color: #155724;"
        if "✅" in str(v)
        else ("background-color: #f8d7da; color: #721c24;" if "❌" in str(v) else ""),
        subset=["Status"],
    ),
    use_container_width=True,
    hide_index=True,
)

# ---------------------------------------------------------------------------
# SECTION E — Water Table Sensitivity (Cl. 5.1.2.3)
# ---------------------------------------------------------------------------
st.header("💧 Section E — Water Table Effect on Bearing Capacity (Cl. 5.1.2.3)")

st.metric("W′ (current water-table factor, —)", f"{result.W_prime:.3f}")
fig_wt = PRESENTER.create_water_table_sensitivity_figure(
    solver=SOLVER,
    footing=footing_spec,
    soil_template=soil_state,
    layers=layers,
    FOS=FOS,
    failure_mode=failure_mode,
    use_profile_overburden=True,
)
st.plotly_chart(fig_wt, use_container_width=True)

# ---------------------------------------------------------------------------
# SECTION F — Eccentric Loading Check (Cl. 5.4)
# ---------------------------------------------------------------------------
st.header("📏 Section F — Eccentric Loading Check (IS 6403:1981 Cl. 5.4)")

if not supports_eccentric:
    st.info("Select **Square** or **Rectangular** footing in the sidebar to evaluate biaxial eccentric loading.")
else:
    ef1, ef2 = st.columns(2)
    with ef1:
        P_ecc = st.number_input("Column load P (kN)", min_value=1.0, value=1000.0, step=10.0, key="ecc_P")
        Mx = st.number_input("Moment Mx (kN·m) → ey = Mx / P", min_value=0.0, value=0.0, step=1.0, key="ecc_Mx")
        My = st.number_input("Moment My (kN·m) → ex = My / P", min_value=0.0, value=0.0, step=1.0, key="ecc_My")

    ex_final = max(ex_input, My / P_ecc if P_ecc > 0 else 0.0)
    ey_final = max(ey_input, Mx / P_ecc if P_ecc > 0 else 0.0)

    ecc_spec = FootingSpec(
        B=B_sidebar,
        L=L_sidebar,
        Df=Df,
        footing_shape=footing_shape,  # type: ignore[arg-type]
        ex=ex_final,
        ey=ey_final,
        alpha_deg=alpha_deg,
    )
    b_eff, l_eff, b_prime, l_prime, a_eff, ecc_kern_warn = ecc_spec.effective_dimensions()

    with ef2:
        st.markdown(
            f"- **ex** = `{ex_final:.3f} m` &nbsp;|&nbsp; **ey** = `{ey_final:.3f} m`\n"
            f"- **B_eff** = B − 2·ex = `{b_eff:.3f} m` &nbsp;|&nbsp; **L_eff** = L − 2·ey = `{l_eff:.3f} m`\n"
            f"- **Normalized B′** = min(B_eff, L_eff) = `{b_prime:.3f} m` &nbsp;|&nbsp; "
            f"**L′** = max(B_eff, L_eff) = `{l_prime:.3f} m`\n"
            f"- **Effective area A_eff** = `{a_eff:.3f} m²`"
        )
        if ecc_kern_warn:
            st.warning(
                f"⚠️ **Kern check exceeded:** ex ≥ B/6 ({B_sidebar/6:.3f} m) or "
                f"ey ≥ L/6 ({L_sidebar/6:.3f} m) — tension / lift-off possible."
            )

        if b_eff <= 0.0 or l_eff <= 0.0:
            st.error("❌ Eccentricity too large — effective area is zero or negative. Increase footing size.")
        else:
            res_ecc = SOLVER.solve(ecc_spec, soil_state, FOS=FOS, failure_mode=failure_mode)
            q_applied = P_ecc / res_ecc.A_eff
            c_e1, c_e2 = st.columns(2)
            c_e1.metric("qns (effective area, kPa)", f"{res_ecc.qns:.2f} kPa")
            c_e2.metric("Applied pressure P / A_eff (kPa)", f"{q_applied:.2f} kPa")
            if q_applied <= res_ecc.qns:
                st.success(f"✅ PASS — {q_applied:.2f} kPa ≤ {res_ecc.qns:.2f} kPa")
            else:
                st.error(f"❌ FAIL — {q_applied:.2f} kPa > {res_ecc.qns:.2f} kPa")

st.divider()
st.caption("IS 6403:1981 — Code of Practice for Determination of Bearing Capacity of Shallow Foundations · All SI units (kN, kPa, m, °).")
