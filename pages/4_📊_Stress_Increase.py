"""
P4 — Boussinesq Stress Increase
Computes vertical stress increase below a uniformly loaded rectangular footing
using the Boussinesq (1885) formula and the 2:1 method.

Sources:
  - Boussinesq (1885) — exact elastic solution for point load
  - Das (2016) Principles of Foundation Engineering, Eq. 5.37, Sec. 5.5
  - IS 8009:1976 Part 1 — Code of practice for calculation of settlements
  - 2:1 method: IS 8009:1976
"""

from uuid import uuid4

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.demo_data import demo_notice
from utils.constants import init_session_state
from utils.bearing_capacity import validate_profile
from utils.stress_increase import (
    stress_increase_centre,
    boussinesq_corner,
    stress_increase_point,
    stress_increase_2to1,
    stress_profile,
    influence_depth,
    effective_stress_profile,
)

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(page_title="P4 – Stress Increase", page_icon="📊", layout="wide")
init_session_state()
demo_notice(st)

st.title("📊 P4 — Vertical Stress Increase")
st.caption(
    "Boussinesq (1885) rectangular load formula and 2:1 method · "
    "IS 8009:1976 Part 1"
)

# ── Sidebar ────────────────────────────────────────────────────────────────
demo = st.session_state.get("demo_project")
with st.sidebar:
    st.header("⚙️ Footing & Load")

    B = st.number_input("Footing width  B (m)", value=2.5 if demo else 2.0, min_value=0.001, step=0.1,
                        key="p4_B")
    L = st.number_input("Footing length  L (m)", value=2.5 if demo else 2.0, min_value=0.001, step=0.1,
                        key="p4_L")
    # Shared P1/P3 foundation depth; use a page-specific widget key.
    Df = st.number_input("Founding depth  Df (m)",
                         value=float(st.session_state.get("foundation_depth", 1.5)),
                         min_value=0.0, step=0.1, key="p4_Df")
    st.session_state.foundation_depth = Df

    st.caption("Illustrative initial values only — enter your own footing and load.")
    if demo:
        st.caption("Demo: edge column, trial 2.5 m square, net load based on the effective surcharge at initial demo depth. Recalculate net input if geometry or groundwater changes.")
    input_mode = st.radio("Load input", ["Net load P (kN)", "Net pressure q (kPa)"],
                          key="p4_input_mode_v2")
    if input_mode == "Net load P (kN)":
        P_kN = st.number_input("Net foundation load P (kN)", value=float(demo["p4_net_load"]) if demo else 1000.0, min_value=0.0,
                               step=10.0, key="p4_net_P",
                               help="Enter the NET load after the appropriate excavation/surcharge adjustment. Do not enter an unadjusted gross column load.")
        q_net = P_kN / (B * L)
        st.metric("Net foundation pressure q", f"{q_net:.1f} kPa")
    else:
        q_net = st.number_input("Net foundation pressure q (kPa)", value=float(demo["p4_net_load"] / 6.25) if demo else 250.0,
                                min_value=0.0, step=5.0, key="p4_q")
    st.caption("Both input modes require net loading. Gross-to-net conversion depends on the chosen stress basis and construction assumptions.")

    st.markdown("---")
    method_opts = {
        "Boussinesq — Centre": "boussinesq_centre",
        "Boussinesq — Corner": "boussinesq_corner",
        "2:1 Method": "2to1",
        "All three": "all",
    }
    method_label = st.selectbox("Method", list(method_opts.keys()), key="p4_method")
    method = method_opts[method_label]

    z_max = st.number_input("Maximum depth below footing (m)", value=3.0 * B,
                            min_value=0.001, step=0.5, key="p4_zmax_m")
    n_pts = st.number_input("Plot resolution (points)", min_value=2, max_value=5000,
                            value=200, step=10, key="p4_resolution")
    table_step = st.number_input("Table depth interval (m)", min_value=0.001,
                                 value=0.25, step=0.05, key="p4_table_step")
    threshold_pct = st.number_input("Centre influence threshold (% of q)",
                                     min_value=0.1, max_value=99.9, value=10.0,
                                     step=1.0, key="p4_threshold")
    threshold = threshold_pct / 100.0
    show_eff_stress = st.checkbox("Overlay effective stress σ′v₀", value=True,
                                  key="p4_show_sv")

