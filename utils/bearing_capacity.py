"""
utils/bearing_capacity.py
IS 6403:1981 — Bearing Capacity of Shallow Foundations
All computations in SI units (kN, kPa, m).
"""

import numpy as np

GAMMA_W = 9.81  # kN/m³, unit weight of water


# ---------------------------------------------------------------------------
# 1. Bearing Capacity Factors
# ---------------------------------------------------------------------------

def bearing_capacity_factors(phi_deg: float):
    """
    IS 6403:1981 Cl. 5.1 / Table 1 — Bearing capacity factors Nc, Nq, Nγ.

    Nq  = exp(π · tan φ) · tan²(45 + φ/2)
    Nc  = (Nq - 1) · cot φ   for φ > 0°
          5.14                for φ = 0°  (Prandtl limit)
    Nγ  = 1.5 · (Nq - 1) · tan φ

    Parameters
    ----------
    phi_deg : float
        Drained (or mobilised) friction angle φ′ in degrees.

    Returns
    -------
    (Nc, Nq, Ngamma) : tuple of float
        Dimensionless bearing capacity factors per IS 6403:1981 Table 1.
    """
    phi_rad = np.radians(phi_deg)

    Nq = np.exp(np.pi * np.tan(phi_rad)) * np.tan(np.radians(45.0 + phi_deg / 2.0)) ** 2

    if phi_deg == 0.0:
        Nc = 5.14
    else:
        Nc = (Nq - 1.0) / np.tan(phi_rad)

    Ngamma = 1.5 * (Nq - 1.0) * np.tan(phi_rad)

    return Nc, Nq, Ngamma


# ---------------------------------------------------------------------------
# 2. Shape Factors
# ---------------------------------------------------------------------------

def shape_factors(B: float, L: float, phi_deg: float):
    """
    IS 6403:1981 Cl. 5.1 — Shape factors sc, sq, sγ.

    For φ > 10°:
        Kp = tan²(45 + φ/2)
        sc  = 1 + 0.2 · Kp · (B/L)
        sq  = sγ = 1 + 0.1 · Kp · (B/L)
    For φ ≤ 10°:
        sc  = 1 + 0.2 · (B/L)
        sq  = sγ = 1.0
    Strip footing (B/L → 0):
        sc = sq = sγ = 1.0

    Parameters
    ----------
    B : float
        Footing width (m).  Pass B = L for square/circular.
    L : float
        Footing length (m).  Pass a large value (e.g. 1e6) for strip.
    phi_deg : float
        Friction angle (degrees).

    Returns
    -------
    (sc, sq, sgamma) : tuple of float
    """
    if L <= 0 or L > 1e5:  # treat as strip
        return 1.0, 1.0, 1.0

    ratio = B / L  # always ≤ 1 for B ≤ L

    if phi_deg > 10.0:
        Kp = np.tan(np.radians(45.0 + phi_deg / 2.0)) ** 2
        sc = 1.0 + 0.2 * Kp * ratio
        sq = 1.0 + 0.1 * Kp * ratio
        sgamma = 1.0 + 0.1 * Kp * ratio
    else:
        sc = 1.0 + 0.2 * ratio
        sq = 1.0
        sgamma = 1.0

    return sc, sq, sgamma


# ---------------------------------------------------------------------------
# 3. Depth Factors
# ---------------------------------------------------------------------------

