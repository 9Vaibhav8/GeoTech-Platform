"""
utils/spt_corrections.py
IS 2131:1981 SPT correction functions, Mohr-Coulomb OLS fitting, and UU cu helpers.
All computations strictly in SI units (m, kPa, kN/m³, deg).

References
----------
IS 2131:1981 — Method for Standard Penetration Test for Soils:
  Cl. 3.6.1 & Fig. 1 : Overburden pressure correction (Peck, Hanson & Thornburn 1974)
  Cl. 3.6.2          : Dilatancy / submergence correction (Terzaghi & Peck 1967)
"""

import math
from typing import Dict, List, Optional, Sequence, Tuple

GAMMA_W = 9.81  # kN/m³, unit weight of water

SOIL_CLASSES = [
    "Fine/Silty Sand",
    "Coarse/Medium Sand",
    "Clay",
    "Cobble/Boulder Gravel",
    "Fill",
]

OVERBURDEN_ELIGIBLE_CLASSES = {"Fine/Silty Sand", "Coarse/Medium Sand"}
DILATANCY_ELIGIBLE_CLASSES = {"Fine/Silty Sand"}

_SYMBOL_TO_CLASS = {
    "SM": "Fine/Silty Sand",
    "ML": "Fine/Silty Sand",
    "SP": "Coarse/Medium Sand",
    "SW": "Coarse/Medium Sand",
    "SC": "Coarse/Medium Sand",
    "CL": "Clay",
    "CI": "Clay",
    "CH": "Clay",
    "MH": "Clay",
    "GW": "Cobble/Boulder Gravel",
    "GP": "Cobble/Boulder Gravel",
    "GM": "Cobble/Boulder Gravel",
    "GC": "Cobble/Boulder Gravel",
    "Fill": "Fill",
}


def map_symbol_to_soil_class(symbol_or_class: str) -> str:
    """Map an IS 1498 soil symbol (or existing soil class) to a canonical SPT soil class."""
    if symbol_or_class in SOIL_CLASSES:
        return symbol_or_class
    return _SYMBOL_TO_CLASS.get(str(symbol_or_class).strip(), "Fill")


def effective_stress(layers: List[Dict], depth_m: float, wt_bgl: float) -> float:
    """
    Compute effective vertical stress σ'v at a given depth (m bgl) using exact
    interval splitting against the measured water table depth `wt_bgl`.

    Uses γ_moist above `wt_bgl` and (γ_sat - γ_w) below `wt_bgl`.

    Parameters
    ----------
    layers  : list[dict] — soil profile layers with depth_top, depth_bot, gamma_moist, gamma_sat
    depth_m : float      — target test depth in metres below ground level (m bgl)
    wt_bgl  : float      — measured water-table depth in metres below ground level (m bgl)

    Returns
    -------
    float — σ'v (kPa)
    """
    if depth_m <= 0.0 or not layers:
        return 0.0

    sorted_layers = sorted(layers, key=lambda lyr: float(lyr["depth_top"]))
    sigma_v = 0.0

    for layer in sorted_layers:
        d_top = float(layer["depth_top"])
        d_bot = float(layer["depth_bot"])
        if d_top >= depth_m:
            break

        slice_top = max(0.0, d_top)
        slice_bot = min(depth_m, d_bot)
        if slice_bot <= slice_top:
            continue

        gamma_moist = float(layer.get("gamma_moist", 18.0))
        gamma_sat = float(layer.get("gamma_sat", 20.0))
        gamma_sub = gamma_sat - GAMMA_W

        if slice_bot <= wt_bgl:
            # Source: IS 2131:1981 Cl. 3.6.1 (moist unit weight above measured WT)
            sigma_v += gamma_moist * (slice_bot - slice_top)
        elif slice_top >= wt_bgl:
            # Source: IS 2131:1981 Cl. 3.6.1 (submerged unit weight below measured WT)
            sigma_v += gamma_sub * (slice_bot - slice_top)
        else:
            # Exact split at wt_bgl when interval straddles the water table
            dz_above = wt_bgl - slice_top
            dz_below = slice_bot - wt_bgl
            # Source: IS 2131:1981 Cl. 3.6.1 (split interval across measured WT)
            sigma_v += gamma_moist * dz_above + gamma_sub * dz_below

    # If depth_m extends below the bottom of the last defined layer, extrapolate with last layer
    max_bot = max(float(lyr["depth_bot"]) for lyr in sorted_layers)
    if depth_m > max_bot:
        last = sorted_layers[-1]
        gamma_moist = float(last.get("gamma_moist", 18.0))
        gamma_sub = float(last.get("gamma_sat", 20.0)) - GAMMA_W
        slice_top = max_bot
        slice_bot = depth_m
        if slice_bot <= wt_bgl:
            # Source: IS 2131:1981 Cl. 3.6.1
            sigma_v += gamma_moist * (slice_bot - slice_top)
        elif slice_top >= wt_bgl:
            # Source: IS 2131:1981 Cl. 3.6.1
            sigma_v += gamma_sub * (slice_bot - slice_top)
        else:
            # Source: IS 2131:1981 Cl. 3.6.1
            sigma_v += gamma_moist * (wt_bgl - slice_top) + gamma_sub * (slice_bot - wt_bgl)

    return max(sigma_v, 0.0)


