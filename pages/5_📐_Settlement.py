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

Initial inputs are illustrative. No assignment-specific calculation defaults.
Units: kN, kPa, m, mm, years (cv in m²/s).
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from utils.demo_data import demo_notice, OEDOMETER
from utils.constants import init_session_state
from utils.settlement import (
    schmertmann_settlement,
    total_consolidation_settlement,
    multilayer_time_settlement,
    _effective_stress_at,
    validate_profile,
)
from utils import Is1904 as IS
import copy

st.set_page_config(page_title="P5 – Settlement", page_icon="📐", layout="wide")
init_session_state()
demo_notice(st)

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
demo = st.session_state.get("demo_project")
with st.sidebar:
    st.header("⚙️ Global inputs")
    lam = st.number_input("Load multiplier", min_value=0.01, value=float(demo["factor"]) if demo else 1.0, step=0.01, key="p5_multiplier", help="Multiplier on entered service loads. Use 1.0 for unmodified loads.")
    Df = st.number_input("Founding depth Df (m)", value=float(st.session_state.foundation_depth), min_value=0.0, step=0.1, key="p5_Df")
    st.session_state.foundation_depth = Df
    load_basis = st.radio("Load basis", ["gross_effective", "net"], format_func=lambda x: "Effective gross contact load (kN)" if x == "gross_effective" else "Net foundation load (kN)")
    st.caption("Gross effective load must exclude pore-water pressure at the footing base; net load already excludes initial effective surcharge. Do not enter total gross load as effective gross below groundwater without conversion.")
    allow_raw_n = st.checkbox("Allow raw N for illustrative Es estimates (only if no valid correction is available)", value=False)
    assume_nc = st.checkbox("Explicitly assume NC if Pc is missing", value=False)
    st.caption("Illustrative defaults only. Replace them with site-specific input before evaluating settlement.")
    t_yr = st.number_input("Design life t (years)", value=50, min_value=1, step=5, key="p5_t")

    st.markdown("---")
    st.subheader("Column grid")
    nx = st.number_input("No. of grid lines 1…n (along length)", value=7 if demo else 3, min_value=2, max_value=26, step=1, key="p5_nx")
    ny = st.number_input("No. of rows A… (across width)", value=4 if demo else 3, min_value=2, max_value=26, step=1, key="p5_ny")
    span_x = st.number_input("Span between grid lines 1,2,… (m)", value=5.0, min_value=0.5, step=0.5, key="p5_sx")
    span_y = st.number_input("Span between rows A,B,… (m)", value=5.0, min_value=0.5, step=0.5, key="p5_sy")
    special_txt = st.text_input("Special column(s) (comma-separated, e.g. C4; blank = none)", value="C4" if demo else "", key="p5_special")

    st.markdown("---")
    st.subheader("Drainage (time curve)")
    st.caption("Select drainage and any overrides separately for each clay layer in the consolidation tab.")

    st.markdown("---")
    st.subheader("IS 1904:1986 limits")
    soil_choice = st.selectbox(
        "Soil governing the total-settlement limit",
        ["Sand / hard clay", "Plastic clay"], index=1 if demo else 0, key="p5_soilsel")
    found_type = "Isolated footings (RC frame)"
    st.caption("Isolated rectangular footings only. Raft limits alone cannot model raft settlement.")
    structure_category = st.selectbox(
        "IS 1904 Table 1 structure category",
        ["General reinforced concrete (ii)", "Multistoreyed framed with panel walls (iii-a)"],
        index=1 if demo else 0, key="p5_structure_category")
    LIM_TABLE = (IS.ISOLATED_RC if structure_category.startswith("General")
                 else IS.ISOLATED_MULTISTOREY)
    st.caption("Choose and justify the category and limits for the actual structure.")

