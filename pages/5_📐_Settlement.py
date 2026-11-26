"""
P5 — Settlement Analysis
Immediate settlement : Schmertmann, Hartman & Brown (1978) strain-influence-factor method
Consolidation        : 1-D Terzaghi (1943), NC / OC / OC→NC, sublayers <= 0.5 m
Compliance           : IS 1904:1986 Table 1 (isolated RC footings) on a full column grid

Sources (list these in the report):
  [S78] Schmertmann, Hartman & Brown (1978) JGED ASCE 104(GT8)
  [T43] Terzaghi (1943) Theoretical Soil Mechanics
  [B96] Bowles (1996) Foundation Analysis & Design, 5th ed. — Es = 500(N+15) kPa for sand (after Webb 1969)
  [IS8009] IS 8009 (Part 1):1976 — Calculation of settlements of foundations
  [IS1904] IS 1904:1986 Table 1 — permissible settlement (see utils/is1904.py)

All site values are INPUTS (sidebar / tables). Nothing is hard-coded to the BH-1/2/3 data.
Units: kN, kPa, m, mm, years (cv in m²/s).
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
from utils import is1904 as IS

st.set_page_config(page_title="P5 – Settlement", page_icon="📐", layout="wide")
init_session_state()

SEC_PER_YEAR = 365.25 * 24 * 3600
KGCM2_TO_KPA = 98.0665          # 1 kg/cm² = 98.0665 kPa  (oedometer units on lab sheets)
T50, T90 = 0.197, 0.848         # Tv at U = 50 % / 90 %  [T43; Das]

# ── small UI helpers (work on old and new Streamlit) ───────────────────────
def show_df(obj):
    try:
        st.dataframe(obj, width="stretch", hide_index=True)
    except TypeError:
        st.dataframe(obj, use_container_width=True, hide_index=True)


def show_plot(fig):
    try:
        st.plotly_chart(fig, width="stretch")
    except TypeError:
        st.plotly_chart(fig, use_container_width=True)


st.title("📐 P5 — Settlement Analysis")
st.caption("Immediate (Schmertmann 1978) + Consolidation (Terzaghi 1943) · IS 8009:1976 · IS 1904:1986")

# ═══════════════════════════ SIDEBAR (all inputs) ══════════════════════════
with st.sidebar:
    st.header("⚙️ Global inputs")
    g_group = st.number_input("Group number g (–)", value=3, min_value=0, step=1, key="p5_g",
                              help="λ = 1 + g/100 multiplies every service load")
    lam = IS.lambda_factor(g_group)
    st.caption(f"λ = 1 + g/100 = **{lam:.2f}**")
    Df = st.number_input("Founding depth Df (m)", value=1.5, min_value=0.0, step=0.1, key="p5_Df")
    t_yr = st.number_input("Design life t (years)", value=50, min_value=1, step=5, key="p5_t")

    st.markdown("---")
    st.subheader("Column grid")
    nx = st.number_input("No. of grid lines 1…n (along length)", value=7, min_value=2, max_value=26, step=1, key="p5_nx")
    ny = st.number_input("No. of rows A… (across width)", value=4, min_value=2, max_value=26, step=1, key="p5_ny")
    span_x = st.number_input("Span between grid lines 1,2,… (m)", value=5.0, min_value=0.5, step=0.5, key="p5_sx")
    span_y = st.number_input("Span between rows A,B,… (m)", value=5.0, min_value=0.5, step=0.5, key="p5_sy")
    special_txt = st.text_input("Special column(s) (comma-separated, e.g. C4; blank = none)", value="C4", key="p5_special")

    st.markdown("---")
    st.subheader("Drainage (time curve)")
    drainage = st.radio("Clay layer drainage", ["Two-way (double)", "One-way (single)"], key="p5_drain")
    clay_H_override = st.number_input("Clay thickness H (m) — override (0 = auto)",
                                      value=0.0, min_value=0.0, step=0.1, key="p5_H_clay")
    cv_override = st.number_input("cv (m²/s) — override (0 = layer value)",
                                  value=0.0, min_value=0.0, step=1e-9, format="%.2e", key="p5_cv",
                                  help="Lab sheets give cv in cm²/s: 1 cm²/s = 1e-4 m²/s")

    st.markdown("---")
    st.subheader("IS 1904:1986 limits")
    soil_choice = st.selectbox(
        "Soil governing the total-settlement limit",
        ["Auto (clay if Sc > 0)", "Sand / hard clay", "Plastic clay"], key="p5_soilsel")
    found_type = st.selectbox("Foundation type", ["Isolated footings (RC frame)", "Raft (RC frame)"], key="p5_found")
    LIM_TABLE = IS.ISOLATED_RC if found_type.startswith("Isolated") else IS.RAFT_RC

# ═══════════════════════════ PROFILES / ZONES ══════════════════════════════
# Optional multi-borehole support: st.session_state["boreholes"] =
#   {"BH-1": {"layers": [...], "wt_design_bgl": float}, ...}
# If absent, the single active P1 profile is used for the whole building.
bh_store = st.session_state.get("boreholes")
if isinstance(bh_store, dict) and len(bh_store) >= 1:
    profiles = {k: {"layers": v["layers"], "wt": v.get("wt_design_bgl", st.session_state.wt_design_bgl)}
                for k, v in bh_store.items()}
else:
    profiles = {"Active profile": {"layers": st.session_state.layers, "wt": st.session_state.wt_design_bgl}}

bh_names = sorted(profiles)
chunks = np.array_split(np.arange(1, nx + 1), len(bh_names))
zone_df = pd.DataFrame({
    "Profile": bh_names,
    "First line": [int(c[0]) if len(c) else 1 for c in chunks],
    "Last line": [int(c[-1]) if len(c) else 1 for c in chunks],
})

with st.expander("🗺️ Borehole zoning by grid line (edit to match your justification)", expanded=len(bh_names) > 1):
    if len(bh_names) == 1:
        st.caption("Only one profile is available, so the whole building uses it. "
                   "Differential settlement between boreholes needs `st.session_state['boreholes']` (see code header).")
    zone_ed = st.data_editor(zone_df, hide_index=True, key="p5_zones", disabled=["Profile"],
                             column_config={"First line": st.column_config.NumberColumn(min_value=1, max_value=int(nx), step=1),
                                            "Last line": st.column_config.NumberColumn(min_value=1, max_value=int(nx), step=1)})
zones = [{"name": r["Profile"], "first": int(r["First line"]), "last": int(r["Last line"])}
         for _, r in zone_ed.iterrows()]
unassigned = [i for i in range(1, int(nx) + 1) if IS.zone_of_line(i, zones) is None]
if unassigned:
    st.error(f"Grid lines {unassigned} are not covered by any zone — they fall back to {zones[0]['name']}.")

# ═══════════════════════════ COLUMN TYPES TABLE ════════════════════════════
special_cols = []
for tok in [s for s in special_txt.split(",") if s.strip()]:
    p = IS.parse_name(tok)
    if p is None or not (1 <= p[0] <= nx and 0 <= p[1] < ny):
        st.warning(f"Special column '{tok.strip()}' is not on the grid — ignored.")
    else:
        special_cols.append(p)

rows = ["Corner", "Edge", "Interior"] + (["Special"] if special_cols else [])
default_P = {"Corner": 650.0, "Edge": 1000.0, "Interior": 1450.0, "Special": 1450.0}
default_B = {"Corner": 2.0, "Edge": 2.5, "Interior": 3.0, "Special": 3.0}
type_df = pd.DataFrame({
    "Type": rows,
    "Service P, unfactored (kN)": [default_P[r] for r in rows],
    "B (m)": [default_B[r] for r in rows],
    "L (m)": [default_B[r] for r in rows],
})

st.subheader("Column loads and footing sizes")
auto_size = st.checkbox("Auto-size square footings from a gross bearing pressure", value=False, key="p5_auto")
q_auto = st.number_input("Gross bearing pressure for sizing q (kPa)", value=150.0, min_value=10.0, step=10.0,
                         key="p5_qauto", disabled=not auto_size)
type_ed = st.data_editor(
    type_df, hide_index=True, key="p5_types", disabled=["Type"],
    column_config={
        "Service P, unfactored (kN)": st.column_config.NumberColumn(min_value=1.0, step=10.0),
        "B (m)": st.column_config.NumberColumn(min_value=0.3, step=0.1),
        "L (m)": st.column_config.NumberColumn(min_value=0.3, step=0.1),
    })

TYPE = {}
for _, r in type_ed.iterrows():
    P_des = float(r["Service P, unfactored (kN)"]) * lam          # λ applied to EVERY load
    if auto_size:
        Bt = Lt = IS.sqrt_size(P_des, q_auto)
    else:
        Bt, Lt = float(r["B (m)"]), float(r["L (m)"])
    TYPE[r["Type"]] = {"P_kN": P_des, "B": Bt, "L": Lt}
st.caption("Design loads = service load × λ → " +
           " · ".join(f"{k}: **{v['P_kN']:.0f} kN** ({v['B']:.1f}×{v['L']:.1f} m)" for k, v in TYPE.items()))

# ═══════════════════════════ SETTLEMENT PER (TYPE, ZONE) ═══════════════════
_memo = {}


def settle(ctype, zone):
    key = (ctype, zone)
    if key not in _memo:
        t = TYPE[ctype]
        pf = profiles[zone]
        imm = schmertmann_settlement(pf["layers"], Df, t["B"], t["L"], t["P_kN"], pf["wt"], t_years=t_yr)
        con = total_consolidation_settlement(pf["layers"], Df, t["B"], t["L"], t["P_kN"], pf["wt"])
        _memo[key] = {"imm": imm, "con": con,
                      "Si": imm["S_mm"], "Sc": con["S_total_mm"], "S": imm["S_mm"] + con["S_total_mm"]}
    return _memo[key]


# Column-by-column settlement map
col_type, col_zone, col_S = {}, {}, {}
special_set = set(special_cols)
for j in range(int(ny)):
    for i in range(1, int(nx) + 1):
        ctype = "Special" if (i, j) in special_set else IS.classify(i, j, int(nx), int(ny))
        zone = IS.zone_of_line(i, zones) or zones[0]["name"]
        col_type[(i, j)], col_zone[(i, j)] = ctype, zone
        col_S[(i, j)] = settle(ctype, zone)["S"]

Sc_max_any = max(v["Sc"] for v in _memo.values())
if soil_choice.startswith("Sand"):
    soil_key = "sand"
elif soil_choice.startswith("Plastic"):
    soil_key = "clay"
else:
    soil_key = "clay" if Sc_max_any > 0 else "sand"
LIM = LIM_TABLE[soil_key]
TOTAL_LIMIT = LIM["total_mm"]

# ═══════════════════════════ SELECTED COLUMN (detail tabs) ═════════════════
d1, d2 = st.columns(2)
sel_type = d1.selectbox("Column type to inspect", list(TYPE), key="p5_seltype")
sel_zone = d2.selectbox("Profile to inspect", bh_names, key="p5_selzone")
sel = settle(sel_type, sel_zone)
imm_result, cons_result = sel["imm"], sel["con"]
S_i_mm, S_c_mm, S_tot_mm = sel["Si"], sel["Sc"], sel["S"]
B, L, P_kN = TYPE[sel_type]["B"], TYPE[sel_type]["L"], TYPE[sel_type]["P_kN"]
layers, wt = profiles[sel_zone]["layers"], profiles[sel_zone]["wt"]

# cv and drainage path for the time curve (selected profile)
clay_below = [l for l in layers if l.get("is_clay") and l.get("depth_bot", 0) > Df]
clay_cv = [l for l in clay_below if l.get("cv_m2s")]
cv_default_used = False
if cv_override > 0:
    cv_use = cv_override
elif clay_cv:
    cv_use = clay_cv[0]["cv_m2s"]
else:
    cv_use, cv_default_used = 6.3e-8, True
if clay_H_override > 0:
    H_clay = clay_H_override
else:
    H_clay = sum(max(0.0, l["depth_bot"] - max(l["depth_top"], Df)) for l in clay_below) or 2.0
Hdr = H_clay / 2.0 if drainage.startswith("Two") else H_clay
t50_yr = T50 * Hdr**2 / cv_use / SEC_PER_YEAR
t90_yr = T90 * Hdr**2 / cv_use / SEC_PER_YEAR
t_max = max(float(t_yr), 1.2 * t90_yr)
t_arr, S_t_mm = time_settlement_curve(S_c_mm / 1000.0, cv_use, Hdr, t_max_years=t_max, n_points=300)

m1, m2, m3 = st.columns(3)
m1.metric("Immediate Sᵢ", f"{S_i_mm:.1f} mm", delta="Schmertmann (1978)", delta_color="off")
m2.metric("Consolidation Sc", f"{S_c_mm:.1f} mm", delta="Terzaghi (1943)", delta_color="off")
m3.metric("Total S = Sᵢ + Sc", f"{S_tot_mm:.1f} mm",
          delta=f"{'🟢' if S_tot_mm <= TOTAL_LIMIT else '🔴'} limit {TOTAL_LIMIT:.0f} mm", delta_color="off")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["⚡ Immediate (Schmertmann)", "🧱 Consolidation (1D)", "✅ IS 1904:1986 check"])

# ═══════════════════════════ TAB 1 ═════════════════════════════════════════
with tab1:
    st.subheader("Immediate settlement — Schmertmann et al. (1978)")
    st.caption(f"Strain influence factor · granular layers only · {sel_type} footing {B:.2f}×{L:.2f} m, "
               f"P = {P_kN:.0f} kN, profile {sel_zone}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net pressure Δp", f"{imm_result['delta_p']:.1f} kPa")
    c2.metric("C₁ (embedment)", f"{imm_result['C1']:.4f}", help="C₁ = 1 − 0.5(σ′v0/Δp) ≥ 0.5  [S78]")
    c3.metric("C₂ (creep)", f"{imm_result['C2']:.4f}", help=f"C₂ = 1 + 0.2 log₁₀(t/0.1), t = {t_yr} yr  [S78]")
    c4.metric("Iz,peak", f"{imm_result['Iz_peak']:.4f}",
              help="Iz,peak = 0.5 + 0.1·√(Δp/σ′vp), σ′vp at the depth of the peak (0.5B square, B strip)  [S78]")
    st.metric("Total immediate settlement Sᵢ", f"{S_i_mm:.2f} mm")

    sub = imm_result["sublayer_data"]
    if sub:
        df_sub = pd.DataFrame(sub).rename(columns={
            "z_top_m": "z_top (m)", "z_bot_m": "z_bot (m)", "z_mid_m": "z_mid (m)", "layer_name": "Layer",
            "symbol": "Symbol", "Es_kPa": "Es (kPa)", "Iz": "Iz", "Iz_over_Es": "Iz/Es (1/kPa)",
            "dz_m": "Δz (m)", "contrib_m": "Iz/Es·Δz (m/kPa)"})
        show_df(df_sub)
        fig_bar = px.bar(df_sub, x="Iz/Es·Δz (m/kPa)", y="z_mid (m)", orientation="h", color="Layer",
                         labels={"z_mid (m)": "Depth below footing (m)"},
                         title="Contribution of each sublayer to Sᵢ")
        fig_bar.update_layout(yaxis=dict(autorange="reversed"), height=400)
        show_plot(fig_bar)
    else:
        st.warning("No granular sublayers in the influence zone (2B below a square footing, up to 4B for a strip). "
                   "Check the profile has sand/gravel layers with N values.")

    with st.expander("📐 Formula — Schmertmann (1978)"):
        st.markdown(r"""
