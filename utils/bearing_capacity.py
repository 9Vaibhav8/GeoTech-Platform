"""
utils/bearing_capacity.py
IS 6403:1981 — Bearing Capacity of Shallow Foundations
All computations in SI units (kN, kPa, m).
"""

import numpy as np

GAMMA_W = 9.81  # kN/m³, unit weight of water
STRIP_LENGTH_EQUIV = 1e6  # m, effectively infinite length for strip footings
DEPTH_EPS = 1e-9  # m, floating-point tolerance for depth boundaries


def _finite(value, name, *, minimum=None, strict=False):
    """Return a finite numeric value or raise an actionable input error."""
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric.") from exc
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    if minimum is not None and (value < minimum or (strict and value == minimum)):
        operator = ">" if strict else ">="
        raise ValueError(f"{name} must be {operator} {minimum}.")
    return value


def _friction_angle(value):
    value = _finite(value, "Friction angle", minimum=0.0)
    if value >= 90.0:
        raise ValueError("Friction angle must be below 90 degrees.")
    return value


def _unit_weights(moist, sat, gamma_w=GAMMA_W):
    moist = _finite(moist, "Moist unit weight", minimum=0.0, strict=True)
    sat = _finite(sat, "Saturated unit weight", minimum=gamma_w, strict=True)
    if sat < moist:
        raise ValueError("Saturated unit weight cannot be below moist unit weight.")
    return moist, sat


