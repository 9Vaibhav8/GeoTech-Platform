"""
pages/4_📊_Stress_Increase.py
P4 — Vertical Stress Increase beneath Shallow Footings
Computes vertical stress increase below a uniformly loaded rectangle using
branch-safe Boussinesq (1885) / Newmark (1935) superposition and the 2:1 method.
All units strictly SI: m, kN, kPa.

Sources:
  - Boussinesq (1885) — exact elastic solution for point load on half-space
  - Newmark (1935) — rectangular area corner formula & quadrant superposition
  - Das, B.M. — Principles of Foundation Engineering, Ch. 10, Eq. 10.33
  - IS 8009:1976 Part 1 — Code of practice for calculation of settlements of foundations
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.constants import init_session_state
from utils.stress_increase import (
    boussinesq_corner,
    boussinesq_rectangle_at_point,
    effective_stress_profile,
    influence_depth,
    stress_increase_2to1,
    stress_increase_centre,
    stress_profile,
)

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(page_title="P4 — Stress Increase", page_icon="📊", layout="wide")
init_session_state()

st.title("📊 P4 — Vertical Stress Increase")
st.caption(
    "Boussinesq (1885) / Newmark (1935) rectangular load superposition & 2:1 method · "
    "IS 8009:1976 Part 1 | SI units: m, kN, kPa"
)

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Footing & Load Inputs")

    B = st.number_input("Footing width B (m)", value=2.0, min_value=0.1, step=0.1, key="p4_B")
    L = st.number_input("Footing length L (m)", value=2.0, min_value=0.1, step=0.1, key="p4_L")
    Df = st.number_input("Founding depth Df (m)", value=1.5, min_value=0.0, step=0.1, key="p4_Df")

    input_mode = st.radio(
        "Load input mode",
        ["Net column load P (kN)", "Net pressure q (kPa)"],
        key="p4_input_mode",
    )
    if input_mode == "Net column load P (kN)":
        P_kN = st.number_input("Net vertical load P (kN)", value=1000.0, min_value=1.0, step=10.0, key="p4_P")
        # Source: Uniform footing contact pressure q = P / (B * L)
        q_net = P_kN / (B * L)
        st.metric("Net bearing pressure q (kPa)", f"{q_net:.2f} kPa")
    else:
        q_net = st.number_input("Net bearing pressure q (kPa)", value=250.0, min_value=1.0, step=5.0, key="p4_q")

    st.markdown("---")
    method_opts = {
        "Boussinesq — Centre": "boussinesq_centre",
        "Boussinesq — Corner": "boussinesq_corner",
        "2:1 Method": "2to1",
        "All three": "all",
    }
    method_label = st.selectbox("Distribution method", list(method_opts.keys()), key="p4_method")
    method = method_opts[method_label]

    z_max_factor = st.slider("Plot depth below footing (× B)", 1.0, 6.0, 3.0, 0.5, key="p4_zmaxfac")
    z_max = z_max_factor * B

    show_eff_stress = st.checkbox("Overlay effective overburden σ′v₀ (kPa)", value=True, key="p4_show_sv")

# ── Compute single-footing profiles ────────────────────────────────────────
layers = st.session_state.layers
wt = float(st.session_state.wt_design_bgl)
n_pts = 200

z_arr = np.concatenate(([0.0], np.linspace(0.001, z_max, n_pts)))

methods_to_plot = (
    ["boussinesq_centre", "boussinesq_corner", "2to1"] if method == "all" else [method]
)

traces_data = {}
for m in methods_to_plot:
    _, ds = stress_profile(q_net, B, L, z_max, method=m, n_points=n_pts)
    traces_data[m] = ds

eff_stress = effective_stress_profile(layers, wt, z_arr, Df=Df)

z_inf = influence_depth(
    q_net,
    B,
    L,
    threshold=0.1,
    method="boussinesq_centre",
    n_points=500,
)

# ── Stress vs depth figure ─────────────────────────────────────────────────
colour_map = {
    "boussinesq_centre": "#1f4e79",
    "boussinesq_corner": "#e67e22",
    "2to1": "#27ae60",
}
label_map = {
    "boussinesq_centre": "Boussinesq — Centre (kPa)",
    "boussinesq_corner": "Boussinesq — Corner (kPa)",
    "2to1": "2:1 Method (kPa)",
}

fig = go.Figure()
for m, ds in traces_data.items():
    fig.add_trace(go.Scatter(
        x=ds,
        y=z_arr,
        mode="lines",
        name=label_map[m],
        line=dict(color=colour_map[m], width=2.5),
    ))

if show_eff_stress:
    fig.add_trace(go.Scatter(
        x=eff_stress,
        y=z_arr,
        mode="lines",
        name="Effective overburden σ′v₀ (kPa)",
        line=dict(color="grey", width=1.5, dash="dot"),
    ))

if z_inf <= z_max:
    fig.add_hline(
        y=z_inf,
        line_dash="dash",
        line_color="red",
        annotation_text=f"10% influence depth z* = {z_inf:.2f} m",
        annotation_position="right",
    )

for lyr in layers:
    zb = float(lyr["depth_bot"]) - Df
    if 0.0 < zb <= z_max:
        fig.add_hline(
            y=zb,
            line_dash="dot",
            line_color="#aaaaaa",
            annotation_text=lyr.get("name", lyr["symbol"]),
            annotation_position="right",
            annotation_font_size=10,
        )

wt_below_footing = wt - Df
if 0.0 < wt_below_footing <= z_max:
    fig.add_hline(
        y=wt_below_footing,
        line_dash="dashdot",
        line_color="blue",
        annotation_text=f"Design WT ({wt:.2f} m bgl)",
        annotation_position="right",
    )

fig.update_layout(
    title=f"Vertical Stress Increase below Footing ({B:.2f} m × {L:.2f} m, q = {q_net:.2f} kPa)",
    xaxis_title="Vertical Stress / Stress Increase (kPa)",
    yaxis_title="Depth below footing base z (m)",
    yaxis=dict(autorange="reversed"),
    legend=dict(x=0.62, y=0.98),
    height=580,
    margin=dict(l=60, r=130, t=60, b=60),
)
st.plotly_chart(fig, use_container_width=True)

# ── Key metrics ────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Net bearing pressure q", f"{q_net:.2f} kPa")
col2.metric("10% influence depth z*", f"{z_inf:.2f} m")
col3.metric("2B depth (Schmertmann)", f"{2.0 * B:.2f} m")
col4.metric("Footing area B × L", f"{B * L:.2f} m²")

# ── Data table ─────────────────────────────────────────────────────────────
st.subheader("📋 Stress Increase Table")
z_table = np.arange(0.25, z_max + 0.001, 0.25)

rows = []
for z in z_table:
    ds_centre = stress_increase_centre(q_net, B, L, float(z))
    ds_corner = boussinesq_corner(q_net, B, L, float(z))
    ds_21 = stress_increase_2to1(q_net, B, L, float(z))
    sv0 = effective_stress_profile(layers, wt, [float(z)], Df=Df)[0]
    rows.append({
        "Depth below footing z (m)": round(float(z), 2),
        "Δσz — Centre (kPa)": round(float(ds_centre), 2),
        "Δσz — Corner (kPa)": round(float(ds_corner), 2),
        "Δσz — 2:1 (kPa)": round(float(ds_21), 2),
        "σ′v₀ (kPa)": round(float(sv0), 2),
        "Δσz / q — Centre (—)": round(float(ds_centre / q_net), 4),
    })

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── True Multi-Footing Superposition Tool ──────────────────────────────────
with st.expander("🔀 Multi-Footing Superposition Tool (Exact Signed-Quadrant Boussinesq)", expanded=True):
    st.markdown(
        "Specify multiple uniformly loaded rectangular footings by their centre coordinates "
        "`(x_center, y_center)` in metres, dimensions `B_x (m) × L_y (m)`, and net pressure `q (kPa)`. "
        "Superposed $\\Delta\\sigma_z$ is evaluated at the target plan point `(x_eval, y_eval)` "
        "using exact signed-quadrant corner superposition."
    )

    eval_c1, eval_c2, eval_c3 = st.columns(3)
    with eval_c1:
        x_eval = st.number_input("Evaluation point x_eval (m)", value=0.0, step=0.25, key="p4_xeval")
    with eval_c2:
        y_eval = st.number_input("Evaluation point y_eval (m)", value=0.0, step=0.25, key="p4_yeval")
    with eval_c3:
        z_check = st.number_input(
            "Check depth below base z_check (m)",
            value=min(2.0, float(z_max)),
            min_value=0.0,
            max_value=float(z_max),
            step=0.25,
            key="p4_zcheck",
        )

    if "superpos_areas" not in st.session_state:
        st.session_state.superpos_areas = [
            {"B": B, "L": L, "q": q_net, "xoff": 0.0, "yoff": 0.0},
            {"B": 2.0, "L": 2.0, "q": 200.0, "xoff": 5.0, "yoff": 0.0},
        ]

    sp_areas = st.session_state.superpos_areas
    to_delete = None
    for idx, area in enumerate(sp_areas):
        c1, c2, c3, c4, c5, c6 = st.columns([1.4, 1.4, 1.4, 1.4, 1.4, 0.6])
        area["B"] = c1.number_input(
            f"B_x #{idx + 1} (m)", value=float(area["B"]), min_value=0.1, step=0.1, key=f"sp_B_{idx}"
        )
        area["L"] = c2.number_input(
            f"L_y #{idx + 1} (m)", value=float(area["L"]), min_value=0.1, step=0.1, key=f"sp_L_{idx}"
        )
        area["q"] = c3.number_input(
            f"q #{idx + 1} (kPa)", value=float(area["q"]), min_value=0.0, step=5.0, key=f"sp_q_{idx}"
        )
        area["xoff"] = c4.number_input(
            f"x_center #{idx + 1} (m)", value=float(area["xoff"]), step=0.25, key=f"sp_xoff_{idx}"
        )
        area["yoff"] = c5.number_input(
            f"y_center #{idx + 1} (m)", value=float(area["yoff"]), step=0.25, key=f"sp_yoff_{idx}"
        )
        if c6.button("✕", key=f"sp_del_{idx}") and len(sp_areas) > 1:
            to_delete = idx

    if to_delete is not None:
        st.session_state.superpos_areas.pop(to_delete)
        st.rerun()

    if st.button("➕ Add loaded footing", key="btn_sp_add"):
        st.session_state.superpos_areas.append(
            {"B": 2.0, "L": 2.0, "q": 150.0, "xoff": 5.0, "yoff": 0.0}
        )
        st.rerun()

    # Compute exact superposed Δσz(z) at (x_eval, y_eval)
    z_sp = np.concatenate(([0.0], np.linspace(0.001, z_max, 200)))
    ds_total = np.zeros_like(z_sp)
    per_footing_curves = []

    for idx, area in enumerate(sp_areas):
        ds_single = np.array([
            boussinesq_rectangle_at_point(
                q=area["q"],
                x_center=area["xoff"],
                y_center=area["yoff"],
                B_x=area["B"],
                L_y=area["L"],
                x_pt=x_eval,
                y_pt=y_eval,
                z=float(zi),
            )
            for zi in z_sp
        ])
        ds_total += ds_single
        per_footing_curves.append((f"Footing {idx + 1} ({area['xoff']:.1f}, {area['yoff']:.1f})", ds_single))

    # Breakdown at z_check
    contrib_rows = []
    total_at_zcheck = 0.0
    for idx, area in enumerate(sp_areas):
        ds_val = boussinesq_rectangle_at_point(
            q=area["q"],
            x_center=area["xoff"],
            y_center=area["yoff"],
            B_x=area["B"],
            L_y=area["L"],
            x_pt=x_eval,
            y_pt=y_eval,
            z=float(z_check),
        )
        total_at_zcheck += ds_val
        contrib_rows.append({
            "Footing": f"Footing {idx + 1}",
            "Centre (x, y) (m)": f"({area['xoff']:.2f}, {area['yoff']:.2f})",
            "B_x × L_y (m)": f"{area['B']:.2f} × {area['L']:.2f}",
            "q (kPa)": round(float(area["q"]), 2),
            f"Δσz at z={z_check:.2f} m (kPa)": round(float(ds_val), 3),
        })

    sp_col1, sp_col2 = st.columns([1.2, 1.0])
    with sp_col1:
        fig_sp = go.Figure()
        fig_sp.add_trace(go.Scatter(
            x=ds_total,
            y=z_sp,
            mode="lines",
            name="Total Superposed Δσz (kPa)",
            line=dict(color="#8e44ad", width=3.0),
        ))
        for name_lbl, ds_single in per_footing_curves:
            fig_sp.add_trace(go.Scatter(
                x=ds_single,
                y=z_sp,
                mode="lines",
                name=f"{name_lbl} (kPa)",
                line=dict(width=1.4, dash="dash"),
            ))
        fig_sp.update_layout(
            title=f"Superposed Δσz at (x={x_eval:.2f} m, y={y_eval:.2f} m)",
            xaxis_title="Vertical Stress Increase Δσz (kPa)",
            yaxis_title="Depth below footing base z (m)",
            yaxis=dict(autorange="reversed"),
            height=420,
        )
        st.plotly_chart(fig_sp, use_container_width=True)

    with sp_col2:
        # Plan view of footings and evaluation point
        fig_plan = go.Figure()
        for idx, area in enumerate(sp_areas):
            x0 = area["xoff"] - area["B"] / 2.0
            x1 = area["xoff"] + area["B"] / 2.0
            y0 = area["yoff"] - area["L"] / 2.0
            y1 = area["yoff"] + area["L"] / 2.0
            fig_plan.add_shape(
                type="rect",
                x0=x0, y0=y0, x1=x1, y1=y1,
                line=dict(color="#1f4e79", width=2),
                fillcolor="rgba(31, 78, 121, 0.15)",
            )
            fig_plan.add_annotation(
                x=area["xoff"], y=area["yoff"],
                text=f"F{idx + 1}<br>{area['q']:.0f} kPa",
                showarrow=False,
                font=dict(size=10),
            )
        fig_plan.add_trace(go.Scatter(
            x=[x_eval],
            y=[y_eval],
            mode="markers+text",
            marker=dict(color="red", size=11, symbol="x"),
            text=[f"Eval ({x_eval:.2f}, {y_eval:.2f})"],
            textposition="top center",
            name="Evaluation Point",
        ))
        fig_plan.update_layout(
            title="Plan View (m)",
            xaxis_title="x (m)",
            yaxis_title="y (m)",
            yaxis=dict(scaleanchor="x", scaleratio=1),
            height=420,
            showlegend=False,
        )
        st.plotly_chart(fig_plan, use_container_width=True)

    st.metric(
        f"Total Superposed Δσz at (x={x_eval:.2f} m, y={y_eval:.2f} m, z={z_check:.2f} m)",
        f"{total_at_zcheck:.3f} kPa",
    )
    st.dataframe(pd.DataFrame(contrib_rows), use_container_width=True, hide_index=True)

# ── Theory box ─────────────────────────────────────────────────────────────
with st.expander("📖 Theory — Branch-Safe Boussinesq & 2:1 Equations"):
    st.markdown(r"""
