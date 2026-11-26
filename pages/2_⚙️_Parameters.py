"""
pages/2_⚙️_Parameters.py
P2 — IS 2131:1981 SPT Corrections & Strength Parameter Fitting
CE 402 Geotechnical Engineering Platform — IIT Mandi
All units strictly SI: m, kPa, kN/m³, deg.

Sections
--------
A  IS 2131:1981 SPT N corrections (overburden Cl. 3.6.1 + dilatancy Cl. 3.6.2)
B  Mohr-Coulomb c′, φ′ fitting from direct-shear data (OLS)
C  Undrained shear strength cu from UU triaxial data
"""

import math
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import streamlit as st

matplotlib.use("Agg")

from utils.constants import init_session_state
from utils.spt_corrections import (
    SOIL_CLASSES,
    build_default_spt_records,
    correct_spt_records,
    fit_mohr_coulomb,
)

st.set_page_config(page_title="P2 — Parameters (IS 2131:1981)", layout="wide")

init_session_state()

st.title("⚙️ P2 — SPT Corrections & Parameter Fitting")
st.caption("IS 2131:1981 SPT N Corrections · Direct Shear OLS · UU Triaxial cu | SI units: m, kPa, deg")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION A — IS 2131:1981 SPT N CORRECTIONS
# ══════════════════════════════════════════════════════════════════════════════
st.header("A — IS 2131:1981 SPT N Corrections")

wt_measured = float(st.session_state.wt_measured_bgl)
wt_design = float(st.session_state.wt_design_bgl)

wt_c1, wt_c2 = st.columns(2)
wt_c1.metric(
    "Measured WT used for SPT corrections (test-time)",
    f"{wt_measured:.2f} m bgl",
    help="IS 2131:1981 uses the groundwater table measured during boring for σ′v and dilatancy.",
)
wt_c2.metric(
    "Design WT (for bearing/settlement only — NOT used here)",
    f"{wt_design:.2f} m bgl",
)

st.info(
    "**IS 2131:1981 Reference:** "
    "**Cl. 3.6.1 & Fig. 1** — Overburden correction $C_N = \\min(2.0,\\; 0.77\\log_{10}(2000/\\sigma'_v))$ "
    "applies **only** to cohesionless sands (`Fine/Silty Sand`, `Coarse/Medium Sand`); "
    "**Cl. 3.6.2** — Dilatancy correction $N'' = 15 + 0.5(N' - 15)$ applies **only** to `Fine/Silty Sand` "
    "below measured WT (`wt_measured_bgl`) when $N' > 15$. Raw $N \\ge 100$ is flagged as **Refusal**."
)

if "spt_records" not in st.session_state:
    st.session_state["spt_records"] = build_default_spt_records(st.session_state.layers)

ctrl_col1, ctrl_col2 = st.columns([1.4, 2.6])
with ctrl_col1:
    if st.button("🔄 Sync / Reset SPT rows from P1 Layers", key="btn_reset_spt_records"):
        st.session_state["spt_records"] = build_default_spt_records(st.session_state.layers)
        st.rerun()

st.markdown("**Depth-specific SPT test records** *(add, edit, or delete rows freely)*:")

df_input = pd.DataFrame(
    st.session_state["spt_records"]
    if st.session_state["spt_records"]
    else [{"depth_m": 1.5, "soil_class": "Fine/Silty Sand", "N_field": 12}]
)

edited_df = st.data_editor(
    df_input,
    num_rows="dynamic",
    use_container_width=True,
    key="spt_data_editor",
    column_config={
        "depth_m": st.column_config.NumberColumn(
            "Test Depth (m bgl)",
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            format="%.2f",
            required=True,
        ),
        "soil_class": st.column_config.SelectboxColumn(
            "Soil Class (IS 2131 Applicability)",
            options=SOIL_CLASSES,
            required=True,
        ),
        "N_field": st.column_config.NumberColumn(
            "Raw N_field (blows/300 mm)",
            min_value=0,
            max_value=500,
            step=1,
            format="%d",
            required=True,
        ),
    },
)

# Persist valid edited records back to session state
valid_records = []
for _, row in edited_df.iterrows():
    if pd.notna(row.get("depth_m")) and pd.notna(row.get("N_field")) and pd.notna(row.get("soil_class")):
        valid_records.append({
            "depth_m": float(row["depth_m"]),
            "soil_class": str(row["soil_class"]),
            "N_field": int(round(float(row["N_field"]))),
        })

