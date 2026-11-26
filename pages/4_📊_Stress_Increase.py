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

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.constants import init_session_state
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

st.title("📊 P4 — Vertical Stress Increase")
st.caption(
    "Boussinesq (1885) rectangular load formula and 2:1 method · "
    "IS 8009:1976 Part 1"
)

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Footing & Load")

    B = st.number_input("Footing width  B (m)", value=2.0, min_value=0.1, step=0.1,
                        key="p4_B")
    L = st.number_input("Footing length  L (m)", value=2.0, min_value=0.1, step=0.1,
                        key="p4_L")
    Df = st.number_input("Founding depth  Df (m)", value=1.5, min_value=0.0, step=0.1,
                         key="p4_Df")

    input_mode = st.radio("Load input", ["Column load P (kN)", "Net pressure q (kPa)"],
                          key="p4_input_mode")
    if input_mode == "Column load P (kN)":
        P_kN = st.number_input("Column load  P (kN)", value=1030.0, min_value=1.0,
                               step=10.0, key="p4_P")
        q_net = P_kN / (B * L)
        st.metric("Net foundation pressure  q", f"{q_net:.1f} kPa")
    else:
        q_net = st.number_input("Net foundation pressure  q (kPa)", value=250.0,
                                min_value=1.0, step=5.0, key="p4_q")

    st.markdown("---")
    method_opts = {
        "Boussinesq — Centre": "boussinesq_centre",
        "Boussinesq — Corner": "boussinesq_corner",
        "2:1 Method": "2to1",
        "All three": "all",
    }
    method_label = st.selectbox("Method", list(method_opts.keys()), key="p4_method")
    method = method_opts[method_label]

    z_max_factor = st.slider("Plot depth  (× B)", 1.0, 6.0, 3.0, 0.5, key="p4_zmaxfac")
    z_max = z_max_factor * B

    show_eff_stress = st.checkbox("Overlay effective stress σ′v₀", value=True,
                                  key="p4_show_sv")

    st.markdown("---")
    st.info(
        "**λ = 1.03** (group g = 3)\n\n"
        "Corner: **669 kN** · Edge: **1 030 kN** · Interior: **1 494 kN**"
    )

# ── Compute profiles ───────────────────────────────────────────────────────
layers = st.session_state.layers
wt = st.session_state.wt_design_bgl
n_pts = 200

z_arr = np.linspace(0.001, z_max, n_pts)

methods_to_plot = (
    ["boussinesq_centre", "boussinesq_corner", "2to1"] if method == "all"
    else [method]
)

traces_data = {}
for m in methods_to_plot:
    _, ds = stress_profile(q_net, B, L, z_max, method=m, n_points=n_pts)
    traces_data[m] = ds

profile_bottom = max(float(lyr["depth_bot"]) for lyr in layers)
valid_eff_stress = (z_arr + Df) <= profile_bottom
eff_stress = np.full(z_arr.shape, np.nan, dtype=float)
if np.any(valid_eff_stress):
    eff_stress[valid_eff_stress] = effective_stress_profile(
        layers, wt, z_arr[valid_eff_stress], Df=Df
    )
if not np.all(valid_eff_stress):
    st.info(
        f"The soil profile ends at {profile_bottom:.2f} m below ground. "
        "Stress increase is plotted to the selected depth; effective stress "
        "is shown only within the entered profile."
    )

# Influence depth (Boussinesq centre)
z_inf = influence_depth(q_net, B, L, threshold=0.1,
                        method="boussinesq_centre")

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

if show_eff_stress:
    fig.add_trace(go.Scatter(
        x=eff_stress, y=z_arr,
        mode="lines", name="Effective stress σ′v₀ (kPa)",
        line=dict(color="grey", width=1.5, dash="dot"),
    ))

# Mark influence depth
if z_inf <= z_max:
    fig.add_hline(y=z_inf, line_dash="dash", line_color="red",
                  annotation_text=f"10% influence depth  z* = {z_inf:.2f} m",
                  annotation_position="right")

