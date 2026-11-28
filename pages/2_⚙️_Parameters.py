"""P2 — SPT corrections and parameter fitting, SI units.
Uses the corrected utils/bearing_capacity.py, constants.py and spt_corrections.py.
"""
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st

from utils.demo_data import demo_notice
from utils.constants import init_session_state
from utils.spt_corrections import (
    SOIL_CLASSES, MAX_CHART_STRESS_KPA, build_default_spt_records,
    correct_spt_records, apply_spt_to_layers, fit_mohr_coulomb, fit_uu_cu,
)
from utils.bearing_capacity import validate_profile

st.set_page_config(page_title="P2 — Parameters (IS 2131:1981)", layout="wide")
init_session_state()
demo_notice(st)
st.title("⚙️ P2 — SPT Corrections & Parameter Fitting")
st.caption("IS 2131:1981 SPT N corrections · Direct shear OLS · UU triaxial | SI units")


def editor(name, initial, columns, config):
    """Keep the data_editor base stable across reruns; store edited rows separately.

    The revision key changes on explicit reset/import to discard old widget edits.
    The last edited rows seed a new widget after leaving and returning to this page.
    """
    base_key = f"p2_{name}_base"
    rev_key = f"p2_{name}_revision"
    if rev_key not in st.session_state:
        st.session_state[rev_key] = 0
    widget_key = f"p2_{name}_editor_{st.session_state[rev_key]}"
    if base_key not in st.session_state or widget_key not in st.session_state:
        st.session_state[base_key] = initial
    df = pd.DataFrame(st.session_state[base_key], columns=columns)
    # Typed empty columns allow adding records to a completely empty table.
    for col, spec in columns.items():
        df[col] = df[col].astype(spec)
    return st.data_editor(df, num_rows="dynamic", hide_index=True,
                          use_container_width=True, key=widget_key, column_config=config)


def reset_editor(name, rows, data_key):
    st.session_state[data_key] = rows
    st.session_state[f"p2_{name}_base"] = rows
    key = f"p2_{name}_revision"
    st.session_state[key] = st.session_state.get(key, 0) + 1
    st.rerun()


def blank_safe(value):
    return None if pd.isna(value) else value


def records_from_spt(df):
    rows = []
    for _, row in df.iterrows():
        depth = blank_safe(row["depth_m"])
        soil = blank_safe(row["soil_class"])
        n = blank_safe(row["N_field"])
        refusal = bool(row["is_refusal"]) if pd.notna(row["is_refusal"]) else False
        excluded = bool(row["excluded"]) if pd.notna(row["excluded"]) else False
        estimated = bool(row["estimated_depth"]) if pd.notna(row["estimated_depth"]) else False
        note = str(row["note"]) if pd.notna(row["note"]) else ""
        if depth is None and soil is None and n is None and not (refusal or excluded or estimated or note):
            continue  # entirely empty editor row
        rows.append(dict(depth_m=depth, soil_class=soil, N_field=n,
                         is_refusal=refusal, excluded=excluded, estimated_depth=estimated, note=note))
    return rows


def lab_rows(df, keys):
    rows = []
    for _, row in df.iterrows():
        record = {key: blank_safe(row[key]) for key in keys}
        if any(v is not None for v in record.values()):
            rows.append(record)
    return rows


def set_layer_value(layer, key, value):
    """Preserve the P1 schema; synchronize existing stable-ID widget state if present."""
    layer[key] = value
    uid = layer.get("_ui_id")
    widget_key = f"p1_layer_{uid}_{key}"
    if uid and widget_key in st.session_state:
        st.session_state[widget_key] = value


def choose_layer(layers, label, key):
    options = list(range(len(layers)))
    return st.selectbox(label, options, key=key,
                        format_func=lambda i: f"{i+1} — {layers[i].get('name', 'Layer')} ({layers[i]['depth_top']:g}–{layers[i]['depth_bot']:g} m)")


