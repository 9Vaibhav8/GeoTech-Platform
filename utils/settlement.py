"""
utils/settlement.py
Immediate (Schmertmann 1978) and 1D consolidation (Terzaghi 1943) settlement.
Cite: Schmertmann et al. (1978); Terzaghi (1943); IS 8009:1976 Part 1;
      Das (2016) Principles of Foundation Engineering.
"""

import numpy as np
from utils.stress_increase import stress_increase_centre

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GAMMA_W = 9.81  # kN/m³
GRANULAR_SYMBOLS = {"SM", "SP", "SW", "SC", "GW", "GP", "GM", "GC", "Fill"}


# ---------------------------------------------------------------------------
# Helper — effective stress at a given depth bgl
# ---------------------------------------------------------------------------
def _effective_stress_at(layers, z_bgl, wt_design_bgl):
    """
    Compute vertical effective stress (kPa) at depth z_bgl (m bgl).
    Uses moist unit weight above WT and buoyant weight below WT.
    """
    sigma_v = 0.0
    u = 0.0
    for lyr in layers:
        if lyr["depth_top"] >= z_bgl:
            break
        z_top = lyr["depth_top"]
        z_bot = min(lyr["depth_bot"], z_bgl)
        dz = z_bot - z_top
        if z_bot <= wt_design_bgl:
            # fully above WT — moist
            sigma_v += lyr.get("gamma_moist", 18.0) * dz
        elif z_top >= wt_design_bgl:
            # fully below WT — saturated
            sigma_v += lyr.get("gamma_sat", 20.0) * dz
            u += GAMMA_W * dz
        else:
            # straddles WT
            dz_above = wt_design_bgl - z_top
            dz_below = z_bot - wt_design_bgl
            sigma_v += lyr.get("gamma_moist", 18.0) * dz_above
            sigma_v += lyr.get("gamma_sat", 20.0) * dz_below
            u += GAMMA_W * dz_below
    return sigma_v - u


def _layer_at_depth(layers, z_bgl):
    """Return the layer dict containing z_bgl, or None."""
    for lyr in layers:
        if lyr["depth_top"] <= z_bgl < lyr["depth_bot"]:
            return lyr
    return layers[-1] if layers else None


def _net_foundation_pressure(layers, Df, B, L, P_kN, wt_design_bgl):
    """
    Net foundation pressure Δp = P / (B×L) - σ′v0(Df) (kPa).
    The existing effective overburden uses moist unit weight above the design
    water table and submerged unit weight below it.
    """
    q_gross = P_kN / (B * L)
    q_surcharge = _effective_stress_at(layers, Df, wt_design_bgl)
    delta_p = q_gross - q_surcharge
    return max(delta_p, 1.0)  # must be positive


# ---------------------------------------------------------------------------
# Schmertmann (1978) — Immediate Settlement
# ---------------------------------------------------------------------------

def schmertmann_Es_from_N(N_corrected, soil_type="sand"):
    """
    Estimate elastic modulus Es (kPa) from corrected SPT N (Schmertmann 1978).
    Sand  : Es = 500  × (N + 15)
    Gravel: Es = 1000 × (N + 15)
    Cite: Schmertmann et al. (1978); Meyerhof (1956)
    """
    N = max(1, int(N_corrected)) if N_corrected else 5
    if soil_type.lower() in ("gravel", "gw", "gp", "gm", "gc"):
        return 1000.0 * (N + 15)
    return 500.0 * (N + 15)  # default: sand


def strain_influence_factor(z, B, L=None, footing_type="square", Iz_peak=0.6):
    """
    Schmertmann et al. (1978) strain influence factor Iz at depth z below footing.

    For square / circular footings (default):
      z1 = 0.5·B  (depth to peak Iz)
      z2 = 2.0·B  (depth where Iz → 0)
      Iz = 0.1 + (Iz_peak - 0.1)·(z/z1)      for z ≤ z1
      Iz = Iz_peak·(z2 - z)/(z2 - z1)         for z1 < z ≤ z2
      Iz = 0                                    for z > z2

    For strip footings (L/B → ∞):
      z1 = B, z2 = 4·B

    Parameters
    ----------
    z : float
        Depth below footing base (m).
    B : float
        Footing width (m).
    L : float or None
        Footing length (m); used only to decide strip vs. square.
    footing_type : str
        "square" or "strip".
    Iz_peak : float
        Peak influence factor (default 0.6; corrected externally via pressure ratio).

    Returns
    -------
    float — Iz (dimensionless, 0 to Iz_peak).
    Cite: Schmertmann et al. (1978) Fig. 4
    """
    if L is not None and L / B >= 10:
        footing_type = "strip"
    if footing_type == "strip":
        z1, z2 = B, 4.0 * B
    else:
        z1, z2 = 0.5 * B, 2.0 * B

    if z <= 0:
        return 0.1
    if z <= z1:
        return 0.1 + (Iz_peak - 0.1) * (z / z1)
    if z <= z2:
        return Iz_peak * (z2 - z) / (z2 - z1)
    return 0.0


