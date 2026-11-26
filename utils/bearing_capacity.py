"""
utils/bearing_capacity.py
IS 6403:1981 — Bearing Capacity of Shallow Foundations
All computations in SI units (kN, kPa, m).
"""

import numpy as np

GAMMA_W = 9.81  # kN/m³, unit weight of water
STRIP_LENGTH_EQUIV = 1e6  # m, effectively infinite length for strip footings
DEPTH_EPS = 1e-9  # m, floating-point tolerance for depth boundaries


# ---------------------------------------------------------------------------
# 1. Bearing Capacity Factors
# ---------------------------------------------------------------------------

def bearing_capacity_factors(phi_deg: float):
    """
    IS 6403:1981 Cl. 5.1 / Table 1 — Bearing capacity factors Nc, Nq, Nγ.

    Nq  = exp(π · tan φ) · tan²(45 + φ/2)
    Nc  = (Nq - 1) · cot φ   for φ > 0°
          5.14                for φ = 0°  (Prandtl limit)
    Nγ  = 2 · (Nq + 1) · tan φ

    Parameters
    ----------
    phi_deg : float
        Drained (or mobilised) friction angle φ′ in degrees.

    Returns
    -------
    (Nc, Nq, Ngamma) : tuple of float
        Dimensionless bearing capacity factors per IS 6403:1981 Table 1.
    """
    if phi_deg < 0.0:
        raise ValueError(f"Friction angle phi_deg must be non-negative, got {phi_deg}")

    phi_rad = np.radians(phi_deg)
    Nq = np.exp(np.pi * np.tan(phi_rad)) * np.tan(np.radians(45.0 + phi_deg / 2.0)) ** 2

    if np.isclose(phi_deg, 0.0):
        Nc = 5.14
    else:
        Nc = (Nq - 1.0) / np.tan(phi_rad)

    Ngamma = 2.0 * (Nq + 1.0) * np.tan(phi_rad)

    return Nc, Nq, Ngamma


# ---------------------------------------------------------------------------
# 2. Shape Factors
# ---------------------------------------------------------------------------

def shape_factors(footing_shape: str, B: float, L: float):
    """
    IS 6403:1981 Cl. 5.1 — Shape factors sc, sq, sγ.

    Table 2 values:
      strip:      sc=sq=sγ=1
      rectangle:  sc=sq=1+0.2(B/L), sγ=1-0.4(B/L)
      square:     sc=1.3, sq=1.2, sγ=0.8
      circle:     sc=1.3, sq=1.2, sγ=0.6

    Parameters
    ----------
    footing_shape : str
        "strip", "square", "rectangular", or "circular".
    B : float
        Footing width or diameter (m).
    L : float
        Footing length (m). Pass a large value (e.g. STRIP_LENGTH_EQUIV) for strip.

    Returns
    -------
    (sc, sq, sgamma) : tuple of float
    """
    shape = footing_shape.lower()
    if shape not in {"strip", "square", "rectangular", "circular"}:
        raise ValueError(f"Unsupported footing shape: {footing_shape}")
    if B <= 0 or L <= 0:
        raise ValueError("Footing dimensions B and L must be positive.")
    if shape == "strip" or L >= STRIP_LENGTH_EQUIV:
        return 1.0, 1.0, 1.0
    if shape == "square":
        return 1.3, 1.2, 0.8
    if shape == "circular":
        return 1.3, 1.2, 0.6

    # For a rectangle, B is the shorter footing dimension per IS 6403.
    ratio = min(B, L) / max(B, L)
    return 1.0 + 0.2 * ratio, 1.0 + 0.2 * ratio, 1.0 - 0.4 * ratio


# ---------------------------------------------------------------------------
# 3. Depth Factors
# ---------------------------------------------------------------------------

def depth_factors(Df: float, B: float, phi_deg: float):
    """
    IS 6403:1981 Cl. 5.1.2.1 — Depth factors dc, dq, dγ.

    √Nφ = tan(45° + φ/2)
    dc  = 1 + 0.2 · √Nφ · (Df/B)         for all φ
    dq  = dγ = 1 + 0.1 · √Nφ · (Df/B)    for φ > 10°
    dq  = dγ = 1.0                        for φ ≤ 10°
    """
    if B <= 0:
        return 1.0, 1.0, 1.0

    ratio = Df / B
    sqrtKp = np.tan(np.radians(45.0 + phi_deg / 2.0))
    dc = 1.0 + 0.2 * sqrtKp * ratio

    if phi_deg > 10.0:
        dq = 1.0 + 0.1 * sqrtKp * ratio
        dgamma = dq
    else:
        dq = 1.0
        dgamma = 1.0

    return dc, dq, dgamma


# ---------------------------------------------------------------------------
# 4. Inclination Factors
# ---------------------------------------------------------------------------

