"""
utils/bearing_capacity.py
IS 6403:1981 — Code of Practice for Determination of Bearing Capacity of Shallow Foundations.
All computations strictly in SI units (m, kN, kPa, kN/m³, deg).
"""

import math
from typing import Dict, List, Optional, Tuple

GAMMA_W = 9.81  # kN/m³, unit weight of water


# ---------------------------------------------------------------------------
# 1. Bearing Capacity Factors — IS 6403:1981 Cl. 5.1.2 & Table 1
# ---------------------------------------------------------------------------

def bearing_capacity_factors(phi_deg: float) -> Tuple[float, float, float]:
    """
    IS 6403:1981 Cl. 5.1.2 & Table 1 — Bearing capacity factors Nc, Nq, Nγ.

    Parameters
    ----------
    phi_deg : float
        Drained (or mobilised) friction angle φ (degrees).

    Returns
    -------
    (Nc, Nq, Ngamma) : tuple of float
        Dimensionless bearing capacity factors per IS 6403:1981 Table 1.
    """
    if phi_deg <= 0.0:
        # Source: IS 6403:1981 Cl. 5.1.2, Table 1 (undrained φ = 0 case)
        return 5.14, 1.0, 0.0

    phi_rad = math.radians(phi_deg)
    tan_phi = math.tan(phi_rad)
    n_phi = math.tan(math.radians(45.0 + phi_deg / 2.0)) ** 2

    # Source: IS 6403:1981 Cl. 5.1.2, Table 1
    Nq = n_phi * math.exp(math.pi * tan_phi)
    # Source: IS 6403:1981 Cl. 5.1.2, Table 1
    Nc = (Nq - 1.0) / tan_phi
    # Source: IS 6403:1981 Cl. 5.1.2, Table 1
    Ngamma = 2.0 * (Nq + 1.0) * tan_phi

    return Nc, Nq, Ngamma


# ---------------------------------------------------------------------------
# 2. Effective Area (Eccentric Loading) — IS 6403:1981 Cl. 5.1.2.1 (Meyerhof)
# ---------------------------------------------------------------------------

def effective_area(
    B: float,
    L: float,
    ex: float = 0.0,
    ey: float = 0.0,
    footing_shape: str = "rectangular",
) -> Tuple[float, float, float]:
    """
    IS 6403:1981 Cl. 5.1.2.1 — Meyerhof effective dimensions B_eff, L_eff, A_eff.

    - Rectangular / Square: B1 = B - 2·ex, L1 = L - 2·ey; enforce B_eff <= L_eff.
    - Strip: B_eff = B - 2·ex, L_eff = L (infinite).
    - Circular (diameter D = B): for e = sqrt(ex² + ey²) > 0, compute lens
      effective area A' and equivalent rectangle B' <= L' with B'·L' = A'.

    Parameters
    ----------
    B : float
        Footing width or circular diameter (m).
    L : float
        Footing length (m).
    ex : float
        Eccentricity along B (m).
    ey : float
        Eccentricity along L (m).
    footing_shape : str
        "strip", "square", "rectangular", or "circular".

    Returns
    -------
    (B_eff, L_eff, A_eff) : tuple of float
        Effective width (m), effective length (m), effective area (m²).
    """
    ex = abs(float(ex))
    ey = abs(float(ey))
    shape = footing_shape.lower()

    if shape == "strip":
        # Source: IS 6403:1981 Cl. 5.1.2.1 (Meyerhof effective width for strip footing)
        B_eff = B - 2.0 * ex
        L_eff = L
        A_eff = B_eff * L_eff
        return B_eff, L_eff, A_eff

    if shape == "circular":
        D = B
        # Source: IS 6403:1981 Cl. 5.1.2.1 (resultant radial eccentricity on circle)
        e = math.hypot(ex, ey)
        if e == 0.0:
            # Source: IS 6403:1981 Cl. 5.1.2.1 (concentric circular footing area)
            A_eff = 0.25 * math.pi * D ** 2
            return D, D, A_eff
        if e >= D / 2.0:
            return 0.0, 0.0, 0.0
        ratio = (2.0 * e) / D
        # Source: IS 6403:1981 Cl. 5.1.2.1 (Meyerhof effective area for eccentric circle)
        A_eff = 0.5 * (D ** 2) * (math.acos(ratio) - ratio * math.sqrt(1.0 - ratio ** 2))
        aspect = math.sqrt((D + 2.0 * e) / (D - 2.0 * e))
        # Source: IS 6403:1981 Cl. 5.1.2.1 (equivalent rectangle B' <= L' for eccentric circle)
        B_eff = math.sqrt(A_eff / aspect)
        L_eff = math.sqrt(A_eff * aspect)
        return B_eff, L_eff, A_eff

    if shape == "square":
        L = B

    # Source: IS 6403:1981 Cl. 5.1.2.1 (Meyerhof effective dimensions)
    B1 = B - 2.0 * ex
    # Source: IS 6403:1981 Cl. 5.1.2.1 (Meyerhof effective dimensions)
    L1 = L - 2.0 * ey

    if B1 <= 0.0 or L1 <= 0.0:
        return min(B1, L1), max(B1, L1), 0.0

    # Enforce B_eff <= L_eff
    B_eff = min(B1, L1)
    L_eff = max(B1, L1)
    # Source: IS 6403:1981 Cl. 5.1.2.1 (effective bearing area)
    A_eff = B_eff * L_eff
    return B_eff, L_eff, A_eff


