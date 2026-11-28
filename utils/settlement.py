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
from utils.bearing_capacity import validate_profile, effective_overburden_pressure

SEC_PER_YEAR = 365.25 * 24 * 3600

GAMMA_W = 9.81  # kN/m³
GRANULAR_SYMBOLS = {"SM", "SP", "SW", "SC", "GW", "GP", "GM", "GC", "Fill"}


# ---------------------------------------------------------------------------
# Effective stress / net pressure
# ---------------------------------------------------------------------------
def _number(value, name, minimum=0.0, positive=False):
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be entered as a number.") from None
    if not np.isfinite(v) or v < minimum or (positive and v == minimum):
        raise ValueError(f"{name} must be finite and {'>' if positive else '>='} {minimum:g}.")
    return v


def _effective_stress_at(layers, z_bgl, wt_design_bgl, warnings=None):
    """Terzaghi effective stress; shared validated overburden integration."""
    return effective_overburden_pressure(layers, z_bgl, wt_design_bgl)[0]


def _net_foundation_pressure(layers, Df, B, L, P_kN, wt_design_bgl, warnings=None, *, load_basis="gross_effective"):
    """S78: net pressure = effective gross contact pressure minus initial effective surcharge.
    Net load input bypasses subtraction. Total gross load is NOT interchangeable
    with effective gross load below groundwater; user must establish load basis.
    Nonpositive net stress is outside this compressive settlement model.
    """
    B = _number(B, "Width B", positive=True)
    L = _number(L, "Length L", positive=True)
    P_kN = _number(P_kN, "Load", positive=True)
    Df = _number(Df, "Founding depth")
    surcharge = _effective_stress_at(layers, Df, wt_design_bgl)
    if load_basis not in ("gross_effective", "net"):
        raise ValueError("Choose gross_effective or net load basis.")
    q = P_kN / (B * L) - (surcharge if load_basis == "gross_effective" else 0.0)
    if not np.isfinite(q) or q <= 0:
        raise ValueError(f"Net pressure {q:.6g} kPa is nonpositive or invalid. Check load basis, excavation and dimensions; no settlement prediction made.")
    return q


# Schmertmann (1978) — granular settlement

def schmertmann_Es_from_N(N_corrected, soil_type="sand"):
    """
    Es (kPa) from corrected SPT N.   Cite: Bowles (1996) Table 5-5, after Webb (1969).
        sand   : Es = 500 (N + 15)
        gravel : Es = 1200 (N + 6)      (gravelly sand and gravel)
    (Schmertmann's own route is Es = 2.5 qc square / 3.5 qc strip; use it if CPT data exist.)
    """
    N = _number(N_corrected, "SPT N", positive=True)
    if N >= 100:
        raise ValueError("SPT N outside this correlation policy; enter a justified Es instead.")
    if soil_type.lower() in ("gravel", "gw", "gp", "gm", "gc"):
        return 1200.0 * (N + 6)
    return 500.0 * (N + 15)


def _iz_geometry(B, L):
    """
    (Iz at z=0, depth to peak z1, depth to zero z2) interpolated linearly with L/B
    between square (L/B = 1) and strip (L/B >= 10).   Cite: S78 Fig. 4
        square: 0.1, 0.5B, 2B      strip: 0.2, B, 4B
    """
    B = _number(B, "Width B", positive=True)
    L = B if L is None else _number(L, "Length L", positive=True)
    B, L = min(B, L), max(B, L)
    r = min(L / B, 10.0)
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
    z = _number(z, "Depth below footing")
    B = _number(B, "Width B", positive=True)
    Iz_peak = _number(Iz_peak, "Peak influence factor", positive=True)
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


