"""
pages/2_⚙️_Parameters.py
P2 — SPT Corrections & Strength Parameter Fitting
CE 402 Geotechnical Engineering Platform — IIT Mandi

Sections
--------
A  IS 2131:1981 SPT N corrections (overburden + dilatancy)
B  Mohr-Coulomb c′, φ′ fitting from direct-shear data (least squares)
C  Undrained shear strength cu from UU triaxial data
"""

import streamlit as st
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

from utils.constants import init_session_state, SOIL_SYMBOLS
from utils.spt_corrections import correct_spt, fit_mohr_coulomb

st.set_page_config(page_title="P2 — Parameters", layout="wide")

init_session_state()

st.title("⚙️ P2 — SPT Corrections & Parameter Fitting")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION A — IS 2131:1981 SPT N CORRECTIONS
# ══════════════════════════════════════════════════════════════════════════════
st.header("A — IS 2131:1981 SPT N Corrections")

st.info(
    "**Reference:** IS 2131:1981, Annex B — Overburden correction (Peck, Hanson & Thornburn 1974); "
    "Clause 4.6 — Dilatancy correction (Terzaghi & Peck 1967)."
)

layers_with_spt = [
    (i, l) for i, l in enumerate(st.session_state.layers) if l.get("N_field") is not None
]

if not layers_with_spt:
    st.warning("No layers with SPT N_field values. Add observed SPT N values in P1 — Soil Profile.")