def kern_check(
    B: float,
    L: float,
    ex: float = 0.0,
    ey: float = 0.0,
    footing_shape: str = "rectangular",
) -> Dict[str, object]:
    """
    Kern (no-tension) check for eccentrically loaded shallow footings.

    - Rectangular / Square: ex/B + ey/L <= 1/6
    - Strip: ex/B <= 1/6
    - Circular (D = B): e <= D/8

    Returns
    -------
    dict with keys: within_kern (bool), metric_value (float), limit_value (float), expression (str)
    """
    ex = abs(float(ex))
    ey = abs(float(ey))
    shape = footing_shape.lower()

    if shape == "circular":
        D = B
        # Source: IS 6403:1981 Cl. 5.1.2.1 / middle-quarter kern rule for circular base
        e = math.hypot(ex, ey)
        limit = D / 8.0
        return {
            "within_kern": e <= limit + 1e-12,
            "metric_value": e,
            "limit_value": limit,
            "expression": "e <= D / 8",
        }

    if shape == "strip":
        # Source: IS 6403:1981 Cl. 5.1.2.1 / middle-third kern rule for strip footing
        val = ex / B if B > 0.0 else float("inf")
        limit = 1.0 / 6.0
        return {
            "within_kern": val <= limit + 1e-12,
            "metric_value": val,
            "limit_value": limit,
            "expression": "ex / B <= 1/6",
        }

    if shape == "square":
        L = B

    # Source: IS 6403:1981 Cl. 5.1.2.1 / middle-third diamond kern rule for rectangular base
    val = (ex / B if B > 0.0 else float("inf")) + (ey / L if L > 0.0 else float("inf"))
    limit = 1.0 / 6.0
    return {
        "within_kern": val <= limit + 1e-12,
        "metric_value": val,
        "limit_value": limit,
        "expression": "ex / B + ey / L <= 1/6",
    }


# ---------------------------------------------------------------------------
# 3. Shape Factors — IS 6403:1981 Table 2, Cl. 5.1.2.1
# ---------------------------------------------------------------------------