def overburden_correction(sigma_v_kPa: float) -> float:
    """
    IS 2131:1981 Cl. 3.6.1 & Fig. 1 (Peck, Hanson & Thornburn 1974)
    Overburden correction factor C_N for cohesionless sands:

        C_N = min(2.0, 0.77 * log10(2000 / σ'v))

    Parameters
    ----------
    sigma_v_kPa : float — effective vertical overburden stress σ'v (kPa)

    Returns
    -------
    float — C_N (dimensionless, capped at 2.0)
    """
    if sigma_v_kPa <= 0.0:
        # Source: IS 2131:1981 Cl. 3.6.1 & Fig. 1 (upper cap at zero overburden)
        return 2.0
    # Source: IS 2131:1981 Cl. 3.6.1 & Fig. 1 (Peck, Hanson & Thornburn 1974)
    cn = 0.77 * math.log10(2000.0 / sigma_v_kPa)
    # Source: IS 2131:1981 Cl. 3.6.1 & Fig. 1 (maximum C_N cap = 2.0)
    return min(2.0, cn)


def dilatancy_correction(
    N_prime: float,
    soil_class_or_symbol: str,
    depth_m: float,
    wt_measured_bgl: float,
) -> Tuple[int, bool]:
    """
    IS 2131:1981 Cl. 3.6.2 (Terzaghi & Peck 1967) — Dilatancy correction
    for fine/silty sands and silts below the measured water table when N' > 15:

        N'' = 15 + 0.5 * (N' - 15)

    Does NOT apply to coarse/medium sands (e.g. gravelly SP), clays, or gravels.

    Parameters
    ----------
    N_prime              : float or int — overburden-corrected N'
    soil_class_or_symbol : str          — canonical soil class or IS 1498 symbol
    depth_m              : float        — test depth (m bgl)
    wt_measured_bgl      : float        — measured water-table depth during SPT (m bgl)

    Returns
    -------
    (N_double_prime: int, applied: bool)
    """
    soil_class = map_symbol_to_soil_class(soil_class_or_symbol)
    apply = (
        soil_class in DILATANCY_ELIGIBLE_CLASSES
        and depth_m > wt_measured_bgl
        and N_prime > 15
    )
    if apply:
        # Source: IS 2131:1981 Cl. 3.6.2 (Terzaghi & Peck 1967 dilatancy correction)
        n_double_prime = int(round(15.0 + 0.5 * (N_prime - 15.0)))
        return n_double_prime, True
    return int(round(N_prime)), False