def depth_factors(Df: float, B: float, phi_deg: float):
    """
    IS 6403:1981 Cl. 5.1 — Depth factors dc, dq, dγ.

    For φ > 10°:
        Kp = tan²(45 + φ/2)
        dc  = 1 + 0.2 · √Kp · (Df/B)
        dq  = dγ = 1 + 0.1 · √Kp · (Df/B)
    For φ ≤ 10°:
        dc  = 1 + 0.2 · (Df/B)
        dq  = dγ = 1.0

    Parameters
    ----------
    Df : float
        Founding depth (m).
    B : float
        Footing width (m).
    phi_deg : float
        Friction angle (degrees).

    Returns
    -------
    (dc, dq, dgamma) : tuple of float
    """
    if B <= 0:
        return 1.0, 1.0, 1.0

    ratio = Df / B

    if phi_deg > 10.0:
        Kp = np.tan(np.radians(45.0 + phi_deg / 2.0)) ** 2
        sqrtKp = np.sqrt(Kp)
        dc = 1.0 + 0.2 * sqrtKp * ratio
        dq = 1.0 + 0.1 * sqrtKp * ratio
        dgamma = 1.0 + 0.1 * sqrtKp * ratio
    else:
        dc = 1.0 + 0.2 * ratio
        dq = 1.0
        dgamma = 1.0

    return dc, dq, dgamma


# ---------------------------------------------------------------------------
# 4. Inclination Factors
# ---------------------------------------------------------------------------

def inclination_factors(alpha_deg: float, phi_deg: float):
    """
    IS 6403:1981 Cl. 5.1 — Inclination factors ic, iq, iγ.

    alpha = inclination of the resultant load from vertical (degrees).

    ic = iq = (1 - alpha/90)²
    iγ      = (1 - alpha/φ)²    if φ > 0
              0.0                 if φ = 0 and alpha > 0

    For vertical load (alpha = 0): ic = iq = iγ = 1.0

    Parameters
    ----------
    alpha_deg : float
        Inclination of resultant load from vertical (degrees, 0–90).
    phi_deg : float
        Friction angle (degrees).

    Returns
    -------
    (ic, iq, igamma) : tuple of float
    """
    ic = (1.0 - alpha_deg / 90.0) ** 2
    iq = ic  # same per IS 6403:1981 Cl. 5.1

    if phi_deg > 0.0:
        igamma = (1.0 - alpha_deg / phi_deg) ** 2 if alpha_deg < phi_deg else 0.0
    else:
        igamma = 0.0 if alpha_deg > 0.0 else 1.0

    return ic, iq, igamma


# ---------------------------------------------------------------------------
# 5. Water Table Factor
# ---------------------------------------------------------------------------

def water_table_factor(Df: float, B: float, wt_bgl: float):
    """
    IS 6403:1981 Cl. 5.2 — Water table correction factor W′ for Nγ term.

    W′ applies to the Nγ term (self-weight of soil below the footing base).

    - wt_bgl ≤ Df           → WT at or above footing base → W′ = 0.5
    - wt_bgl ≥ Df + B       → WT deeper than B below base → W′ = 1.0
    - Df < wt_bgl < Df + B  → Linear interpolation:
      W′ = 0.5 + 0.5 · (wt_bgl - Df) / B

    Parameters
    ----------
    Df : float
        Founding depth (m bgl).
    B : float
        Footing width (m).
    wt_bgl : float
        Water table depth below ground level (m bgl).

    Returns
    -------
    W_prime : float
        Correction factor (0.5 ≤ W′ ≤ 1.0).
    """
    if wt_bgl <= Df:
        return 0.5
    elif wt_bgl >= Df + B:
        return 1.0
    else:
        return 0.5 + 0.5 * (wt_bgl - Df) / B


# ---------------------------------------------------------------------------
# 6. Local Shear Parameters
# ---------------------------------------------------------------------------

def local_shear_params(c_prime: float, phi_prime_deg: float):
    """
    IS 6403:1981 Cl. 5.3 — Local shear failure modification.

    Mobilised (reduced) strength parameters for local shear failure:
        c_local   = (2/3) · c′
        φ_local   = arctan((2/3) · tan φ′)

    Parameters
    ----------
    c_prime : float
        Drained cohesion (kPa).
    phi_prime_deg : float
        Drained friction angle (degrees).

    Returns
    -------
    (c_local_kPa, phi_local_deg) : tuple of float
    """
    c_local = (2.0 / 3.0) * c_prime
    phi_local_deg = np.degrees(np.arctan((2.0 / 3.0) * np.tan(np.radians(phi_prime_deg))))
    return c_local, phi_local_deg