# ── Compute profiles ───────────────────────────────────────────────────────
layers = st.session_state.layers
wt = float(st.session_state.wt_design_bgl)

# One depth grid, including the exact surface limit, for every plotted method.
z_arr = np.linspace(0.0, z_max, int(n_pts))
methods_to_plot = (
    ["boussinesq_centre", "boussinesq_corner", "2to1"] if method == "all"
    else [method]
)
traces_data = {}
try:
    for m in methods_to_plot:
        _, ds = stress_profile(q_net, B, L, z_max, method=m, n_points=n_pts)
        traces_data[m] = ds
    z_inf = (influence_depth(q_net, B, L, threshold=threshold,
                             method="boussinesq_centre") if q_net > 0 else None)
except ValueError as exc:
    st.error(f"Invalid stress input: {exc}")
    st.stop()

# Stress increments do not require a soil profile. The effective stress overlay does.
profile_bottom = None
profile_ok = False
try:
    ordered = validate_profile(layers)
    profile_bottom = float(ordered[-1]["depth_bot"])
    # Validate all unit weights before offering the overlay.
    effective_stress_profile(ordered, wt, [profile_bottom])
    profile_ok = True
except (ValueError, TypeError, KeyError) as exc:
    st.warning(f"Effective stress unavailable: {exc}. Stress-increase methods remain available.")


def overlay_at(depths):
    depths = np.asarray(depths, dtype=float)
    result = np.full(depths.shape, np.nan)
    if profile_ok:
        mask = depths + Df <= profile_bottom + 1e-9
        if np.any(mask):
            result[mask] = effective_stress_profile(layers, wt, depths[mask], Df=Df)
    return result


eff_stress = overlay_at(z_arr)
if profile_ok and Df + z_max > profile_bottom:
    st.info(f"The entered soil profile ends at {profile_bottom:.2f} m bgl. "
            "Stress increase is plotted to the selected depth; effective stress is shown only within the known profile.")
if q_net == 0:
    st.info("Zero net loading: stress increase is zero; normalized influence depth is not defined.")

# ── Figure ─────────────────────────────────────────────────────────────────
colour_map = {
    "boussinesq_centre": "#1f4e79",
    "boussinesq_corner": "#e67e22",
    "2to1": "#27ae60",
}
label_map = {
    "boussinesq_centre": "Boussinesq — Centre",
    "boussinesq_corner": "Boussinesq — Corner",
    "2to1": "2:1 Method",
}

fig = go.Figure()

for m, ds in traces_data.items():
    fig.add_trace(go.Scatter(
        x=ds, y=z_arr,
        mode="lines", name=label_map[m],
        line=dict(color=colour_map[m], width=2.5),
    ))

if show_eff_stress and np.any(np.isfinite(eff_stress)):
    fig.add_trace(go.Scatter(
        x=eff_stress, y=z_arr,
        mode="lines", name="Effective stress σ′v₀ (kPa)",
        line=dict(color="grey", width=1.5, dash="dot"),
    ))

# Mark influence depth
if z_inf is not None and z_inf <= z_max:
    fig.add_hline(y=z_inf, line_dash="dash", line_color="red",
                  annotation_text=f"{threshold_pct:g}% centre influence depth z* = {z_inf:.2f} m",
                  annotation_position="right")

# Mark layer boundaries
for lyr in (layers if profile_ok else []):
    zb = float(lyr["depth_bot"]) - Df
    if 0 < zb <= z_max:
        fig.add_hline(y=zb, line_dash="dot", line_color="#aaa",
                      annotation_text=lyr.get("name", lyr.get("symbol", "Layer boundary")),
                      annotation_position="right",
                      annotation_font_size=10)