def inclination_factors(alpha_deg: float, phi_deg: float):
    if not (0.0 <= alpha_deg <= 90.0):
        raise ValueError(f"Load inclination alpha_deg must be in [0, 90], got {alpha_deg}")
    if phi_deg < 0.0:
        raise ValueError(f"Friction angle phi_deg must be non-negative, got {phi_deg}")

    ic = (1.0 - alpha_deg / 90.0) ** 2
    iq = ic

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
    Cl. 5.1.2.3 in IS 6403:1981 — Water table correction factor W′ for Nγ term.

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
    if B <= 0:
        raise ValueError("Footing width B must be positive.")
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
    Cl. 5.1.3 in IS 6403:1981 — Local shear failure modification.

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
# 6b. Stratified Effective Overburden Pressure
# ---------------------------------------------------------------------------

def effective_overburden_pressure(
    layers: list[dict] | None,
    Df: float,
    wt_bgl: float,
    gamma_w: float = GAMMA_W,
    fallback_gamma_moist: float | None = None,
    fallback_gamma_sat: float | None = None,
) -> tuple[float, list[str]]:
    """
    Integrate effective vertical overburden stress q_eff from ground level (0 m)
    to founding depth Df (m), splitting layers at the design water table wt_bgl.

    Parameters
    ----------
    layers : list of dict or None
        Soil layer dicts containing 'depth_top', 'depth_bot', 'gamma_moist',
        'gamma_sat', and optionally 'symbol' / 'name'.
    Df : float
        Founding depth below ground level (m).
    wt_bgl : float
        Design water table depth below ground level (m).
    gamma_w : float
        Unit weight of water (kN/m³), defaults to GAMMA_W.
    fallback_gamma_moist : float or None
        Used only if layers is empty/None or a layer omits 'gamma_moist'.
    fallback_gamma_sat : float or None
        Used only if layers is empty/None or a layer omits 'gamma_sat'.

    Returns
    -------
    (q_eff, breakdown) : tuple[float, list[str]]
        Effective surcharge q_eff (kPa) and step-by-step calculation breakdown.
    """
    if Df < 0.0:
        raise ValueError(f"Founding depth Df must be non-negative, got {Df}")
    if np.isclose(Df, 0.0):
        return 0.0, ["Df = 0.00 m → q = 0.00 kPa"]

    wt_eff = max(0.0, float(wt_bgl))

    if not layers:
        if fallback_gamma_moist is None or fallback_gamma_sat is None:
            raise ValueError(
                "No soil layers provided and fallback unit weights were not specified."
            )
        if wt_eff >= Df:
            q_eff = fallback_gamma_moist * Df
            return q_eff, [
                f"0.00–{Df:.2f} m (moist): {fallback_gamma_moist:.2f} × {Df:.2f} = {q_eff:.2f} kPa"
            ]
        q_above = fallback_gamma_moist * wt_eff
        q_below = (fallback_gamma_sat - gamma_w) * (Df - wt_eff)
        steps = []
        if wt_eff > DEPTH_EPS:
            steps.append(
                f"0.00–{wt_eff:.2f} m (moist): {fallback_gamma_moist:.2f} × {wt_eff:.2f} = {q_above:.2f} kPa"
            )
        steps.append(
            f"{wt_eff:.2f}–{Df:.2f} m (sub): ({fallback_gamma_sat:.2f} − {gamma_w:.2f}) × {Df - wt_eff:.2f} = {q_below:.2f} kPa"
        )
        return q_above + q_below, steps

    sorted_layers = sorted(layers, key=lambda lyr: float(lyr["depth_top"]))
    q_eff = 0.0
    breakdown: list[str] = []
    cursor = 0.0

    for idx, lyr in enumerate(sorted_layers):
        if cursor >= Df - DEPTH_EPS:
            break

        lyr_top = float(lyr["depth_top"])
        lyr_bot = float(lyr["depth_bot"])

        # Extend final layer down to Df if Df lies below the bottom of the defined profile
        if idx == len(sorted_layers) - 1 and lyr_bot < Df:
            lyr_bot = Df

        seg_top = max(cursor, lyr_top)
        seg_bot = min(lyr_bot, Df)
        if seg_bot <= seg_top + DEPTH_EPS:
            continue

        raw_moist = lyr.get("gamma_moist", fallback_gamma_moist)
        raw_sat = lyr.get("gamma_sat", fallback_gamma_sat)
        if raw_moist is None or raw_sat is None:
            raise ValueError(f"Layer {idx + 1} is missing 'gamma_moist' or 'gamma_sat'.")

        g_moist = float(raw_moist)
        g_sat = float(raw_sat)
        label = lyr.get("symbol") or lyr.get("name") or f"Layer {idx + 1}"

        if wt_eff <= seg_top + DEPTH_EPS:
            dz = seg_bot - seg_top
            dq = (g_sat - gamma_w) * dz
            q_eff += dq
            breakdown.append(
                f"{seg_top:.2f}–{seg_bot:.2f} m [{label}, sub]: "
                f"({g_sat:.2f} − {gamma_w:.2f}) × {dz:.2f} = {dq:.2f} kPa"
            )
        elif wt_eff >= seg_bot - DEPTH_EPS:
            dz = seg_bot - seg_top
            dq = g_moist * dz
            q_eff += dq
            breakdown.append(
                f"{seg_top:.2f}–{seg_bot:.2f} m [{label}, moist]: "
                f"{g_moist:.2f} × {dz:.2f} = {dq:.2f} kPa"
            )
        else:
            dz_above = wt_eff - seg_top
            dq_above = g_moist * dz_above
            dz_below = seg_bot - wt_eff
            dq_below = (g_sat - gamma_w) * dz_below
            q_eff += dq_above + dq_below
            breakdown.append(
                f"{seg_top:.2f}–{wt_eff:.2f} m [{label}, moist]: "
                f"{g_moist:.2f} × {dz_above:.2f} = {dq_above:.2f} kPa"
            )
            breakdown.append(
                f"{wt_eff:.2f}–{seg_bot:.2f} m [{label}, sub]: "
                f"({g_sat:.2f} − {gamma_w:.2f}) × {dz_below:.2f} = {dq_below:.2f} kPa"
            )

        cursor = seg_bot

    return q_eff, breakdown


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
    layers: list[dict] | None = None,
    q_eff_override: float | None = None,
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
        Integrated across `layers` from 0 to Df (splitting at wt_bgl) when
        `layers` is provided; otherwise computed from homogeneous `gamma_moist`
        and `gamma_sat`. Can also be supplied directly via `q_eff_override`.

    Net ultimate bearing capacity:
        qnu = qf − q  (gross ultimate minus overburden)
        For undrained case: qnu = cu · Nc · sc · dc

    Local shear: parameters reduced per IS 6403:1981 Cl. 5.3 before computation.
    """
    # --- Adjust L for square/circular/strip ---------------------------------
    if footing_shape in ("square", "circular"):
        L = B
    elif footing_shape == "strip":
        L = STRIP_LENGTH_EQUIV
    elif footing_shape == "rectangular" and L < B:
        # IS 6403 uses B as the shorter dimension for rectangular footings.
        B, L = L, B

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

    # --- Effective overburden at founding level (IS 6403 Cl. 5.1.2) ---------
    wt_eff = max(0.0, wt_bgl)
    if q_eff_override is not None:
        q_eff = float(q_eff_override)
    else:
        q_eff, _ = effective_overburden_pressure(
            layers=layers,
            Df=Df,
            wt_bgl=wt_eff,
            fallback_gamma_moist=gamma_moist,
            fallback_gamma_sat=gamma_sat,
        )

    # --- Water table correction factor W' (IS 6403 Cl. 5.1.2.3) -------------
    W_prime = water_table_factor(Df, B, wt_eff)

    # --- Shape, depth, inclination factors (IS 6403 Table 2 & Cl. 5.1.2.1) --
    sc, sq, sgamma = shape_factors(footing_shape, B, L)
    dc, dq, dgamma = depth_factors(Df, B, phi_used)
    ic, iq, igamma = inclination_factors(alpha_deg, phi_used)

    # --- Net & Gross ultimate bearing capacity (IS 6403:1981 Cl. 5.1.2) -----
    if is_undrained and np.isclose(phi_used, 0.0):
        qnu = c_used * Nc * sc * dc * ic
        qf = qnu + q_eff
        Nq_disp, Ngamma_disp = 1.0, 0.0
    else:
        c_term     = c_used * Nc * sc * dc * ic
        q_term     = q_eff * (Nq - 1.0) * sq * dq * iq
        gamma_term = 0.5 * gamma_moist * B * Ngamma * sgamma * dgamma * igamma * W_prime
        qnu = c_term + q_term + gamma_term
        qf = qnu + q_eff
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
        # Effective coefficient multiplying Nγ after applying W′.
        "gamma_ngamma": gamma_moist * W_prime,
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
    IS 6403:1981 Cl. 5.0.1 — Effective dimensions for eccentric loading.

    B_eff = B − 2 · |ex|   (eccentricity along width B)
    L_eff = L − 2 · |ey|   (eccentricity along length L)
    A_eff = B_eff × L_eff
    """
    if B <= 0 or L <= 0:
        raise ValueError("Footing dimensions B and L must be positive.")

    B_eff = B - 2.0 * abs(ex)
    L_eff = L - 2.0 * abs(ey)

    if B_eff <= 0 or L_eff <= 0:
        raise ValueError(
            f"Eccentricity exceeds footing bounds (|ex| >= B/2 or |ey| >= L/2): "
            f"B_eff={B_eff:.3f}, L_eff={L_eff:.3f}"
        )

    # Ensure B_eff <= L_eff for downstream shape/depth/Ngamma terms
    B_eff, L_eff = min(B_eff, L_eff), max(B_eff, L_eff)
    A_eff = B_eff * L_eff

    return B_eff, L_eff, A_eff


