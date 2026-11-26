"""
pages/1_🗺️_Soil_Profile.py
P1 — Soil Profile Input & Visualization
CE 402 Geotechnical Engineering Platform — IIT Mandi
"""

import copy
import uuid

import matplotlib

matplotlib.use("Agg")  # must be set before pyplot is imported

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import streamlit as st

from utils.constants import init_session_state, SOIL_SYMBOLS, DEFAULT_LAYER

st.set_page_config(page_title="P1 — Soil Profile", page_icon="🗺️", layout="wide")

# ── Styling (works in light and dark themes) ─────────────────────────────────
st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; max-width: 1400px; }

    /* Metric strip */
    [data-testid="stMetric"] {
        background: rgba(128,128,128,0.07);
        border: 1px solid rgba(128,128,128,0.22);
        border-radius: 10px;
        padding: 0.7rem 1rem;
    }
    [data-testid="stMetricLabel"] p { font-size: 0.8rem; opacity: 0.75; }

    /* Layer cards */
    [data-testid="stExpander"] {
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 10px;
        background: rgba(128,128,128,0.035);
    }
    [data-testid="stExpander"] summary p { font-size: 0.95rem; }

    /* Tabs inside layer cards */
    [data-testid="stExpander"] button[role="tab"] { font-size: 0.85rem; padding: 0.3rem 0.8rem; }

    /* Slightly tighter number inputs */
    [data-testid="stNumberInput"] input { font-variant-numeric: tabular-nums; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _stretch(fn, *args, **kwargs):
    """Full-width helper that works on old and new Streamlit versions."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except TypeError:
        return fn(*args, use_container_width=True, **kwargs)


# ── Session state ────────────────────────────────────────────────────────────
init_session_state()

# Give every layer a stable id so widget keys survive sorting / deleting.
for _l in st.session_state.layers:
    _l.setdefault("uid", uuid.uuid4().hex[:8])

DF = 1.5  # foundation depth (m)

GRAVEL = ("GW", "GP", "GM", "GC")
SWATCH = {
    "GW": "🟫", "GP": "🟫", "GM": "🟫", "GC": "🟫",
    "SM": "🟨", "SP": "🟨", "SW": "🟨", "SC": "🟨",
    "ML": "🟩", "MH": "🟩",
    "CL": "🟦", "CI": "🟦", "CH": "🟦",
    "Fill": "⬜",
}
HATCH_MAP = {
    "SM": "///", "SP": "...", "SW": "xxx", "SC": "\\\\",
    "ML": "---", "CL": "---", "CI": "---", "CH": "---",
    "MH": "===", "GW": "++", "GP": "ooo", "GM": "///", "GC": "xxx",
    "Fill": "***",
}
COLOR_MAP = {
    "SM": "#d4c5a0", "SP": "#f0e68c", "SW": "#daa520", "SC": "#b8860b",
    "ML": "#90ee90", "CL": "#a2c4c9", "CI": "#7fb3d3", "CH": "#5b8db8",
    "MH": "#c5e0b4", "GW": "#c7b89d", "GP": "#e0cda9", "GM": "#b5a07a",
    "GC": "#9b7653", "Fill": "#d3d3d3",
}


# ── Helpers ──────────────────────────────────────────────────────────────────
def sort_layers():
    st.session_state.layers.sort(key=lambda l: l["depth_top"])


def wkey(layer, name):
    return f"layer_{layer['uid']}_{name}"


def validate_profile(layers, wt_meas, wt_des):
    """Return a list of (level, message). level is 'error' or 'warning'."""
    issues = []
    if not layers:
        return issues
    ordered = sorted(layers, key=lambda l: l["depth_top"])

    if abs(ordered[0]["depth_top"]) > 1e-6:
        issues.append(("warning", f"The first layer starts at {ordered[0]['depth_top']:.2f} m, not at the ground surface (0 m)."))

    for i, l in enumerate(ordered):
        if l["depth_bot"] <= l["depth_top"]:
            issues.append(("error", f"Layer {i + 1} ({l['name']}): bottom depth must be greater than top depth."))
        if l["gamma_sat"] < l["gamma_moist"]:
            issues.append(("warning", f"Layer {i + 1} ({l['name']}): γ_sat is lower than γ_moist."))
        if i > 0:
            prev = ordered[i - 1]
            gap = l["depth_top"] - prev["depth_bot"]
            if gap > 1e-6:
                issues.append(("error", f"Gap of {gap:.2f} m between layer {i} and layer {i + 1}."))
            elif gap < -1e-6:
                issues.append(("error", f"Layers {i} and {i + 1} overlap by {-gap:.2f} m."))

    if wt_des > wt_meas:
        issues.append(("warning", "Design WT is deeper than the measured WT. Design should use the highest seasonal WT."))
    return issues


def snap_contiguous():
    """Stack layers from 0 m, keeping each layer's thickness."""
    sort_layers()
    prev = 0.0
    for l in st.session_state.layers:
        thickness = max(l["depth_bot"] - l["depth_top"], 0.1)
        l["depth_top"] = prev
        l["depth_bot"] = prev + thickness
        prev = l["depth_bot"]
        # Keyed widgets ignore `value=` once they exist, so update their state too.
        st.session_state[wkey(l, "depth_top")] = float(l["depth_top"])
        st.session_state[wkey(l, "depth_bot")] = float(l["depth_bot"])


def estimate_es_kpa(layer):
    n = layer.get("N_corrected") or layer.get("N_field")
    if not n:
        return None
    if layer["symbol"] in GRAVEL:
        return 1200.0 * (n + 6)
    return 500.0 * (n + 15)


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Site information")

    st.subheader("Borehole")
    st.session_state.borehole_name = st.text_input(
        "Borehole name",
        value=st.session_state.borehole_name,
        key="sidebar_borehole_name",
    )
    st.session_state.ground_rl = st.number_input(
        "Ground RL (m)",
        value=float(st.session_state.ground_rl),
        step=0.1,
        format="%.2f",
        key="sidebar_ground_rl",
    )

    st.divider()
    st.subheader("Groundwater")
    st.session_state.wt_measured_bgl = st.number_input(
        "Measured WT depth (m bgl)",
        min_value=0.0,
        value=float(st.session_state.wt_measured_bgl),
        step=0.1,
        format="%.2f",
        key="sidebar_wt_measured",
    )
    st.session_state.wt_design_bgl = st.number_input(
        "Design WT depth (m bgl)",
        min_value=0.0,
        value=float(st.session_state.wt_design_bgl),
        step=0.1,
        format="%.2f",
        key="sidebar_wt_design",
        help="Use the highest seasonal WT for bearing capacity.",
    )
    st.caption("Use the highest seasonal WT for bearing capacity design.")

# ── Page header ──────────────────────────────────────────────────────────────
st.title("🗺️ Soil profile")
st.caption(
    f"Borehole **{st.session_state.borehole_name}**  ·  Ground RL **{st.session_state.ground_rl:.2f} m**"
)

layers = st.session_state.layers
wt_meas = st.session_state.wt_measured_bgl
wt_des = st.session_state.wt_design_bgl
issues = validate_profile(layers, wt_meas, wt_des)
n_errors = sum(1 for lvl, _ in issues if lvl == "error")

# ── Metric strip ─────────────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Layers", len(layers))
m2.metric("Profile depth", f"{max((l['depth_bot'] for l in layers), default=0.0):.1f} m")
m3.metric("Measured WT", f"{wt_meas:.1f} m bgl")
m4.metric(
    "Design WT",
    f"{wt_des:.1f} m bgl",
    delta=f"{wt_des - DF:+.1f} m vs Df",
    delta_color="off",
    help=f"Foundation depth Df = {DF} m. Positive means the WT is below the foundation level.",
)
m5.metric("Profile check", "Valid" if not issues else (f"{n_errors} error(s)" if n_errors else f"{len(issues)} warning(s)"))

if issues:
    with st.expander(f"Profile check: {len(issues)} item(s) to review", expanded=bool(n_errors)):
        for lvl, msg in issues:
            (st.error if lvl == "error" else st.warning)(msg)
        if any("Gap" in m or "overlap" in m or "ground surface" in m for _, m in issues):
            if st.button("Stack layers from 0 m (keep thicknesses)", key="btn_snap"):
                snap_contiguous()
                st.rerun()

st.write("")

# ── Main columns ─────────────────────────────────────────────────────────────
col_editor, col_viz = st.columns([1.1, 0.9], gap="large")

# ═════════════════════════════════════════════════════════════════════════════
# LEFT — Layer editor
# ═════════════════════════════════════════════════════════════════════════════
with col_editor:
    head_l, head_r = st.columns([0.6, 0.4], vertical_alignment="center")
    head_l.subheader("Layers")
    if head_r.button("➕ Add layer", key="btn_add_layer", type="primary"):
        last = st.session_state.layers[-1] if st.session_state.layers else DEFAULT_LAYER
        new = copy.deepcopy(DEFAULT_LAYER)
        new["uid"] = uuid.uuid4().hex[:8]
        new["depth_top"] = last["depth_bot"]
        new["depth_bot"] = last["depth_bot"] + 1.5
        new["name"] = f"Layer {len(st.session_state.layers) + 1}"
        st.session_state.layers.append(new)
        sort_layers()
        st.rerun()

    if not st.session_state.layers:
        st.info("No layers yet. Select **Add layer** to start the profile.")

    to_delete = None
    to_duplicate = None

    for i, layer in enumerate(st.session_state.layers):
        label = (
            f"{SWATCH.get(layer['symbol'], '⬜')} **{i + 1}. {layer['name']}**  "
            f"({layer['symbol']}, {layer['depth_top']:.1f}–{layer['depth_bot']:.1f} m)"
        )
        with st.expander(label, expanded=(i == 0)):
            tab_geo, tab_str, tab_cons, tab_stiff = st.tabs(
                ["Geometry", "Unit weight & strength", "Consolidation", "SPT & stiffness"]
            )

            # ── Geometry ─────────────────────────────────────────────────────
            with tab_geo:
                c1, c2 = st.columns(2)
                with c1:
                    layer["depth_top"] = st.number_input(
                        "Depth top (m bgl)",
                        value=float(layer["depth_top"]),
                        step=0.1,
                        format="%.2f",
                        key=wkey(layer, "depth_top"),
                    )
                with c2:
                    layer["depth_bot"] = st.number_input(
                        "Depth bottom (m bgl)",
                        value=float(layer["depth_bot"]),
                        step=0.1,
                        format="%.2f",
                        key=wkey(layer, "depth_bot"),
                    )
                c3, c4 = st.columns(2)
                with c3:
                    layer["name"] = st.text_input(
                        "Layer name",
                        value=layer["name"],
                        key=wkey(layer, "name"),
                    )
                with c4:
                    sym_idx = SOIL_SYMBOLS.index(layer["symbol"]) if layer["symbol"] in SOIL_SYMBOLS else 0
                    layer["symbol"] = st.selectbox(
                        "Soil symbol (IS 1498)",
                        options=SOIL_SYMBOLS,
                        index=sym_idx,
                        key=wkey(layer, "symbol"),
                    )
                thickness = layer["depth_bot"] - layer["depth_top"]
                if thickness <= 0:
                    st.error("Bottom depth must be greater than top depth.")
                else:
                    st.caption(f"Thickness: **{thickness:.2f} m**")

            # ── Unit weight & strength ───────────────────────────────────────
            with tab_str:
                st.markdown("**Unit weights**")
                cg1, cg2 = st.columns(2)
                with cg1:
                    layer["gamma_moist"] = st.number_input(
                        "γ_moist (kN/m³)",
                        value=float(layer["gamma_moist"]),
                        min_value=10.0,
                        max_value=25.0,
                        step=0.1,
                        format="%.1f",
                        key=wkey(layer, "gamma_moist"),
                    )
                with cg2:
                    layer["gamma_sat"] = st.number_input(
                        "γ_sat (kN/m³)",
                        value=float(layer["gamma_sat"]),
                        min_value=10.0,
                        max_value=25.0,
                        step=0.1,
                        format="%.1f",
                        key=wkey(layer, "gamma_sat"),
                    )
                if layer["gamma_sat"] < layer["gamma_moist"]:
                    st.warning("γ_sat is lower than γ_moist.")

                st.markdown("**Drained strength**")
                cd1, cd2 = st.columns(2)
                with cd1:
                    layer["c_prime"] = st.number_input(
                        "c′ (kPa)",
                        value=float(layer["c_prime"]),
                        min_value=0.0,
                        step=0.5,
                        format="%.1f",
                        key=wkey(layer, "c_prime"),
                    )
                with cd2:
                    layer["phi_prime"] = st.number_input(
                        "φ′ (degrees)",
                        value=float(layer["phi_prime"]),
                        min_value=0.0,
                        max_value=50.0,
                        step=0.5,
                        format="%.1f",
                        key=wkey(layer, "phi_prime"),
                    )

                st.markdown("**Undrained strength**")
                layer["is_undrained"] = st.checkbox(
                    "Use undrained cu (UU analysis)",
                    value=bool(layer["is_undrained"]),
                    key=wkey(layer, "is_undrained"),
                )
                if layer["is_undrained"]:
                    layer["cu"] = st.number_input(
                        "cu (kPa)",
                        value=float(layer["cu"]) if layer["cu"] else 0.0,
                        min_value=0.0,
                        step=1.0,
                        format="%.1f",
                        key=wkey(layer, "cu"),
                    )

            # ── Consolidation ────────────────────────────────────────────────
            with tab_cons:
                layer["is_clay"] = st.checkbox(
                    "Clay: consolidation settlement applies",
                    value=bool(layer["is_clay"]),
                    key=wkey(layer, "is_clay"),
                )
                if layer["is_clay"]:
                    cc1, cc2, cc3 = st.columns(3)
                    with cc1:
                        cc_val = layer["Cc"] if layer["Cc"] is not None else 0.3
                        layer["Cc"] = st.number_input(
                            "Cc",
                            value=float(cc_val),
                            min_value=0.0,
                            step=0.01,
                            format="%.3f",
                            key=wkey(layer, "Cc"),
                        )
                    with cc2:
                        cr_val = layer["Cr"] if layer["Cr"] is not None else 0.05
                        layer["Cr"] = st.number_input(
                            "Cr",
                            value=float(cr_val),
                            min_value=0.0,
                            step=0.01,
                            format="%.3f",
                            key=wkey(layer, "Cr"),
                        )
                    with cc3:
                        e0_val = layer["e0"] if layer["e0"] is not None else 0.9
                        layer["e0"] = st.number_input(
                            "e₀ (void ratio)",
                            value=float(e0_val),
                            min_value=0.0,
                            step=0.01,
                            format="%.3f",
                            key=wkey(layer, "e0"),
                        )
                    cp1, cp2 = st.columns(2)
                    with cp1:
                        pc_val = layer["Pc_kPa"] if layer["Pc_kPa"] is not None else 100.0
                        layer["Pc_kPa"] = st.number_input(
                            "Pc (kPa), preconsolidation pressure",
                            value=float(pc_val),
                            min_value=0.0,
                            step=1.0,
                            format="%.1f",
                            key=wkey(layer, "Pc_kPa"),
                        )
                    with cp2:
                        cv_val = layer["cv_m2s"] if layer["cv_m2s"] is not None else 1e-8
                        cv_input = st.number_input(
                            "cv (×10⁻⁸ m²/s)",
                            value=float(cv_val) * 1e8,
                            min_value=0.0,
                            step=0.1,
                            format="%.2f",
                            key=wkey(layer, "cv_m2s"),
                        )
                        layer["cv_m2s"] = cv_input * 1e-8
                else:
                    st.caption("Tick the box above for clay layers to enter Cc, Cr, e₀, Pc and cv.")

            # ── SPT & stiffness ──────────────────────────────────────────────
            with tab_stiff:
                n_field_val = layer["N_field"]
                use_spt = st.checkbox(
                    "Has SPT N value",
                    value=(n_field_val is not None),
                    key=wkey(layer, "has_spt"),
                )
                if use_spt:
                    n_default = int(n_field_val) if n_field_val is not None else 10
                    layer["N_field"] = st.number_input(
                        "N_field (observed SPT N)",
                        value=n_default,
                        min_value=1,
                        max_value=100,
                        step=1,
                        key=wkey(layer, "N_field"),
                    )
                else:
                    layer["N_field"] = None

                es_val = layer.get("Es_kPa")
                use_custom_es = st.checkbox(
                    "Specify measured / design Es (MPa)",
                    value=(es_val is not None and es_val > 0),
                    key=wkey(layer, "has_es"),
                    help="Overrides the SPT correlation in P5 immediate settlement. Leave unticked to estimate Es from SPT N.",
                )
                if use_custom_es:
                    es_mpa_default = (float(es_val) / 1000.0) if (es_val is not None and es_val > 0) else 15.0
                    es_mpa = st.number_input(
                        "Es (MPa)",
                        value=es_mpa_default,
                        min_value=0.1,
                        max_value=5000.0,
                        step=1.0,
                        format="%.1f",
                        key=wkey(layer, "Es_MPa"),
                    )
                    layer["Es_kPa"] = es_mpa * 1000.0
                else:
                    layer["Es_kPa"] = None
                    if not layer.get("is_clay", False):
                        est = estimate_es_kpa(layer)
                        n_used = layer.get("N_corrected") or layer.get("N_field")
                        if est:
                            st.caption(
                                f"P5 will use the SPT correlation: **Es ≈ {est / 1000.0:.2f} MPa** "
                                f"({est:.0f} kPa) from N = {n_used}."
                            )
                        else:
                            st.warning(
                                "Neither Es nor SPT N is entered for this layer. "
                                "P5 immediate settlement will skip it until one is provided."
                            )

            # ── Layer actions ────────────────────────────────────────────────
            a1, a2, _sp = st.columns([0.25, 0.25, 0.5])
            if a1.button("Duplicate", key=wkey(layer, "dup"), icon=":material/content_copy:"):
                to_duplicate = i
            if a2.button("Delete", key=wkey(layer, "delete"), icon=":material/delete:"):
                to_delete = i

    if to_duplicate is not None:
        src = st.session_state.layers[to_duplicate]
        dup = copy.deepcopy(src)
        thick = max(src["depth_bot"] - src["depth_top"], 0.1)
        top = max(l["depth_bot"] for l in st.session_state.layers)
        dup["uid"] = uuid.uuid4().hex[:8]
        dup["depth_top"] = top
        dup["depth_bot"] = top + thick
        dup["name"] = f"{src['name']} (copy)"
        st.session_state.layers.append(dup)
        sort_layers()
        st.rerun()

    if to_delete is not None:
        st.session_state.layers.pop(to_delete)
        sort_layers()
        st.rerun()

    sort_layers()

# ═════════════════════════════════════════════════════════════════════════════
# RIGHT — Profile visualization
# ═════════════════════════════════════════════════════════════════════════════
with col_viz:
    st.subheader("Profile")

    layers = st.session_state.layers
    GRAY = "#8a8a8a"

    with st.container(border=True):
        if layers:
            max_depth = max(l["depth_bot"] for l in layers)
            rl = float(st.session_state.ground_rl)

            with plt.rc_context({"hatch.linewidth": 0.5}):
                fig, ax = plt.subplots(figsize=(4.8, min(max(5.0, max_depth * 0.55), 11.0)))
                fig.patch.set_alpha(0)
                ax.set_facecolor("none")

                ax.set_xlim(0, 1)
                ax.set_ylim(max_depth + 0.5, -0.3)  # depth increases downward
                ax.set_xticks([])
                ax.set_yticks(sorted({l["depth_top"] for l in layers} | {layers[-1]["depth_bot"]}))
                ax.set_ylabel("Depth (m bgl)", fontsize=9, color=GRAY)
                ax.tick_params(axis="y", labelsize=8, colors=GRAY)
                for side in ("top", "right", "bottom"):
                    ax.spines[side].set_visible(False)
                ax.spines["left"].set_color(GRAY)

                # Secondary axis: reduced level
                sec = ax.secondary_yaxis("right", functions=(lambda d: rl - d, lambda r: rl - r))
                sec.set_ylabel("RL (m)", fontsize=9, color=GRAY)
                sec.tick_params(labelsize=8, colors=GRAY)
                sec.spines["right"].set_visible(False)

                for layer in layers:
                    d_top, d_bot = layer["depth_top"], layer["depth_bot"]
                    sym = layer["symbol"]
                    h = d_bot - d_top
                    if h <= 0:
                        continue
                    # Fill + faint hatch
                    ax.add_patch(
                        mpatches.Rectangle(
                            (0.05, d_top), 0.90, h,
                            facecolor=COLOR_MAP.get(sym, "#cccccc"),
                            edgecolor=(0, 0, 0, 0.22),
                            hatch=HATCH_MAP.get(sym, "/"),
                            linewidth=0,
                        )
                    )
                    # Crisp outline
                    ax.add_patch(
                        mpatches.Rectangle(
                            (0.05, d_top), 0.90, h,
                            fill=False, edgecolor="#333333", linewidth=1.0,
                        )
                    )
                    text = (
                        f"{layer['name']} ({sym})\n{d_top:.1f}–{d_bot:.1f} m"
                        if h >= 0.9
                        else f"{layer['name']} ({sym}), {d_top:.1f}–{d_bot:.1f} m"
                    )
                    ax.text(
                        0.50, (d_top + d_bot) / 2, text,
                        ha="center", va="center", fontsize=7.5, fontweight="bold",
                        color="#1a1a1a",
                        bbox=dict(boxstyle="round,pad=0.25", facecolor=(1, 1, 1, 0.55), edgecolor="none"),
                    )

                # Water table
                if 0 <= wt_meas <= max_depth:
                    ax.axhline(wt_meas, color="#1f6fd1", linewidth=1.6, linestyle="-", label=f"Measured WT, {wt_meas:.1f} m")
                    ax.plot([0.05], [wt_meas], marker="v", color="#1f6fd1", markersize=7, clip_on=False)
                if 0 <= wt_des <= max_depth and abs(wt_des - wt_meas) > 1e-6:
                    ax.axhline(wt_des, color="#1f6fd1", linewidth=1.6, linestyle="--", label=f"Design WT, {wt_des:.1f} m")
                    ax.plot([0.95], [wt_des], marker="v", color="#1f6fd1", markersize=7, clip_on=False)

                # Foundation level
                if 0 <= DF <= max_depth:
                    ax.axhline(DF, color="#d62728", linewidth=1.4, linestyle=":", label=f"Foundation level Df, {DF} m")

                ax.legend(
                    loc="upper center", bbox_to_anchor=(0.5, -0.02),
                    fontsize=8, frameon=False, ncol=1,
                )
                fig.tight_layout()
                _stretch(st.pyplot, fig)
                plt.close(fig)
        else:
            st.info("The profile appears here once you add a layer.")

# ═════════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE
# ═════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("Layer summary")

if st.session_state.layers:
    rows = []
    for i, l in enumerate(st.session_state.layers):
        es_kpa = l.get("Es_kPa")
        if es_kpa is not None and es_kpa > 0:
            es_display = f"{es_kpa / 1000.0:.1f} MPa (entered)"
        elif not l.get("is_clay", False) and estimate_es_kpa(l):
            es_display = f"{estimate_es_kpa(l) / 1000.0:.1f} MPa (SPT est.)"
        else:
            es_display = "—"

        rows.append(
            {
                "Layer": f"{i + 1} — {l['name']}",
                "Symbol": l["symbol"],
                "Depth (m)": f"{l['depth_top']:.1f} – {l['depth_bot']:.1f}",
                "Thickness (m)": round(l["depth_bot"] - l["depth_top"], 2),
                "γ_moist (kN/m³)": round(l["gamma_moist"], 1),
                "γ_sat (kN/m³)": round(l["gamma_sat"], 1),
                "c′ (kPa)": round(l["c_prime"], 1),
                "φ′ (°)": round(l["phi_prime"], 1),
                "cu (kPa)": round(l["cu"], 1) if l.get("is_undrained") and l.get("cu") else "—",
                "Es": es_display,
                "N_field": l["N_field"] if l["N_field"] is not None else "—",
                "Cc": round(l["Cc"], 3) if l["is_clay"] and l["Cc"] is not None else "—",
                "cv (m²/s)": f"{l['cv_m2s']:.2e}" if l["is_clay"] and l["cv_m2s"] is not None else "—",
            }
        )
    df_summary = pd.DataFrame(rows)
    _stretch(st.dataframe, df_summary, hide_index=True)

    st.download_button(
        "Download summary (CSV)",
        data=df_summary.to_csv(index=False).encode("utf-8"),
        file_name=f"{st.session_state.borehole_name}_soil_profile.csv",
        mime="text/csv",
        icon=":material/download:",
    )
else:
    st.info("No layers to summarise yet.")