# ---------------------------------------------------------------------------
# 7. Net Ultimate Bearing Capacity
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
    footing_shape: str = "square",   # "strip", "square", "rectangular", "circular"
    failure_mode: str = "general",   # "general", "local"
    alpha_deg: float = 0.0,          # inclination of load from vertical (degrees)
    is_undrained: bool = False,       # True → φ=0 cu analysis
    cu: float = 0.0,
):
    """
    IS 6403:1981 Cl. 5.1 — Net ultimate bearing capacity qnu (kPa).

    General bearing capacity equation (IS 6403:1981 Cl. 5.1):
        qf  = c · Nc · sc · dc · ic
            + q · Nq · sq · dq · iq
            + 0.5 · γ · B · Nγ · sγ · dγ · iγ · W′

    For undrained φ=0 (cu analysis):
        qf  = cu · Nc · sc · dc + q       [Nq = 1, Nγ = 0]
        qnu = cu · Nc · sc · dc           (net)

    Effective overburden at founding level:
        q = γ_moist · Df                              if wt_bgl ≥ Df
        q = γ_moist · wt_bgl + (γ_sat − γw)·(Df − wt_bgl)   if wt_bgl < Df

    Net ultimate bearing capacity:
        qnu = qf − q  (gross ultimate minus overburden)
        For undrained case: qnu = cu · Nc · sc · dc

    Local shear: parameters reduced per IS 6403:1981 Cl. 5.3 before computation.

    Parameters
    ----------
    c_prime : float
        Drained cohesion c′ (kPa).  Ignored when is_undrained=True.
    phi_prime_deg : float
        Drained friction angle φ′ (degrees).  Ignored when is_undrained=True.
    gamma_moist : float
        Moist unit weight above WT (kN/m³).
    gamma_sat : float
        Saturated unit weight (kN/m³).
    Df : float
        Founding depth below GL (m).
    B : float
        Footing width (m).
    L : float
        Footing length (m).  Set equal to B for square/circular; large (1e6) for strip.
    wt_bgl : float
        Water table depth below GL (m).
    footing_shape : str
        One of "strip", "square", "rectangular", "circular".
    failure_mode : str
        "general" or "local".
    alpha_deg : float
        Load inclination from vertical (degrees).
    is_undrained : bool
        If True, perform undrained (φ=0, cu) analysis.
    cu : float
        Undrained shear strength (kPa).  Used only when is_undrained=True.

    Returns
    -------
    result : dict
        Dictionary with keys:
            Nc, Nq, Ngamma, sc, sq, sgamma, dc, dq, dgamma,
            ic, iq, igamma, W_prime, q_eff, qf, qnu,
            c_used, phi_used, B, L, footing_shape, failure_mode
    """
    # --- Adjust L for square/circular/strip ---------------------------------
    if footing_shape in ("square", "circular"):
        L = B
    elif footing_shape == "strip":
        L = 1e6  # effectively infinite

    # --- Undrained vs drained parameters ------------------------------------
    if is_undrained:
        c_used = cu
        phi_used = 0.0
    else:
        c_used = c_prime
        phi_used = phi_prime_deg

    # --- Local shear reduction (IS 6403:1981 Cl. 5.3) ----------------------
    if failure_mode == "local":
        c_used, phi_used = local_shear_params(c_used, phi_used)

    # --- Bearing capacity factors -------------------------------------------
    Nc, Nq, Ngamma = bearing_capacity_factors(phi_used)

    # --- Effective overburden at founding level (Nq term) -------------------
    if wt_bgl >= Df:
        q_eff = gamma_moist * Df
    else:
        q_eff = gamma_moist * wt_bgl + (gamma_sat - GAMMA_W) * (Df - wt_bgl)

    # --- Effective unit weight for Nγ term (below footing) ------------------
    W_prime = water_table_factor(Df, B, wt_bgl)

    # Effective γ below footing base for Nγ term
    if wt_bgl <= Df:
        gamma_eff = gamma_sat - GAMMA_W   # fully submerged below footing
    else:
        gamma_eff = gamma_moist            # WT deeper than footing base

    # Apply W′ correction to the Nγ term: use W′ · gamma_eff
    # (W′ already encodes interpolation; use directly with moist/sat)
    # Per IS 6403:1981 Cl. 5.2: replace γ in Nγ term with
    #   W′ · γ_moist + (1 - W′) · (γ_sat - γw) when WT between Df and Df+B
    # Simplified: effective γ for Nγ term = (1 - W′)·(γ_sat - γw) + W′·γ_moist
    gamma_ngamma = (1.0 - W_prime) * (gamma_sat - GAMMA_W) + W_prime * gamma_moist

    # --- Shape, depth, inclination factors ----------------------------------
    sc, sq, sgamma = shape_factors(B, L, phi_used)
    dc, dq, dgamma = depth_factors(Df, B, phi_used)
    ic, iq, igamma = inclination_factors(alpha_deg, phi_used)

    # --- Gross ultimate bearing capacity (IS 6403:1981 Eq. 1) ---------------
    if is_undrained and phi_used == 0.0:
        # φ=0: Nq=1, Nγ=0 (Skempton / IS 6403 for undrained)
        qf = c_used * Nc * sc * dc * ic + q_eff * 1.0
        qnu = c_used * Nc * sc * dc * ic   # net (subtract q)
        # Override Nq and Ngamma for display
        Nq_disp, Ngamma_disp = 1.0, 0.0
    else:
        c_term     = c_used     * Nc     * sc     * dc     * ic
        q_term     = q_eff      * Nq     * sq     * dq     * iq
        gamma_term = 0.5 * gamma_ngamma * B * Ngamma * sgamma * dgamma * igamma
        qf = c_term + q_term + gamma_term
        qnu = qf - q_eff
        Nq_disp, Ngamma_disp = Nq, Ngamma

    return {
        "Nc": Nc,
        "Nq": Nq_disp if (is_undrained and phi_used == 0.0) else Nq,
        "Ngamma": Ngamma_disp if (is_undrained and phi_used == 0.0) else Ngamma,
        "sc": sc, "sq": sq, "sgamma": sgamma,
        "dc": dc, "dq": dq, "dgamma": dgamma,
        "ic": ic, "iq": iq, "igamma": igamma,
        "W_prime": W_prime,
        "q_eff": q_eff,
        "gamma_ngamma": gamma_ngamma,
        "qf": qf,
        "qnu": qnu,
        "c_used": c_used,
        "phi_used": phi_used,
        "B": B,
        "L": L if footing_shape not in ("square", "circular", "strip") else B,
        "footing_shape": footing_shape,
        "failure_mode": failure_mode,
    }


