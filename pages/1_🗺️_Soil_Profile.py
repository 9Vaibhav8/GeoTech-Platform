"""
pages/1_🗺️_Soil_Profile.py
P1 — Soil Profile Input & Visualization
GeoForge — Geotechnical Analysis & Foundation Design
"""

import copy
import math
from uuid import uuid4
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

from utils.demo_data import demo_notice
from utils.constants import init_session_state, SOIL_SYMBOLS, DEFAULT_LAYER
from utils.bearing_capacity import GAMMA_W, validate_profile

st.set_page_config(page_title="P1 — Soil Profile", layout="wide")

# ── Session state ────────────────────────────────────────────────────────────
init_session_state()
demo_notice(st)

# Persistent layer identities prevent widget values from moving to the wrong
# layer when its position changes. They are metadata, not engineering inputs.
seen_ids = set()
for layer in st.session_state.layers:
    uid = layer.get("_ui_id")
    if not uid or uid in seen_ids:
        uid = uuid4().hex
        layer["_ui_id"] = uid
    seen_ids.add(uid)


def preview_es(layer):
    """Existing SPT–Es estimate, for display only; verify source with P5.

    Correlation coefficients retained from original P1. A source was not
    supplied; this is not a verified IS-code relationship.
    """
    if layer.get("is_clay") or layer.get("N_refusal"):
        return None, None
    n = layer.get("N_corrected")
    if n is None:
        n = layer.get("N_field")
    if n is None or not math.isfinite(float(n)) or float(n) <= 0:
        return None, None
    n = float(n)
    gravel = layer["symbol"] in ("GW", "GP", "GM", "GC")
    return (1200.0 * (n + 6) if gravel else 500.0 * (n + 15)), n


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🏗️ Site Information")

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
        help="Use highest seasonal WT for bearing capacity",
    )
    st.caption("ℹ️ Use highest seasonal WT for bearing capacity design.")
    st.session_state.foundation_depth = st.number_input(
        "Foundation depth for profile preview (m bgl)",
        min_value=0.0,
        value=float(st.session_state.get("foundation_depth", 1.5)),
        step=0.1,
        format="%.2f",
        key="p1_foundation_depth",
        help="Editable preview value; use the same Df in footing modules if applicable.",
    )

# ── Page title ───────────────────────────────────────────────────────────────
st.title("🗺️ P1 — Soil Profile")
st.caption(f"Borehole: **{st.session_state.borehole_name}** | Ground RL: **{st.session_state.ground_rl:.2f} m**")

# ── Helper: sort layers ───────────────────────────────────────────────────────
def sort_layers():
    st.session_state.layers.sort(key=lambda l: l["depth_top"])

# ── Main columns ──────────────────────────────────────────────────────────────
col_editor, col_viz = st.columns([1.1, 0.9], gap="large")