def shape_factors(
    B: float,
    L: float,
    phi_deg: float = 0.0,
    footing_shape: str = "rectangular",
    is_eccentric: bool = False,
) -> Tuple[float, float, float]:
    """
    IS 6403:1981 Table 2, Cl. 5.1.2.1 — Shape factors sc, sq, sγ.

    - Strip: sc = 1.0, sq = 1.0, sγ = 1.0
    - Square (concentric): sc = 1.3, sq = 1.2, sγ = 0.8
    - Circular (concentric): sc = 1.3, sq = 1.2, sγ = 0.6
    - Rectangle (and eccentric square/circular converted to equivalent rectangle B' x L'):
        Enforce B' <= L':
        sc = 1 + 0.2*(B'/L'), sq = 1 + 0.2*(B'/L'), sγ = 1 - 0.4*(B'/L')

    Parameters
    ----------
    B : float
        Effective (or concentric) footing width (m).
    L : float
        Effective (or concentric) footing length (m).
    phi_deg : float
        Retained for signature compatibility (IS 6403 Table 2 shape factors are geometric).
    footing_shape : str
        "strip", "square", "rectangular", or "circular".
    is_eccentric : bool
        True if eccentric loading converts square/circular to equivalent rectangle.

    Returns
    -------
    (sc, sq, sgamma) : tuple of float
    """
    _ = phi_deg
    shape = footing_shape.lower()

    if shape == "strip" or L <= 0.0 or L > 1e5:
        # Source: IS 6403:1981 Cl. 5.1.2.1, Table 2 (Strip footing)
        return 1.0, 1.0, 1.0

    if not is_eccentric:
        if shape == "square":
            # Source: IS 6403:1981 Cl. 5.1.2.1, Table 2 (Concentric square footing)
            return 1.3, 1.2, 0.8
        if shape == "circular":
            # Source: IS 6403:1981 Cl. 5.1.2.1, Table 2 (Concentric circular footing)
            return 1.3, 1.2, 0.6

    # Rectangular (or eccentric square/circular converted to equivalent rectangle B' <= L')
    B_eff = min(B, L)
    L_eff = max(B, L)
    ratio = B_eff / L_eff if L_eff > 0.0 else 1.0

    # Source: IS 6403:1981 Cl. 5.1.2.1, Table 2 (Rectangular footing)
    sc = 1.0 + 0.2 * ratio
    # Source: IS 6403:1981 Cl. 5.1.2.1, Table 2 (Rectangular footing)
    sq = 1.0 + 0.2 * ratio
    # Source: IS 6403:1981 Cl. 5.1.2.1, Table 2 (Rectangular footing)
    sgamma = 1.0 - 0.4 * ratio

    return sc, sq, sgamma


# ---------------------------------------------------------------------------
# 4. Depth Factors — IS 6403:1981 Cl. 5.1.2.2
# ---------------------------------------------------------------------------

def depth_factors(Df: float, B: float, phi_deg: float) -> Tuple[float, float, float]:
    """
    IS 6403:1981 Cl. 5.1.2.2 — Depth factors dc, dq, dγ.

    sqrt(N_phi) = tan(45 + phi/2)
    dc          = 1 + 0.2 * (Df / B) * sqrt(N_phi)
    dq = dgamma = 1.0                         if phi < 10°
                  1 + 0.1 * (Df / B) * sqrt(N_phi)  if phi >= 10°

    Parameters
    ----------
    Df : float
        Founding depth below ground level (m).
    B : float
        Footing width (m).
    phi_deg : float
        Friction angle φ (degrees).

    Returns
    -------
    (dc, dq, dgamma) : tuple of float
    """
    if B <= 0.0 or Df <= 0.0:
        return 1.0, 1.0, 1.0

    # Source: IS 6403:1981 Cl. 5.1.2.2
    sqrt_n_phi = math.tan(math.radians(45.0 + phi_deg / 2.0))
    ratio = Df / B

    # Source: IS 6403:1981 Cl. 5.1.2.2
    dc = 1.0 + 0.2 * ratio * sqrt_n_phi

    if phi_deg < 10.0:
        # Source: IS 6403:1981 Cl. 5.1.2.2 (phi < 10 deg)
        dq = 1.0
        # Source: IS 6403:1981 Cl. 5.1.2.2 (phi < 10 deg)
        dgamma = 1.0
    else:
        # Source: IS 6403:1981 Cl. 5.1.2.2 (phi >= 10 deg)
        dq = 1.0 + 0.1 * ratio * sqrt_n_phi
        # Source: IS 6403:1981 Cl. 5.1.2.2 (phi >= 10 deg)
        dgamma = dq

    return dc, dq, dgamma


# ---------------------------------------------------------------------------
# 5. Inclination Factors — IS 6403:1981 Cl. 5.1.2.3
# ---------------------------------------------------------------------------