def schmertmann_settlement(layers, Df, B, L, P_kN, wt_design_bgl, t_years=50):
    """
    Schmertmann et al. (1978) strain influence factor method for immediate
    settlement of footings on granular (sand/gravel) layers.

    Steps
    -----
    1. Net foundation pressure: Δp
    2. C1 = 1 - 0.5·(σ′v0/Δp) ≥ 0.5          [embedment correction]
    3. C2 = 1 + 0.2·log10(t_years/0.1)         [creep correction]
    4. Divide soil below footing into sublayers of ≤ 0.5 m (granular only)
    5. For each sublayer at mid-depth z_mid:
       a. σ′v at z=0.5B below footing → compute Iz_peak
          Iz_peak = 0.5 + 0.1·√(Δp / σ′v_halfB)
       b. Iz at sublayer mid using strain_influence_factor with scaled Iz_peak
       c. Es from N_corrected of that layer
       d. Contribution: (Iz / Es) · Δz
    6. S_i = C1 × C2 × Δp × Σ(Iz/Es·Δz)  in metres

    Returns
    -------
    dict with keys: S_mm, C1, C2, delta_p, sublayer_data (list of dicts)
    Cite: Schmertmann et al. (1978); IS 8009 Part 1
    """
    delta_p = _net_foundation_pressure(layers, Df, B, L, P_kN, wt_design_bgl)
    sigma_v0 = _effective_stress_at(layers, Df, wt_design_bgl)   # at footing base

    C1 = max(0.5, 1.0 - 0.5 * (sigma_v0 / delta_p))
    C2 = 1.0 + 0.2 * np.log10(max(t_years, 0.1) / 0.1)

    # Iz_peak depends on effective stress at z = 0.5B below footing base
    sigma_v_halfB = _effective_stress_at(layers, Df + 0.5 * B, wt_design_bgl)
    if sigma_v_halfB > 0 and delta_p > 0:
        Iz_peak = 0.5 + 0.1 * np.sqrt(delta_p / sigma_v_halfB)
    else:
        Iz_peak = 0.6

    # Determine influence zone depth (2B for square)
    is_strip = (L / B >= 10)
    z_max_influence = (4.0 * B) if is_strip else (2.0 * B)

    sublayer_data = []
    sum_Iz_Es_dz = 0.0
    sub_thick = 0.5  # m

    # Iterate over layers that fall within [Df, Df + z_max_influence]
    z_start = Df
    z_end = Df + z_max_influence

    for lyr in layers:
        lyr_top = lyr["depth_top"]
        lyr_bot = lyr["depth_bot"]

        # Intersect with [z_start, z_end]
        seg_top = max(lyr_top, z_start)
        seg_bot = min(lyr_bot, z_end)
        if seg_top >= seg_bot:
            continue

        # Skip clay layers (consolidation handles them)
        if lyr.get("is_clay", False):
            continue
        symbol = lyr.get("symbol", "SM")

        N_corr = lyr.get("N_corrected") or lyr.get("N_field") or 10
        soil_type = "gravel" if symbol in ("GW", "GP", "GM", "GC") else "sand"
        Es = schmertmann_Es_from_N(N_corr, soil_type=soil_type)

        # Divide this segment into sub-layers
        z = seg_top
        while z < seg_bot:
            dz = min(sub_thick, seg_bot - z)
            z_mid_bgl = z + dz / 2.0
            z_mid = z_mid_bgl - Df  # depth below footing

            Iz = strain_influence_factor(z_mid, B, L, Iz_peak=Iz_peak,
                                         footing_type="strip" if is_strip else "square")
            if Iz <= 0:
                z += dz
                continue

            contrib = (Iz / Es) * dz
            sum_Iz_Es_dz += contrib
            sublayer_data.append({
                "z_top_m": round(z - Df, 3),
                "z_bot_m": round(z + dz - Df, 3),
                "z_mid_m": round(z_mid, 3),
                "layer_name": lyr.get("name", symbol),
                "symbol": symbol,
                "Es_kPa": round(Es, 1),
                "Iz": round(Iz, 4),
                "Iz_over_Es": round(Iz / Es, 8),
                "dz_m": round(dz, 3),
                "contrib_m": round(contrib, 8),
            })
            z += dz

    S_i_m = C1 * C2 * delta_p * sum_Iz_Es_dz
    return {
        "S_mm": round(S_i_m * 1000, 2),
        "C1": round(C1, 4),
        "C2": round(C2, 4),
        "delta_p": round(delta_p, 2),
        "Iz_peak": round(Iz_peak, 4),
        "sigma_v0": round(sigma_v0, 2),
        "sublayer_data": sublayer_data,
    }


