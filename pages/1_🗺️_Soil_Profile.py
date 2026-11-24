"""
pages/1_🗺️_Soil_Profile.py
P1 — Soil Profile Input & Visualization
CE 402 Geotechnical Engineering Platform — IIT Mandi
"""

import copy
import streamlit as st
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

matplotlib.use("Agg")

from utils.constants import init_session_state, SOIL_SYMBOLS, DEFAULT_LAYER

st.set_page_config(page_title="P1 — Soil Profile", layout="wide")

# ── Session state ────────────────────────────────────────────────────────────
init_session_state()

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
        last = st.session_state.layers[-1] if st.session_state.layers else DEFAULT_LAYER
        new = copy.deepcopy(DEFAULT_LAYER)
        new["depth_top"] = last["depth_bot"]
        new["depth_bot"] = last["depth_bot"] + 1.5
        new["name"] = f"Layer {len(st.session_state.layers) + 1}"
        st.session_state.layers.append(new)
        sort_layers()
        st.rerun()

    # Keep track of which layer to delete (avoid mutating list during iteration)
    to_delete = None

    for i, layer in enumerate(st.session_state.layers):
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
                    step=0.1,
                    format="%.2f",
                    key=f"layer_{i}_depth_top",
                )
            with c2:
                st.session_state.layers[i]["depth_bot"] = st.number_input(
                    "Depth bottom (m bgl)",
                    value=float(layer["depth_bot"]),
                    step=0.1,
                    format="%.2f",
                    key=f"layer_{i}_depth_bot",
                )

            c3, c4 = st.columns(2)
            with c3:
                st.session_state.layers[i]["name"] = st.text_input(
                    "Layer name",
                    value=layer["name"],
                    key=f"layer_{i}_name",
                )
            with c4:
                sym_idx = SOIL_SYMBOLS.index(layer["symbol"]) if layer["symbol"] in SOIL_SYMBOLS else 0
                st.session_state.layers[i]["symbol"] = st.selectbox(
                    "Soil symbol (IS 1498)",
                    options=SOIL_SYMBOLS,
                    index=sym_idx,
                    key=f"layer_{i}_symbol",
                )

            st.markdown("**Unit weights**")
            cg1, cg2 = st.columns(2)
            with cg1:
                st.session_state.layers[i]["gamma_moist"] = st.number_input(
                    "γ_moist (kN/m³)",
                    value=float(layer["gamma_moist"]),
                    min_value=10.0,
                    max_value=25.0,
                    step=0.1,
                    format="%.1f",
                    key=f"layer_{i}_gamma_moist",
                )
            with cg2:
                st.session_state.layers[i]["gamma_sat"] = st.number_input(
                    "γ_sat (kN/m³)",
                    value=float(layer["gamma_sat"]),
                    min_value=10.0,
                    max_value=25.0,
                    step=0.1,
                    format="%.1f",
                    key=f"layer_{i}_gamma_sat",
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
                    key=f"layer_{i}_c_prime",
                )
            with cd2:
                st.session_state.layers[i]["phi_prime"] = st.number_input(
                    "φ′ (degrees)",
                    value=float(layer["phi_prime"]),
                    min_value=0.0,
                    max_value=50.0,
                    step=0.5,
                    format="%.1f",
                    key=f"layer_{i}_phi_prime",
                )

            st.markdown("**Undrained shear strength**")
            st.session_state.layers[i]["is_undrained"] = st.checkbox(
                "Use undrained (cu) — UU analysis",
                value=bool(layer["is_undrained"]),
                key=f"layer_{i}_is_undrained",
            )
            if st.session_state.layers[i]["is_undrained"]:
                st.session_state.layers[i]["cu"] = st.number_input(
                    "cu (kPa)",
                    value=float(layer["cu"]) if layer["cu"] else 0.0,
                    min_value=0.0,
                    step=1.0,
                    format="%.1f",
                    key=f"layer_{i}_cu",
                )

            st.markdown("**Consolidation (clay)**")
            st.session_state.layers[i]["is_clay"] = st.checkbox(
                "Clay (consolidation settlement applies)",
                value=bool(layer["is_clay"]),
                key=f"layer_{i}_is_clay",
            )
            if st.session_state.layers[i]["is_clay"]:
                cc1, cc2, cc3 = st.columns(3)
                with cc1:
                    cc_val = layer["Cc"] if layer["Cc"] is not None else 0.3
                    st.session_state.layers[i]["Cc"] = st.number_input(
                        "Cc",
                        value=float(cc_val),
                        min_value=0.0,
                        step=0.01,
                        format="%.3f",
                        key=f"layer_{i}_Cc",
                    )
                with cc2:
                    cr_val = layer["Cr"] if layer["Cr"] is not None else 0.05
                    st.session_state.layers[i]["Cr"] = st.number_input(
                        "Cr",
                        value=float(cr_val),
                        min_value=0.0,
                        step=0.01,
                        format="%.3f",
                        key=f"layer_{i}_Cr",
                    )
                with cc3:
                    e0_val = layer["e0"] if layer["e0"] is not None else 0.9
                    st.session_state.layers[i]["e0"] = st.number_input(
                        "e₀ (void ratio)",
                        value=float(e0_val),
                        min_value=0.0,
                        step=0.01,
                        format="%.3f",
                        key=f"layer_{i}_e0",
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
                        key=f"layer_{i}_Pc_kPa",
                    )
                with cp2:
                    cv_val = layer["cv_m2s"] if layer["cv_m2s"] is not None else 1e-8
                    cv_input = st.number_input(
                        "cv (×10⁻⁸ m²/s)",
                        value=float(cv_val) * 1e8,
                        min_value=0.0,
                        step=0.1,
                        format="%.2f",
                        key=f"layer_{i}_cv_m2s",
                    )
                    st.session_state.layers[i]["cv_m2s"] = cv_input * 1e-8

            st.markdown("**SPT**")
            n_field_val = layer["N_field"]
            use_spt = st.checkbox(
                "Has SPT N value",
                value=(n_field_val is not None),
                key=f"layer_{i}_has_spt",
            )
            if use_spt:
                n_default = int(n_field_val) if n_field_val is not None else 10
                st.session_state.layers[i]["N_field"] = st.number_input(
                    "N_field (observed SPT N)",
                    value=n_default,
                    min_value=1,
                    max_value=100,
                    step=1,
                    key=f"layer_{i}_N_field",
                )
            else:
                st.session_state.layers[i]["N_field"] = None

            if st.button(f"🗑️ Delete layer {i + 1}", key=f"layer_{i}_delete"):
                to_delete = i

    # Perform deletion outside the loop
    if to_delete is not None:
        st.session_state.layers.pop(to_delete)
        sort_layers()
        st.rerun()

    sort_layers()