### Boussinesq Rectangular Load — Branch-Safe Formulation (Newmark 1935; Das Ch. 10 Eq. 10.33)

For a uniformly loaded rectangle $B \times L$ with net pressure $q$ (kPa), let $m = B/z$, $n = L/z$, and $r = \sqrt{m^2 + n^2 + 1}$.
The corner influence factor $I_c \in [0,\, 0.25]$ is:

$$\Delta\sigma_z = q \cdot I_c$$

$$I_c = \frac{1}{4\pi}\left[
  \frac{2mn\,r}{m^2+n^2+m^2n^2+1}\cdot\frac{m^2+n^2+2}{m^2+n^2+1}
  + \operatorname{atan2}\!\left(2mn\,r,\; m^2+n^2-m^2n^2+1\right)
\right]$$

Using `atan2(y, x)` guarantees the inverse-tangent term remains continuously in $[0, \pi]$ even when $m^2 n^2 > m^2 + n^2 + 1$ (shallow depths or large footings).

**Arbitrary evaluation point $(x_{\text{pt}}, y_{\text{pt}})$:** For each rectangle $[u_1, u_2] \times [v_1, v_2]$ shifted relative to $(x_{\text{pt}}, y_{\text{pt}})$, signed-quadrant superposition gives:
$$I_{\text{total}} = F(u_2, v_2, z) - F(u_1, v_2, z) - F(u_2, v_1, z) + F(u_1, v_1, z), \quad F(a,b,z) = \operatorname{sign}(a)\operatorname{sign}(b)\,I_c(|a|,|b|,z)$$

---

### 2:1 Approximate Method (IS 8009:1976 Part 1)

$$\Delta\sigma_z = \frac{q \cdot B \cdot L}{(B+z)(L+z)}$$
    """)
