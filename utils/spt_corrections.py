"""P2 — SPT corrections, strength fitting and UU analysis (SI units).

IS 2131:1981, clauses 3.3.3, 3.6.1 (Fig. 1), 3.6.2.
The logarithmic C_N expression is an approximation to Fig. 1, not a
literal equation printed in the 1981 standard. Outside the chart's stress
range an independently justified method is required.
"""
import math
from typing import Dict, List, Sequence, Tuple
from .bearing_capacity import effective_overburden_pressure, validate_profile, GAMMA_W

SOIL_CLASSES = ["Fine/Silty Sand", "Coarse/Medium Sand", "Clay",
                "Cobble/Boulder Gravel", "Fill", "Cohesionless Gravel (valid SPT)"]
OVERBURDEN_ELIGIBLE_CLASSES = {"Fine/Silty Sand", "Coarse/Medium Sand", "Cohesionless Gravel (valid SPT)"}
DILATANCY_ELIGIBLE_CLASSES = {"Fine/Silty Sand"}
_SYMBOL_TO_CLASS = {"SM": "Fine/Silty Sand", "ML": "Fine/Silty Sand",
    "SP": "Coarse/Medium Sand", "SW": "Coarse/Medium Sand", "SC": "Coarse/Medium Sand",
    "CL": "Clay", "CI": "Clay", "CH": "Clay", "MH": "Clay",
    "GW": "Cobble/Boulder Gravel", "GP": "Cobble/Boulder Gravel",
    "GM": "Cobble/Boulder Gravel", "GC": "Cobble/Boulder Gravel", "FILL": "Fill"}
# IS 2131:1981 Fig. 1 extends to 5 kgf/cm²; 1 kgf/cm² = 98.0665 kPa.
MAX_CHART_STRESS_KPA = 5.0 * 98.0665


def _number(value, name, minimum=0.0):
    try:
        x = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric.") from exc
    if not math.isfinite(x) or x < minimum:
        raise ValueError(f"{name} must be finite and at least {minimum:g}.")
    return x


def map_symbol_to_soil_class(symbol_or_class: str) -> str:
    """Provisional grouping; grain size and test validity need user confirmation."""
    text = str(symbol_or_class).strip()
    if text in SOIL_CLASSES:
        return text
    if text.upper() in _SYMBOL_TO_CLASS:
        return _SYMBOL_TO_CLASS[text.upper()]
    raise ValueError(f"Unknown SPT soil class/symbol: {text}. Select a supported class explicitly.")


def effective_stress(layers: List[Dict], depth_m: float, wt_bgl: float) -> float:
    """Share the strict stratified effective-stress implementation used by P3.

    Use measured/test-time groundwater, not the design water table. No
    default unit weights, gaps, overlaps or implicit extrapolation.
    """
    if not layers:
        raise ValueError("No soil profile. Enter layers in P1.")
    return effective_overburden_pressure(layers, depth_m, wt_bgl)[0]


def overburden_correction(sigma_v_kPa: float) -> float:
    """Approximation to IS 2131:1981 Fig. 1 (Peck et al. logarithmic fit).

    Existing 2000 kPa approximation retained, limited to chart stress range.
    The cap at 2 represents the low-stress end of the curve.
    """
    s = _number(sigma_v_kPa, "Effective overburden stress")
    if s > MAX_CHART_STRESS_KPA:
        raise ValueError(f"Effective stress {s:g} kPa exceeds the IS 2131:1981 Fig. 1 range (~{MAX_CHART_STRESS_KPA:.1f} kPa). Use a justified alternative.")
    if s == 0.0:
        return 2.0
    return min(2.0, 0.77 * (math.log10(2000.0) - math.log10(s)))