def correct_spt_records(
    records: List[Dict],
    layers: List[Dict],
    wt_measured_bgl: float,
) -> List[Dict]:
    """
    Apply full IS 2131:1981 SPT correction sequence to arbitrary depth-specific records.

    Rules enforced:
    1. σ'v computed against measured (test-time) water table `wt_measured_bgl`.
    2. Raw N_field >= 100 flagged as Refusal and excluded from correlations.
    3. Overburden correction C_N (Cl. 3.6.1) applied ONLY to 'Fine/Silty Sand'
       and 'Coarse/Medium Sand'.
    4. Dilatancy correction (Cl. 3.6.2) applied AFTER C_N, and ONLY to
       'Fine/Silty Sand' below `wt_measured_bgl` when N' > 15.

    Parameters
    ----------
    records         : list[dict] — each dict has depth_m, soil_class (or symbol), N_field
    layers          : list[dict] — layered profile from P1
    wt_measured_bgl : float      — measured WT depth during boring (m bgl)

    Returns
    -------
    list[dict] — detailed intermediate and final results for every test record
    """
    results = []
    sorted_records = sorted(records, key=lambda r: float(r["depth_m"]))

    for rec in sorted_records:
        depth_m = float(rec["depth_m"])
        raw_n = float(rec["N_field"])
        soil_class = map_symbol_to_soil_class(rec.get("soil_class", rec.get("symbol", "Fill")))

        sigma_v = effective_stress(layers, depth_m, wt_measured_bgl)
        below_wt = depth_m > wt_measured_bgl
        is_refusal = raw_n >= 100.0

        if is_refusal:
            results.append({
                "depth_m": depth_m,
                "soil_class": soil_class,
                "N_field": int(round(raw_n)),
                "sigma_v": sigma_v,
                "CN": None,
                "N_prime": None,
                "below_wt": below_wt,
                "dilatancy_applied": False,
                "N_final": None,
                "is_refusal": True,
                "notes": "Refusal (N ≥ 100) — excluded from correlations",
            })
            continue

        if soil_class not in OVERBURDEN_ELIGIBLE_CLASSES:
            results.append({
                "depth_m": depth_m,
                "soil_class": soil_class,
                "N_field": int(round(raw_n)),
                "sigma_v": sigma_v,
                "CN": None,
                "N_prime": int(round(raw_n)),
                "below_wt": below_wt,
                "dilatancy_applied": False,
                "N_final": int(round(raw_n)),
                "is_refusal": False,
                "notes": f"{soil_class} — C_N and dilatancy N/A per IS 2131",
            })
            continue

        # Step 1: Overburden correction (IS 2131:1981 Cl. 3.6.1 & Fig. 1)
        cn = overburden_correction(sigma_v)
        # Source: IS 2131:1981 Cl. 3.6.1 (overburden-corrected SPT N')
        n_prime = int(round(cn * raw_n))

        # Step 2: Dilatancy correction (IS 2131:1981 Cl. 3.6.2)
        n_final, dil_applied = dilatancy_correction(
            n_prime, soil_class, depth_m, wt_measured_bgl
        )

        if dil_applied:
            note = "C_N (Cl. 3.6.1) + Dilatancy (Cl. 3.6.2)"
        elif soil_class == "Coarse/Medium Sand" and below_wt and n_prime > 15:
            note = "C_N (Cl. 3.6.1); Dilatancy N/A for Coarse/Medium Sand"
        elif soil_class == "Fine/Silty Sand" and below_wt and n_prime <= 15:
            note = "C_N (Cl. 3.6.1); N' ≤ 15 (no dilatancy)"
        else:
            note = "C_N (Cl. 3.6.1); above measured WT"

        results.append({
            "depth_m": depth_m,
            "soil_class": soil_class,
            "N_field": int(round(raw_n)),
            "sigma_v": sigma_v,
            "CN": cn,
            "N_prime": n_prime,
            "below_wt": below_wt,
            "dilatancy_applied": dil_applied,
            "N_final": n_final,
            "is_refusal": False,
            "notes": note,
        })

    return results