else:
    if st.button("🔄 Compute / Refresh SPT Corrections", key="btn_compute_spt"):
        results = correct_spt(st.session_state.layers, st.session_state.wt_design_bgl)
        st.session_state["spt_results"] = results

    # Auto-compute on first visit
    if "spt_results" not in st.session_state:
        st.session_state["spt_results"] = correct_spt(
            st.session_state.layers, st.session_state.wt_design_bgl
        )

    spt_results = st.session_state["spt_results"]

    if spt_results:
        rows = []
        for r in spt_results:
            layer = st.session_state.layers[r["layer_idx"]]
            rows.append({
                "Layer": f"{r['layer_idx'] + 1} — {layer['name']}",
                "Symbol": layer["symbol"],
                "Depth mid (m)": f"{r['depth_mid']:.2f}",
                "σ′v (kPa)": f"{r['sigma_v']:.1f}",
                "CN": f"{r['CN']:.3f}",
                "N_field": r["N_field"],
                "N_corr1": r["N_corr1"],
                "Dilatancy?": "✅ Yes" if r["dilatancy_applied"] else "No",
                "N_corrected": r["N_corrected"],
            })
        df_spt = pd.DataFrame(rows)
        st.dataframe(df_spt, use_container_width=True, hide_index=True)

        st.caption(
            "**Formulae used:**  "
            "C_N = 0.77 × log₁₀(2000 / σ′v) [clamped 0.5 – 2.0]; "
            "Dilatancy: N_cor = 15 + 0.5(N_corr1 − 15) for SM/ML/SP below WT when N_corr1 > 15."
        )
    else:
        st.info("No SPT results computed.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION B — MOHR-COULOMB FITTING FROM DIRECT SHEAR
# ══════════════════════════════════════════════════════════════════════════════
st.header("B — Strength Parameter Fitting (Direct Shear — Least Squares)")
st.caption(
    "Fits τ = c′ + σn · tan(φ′) using least-squares linear regression "
    "(Direct shear test per IS 2720 Part 13:1986)."
)

# Initialise direct-shear data table in session state
if "ds_data" not in st.session_state:
    st.session_state["ds_data"] = [
        {"sigma_n": 50.0, "tau": 35.0},
        {"sigma_n": 100.0, "tau": 65.0},
        {"sigma_n": 200.0, "tau": 115.0},
    ]

col_ds_ctrl, _ = st.columns([1, 3])
with col_ds_ctrl:
    if st.button("➕ Add data point", key="btn_ds_add"):
        st.session_state["ds_data"].append({"sigma_n": 0.0, "tau": 0.0})
        st.rerun()
    if st.button("➖ Remove last point", key="btn_ds_remove"):
        if len(st.session_state["ds_data"]) > 2:
            st.session_state["ds_data"].pop()
            st.rerun()

st.markdown("**Enter direct shear data points:**")
ds_cols = st.columns([0.4, 0.4, 0.2])
ds_cols[0].markdown("**σn (kPa) — Normal stress**")
ds_cols[1].markdown("**τf (kPa) — Shear stress at failure**")

to_remove_ds = None
for j, row in enumerate(st.session_state["ds_data"]):
    c1, c2, c3 = st.columns([0.4, 0.4, 0.2])
    with c1:
        st.session_state["ds_data"][j]["sigma_n"] = st.number_input(
            f"σn #{j + 1}",
            value=float(row["sigma_n"]),
            step=1.0,
            format="%.1f",
            key=f"ds_sigma_{j}",
            label_visibility="collapsed",
        )
    with c2:
        st.session_state["ds_data"][j]["tau"] = st.number_input(
            f"τf #{j + 1}",
            value=float(row["tau"]),
            step=1.0,
            format="%.1f",
            key=f"ds_tau_{j}",
            label_visibility="collapsed",
        )
    with c3:
        if st.button("🗑️", key=f"ds_del_{j}") and len(st.session_state["ds_data"]) > 2:
            to_remove_ds = j

if to_remove_ds is not None:
    st.session_state["ds_data"].pop(to_remove_ds)
    st.rerun()

if st.button("📐 Fit c′ and φ′", key="btn_fit_mc"):
    sigma_n_vals = [r["sigma_n"] for r in st.session_state["ds_data"]]
    tau_vals = [r["tau"] for r in st.session_state["ds_data"]]
    if len(sigma_n_vals) < 2:
        st.error("At least 2 data points are required.")
    else:
        try:
            c_fit, phi_fit, r2 = fit_mohr_coulomb(sigma_n_vals, tau_vals)
            st.session_state["mc_fit"] = {"c": c_fit, "phi": phi_fit, "r2": r2,
                                          "sigma_n": sigma_n_vals, "tau": tau_vals}
        except Exception as e:
            st.error(f"Fitting error: {e}")

if "mc_fit" in st.session_state:
    fit = st.session_state["mc_fit"]
    col_res, col_plot = st.columns([1, 1.4])

    with col_res:
        st.success(
            f"**c′ = {fit['c']:.2f} kPa**  \n"
            f"**φ′ = {fit['phi']:.2f}°**  \n"
            f"R² = {fit['r2']:.4f}"
        )
        st.caption(
            "Method: Least-squares linear regression, τ = c′ + σn · tan(φ′)  \n"
            "Reference: IS 2720 (Part 13):1986 — Direct shear test for determination of c′ and φ′."
        )

        # Copy to layer
        layer_names = [
            f"{i + 1} — {l['name']}" for i, l in enumerate(st.session_state.layers)
        ]
        target_layer = st.selectbox(
            "Copy fitted c′, φ′ to layer:", layer_names, key="mc_copy_layer"
        )
        if st.button("📋 Apply to layer", key="btn_mc_apply"):
            idx = layer_names.index(target_layer)
            st.session_state.layers[idx]["c_prime"] = round(fit["c"], 2)
            st.session_state.layers[idx]["phi_prime"] = round(fit["phi"], 2)
            st.success(
                f"Applied c′ = {fit['c']:.2f} kPa, φ′ = {fit['phi']:.2f}° "
                f"to Layer {idx + 1}."
            )

    with col_plot:
        sigma_n_arr = np.asarray(fit["sigma_n"])
        tau_arr = np.asarray(fit["tau"])
        sigma_range = np.linspace(0, max(sigma_n_arr) * 1.15, 200)
        import math as _math
        tau_fit_line = fit["c"] + sigma_range * _math.tan(_math.radians(fit["phi"]))

        fig, ax = plt.subplots(figsize=(5, 3.5))
        ax.scatter(sigma_n_arr, tau_arr, color="steelblue", zorder=5, label="Data points")
        ax.plot(sigma_range, tau_fit_line, "r-", linewidth=1.8,
                label=f"Fit: τ = {fit['c']:.1f} + σn·tan({fit['phi']:.1f}°)")
        ax.set_xlabel("Normal stress σn (kPa)")
        ax.set_ylabel("Shear stress τf (kPa)")
        ax.set_title("Mohr-Coulomb Failure Envelope", fontsize=10)
        ax.legend(fontsize=8)
        ax.grid(True, linestyle=":", alpha=0.6)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION C — UNDRAINED SHEAR STRENGTH FROM UU TRIAXIAL
# ══════════════════════════════════════════════════════════════════════════════
st.header("C — Undrained Shear Strength (cu) from UU Triaxial")
st.caption(
    "IS 2720 (Part 11):1993 — Unconsolidated undrained (UU) triaxial compression test "
    "(φu ≈ 0° assumed; cu = deviator stress at failure / 2, averaged over all tests)."
)

if "uu_data" not in st.session_state:
    st.session_state["uu_data"] = [
        {"sigma3": 50.0, "deviator": 80.0},
        {"sigma3": 100.0, "deviator": 82.0},
    ]

col_uu_ctrl, _ = st.columns([1, 3])
with col_uu_ctrl:
    if st.button("➕ Add UU test", key="btn_uu_add"):
        st.session_state["uu_data"].append({"sigma3": 0.0, "deviator": 0.0})
        st.rerun()
    if st.button("➖ Remove last test", key="btn_uu_remove"):
        if len(st.session_state["uu_data"]) > 1:
            st.session_state["uu_data"].pop()
            st.rerun()

st.markdown("**Enter UU triaxial test data:**")
uu_hdr = st.columns([0.4, 0.4, 0.2])
uu_hdr[0].markdown("**σ₃ (kPa) — Cell pressure**")
uu_hdr[1].markdown("**Deviator stress at failure (kPa)**")

to_remove_uu = None
for j, row in enumerate(st.session_state["uu_data"]):
    cu1, cu2, cu3 = st.columns([0.4, 0.4, 0.2])
    with cu1:
        st.session_state["uu_data"][j]["sigma3"] = st.number_input(
            f"σ₃ #{j + 1}",
            value=float(row["sigma3"]),
            step=1.0,
            format="%.1f",
            key=f"uu_sigma3_{j}",
            label_visibility="collapsed",
        )
    with cu2:
        st.session_state["uu_data"][j]["deviator"] = st.number_input(
            f"Dev #{j + 1}",
            value=float(row["deviator"]),
            step=1.0,
            format="%.1f",
            key=f"uu_dev_{j}",
            label_visibility="collapsed",
        )
    with cu3:
        if st.button("🗑️", key=f"uu_del_{j}") and len(st.session_state["uu_data"]) > 1:
            to_remove_uu = j

if to_remove_uu is not None:
    st.session_state["uu_data"].pop(to_remove_uu)
    st.rerun()

if st.button("🧮 Compute cu", key="btn_compute_cu"):
    devs = [r["deviator"] for r in st.session_state["uu_data"]]
    cu_vals = [d / 2.0 for d in devs]
    cu_avg = float(np.mean(cu_vals))
    st.session_state["cu_result"] = {"cu": cu_avg, "individual": cu_vals}

if "cu_result" in st.session_state:
    cu_res = st.session_state["cu_result"]
    cu_avg = cu_res["cu"]

    st.success(
        f"**cu = {cu_avg:.2f} kPa** (average of {len(cu_res['individual'])} tests)  \n"
        "φu = 0° assumed (UU triaxial test per IS 2720 Part 11:1993; Skempton 1954)."
    )

    # Individual cu values table
    cu_df = pd.DataFrame({
        "Test": [f"T{j + 1}" for j in range(len(st.session_state["uu_data"]))],
        "σ₃ (kPa)": [r["sigma3"] for r in st.session_state["uu_data"]],
        "Deviator (kPa)": [r["deviator"] for r in st.session_state["uu_data"]],
        "cu = Dev/2 (kPa)": [round(v, 2) for v in cu_res["individual"]],
    })
    st.dataframe(cu_df, use_container_width=False, hide_index=True)

    # Copy to clay layer
    clay_layers = [
        (i, l) for i, l in enumerate(st.session_state.layers) if l.get("is_clay")
    ]
    if clay_layers:
        clay_names = [f"{i + 1} — {l['name']}" for i, l in clay_layers]
        target_cu = st.selectbox(
            "Copy cu to clay layer:", clay_names, key="cu_copy_layer"
        )
        if st.button("📋 Apply cu to layer", key="btn_cu_apply"):
            # Find the actual layer index from the display name
            chosen_name = target_cu
            for i, l in clay_layers:
                if chosen_name == f"{i + 1} — {l['name']}":
                    st.session_state.layers[i]["cu"] = round(cu_avg, 2)
                    st.session_state.layers[i]["is_undrained"] = True
                    st.success(
                        f"Applied cu = {cu_avg:.2f} kPa to Layer {i + 1} "
                        f"({l['name']}) and set undrained flag."
                    )
                    break
    else:
        st.info("No clay layers found. Mark a layer as 'Clay' in P1 to enable copy.")