# A — SPT corrections
st.header("A — IS 2131:1981 SPT N Corrections")
wt_measured = float(st.session_state.wt_measured_bgl)
wt_design = float(st.session_state.wt_design_bgl)
wc1, wc2 = st.columns(2)
wc1.metric("Measured WT used for SPT", f"{wt_measured:.2f} m bgl")
wc2.metric("Design WT (not used for SPT)", f"{wt_design:.2f} m bgl")
st.info("IS 2131:1981 cl. 3.6.1 & Fig. 1: the existing logarithmic approximation "
        "to the correction chart is used only for its plotted stress range. "
        "Cl. 3.6.2: dilatancy applies after overburden correction to submerged fine sands/silts when N′ > 15.")
st.latex(r"C_N \approx \min(2,\,0.77\log_{10}(2000/\sigma'_v)),\quad N'=C_N N")
st.latex(r"N''=15+0.5(N'-15)")
st.caption(f"Chart range: 0–{MAX_CHART_STRESS_KPA:.2f} kPa. Select the actual test soil class; IS 1498 symbols alone do not establish grain size or SPT validity.")
st.caption("Refusal or incomplete penetration is a field observation (cl. 3.3.3). Enter the blows/penetration in Note and flag refusal. Legacy N ≥ 100 is also conservatively flagged; this is an app convention, not an IS refusal threshold.")

try:
    if "spt_records" not in st.session_state:
        st.session_state.spt_records = build_default_spt_records(st.session_state.layers)
    if st.button("🔄 Sync / Reset SPT rows from P1 Layers", key="btn_reset_spt_records"):
        reset_editor("spt", build_default_spt_records(st.session_state.layers), "spt_records")
except (ValueError, TypeError, KeyError) as exc:
    st.error(f"Cannot import P1 records: {exc}")
    st.session_state.setdefault("spt_records", [])
if st.button("Clear all SPT rows", key="p2_clear_spt"):
    reset_editor("spt", [], "spt_records")
st.markdown("**Depth-specific SPT records** — add, edit or delete rows.")
st.caption("Imported P1 values use estimated layer mid-depths. Enter actual test depths, then uncheck Estimated depth. Use Exclude for anomalous tests, e.g. a cobble strike; record the reason.")

spt_columns = {"depth_m": "float64", "soil_class": "object", "N_field": "float64",
               "is_refusal": "boolean", "excluded": "boolean", "estimated_depth": "boolean", "note": "object"}
spt_initial = [dict(is_refusal=False, excluded=False, estimated_depth=True, note="") | r
               for r in st.session_state.spt_records]
spt_df = editor("spt", spt_initial, spt_columns, {
    "depth_m": st.column_config.NumberColumn("Test depth (m bgl)", min_value=0.0, format="%.3f"),
    "soil_class": st.column_config.SelectboxColumn("Test soil class", options=SOIL_CLASSES),
    "N_field": st.column_config.NumberColumn("Raw N (blows/300 mm)", min_value=0, step=1, format="%d"),
    "is_refusal": st.column_config.CheckboxColumn("Refusal / incomplete", default=False),
    "excluded": st.column_config.CheckboxColumn("Exclude", default=False),
    "estimated_depth": st.column_config.CheckboxColumn("Estimated depth", default=False),
    "note": st.column_config.TextColumn("Note / refusal / exclusion reason"),
})
records = records_from_spt(spt_df)
st.session_state.spt_records = records
st.session_state.spt_results = []
spt_results = []
spt_valid = False
try:
    validate_profile(st.session_state.layers)
    spt_results = correct_spt_records(records, st.session_state.layers, wt_measured)
    st.session_state.spt_results = spt_results
    spt_valid = True
except (ValueError, TypeError, KeyError) as exc:
    st.error(f"SPT correction unavailable: {exc}")

