"""
utils/spt_corrections.py
IS 2131:1981 SPT correction functions and Mohr-Coulomb fitting.

References
----------
IS 2131:1981 — Method for Standard Penetration Test for Soils
  Annex B : Overburden pressure correction (Peck et al. 1974)
  Clause 4.6 : Dilatancy correction (Terzaghi & Peck 1967)
"""

import math
import numpy as np


def effective_stress(layers, depth_m, wt_bgl):
    """
    Compute effective vertical stress at a given depth (m bgl).

    IS 2131:1981 — uses γ_moist above water table, (γ_sat - γw) below.
    γw = 9.81 kN/m³

    Parameters
    ----------
    layers    : list[dict]  — session-state layer list, sorted by depth_top
    depth_m   : float       — target depth in metres below ground level
    wt_bgl    : float       — design water-table depth in metres bgl

    Returns
    -------
    float — σ′v in kPa
    """
    gamma_w = 9.81  # kN/m³
    sigma_v = 0.0
    remaining = depth_m

    for layer in layers:
        d_top = layer["depth_top"]
        d_bot = layer["depth_bot"]
        thickness = d_bot - d_top

        if remaining <= 0:
            break

        # Portion of this layer we still need to integrate
        contrib = min(thickness, remaining)

        # Mid-depth of the contributing slice
        slice_top = depth_m - remaining
        slice_mid = slice_top + contrib / 2.0

        if slice_mid <= wt_bgl:
            # Entire slice above WT → moist unit weight
            sigma_v += layer["gamma_moist"] * contrib
        elif slice_top >= wt_bgl:
            # Entire slice below WT → submerged unit weight
            sigma_v += (layer["gamma_sat"] - gamma_w) * contrib
        else:
            # Slice straddles WT
            above = wt_bgl - slice_top
            below = contrib - above
            sigma_v += layer["gamma_moist"] * above
            sigma_v += (layer["gamma_sat"] - gamma_w) * below

        remaining -= contrib

    return max(sigma_v, 0.0)


def overburden_correction(sigma_v_kPa):
    """
    IS 2131:1981 Annex B — Peck, Hanson & Thornburn (1974) overburden
    correction factor C_N.

    C_N = 0.77 × log10(2000 / σ′v)   for σ′v ≥ 25 kPa
    C_N = 2.0                          for σ′v < 25 kPa  (low-stress cap)

    Clamped:  0.5 ≤ C_N ≤ 2.0

    Parameters
    ----------
    sigma_v_kPa : float — effective vertical stress in kPa

    Returns
    -------
    float — C_N (dimensionless)
    """
    if sigma_v_kPa < 25.0:
        return 2.0
    cn = 0.77 * math.log10(2000.0 / sigma_v_kPa)
    return max(0.5, min(cn, 2.0))


def dilatancy_correction(N_corr1, symbol, depth_m, wt_bgl):
    """
    IS 2131:1981 Clause 4.6 — Terzaghi & Peck (1967) dilatancy correction
    for fine saturated sands and silts.

    Applied ONLY when ALL of:
      • symbol in {'SM', 'ML', 'SP'}   (fine sand / silt susceptible to dilation)
      • depth_m > wt_bgl               (layer mid-depth is below design WT)
      • N_corr1 > 15                   (IS 2131 threshold)

    If applied:
      N_corrected = 15 + 0.5 × (N_corr1 − 15)

    Parameters
    ----------
    N_corr1  : int   — overburden-corrected N value
    symbol   : str   — IS 1498 soil symbol
    depth_m  : float — mid-depth of layer (m bgl)
    wt_bgl   : float — design water-table depth (m bgl)

    Returns
    -------
    (N_corrected: int, applied: bool)
    """
    eligible_symbols = {"SM", "ML", "SP"}
    apply = (
        symbol in eligible_symbols
        and depth_m > wt_bgl
        and N_corr1 > 15
    )
    if apply:
        n_corr = int(round(15 + 0.5 * (N_corr1 - 15)))
        return n_corr, True
    return N_corr1, False


def correct_spt(layers, wt_design_bgl):
    """
    Apply full IS 2131:1981 correction chain to all layers that have
    a measured N_field value.

    Steps per layer:
      1. Compute σ′v at mid-depth            (Annex B)
      2. Compute overburden correction C_N   (Annex B, Peck et al. 1974)
      3. N_corr1 = round(C_N × N_field)
      4. Apply dilatancy correction           (Clause 4.6)
      5. Store N_corrected back into the layer dict

    Parameters
    ----------
    layers          : list[dict]  — session-state layers (mutated in place)
    wt_design_bgl   : float       — design WT depth (m bgl)

    Returns
    -------
    list[dict] — one record per corrected layer with keys:
        layer_idx, depth_mid, sigma_v, CN, N_field,
        N_corr1, dilatancy_applied, N_corrected
    """
    results = []
    for i, layer in enumerate(layers):
        if layer.get("N_field") is None:
            continue

        depth_mid = (layer["depth_top"] + layer["depth_bot"]) / 2.0
        sigma_v = effective_stress(layers, depth_mid, wt_design_bgl)
        cn = overburden_correction(sigma_v)
        n_corr1 = int(round(cn * layer["N_field"]))

        n_corrected, dil_applied = dilatancy_correction(
            n_corr1, layer["symbol"], depth_mid, wt_design_bgl
        )

        # Mutate session state in place
        layer["N_corrected"] = n_corrected

        results.append({
            "layer_idx": i,
            "depth_mid": depth_mid,
            "sigma_v": sigma_v,
            "CN": cn,
            "N_field": layer["N_field"],
            "N_corr1": n_corr1,
            "dilatancy_applied": dil_applied,
            "N_corrected": n_corrected,
        })

    return results


def fit_mohr_coulomb(sigma_n_arr, tau_arr):
    """
    Least-squares fit of the Mohr-Coulomb failure envelope:
        τ = c′ + σn · tan(φ′)

    Solved as a linear system  A x = b  where
        A[:, 0] = 1           (intercept → c′)
        A[:, 1] = σn values   (slope     → tan φ′)
        b       = τ values

    Reference: standard linear regression; cited per IS 2131:1981
    recommendation to use laboratory shear-box data for φ′ determination.

    Parameters
    ----------
    sigma_n_arr : array-like — normal stresses (kPa), length ≥ 2
    tau_arr     : array-like — shear stresses at failure (kPa), same length

    Returns
    -------
    (c_prime_kPa: float, phi_prime_deg: float, r_squared: float)
    """
    sigma_n = np.asarray(sigma_n_arr, dtype=float)
    tau = np.asarray(tau_arr, dtype=float)

    if len(sigma_n) < 2:
        raise ValueError("At least 2 data points are required for fitting.")

    # Build design matrix [1, σn]
    A = np.column_stack([np.ones_like(sigma_n), sigma_n])
    # Least-squares solution
    result, _, _, _ = np.linalg.lstsq(A, tau, rcond=None)
    c_prime = float(result[0])
    tan_phi = float(result[1])
    phi_prime_deg = float(math.degrees(math.atan(tan_phi)))

    # R² (coefficient of determination)
    tau_pred = c_prime + sigma_n * tan_phi
    ss_res = float(np.sum((tau - tau_pred) ** 2))
    ss_tot = float(np.sum((tau - np.mean(tau)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0

    return c_prime, phi_prime_deg, r_squared