# ---------------------------------------------------------------------------
# 10. Footing Size
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
    aspect_ratio: float = 1.5,       # L/B for rectangular footings
    failure_mode: str = "general",
    alpha_deg: float = 0.0,
    is_undrained: bool = False,
    cu: float = 0.0,
    max_iter: int = 50,
    tol: float = 1e-4,
    layers: list[dict] | None = None,
    q_eff_override: float | None = None,
    width_step: float = 0.05,
):
    """Iterative solution for required footing width B (and length L) per IS 6403:1981.
    Note: For 'strip' footings, P_kN is interpreted as load per unit length (kN/m).
    """
    if P_kN <= 0 or FOS <= 0:
        raise ValueError("Load P_kN and FOS must be positive.")

    shape = footing_shape.lower()
    if shape not in ("square", "circular", "rectangular", "strip"):
        raise ValueError(f"Unsupported footing_shape: {footing_shape}")

    def _area(b, l):
        if shape == "circular":
            return 0.25 * np.pi * b ** 2
        elif shape == "strip":
            return b  # per unit length (m²/m)
        return b * l

    def _width_from_qns(qns):
        if shape == "square":
            return np.sqrt(P_kN / qns)
        elif shape == "circular":
            return np.sqrt(4.0 * P_kN / (np.pi * qns))
        elif shape == "rectangular":
            return np.sqrt(P_kN / (aspect_ratio * qns))
        else:  # strip (P_kN in kN/m)
            return P_kN / qns

    def _length_from_B(b):
        if shape in ("square", "circular"):
            return b
        elif shape == "rectangular":
            return aspect_ratio * b
        return STRIP_LENGTH_EQUIV

    # Compute initial qnu at B = 1.0 m so the initial trial width scales dynamically
    B_init = 1.0
    res_init = net_ultimate_bearing_capacity(
        c_prime=c_prime, phi_prime_deg=phi_prime_deg,
        gamma_moist=gamma_moist, gamma_sat=gamma_sat,
        Df=Df, B=B_init, L=_length_from_B(B_init), wt_bgl=wt_bgl,
        footing_shape=shape, failure_mode=failure_mode,
        alpha_deg=alpha_deg, is_undrained=is_undrained, cu=cu,
        layers=layers, q_eff_override=q_eff_override,
    )
    qns_init = max(res_init["qnu"] / FOS, tol)
    B = max(B_init, _width_from_qns(qns_init))

    for _ in range(max_iter):
        L_iter = _length_from_B(B)
        res = net_ultimate_bearing_capacity(
            c_prime=c_prime, phi_prime_deg=phi_prime_deg,
            gamma_moist=gamma_moist, gamma_sat=gamma_sat,
            Df=Df, B=B, L=L_iter, wt_bgl=wt_bgl,
            footing_shape=shape, failure_mode=failure_mode,
            alpha_deg=alpha_deg, is_undrained=is_undrained, cu=cu,
            layers=layers, q_eff_override=q_eff_override,
        )
        qnu = res["qnu"]
        if qnu <= 0:
            raise ValueError(f"Non-positive bearing capacity (qnu={qnu:.2f} kPa); footing cannot be sized.")

        qns = qnu / FOS
        B_new = _width_from_qns(qns)
        if abs(B_new - B) < tol:
            B = B_new
            break
        B = B_new

    # Round up to nearest width increment
    B_rounded = float(np.ceil(B / width_step) * width_step)
    L_final = _length_from_B(B_rounded)

    res_final = net_ultimate_bearing_capacity(
        c_prime=c_prime, phi_prime_deg=phi_prime_deg,
        gamma_moist=gamma_moist, gamma_sat=gamma_sat,
        Df=Df, B=B_rounded, L=L_final, wt_bgl=wt_bgl,
        footing_shape=shape, failure_mode=failure_mode,
        alpha_deg=alpha_deg, is_undrained=is_undrained, cu=cu,
        layers=layers, q_eff_override=q_eff_override,
    )
    qnu_final = res_final["qnu"]
    qns_final = qnu_final / FOS
    applied_pressure = P_kN / _area(B_rounded, L_final)
    actual_FOS = qnu_final / applied_pressure

    return {
        "B": B_rounded,
        "L": L_final,
        "qns": qns_final,
        "qnu": qnu_final,
        "actual_FOS": actual_FOS,
    }