if spt_valid and spt_results:
    display_rows = []
    for r in spt_results:
        def fmt(value):
            return "—" if value is None else f"{value:.3f}"
        display_rows.append({"Depth (m)": f"{r['depth_m']:.3f}", "Soil class": r["soil_class"],
            "Raw N (blows/300 mm)": r["N_field"], "σ′v (kPa)": fmt(r["sigma_v"]),
            "C_N": fmt(r["CN"]), "N′": fmt(r["N_prime"]), "Below WT?": r["below_wt"],
            "Dilatancy?": r["dilatancy_applied"], "Final N″": fmt(r["N_final"]), "Notes": r["notes"]})
    st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)
elif spt_valid:
    st.warning("No SPT observations entered. No N values have been invented.")

if spt_valid:
    approximate = any(r["estimated_depth"] and r["N_final"] is not None for r in spt_results)
    confirmed = not approximate or st.checkbox("I accept the estimated test depths for this preliminary calculation.", key="p2_accept_estimated")
    st.caption("Applying replaces all previous corrected layer N values, including clearing unmatched/refusal/excluded-only layers. Raw P1 observations are not changed. Reapply after changing test data or the profile.")
    if st.button("📋 Apply layer-averaged Final N″ to P1 (for P5)", key="btn_apply_spt_layers", disabled=not confirmed):
        messages = apply_spt_to_layers(st.session_state.layers, spt_results)
        st.success(" | ".join(messages))
        st.warning("P5 may still use raw N when no corrected N exists. Verify raw inputs and refusal status in P1 before settlement design.")

# B — Direct shear OLS
st.divider()
if st.session_state.get("demo_project"):
    st.info("The preloaded direct shear and UU specimens are from BH-1 only; do not treat them as laboratory measurements from BH-2 or BH-3. Change the selected specimen on Home by reloading the demo.")
st.header("B — Strength Parameter Fitting (Direct Shear — Ordinary Least Squares)")
st.caption("Enter effective normal stress and peak shear stress from an appropriate drained test. Use one specimen/material condition per fit. No lab readings are supplied automatically.")
st.latex(r"\tau_f=c'+\sigma'_n\tan\phi'")
if "ds_data" not in st.session_state:
    st.session_state.ds_data = []
if st.button("Clear direct shear observations", key="p2_clear_ds"):
    reset_editor("ds", [], "ds_data")
ds_df = editor("ds", st.session_state.ds_data, {"sigma_n": "float64", "tau": "float64"}, {
    "sigma_n": st.column_config.NumberColumn("Effective normal stress σ′n (kPa)", min_value=0.0, format="%.3f"),
    "tau": st.column_config.NumberColumn("Peak shear stress τf (kPa)", min_value=0.0, format="%.3f"),
})
ds = lab_rows(ds_df, ["sigma_n", "tau"])
st.session_state.ds_data = ds
# Results always derived from current editor data, not a previous button click.
st.session_state.pop("mc_fit", None)
if ds:
    try:
        x, y = [r["sigma_n"] for r in ds], [r["tau"] for r in ds]
        c, phi, r2 = fit_mohr_coulomb(x, y)
        fit = dict(c=c, phi=phi, r2=r2, sigma_n=x, tau=y)
        st.session_state.mc_fit = fit
    except (ValueError, TypeError) as exc:
        st.warning(f"Fit unavailable: {exc}")
else:
    st.info("Enter at least two matched data points.")