# ═══════════════════════════════════════════════════════════════════════════════
# LEFT COLUMN — Layer Editor
# ═══════════════════════════════════════════════════════════════════════════════
with col_editor:
    st.subheader("📋 Layer Editor")

    if st.button("➕ Add Layer", key="btn_add_layer"):
        top = max((float(l["depth_bot"]) for l in st.session_state.layers), default=0.0)
        new = copy.deepcopy(DEFAULT_LAYER)
        new["_ui_id"] = uuid4().hex
        new["depth_top"] = top
        new["depth_bot"] = top + 1.5  # editable initial thickness, not a calculation limit
        new["name"] = f"Layer {len(st.session_state.layers) + 1}"
        st.session_state.layers.append(new)
        sort_layers()
        st.rerun()

    # Keep track of which layer to delete (avoid mutating list during iteration)
    to_delete = None

    for i, layer in enumerate(st.session_state.layers):
        uid = layer["_ui_id"]
        label = (
            f"**Layer {i + 1}** — {layer['name']} ({layer['symbol']})  "
            f"| {layer['depth_top']:.1f}–{layer['depth_bot']:.1f} m"
        )
        with st.expander(label, expanded=(i == 0)):

            c1, c2 = st.columns(2)
            with c1:
                st.session_state.layers[i]["depth_top"] = st.number_input(
                    "Depth top (m bgl)",
                    value=float(layer["depth_top"]),
                    min_value=0.0,
                    step=0.1,
                    format="%.2f",
                    key=f"p1_layer_{uid}_depth_top",
                )
            with c2:
                st.session_state.layers[i]["depth_bot"] = st.number_input(
                    "Depth bottom (m bgl)",
                    value=float(layer["depth_bot"]),
                    min_value=0.0,
                    step=0.1,
                    format="%.2f",
                    key=f"p1_layer_{uid}_depth_bot",
                )

            c3, c4 = st.columns(2)
            with c3:
                st.session_state.layers[i]["name"] = st.text_input(
                    "Layer name",
                    value=layer["name"],
                    key=f"p1_layer_{uid}_name",
                )
            with c4:
                sym_idx = SOIL_SYMBOLS.index(layer["symbol"]) if layer["symbol"] in SOIL_SYMBOLS else 0
                st.session_state.layers[i]["symbol"] = st.selectbox(
                    "Soil symbol (IS 1498)",
                    options=SOIL_SYMBOLS,
                    index=sym_idx,
                    key=f"p1_layer_{uid}_symbol",
                )

            st.markdown("**Unit weights**")
            cg1, cg2 = st.columns(2)
            with cg1:
                st.session_state.layers[i]["gamma_moist"] = st.number_input(
                    "γ_moist (kN/m³)",
                    value=float(layer["gamma_moist"]),
                    min_value=0.1,
                    step=0.1,
                    format="%.1f",
                    key=f"p1_layer_{uid}_gamma_moist",
                )
            with cg2:
                st.session_state.layers[i]["gamma_sat"] = st.number_input(
                    "γ_sat (kN/m³)",
                    value=float(layer["gamma_sat"]),
                    min_value=0.1,
                    step=0.1,
                    format="%.1f",
                    key=f"p1_layer_{uid}_gamma_sat",
                )

            st.markdown("**Drained strength parameters**")
            cd1, cd2 = st.columns(2)
            with cd1:
                st.session_state.layers[i]["c_prime"] = st.number_input(
                    "c′ (kPa)",
                    value=float(layer["c_prime"]),
                    min_value=0.0,
                    step=0.5,
                    format="%.1f",
                    key=f"p1_layer_{uid}_c_prime",
                )
            with cd2:
                st.session_state.layers[i]["phi_prime"] = st.number_input(
                    "φ′ (degrees)",
                    value=float(layer["phi_prime"]),
                    min_value=0.0,
                    max_value=89.9,
                    step=0.5,
                    format="%.1f",
                    key=f"p1_layer_{uid}_phi_prime",
                )

            st.markdown("**Undrained shear strength**")
            st.session_state.layers[i]["is_undrained"] = st.checkbox(
                "Use undrained (cu) — UU analysis",
                value=bool(layer["is_undrained"]),
                key=f"p1_layer_{uid}_is_undrained",
            )
            if st.session_state.layers[i]["is_undrained"]:
                st.session_state.layers[i]["cu"] = st.number_input(
                    "cu (kPa)",
                    value=float(layer["cu"]) if layer["cu"] else 0.0,
                    min_value=0.0,
                    step=1.0,
                    format="%.1f",
                    key=f"p1_layer_{uid}_cu",
                )

            st.markdown("**Consolidation (clay)**")
            st.session_state.layers[i]["is_clay"] = st.checkbox(
                "Clay (consolidation settlement applies)",
                value=bool(layer["is_clay"]),
                key=f"p1_layer_{uid}_is_clay",
            )
            if st.session_state.layers[i]["is_clay"]:
                st.caption("Initial values are editable assumptions when no data are present; verify each against lab/design data before use.")
                cc1, cc2, cc3 = st.columns(3)
                with cc1:
                    cc_val = layer["Cc"] if layer["Cc"] is not None else 0.3
                    st.session_state.layers[i]["Cc"] = st.number_input(
                        "Cc",
                        value=float(cc_val),
                        min_value=0.0,
                        step=0.01,
                        format="%.3f",
                        key=f"p1_layer_{uid}_Cc",
                    )
                with cc2:
                    cr_val = layer["Cr"] if layer["Cr"] is not None else 0.05
                    st.session_state.layers[i]["Cr"] = st.number_input(
                        "Cr",
                        value=float(cr_val),
                        min_value=0.0,
                        step=0.01,
                        format="%.3f",
                        key=f"p1_layer_{uid}_Cr",
                    )
                with cc3:
                    e0_val = layer["e0"] if layer["e0"] is not None else 0.9
                    st.session_state.layers[i]["e0"] = st.number_input(
                        "e₀ (void ratio)",
                        value=float(e0_val),
                        min_value=0.0,
                        step=0.01,
                        format="%.3f",
                        key=f"p1_layer_{uid}_e0",
                    )
                cp1, cp2 = st.columns(2)
                with cp1:
                    pc_val = layer["Pc_kPa"] if layer["Pc_kPa"] is not None else 100.0
                    st.session_state.layers[i]["Pc_kPa"] = st.number_input(
                        "Pc (kPa) — preconsolidation pressure",
                        value=float(pc_val),
                        min_value=0.0,
                        step=1.0,
                        format="%.1f",
                        key=f"p1_layer_{uid}_Pc_kPa",
                    )
                with cp2:
                    cv_val = layer["cv_m2s"] if layer["cv_m2s"] is not None else 1e-8
                    cv_input = st.number_input(
                        "cv (×10⁻⁸ m²/s)",
                        value=float(cv_val) * 1e8,
                        min_value=0.0,
                        step=0.1,
                        format="%.2f",
                        key=f"p1_layer_{uid}_cv_m2s",
                    )
                    st.session_state.layers[i]["cv_m2s"] = cv_input * 1e-8

            st.markdown("**SPT**")
            n_field_val = layer.get("N_field")
            old_refusal = bool(layer.get("N_refusal"))
            refusal = st.checkbox(
                "SPT refusal / incomplete penetration (not an exact N)",
                value=old_refusal,
                key=f"p1_layer_{uid}_refusal",
            )
            layer["N_refusal"] = refusal
            if refusal:
                layer["N_refusal_note"] = st.text_input(
                    "Reported refusal (blows / penetration)",
                    value=layer.get("N_refusal_note", ""),
                    key=f"p1_layer_{uid}_refusal_note",
                )
                layer["N_field"] = None
                layer["N_corrected"] = None
                st.caption("Refusal is retained as a note, not substituted as an exact N. Enter a justified Es if needed.")
            else:
                use_spt = st.checkbox(
                    "Has SPT N value",
                    value=(n_field_val is not None),
                    key=f"p1_layer_{uid}_has_spt",
                )
                if use_spt:
                    layer["N_field"] = st.number_input(
                        "N_field (observed SPT N)",
                        value=int(n_field_val) if n_field_val is not None else 10,
                        min_value=0,
                        step=1,
                        key=f"p1_layer_{uid}_N_field",
                        help="Enter an exact observed count, not an estimated refusal equivalent.",
                    )
                else:
                    layer["N_field"] = None
                if layer["N_field"] != n_field_val or old_refusal:
                    layer["N_corrected"] = None

            st.markdown("**Stiffness / Elastic Modulus (Es)**")
            es_val = layer.get("Es_kPa")
            use_custom_es = st.checkbox(
                "Specify measured / design Es (MPa)",
                value=(es_val is not None and es_val > 0),
                key=f"p1_layer_{uid}_has_es",
                help="Overrides SPT correlation in P5 immediate settlement. Leave unchecked to estimate Es from SPT N.",
            )
            if use_custom_es:
                es_mpa_default = (float(es_val) / 1000.0) if (es_val is not None and es_val > 0) else 15.0
                es_mpa = st.number_input(
                    "Es (MPa)",
                    value=es_mpa_default,
                    min_value=0.000001,
                    step=0.1,
                    format="%.6f",
                    key=f"p1_layer_{uid}_Es_MPa",
                )
                st.session_state.layers[i]["Es_kPa"] = es_mpa * 1000.0
            else:
                st.session_state.layers[i]["Es_kPa"] = None
                if not layer.get("is_clay", False):
                    est_kpa, n_preview = preview_es(layer)
                    if est_kpa is not None:
                        st.caption(
                            f"ℹ️ Existing SPT correlation preview (source and P5 consistency need verification): "
                            f"**Es ≈ {est_kpa / 1000.0:.2f} MPa** ({est_kpa:.0f} kPa) from N = {n_preview}."
                        )
                    else:
                        st.warning(
                            "⚠️ No usable positive SPT N or entered Es for this layer. "
                            "Provide a justified Es before immediate-settlement calculations."
                        )

            if st.button(f"🗑️ Delete layer {i + 1}", key=f"p1_layer_{uid}_delete"):
                to_delete = i

    # Perform deletion outside the loop
    if to_delete is not None:
        st.session_state.layers.pop(to_delete)
        sort_layers()
        st.rerun()

    sort_layers()

    # Keep the editor available so users can repair incomplete profiles.
    errors = []
    try:
        validate_profile(st.session_state.layers)
    except ValueError as exc:
        errors.append(str(exc))
    for i, layer in enumerate(st.session_state.layers, 1):
        moist, sat = layer["gamma_moist"], layer["gamma_sat"]
        if not (math.isfinite(moist) and math.isfinite(sat) and moist > 0 and sat > GAMMA_W and sat >= moist):
            errors.append(f"Layer {i}: require γ_moist > 0, γ_sat > γ_w and γ_sat ≥ γ_moist.")
        if layer.get("is_clay"):
            for name in ("Cc", "Cr", "e0", "Pc_kPa", "cv_m2s"):
                value = layer.get(name)
                if value is None or not math.isfinite(float(value)) or value < 0:
                    errors.append(f"Layer {i}: {name} must be finite and nonnegative.")
            if layer.get("cv_m2s") == 0:
                errors.append(f"Layer {i}: cv must be positive for time-settlement calculations.")
    st.session_state.profile_errors = errors
    st.session_state.profile_valid = not errors
    if errors:
        for error in errors:
            st.error(error)
        st.warning("Correct the profile before using it for calculations. Other pages must also check profile_valid or validate their inputs.")
    else:
        st.success("Soil profile geometry and basic unit-weight checks passed.")
        if st.session_state.foundation_depth > st.session_state.layers[-1]["depth_bot"]:
            st.warning("Preview foundation depth is below the defined profile.")