def dilatancy_correction(N_prime: float, soil_class_or_symbol: str,
                         depth_m: float, wt_measured_bgl: float) -> Tuple[float, bool]:
    """IS 2131:1981 cl. 3.6.2. Retain precision through both corrections."""
    n = _number(N_prime, "Overburden-corrected N")
    depth = _number(depth_m, "Test depth")
    wt = _number(wt_measured_bgl, "Measured water table")
    applies = (map_symbol_to_soil_class(soil_class_or_symbol) in DILATANCY_ELIGIBLE_CLASSES
               and depth > wt and n > 15.0)
    return (15.0 + 0.5 * (n - 15.0), True) if applies else (n, False)


def correct_spt_records(records: List[Dict], layers: List[Dict],
                        wt_measured_bgl: float) -> List[Dict]:
    """Correct arbitrary test records; preserve existing output dictionary keys.

    Optional input fields: is_refusal, excluded, note, estimated_depth.
    A missing N is allowed only for refusal/excluded records. For legacy
    compatibility, N >= 100 is conservatively treated as a
    refusal placeholder (not an IS refusal criterion). Explicit refusal or
    incomplete penetration is recorded separately per cl. 3.3.3.
    """
    wt = _number(wt_measured_bgl, "Measured water table")
    if not records:
        return []
    ordered = validate_profile(layers)
    results = []
    for i, rec in enumerate(records, 1):
        try:
            depth = _number(rec.get("depth_m"), "Test depth")
            soil = map_symbol_to_soil_class(rec.get("soil_class", rec.get("symbol", "")))
            raw = rec.get("N_field")
            if raw is not None:
                raw = _number(raw, "Observed N")
                if not raw.is_integer():
                    raise ValueError("Observed N must be an integer count.")
                raw = int(raw)
            refusal = bool(rec.get("is_refusal", rec.get("N_refusal", False))) or (raw is not None and raw >= 100)
            excluded = bool(rec.get("excluded", False))
            if raw is None and not (refusal or excluded):
                raise ValueError("Enter observed N or flag refusal/exclusion.")
            sigma = effective_stress(ordered, depth, wt)
            below = depth > wt
            result = dict(depth_m=depth, soil_class=soil, N_field=raw, sigma_v=sigma,
                          CN=None, N_prime=None, below_wt=below, dilatancy_applied=False,
                          N_final=None, is_refusal=refusal, excluded=excluded,
                          estimated_depth=bool(rec.get("estimated_depth", False)))
            if refusal:
                note = "Refusal / incomplete penetration / legacy N≥100 flag — no correlation"
            elif excluded:
                note = "Excluded by user — no correlation"
            elif soil not in OVERBURDEN_ELIGIBLE_CLASSES:
                result.update(N_prime=float(raw), N_final=float(raw))
                note = "Raw N retained; no correction for selected class"
            else:
                cn = overburden_correction(sigma)
                n_prime = cn * raw  # IS 2131:1981 cl. 3.6.1, Fig. 1
                n_final, applied = dilatancy_correction(n_prime, soil, depth, wt)
                result.update(CN=cn, N_prime=n_prime, N_final=n_final, dilatancy_applied=applied)
                note = "Overburden + dilatancy" if applied else "Overburden only (dilatancy conditions not met)"
            if result["estimated_depth"]:
                note += "; estimated layer midpoint — verify actual test depth"
            if rec.get("note"):
                note += "; " + str(rec["note"])
            result["notes"] = note
            results.append(result)
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"SPT record {i}: {exc}") from exc
    return sorted(results, key=lambda r: r["depth_m"])


def build_default_spt_records(layers: List[Dict]) -> List[Dict]:
    """Import representative P1 counts, explicitly labeling assumed mid-depths."""
    records = []
    for layer in sorted(layers, key=lambda l: float(l["depth_top"])):
        refusal = bool(layer.get("N_refusal"))
        if layer.get("N_field") is None and not refusal:
            continue
        depth = (float(layer["depth_top"]) + float(layer["depth_bot"])) / 2
        records.append(dict(depth_m=depth, soil_class=map_symbol_to_soil_class(layer["symbol"]),
                            N_field=layer.get("N_field"), is_refusal=refusal, excluded=False,
                            note=layer.get("N_refusal_note", "") if refusal else "",
                            estimated_depth=True))
    return records


