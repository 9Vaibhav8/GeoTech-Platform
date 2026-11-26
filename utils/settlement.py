"""
utils/settlement.py
Immediate (Schmertmann et al. 1978) and 1-D consolidation (Terzaghi 1943) settlement.

Sources (cite in the report):
  [S78]  Schmertmann, Hartman & Brown (1978) "Improved strain influence factor diagrams",
         JGED ASCE 104(GT8) — C1, C2, Iz diagram, Izp.
  [S70]  Schmertmann (1970) JSMFD ASCE 96(SM3) — origin of the Iz method.
  [B96]  Bowles (1996) Foundation Analysis and Design, 5th ed., Table 5-5 (Es from SPT N,
         after Webb 1969):  sand 500(N+15) kPa;  gravelly sand/gravel 1200(N+6) kPa.
         ** verify the table values against your copy **
  [T43]  Terzaghi (1943) Theoretical Soil Mechanics — 1-D consolidation and Tv(U).
  [IS8009] IS 8009 (Part 1):1976 — Calculation of settlements of foundations.
Units: kN, kPa, m (settlements returned in mm).
"""

import numpy as np
from utils.stress_increase import stress_increase_centre

GAMMA_W = 9.81  # kN/m³
GRANULAR_SYMBOLS = {"SM", "SP", "SW", "SC", "GW", "GP", "GM", "GC", "Fill"}


# ---------------------------------------------------------------------------
# Effective stress / net pressure
# ---------------------------------------------------------------------------
def _effective_stress_at(layers, z_bgl, wt_design_bgl, warnings=None):
    """
    σ′v at depth z_bgl (m): γ_moist above the design water table, γ_sat below,
    minus u = γw·(z − z_wt).  [Terzaghi effective-stress principle, T43]
    Missing unit weights fall back to 18 / 20 kN/m³ and are reported in `warnings`.
    """
    sigma_v = 0.0
    u = 0.0
    for lyr in layers:
        if lyr["depth_top"] >= z_bgl:
            break
        z_top = lyr["depth_top"]
        z_bot = min(lyr["depth_bot"], z_bgl)
        g_m = lyr.get("gamma_moist")
        g_s = lyr.get("gamma_sat")
        if (not g_m or not g_s) and warnings is not None:
            msg = f"Layer {lyr.get('name', lyr.get('symbol', '?'))}: missing unit weight, default 18/20 kN/m³ used"
            if msg not in warnings:
                warnings.append(msg)
        g_m = g_m or 18.0
        g_s = g_s or 20.0
        if z_bot <= wt_design_bgl:                       # fully above WT
            sigma_v += g_m * (z_bot - z_top)
        elif z_top >= wt_design_bgl:                     # fully below WT
            sigma_v += g_s * (z_bot - z_top)
            u += GAMMA_W * (z_bot - z_top)
        else:                                            # straddles WT
            sigma_v += g_m * (wt_design_bgl - z_top) + g_s * (z_bot - wt_design_bgl)
            u += GAMMA_W * (z_bot - wt_design_bgl)
    return sigma_v - u


def _net_foundation_pressure(layers, Df, B, L, P_kN, wt_design_bgl, warnings=None):
    """
    Δp = P/(B·L) − σ′v0(Df)   (net pressure, kPa)   [S78 uses q − σ′vo]
    NOTE: strictly the excavation removes TOTAL stress; using effective σ′v0 (textbook
    practice, Das/Schmertmann) adds u(Df) to Δp when the base is below the water table.
    """
    q_gross = P_kN / (B * L)
    q_surcharge = _effective_stress_at(layers, Df, wt_design_bgl, warnings)
    delta_p = q_gross - q_surcharge
    if delta_p < 1.0 and warnings is not None:
        warnings.append(f"Net pressure {delta_p:.1f} kPa ≤ 0 (footing too large/deep for the load) — set to 1 kPa")
    return max(delta_p, 1.0)