# ═══════════════════════════════════════════════════════════════════════════════
# RIGHT COLUMN — Profile Visualization
# ═══════════════════════════════════════════════════════════════════════════════
with col_viz:
    st.subheader("📊 Soil Profile Visualization")

    layers = st.session_state.layers
    wt_meas = st.session_state.wt_measured_bgl
    wt_des = st.session_state.wt_design_bgl
    DF = st.session_state.foundation_depth

    # Hatching patterns by symbol
    HATCH_MAP = {
        "SM": "///",
        "SP": "...",
        "SW": "xxx",
        "SC": "\\\\",
        "ML": "---",
        "CL": "---",
        "CI": "---",
        "CH": "---",
        "MH": "===",
        "GW": "++",
        "GP": "ooo",
        "GM": "///",
        "GC": "xxx",
        "Fill": "***",
    }
    # Colour map (light fills)
    COLOR_MAP = {
        "SM": "#d4c5a0",
        "SP": "#f0e68c",
        "SW": "#daa520",
        "SC": "#b8860b",
        "ML": "#90ee90",
        "CL": "#a2c4c9",
        "CI": "#7fb3d3",
        "CH": "#5b8db8",
        "MH": "#c5e0b4",
        "GW": "#c7b89d",
        "GP": "#e0cda9",
        "GM": "#b5a07a",
        "GC": "#9b7653",
        "Fill": "#d3d3d3",
    }

    if layers and st.session_state.profile_valid:
        max_depth = max(l["depth_bot"] for l in layers)
        fig, ax = plt.subplots(figsize=(4.5, min(18, max(6, max_depth * 0.6))))
        ax.set_xlim(0, 1)
        ax.set_ylim(max_depth + 0.5, -0.3)  # inverted y-axis (depth increases down)
        ax.set_yticks(sorted({l["depth_top"] for l in layers} | {l["depth_bot"] for l in layers}))
        ax.set_ylabel("Depth (m bgl)", fontsize=10)
        ax.set_xticks([])
        ax.set_title(
            f"Borehole: {st.session_state.borehole_name}\nGround RL = {st.session_state.ground_rl:.2f} m",
            fontsize=9,
        )

        for layer in layers:
            d_top = layer["depth_top"]
            d_bot = layer["depth_bot"]
            sym = layer["symbol"]
            color = COLOR_MAP.get(sym, "#cccccc")
            hatch = HATCH_MAP.get(sym, "/")

            rect = mpatches.FancyBboxPatch(
                (0.05, d_top),
                0.90,
                d_bot - d_top,
                boxstyle="square,pad=0",
                facecolor=color,
                edgecolor="black",
                linewidth=0.8,
                hatch=hatch,
            )
            ax.add_patch(rect)

            mid = (d_top + d_bot) / 2
            ax.text(
                0.50, mid,
                f"{sym}\n{d_top:.1f}–{d_bot:.1f} m",
                ha="center", va="center", fontsize=7.5,
                fontweight="bold", color="#1a1a1a",
            )

        # Ground-water table lines
        if 0 <= wt_meas <= max_depth:
            ax.axhline(wt_meas, color="blue", linewidth=1.5, linestyle="-", label=f"WT meas = {wt_meas:.1f} m")
            ax.text(0.97, wt_meas - 0.1, f"WT\n({wt_meas:.1f} m)", ha="right", va="bottom",
                    color="blue", fontsize=7)
        if 0 <= wt_des <= max_depth:
            ax.axhline(wt_des, color="blue", linewidth=1.5, linestyle="--", label=f"WT design = {wt_des:.1f} m")
            ax.text(0.03, wt_des - 0.1, f"WT_d\n({wt_des:.1f} m)", ha="left", va="bottom",
                    color="blue", fontsize=7)

        # Foundation depth Df
        if 0 <= DF <= max_depth:
            ax.axhline(DF, color="red", linewidth=1.5, linestyle="--", label=f"Df = {DF} m")
            ax.text(0.97, DF + 0.1, f"Df = {DF} m", ha="right", va="top",
                    color="red", fontsize=7, fontweight="bold")

        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(loc="lower right", fontsize=7, framealpha=0.8)
        ax.grid(axis="y", linestyle=":", linewidth=0.4, color="#aaaaaa")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    elif layers:
        st.info("Correct the profile validation errors to display the plot.")
    else:
        st.info("No layers defined. Add layers in the editor on the left.")

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE
# ═══════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("📄 Layer Summary")