st.session_state["spt_records"] = valid_records

if not valid_records:
    st.warning("Add at least one SPT test record above (or define N_field values in P1).")
else:
    spt_results = correct_spt_records(
        valid_records,
        st.session_state.layers,
        wt_measured_bgl=wt_measured,
    )
    st.session_state["spt_results"] = spt_results

    display_rows = []
    for r in spt_results:
        if r["is_refusal"]:
            cn_disp = "—"
            n_prime_disp = "Refusal"
            n_final_disp = "Refusal"
        elif r["CN"] is None:
            cn_disp = "—"
            n_prime_disp = f"{r['N_prime']}"
            n_final_disp = f"{r['N_final']}"
        else:
            cn_disp = f"{r['CN']:.3f}"
            n_prime_disp = f"{r['N_prime']}"
            n_final_disp = f"{r['N_final']}"

        display_rows.append({
            "Depth (m)": f"{r['depth_m']:.2f}",
            "Soil Class": r["soil_class"],
            "Raw N (blows/300 mm)": r["N_field"],
            "σ′v (kPa)": f"{r['sigma_v']:.2f}",
            "C_N (—)": cn_disp,
            "N′ (—)": n_prime_disp,
            "Below Meas. WT?": "Yes" if r["below_wt"] else "No",
            "Dilatancy Applied?": "✅ Yes" if r["dilatancy_applied"] else "No",
            "Final N″ (—)": n_final_disp,
            "Notes": r["notes"],
        })

    df_spt = pd.DataFrame(display_rows)
    st.dataframe(df_spt, use_container_width=True, hide_index=True)

    # Sync layer-averaged non-refusal Final N'' back to P1 layers for downstream P5
    if st.button("📋 Apply layer-averaged Final N″ to P1 Soil Layers (for P5)", key="btn_apply_spt_layers"):
        updated_msgs = []
        sorted_indices = sorted(
            range(len(st.session_state.layers)),
            key=lambda idx: float(st.session_state.layers[idx]["depth_top"]),
        )
        for pos, idx in enumerate(sorted_indices):
            lyr = st.session_state.layers[idx]
            d_top = float(lyr["depth_top"])
            d_bot = float(lyr["depth_bot"])
            is_last = pos == len(sorted_indices) - 1
            in_layer = [
                r["N_final"]
                for r in spt_results
                if (not r["is_refusal"])
                and (r["N_final"] is not None)
                and (d_top <= r["depth_m"] < d_bot or (is_last and d_top <= r["depth_m"] <= d_bot))
            ]
            if in_layer:
                avg_n = int(round(sum(in_layer) / len(in_layer)))
                lyr["N_corrected"] = avg_n
                updated_msgs.append(f"Layer {idx + 1} ({lyr['name']}): N_corrected = {avg_n}")
        if updated_msgs:
            st.success("Updated P1 layers: " + " | ".join(updated_msgs))
        else:
            st.warning("No non-refusal SPT records matched P1 layer depth intervals.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION B — MOHR-COULOMB FITTING FROM DIRECT SHEAR (OLS)
# ══════════════════════════════════════════════════════════════════════════════
st.header("B — Strength Parameter Fitting (Direct Shear — Ordinary Least Squares)")
st.caption("Fits τ_f = c′ + σ_n · tan(φ′) by OLS linear regression (SI units: kPa, deg).")

if "ds_data" not in st.session_state:
    st.session_state["ds_data"] = [
        {"sigma_n": 50.0, "tau": 35.0},
        {"sigma_n": 100.0, "tau": 65.0},
        {"sigma_n": 150.0, "tau": 95.0},
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

st.markdown("**Enter direct shear test data points:**")
ds_cols = st.columns([0.4, 0.4, 0.2])
ds_cols[0].markdown("**Normal stress σ_n (kPa)**")
ds_cols[1].markdown("**Peak shear stress τ_f (kPa)**")

to_remove_ds = None
for j, row in enumerate(st.session_state["ds_data"]):
    c1, c2, c3 = st.columns([0.4, 0.4, 0.2])
    with c1:
        st.session_state["ds_data"][j]["sigma_n"] = st.number_input(
            f"σ_n (kPa) #{j + 1}",
            value=float(row["sigma_n"]),
            step=1.0,
            format="%.2f",
            key=f"ds_sigma_{j}",
            label_visibility="collapsed",
        )
    with c2:
        st.session_state["ds_data"][j]["tau"] = st.number_input(
            f"τ_f (kPa) #{j + 1}",
            value=float(row["tau"]),
            step=1.0,
            format="%.2f",
            key=f"ds_tau_{j}",
            label_visibility="collapsed",
        )
    with c3:
        if st.button("🗑️", key=f"ds_del_{j}") and len(st.session_state["ds_data"]) > 2:
            to_remove_ds = j

if to_remove_ds is not None:
    st.session_state["ds_data"].pop(to_remove_ds)
    st.rerun()

if st.button("📐 Fit c′ (kPa) and φ′ (deg)", key="btn_fit_mc"):
    sigma_n_vals = [r["sigma_n"] for r in st.session_state["ds_data"]]
    tau_vals = [r["tau"] for r in st.session_state["ds_data"]]
    if len(sigma_n_vals) < 2:
        st.error("At least 2 data points are required.")
    else:
        try:
            c_fit, phi_fit, r2 = fit_mohr_coulomb(sigma_n_vals, tau_vals)
            st.session_state["mc_fit"] = {
                "c": c_fit,
                "phi": phi_fit,
                "r2": r2,
                "sigma_n": sigma_n_vals,
                "tau": tau_vals,
            }
        except Exception as e:
            st.error(f"Fitting error: {e}")

if "mc_fit" in st.session_state:
    fit = st.session_state["mc_fit"]
    col_res, col_plot = st.columns([1, 1.4])

    with col_res:
        st.success(
            f"**c′ = {fit['c']:.2f} kPa**  \n"
            f"**φ′ = {fit['phi']:.2f} deg**  \n"
            f"**R² = {fit['r2']:.4f} (—)**"
        )
        st.caption(
            "Method: Ordinary Least Squares regression, τ_f = c′ + σ_n · tan(φ′) "
            "(IS 2720 Part 13 / IS 2131:1981)."
        )

        layer_names = [
            f"{i + 1} — {l['name']}" for i, l in enumerate(st.session_state.layers)
        ]
        target_layer = st.selectbox(
            "Copy fitted c′ (kPa), φ′ (deg) to layer:", layer_names, key="mc_copy_layer"
        )
        if st.button("📋 Apply to layer", key="btn_mc_apply"):
            idx = layer_names.index(target_layer)
            st.session_state.layers[idx]["c_prime"] = max(0.0, round(fit["c"], 2))
            st.session_state.layers[idx]["phi_prime"] = round(fit["phi"], 2)
            st.success(
                f"Applied c′ = {max(0.0, fit['c']):.2f} kPa, φ′ = {fit['phi']:.2f} deg "
                f"to Layer {idx + 1}."
            )

    with col_plot:
        sigma_n_arr = np.asarray(fit["sigma_n"], dtype=float)
        tau_arr = np.asarray(fit["tau"], dtype=float)
        sigma_range = np.linspace(0.0, max(float(np.max(sigma_n_arr)), 10.0) * 1.15, 200)
        # Source: Mohr-Coulomb linear failure envelope τ_f = c' + σ_n tan(φ')
        tau_fit_line = fit["c"] + sigma_range * math.tan(math.radians(fit["phi"]))

        fig, ax = plt.subplots(figsize=(5, 3.5))
        ax.scatter(sigma_n_arr, tau_arr, color="steelblue", zorder=5, label="Lab data")
        ax.plot(
            sigma_range,
            tau_fit_line,
            "r-",
            linewidth=1.8,
            label=f"OLS Fit: τ = {fit['c']:.2f} + σ_n·tan({fit['phi']:.2f}°)",
        )
        ax.set_xlabel("Normal stress σ_n (kPa)")
        ax.set_ylabel("Shear stress τ_f (kPa)")
        ax.set_title("Mohr-Coulomb Failure Envelope (OLS)", fontsize=10)
        ax.legend(fontsize=8)
        ax.grid(True, linestyle=":", alpha=0.6)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION C — UNDRAINED SHEAR STRENGTH FROM UU TRIAXIAL
# ══════════════════════════════════════════════════════════════════════════════
st.header("C — Undrained Shear Strength cu (kPa) from UU Triaxial")
st.caption(
    "For saturated clay UU triaxial tests (φ_u = 0 deg): "
    "c_u = (σ₁ − σ₃)_f / 2 (kPa). Average over all tests."
)

if "uu_data" not in st.session_state:
    st.session_state["uu_data"] = [
        {"sigma3": 50.0, "deviator": 57.2},
        {"sigma3": 100.0, "deviator": 55.8},
        {"sigma3": 150.0, "deviator": 58.1},
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
uu_hdr[0].markdown("**Cell pressure σ₃ (kPa)**")
uu_hdr[1].markdown("**Deviator stress at failure Δσ_f (kPa)**")

to_remove_uu = None
for j, row in enumerate(st.session_state["uu_data"]):
    cu1, cu2, cu3 = st.columns([0.4, 0.4, 0.2])
    with cu1:
        st.session_state["uu_data"][j]["sigma3"] = st.number_input(
            f"σ₃ (kPa) #{j + 1}",
            value=float(row["sigma3"]),
            step=1.0,
            format="%.2f",
            key=f"uu_sigma3_{j}",
            label_visibility="collapsed",
        )
    with cu2:
        st.session_state["uu_data"][j]["deviator"] = st.number_input(
            f"Δσ_f (kPa) #{j + 1}",
            value=float(row["deviator"]),
            step=1.0,
            format="%.2f",
            key=f"uu_dev_{j}",
            label_visibility="collapsed",
        )
    with cu3:
        if st.button("🗑️", key=f"uu_del_{j}") and len(st.session_state["uu_data"]) > 1:
            to_remove_uu = j

if to_remove_uu is not None:
    st.session_state["uu_data"].pop(to_remove_uu)
    st.rerun()

if st.button("🧮 Compute cu (kPa)", key="btn_compute_cu"):
    devs = [float(r["deviator"]) for r in st.session_state["uu_data"]]
    # Source: IS 2720 Part 11 / Mohr circle for φ_u = 0: c_u = (σ1 - σ3)_f / 2
    cu_vals = [d / 2.0 for d in devs]
    cu_avg = float(sum(cu_vals) / len(cu_vals))
    st.session_state["cu_result"] = {"cu": cu_avg, "individual": cu_vals}

if "cu_result" in st.session_state:
    cu_res = st.session_state["cu_result"]
    cu_avg = cu_res["cu"]

    st.success(
        f"**c_u = {cu_avg:.2f} kPa** (average of {len(cu_res['individual'])} tests)  \n"
        "φ_u = 0.0 deg assumed (UU test on saturated cohesive soil — IS 2720 Part 11)."
    )

    cu_df = pd.DataFrame({
        "Test": [f"T{j + 1}" for j in range(len(st.session_state["uu_data"]))],
        "σ₃ (kPa)": [round(float(r["sigma3"]), 2) for r in st.session_state["uu_data"]],
        "Deviator Δσ_f (kPa)": [round(float(r["deviator"]), 2) for r in st.session_state["uu_data"]],
        "c_u = Δσ_f / 2 (kPa)": [round(v, 2) for v in cu_res["individual"]],
    })
    st.dataframe(cu_df, use_container_width=False, hide_index=True)

    clay_layers = [
        (i, l) for i, l in enumerate(st.session_state.layers) if l.get("is_clay")
    ]
    if clay_layers:
        clay_names = [f"{i + 1} — {l['name']}" for i, l in clay_layers]
        target_cu = st.selectbox(
            "Copy cu (kPa) to clay layer:", clay_names, key="cu_copy_layer"
        )
        if st.button("📋 Apply cu to layer", key="btn_cu_apply"):
            for i, l in clay_layers:
                if target_cu == f"{i + 1} — {l['name']}":
                    st.session_state.layers[i]["cu"] = round(cu_avg, 2)
                    st.session_state.layers[i]["is_undrained"] = True
                    st.success(
                        f"Applied cu = {cu_avg:.2f} kPa to Layer {i + 1} "
                        f"({l['name']}) and enabled undrained (φ = 0) flag."
                    )
                    break
    else:
        st.info("No clay layers found. Mark a layer as 'Clay' in P1 to enable copy.")