def inclination_factors(alpha_deg: float, phi_deg: float) -> Tuple[float, float, float]:
    """
    IS 6403:1981 Cl. 5.1.2.3 — Inclination factors ic, iq, iγ.

    ic = iq = (1 - alpha / 90)²
    iγ      = 1.0                      if phi == 0
              (1 - alpha / phi)²       if phi > 0 and alpha < phi
              0.0                      if phi > 0 and alpha >= phi

    Parameters
    ----------
    alpha_deg : float
        Inclination of resultant load from vertical (degrees, 0–90).
    phi_deg : float
        Friction angle φ (degrees).

    Returns
    -------
    (ic, iq, igamma) : tuple of float
    """
    # Source: IS 6403:1981 Cl. 5.1.2.3
    ic = (1.0 - alpha_deg / 90.0) ** 2
    # Source: IS 6403:1981 Cl. 5.1.2.3
    iq = ic

    if phi_deg <= 0.0:
        # Source: IS 6403:1981 Cl. 5.1.2.3 (phi == 0 case)
        igamma = 1.0
    elif alpha_deg >= phi_deg:
        # Source: IS 6403:1981 Cl. 5.1.2.3 (alpha >= phi limit)
        igamma = 0.0
    else:
        # Source: IS 6403:1981 Cl. 5.1.2.3
        igamma = (1.0 - alpha_deg / phi_deg) ** 2

    return ic, iq, igamma


# ---------------------------------------------------------------------------
# 6. Groundwater Correction — IS 6403:1981 Cl. 5.1.2.4
# ---------------------------------------------------------------------------

def water_table_factor(Df: float, B_eff: float, wt_bgl: float) -> float:
    """
    IS 6403:1981 Cl. 5.1.2.4 — Water table correction factor W' for the Nγ term.

    W' = 0.5                          if wt_bgl <= Df
    W' = 1.0                          if wt_bgl >= Df + B_eff
    W' = 0.5 * (1 + (wt_bgl - Df)/B_eff)  if Df < wt_bgl < Df + B_eff

    Parameters
    ----------
    Df : float
        Founding depth below ground level (m).
    B_eff : float
        Effective footing width (m).
    wt_bgl : float
        Design water table depth below ground level (m).

    Returns
    -------
    W_prime : float
        Dimensionless water table correction factor (0.5 <= W' <= 1.0).
    """
    if wt_bgl <= Df or B_eff <= 0.0:
        # Source: IS 6403:1981 Cl. 5.1.2.4
        return 0.5
    if wt_bgl >= Df + B_eff:
        # Source: IS 6403:1981 Cl. 5.1.2.4
        return 1.0
    # Source: IS 6403:1981 Cl. 5.1.2.4
    return 0.5 * (1.0 + (wt_bgl - Df) / B_eff)


def effective_overburden_at_depth(
    Df: float,
    wt_bgl: float,
    layers: Optional[List[Dict]] = None,
    gamma_moist: float = 18.0,
    gamma_sat: float = 20.0,
) -> float:
    """
    Compute effective overburden stress q_eff = σ'_v0(Df) at founding depth Df (kPa),
    integrating all overlying layers with moist unit weight above wt_bgl and
    submerged unit weight (γ_sat - γ_w) below wt_bgl.

    Falls back to single-layer (gamma_moist, gamma_sat) when layers is None/empty.
    """
    if Df <= 0.0:
        return 0.0

    if layers:
        sorted_layers = sorted(layers, key=lambda lyr: lyr["depth_top"])
        q_eff = 0.0
        for lyr in sorted_layers:
            z_top = float(lyr["depth_top"])
            z_bot = min(float(lyr["depth_bot"]), Df)
            if z_top >= Df:
                break
            if z_bot <= z_top:
                continue
            g_moist = float(lyr.get("gamma_moist", gamma_moist))
            g_sat = float(lyr.get("gamma_sat", gamma_sat))
            g_sub = g_sat - GAMMA_W

            if z_bot <= wt_bgl:
                # Source: IS 6403:1981 Cl. 5.1.2.4 (overburden above water table)
                q_eff += g_moist * (z_bot - z_top)
            elif z_top >= wt_bgl:
                # Source: IS 6403:1981 Cl. 5.1.2.4 (submerged overburden below water table)
                q_eff += g_sub * (z_bot - z_top)
            else:
                # Layer straddles the water table
                dz_above = wt_bgl - z_top
                dz_below = z_bot - wt_bgl
                # Source: IS 6403:1981 Cl. 5.1.2.4 (split overburden at water table)
                q_eff += g_moist * dz_above + g_sub * dz_below

        # Handle case where Df extends deeper than the bottom of the last defined layer
        max_layer_bot = max(float(lyr["depth_bot"]) for lyr in sorted_layers)
        if Df > max_layer_bot:
            last_lyr = sorted_layers[-1]
            g_moist = float(last_lyr.get("gamma_moist", gamma_moist))
            g_sub = float(last_lyr.get("gamma_sat", gamma_sat)) - GAMMA_W
            z_top = max_layer_bot
            if Df <= wt_bgl:
                q_eff += g_moist * (Df - z_top)
            elif z_top >= wt_bgl:
                q_eff += g_sub * (Df - z_top)
            else:
                q_eff += g_moist * (wt_bgl - z_top) + g_sub * (Df - wt_bgl)

        return max(q_eff, 0.0)

    # Single-layer fallback
    if wt_bgl >= Df:
        # Source: IS 6403:1981 Cl. 5.1.2.4
        return gamma_moist * Df
    # Source: IS 6403:1981 Cl. 5.1.2.4
    return gamma_moist * wt_bgl + (gamma_sat - GAMMA_W) * (Df - wt_bgl)