# Mark layer boundaries
for lyr in layers:
    zb = lyr["depth_bot"] - Df
    if 0 < zb <= z_max:
        fig.add_hline(y=zb, line_dash="dot", line_color="#aaa",
                      annotation_text=lyr.get("name", lyr["symbol"]),
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
col2.metric("10% influence depth  z*", f"{z_inf:.2f} m")
col3.metric("2B depth (Schmertmann limit)", f"{2*B:.2f} m")
col4.metric("Footing area  B × L", f"{B*L:.2f} m²")

# ── Data table ─────────────────────────────────────────────────────────────
st.subheader("📋 Stress Increase Table")
z_table = np.arange(0.0, z_max + 0.25, 0.25)
z_table = z_table[z_table > 0]

rows = []
for z in z_table:
    ds_centre = stress_increase_centre(q_net, B, L, z)
    ds_corner = boussinesq_corner(q_net, B, L, z)
    ds_21 = stress_increase_2to1(q_net, B, L, z)
    sv0 = (
        effective_stress_profile(layers, wt, np.array([z]), Df=Df)[0]
        if z + Df <= profile_bottom
        else np.nan
    )
    rows.append({
        "Depth below footing  z (m)": round(float(z), 2),
        "Δσz — Centre (kPa)": round(float(ds_centre), 2),
        "Δσz — Corner (kPa)": round(float(ds_corner), 2),
        "Δσz — 2:1 (kPa)": round(float(ds_21), 2),
        "σ′v₀ (kPa)": round(float(sv0), 2),
        "Δσz/q — Centre": round(float(ds_centre / q_net), 3),
    })

df_table = pd.DataFrame(rows)
st.dataframe(df_table, use_container_width=True, hide_index=True)

# ── Superposition tool ─────────────────────────────────────────────────────
with st.expander("🔀 Superposition Tool — multiple loaded areas"):
    st.write(
        "Add several footings (each with its own B, L, q, and plan offsets). "
        "The offsets locate each footing's near corner from the observation point "
        "at (0, 0); the tool sums the stress at that point."
    )
    if "superpos_areas" not in st.session_state:
        st.session_state.superpos_areas = [
            {"B": B, "L": L, "q": q_net, "xoff": 0.0, "yoff": 0.0}
        ]

    sp_areas = st.session_state.superpos_areas
    to_delete = None
    for idx, area in enumerate(sp_areas):
        c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1.5, 1.5, 1.5, 1.5, 0.6])
        area["B"] = c1.number_input(f"B{idx+1} (m)", value=area["B"],
                                    min_value=0.1, key=f"sp_B_{idx}")
        area["L"] = c2.number_input(f"L{idx+1} (m)", value=area["L"],
                                    min_value=0.1, key=f"sp_L_{idx}")
        area["q"] = c3.number_input(f"q{idx+1} (kPa)", value=area["q"],
                                    min_value=0.1, key=f"sp_q_{idx}")
        area["xoff"] = c4.number_input(f"Near-corner x{idx+1} (m)", value=area["xoff"],
                                       key=f"sp_xoff_{idx}")
        area["yoff"] = c5.number_input(f"Near-corner y{idx+1} (m)", value=area["yoff"],
                                       key=f"sp_yoff_{idx}")
        if c6.button("✕", key=f"sp_del_{idx}"):
            to_delete = idx
    if to_delete is not None:
        st.session_state.superpos_areas.pop(to_delete)
        st.rerun()
    if st.button("+ Add loaded area"):
        st.session_state.superpos_areas.append(
            {"B": 2.0, "L": 2.0, "q": 100.0, "xoff": 5.0, "yoff": 0.0}
        )
        st.rerun()

    # Compute superposed profile
    z_sp = np.linspace(0.001, z_max, 200)
    ds_total = np.zeros_like(z_sp)
    for area in sp_areas:
        for i, z in enumerate(z_sp):
            # Offsets locate the near corner relative to observation point (0, 0).
            ds_total[i] += stress_increase_point(
                area["q"], area["B"], area["L"],
                -area["xoff"], -area["yoff"], z,
            )

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
        "It is less accurate than the Boussinesq solution, so check it against that result."
    )
