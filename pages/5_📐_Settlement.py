"""
P5 — Settlement Analysis
Immediate settlement by the Schmertmann et al. (1978) strain influence factor method
(granular layers) and 1D consolidation settlement (Terzaghi 1943) for clay layers.
IS 1904:1986 compliance check for RC framed buildings.

Sources:
  - Schmertmann, Hartman & Brown (1978) JGED ASCE
  - Terzaghi (1943) Theoretical Soil Mechanics
  - IS 8009:1976 Part 1 — Calculation of settlements of foundations
  - IS 1904:1986 — Code of practice for design and construction of foundations
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from utils.constants import init_session_state
from utils.settlement import (
    schmertmann_settlement,
    total_consolidation_settlement,
    time_settlement_curve,
)

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(page_title="P5 – Settlement", page_icon="📐", layout="wide")
init_session_state()

st.title("📐 P5 — Settlement Analysis")
st.caption(
    "Immediate (Schmertmann 1978) + Consolidation (Terzaghi 1943) · "
    "IS 8009:1976 · IS 1904:1986"
)

# ── IS 1904:1986 limits for RC framed buildings ────────────────────────────
IS_TOTAL_LIMIT_MM    = 50.0   # mm — IS 1904:1986 Table 1 (sand) / 65 mm (clay)
IS_DIFF_LIMIT_RATIO  = 1/500  # angular distortion limit
SPAN_M               = 5.0    # column grid spacing (m)
IS_DIFF_LIMIT_MM     = SPAN_M * 1000 * IS_DIFF_LIMIT_RATIO   # = 10 mm

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Footing Parameters")
    B    = st.number_input("Width  B (m)",     value=2.0,  min_value=0.1, step=0.1,  key="p5_B")
    L    = st.number_input("Length  L (m)",    value=2.0,  min_value=0.1, step=0.1,  key="p5_L")
    Df   = st.number_input("Depth  Df (m)",    value=1.5,  min_value=0.0, step=0.1,  key="p5_Df")
    P_kN = st.number_input("Column load  P (kN)", value=1030.0, min_value=1.0, step=10.0, key="p5_P")
    t_yr = st.number_input("Design life  t (years)", value=50, min_value=1, step=5, key="p5_t")

    st.markdown("---")
    st.subheader("Drainage Conditions")
    drainage = st.radio("Clay layer drainage", ["Two-way (double)", "One-way (single)"],
                        key="p5_drain")
    clay_H_override = st.number_input(
        "Clay layer thickness  H (m) — override (0 = auto)",
        value=0.0, min_value=0.0, step=0.1, key="p5_H_clay"
    )
    cv_override = st.number_input(
        "cv (m²/s) — override (0 = use layer value)",
        value=0.0, min_value=0.0, step=1e-9, format="%.2e", key="p5_cv"
    )

    st.markdown("---")
    st.subheader("IS 1904:1986 Limits (RC Frame)")
    st.info(
        f"**Total settlement** ≤ {IS_TOTAL_LIMIT_MM:.0f} mm\n\n"
        f"**Differential settlement** ≤ span/500 = {IS_DIFF_LIMIT_MM:.1f} mm\n\n"
        f"**Angular distortion** ≤ 1/500\n\n"
        f"*(IS 1904:1986 Table 1)*"
    )
    st.markdown("---")
    st.info(
        "**λ = 1.03** (group g = 3)\n\n"
        "Corner: **669 kN** · Edge: **1 030 kN** · Interior: **1 494 kN**"
    )

# ── Retrieve session state ─────────────────────────────────────────────────
layers = st.session_state.layers
wt     = st.session_state.wt_design_bgl

# ── Run calculations ───────────────────────────────────────────────────────
imm_result  = schmertmann_settlement(layers, Df, B, L, P_kN, wt, t_years=t_yr)
cons_result = total_consolidation_settlement(layers, Df, B, L, P_kN, wt)

S_i_mm = imm_result["S_mm"]
S_c_mm = cons_result["S_total_mm"]
S_tot_mm = S_i_mm + S_c_mm

# Determine cv and Hdr for time-settlement curve
clay_layers = [lyr for lyr in layers if lyr.get("is_clay") and lyr.get("cv_m2s")]
if clay_layers:
    cv_use = cv_override if cv_override > 0 else clay_layers[0].get("cv_m2s", 6.3e-8)
    if clay_H_override > 0:
        H_clay = clay_H_override
    else:
        H_clay = sum(
            max(0, lyr["depth_bot"] - max(lyr["depth_top"], Df))
            for lyr in layers if lyr.get("is_clay")
        )
        H_clay = max(H_clay, 0.1)
else:
    cv_use = cv_override if cv_override > 0 else 6.3e-8
    H_clay = clay_H_override if clay_H_override > 0 else 2.0

Hdr = H_clay / 2.0 if drainage == "Two-way (double)" else H_clay
t_yr_arr, S_t_mm = time_settlement_curve(S_c_mm / 1000.0, cv_use, Hdr,
                                          t_max_years=float(t_yr), n_points=300)

# ── Summary metrics at top ─────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)

def metric_color(val, limit):
    return "🟢" if val <= limit else "🔴"

c1.metric("Immediate  Sᵢ", f"{S_i_mm:.1f} mm",
          delta="Schmertmann (1978)", delta_color="off")
c2.metric("Consolidation  Sc", f"{S_c_mm:.1f} mm",
          delta="Terzaghi (1943)", delta_color="off")
c3.metric("Total  S = Sᵢ + Sc", f"{S_tot_mm:.1f} mm",
          delta=f"{metric_color(S_tot_mm, IS_TOTAL_LIMIT_MM)} Limit = {IS_TOTAL_LIMIT_MM:.0f} mm",
          delta_color="off")

st.markdown("---")

# ── Tabs ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "⚡ Immediate Settlement (Schmertmann)",
    "🧱 Consolidation Settlement (1D)",
    "✅ Summary & IS 1904:1986 Check",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — Schmertmann Immediate Settlement
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Immediate Settlement — Schmertmann et al. (1978)")
    st.caption("Strain influence factor method · granular (sand/gravel) layers only")

    # Correction factors
    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("Net pressure  Δp", f"{imm_result['delta_p']:.1f} kPa")
    cc2.metric("C₁  (embedment)", f"{imm_result['C1']:.4f}",
               help="C₁ = 1 − 0.5·(σ′v₀/Δp) ≥ 0.5  [Schmertmann 1978]")
    cc3.metric("C₂  (creep)",     f"{imm_result['C2']:.4f}",
               help=f"C₂ = 1 + 0.2·log₁₀(t/0.1), t = {t_yr} yr  [Schmertmann 1978]")
    cc4.metric("Iz_peak",         f"{imm_result['Iz_peak']:.4f}",
               help="Iz_peak = 0.5 + 0.1·√(Δp/σ′v₀·₅B)  [Schmertmann 1978 Fig. 4]")

    st.metric("**Total immediate settlement  Sᵢ**", f"**{S_i_mm:.2f} mm**")

    # Sublayer table
    sub = imm_result["sublayer_data"]
    if sub:
        df_sub = pd.DataFrame(sub)
        df_sub.rename(columns={
            "z_top_m": "z_top (m)",
            "z_bot_m": "z_bot (m)",
            "z_mid_m": "z_mid (m)",
            "layer_name": "Layer",
            "symbol": "Symbol",
            "Es_kPa": "Es (kPa)",
            "Iz": "Iz",
            "Iz_over_Es": "Iz/Es (m/kPa)",
            "dz_m": "Δz (m)",
            "contrib_m": "Iz/Es·Δz (m)",
        }, inplace=True)
        st.dataframe(df_sub, use_container_width=True, hide_index=True)

        # Bar chart — contributions by sublayer
        fig_bar = px.bar(
            df_sub,
            x="Iz/Es·Δz (m)", y="z_mid (m)",
            orientation="h",
            color="Layer",
            labels={"z_mid (m)": "Depth below footing (m)", "Iz/Es·Δz (m)": "Contribution (m)"},
            title="Contribution of each sublayer to Sᵢ",
        )
        fig_bar.update_layout(yaxis=dict(autorange="reversed"), height=400)
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.warning(
            "No granular sublayers found in the stress influence zone (0 to 2B below footing). "
            "Check that your soil profile has SM, SP, GW, etc. layers with N values entered."
        )

    with st.expander("📐 Formula — Schmertmann (1978)"):
        st.markdown(r"""