# ---------------------------------------------------------------------------
# 7. Shear Mode Parameters — IS 6403:1981 Cl. 5.2.1 & Cl. 5.2.2
# ---------------------------------------------------------------------------

def local_shear_params(c_prime: float, phi_prime_deg: float) -> Tuple[float, float]:
    """
    IS 6403:1981 Cl. 5.2.2 — Local shear failure modification.

    c_m   = (2/3) * c
    phi_m = arctan((2/3) * tan(phi))

    Parameters
    ----------
    c_prime : float
        Cohesion c (kPa).
    phi_prime_deg : float
        Friction angle φ (degrees).

    Returns
    -------
    (c_m, phi_m_deg) : tuple of float
    """
    # Source: IS 6403:1981 Cl. 5.2.2
    c_local = (2.0 / 3.0) * c_prime
    # Source: IS 6403:1981 Cl. 5.2.2
    phi_local_deg = math.degrees(math.atan((2.0 / 3.0) * math.tan(math.radians(phi_prime_deg))))
    return c_local, phi_local_deg


def _normalize_failure_mode(failure_mode: str) -> str:
    """Map UI/caller failure mode labels to 'auto', 'general', or 'local'."""
    mode = (failure_mode or "general").strip().lower()
    if "auto" in mode:
        return "auto"
    if "local" in mode:
        return "local"
    return "general"


def _compute_single_shear_mode(
    c_val: float,
    phi_val: float,
    gamma_moist: float,
    q_eff: float,
    Df: float,
    B: float,
    B_eff: float,
    L_eff: float,
    wt_bgl: float,
    footing_shape: str,
    is_eccentric: bool,
    alpha_deg: float,
    is_local: bool,
) -> Dict[str, object]:
    """Evaluate IS 6403:1981 Cl. 5.1.2 Eq. 1 for a single shear regime (general or local)."""
    if is_local:
        c_used, phi_used = local_shear_params(c_val, phi_val)
    else:
        c_used, phi_used = c_val, phi_val

    Nc, Nq, Ngamma = bearing_capacity_factors(phi_used)
    sc, sq, sgamma = shape_factors(
        B_eff, L_eff, phi_used, footing_shape=footing_shape, is_eccentric=is_eccentric
    )
    dc, dq, dgamma = depth_factors(Df, B, phi_used)
    ic, iq, igamma = inclination_factors(alpha_deg, phi_used)
    W_prime = water_table_factor(Df, B_eff, wt_bgl)

    # Source: IS 6403:1981 Cl. 5.1.2 Eq. 1 (net ultimate bearing capacity)
    c_term = c_used * Nc * sc * dc * ic
    # Source: IS 6403:1981 Cl. 5.1.2 Eq. 1 (overburden net term)
    q_term = q_eff * (Nq - 1.0) * sq * dq * iq
    # Source: IS 6403:1981 Cl. 5.1.2 Eq. 1 & Cl. 5.1.2.4 (self-weight term with W' and gamma_moist)
    gamma_term = 0.5 * B_eff * gamma_moist * Ngamma * sgamma * dgamma * igamma * W_prime
    # Source: IS 6403:1981 Cl. 5.1.2 Eq. 1
    q_nu = c_term + q_term + gamma_term

    return {
        "Nc": Nc,
        "Nq": Nq,
        "Ngamma": Ngamma,
        "sc": sc,
        "sq": sq,
        "sgamma": sgamma,
        "dc": dc,
        "dq": dq,
        "dgamma": dgamma,
        "ic": ic,
        "iq": iq,
        "igamma": igamma,
        "W_prime": W_prime,
        "c_used": c_used,
        "phi_used": phi_used,
        "c_term": c_term,
        "q_term": q_term,
        "gamma_term": gamma_term,
        "qnu": q_nu,
    }