# ---------------------------------------------------------------------------
# Schmertmann (1978) — immediate settlement
# ---------------------------------------------------------------------------
def schmertmann_Es_from_N(N_corrected, soil_type="sand"):
    """
    Es (kPa) from corrected SPT N.   Cite: Bowles (1996) Table 5-5, after Webb (1969).
        sand   : Es = 500 (N + 15)
        gravel : Es = 1200 (N + 6)      (gravelly sand and gravel)
    (Schmertmann's own route is Es = 2.5 qc square / 3.5 qc strip; use it if CPT data exist.)
    """
    N = max(1, int(N_corrected)) if N_corrected else 5
    if soil_type.lower() in ("gravel", "gw", "gp", "gm", "gc"):
        return 1200.0 * (N + 6)
    return 500.0 * (N + 15)


def _iz_geometry(B, L):
    """
    (Iz at z=0, depth to peak z1, depth to zero z2) interpolated linearly with L/B
    between square (L/B = 1) and strip (L/B >= 10).   Cite: S78 Fig. 4
        square: 0.1, 0.5B, 2B      strip: 0.2, B, 4B
    """
    r = 1.0 if not L else min(max(L / B, 1.0), 10.0)
    f = (r - 1.0) / 9.0
    return 0.1 + 0.1 * f, B * (0.5 + 0.5 * f), B * (2.0 + 2.0 * f)


def strain_influence_factor(z, B, L=None, footing_type="square", Iz_peak=0.6):
    """
    Schmertmann et al. (1978) Iz at depth z (m) below the footing base.
      0 ≤ z ≤ z1 : Iz = Iz0 + (Iz_peak − Iz0)·z/z1
      z1 < z ≤ z2: Iz = Iz_peak·(z2 − z)/(z2 − z1)
      z > z2     : 0
    Iz0, z1, z2 interpolated with L/B (square 0.1/0.5B/2B, strip 0.2/B/4B).
    """
    if L is None:
        L = 10.0 * B if footing_type == "strip" else B
    Iz0, z1, z2 = _iz_geometry(B, L)
    if z <= 0:
        return Iz0
    if z <= z1:
        return Iz0 + (Iz_peak - Iz0) * z / z1
    if z <= z2:
        return Iz_peak * (z2 - z) / (z2 - z1)
    return 0.0


def _mean_Iz(z_top, z_bot, B, L, Iz_peak):
    """Exact mean of the piecewise-linear Iz over [z_top, z_bot] (kinks at z1, z2 included)."""
    _, z1, z2 = _iz_geometry(B, L)
    pts = sorted({z_top, z_bot, *[k for k in (z1, z2) if z_top < k < z_bot]})
    area = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        area += 0.5 * (strain_influence_factor(a, B, L, Iz_peak=Iz_peak) +
                       strain_influence_factor(b, B, L, Iz_peak=Iz_peak)) * (b - a)
    return area / (z_bot - z_top)