def validate_profile(layers, required_depth=None):
    """Return depth-sorted layers, rejecting gaps, overlaps and invalid depths.

    Does not mutate the input. Depths are in m below ground level. A supplied
    profile must start at ground level and cover required_depth, if specified.
    """
    if not layers:
        raise ValueError("No soil layers defined. Enter a soil profile first.")
    for i, layer in enumerate(layers, 1):
        if not isinstance(layer, dict):
            raise ValueError(f"Layer {i} must be a dictionary.")
        top = _finite(layer.get("depth_top"), f"Layer {i} top depth", minimum=0.0)
        bot = _finite(layer.get("depth_bot"), f"Layer {i} bottom depth", minimum=0.0)
        if bot - top <= DEPTH_EPS:
            raise ValueError(f"Layer {i}: bottom depth must exceed top depth.")
    ordered = sorted(layers, key=lambda layer: float(layer["depth_top"]))
    cursor = 0.0
    for i, layer in enumerate(ordered, 1):
        top = float(layer["depth_top"])
        if abs(top - cursor) > DEPTH_EPS:
            kind = "Gap" if top > cursor else "Overlap"
            raise ValueError(f"{kind} before layer {i}: expected top {cursor:g} m, got {top:g} m.")
        cursor = float(layer["depth_bot"])
    if required_depth is not None:
        required_depth = _finite(required_depth, "Required depth", minimum=0.0)
        if required_depth > cursor + DEPTH_EPS:
            raise ValueError(f"Profile ends at {cursor:g} m; required depth is {required_depth:g} m. Extend the profile explicitly.")
    return ordered


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
    phi_deg = _friction_angle(phi_deg)
    if phi_deg == 0.0:
        return 5.14, 1.0, 0.0

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
    B = _finite(B, "Width B", minimum=0.0, strict=True)
    L = _finite(L, "Length L", minimum=0.0, strict=True)
    if shape == "strip":
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
    B = _finite(B, "Width B", minimum=0.0, strict=True)
    Df = _finite(Df, "Founding depth", minimum=0.0)
    phi_deg = _friction_angle(phi_deg)

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
    alpha_deg = _finite(alpha_deg, "Load inclination")
    phi_deg = _friction_angle(phi_deg)
    if not (0.0 <= alpha_deg <= 90.0):
        raise ValueError(f"Load inclination alpha_deg must be in [0, 90], got {alpha_deg}")
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
    B = _finite(B, "Width B", minimum=0.0, strict=True)
    Df = _finite(Df, "Founding depth", minimum=0.0)
    wt_bgl = _finite(wt_bgl, "Water-table depth", minimum=0.0)
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
    c_prime = _finite(c_prime, "Cohesion", minimum=0.0)
    phi_prime_deg = _friction_angle(phi_prime_deg)
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
        Used only when layers is None (explicit homogeneous profile).
    fallback_gamma_sat : float or None
        Used only when layers is None (explicit homogeneous profile).

    Returns
    -------
    (q_eff, breakdown) : tuple[float, list[str]]
        Effective surcharge q_eff (kPa) and step-by-step calculation breakdown.
    """
    Df = _finite(Df, "Founding depth", minimum=0.0)
    wt_eff = _finite(wt_bgl, "Water-table depth", minimum=0.0)
    gamma_w = _finite(gamma_w, "Water unit weight", minimum=0.0, strict=True)
    sorted_layers = validate_profile(layers, Df) if layers is not None else None
    if Df == 0.0:
        return 0.0, ["Df = 0.00 m → q = 0.00 kPa"]

    if layers is None:
        if fallback_gamma_moist is None or fallback_gamma_sat is None:
            raise ValueError(
                "No soil layers provided and fallback unit weights were not specified."
            )
        fallback_gamma_moist, fallback_gamma_sat = _unit_weights(
            fallback_gamma_moist, fallback_gamma_sat, gamma_w
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

    q_eff = 0.0
    breakdown: list[str] = []
    cursor = 0.0

    for idx, lyr in enumerate(sorted_layers):
        if cursor >= Df - DEPTH_EPS:
            break

        lyr_top = float(lyr["depth_top"])
        lyr_bot = float(lyr["depth_bot"])

        seg_top = max(cursor, lyr_top)
        seg_bot = min(lyr_bot, Df)
        if seg_bot <= seg_top + DEPTH_EPS:
            continue

        raw_moist = lyr.get("gamma_moist")
        raw_sat = lyr.get("gamma_sat")
        if raw_moist is None or raw_sat is None:
            raise ValueError(f"Layer {idx + 1} is missing 'gamma_moist' or 'gamma_sat'.")

        try:
            g_moist, g_sat = _unit_weights(raw_moist, raw_sat, gamma_w)
        except ValueError as exc:
            raise ValueError(f"Layer {idx + 1}: {exc}") from exc
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

    Net equation used by this implementation (verify factors against IS 6403):
        qnu = c · Nc · sc · dc · ic
            + q · (Nq - 1) · sq · dq · iq
            + 0.5 · γ · B · Nγ · sγ · dγ · iγ · W′

    For undrained φ=0 (cu analysis):
        qnu = cu · Nc · sc · dc · ic      [Nq = 1, Nγ = 0]
        qf = qnu + q

    Effective overburden at founding level:
        Integrated across `layers` from 0 to Df (splitting at wt_bgl) when
        `layers` is provided; otherwise computed from homogeneous `gamma_moist`
        and `gamma_sat`. Can also be supplied directly via `q_eff_override`.

    Net ultimate bearing capacity:
        qnu = qf − q  (gross ultimate minus overburden)
        For undrained case: qnu = cu · Nc · sc · dc · ic

    Local shear: parameters reduced per IS 6403:1981 Cl. 5.3 before computation.
    """
    footing_shape = footing_shape.lower()
    failure_mode = failure_mode.lower()
    if footing_shape not in {"strip", "square", "rectangular", "circular"}:
        raise ValueError(f"Unsupported footing shape: {footing_shape}")
    if failure_mode not in {"general", "local"}:
        raise ValueError(f"Unsupported failure mode: {failure_mode}")
    B = _finite(B, "Width B", minimum=0.0, strict=True)
    if footing_shape == "rectangular":
        L = _finite(L, "Length L", minimum=0.0, strict=True)
    Df = _finite(Df, "Founding depth", minimum=0.0)
    wt_bgl = _finite(wt_bgl, "Water-table depth", minimum=0.0)
    gamma_moist, gamma_sat = _unit_weights(gamma_moist, gamma_sat)
    if layers is not None:
        validate_profile(layers, Df)

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
        c_used = _finite(cu, "Undrained shear strength", minimum=0.0)
        phi_used = 0.0
    else:
        c_used = _finite(c_prime, "Cohesion", minimum=0.0)
        phi_used = _friction_angle(phi_prime_deg)

    # --- Local shear reduction (IS 6403:1981 Cl. 5.3) ----------------------
    if failure_mode == "local":
        c_used, phi_used = local_shear_params(c_used, phi_used)

    # --- Bearing capacity factors -------------------------------------------
    Nc, Nq, Ngamma = bearing_capacity_factors(phi_used)

    # --- Effective overburden at founding level (IS 6403 Cl. 5.1.2) ---------
    wt_eff = wt_bgl
    if q_eff_override is not None:
        q_eff = _finite(q_eff_override, "Effective surcharge override", minimum=0.0)
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

    if not np.isfinite(qnu) or not np.isfinite(qf):
        raise ValueError("Bearing-capacity result is not finite; check inputs and method applicability.")
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
        "L": 1.0 if footing_shape == "strip" else L,
        "strip_per_unit_length": footing_shape == "strip",
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
    qnu = _finite(qnu, "Net ultimate capacity", minimum=0.0)
    FOS = _finite(FOS, "Factor of safety", minimum=0.0, strict=True)
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
    B = _finite(B, "Width B", minimum=0.0, strict=True)
    L = _finite(L, "Length L", minimum=0.0, strict=True)
    ex = _finite(ex, "Width eccentricity")
    ey = _finite(ey, "Length eccentricity")

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
    load_is_net: bool = True,
):
    """Size a concentrically loaded footing with a checked bearing-capacity target.

    P_kN is a net applied load by default (backward-compatible convention).
    For a gross load, set load_is_net=False: net pressure is P/A - q_eff,
    using the surcharge convention of this utility. For strip footings P_kN
    is in kN/m and returned L=1 m denotes the unit-length calculation basis.
    This is a bearing-capacity-only check, not a settlement or eccentric design.
    The existing capacity equation is used without changing its coefficients.
    """
    P_kN = _finite(P_kN, "Applied load", minimum=0.0, strict=True)
    FOS = _finite(FOS, "Factor of safety", minimum=0.0, strict=True)
    width_step = _finite(width_step, "Width increment", minimum=0.0, strict=True)
    tol = _finite(tol, "Width tolerance", minimum=0.0, strict=True)
    if isinstance(max_iter, bool) or not isinstance(max_iter, (int, np.integer)) or max_iter <= 0:
        raise ValueError("max_iter must be a positive integer.")
    if not isinstance(load_is_net, (bool, np.bool_)):
        raise ValueError("load_is_net must be True or False.")
    shape = footing_shape.lower()
    if shape not in ("square", "circular", "rectangular", "strip"):
        raise ValueError(f"Unsupported footing_shape: {footing_shape}")
    if shape == "rectangular":
        aspect_ratio = _finite(aspect_ratio, "L/B aspect ratio", minimum=1.0)

    def _length(b):
        if shape == "rectangular":
            return aspect_ratio * b
        if shape == "strip":
            return 1.0
        return b

    def _evaluate(b):
        length = _length(b)
        if shape == "circular":
            area = np.pi * b ** 2 / 4.0
        else:
            area = b * length  # strip area per metre of footing
        res = net_ultimate_bearing_capacity(
            c_prime=c_prime, phi_prime_deg=phi_prime_deg,
            gamma_moist=gamma_moist, gamma_sat=gamma_sat,
            Df=Df, B=b, L=length, wt_bgl=wt_bgl,
            footing_shape=shape, failure_mode=failure_mode,
            alpha_deg=alpha_deg, is_undrained=is_undrained, cu=cu,
            layers=layers, q_eff_override=q_eff_override,
        )
        qnu = res["qnu"]
        if qnu <= 0.0:
            raise ValueError("Non-positive net ultimate capacity; footing cannot be sized.")
        qns = net_safe_bearing_capacity(qnu, FOS)
        gross_or_net_input = P_kN / area
        net_pressure = gross_or_net_input if load_is_net else gross_or_net_input - res["q_eff"]
        return length, qnu, qns, net_pressure, gross_or_net_input, res["q_eff"]

    # Bracket a feasible width, then bisect. For the retained capacity model,
    # the supported concentric geometries have increasing load resistance
    # with width when valid nonnegative strength/surcharge inputs are used.
    lo = 0.0
    hi = width_step
    for _ in range(max_iter):
        _, _, qns, net_pressure, _, _ = _evaluate(hi)
        if net_pressure <= qns:
            break
        lo, hi = hi, hi * 2.0
    else:
        raise ValueError("Could not bracket a feasible footing width; check inputs or iteration limit.")

    for _ in range(max_iter):
        if hi - lo <= min(tol, width_step):
            break
        mid = (lo + hi) / 2.0
        _, _, qns, net_pressure, _, _ = _evaluate(mid)
        if net_pressure <= qns:
            hi = mid
        else:
            lo = mid
    else:
        if hi - lo > min(tol, width_step):
            raise ValueError("Footing sizing did not converge within the iteration limit.")

    B_rounded = float(np.ceil(hi / width_step) * width_step)
    L_final, qnu, qns, net_pressure, input_pressure, q_eff = _evaluate(B_rounded)
    if net_pressure <= 0.0:
        raise ValueError("Net applied pressure is nonpositive; review the load basis and footing dimensions.")
    if net_pressure > qns:
        raise ValueError("Final rounded footing does not meet the target factor of safety.")
    return {
        "B": B_rounded,
        "L": L_final,
        "qns": qns,
        "qnu": qnu,
        "actual_FOS": qnu / net_pressure,
        "net_applied_pressure": net_pressure,
        "input_pressure": input_pressure,
        "q_eff": q_eff,
        "load_is_net": load_is_net,
        "strip_per_unit_length": shape == "strip",
    }