# ═══════════════════════════ PROFILES / ZONES ══════════════════════════════
# Optional multi-borehole support: st.session_state["boreholes"] =
#   {"BH-1": {"layers": [...], "wt_design_bgl": float}, ...}
# If absent, the single active P1 profile is used for the whole building.
with st.expander("Save active P1 profile for multi-borehole zoning"):
    profile_name = st.text_input("Profile name", value=str(st.session_state.borehole_name), key="p5_save_profile_name")
    if st.button("Save / replace active profile"):
        try:
            validate_profile(st.session_state.layers)
            if not profile_name.strip():
                raise ValueError("Profile name is required.")
            st.session_state.setdefault("boreholes", {})[profile_name.strip()] = {
                "layers": copy.deepcopy(st.session_state.layers), "wt_design_bgl": st.session_state.wt_design_bgl}
            st.success("Profile snapshot saved. Changes in P1 require saving again.")
        except ValueError as exc:
            st.error(str(exc))
    if st.session_state.get("boreholes"):
        remove = st.selectbox("Saved profile to remove", list(st.session_state.boreholes), key="p5_remove_profile")
        if st.button("Remove saved profile"):
            del st.session_state.boreholes[remove]
            st.rerun()
bh_store = st.session_state.get("boreholes")
if isinstance(bh_store, dict) and len(bh_store) >= 1:
    profiles = {k: {"layers": v["layers"], "wt": v["wt_design_bgl"]}
                for k, v in bh_store.items()}
else:
    profiles = {"Active profile": {"layers": st.session_state.layers, "wt": st.session_state.wt_design_bgl}}

bh_names = sorted(profiles)
if len(bh_names) > nx:
    st.error("There are more saved profiles than grid lines. Remove unused profiles or increase grid size.")
    st.stop()
chunks = np.array_split(np.arange(1, nx + 1), len(bh_names))
zone_df = pd.DataFrame({
    "Profile": bh_names,
    "First line": [int(c[0]) if len(c) else 1 for c in chunks],
    "Last line": [int(c[-1]) if len(c) else 1 for c in chunks],
})

if demo and nx == 7 and set(bh_names) == set(demo["zones"]):
    zone_df["First line"] = [demo["zones"][k][0] for k in bh_names]
    zone_df["Last line"] = [demo["zones"][k][1] for k in bh_names]

with st.expander("🗺️ Borehole zoning by grid line (edit to match your justification)", expanded=len(bh_names) > 1):
    if len(bh_names) == 1:
        st.caption("Only one profile is available, so the whole building uses it. "
                   "Differential settlement between boreholes needs `st.session_state['boreholes']` (see code header).")
    zone_ed = st.data_editor(zone_df, hide_index=True, key="p5_zones", disabled=["Profile"],
                             column_config={"First line": st.column_config.NumberColumn(min_value=1, max_value=int(nx), step=1),
                                            "Last line": st.column_config.NumberColumn(min_value=1, max_value=int(nx), step=1)})
try:
    zones = [{"name": r["Profile"], "first": int(r["First line"]), "last": int(r["Last line"])}
             for _, r in zone_ed.iterrows()]
    IS.validate_zones(zones, nx)
except (ValueError, TypeError) as exc:
    st.error(str(exc))
    st.stop()

# ═══════════════════════════ COLUMN TYPES TABLE ════════════════════════════
special_cols = []
for tok in [s for s in special_txt.split(",") if s.strip()]:
    p = IS.parse_name(tok)
    if p is None or not (1 <= p[0] <= nx and 0 <= p[1] < ny):
        st.warning(f"Special column '{tok.strip()}' is not on the grid — ignored.")
    else:
        special_cols.append(p)

rows = ["Corner", "Edge", "Interior"] + (["Special"] if special_cols else [])
default_P = {"Corner": 400.0, "Edge": 600.0, "Interior": 900.0, "Special": 900.0}
default_B = {"Corner": 2.0, "Edge": 2.5, "Interior": 3.0, "Special": 3.0}
if demo:
    default_P = demo["loads"]
    default_B = demo["widths"]
    st.warning("C4 load and moment are absent from the supplied table. The demo uses a clearly assumed concentric interior load for C4; this is not an eccentric settlement check.")