if "mc_fit" in st.session_state:
    fit = st.session_state.mc_fit
    col_res, col_plot = st.columns([1, 1.4])
    with col_res:
        st.write(f"**c′ = {fit['c']:.3f} kPa**  \n**φ′ = {fit['phi']:.3f}°**  \n**R² = {fit['r2']:.4f}**")
        admissible = fit["c"] >= -1e-9 and fit["phi"] >= -1e-9
        if not admissible:
            st.warning("The unconstrained OLS fit has negative cohesion or friction angle. Review the data or justify a separate constrained fit; this result will not be silently clipped or transferred.")
        if len(fit["sigma_n"]) == 2:
            st.caption("Two points determine a line; R² alone does not demonstrate reliability.")
        layers = st.session_state.layers
        if layers:
            idx = choose_layer(layers, "Copy fitted parameters to layer", "mc_copy_layer_v2")
            if st.button("📋 Apply to layer", key="btn_mc_apply", disabled=not admissible):
                # Only remove floating-point negative zero, not a physically negative fit.
                set_layer_value(layers[idx], "c_prime", max(0.0, fit["c"]))
                set_layer_value(layers[idx], "phi_prime", max(0.0, fit["phi"]))
                st.success("Applied fitted drained parameters to selected layer. Check the drained/undrained setting in P1.")
        else:
            st.info("Define soil layers in P1 to transfer fitted parameters.")
    with col_plot:
        xx = np.linspace(0, max(fit["sigma_n"]) * 1.15, 200)
        yy = fit["c"] + xx * math.tan(math.radians(fit["phi"]))  # Mohr-Coulomb envelope
        fig, ax = plt.subplots(figsize=(5, 3.5))
        ax.scatter(fit["sigma_n"], fit["tau"], label="Lab data")
        ax.plot(xx, yy, label="Unconstrained OLS fit")
        ax.set(xlabel="Effective normal stress (kPa)", ylabel="Shear stress (kPa)", title="Mohr-Coulomb failure envelope")
        ax.grid(True, linestyle=":", alpha=.6)
        ax.legend()
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

# C — UU triaxial
st.divider()
st.header("C — Undrained Shear Strength from UU Triaxial")
st.caption("For saturated cohesive soil under the φu = 0 assumption. Use tests from the same representative material, not unrelated samples.")
st.latex(r"c_u=(\sigma_1-\sigma_3)_f/2")
if "uu_data" not in st.session_state:
    st.session_state.uu_data = []
if st.button("Clear UU observations", key="p2_clear_uu"):
    reset_editor("uu", [], "uu_data")
uu_df = editor("uu", st.session_state.uu_data, {"sigma3": "float64", "deviator": "float64"}, {
    "sigma3": st.column_config.NumberColumn("Cell pressure σ3 (kPa)", min_value=0.0, format="%.3f"),
    "deviator": st.column_config.NumberColumn("Failure deviator stress Δσf (kPa)", min_value=0.0, format="%.3f"),
})
uu = lab_rows(uu_df, ["sigma3", "deviator"])
st.session_state.uu_data = uu
st.session_state.pop("cu_result", None)
if uu:
    try:
        cu, vals = fit_uu_cu([r["sigma3"] for r in uu], [r["deviator"] for r in uu])
        st.session_state.cu_result = dict(cu=cu, individual=vals)
    except (ValueError, TypeError) as exc:
        st.warning(f"UU calculation unavailable: {exc}")
else:
    st.info("Enter one or more matched UU test observations.")
if "cu_result" in st.session_state:
    res = st.session_state.cu_result
    st.write(f"**Mean cu = {res['cu']:.3f} kPa** from {len(res['individual'])} test(s).")
    st.dataframe(pd.DataFrame([dict(r, cu_kPa=v) for r, v in zip(uu, res["individual"])]).rename(columns={"sigma3":"σ3 (kPa)", "deviator":"Δσf (kPa)", "cu_kPa":"cu (kPa)"}), hide_index=True, use_container_width=True)
    st.caption("Check the spread of failure deviator stresses and whether φu = 0 is justified before adopting the mean.")
    clay_layers = [l for l in st.session_state.layers if l.get("is_clay")]
    if clay_layers:
        idx = choose_layer(clay_layers, "Copy cu to clay layer", "cu_copy_layer_v2")
        accepted = st.checkbox("I confirm the saturated-clay φu = 0 assumption is appropriate for this data.", key="p2_uu_assumption")
        if st.button("📋 Apply cu to layer", key="btn_cu_apply", disabled=not accepted):
            set_layer_value(clay_layers[idx], "cu", res["cu"])
            set_layer_value(clay_layers[idx], "is_undrained", True)
            st.success("Applied cu and enabled undrained analysis in selected clay layer.")
    else:
        st.info("No clay layers defined in P1; results can still be calculated.")