# ---------------------------------------------------------------------------
# 8. Net Ultimate, Net Safe & Gross Safe Bearing Capacity
# ---------------------------------------------------------------------------

def net_ultimate_bearing_capacity(
    c_prime: float,
    phi_prime_deg: float,
    gamma_moist: float,
    gamma_sat: float,
    Df: float,
    B: float,
    L: float,
    wt_bgl: float,
    footing_shape: str = "square",
    failure_mode: str = "general",
    alpha_deg: float = 0.0,
    is_undrained: bool = False,
    cu: float = 0.0,
    ex: float = 0.0,
    ey: float = 0.0,
    FOS: float = 3.0,
    layers: Optional[List[Dict]] = None,
) -> Dict[str, object]:
    """
    IS 6403:1981 Cl. 5.1.2 — Net ultimate bearing capacity q_nu (kPa),
    net safe bearing capacity q_ns (kPa), and gross safe bearing capacity q_s_gross (kPa).

    q_nu = c*Nc*sc*dc*ic + q_eff*(Nq - 1)*sq*dq*iq + 0.5*B_eff*gamma_moist*Ngamma*sgamma*dgamma*igamma*W'

    Parameters
    ----------
    c_prime : float
        Drained cohesion c' (kPa). Ignored when is_undrained=True.
    phi_prime_deg : float
        Drained friction angle φ' (degrees). Ignored when is_undrained=True.
    gamma_moist : float
        Moist unit weight of bearing stratum (kN/m³).
    gamma_sat : float
        Saturated unit weight of bearing stratum (kN/m³).
    Df : float
        Founding depth below ground level (m).
    B : float
        Footing width or circular diameter (m).
    L : float
        Footing length (m). Set equal to B for square/circular; 1e6 for strip.
    wt_bgl : float
        Design water table depth below ground level (m).
    footing_shape : str
        "strip", "square", "rectangular", or "circular".
    failure_mode : str
        "auto" ("Auto (IS 6403 Cl. 5.2.1)"), "general" ("General Shear"),
        or "local" ("Local Shear").
    alpha_deg : float
        Resultant load inclination from vertical (degrees).
    is_undrained : bool
        If True, perform undrained (φ = 0, c = cu) analysis.
    cu : float
        Undrained shear strength (kPa). Used only when is_undrained=True.
    ex : float
        Eccentricity along B (m).
    ey : float
        Eccentricity along L (m).
    FOS : float
        Factor of safety on net ultimate bearing capacity (default 3.0).
    layers : list[dict] or None
        Optional soil layers (e.g. st.session_state.layers) used to integrate
        q_eff = σ'_v0(Df) across all overlying strata.

    Returns
    -------
    dict
        All factors, effective dimensions, kern check, q_nu / qnu, q_ns / qns,
        q_s_gross, qf, and resolved shear mode metadata.
    """
    shape = footing_shape.lower()
    if shape in ("square", "circular"):
        L_nom = B
    elif shape == "strip":
        L_nom = 1e6
    else:
        L_nom = L

    is_eccentric = (abs(ex) > 0.0) or (abs(ey) > 0.0)
    B_eff, L_eff, A_eff = effective_area(B, L_nom, ex=ex, ey=ey, footing_shape=shape)
    kern = kern_check(B, L_nom, ex=ex, ey=ey, footing_shape=shape)

    # Effective overburden q_eff = σ'_v0(Df) integrating all overlying layers
    q_eff = effective_overburden_at_depth(
        Df=Df,
        wt_bgl=wt_bgl,
        layers=layers,
        gamma_moist=gamma_moist,
        gamma_sat=gamma_sat,
    )

    # Select input strength parameters
    if is_undrained:
        c_in = float(cu)
        phi_in = 0.0
    else:
        c_in = float(c_prime)
        phi_in = float(phi_prime_deg)

    mode_norm = _normalize_failure_mode(failure_mode)

    # Determine shear regime per IS 6403:1981 Cl. 5.2.1 & Cl. 5.2.2
    if mode_norm == "general":
        resolved_mode = "General Shear"
        interp_t = 1.0
        comp = _compute_single_shear_mode(
            c_in, phi_in, gamma_moist, q_eff, Df, B, B_eff, L_eff,
            wt_bgl, shape, is_eccentric, alpha_deg, is_local=False,
        )
    elif mode_norm == "local":
        resolved_mode = "Local Shear"
        interp_t = 0.0
        comp = _compute_single_shear_mode(
            c_in, phi_in, gamma_moist, q_eff, Df, B, B_eff, L_eff,
            wt_bgl, shape, is_eccentric, alpha_deg, is_local=True,
        )
    else:
        # Source: IS 6403:1981 Cl. 5.2.1 (Auto shear mode selection based on phi)
        if phi_in == 0.0 or phi_in >= 36.0:
            resolved_mode = "General Shear (Auto)"
            interp_t = 1.0
            comp = _compute_single_shear_mode(
                c_in, phi_in, gamma_moist, q_eff, Df, B, B_eff, L_eff,
                wt_bgl, shape, is_eccentric, alpha_deg, is_local=False,
            )
        elif phi_in <= 28.0:
            resolved_mode = "Local Shear (Auto)"
            interp_t = 0.0
            comp = _compute_single_shear_mode(
                c_in, phi_in, gamma_moist, q_eff, Df, B, B_eff, L_eff,
                wt_bgl, shape, is_eccentric, alpha_deg, is_local=True,
            )
        else:
            # Source: IS 6403:1981 Cl. 5.2.1 (Linear interpolation between Local at 28° and General at 36°)
            interp_t = (phi_in - 28.0) / (36.0 - 28.0)
            resolved_mode = f"Interpolated (Auto, t = {interp_t:.2f})"
            res_loc = _compute_single_shear_mode(
                c_in, phi_in, gamma_moist, q_eff, Df, B, B_eff, L_eff,
                wt_bgl, shape, is_eccentric, alpha_deg, is_local=True,
            )
            res_gen = _compute_single_shear_mode(
                c_in, phi_in, gamma_moist, q_eff, Df, B, B_eff, L_eff,
                wt_bgl, shape, is_eccentric, alpha_deg, is_local=False,
            )
            comp = {}
            for key in res_loc:
                # Source: IS 6403:1981 Cl. 5.2.1 (linear transition interpolation)
                comp[key] = (1.0 - interp_t) * res_loc[key] + interp_t * res_gen[key]

    q_nu = float(comp["qnu"])
    # Source: IS 6403:1981 Cl. 6 (net safe bearing capacity)
    q_ns = net_safe_bearing_capacity(q_nu, FOS)
    # Source: IS 6403:1981 Cl. 6 (gross safe bearing capacity)
    q_s_gross = q_ns + q_eff
    # Source: IS 6403:1981 Cl. 5.1.2 (gross ultimate bearing capacity)
    qf = q_nu + q_eff

    return {
        **comp,
        "q_eff": q_eff,
        "gamma_moist": gamma_moist,
        "gamma_ngamma": gamma_moist,  # retained key for compatibility; W' handles WT reduction
        "qf": qf,
        "qnu": q_nu,
        "q_nu": q_nu,
        "qns": q_ns,
        "q_ns": q_ns,
        "q_s_gross": q_s_gross,
        "FOS": FOS,
        "B": B,
        "L": L_nom,
        "B_eff": B_eff,
        "L_eff": L_eff,
        "A_eff": A_eff,
        "ex": abs(ex),
        "ey": abs(ey),
        "is_eccentric": is_eccentric,
        "within_kern": kern["within_kern"],
        "kern_expression": kern["expression"],
        "kern_value": kern["metric_value"],
        "kern_limit": kern["limit_value"],
        "footing_shape": shape,
        "failure_mode": mode_norm,
        "resolved_mode": resolved_mode,
        "interpolation_t": interp_t,
    }