def schmertmann_settlement(layers, Df, B, L, P_kN, wt_design_bgl, t_years=50):
    """
    S_i = C1·C2·Δp·Σ (Iz/Es)·Δz        [S78]
      C1 = 1 − 0.5 σ′v0/Δp ≥ 0.5,   C2 = 1 + 0.2 log10(t/0.1),
      Iz,peak = 0.5 + 0.1 √(Δp/σ′vp), σ′vp at the depth of the Iz peak (0.5B square … B strip).
    B is taken as the smaller plan dimension. Granular layers only (clay → consolidation).
    Returns dict: S_mm, C1, C2, delta_p, Iz_peak, sigma_v0, sublayer_data, warnings.
    """
    B, L = min(B, L), max(B, L)
    warnings = []
    delta_p = _net_foundation_pressure(layers, Df, B, L, P_kN, wt_design_bgl, warnings)
    sigma_v0 = _effective_stress_at(layers, Df, wt_design_bgl, warnings)

    C1 = max(0.5, 1.0 - 0.5 * (sigma_v0 / delta_p))
    C2 = 1.0 + 0.2 * np.log10(max(t_years, 0.1) / 0.1)

    Iz0, z1, z2 = _iz_geometry(B, L)
    sigma_vp = _effective_stress_at(layers, Df + z1, wt_design_bgl)
    Iz_peak = 0.5 + 0.1 * np.sqrt(delta_p / sigma_vp) if sigma_vp > 0 else 0.6

    sublayer_data, sum_Iz_Es_dz, sub_thick = [], 0.0, 0.5
    z_start, z_end = Df, Df + z2

    for lyr in layers:
        seg_top = max(lyr["depth_top"], z_start)
        seg_bot = min(lyr["depth_bot"], z_end)
        if seg_top >= seg_bot:
            continue
        symbol = lyr.get("symbol", "SM")
        if lyr.get("is_clay", False) or symbol not in GRANULAR_SYMBOLS:
            continue                                   # cohesive → consolidation module

        N_corr = lyr.get("N_corrected") or lyr.get("N_field")
        if not N_corr:
            N_corr = 10
            warnings.append(f"Layer {lyr.get('name', symbol)}: no N entered — N = 10 assumed")
        Es = schmertmann_Es_from_N(N_corr, "gravel" if symbol in ("GW", "GP", "GM", "GC") else "sand")

        z = seg_top
        while z < seg_bot - 1e-9:
            dz = min(sub_thick, seg_bot - z)
            zt, zb = z - Df, z + dz - Df
            Iz = _mean_Iz(zt, zb, B, L, Iz_peak)
            if Iz > 0:
                contrib = (Iz / Es) * dz
                sum_Iz_Es_dz += contrib
                sublayer_data.append({
                    "z_top_m": round(zt, 3), "z_bot_m": round(zb, 3), "z_mid_m": round((zt + zb) / 2, 3),
                    "layer_name": lyr.get("name", symbol), "symbol": symbol,
                    "Es_kPa": round(Es, 1), "Iz": round(Iz, 4), "Iz_over_Es": round(Iz / Es, 8),
                    "dz_m": round(dz, 3), "contrib_m": round(contrib, 8),
                })
            z += dz

    S_i_m = C1 * C2 * delta_p * sum_Iz_Es_dz
    return {
        "S_mm": round(S_i_m * 1000, 2), "C1": round(C1, 4), "C2": round(C2, 4),
        "delta_p": round(delta_p, 2), "Iz_peak": round(float(Iz_peak), 4),
        "sigma_v0": round(sigma_v0, 2), "sublayer_data": sublayer_data, "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 1-D consolidation — Terzaghi (1943)
# ---------------------------------------------------------------------------
def consolidation_settlement_layer(H_m, e0, Cc, Cr, sigma_v0_kPa, Pc_kPa, delta_sigma_kPa):
    """
    Sublayer settlement (m).  Cite: T43; IS 8009 (Part 1); add your textbook equation numbers.
      NC (σ′v0 ≥ Pc)   : Sc = Cc/(1+e0)·H·log10((σ′v0+Δσ)/σ′v0)
      OC, stays OC     : Sc = Cr/(1+e0)·H·log10((σ′v0+Δσ)/σ′v0)
      OC → NC          : Sc = Cr/(1+e0)·H·log10(Pc/σ′v0) + Cc/(1+e0)·H·log10((σ′v0+Δσ)/Pc)
    Returns (Sc_m, case_label)
    """
    sigma_f = sigma_v0_kPa + delta_sigma_kPa
    factor = H_m / (1.0 + e0)
    if sigma_v0_kPa <= 0 or sigma_f <= sigma_v0_kPa:
        return 0.0, "No load"
    if sigma_v0_kPa >= Pc_kPa:
        return Cc * factor * np.log10(sigma_f / sigma_v0_kPa), "NC"
    if sigma_f <= Pc_kPa:
        return Cr * factor * np.log10(sigma_f / sigma_v0_kPa), "OC"
    return (Cr * factor * np.log10(Pc_kPa / sigma_v0_kPa) +
            Cc * factor * np.log10(sigma_f / Pc_kPa)), "OC→NC"


def total_consolidation_settlement(layers, Df, B, L, P_kN, wt_design_bgl, sublayer_thickness=0.5):
    """
    Σ Sc over clay sublayers ≤ 0.5 m thick, Δσ from Boussinesq at the footing centre
    (utils.stress_increase), Δp = net pressure.  Cite: IS 8009 (Part 1):1976; T43.
    A missing Pc is treated as NORMALLY consolidated (Pc = σ′v0), not as a default value.
    Returns dict: S_total_mm, sublayer_data, warnings.
    """
    warnings = []
    sublayer_thickness = min(sublayer_thickness, 0.5)
    delta_p = _net_foundation_pressure(layers, Df, B, L, P_kN, wt_design_bgl, warnings)
    sublayer_data, S_total = [], 0.0

    for lyr in layers:
        if not lyr.get("is_clay", False):
            continue
        nm = lyr.get("name", lyr.get("symbol", "Clay"))
        lyr_top, lyr_bot = max(lyr["depth_top"], Df), lyr["depth_bot"]
        if lyr_top >= lyr_bot:
            continue
        for key, dflt in (("Cc", 0.3), ("Cr", 0.06), ("e0", 0.9)):
            if not lyr.get(key):
                warnings.append(f"{nm}: {key} not entered — default {dflt} used")
        Cc, Cr, e0 = lyr.get("Cc") or 0.3, lyr.get("Cr") or 0.06, lyr.get("e0") or 0.9
        Pc_in = lyr.get("Pc_kPa")
        if not Pc_in:
            warnings.append(f"{nm}: Pc not entered — treated as normally consolidated (Pc = σ′v0)")

        z = lyr_top
        while z < lyr_bot - 1e-9:
            dz = min(sublayer_thickness, lyr_bot - z)
            z_mid_bgl = z + dz / 2.0
            z_bf = z_mid_bgl - Df
            sigma_v0 = _effective_stress_at(layers, z_mid_bgl, wt_design_bgl)
            delta_sigma = stress_increase_centre(delta_p, B, L, z_bf)
            Pc = Pc_in if Pc_in else sigma_v0
            Sc, case = consolidation_settlement_layer(dz, e0, Cc, Cr, sigma_v0, Pc, delta_sigma)
            S_total += Sc
            sublayer_data.append({
                "z_mid_bgl_m": round(z_mid_bgl, 3), "z_below_footing_m": round(z_bf, 3), "layer_name": nm,
                "sigma_v0_kPa": round(sigma_v0, 2), "delta_sigma_kPa": round(delta_sigma, 2),
                "sigma_f_kPa": round(sigma_v0 + delta_sigma, 2), "Pc_kPa": round(Pc, 2),
                "case": case, "Sc_mm": round(Sc * 1000, 3), "dz_m": round(dz, 3),
            })
            z += dz

    return {"S_total_mm": round(S_total * 1000, 2), "sublayer_data": sublayer_data,
            "warnings": sorted(set(warnings), key=warnings.index)}


# ---------------------------------------------------------------------------
# Terzaghi consolidation theory
# ---------------------------------------------------------------------------
def degree_of_consolidation(Tv):
    """
    Average degree of consolidation, exact series  [T43]:
        U = 1 − Σ_{m=0}^{∞} (2/M²)·exp(−M²·Tv),  M = π(2m+1)/2
    (parabolic √(4Tv/π) used only for Tv < 1e-4 where the series converges slowly).
    Check: U(Tv=0.848) = 0.90, U(Tv=0.197) = 0.50.
    """
    scalar = np.isscalar(Tv)
    Tv = np.atleast_1d(np.asarray(Tv, dtype=float))
    U = np.sqrt(4.0 * np.clip(Tv, 0, None) / np.pi)
    big = Tv >= 1e-4
    if big.any():
        M = np.pi * (2 * np.arange(500) + 1) / 2.0
        U[big] = 1.0 - np.sum(2.0 / M**2 * np.exp(-np.outer(Tv[big], M**2)), axis=1)
    U = np.clip(U, 0.0, 1.0)
    return float(U[0]) if scalar else U


def time_factor(cv_m2s, t_seconds, Hdr_m):
    """Tv = cv·t/Hdr².  Hdr = H (one-way) or H/2 (two-way).  Cite: T43; IS 8009."""
    if Hdr_m <= 0:
        return 0.0
    return float(cv_m2s) * float(t_seconds) / (float(Hdr_m) ** 2)


def time_settlement_curve(Sc_total_m, cv_m2s, Hdr_m, t_max_years=50, n_points=200):
    """Consolidation settlement S(t) = U(Tv)·Sc.  Returns (t_years, S_mm) arrays."""
    t_years = np.linspace(0.0, float(t_max_years), int(n_points))
    Tv = np.array([time_factor(cv_m2s, t * 365.25 * 24 * 3600, Hdr_m) for t in t_years])
    return t_years, np.asarray(degree_of_consolidation(Tv)) * Sc_total_m * 1000.0