# ---------------------------------------------------------------------------
# 8. Net Safe Bearing Capacity
# ---------------------------------------------------------------------------

def net_safe_bearing_capacity(qnu: float, FOS: float = 3.0):
    """
    IS 6403:1981 Cl. 6 — Net safe bearing capacity.

    qns = qnu / FOS

    Parameters
    ----------
    qnu : float
        Net ultimate bearing capacity (kPa).
    FOS : float
        Factor of safety (default 3.0 per IS 6403:1981 Cl. 6).

    Returns
    -------
    qns : float
        Net safe bearing capacity (kPa).
    """
    return qnu / FOS


# ---------------------------------------------------------------------------
# 9. Effective Area (Eccentric Loading)
# ---------------------------------------------------------------------------

def effective_area(B: float, L: float, ex: float, ey: float):
    """
    IS 6403:1981 Cl. 5.4 — Effective dimensions for eccentric loading.

    B_eff = B − 2 · ex   (eccentricity along short dimension B)
    L_eff = L − 2 · ey   (eccentricity along long dimension L)
    A_eff = B_eff × L_eff

    Parameters
    ----------
    B : float
        Footing width (m).
    L : float
        Footing length (m).
    ex : float
        Eccentricity along B (m).
    ey : float
        Eccentricity along L (m).

    Returns
    -------
    (B_eff, L_eff, A_eff) : tuple of float
        Effective dimensions (m, m, m²).
    """
    B_eff = B - 2.0 * ex
    L_eff = L - 2.0 * ey
    A_eff = B_eff * L_eff
    return B_eff, L_eff, A_eff