def correct_spt(layers: List[Dict], wt_measured_bgl: float) -> List[Dict]:
    """Legacy layer-level interface; update only after all records validate."""
    if layers:
        validate_profile(layers)
    pending = []
    for i, layer in enumerate(layers):
        records = build_default_spt_records([layer])
        if records:
            r = correct_spt_records(records, layers, wt_measured_bgl)[0]
            pending.append((i, r))
    for layer in layers:
        layer["N_corrected"] = None
    results = []
    for i, r in pending:
        layers[i]["N_corrected"] = r["N_final"]
        results.append(dict(r, layer_idx=i, depth_mid=r["depth_m"],
                            N_corr1=r["N_prime"], N_corrected=r["N_final"]))
    return results


def apply_spt_to_layers(layers: List[Dict], results: List[Dict]) -> List[str]:
    """Replace (not accumulate) layer-average corrections. Raw P1 data unchanged.

    Half-open depth intervals, except the final profile bottom. Refusal and
    excluded records never contribute. P1 refusal flags take precedence.
    """
    ordered = validate_profile(layers)
    messages = []
    for i, layer in enumerate(ordered):
        top, bottom = float(layer["depth_top"]), float(layer["depth_bot"])
        matching = [r for r in results if top <= r["depth_m"] < bottom or
                    (i == len(ordered)-1 and r["depth_m"] == bottom)]
        valid = [r["N_final"] for r in matching if r.get("N_final") is not None
                 and not r.get("is_refusal") and not r.get("excluded")]
        layer["N_corrected"] = (math.fsum(valid) / len(valid) if valid and not layer.get("N_refusal") else None)
        layer["P2_spt_status"] = ("corrected" if layer["N_corrected"] is not None else
                                  "no_valid_record" if matching else "no_record")
        val = layer["N_corrected"]
        messages.append(f"{layer.get('name', f'Layer {i+1}')}: " + (f"N_corrected = {val:.2f}" if val is not None else "no corrected N (previous value cleared)"))
    return messages


def fit_mohr_coulomb(sigma_n_arr: Sequence[float], tau_arr: Sequence[float]) -> Tuple[float, float, float]:
    """OLS of Mohr-Coulomb τ = c′ + σ_n tan φ′; return unconstrained fit.

    Negative intercept/slope are shown, not silently clipped. The UI blocks
    transferring such parameters until the engineer resolves the fit.
    """
    x = [_number(v, "Normal stress") for v in sigma_n_arr]
    y = [_number(v, "Peak shear stress") for v in tau_arr]
    if len(x) < 2 or len(x) != len(y):
        raise ValueError("At least two matched (normal, shear) observations required.")
    mx, my = math.fsum(x)/len(x), math.fsum(y)/len(y)
    sxx = math.fsum((v-mx)**2 for v in x)
    if sxx <= 0:
        raise ValueError("Normal stress values must not all be identical.")
    slope = math.fsum((a-mx)*(b-my) for a,b in zip(x,y))/sxx
    c = my - slope*mx
    phi = math.degrees(math.atan(slope))
    ss_res = math.fsum((b-c-slope*a)**2 for a,b in zip(x,y))
    ss_tot = math.fsum((b-my)**2 for b in y)
    r2 = 1-ss_res/ss_tot if ss_tot > 0 else 1.0
    return c, phi, r2


def fit_uu_cu(sigma3: Sequence[float], deviator: Sequence[float]) -> Tuple[float, List[float]]:
    """IS 2720 Part 11 / Mohr circle, saturated clay, φ_u=0 assumption."""
    pressures = [_number(x, "Cell pressure") for x in sigma3]
    devs = [_number(x, "Failure deviator stress") for x in deviator]
    if not devs or len(pressures) != len(devs):
        raise ValueError("At least one matched UU observation is required.")
    values = [d/2.0 for d in devs]
    return math.fsum(values)/len(values), values