# ---------------------------------------------------------------------------
# 1D Consolidation Settlement — Terzaghi (1943)
# ---------------------------------------------------------------------------

def consolidation_settlement_layer(H_m, e0, Cc, Cr, sigma_v0_kPa, Pc_kPa, delta_sigma_kPa):
    """
    1D consolidation settlement for a single clay sublayer (Terzaghi 1943).

    Case 1 — Normally consolidated (σ′v0 ≥ Pc):
        Sc = Cc/(1+e0) × H × log10((σ′v0 + Δσ) / σ′v0)

    Case 2 — Overconsolidated, stays OC (σ′v0 + Δσ ≤ Pc):
        Sc = Cr/(1+e0) × H × log10((σ′v0 + Δσ) / σ′v0)

    Case 3 — Overconsolidated, crosses preconsolidation pressure:
        Sc = Cr/(1+e0) × H × log10(Pc / σ′v0)
           + Cc/(1+e0) × H × log10((σ′v0 + Δσ) / Pc)

    Returns (Sc_m, case_label)
    Cite: Terzaghi (1943); Das (2016) Eq. 7.21-7.23
    """
    sigma_f = sigma_v0_kPa + delta_sigma_kPa
    factor = H_m / (1.0 + e0)

    if sigma_v0_kPa <= 0 or sigma_f <= sigma_v0_kPa:
        return 0.0, "No load"

    # Normally consolidated
    if sigma_v0_kPa >= Pc_kPa:
        Sc = Cc * factor * np.log10(sigma_f / sigma_v0_kPa)
        return Sc, "NC"

    # Overconsolidated — stays OC
    if sigma_f <= Pc_kPa:
        Sc = Cr * factor * np.log10(sigma_f / sigma_v0_kPa)
        return Sc, "OC"

    # Crosses preconsolidation pressure (OC → NC)
    Sc = (Cr * factor * np.log10(Pc_kPa / sigma_v0_kPa) +
          Cc * factor * np.log10(sigma_f / Pc_kPa))
    return Sc, "OC→NC"


def total_consolidation_settlement(layers, Df, B, L, P_kN, wt_design_bgl,
                                   sublayer_thickness=0.5):
    """
    Total 1D consolidation settlement below a rectangular footing.

    Steps
    -----
    1. Net foundation pressure Δp
    2. For each clay layer below the footing, divide into sublayers ≤ 0.5 m
    3. For each sublayer at mid-depth z_mid (bgl):
       a. σ′v0 = effective vertical stress at z_mid
       b. Δσ = Boussinesq centre stress increase at depth (z_mid - Df)
       c. Sc from consolidation_settlement_layer(...)
    4. Sum all Sc over clay sublayers

    Returns
    -------
    dict with keys: S_total_mm, sublayer_data (list of dicts)
    Cite: IS 8009:1976 Part 1 Cl. 5
    """
    delta_p = _net_foundation_pressure(layers, Df, B, L, P_kN, wt_design_bgl)

    sublayer_data = []
    S_total = 0.0

    for lyr in layers:
        if not lyr.get("is_clay", False):
            continue
        Cc = lyr.get("Cc") or 0.3
        Cr = lyr.get("Cr") or 0.06
        e0 = lyr.get("e0") or 0.9
        Pc = lyr.get("Pc_kPa") or 100.0

        lyr_top = max(lyr["depth_top"], Df)
        lyr_bot = lyr["depth_bot"]
        if lyr_top >= lyr_bot:
            continue

        z = lyr_top
        while z < lyr_bot:
            dz = min(sublayer_thickness, lyr_bot - z)
            z_mid_bgl = z + dz / 2.0
            z_below_footing = z_mid_bgl - Df  # depth below footing base

            sigma_v0 = _effective_stress_at(layers, z_mid_bgl, wt_design_bgl)
            delta_sigma = stress_increase_centre(delta_p, B, L, z_below_footing)

            Sc, case = consolidation_settlement_layer(
                dz, e0, Cc, Cr, sigma_v0, Pc, delta_sigma
            )
            S_total += Sc
            sublayer_data.append({
                "z_mid_bgl_m": round(z_mid_bgl, 3),
                "z_below_footing_m": round(z_below_footing, 3),
                "layer_name": lyr.get("name", lyr.get("symbol", "Clay")),
                "sigma_v0_kPa": round(sigma_v0, 2),
                "delta_sigma_kPa": round(delta_sigma, 2),
                "sigma_f_kPa": round(sigma_v0 + delta_sigma, 2),
                "Pc_kPa": round(Pc, 2),
                "case": case,
                "Sc_mm": round(Sc * 1000, 3),
                "dz_m": round(dz, 3),
            })
            z += dz

    return {
        "S_total_mm": round(S_total * 1000, 2),
        "sublayer_data": sublayer_data,
    }