# ═══════════════════════════════════════════════════════════════════════════════
# RIGHT COLUMN — Profile Visualization
# ═══════════════════════════════════════════════════════════════════════════════
with col_viz:
    st.subheader("📊 Soil Profile Visualization")

    layers = st.session_state.layers
    wt_meas = st.session_state.wt_measured_bgl
    wt_des = st.session_state.wt_design_bgl
    DF = 1.5  # foundation depth

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

    if layers:
        max_depth = max(l["depth_bot"] for l in layers)
        fig, ax = plt.subplots(figsize=(4.5, max(6, max_depth * 0.6)))
        ax.set_xlim(0, 1)
        ax.set_ylim(max_depth + 0.5, -0.3)  # inverted y-axis (depth increases down)
        ax.set_yticks([l["depth_top"] for l in layers] + [layers[-1]["depth_bot"]])
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

        ax.legend(loc="lower right", fontsize=7, framealpha=0.8)
        ax.grid(axis="y", linestyle=":", linewidth=0.4, color="#aaaaaa")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
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
        rows.append({
            "Layer": f"{i + 1} — {l['name']}",
            "Symbol": l["symbol"],
            "Depth (m)": f"{l['depth_top']:.1f} – {l['depth_bot']:.1f}",
            "γ_moist (kN/m³)": round(l["gamma_moist"], 1),
            "γ_sat (kN/m³)": round(l["gamma_sat"], 1),
            "c′ (kPa)": round(l["c_prime"], 1),
            "φ′ (°)": round(l["phi_prime"], 1),
            "N_field": l["N_field"] if l["N_field"] is not None else "—",
            "Cc": round(l["Cc"], 3) if l["Cc"] is not None else "—",
            "cv (m²/s)": f"{l['cv_m2s']:.2e}" if l["cv_m2s"] is not None else "—",
        })
    df_summary = pd.DataFrame(rows)
    st.dataframe(df_summary, use_container_width=True, hide_index=True)
else:
    st.info("No layers to display.")