def net_safe_bearing_capacity(qnu: float, FOS: float = 3.0) -> float:
    """
    IS 6403:1981 Cl. 6 — Net safe bearing capacity.

    q_ns = q_nu / FOS
    """
    # Source: IS 6403:1981 Cl. 6
    return qnu / FOS


# ---------------------------------------------------------------------------
# 9. Required Footing Size (Iterative)
# ---------------------------------------------------------------------------

def required_footing_size(
    P_kN: float,
    c_prime: float,
    phi_prime_deg: float,
    gamma_moist: float,
    gamma_sat: float,
    Df: float,
    wt_bgl: float,
    FOS: float = 3.0,
    footing_shape: str = "square",
    failure_mode: str = "general",
    alpha_deg: float = 0.0,
    is_undrained: bool = False,
    cu: float = 0.0,
    n_iter: int = 12,
    layers: Optional[List[Dict]] = None,
    L_ratio: float = 1.5,
) -> Dict[str, float]:
    """
    IS 6403:1981 Cl. 6 — Iterative solution for required footing size.

    Parameters
    ----------
    P_kN : float
        Column service load (kN) — or kN/m for strip footing.
    L_ratio : float
        L / B aspect ratio used when footing_shape == "rectangular" (default 1.5).

    Returns
    -------
    dict with keys: B, L, qns, qnu, q_s_gross, actual_FOS
    """
    shape = footing_shape.lower()
    B = max(0.5, math.sqrt(P_kN / 150.0)) if shape != "strip" else max(0.5, P_kN / 150.0)

    for _ in range(n_iter):
        if shape in ("square", "circular"):
            L_iter = B
        elif shape == "strip":
            L_iter = 1e6
        else:
            L_iter = B * L_ratio

        res = net_ultimate_bearing_capacity(
            c_prime=c_prime,
            phi_prime_deg=phi_prime_deg,
            gamma_moist=gamma_moist,
            gamma_sat=gamma_sat,
            Df=Df,
            B=B,
            L=L_iter,
            wt_bgl=wt_bgl,
            footing_shape=shape,
            failure_mode=failure_mode,
            alpha_deg=alpha_deg,
            is_undrained=is_undrained,
            cu=cu,
            FOS=FOS,
            layers=layers,
        )
        qns = max(res["qnu"] / FOS, 1.0)
        if shape == "circular":
            # Source: Area = pi * B² / 4 >= P / qns
            B = math.sqrt((4.0 * P_kN) / (math.pi * qns))
        elif shape == "strip":
            B = P_kN / qns
        elif shape == "rectangular":
            B = math.sqrt(P_kN / (L_ratio * qns))
        else:
            B = math.sqrt(P_kN / qns)

    B_rounded = math.ceil(B / 0.05) * 0.05
    if shape in ("square", "circular"):
        L_final = B_rounded
    elif shape == "strip":
        L_final = 1e6
    else:
        L_final = math.ceil((B_rounded * L_ratio) / 0.05) * 0.05

    res_final = net_ultimate_bearing_capacity(
        c_prime=c_prime,
        phi_prime_deg=phi_prime_deg,
        gamma_moist=gamma_moist,
        gamma_sat=gamma_sat,
        Df=Df,
        B=B_rounded,
        L=L_final,
        wt_bgl=wt_bgl,
        footing_shape=shape,
        failure_mode=failure_mode,
        alpha_deg=alpha_deg,
        is_undrained=is_undrained,
        cu=cu,
        FOS=FOS,
        layers=layers,
    )
    qnu_final = float(res_final["qnu"])
    qns_final = qnu_final / FOS

    if shape == "circular":
        area = 0.25 * math.pi * (B_rounded ** 2)
    elif shape == "strip":
        area = B_rounded  # per metre run
    else:
        area = B_rounded * L_final

    applied_pressure = P_kN / area if area > 0.0 else float("inf")
    actual_FOS = qnu_final / applied_pressure if applied_pressure > 0.0 else float("inf")

    return {
        "B": B_rounded,
        "L": L_final,
        "qns": qns_final,
        "qnu": qnu_final,
        "q_s_gross": float(res_final["q_s_gross"]),
        "actual_FOS": actual_FOS,
    }