$$S_i = C_1\,C_2\,\Delta p \sum_j \frac{I_{z,j}}{E_{s,j}}\,\Delta z_j$$

- $C_1 = 1 - 0.5\,(\sigma'_{v0}/\Delta p) \ge 0.5$ — embedment  *(Schmertmann et al. 1978)*
- $C_2 = 1 + 0.2\log_{10}(t/0.1)$ — creep, $t$ in years  *(Schmertmann et al. 1978)*
- $I_{z,\text{peak}} = 0.5 + 0.1\sqrt{\Delta p/\sigma'_{vp}}$  *(Schmertmann et al. 1978)*
- $E_s = 500\,(N+15)$ kPa for sand  *(Bowles 1996, after Webb 1969 — N corrected per IS 2131 if P2 is used)*

*Cite: Schmertmann, Hartman & Brown (1978) JGED ASCE 104(GT8); IS 8009 (Part 1):1976*
""")

# ═══════════════════════════ TAB 2 ═════════════════════════════════════════
with tab2:
    st.subheader("1-D consolidation settlement — Terzaghi (1943)")
    st.caption("IS 8009 (Part 1):1976 · sublayers ≤ 0.5 m")
    st.metric("Total consolidation settlement Sc", f"{S_c_mm:.2f} mm")

    sub_c = cons_result["sublayer_data"]
    if sub_c:
        df_c = pd.DataFrame(sub_c).rename(columns={
            "z_mid_bgl_m": "Depth bgl (m)", "z_below_footing_m": "z below footing (m)", "layer_name": "Layer",
            "sigma_v0_kPa": "σ′v0 (kPa)", "delta_sigma_kPa": "Δσ (kPa)", "sigma_f_kPa": "σ′vf (kPa)",
            "Pc_kPa": "Pc (kPa)", "case": "Case", "Sc_mm": "Sc (mm)", "dz_m": "Δz (m)"})

        def style_case(val):
            return {"NC": "background-color: #ffdede", "OC": "background-color: #d6f0d6",
                    "OC→NC": "background-color: #fff3cc"}.get(val, "")
        try:
            styled = df_c.style.map(style_case, subset=["Case"])
        except AttributeError:                    # pandas < 2.1
            styled = df_c.style.applymap(style_case, subset=["Case"])
        show_df(styled)
    else:
        st.info("No clay layers with consolidation parameters in this profile "
                "(tick 'Clay' in P1 and enter Cc, Cr, e₀, Pc, cv).")

    # e–log p diagram: e0 is the void ratio at σ′v0 (in situ), NOT at Pc
    with_params = [l for l in layers if l.get("is_clay") and l.get("Cc") and l.get("e0") and l.get("Pc_kPa")]
    if with_params and sub_c:
        st.subheader("e–log p curve")
        ly = with_params[0]
        Cc_pl, e0_pl, Pc_pl = ly["Cc"], ly["e0"], ly["Pc_kPa"]
        Cr_pl = ly.get("Cr") or 0.0
        if not ly.get("Cr"):
            st.warning("Cr not entered for this layer — recompression branch drawn flat (Cr = 0).")
        s0 = float(sub_c[0]["sigma_v0_kPa"]) if "sigma_v0_kPa" in sub_c[0] else float(sub_c[0].get("σ′v0 (kPa)", 1.0))
        s0 = max(s0, 1.0)
        e_pc = e0_pl - Cr_pl * np.log10(max(Pc_pl, s0) / s0)          # e at Pc along recompression
        p_re = np.logspace(np.log10(s0), np.log10(max(Pc_pl, s0 * 1.0001)), 30)
        e_re = e0_pl - Cr_pl * np.log10(p_re / s0)
        p_nc = np.logspace(np.log10(max(Pc_pl, s0)), np.log10(max(Pc_pl, s0) * 20), 50)
        e_nc = e_pc - Cc_pl * np.log10(p_nc / max(Pc_pl, s0))

        fig_ep = go.Figure()
        fig_ep.add_trace(go.Scatter(x=p_re, y=e_re, mode="lines", name="Recompression (Cr)", line=dict(color="green", width=2)))
        fig_ep.add_trace(go.Scatter(x=p_nc, y=e_nc, mode="lines", name="Virgin (Cc)", line=dict(color="red", width=2)))
        fig_ep.add_trace(go.Scatter(x=[s0], y=[e0_pl], mode="markers", name="In situ (σ′v0, e₀)",
                                    marker=dict(size=10, color="black")))
        fig_ep.add_vline(x=Pc_pl, line_dash="dash", line_color="orange",
                         annotation_text=f"Pc = {Pc_pl:.0f} kPa", annotation_position="top right")

        with st.expander("Overlay laboratory oedometer data (optional)"):
            u = st.selectbox("Pressure unit of the table", ["kg/cm²", "kPa"], key="p5_oed_unit")
            oed = st.data_editor(pd.DataFrame({"Pressure": [0.0], "Void ratio e": [0.0]}), num_rows="dynamic",
                                 hide_index=True, key="p5_oed")
            oed = oed[(oed["Pressure"] > 0) & (oed["Void ratio e"] > 0)]
            if len(oed):
                px_kpa = oed["Pressure"] * (KGCM2_TO_KPA if u == "kg/cm²" else 1.0)
                fig_ep.add_trace(go.Scatter(x=px_kpa, y=oed["Void ratio e"], mode="markers+lines",
                                            name="Lab oedometer", line=dict(color="blue", dash="dot")))
        fig_ep.update_layout(title=f"e–log p | Cc = {Cc_pl:.3f}, Cr = {Cr_pl:.3f}, e₀ = {e0_pl:.3f}, σ′v0 = {s0:.0f} kPa",
                             xaxis=dict(title="Effective vertical stress p (kPa)", type="log"),
                             yaxis_title="Void ratio e", height=420)
        show_plot(fig_ep)

    # time–settlement
    st.subheader("Time–settlement curve")
    if cv_default_used:
        st.warning("No cv found for a clay layer below Df — a placeholder cv = 6.3e-8 m²/s is used. "
                   "Enter cv in P1 or use the sidebar override.")
    a, b, c, d = st.columns(4)
    a.metric("Clay thickness H", f"{H_clay:.2f} m")
    b.metric("Drainage path Hdr", f"{Hdr:.2f} m", help="H/2 two-way, H one-way")
    c.metric("cv", f"{cv_use:.2e} m²/s")
    d.metric("t₉₀", f"{t90_yr:.2f} yr", help=f"t = Tv·Hdr²/cv with Tv(90%) = {T90}; t₅₀ = {t50_yr:.2f} yr")
    log_t = st.checkbox("Logarithmic time axis", value=True, key="p5_logt")

    if S_c_mm > 0:
        m = np.asarray(t_arr) > 0
        t_p = np.asarray(t_arr)[m] if log_t else np.asarray(t_arr)
        Sct = np.asarray(S_t_mm)[m] if log_t else np.asarray(S_t_mm)
        fig_ts = go.Figure()
        fig_ts.add_trace(go.Scatter(x=t_p, y=Sct, mode="lines", name="Consolidation Sc(t)", line=dict(color="#1f4e79", width=2.5)))
        fig_ts.add_trace(go.Scatter(x=t_p, y=Sct + S_i_mm, mode="lines", name="Total Sᵢ + Sc(t)",
                                    line=dict(color="#c0392b", width=2, dash="dash")))
        for yrs, lab, col in [(t50_yr, "U = 50%", "orange"), (t90_yr, "U = 90%", "red")]:
            fig_ts.add_vline(x=yrs, line_dash="dash", line_color=col,
                             annotation_text=f"{lab}  t = {yrs:.2f} yr", annotation_position="top right")
        fig_ts.add_hline(y=S_c_mm, line_dash="dot", line_color="grey", annotation_text=f"Sc = {S_c_mm:.1f} mm")
        fig_ts.update_layout(title="Time–settlement (Sᵢ immediate at t = 0)", xaxis_title="Time (years)",
                             yaxis_title="Settlement (mm)", height=420,
                             xaxis=dict(type="log" if log_t else "linear"))
        show_plot(fig_ts)
    else:
        st.info("No consolidation settlement to plot (Sc = 0 mm).")

    with st.expander("📐 Formulae — 1-D consolidation"):
        st.markdown(r"""
**NC:** $S_c = \dfrac{C_c}{1+e_0}H\log_{10}\dfrac{\sigma'_{v0}+\Delta\sigma}{\sigma'_{v0}}$ ·
**OC (stays OC):** same with $C_r$ ·
**OC→NC:** $\dfrac{C_r}{1+e_0}H\log_{10}\dfrac{p_c}{\sigma'_{v0}}+\dfrac{C_c}{1+e_0}H\log_{10}\dfrac{\sigma'_{v0}+\Delta\sigma}{p_c}$

**Time:** $T_v = c_v t/H_{dr}^2$; $U=\sqrt{4T_v/\pi}$ for $U\le 0.6$, $T_v=-0.933\log_{10}(1-U)-0.085$ for $U>0.6$.

*Cite: Terzaghi (1943); IS 8009 (Part 1):1976. Add the exact textbook equation numbers from the edition you used.*
""")

# ═══════════════════════════ TAB 3 ═════════════════════════════════════════
with tab3:
    st.subheader(f"IS 1904:1986 compliance — {found_type}")
    st.markdown(
        f"Limits adopted (**{'plastic clay' if soil_key == 'clay' else 'sand / hard clay'}**): "
        f"total ≤ **{TOTAL_LIMIT:.0f} mm**; differential ≤ **{LIM['diff_ratio']:.4f}·L**; "
        f"angular distortion ≤ **1/{round(1 / LIM['ang_limit'])}**  *(IS 1904:1986 Table 1 — verify against your copy)*")
    st.caption("Differential settlement and angular distortion are taken between **adjacent columns** joined by a grid line; "
               "L is that centre-to-centre distance. For one span δ ≤ 0.0015L and β ≤ 1/666 are the same test.")

    # 1. total
    st.markdown("### 1. Total settlement")
    S_max_key = max(col_S, key=col_S.get)
    S_max = col_S[S_max_key]
    ok_total = S_max <= TOTAL_LIMIT
    t1, t2 = st.columns(2)
    t1.metric("Maximum total settlement", f"{S_max:.1f} mm",
              delta=f"{'🟢 PASS' if ok_total else '🔴 FAIL'} at {IS.column_name(*S_max_key)}", delta_color="off")
    t2.metric("Minimum total settlement", f"{min(col_S.values()):.1f} mm")
    if not ok_total:
        st.error(f"Total settlement {S_max:.1f} mm exceeds {TOTAL_LIMIT:.0f} mm.")

    # settlement per (type, zone)
    st.markdown("#### Settlement by column type and profile")
    rows_tz = []
    for (ct, zn), v in sorted(_memo.items()):
        n_cols = sum(1 for k in col_type if col_type[k] == ct and col_zone[k] == zn)
        if n_cols:
            rows_tz.append({"Type": ct, "Profile": zn, "No. columns": n_cols, "P design (kN)": round(TYPE[ct]["P_kN"], 0),
                            "B×L (m)": f"{TYPE[ct]['B']:.1f}×{TYPE[ct]['L']:.1f}",
                            "Sᵢ (mm)": round(v["Si"], 1), "Sc (mm)": round(v["Sc"], 1), "S total (mm)": round(v["S"], 1)})
    show_df(pd.DataFrame(rows_tz))
    fig_col = go.Figure(go.Bar(x=[f"{r['Type']} / {r['Profile']}" for r in rows_tz],
                               y=[r["S total (mm)"] for r in rows_tz],
                               text=[f"{r['S total (mm)']:.1f} mm" for r in rows_tz], textposition="outside"))
    fig_col.add_hline(y=TOTAL_LIMIT, line_dash="dash", line_color="red",
                      annotation_text=f"IS 1904 limit = {TOTAL_LIMIT:.0f} mm")
    fig_col.update_layout(title=f"Total settlement by column type (λ = {lam:.2f}, g = {g_group})",
                          yaxis_title="Total settlement (mm)", height=380)
    show_plot(fig_col)

    st.markdown("---")
    # 2. differential / angular distortion on the real grid
    st.markdown("### 2. Differential settlement & angular distortion (adjacent columns)")
    pairs = IS.check_pairs(col_S, int(nx), int(ny), span_x, span_y, LIM)
    gov = max(pairs, key=lambda p: p.ratio)
    ok_diff = all(p.ok_diff for p in pairs)
    ok_ang = all(p.ok_ang for p in pairs)
    g1, g2, g3 = st.columns(3)
    g1.metric("Max differential δ", f"{max(p.delta_mm for p in pairs):.1f} mm")
    g2.metric("Max angular distortion β", IS.fmt_ratio(gov.ratio),
              delta=f"{'🟢 PASS' if ok_ang else '🔴 FAIL'} (limit 1/{round(1 / LIM['ang_limit'])})", delta_color="off")
    g3.metric("Governing pair", f"{gov.a} ↔ {gov.b}", help=f"L = {gov.L_m:.1f} m, δ = {gov.delta_mm:.1f} mm")
    df_pairs = pd.DataFrame([{
        "Pair": f"{p.a} ↔ {p.b}", "L (m)": p.L_m, "S₁ (mm)": round(p.S_a_mm, 1), "S₂ (mm)": round(p.S_b_mm, 1),
        "δ (mm)": round(p.delta_mm, 1), "δ limit (mm)": round(p.limit_mm, 1),
        "β = δ/L": IS.fmt_ratio(p.ratio),
        "δ check": "🟢 PASS" if p.ok_diff else "🔴 FAIL", "β check": "🟢 PASS" if p.ok_ang else "🔴 FAIL"}
        for p in sorted(pairs, key=lambda p: -p.ratio)])
    with st.expander(f"All {len(pairs)} adjacent column pairs (worst first)", expanded=not (ok_diff and ok_ang)):
        show_df(df_pairs)

    st.markdown("---")
    st.markdown("### 3. Overall verdict")
    if ok_total and ok_diff and ok_ang:
        st.success(f"✅ All IS 1904:1986 settlement checks PASS for {found_type.lower()} at these sizes. "
                   "(Bearing capacity, FoS = 3.0, is checked separately in P3.)")
    else:
        fails = [n for n, ok in [("total settlement", ok_total), ("differential settlement", ok_diff),
                                 ("angular distortion", ok_ang)] if not ok]
        st.error(f"❌ FAIL: {', '.join(fails)}.\n\n"
                 "Options: larger footings · deeper founding · raft (limits above switch with the sidebar) · "
                 "piles to the gravel · ground improvement (preloading, stone columns). Justify the choice in the report.")

    with st.expander("📋 IS 1904:1986 Table 1 values used (verify against the standard)"):
        show_df(pd.DataFrame([
            {"Foundation": "Isolated, RC", "Soil": "Sand / hard clay", "Total (mm)": 50, "Differential": "0.0015 L", "Angular dist.": "1/666"},
            {"Foundation": "Isolated, RC", "Soil": "Plastic clay", "Total (mm)": 75, "Differential": "0.0015 L", "Angular dist.": "1/666"},
            {"Foundation": "Raft, RC", "Soil": "Sand / hard clay", "Total (mm)": 75, "Differential": "0.002 L", "Angular dist.": "1/500"},
            {"Foundation": "Raft, RC", "Soil": "Plastic clay", "Total (mm)": 100, "Differential": "0.002 L", "Angular dist.": "1/500"},
        ]))