# Mark groundwater table
wt_below_footing = wt - Df
if 0 < wt_below_footing <= z_max:
    fig.add_hline(y=wt_below_footing, line_dash="dashdot", line_color="blue",
                  annotation_text="Design WT", annotation_position="right")

fig.update_layout(
    title=f"Vertical Stress Increase below Footing ({B:.1f} m × {L:.1f} m, q = {q_net:.1f} kPa)",
    xaxis_title="Stress (kPa)",
    yaxis_title="Depth below footing base (m)",
    yaxis=dict(autorange="reversed"),
    legend=dict(x=0.65, y=0.98),
    height=600,
    margin=dict(l=60, r=120, t=60, b=60),
)
st.plotly_chart(fig, use_container_width=True)

# ── Key metrics ────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Net pressure  q", f"{q_net:.1f} kPa")
col2.metric(f"{threshold_pct:g}% centre influence depth", f"{z_inf:.2f} m" if z_inf is not None else "N/A")
col3.metric("Depth plotted", f"{z_max:.2f} m")
col4.metric("Footing area  B × L", f"{B*L:.2f} m²")

# ── Data table ─────────────────────────────────────────────────────────────
st.subheader("📋 Stress Increase Table")
# Keep the table within the selected plot depth and include both endpoints.
if z_max / table_step > 5000:
    st.warning("Table interval increased to limit the table to about 5,001 rows.")
    table_step = z_max / 5000
z_table = np.arange(0.0, z_max, table_step)
z_table = z_table[z_table < z_max]
z_table = np.append(z_table, z_max)
sv_table = overlay_at(z_table)
rows = []
for z, sv0 in zip(z_table, sv_table):
    ds_centre = stress_increase_centre(q_net, B, L, z)
    ds_corner = boussinesq_corner(q_net, B, L, z)
    ds_21 = stress_increase_2to1(q_net, B, L, z)
    rows.append({
        "Depth below footing  z (m)": round(float(z), 2),
        "Δσz — Centre (kPa)": round(float(ds_centre), 2),
        "Δσz — Corner (kPa)": round(float(ds_corner), 2),
        "Δσz — 2:1 (kPa)": round(float(ds_21), 2),
        "σ′v₀ (kPa)": round(float(sv0), 2),
        "Δσz/q — Centre": round(float(ds_centre / q_net), 3) if q_net > 0 else np.nan,
    })

df_table = pd.DataFrame(rows)
st.dataframe(df_table, use_container_width=True, hide_index=True)