# ---------------------------------------------------------------------------
# Terzaghi consolidation theory
# ---------------------------------------------------------------------------

def degree_of_consolidation(Tv):
    """
    Terzaghi (1943) average degree of consolidation U vs time factor Tv.
    For Tv giving U ≤ 0.60: U = √(4·Tv/π)
    For Tv giving U > 0.60: U = 1 - (8/π²)·exp(-π²·Tv/4)

    Solve iteratively: use approximation boundary at Tv ≈ 0.2171 (U=0.6).
    Returns U in range [0, 1].
    Cite: Terzaghi (1943); Das (2016) Eq. 7.56-7.57
    """
    if np.isscalar(Tv):
        Tv = float(Tv)
        U_approx = np.sqrt(4.0 * Tv / np.pi)
        if U_approx <= 0.60:
            return float(np.clip(U_approx, 0, 1))
        return float(np.clip(1.0 - (8.0 / np.pi ** 2) * np.exp(-np.pi ** 2 * Tv / 4.0), 0, 1))
    else:
        Tv = np.asarray(Tv, dtype=float)
        U = np.empty_like(Tv)
        U_approx = np.sqrt(4.0 * Tv / np.pi)
        mask = U_approx <= 0.60
        U[mask] = U_approx[mask]
        U[~mask] = 1.0 - (8.0 / np.pi ** 2) * np.exp(-np.pi ** 2 * Tv[~mask] / 4.0)
        return np.clip(U, 0, 1)


def time_factor(cv_m2s, t_seconds, Hdr_m):
    """
    Time factor  Tv = cv × t / Hdr²
    Hdr = drainage path length (m):
        One-way drainage: Hdr = H (full layer thickness)
        Two-way drainage: Hdr = H/2

    Parameters
    ----------
    cv_m2s : float
        Coefficient of consolidation (m²/s).
    t_seconds : float
        Elapsed time (seconds).
    Hdr_m : float
        Drainage path length (m).

    Returns Tv (dimensionless).
    Cite: Terzaghi (1943); IS 8009:1976
    """
    if Hdr_m <= 0:
        return 0.0
    return float(cv_m2s) * float(t_seconds) / (float(Hdr_m) ** 2)


def time_settlement_curve(Sc_total_m, cv_m2s, Hdr_m, t_max_years=50, n_points=200):
    """
    Generate a time–settlement curve using Terzaghi consolidation theory.

    Parameters
    ----------
    Sc_total_m : float
        Ultimate consolidation settlement (m).
    cv_m2s : float
        Coefficient of consolidation (m²/s).
    Hdr_m : float
        Drainage path length (m).
    t_max_years : float
        Maximum time to plot (years).
    n_points : int
        Number of evaluation points.

    Returns
    -------
    t_years_array : np.ndarray
        Time values (years), from 0 to t_max_years.
    S_mm_array : np.ndarray
        Corresponding settlement values (mm).
    Cite: Terzaghi (1943) consolidation theory
    """
    t_years_array = np.linspace(0.0, t_max_years, n_points)
    SECONDS_PER_YEAR = 365.25 * 24 * 3600

    S_mm_array = np.empty(n_points)
    for i, t_yr in enumerate(t_years_array):
        t_sec = t_yr * SECONDS_PER_YEAR
        Tv = time_factor(cv_m2s, t_sec, Hdr_m)
        U = degree_of_consolidation(Tv)
        S_mm_array[i] = U * Sc_total_m * 1000.0

    return t_years_array, S_mm_array