def correct_spt(layers: List[Dict], wt_measured_bgl: float) -> List[Dict]:
    """
    Apply IS 2131:1981 corrections to layer-level N_field values at layer mid-depths.
    Mutates `layer['N_corrected']` in place (set to None for refusal records).

    Parameters
    ----------
    layers          : list[dict] — session-state layers (mutated in place)
    wt_measured_bgl : float      — measured WT depth during SPT (m bgl)

    Returns
    -------
    list[dict] — per-layer correction records
    """
    results = []
    for i, layer in enumerate(layers):
        if layer.get("N_field") is None:
            continue

        depth_mid = (float(layer["depth_top"]) + float(layer["depth_bot"])) / 2.0
        soil_class = map_symbol_to_soil_class(layer.get("symbol", "Fill"))
        rec = correct_spt_records(
            [{"depth_m": depth_mid, "soil_class": soil_class, "N_field": layer["N_field"]}],
            layers,
            wt_measured_bgl,
        )[0]

        layer["N_corrected"] = rec["N_final"]
        results.append({
            "layer_idx": i,
            "depth_mid": rec["depth_m"],
            "soil_class": rec["soil_class"],
            "sigma_v": rec["sigma_v"],
            "CN": rec["CN"],
            "N_field": rec["N_field"],
            "N_corr1": rec["N_prime"],
            "N_prime": rec["N_prime"],
            "below_wt": rec["below_wt"],
            "dilatancy_applied": rec["dilatancy_applied"],
            "N_corrected": rec["N_final"],
            "N_final": rec["N_final"],
            "is_refusal": rec["is_refusal"],
            "notes": rec["notes"],
        })

    return results


def build_default_spt_records(layers: List[Dict]) -> List[Dict]:
    """Generate initial depth-specific SPT records from P1 soil layers that have N_field."""
    records = []
    for layer in sorted(layers, key=lambda lyr: float(lyr["depth_top"])):
        if layer.get("N_field") is not None:
            depth_mid = round((float(layer["depth_top"]) + float(layer["depth_bot"])) / 2.0, 2)
            records.append({
                "depth_m": depth_mid,
                "soil_class": map_symbol_to_soil_class(layer.get("symbol", "Fill")),
                "N_field": int(round(float(layer["N_field"]))),
            })
    return records


def fit_mohr_coulomb(
    sigma_n_arr: Sequence[float],
    tau_arr: Sequence[float],
) -> Tuple[float, float, float]:
    """
    Ordinary Least Squares (OLS) fit of the Mohr-Coulomb failure envelope:
        τ = c′ + σ_n · tan(φ′)

    Parameters
    ----------
    sigma_n_arr : array-like — normal stresses σ_n (kPa), length ≥ 2
    tau_arr     : array-like — shear stresses at failure τ_f (kPa), same length

    Returns
    -------
    (c_prime_kPa: float, phi_prime_deg: float, r_squared: float)
    """
    sigma_n = [float(x) for x in sigma_n_arr]
    tau = [float(y) for y in tau_arr]

    if len(sigma_n) < 2 or len(sigma_n) != len(tau):
        raise ValueError("At least 2 matched (σ_n, τ_f) data points are required for fitting.")

    n = len(sigma_n)
    mean_x = sum(sigma_n) / n
    mean_y = sum(tau) / n

    sxx = sum((x - mean_x) ** 2 for x in sigma_n)
    if sxx <= 0.0:
        raise ValueError("Normal stress values σ_n must not all be identical.")

    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(sigma_n, tau))

    # Source: IS 2720 Part 13 / Ordinary Least Squares regression for τ = c' + σ_n tan(φ')
    tan_phi = sxy / sxx
    # Source: IS 2720 Part 13 / Ordinary Least Squares intercept c'
    c_prime = mean_y - tan_phi * mean_x
    # Source: Mohr-Coulomb failure criterion φ' = arctan(slope)
    phi_prime_deg = math.degrees(math.atan(tan_phi))

    tau_pred = [c_prime + tan_phi * x for x in sigma_n]
    ss_res = sum((y - yp) ** 2 for y, yp in zip(tau, tau_pred))
    ss_tot = sum((y - mean_y) ** 2 for y in tau)
    # Source: Coefficient of determination R²
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 1.0

    return c_prime, phi_prime_deg, r_squared