# ── Superposition tool ─────────────────────────────────────────────────────
with st.expander("🔀 Superposition Tool — multiple loaded areas"):
    st.write(
        "Add several footings (each with its own B, L, q, and plan offsets). "
        "The offsets locate each footing's near corner from the observation point "
        "at (0, 0); the tool sums the stress at that point. All uniformly loaded rectangles "
        "must lie in the same horizontal loading plane; depths are measured below that plane."
    )
    if "superpos_areas" not in st.session_state:
        st.session_state.superpos_areas = [
            {"B": B, "L": L, "q": q_net, "xoff": 0.0, "yoff": 0.0}
        ]

    sp_areas = st.session_state.superpos_areas
    to_delete = None
    for idx, area in enumerate(sp_areas):
        if "uid" not in area:
            area["uid"] = uuid4().hex
        uid = area["uid"]
        c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1.5, 1.5, 1.5, 1.5, 0.6])
        area["B"] = c1.number_input(f"B{idx+1} (m)", value=area["B"],
                                    min_value=0.001, key=f"sp_B_{uid}")
        area["L"] = c2.number_input(f"L{idx+1} (m)", value=area["L"],
                                    min_value=0.001, key=f"sp_L_{uid}")
        area["q"] = c3.number_input(f"q{idx+1} (kPa)", value=area["q"],
                                    min_value=0.0, key=f"sp_q_{uid}")
        area["xoff"] = c4.number_input(f"Near-corner x{idx+1} (m)", value=area["xoff"],
                                       key=f"sp_xoff_{uid}")
        area["yoff"] = c5.number_input(f"Near-corner y{idx+1} (m)", value=area["yoff"],
                                       key=f"sp_yoff_{uid}")
        if c6.button("✕", key=f"sp_del_{uid}"):
            to_delete = idx
    if to_delete is not None:
        st.session_state.superpos_areas.pop(to_delete)
        st.rerun()
    if st.button("+ Add loaded area"):
        st.session_state.superpos_areas.append(
            {"B": B, "L": L, "q": q_net, "xoff": B, "yoff": 0.0, "uid": uuid4().hex}
        )
        st.rerun()

    # Compute superposed profile
    z_sp = z_arr.copy()
    ds_total = np.zeros_like(z_sp)
    for area in sp_areas:
        # Convert near-corner coordinates to observation coordinates relative to that corner.
        ds_total += stress_increase_point(
            area["q"], area["B"], area["L"], -area["xoff"], -area["yoff"], z_sp
        )
    if not sp_areas:
        st.info("No loaded areas: superposed stress is zero. Add an area to continue.")

    fig_sp = go.Figure()
    fig_sp.add_trace(go.Scatter(
        x=ds_total, y=z_sp,
        mode="lines", name="Superposed Δσz",
        line=dict(color="#8e44ad", width=2.5),
    ))
    fig_sp.update_layout(
        title="Superposed Vertical Stress Increase",
        xaxis_title="Δσz (kPa)",
        yaxis_title="Depth below footing base (m)",
        yaxis=dict(autorange="reversed"),
        height=400,
    )
    st.plotly_chart(fig_sp, use_container_width=True)

# ── Theory box ─────────────────────────────────────────────────────────────
with st.expander("📖 Theory — Boussinesq Stress Increase"):
    st.markdown("### Boussinesq Rectangular Load (IS 8009:1976)")
    st.markdown(
        "For a uniformly loaded rectangle $B \\times L$ with net pressure $q$ (kPa), "
        "the vertical stress increase at depth $z$ below the **corner** is:"
    )
    st.latex(r"\Delta\sigma_z = q \, I_\sigma")
    st.latex(
        r"I_\sigma = \frac{1}{4\pi}\left[ "
        r"\frac{2 m_1 n_1 \sqrt{1+m_1^2+n_1^2}}{1+m_1^2+n_1^2+m_1^2 n_1^2}"
        r"\cdot\frac{2+m_1^2+n_1^2}{1+m_1^2+n_1^2} "
        r"+ \tan^{-1}\!\left(\frac{2 m_1 n_1 \sqrt{1+m_1^2+n_1^2}}"
        r"{1+m_1^2+n_1^2-m_1^2 n_1^2}\right) \right]"
    )
    st.markdown("where $m_1 = B/z$ and $n_1 = L/z$ *(Das 2016, Eq. 5.37)*.")
    st.caption(
        "Note: when $m_1^2 n_1^2 > 1 + m_1^2 + n_1^2$ the arctan argument goes negative; "
        "add $\\pi$ to the arctan term (use `atan2` in code)."
    )

    st.markdown("**Below the centre:** superpose 4 corner rectangles of size $(B/2 \\times L/2)$:")
    st.latex(r"\Delta\sigma_{z,\text{centre}} = 4\,\Delta\sigma_{z,\text{corner}}(B/2,\ L/2,\ z)")

    st.divider()

    st.markdown("### 2:1 Method")
    st.latex(r"\Delta\sigma_z = \frac{q\,B\,L}{(B+z)(L+z)}")
    st.markdown(
        "Simple approximate method that assumes the load spreads at 2 vertical : 1 horizontal. "
        "Compare it against the elastic Boussinesq solution. Both use an idealized loading plane; "
        "the stress-increase model does not explicitly account for layered stiffness or embedment boundary effects."
    )