if st.session_state.layers:
    rows = []
    for i, l in enumerate(st.session_state.layers):
        es_kpa = l.get("Es_kPa")
        if es_kpa is not None and es_kpa > 0:
            es_display = f"{es_kpa / 1000.0:.1f} MPa (entered)"
        else:
            est, _ = preview_es(l)
            es_display = f"{est / 1000.0:.1f} MPa (est. SPT)" if est is not None else "—"

        rows.append({
            "Layer": f"{i + 1} — {l['name']}",
            "Symbol": l["symbol"],
            "Depth (m)": f"{l['depth_top']:.1f} – {l['depth_bot']:.1f}",
            "γ_moist (kN/m³)": round(l["gamma_moist"], 1),
            "γ_sat (kN/m³)": round(l["gamma_sat"], 1),
            "c′ (kPa)": round(l["c_prime"], 1),
            "φ′ (°)": round(l["phi_prime"], 1),
            "Es": es_display,
            "N_field": "Refusal" if l.get("N_refusal") else (l["N_field"] if l["N_field"] is not None else "—"),
            "SPT refusal note": l.get("N_refusal_note", "") if l.get("N_refusal") else "",
            "Cc": round(l["Cc"], 3) if l.get("is_clay") and l["Cc"] is not None else "—",
            "cv (m²/s)": f"{l['cv_m2s']:.2e}" if l.get("is_clay") and l["cv_m2s"] is not None else "—",
        })
    df_summary = pd.DataFrame(rows)
    st.dataframe(df_summary, use_container_width=True, hide_index=True)
else:
    st.info("No layers to display.")