$$S_i = C_1 \cdot C_2 \cdot \Delta p \sum_{j} \frac{I_{z,j}}{E_{s,j}} \Delta z_j$$

where:
- $C_1 = 1 - 0.5\,(\sigma'_{v0}/\Delta p) \geq 0.5$ — embedment correction
- $C_2 = 1 + 0.2\,\log_{10}(t/0.1)$ — creep correction ($t$ in years)
- $I_{z,\text{peak}} = 0.5 + 0.1\sqrt{\Delta p / \sigma'_{v,\,0.5B}}$ — peak strain influence factor
- $E_s = 500(N_{60}+15)$ kPa for sand *(Meyerhof 1956)*

*Cite: Schmertmann, Hartman & Brown (1978) JGED ASCE; IS 8009:1976 Part 1*
        """)

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — 1D Consolidation Settlement
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("1D Consolidation Settlement — Terzaghi (1943)")
    st.caption("IS 8009:1976 Part 1 · sublayers ≤ 0.5 m")

    st.metric("**Total consolidation settlement  Sc**", f"**{S_c_mm:.2f} mm**")

    # Sublayer table
    sub_c = cons_result["sublayer_data"]
    if sub_c:
        df_c = pd.DataFrame(sub_c)
        df_c.rename(columns={
            "z_mid_bgl_m": "Depth bgl (m)",
            "z_below_footing_m": "z below footing (m)",
            "layer_name": "Layer",
            "sigma_v0_kPa": "σ′v₀ (kPa)",
            "delta_sigma_kPa": "Δσ (kPa)",
            "sigma_f_kPa": "σ′vf (kPa)",
            "Pc_kPa": "Pc (kPa)",
            "case": "Case",
            "Sc_mm": "Sc (mm)",
            "dz_m": "Δz (m)",
        }, inplace=True)

        # Colour-code case column
        def style_case(val):
            if val == "NC":
                return "background-color: #ffdede"
            elif val == "OC":
                return "background-color: #d6f0d6"
            elif val == "OC→NC":
                return "background-color: #fff3cc"
            return ""

        st.dataframe(
            df_c.style.applymap(style_case, subset=["Case"]),
            use_container_width=True, hide_index=True
        )
    else:
        st.info("No clay layers with consolidation parameters found in the profile. "
                "Add clay layers in P1 and tick 'Clay (consolidation settlement)', "
                "then enter Cc, Cr, e₀, Pc, and cv.")

    # e–log p diagram
    clay_layers_with_params = [
        lyr for lyr in layers
        if lyr.get("is_clay") and lyr.get("Cc") and lyr.get("e0") and lyr.get("Pc_kPa")
    ]
    if clay_layers_with_params:
        st.subheader("Oedometer e–log p Curve")
        lyr_sel = clay_layers_with_params[0]
        Cc_pl = lyr_sel["Cc"]
        Cr_pl = lyr_sel.get("Cr", 0.06)
        e0_pl = lyr_sel["e0"]
        Pc_pl = lyr_sel["Pc_kPa"]

        # Reconstruct typical e–log p from assignment oedometer data or params
        p_nc = np.logspace(np.log10(Pc_pl), np.log10(max(Pc_pl * 20, 1000)), 50)
        e_nc = e0_pl - Cc_pl * np.log10(p_nc / Pc_pl)

        # Recompression branch (up to Pc)
        p_oc = np.logspace(np.log10(10), np.log10(Pc_pl), 30)
        # estimate initial e at p=10 kPa using Cr
        e_at_start = e0_pl + Cr_pl * np.log10(Pc_pl / 10)
        e_oc = e_at_start - Cr_pl * np.log10(p_oc / 10)

        fig_ep = go.Figure()
        fig_ep.add_trace(go.Scatter(
            x=p_oc, y=e_oc, mode="lines", name="Recompression (Cr)",
            line=dict(color="green", width=2)
        ))
        fig_ep.add_trace(go.Scatter(
            x=p_nc, y=e_nc, mode="lines", name="Virgin compression (Cc)",
            line=dict(color="red", width=2)
        ))
        fig_ep.add_vline(x=Pc_pl, line_dash="dash", line_color="orange",
                         annotation_text=f"Pc = {Pc_pl:.0f} kPa",
                         annotation_position="top right")
        fig_ep.update_layout(
            title=f"e–log p  |  Cc = {Cc_pl:.3f}, Cr = {Cr_pl:.3f}, e₀ = {e0_pl:.3f}",
            xaxis=dict(title="Effective vertical stress p (kPa)", type="log"),
            yaxis_title="Void ratio  e",
            height=400,
        )
        st.plotly_chart(fig_ep, use_container_width=True)

    # Time–settlement curve
    st.subheader("Time–Settlement Curve")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Clay thickness  H", f"{H_clay:.2f} m")
    col_b.metric("Drainage path  Hdr", f"{Hdr:.2f} m",
                 help="H for one-way, H/2 for two-way drainage")
    col_c.metric("cv", f"{cv_use:.2e} m²/s")

    if S_c_mm > 0:
        fig_ts = go.Figure()
        fig_ts.add_trace(go.Scatter(
            x=t_yr_arr, y=S_t_mm,
            mode="lines", name="Consolidation settlement",
            line=dict(color="#1f4e79", width=2.5),
            fill="tozeroy", fillcolor="rgba(31,78,121,0.1)"
        ))
        # Mark 90% and 50% consolidation
        for U_target, label, col_line in [(0.9, "U = 90%", "red"), (0.5, "U = 50%", "orange")]:
            # find time
            idx = np.where(S_t_mm >= U_target * S_c_mm)[0]
            if len(idx):
                t_tgt = t_yr_arr[idx[0]]
                fig_ts.add_vline(x=t_tgt, line_dash="dash", line_color=col_line,
                                 annotation_text=f"{label}  t = {t_tgt:.1f} yr",
                                 annotation_position="top right")
        fig_ts.add_hline(y=S_c_mm, line_dash="dot", line_color="grey",
                         annotation_text=f"Sc = {S_c_mm:.1f} mm",
                         annotation_position="right")
        fig_ts.update_layout(
            title="Time–Settlement Curve (Consolidation Component)",
            xaxis_title="Time (years)",
            yaxis_title="Settlement (mm)",
            height=400,
        )
        st.plotly_chart(fig_ts, use_container_width=True)
    else:
        st.info("No consolidation settlement to plot (Sc = 0 mm).")

    with st.expander("📐 Formulae — 1D Consolidation"):
        st.markdown(r"""
**NC clay:** $S_c = \dfrac{C_c}{1+e_0} H \log_{10}\!\left(\dfrac{\sigma'_{v0}+\Delta\sigma}{\sigma'_{v0}}\right)$

**OC clay (stays OC):** $S_c = \dfrac{C_r}{1+e_0} H \log_{10}\!\left(\dfrac{\sigma'_{v0}+\Delta\sigma}{\sigma'_{v0}}\right)$

**OC→NC (crosses $p_c$):** $S_c = \dfrac{C_r}{1+e_0} H \log_{10}\!\left(\dfrac{p_c}{\sigma'_{v0}}\right) + \dfrac{C_c}{1+e_0} H \log_{10}\!\left(\dfrac{\sigma'_{v0}+\Delta\sigma}{p_c}\right)$

**Degree of consolidation:**
$$U = \sqrt{\frac{4T_v}{\pi}} \quad (U \leq 0.6) \qquad U = 1 - \frac{8}{\pi^2}e^{-\pi^2 T_v/4} \quad (U > 0.6)$$

where $T_v = c_v t / H_{dr}^2$

*Cite: Terzaghi (1943); Das (2016) Eq. 7.21-7.23, 7.56-7.57; IS 8009:1976 Part 1*
        """)

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — Summary & IS 1904:1986 Check
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("IS 1904:1986 — Settlement Compliance Check (RC Framed Building)")

    # ── Total settlement check ──
    st.markdown("### 1. Total Settlement")
    st.markdown(f"**IS 1904:1986 Table 1** — RC framed building on isolated footings: "
                f"≤ **{IS_TOTAL_LIMIT_MM:.0f} mm** (sand/silt) or ≤ 65 mm (clay)")

    result_col1, result_col2 = st.columns(2)
    with result_col1:
        status_total = "🟢 PASS" if S_tot_mm <= IS_TOTAL_LIMIT_MM else "🔴 FAIL"
        st.metric(
            "Total settlement  S",
            f"{S_tot_mm:.1f} mm",
            delta=status_total,
            delta_color="normal" if S_tot_mm <= IS_TOTAL_LIMIT_MM else "inverse"
        )
        if S_tot_mm > IS_TOTAL_LIMIT_MM:
            st.error(
                f"Total settlement **{S_tot_mm:.1f} mm** exceeds IS 1904:1986 limit of "
                f"{IS_TOTAL_LIMIT_MM:.0f} mm. Consider: larger footing, deeper founding level, "
                "or raft/pile foundation."
            )
    with result_col2:
        st.info(
            f"Sᵢ (immediate) = **{S_i_mm:.1f} mm**\n\n"
            f"Sc (consolidation) = **{S_c_mm:.1f} mm**\n\n"
            f"S (total) = **{S_tot_mm:.1f} mm**"
        )

    st.markdown("---")

    # ── Differential settlement & angular distortion ──
    st.markdown("### 2. Differential Settlement & Angular Distortion")
    st.markdown(
        f"**IS 1904:1986 Table 2** — maximum differential settlement = span/500 = "
        f"{SPAN_M * 1000:.0f} mm / 500 = **{IS_DIFF_LIMIT_MM:.1f} mm**\n\n"
        f"Angular distortion β = δ / L ≤ **1/500 = 0.002**"
    )

    # Estimate settlement for each column type
    col_loads = {
        "Corner":   650 * 1.03,
        "Edge":     1000 * 1.03,
        "Interior": 1450 * 1.03,
    }

    col_settlements = {}
    for ctype, P in col_loads.items():
        r_i = schmertmann_settlement(layers, Df, B, L, P, wt, t_years=t_yr)
        r_c = total_consolidation_settlement(layers, Df, B, L, P, wt)
        col_settlements[ctype] = r_i["S_mm"] + r_c["S_total_mm"]

    rows_diff = []
    pairs = [
        ("Corner", "Edge"),
        ("Edge", "Interior"),
        ("Corner", "Interior"),
    ]
    for a, b_type in pairs:
        Sa = col_settlements[a]
        Sb = col_settlements[b_type]
        delta = abs(Sa - Sb)
        ang = delta / (SPAN_M * 1000)
        pass_diff = delta <= IS_DIFF_LIMIT_MM
        pass_ang = ang <= IS_DIFF_LIMIT_RATIO
        rows_diff.append({
            "Pair": f"{a} ↔ {b_type}",
            f"S_{a} (mm)": round(Sa, 1),
            f"S_{b_type} (mm)": round(Sb, 1),
            "δ differential (mm)": round(delta, 1),
            "Angular distortion β": f"1/{int(1/ang) if ang > 0 else '∞'}",
            "Differential check": "🟢 PASS" if pass_diff else "🔴 FAIL",
            "Angular distortion check": "🟢 PASS" if pass_ang else "🔴 FAIL",
        })

    df_diff = pd.DataFrame(rows_diff)
    st.dataframe(df_diff, use_container_width=True, hide_index=True)

    # Settlement by column type
    st.markdown("#### Settlement by Column Type")
    fig_col = go.Figure(go.Bar(
        x=list(col_settlements.keys()),
        y=list(col_settlements.values()),
        marker_color=["#2980b9", "#e67e22", "#e74c3c"],
        text=[f"{v:.1f} mm" for v in col_settlements.values()],
        textposition="outside",
    ))
    fig_col.add_hline(y=IS_TOTAL_LIMIT_MM, line_dash="dash", line_color="red",
                      annotation_text=f"IS 1904 limit = {IS_TOTAL_LIMIT_MM:.0f} mm")
    fig_col.update_layout(
        title="Total Settlement by Column Type (λ = 1.03, g = 3)",
        yaxis_title="Total settlement (mm)",
        height=350,
    )
    st.plotly_chart(fig_col, use_container_width=True)

    st.markdown("---")

    # ── Overall verdict ──
    st.markdown("### 3. Overall Verdict")
    all_pass = (
        S_tot_mm <= IS_TOTAL_LIMIT_MM
        and all(abs(col_settlements[a] - col_settlements[b_type]) <= IS_DIFF_LIMIT_MM
                for a, b_type in pairs)
    )
    if all_pass:
        st.success(
            "✅ **All IS 1904:1986 checks PASS.**\n\n"
            "Isolated square footings are adequate for settlement at the given footing size."
        )
    else:
        st.error(
            "❌ **One or more IS 1904:1986 checks FAIL.**\n\n"
            "Consider the following alternatives:\n"
            "1. **Increase footing size** — reduces net pressure, reduces settlement\n"
            "2. **Increase founding depth** to avoid the soft clay layer\n"
            "3. **Raft foundation** — spreads load, reduces differential settlement\n"
            "4. **Piled foundation** — bypass the soft CI clay, bear in the GW gravel layer\n"
            "5. **Soil improvement** — preloading, stone columns, vibro-compaction"
        )

    with st.expander("📋 IS 1904:1986 Limits Reference"):
        st.markdown("""
| Foundation type | Soil | Total settlement | Differential | Angular distortion |
|---|---|---|---|---|
| Isolated footing — RC frame | Sand/hard clay | 50 mm | L/500 | 1/500 |
| Isolated footing — RC frame | Soft clay | 65 mm | L/500 | 1/500 |
| Raft — RC frame | Sand | 75 mm | L/500 | 1/500 |
| Raft — RC frame | Clay | 100 mm | L/500 | 1/500 |

*Source: IS 1904:1986 Table 1 & Table 2*
        """)