# ---------------------------------------------------------------------------
# 10. Required Footing Size (Iterative)
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
    n_iter: int = 10,
):
    """
    IS 6403:1981 Cl. 6 — Iterative solution for required footing size.

    For a square footing under axial load P (kN):
        First estimate: B = √(P / qns)
        qns depends on B → iterate n_iter times until convergence.

    Algorithm
    ----------
    1. Start with B = 1.0 m.
    2. Compute qnu → qns = qnu / FOS.
    3. Update B = √(P / qns).
    4. Repeat for n_iter iterations.
    5. Round B up to nearest 0.05 m.

    Parameters
    ----------
    P_kN : float
        Column (service) load (kN).
    c_prime, phi_prime_deg, gamma_moist, gamma_sat : float
        Soil parameters at founding level.
    Df : float
        Founding depth (m).
    wt_bgl : float
        Water table depth (m bgl).
    FOS : float
        Factor of safety (default 3.0).
    footing_shape : str
        "square", "rectangular", "circular", "strip".
    failure_mode : str
        "general" or "local".
    alpha_deg : float
        Load inclination (degrees).
    is_undrained : bool
        True → undrained analysis.
    cu : float
        Undrained shear strength (kPa).
    n_iter : int
        Number of iterations (default 10).

    Returns
    -------
    result : dict
        {
          "B": float,          # required width (m), rounded up to 0.05 m
          "L": float,          # same as B for square footing
          "qns": float,        # net safe bearing capacity (kPa) at final B
          "qnu": float,        # net ultimate bearing capacity (kPa)
          "actual_FOS": float, # qnu / (P / B²) — actual FOS
        }
    """
    B = max(1.0, np.sqrt(P_kN / 150.0))  # first guess using 150 kPa as seed

    for _ in range(n_iter):
        L_iter = B if footing_shape in ("square", "circular") else B * 1.5
        res = net_ultimate_bearing_capacity(
            c_prime=c_prime, phi_prime_deg=phi_prime_deg,
            gamma_moist=gamma_moist, gamma_sat=gamma_sat,
            Df=Df, B=B, L=L_iter, wt_bgl=wt_bgl,
            footing_shape=footing_shape,
            failure_mode=failure_mode,
            alpha_deg=alpha_deg,
            is_undrained=is_undrained,
            cu=cu,
        )
        qnu = res["qnu"]
        qns = max(qnu / FOS, 1.0)   # avoid division by zero
        B_new = np.sqrt(P_kN / qns)
        B = B_new

    # Round up to nearest 0.05 m
    B_rounded = np.ceil(B / 0.05) * 0.05
    L_final = B_rounded

    # Final check with rounded B
    res_final = net_ultimate_bearing_capacity(
        c_prime=c_prime, phi_prime_deg=phi_prime_deg,
        gamma_moist=gamma_moist, gamma_sat=gamma_sat,
        Df=Df, B=B_rounded, L=L_final, wt_bgl=wt_bgl,
        footing_shape=footing_shape,
        failure_mode=failure_mode,
        alpha_deg=alpha_deg,
        is_undrained=is_undrained,
        cu=cu,
    )
    qnu_final = res_final["qnu"]
    qns_final = qnu_final / FOS

    # Actual FOS = qnu / applied net pressure
    applied_pressure = P_kN / (B_rounded ** 2)
    actual_FOS = qnu_final / applied_pressure if applied_pressure > 0 else float("inf")

    return {
        "B": B_rounded,
        "L": L_final,
        "qns": qns_final,
        "qnu": qnu_final,
        "actual_FOS": actual_FOS,
    }