type_df = pd.DataFrame({
    "Type": rows,
    "Service P, unfactored (kN)": [default_P[r] for r in rows],
    "B (m)": [default_B[r] for r in rows],
    "L (m)": [default_B[r] for r in rows],
})

st.subheader("Column loads and footing sizes")
auto_size = st.checkbox("Auto-size square footings from a pressure on the selected load basis", value=False, key="p5_auto")
q_auto = st.number_input("Selected-basis pressure for preliminary sizing q (kPa)", value=150.0, min_value=10.0, step=10.0,
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
    if any(pd.isna(r[k]) or not np.isfinite(float(r[k])) or float(r[k]) <= 0 for k in ("Service P, unfactored (kN)", "B (m)", "L (m)")):
        st.error("Enter positive finite loads and footing dimensions for every column type.")
        st.stop()
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
        try:
            imm = schmertmann_settlement(pf["layers"], Df, t["B"], t["L"], t["P_kN"], pf["wt"], t_years=t_yr, load_basis=load_basis, allow_raw_n=allow_raw_n)
            con = total_consolidation_settlement(pf["layers"], Df, t["B"], t["L"], t["P_kN"], pf["wt"], load_basis=load_basis, assume_nc=assume_nc)
        except ValueError as exc:
            st.error(f"{ctype} / {zone}: {exc}")
            st.stop()
        _memo[key] = {"imm": imm, "con": con,
                      "Si": imm["S_mm"], "Sc": con["S_total_mm"], "S": imm["S_mm"] + con["S_total_mm"]}
    return _memo[key]


# Column-by-column settlement map
col_type, col_zone, col_S = {}, {}, {}
special_set = set(special_cols)
for j in range(int(ny)):
    for i in range(1, int(nx) + 1):
        ctype = "Special" if (i, j) in special_set else IS.classify(i, j, int(nx), int(ny))
        zone = IS.zone_of_line(i, zones)
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

# Report all model warnings; never hide assumed parameters in compliance.
for (ct, zn), v in _memo.items():
    for warning in v["imm"]["warnings"] + v["con"]["warnings"]:
        st.warning(f"{ct} / {zn}: {warning}")
st.caption("Granular strain-influence estimate includes creep to the selected design time; clay value is ultimate primary consolidation. Independent footing loads only; neighboring footing interactions and clay immediate settlement are not modeled.")

m1, m2, m3 = st.columns(3)
m1.metric("Granular Sᵢ at design time", f"{S_i_mm:.1f} mm", delta="Schmertmann (1978)", delta_color="off")
m2.metric("Consolidation Sc", f"{S_c_mm:.1f} mm", delta="Terzaghi (1943)", delta_color="off")
m3.metric("Granular + ultimate primary Sc", f"{S_tot_mm:.1f} mm",
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
    st.metric("Granular settlement at design time Sᵢ", f"{S_i_mm:.2f} mm")

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
        st.warning("No granular sublayers in the influence zone (2B below a square footing, up to 4B for a strip). Clay immediate settlement is outside this model.")

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
    with_params = [l for l in layers if l.get("is_clay") and l["depth_bot"] > Df and l.get("Cc") is not None and l.get("e0") is not None and l.get("Pc_kPa")]
    if with_params and sub_c:
        st.subheader("e–log p curve")
        ly = st.selectbox("Clay for e–log p curve", with_params, format_func=lambda l: l.get("name", "Clay"), key=f"p5_eplot_{sel_zone}")
        Cc_pl, e0_pl, Pc_pl = ly["Cc"], ly["e0"], ly["Pc_kPa"]
        Cr_pl = ly.get("Cr") or 0.0
        if not ly.get("Cr"):
            st.warning("Cr not entered for this layer — recompression branch drawn flat (Cr = 0).")
        s0 = _effective_stress_at(layers, (max(Df, ly["depth_top"]) + ly["depth_bot"])/2, wt)
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
            if demo: st.caption("Raw UDS-1 oedometer observations from BH-1 only, regardless of inspected borehole.")
            u = st.selectbox("Pressure unit of the table", ["kg/cm²", "kPa"], key="p5_oed_unit")
            oed = st.data_editor(pd.DataFrame({"Pressure": [v[0] * (1.0 if u == "kg/cm²" else KGCM2_TO_KPA) for v in OEDOMETER], "Void ratio e": [v[1] for v in OEDOMETER]}) if demo else pd.DataFrame({"Pressure": [0.0], "Void ratio e": [0.0]}), num_rows="dynamic",
                                 hide_index=True, key=f"p5_oed_{u}")
            oed = oed[(oed["Pressure"] > 0) & (oed["Void ratio e"] > 0)]
            if len(oed):
                px_kpa = oed["Pressure"] * (KGCM2_TO_KPA if u == "kg/cm²" else 1.0)
                fig_ep.add_trace(go.Scatter(x=px_kpa, y=oed["Void ratio e"], mode="markers+lines",
                                            name="Lab oedometer", line=dict(color="blue", dash="dot")))
        fig_ep.update_layout(title=f"e–log p | Cc = {Cc_pl:.3f}, Cr = {Cr_pl:.3f}, e₀ = {e0_pl:.3f}, σ′v0 = {s0:.0f} kPa",
                             xaxis=dict(title="Effective vertical stress p (kPa)", type="log"),
                             yaxis_title="Void ratio e", height=420)
        show_plot(fig_ep)

    # Time response of each physical clay layer, not of individual numerical sublayers.
    st.subheader("Time–settlement curve (primary consolidation)")
    st.caption("Independent 1-D layer response, summed across layers. Confirm each drainage boundary; adjacent clay layers may require a coupled analysis.")
    clay_results = [r for r in cons_result["layer_results"] if r["Sc_mm"] > 0]
    configs = {}
    for r in clay_results:
        idx = r["layer_idx"]
        key = f"p5_time_{sel_zone}_{idx}"
        st.markdown(f"**{r['layer_name']} — H = {r['H_m']:.3f} m**")
        mode = st.selectbox("Drainage assumption", ["single", "double"], format_func=lambda m: "One-way" if m == "single" else "Two-way", key=key+"_drain")
        cv = st.number_input("cv (m²/s)", value=float(r["cv_m2s"] or 0.0), min_value=0.0, step=1e-9, format="%.3e", key=key+"_cv")
        hdr = st.number_input("Drainage path override Hdr (m; 0 = H or H/2)", value=0.0, min_value=0.0, step=0.1, key=key+"_hdr")
        configs[idx] = {"drainage": mode, "cv_m2s": cv}
        if hdr > 0:
            configs[idx]["Hdr_m"] = hdr
    if clay_results:
        horizon = st.number_input("Time curve horizon (years)", min_value=0.01, value=float(t_yr), step=1.0, key="p5_curve_horizon")
        log_t = st.checkbox("Logarithmic time axis", value=True, key="p5_logt")
        t_arr = np.unique(np.r_[0.0, np.geomspace(max(horizon*1e-8, 1e-10), horizon, 400), np.linspace(0, horizon, 300)])
        try:
            S_t_mm, details = multilayer_time_settlement(clay_results, t_arr, configs)
        except ValueError as exc:
            st.error(f"Time curve unavailable: {exc}")
        else:
            show_df(pd.DataFrame([{k:v for k,v in d.items() if k != "curve_mm"} for d in details]))
            mask = t_arr > 0 if log_t else np.ones_like(t_arr, dtype=bool)
            fig_ts = go.Figure()
            for d in details:
                fig_ts.add_trace(go.Scatter(x=t_arr[mask], y=d["curve_mm"][mask], mode="lines", name=f"Layer {d['layer_idx']+1}: {d['layer_name']}"))
            fig_ts.add_trace(go.Scatter(x=t_arr[mask], y=S_t_mm[mask], mode="lines", name="Total primary consolidation", line=dict(width=3)))
            # S78 creep factor changes with time; t <= 0.1 yr uses C2=1.
            granular_t = imm_result["S_initial_mm"] * (1 + 0.2*np.log10(np.maximum(t_arr, 0.1)/0.1))
            fig_ts.add_trace(go.Scatter(x=t_arr[mask], y=(S_t_mm+granular_t)[mask], mode="lines", name="Granular + consolidation", line=dict(dash="dash")))
            fig_ts.add_hline(y=S_c_mm, line_dash="dot", annotation_text=f"Ultimate primary Sc = {S_c_mm:.1f} mm")
            fig_ts.update_layout(title="Settlement versus time", xaxis=dict(title="Time (years)", type="log" if log_t else "linear"), yaxis_title="Settlement (mm)", height=420)
            show_plot(fig_ts)
    else:
        st.info("No positive primary consolidation settlement for this profile.")

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
    st.caption("Adjacent-column checks are supplemented by the maximum/minimum settlement pair (Cl. 16.3.5). Straight-line grid separation is assumed. This is a screening check only.")

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
    fig_col.update_layout(title=f"Total settlement by column type (load multiplier = {lam:.2f})",
                          yaxis_title="Total settlement (mm)", height=380)
    show_plot(fig_col)

    st.markdown("---")
    # 2. differential / angular distortion on the real grid
    st.markdown("### 2. Differential settlement & angular distortion")
    pairs = IS.check_pairs(col_S, int(nx), int(ny), span_x, span_y, LIM)
    extreme = IS.check_extreme_pair(col_S, int(nx), int(ny), span_x, span_y, LIM)
    checked_pairs = pairs + ([extreme] if extreme is not None else [])
    gov = max(checked_pairs, key=lambda p: p.ratio)
    ok_diff = all(p.ok_diff for p in checked_pairs)
    ok_ang = all(p.ok_ang for p in checked_pairs)
    g1, g2, g3 = st.columns(3)
    g1.metric("Max differential δ", f"{max(p.delta_mm for p in checked_pairs):.1f} mm")
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

    if extreme is not None:
        st.markdown("#### Global maximum/minimum settlement pair (Clause 16.3.5)")
        show_df(pd.DataFrame([{
            "Pair": f"{extreme.a} ↔ {extreme.b}", "Distance (m)": extreme.L_m,
            "Differential (mm)": extreme.delta_mm, "Limit (mm)": extreme.limit_mm,
            "Angular distortion": IS.fmt_ratio(extreme.ratio),
            "Differential check": "PASS" if extreme.ok_diff else "FAIL",
            "Angular check": "PASS" if extreme.ok_ang else "FAIL"}]))
    st.markdown("---")
    st.markdown("### 3. Overall verdict")
    if ok_total and ok_diff and ok_ang:
        st.success("Calculated settlement values satisfy the adopted screening limits. This is not foundation approval; verify input data, limits, interactions, eccentricity and bearing capacity separately.")
    else:
        fails = [n for n, ok in [("total settlement", ok_total), ("differential settlement", ok_diff),
                                 ("angular distortion", ok_ang)] if not ok]
        st.error(f"❌ FAIL: {', '.join(fails)}.\n\n"
                 "Options for separate engineering assessment: larger footings · deeper founding · raft · "
                 "piles to the gravel · ground improvement (preloading, stone columns). Justify the choice in the report.")

    with st.expander("📋 Adopted limits from shared IS1904 utility (verify against standard)"):
        show_df(pd.DataFrame([{"Foundation": label, "Soil": soil, "Total (mm)": vals["total_mm"],
                               "Differential ratio": vals["diff_ratio"], "Angular ratio": vals["ang_limit"]}
                              for label, table in (("Isolated, RC (ii)", IS.ISOLATED_RC), ("Raft, RC (ii)", IS.RAFT_RC),
                                                    ("Isolated, multistoreyed (iii-a)", IS.ISOLATED_MULTISTOREY),
                                                    ("Raft, multistoreyed (iii-a)", IS.RAFT_MULTISTOREY))
                              for soil, vals in table.items()]))