def schmertmann_settlement(layers, Df, B, L, P_kN, wt_design_bgl, t_years=50, *, load_basis="gross_effective", allow_raw_n=False):
    """
    S_i = C1·C2·Δp·Σ (Iz/Es)·Δz        [S78]
      C1 = 1 − 0.5 σ′v0/Δp ≥ 0.5,   C2 = 1 + 0.2 log10(t/0.1),
      Iz,peak = 0.5 + 0.1 √(Δp/σ′vp), σ′vp at the depth of the Iz peak (0.5B square … B strip).
    B is taken as the smaller plan dimension. Granular layers only (clay → consolidation).
    Uses entered layer Es_kPa when provided; otherwise estimates from SPT N (optional correlation)
    and logs a warning. Missing or invalid stiffness raises an error.
    Returns dict: S_mm, C1, C2, delta_p, Iz_peak, sigma_v0, sublayer_data, warnings.
    """
    B, L = sorted((_number(B, "Width", positive=True), _number(L, "Length", positive=True)))
    Df = _number(Df, "Founding depth")
    t_years = _number(t_years, "Time")
    warnings = []
    delta_p = _net_foundation_pressure(layers, Df, B, L, P_kN, wt_design_bgl, warnings, load_basis=load_basis)
    sigma_v0 = _effective_stress_at(layers, Df, wt_design_bgl, warnings)

    C1 = max(0.5, 1.0 - 0.5 * (sigma_v0 / delta_p))
    C2 = 1.0 + 0.2 * np.log10(max(t_years, 0.1) / 0.1)

    Iz0, z1, z2 = _iz_geometry(B, L)
    layers = validate_profile(layers, Df + z2)
    sigma_vp = _effective_stress_at(layers, Df + z1, wt_design_bgl)
    if sigma_vp <= 0:
        raise ValueError("Effective stress at Iz peak must be positive.")
    Iz_peak = 0.5 + 0.1 * np.sqrt(delta_p / sigma_vp)

    sublayer_data, sum_Iz_Es_dz, sub_thick = [], 0.0, 0.5
    z_start, z_end = Df, Df + z2

    for lyr in layers:
        seg_top = max(lyr["depth_top"], z_start)
        seg_bot = min(lyr["depth_bot"], z_end)
        if seg_top >= seg_bot:
            continue
        symbol = lyr.get("symbol")
        if lyr.get("is_clay", False):
            continue
        if symbol not in GRANULAR_SYMBOLS:
            raise ValueError(f"Layer {lyr.get('name', symbol)}: unsupported soil for granular settlement; classify and select an appropriate model.")

        lyr_label = lyr.get("name", symbol)
        es_entered = lyr.get("Es_kPa")
        if es_entered is not None:
            Es = _number(es_entered, f"{lyr_label}: Es", positive=True)
            es_source = "Entered"
        else:
            N_corr = lyr.get("N_corrected")
            raw_used = False
            if lyr.get("N_refusal") or lyr.get("P2_spt_status") == "no_valid_record":
                N_corr = None
            elif N_corr is None and allow_raw_n and lyr.get("P2_spt_status") != "corrected":
                N_corr = lyr.get("N_field")
                raw_used = True
            if N_corr is None:
                raise ValueError(f"{lyr_label}: enter Es or apply valid corrected SPT N in P2. Refusal/excluded data cannot be used.")
            Es = schmertmann_Es_from_N(N_corr, "gravel" if symbol in ("GW", "GP", "GM", "GC") else "sand")
            es_source = f"{'Raw' if raw_used else 'Corrected'} SPT correlation (N={N_corr})"
            warnings.append(f"{lyr_label}: {es_source}; Es={Es:.3g} kPa. Verify empirical correlation for this soil.")

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
                    "layer_name": lyr_label, "symbol": symbol,
                    "Es_kPa": round(Es, 1), "Es_source": es_source,
                    "Iz": round(Iz, 4), "Iz_over_Es": round(Iz / Es, 8),
                    "dz_m": round(dz, 3), "contrib_m": round(contrib, 8),
                })
            z += dz

    S_i_m = C1 * C2 * delta_p * sum_Iz_Es_dz
    return {
        "S_mm": float(S_i_m * 1000), "C1": round(C1, 4), "C2": round(C2, 4),
        "delta_p": round(delta_p, 2), "Iz_peak": round(float(Iz_peak), 4),
        "sigma_v0": round(sigma_v0, 2), "S_initial_mm": S_i_m * 1000 / C2, "sublayer_data": sublayer_data, "warnings": warnings,
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
    H_m = _number(H_m, "Sublayer thickness", positive=True)
    e0 = _number(e0, "Void ratio")
    Cc = _number(Cc, "Cc")
    Cr = _number(Cr, "Cr")
    if Cr > Cc:
        raise ValueError("Cr cannot exceed Cc in this compression model.")
    sigma_v0_kPa = _number(sigma_v0_kPa, "Initial effective stress", positive=True)
    Pc_kPa = _number(Pc_kPa, "Preconsolidation pressure", positive=True)
    delta_sigma_kPa = _number(delta_sigma_kPa, "Stress increase")
    sigma_f = sigma_v0_kPa + delta_sigma_kPa
    factor = H_m / (1.0 + e0)
    if delta_sigma_kPa == 0:
        return 0.0, "No load"
    if sigma_v0_kPa >= Pc_kPa:
        return Cc * factor * np.log10(sigma_f / sigma_v0_kPa), "NC"
    if sigma_f <= Pc_kPa:
        return Cr * factor * np.log10(sigma_f / sigma_v0_kPa), "OC"
    return (Cr * factor * np.log10(Pc_kPa / sigma_v0_kPa) +
            Cc * factor * np.log10(sigma_f / Pc_kPa)), "OC→NC"


def total_consolidation_settlement(layers, Df, B, L, P_kN, wt_design_bgl, sublayer_thickness=0.5, *, load_basis="gross_effective", assume_nc=False):
    """
    Σ Sc over clay sublayers ≤ 0.5 m thick, Δσ from Boussinesq at the footing centre
    (utils.stress_increase), Δp = net pressure.  Cite: IS 8009 (Part 1):1976; T43.
    Missing Pc requires explicit assume_nc=True.
    Returns dict: S_total_mm, sublayer_data, warnings.
    """
    warnings = []
    sublayer_thickness = _number(sublayer_thickness, "Sublayer thickness", positive=True)
    if sublayer_thickness > 0.5:
        raise ValueError("Consolidation sublayers must be no thicker than 0.5 m.")
    if sublayer_thickness < 1e-6:
        raise ValueError("Sublayer thickness below numerical resolution.")
    Df = _number(Df, "Founding depth")
    B, L = sorted((_number(B, "Width", positive=True), _number(L, "Length", positive=True)))
    layers = validate_profile(layers, Df)
    delta_p = _net_foundation_pressure(layers, Df, B, L, P_kN, wt_design_bgl, warnings, load_basis=load_basis)
    sublayer_data, S_total, layer_results = [], 0.0, []

    for layer_idx, lyr in enumerate(layers):
        if not lyr.get("is_clay", False):
            if lyr.get("symbol") in {"CL", "CI", "CH"} and lyr["depth_bot"] > Df:
                raise ValueError(f"{lyr.get('name', lyr['symbol'])}: clay symbol present but consolidation flag is disabled.")
            continue
        nm = lyr.get("name", lyr.get("symbol", "Clay"))
        lyr_top, lyr_bot = max(lyr["depth_top"], Df), lyr["depth_bot"]
        if lyr_top >= lyr_bot:
            continue
        Cc = _number(lyr.get("Cc"), f"{nm}: Cc")
        e0 = _number(lyr.get("e0"), f"{nm}: e0")
        Pc_in = lyr.get("Pc_kPa")
        if Pc_in is None:
            if not assume_nc:
                raise ValueError(f"{nm}: enter Pc or explicitly assume normally consolidated clay.")
            warnings.append(f"{nm}: user explicitly assumed normally consolidated clay.")
        else:
            Pc_in = _number(Pc_in, f"{nm}: Pc", positive=True)
        Cr = lyr.get("Cr")
        layer_sum = 0.0

        z = lyr_top
        while z < lyr_bot - 1e-9:
            dz = min(sublayer_thickness, lyr_bot - z)
            z_mid_bgl = z + dz / 2.0
            z_bf = z_mid_bgl - Df
            sigma_v0 = _effective_stress_at(layers, z_mid_bgl, wt_design_bgl)
            delta_sigma = stress_increase_centre(delta_p, B, L, z_bf)
            Pc = Pc_in if Pc_in is not None else sigma_v0
            cr_used = 0.0 if Cr is None and sigma_v0 >= Pc else _number(Cr, f"{nm}: Cr")
            Sc, case = consolidation_settlement_layer(dz, e0, Cc, cr_used, sigma_v0, Pc, delta_sigma)
            S_total += Sc
            layer_sum += Sc
            sublayer_data.append({
                "z_mid_bgl_m": round(z_mid_bgl, 3), "z_below_footing_m": round(z_bf, 3), "layer_name": nm, "layer_idx": layer_idx,
                "sigma_v0_kPa": round(sigma_v0, 2), "delta_sigma_kPa": round(delta_sigma, 2),
                "sigma_f_kPa": round(sigma_v0 + delta_sigma, 2), "Pc_kPa": round(Pc, 2),
                "case": case, "Sc_mm": round(Sc * 1000, 3), "dz_m": round(dz, 3),
            })
            z += dz
        layer_results.append({"layer_idx": layer_idx, "layer_name": nm, "H_m": lyr_bot - lyr_top,
                              "cv_m2s": lyr.get("cv_m2s"), "Sc_mm": layer_sum * 1000})

    return {"S_total_mm": S_total * 1000, "sublayer_data": sublayer_data, "layer_results": layer_results,
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
    arr = np.asarray(Tv, dtype=float)
    if np.any(~np.isfinite(arr)) or np.any(arr < 0):
        raise ValueError("Tv must be finite and nonnegative.")
    flat = arr.reshape(-1)
    U = np.sqrt(4.0 * flat / np.pi)
    big = flat >= 1e-4
    if big.any():
        M = np.pi * (2 * np.arange(500) + 1) / 2.0
        U[big] = 1.0 - np.sum(2.0 / M**2 * np.exp(-np.outer(flat[big], M**2)), axis=1)
    U = np.clip(U, 0.0, 1.0).reshape(arr.shape)
    return float(U) if arr.ndim == 0 else U


def time_factor(cv_m2s, t_seconds, Hdr_m):
    """Tv = cv·t/Hdr².  Hdr = H (one-way) or H/2 (two-way).  Cite: T43; IS 8009."""
    Hdr_m = _number(Hdr_m, "Drainage path", positive=True)
    return _number(cv_m2s, "cv", positive=True) * _number(t_seconds, "Time") / Hdr_m**2


def time_settlement_curve(Sc_total_m, cv_m2s, Hdr_m, t_max_years=50, n_points=200):
    """Consolidation settlement S(t) = U(Tv)·Sc.  Returns (t_years, S_mm) arrays."""
    Sc_total_m = _number(Sc_total_m, "Final settlement")
    t_max_years = _number(t_max_years, "Time horizon", positive=True)
    if not isinstance(n_points, (int, np.integer)) or not 2 <= n_points <= 10000:
        raise ValueError("n_points must be an integer from 2 to 10000.")
    t_years = np.linspace(0.0, t_max_years, n_points)
    Tv = np.array([time_factor(cv_m2s, t * 365.25 * 24 * 3600, Hdr_m) for t in t_years])
    return t_years, np.asarray(degree_of_consolidation(Tv)) * Sc_total_m * 1000.0



def multilayer_time_settlement(layer_results, t_years, drainage_by_layer):
    """Independent 1-D drainage approximation; sum Sc_i * U(cv_i*t/Hdr_i²).
    drainage_by_layer maps layer_idx to {'drainage': 'single'/'double',
    optional 'cv_m2s' and 'Hdr_m'}; Hdr override is an explicit drainage path.
    Terzaghi 1943 average U series; not a coupled multilayer diffusion solver.
    """
    t = np.asarray(t_years, dtype=float)
    if np.any(~np.isfinite(t)) or np.any(t < 0):
        raise ValueError("Time values must be finite and nonnegative.")
    total = np.zeros_like(t)
    details = []
    for layer in layer_results:
        sc = _number(layer["Sc_mm"], "Final layer settlement")
        if sc == 0:
            continue
        i = layer["layer_idx"]
        cfg = drainage_by_layer.get(i, {})
        mode = cfg.get("drainage")
        if mode not in ("single", "double"):
            raise ValueError(f"Choose drainage for {layer['layer_name']}.")
        cv = _number(cfg.get("cv_m2s", layer.get("cv_m2s")), f"{layer['layer_name']}: cv", positive=True)
        H = _number(layer["H_m"], "Clay thickness", positive=True)
        Hdr = _number(cfg.get("Hdr_m", H / (2 if mode == "double" else 1)), "Drainage path", positive=True)
        Tv = cv * t * SEC_PER_YEAR / Hdr**2
        curve = sc * degree_of_consolidation(Tv)
        total += curve
        details.append({"layer_idx": i, "layer_name": layer["layer_name"], "H_m": H, "Hdr_m": Hdr,
                        "cv_m2s": cv, "Sc_mm": sc, "t50_years": 0.197*Hdr**2/cv/SEC_PER_YEAR,
                        "t90_years": 0.848*Hdr**2/cv/SEC_PER_YEAR, "curve_mm": curve})
    return total, details
