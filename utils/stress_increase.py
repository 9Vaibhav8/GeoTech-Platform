"""
utils/stress_increase.py
Boussinesq (1885), Newmark (1935), and 2:1 vertical stress increase calculations.
All computations strictly in SI units (m, kN, kPa).

Sources:
  - Boussinesq (1885) — elastic half-space vertical stress solution
  - Newmark (1935) — Simplified computation of vertical pressures in elastic foundations
  - Das, B.M. — Principles of Foundation Engineering, Ch. 10, Eq. 10.33
  - IS 8009:1976 Part 1 — Code of practice for calculation of settlements of foundations
"""

import math
from typing import Dict, List, Sequence, Union

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

GAMMA_W = 9.81  # kN/m³, unit weight of water


def _is_scalar(val) -> bool:
    """Return True if val is a Python/NumPy scalar."""
    if np is not None:
        return bool(np.isscalar(val))
    return isinstance(val, (int, float))


def boussinesq_corner_factor(B: float, L: float, z: float) -> float:
    """
    Branch-safe Boussinesq influence factor I_c below the CORNER of a uniformly
    loaded rectangle (B × L) at depth z > 0.

    Uses math.atan2 so the inverse-tangent term remains continuously in [0, π]
    even when m²·n² > m² + n² + 1 (shallow depths / large footings).

    Parameters
    ----------
    B : float — rectangle dimension along X (m)
    L : float — rectangle dimension along Y (m)
    z : float — depth below loaded plane (m)

    Returns
    -------
    float — dimensionless influence factor I_c in [0.0, 0.25]
    """
    B = float(B)
    L = float(L)
    z = float(z)

    if B <= 0.0 or L <= 0.0:
        return 0.0
    if z <= 0.0:
        # Source: Boussinesq (1885) / Newmark (1935) surface corner limit (z -> 0+)
        return 0.25

    # Source: Newmark (1935); Das Ch. 10 Eq. 10.33
    m = B / z
    # Source: Newmark (1935); Das Ch. 10 Eq. 10.33
    n = L / z

    m2 = m * m
    n2 = n * n
    mn2 = m2 * n2

    # Source: Newmark (1935); Das Ch. 10 Eq. 10.33
    r = math.sqrt(m2 + n2 + 1.0)

    # Source: Newmark (1935); Das Ch. 10 Eq. 10.33 (first rational term)
    term1 = ((2.0 * m * n * r) / (m2 + n2 + mn2 + 1.0)) * ((m2 + n2 + 2.0) / (m2 + n2 + 1.0))

    # Source: Newmark (1935); Das Ch. 10 Eq. 10.33 (branch-safe atan2 in [0, pi])
    term2 = math.atan2(2.0 * m * n * r, m2 + n2 - mn2 + 1.0)

    # Source: Newmark (1935); Das Ch. 10 Eq. 10.33
    return (term1 + term2) / (4.0 * math.pi)


def boussinesq_corner(q: float, B: float, L: float, z: Union[float, Sequence[float]]):
    """
    Vertical stress increase Δσz (kPa) at depth z (m) below the CORNER
    of a uniformly loaded rectangle (B × L) carrying pressure q (kPa).
    """
    if _is_scalar(z):
        # Source: Newmark (1935); Das Ch. 10 Eq. 10.33
        return float(q) * boussinesq_corner_factor(B, L, float(z))

    if np is not None:
        z_arr = np.asarray(z, dtype=float)
        result = np.empty_like(z_arr)
        for i, zi in enumerate(z_arr.flat):
            # Source: Newmark (1935); Das Ch. 10 Eq. 10.33
            result.flat[i] = float(q) * boussinesq_corner_factor(B, L, float(zi))
        return result

    return [float(q) * boussinesq_corner_factor(B, L, float(zi)) for zi in z]


def stress_increase_centre(q: float, B: float, L: float, z: Union[float, Sequence[float]]):
    """
    Vertical stress increase Δσz (kPa) at depth z (m) below the CENTRE
    of a uniformly loaded rectangle B × L using 4-quadrant superposition.
    """
    if _is_scalar(z):
        # Source: Newmark (1935) 4-corner superposition at rectangle centre
        return 4.0 * float(q) * boussinesq_corner_factor(float(B) / 2.0, float(L) / 2.0, float(z))

    if np is not None:
        z_arr = np.asarray(z, dtype=float)
        result = np.empty_like(z_arr)
        for i, zi in enumerate(z_arr.flat):
            # Source: Newmark (1935) 4-corner superposition at rectangle centre
            result.flat[i] = 4.0 * float(q) * boussinesq_corner_factor(float(B) / 2.0, float(L) / 2.0, float(zi))
        return result

    return [4.0 * float(q) * boussinesq_corner_factor(float(B) / 2.0, float(L) / 2.0, float(zi)) for zi in z]


def _signed_quadrant_factor(a: float, b: float, z: float) -> float:
    """Signed quadrant corner influence factor F(a, b, z) = sign(a)*sign(b)*I_c(|a|, |b|, z)."""
    if a == 0.0 or b == 0.0:
        return 0.0
    sign_ab = (1.0 if a > 0.0 else -1.0) * (1.0 if b > 0.0 else -1.0)
    # Source: Newmark (1935) signed-quadrant corner kernel
    return sign_ab * boussinesq_corner_factor(abs(a), abs(b), z)


def boussinesq_rectangle_at_point(
    q: float,
    x_center: float,
    y_center: float,
    B_x: float,
    L_y: float,
    x_pt: float,
    y_pt: float,
    z: float,
) -> float:
    """
    Vertical stress increase Δσz (kPa) at arbitrary point (x_pt, y_pt, z)
    due to a uniformly loaded rectangle centred at (x_center, y_center)
    spanning [x_c - B_x/2, x_c + B_x/2] × [y_c - L_y/2, y_c + L_y/2] with pressure q (kPa).

    Uses exact signed-quadrant corner superposition over the 4 rectangle corners
    relative to (x_pt, y_pt).
    """
    if B_x <= 0.0 or L_y <= 0.0:
        return 0.0

    u1 = (float(x_center) - float(B_x) / 2.0) - float(x_pt)
    u2 = (float(x_center) + float(B_x) / 2.0) - float(x_pt)
    v1 = (float(y_center) - float(L_y) / 2.0) - float(y_pt)
    v2 = (float(y_center) + float(L_y) / 2.0) - float(y_pt)

    # Source: Newmark (1935) signed-quadrant inclusion-exclusion superposition
    i_total = (
        _signed_quadrant_factor(u2, v2, z)
        - _signed_quadrant_factor(u1, v2, z)
        - _signed_quadrant_factor(u2, v1, z)
        + _signed_quadrant_factor(u1, v1, z)
    )
    # Source: Boussinesq (1885) / Newmark (1935)
    return float(q) * i_total


def stress_increase_point(
    q: float,
    B: float,
    L: float,
    x_offset: float,
    y_offset: float,
    z: float,
) -> float:
    """
    Δσz (kPa) at depth z (m) below a point offset (x_offset, y_offset) from the
    (0, 0) corner of a rectangle [0, B] × [0, L].
    """
    return boussinesq_rectangle_at_point(
        q=q,
        x_center=float(B) / 2.0,
        y_center=float(L) / 2.0,
        B_x=B,
        L_y=L,
        x_pt=x_offset,
        y_pt=y_offset,
        z=z,
    )


def stress_increase_2to1(q: float, B: float, L: float, z: Union[float, Sequence[float]]):
    """
    2:1 approximate vertical stress distribution method (IS 8009:1976 Part 1):
        Δσz = (q · B · L) / ((B + z) · (L + z))
    """
    if _is_scalar(z):
        zf = float(z)
        if zf <= 0.0:
            return float(q)
        # Source: IS 8009:1976 Part 1 (2:1 stress distribution method)
        return float(q) * float(B) * float(L) / ((float(B) + zf) * (float(L) + zf))

    if np is not None:
        z_arr = np.asarray(z, dtype=float)
        # Source: IS 8009:1976 Part 1 (2:1 stress distribution method)
        return np.where(
            z_arr <= 0.0,
            float(q),
            float(q) * float(B) * float(L) / ((float(B) + z_arr) * (float(L) + z_arr)),
        )

    return [
        float(q) if float(zi) <= 0.0 else float(q) * float(B) * float(L) / ((float(B) + float(zi)) * (float(L) + float(zi)))
        for zi in z
    ]


def stress_profile(
    q: float,
    B: float,
    L: float,
    z_max: float,
    method: str = "boussinesq_centre",
    n_points: int = 50,
):
    """
    Compute Δσz (kPa) across depths z from 0 to z_max (m).
    Returns (z_array, delta_sigma_array).
    """
    if np is not None:
        z_array = np.concatenate(([0.0], np.linspace(0.001, z_max, n_points)))
    else:
        step = (z_max - 0.001) / max(n_points - 1, 1)
        z_array = [0.0] + [0.001 + i * step for i in range(n_points)]

    if method == "boussinesq_centre":
        delta_sigma_array = stress_increase_centre(q, B, L, z_array)
    elif method == "boussinesq_corner":
        delta_sigma_array = boussinesq_corner(q, B, L, z_array)
    elif method == "2to1":
        delta_sigma_array = stress_increase_2to1(q, B, L, z_array)
    else:
        raise ValueError(
            f"Unknown method '{method}'. Choose from 'boussinesq_centre', 'boussinesq_corner', '2to1'."
        )

    return z_array, delta_sigma_array


def influence_depth(
    q: float,
    B: float,
    L: float,
    threshold: float = 0.1,
    method: str = "boussinesq_centre",
    n_points: int = 500,
) -> float:
    """
    Find depth z* (m) below footing base where Δσz / q <= threshold (default 0.10).
    Returns z* in metres, or 5.0 * B if threshold is not reached within 5B.
    """
    z_max = 5.0 * float(B)
    z_arr, ds_arr = stress_profile(q, B, L, z_max, method=method, n_points=n_points)
    if float(q) <= 0.0:
        return z_max

    for zi, dsi in zip(z_arr, ds_arr):
        if (float(dsi) / float(q)) <= threshold:
            return float(zi)
    return z_max


def _sigma_v0_at_bgl(layers: List[Dict], z_bgl: float, wt_bgl: float) -> float:
    """Compute σ'v0 (kPa) at depth z_bgl (m bgl) with exact splitting at wt_bgl."""
    if z_bgl <= 0.0 or not layers:
        return 0.0

    sorted_layers = sorted(layers, key=lambda lyr: float(lyr["depth_top"]))
    sigma = 0.0

    for lyr in sorted_layers:
        d_top = float(lyr["depth_top"])
        d_bot = float(lyr["depth_bot"])
        if d_top >= z_bgl:
            break
        slice_top = max(0.0, d_top)
        slice_bot = min(z_bgl, d_bot)
        if slice_bot <= slice_top:
            continue

        g_moist = float(lyr.get("gamma_moist", 18.0))
        g_sub = float(lyr.get("gamma_sat", 20.0)) - GAMMA_W

        if slice_bot <= wt_bgl:
            # Source: Effective overburden above water table (γ_moist · Δz)
            sigma += g_moist * (slice_bot - slice_top)
        elif slice_top >= wt_bgl:
            # Source: Submerged effective overburden below water table ((γ_sat - γ_w) · Δz)
            sigma += g_sub * (slice_bot - slice_top)
        else:
            # Source: Exact water-table split within layer
            sigma += g_moist * (wt_bgl - slice_top) + g_sub * (slice_bot - wt_bgl)

    max_bot = max(float(lyr["depth_bot"]) for lyr in sorted_layers)
    if z_bgl > max_bot:
        last = sorted_layers[-1]
        g_moist = float(last.get("gamma_moist", 18.0))
        g_sub = float(last.get("gamma_sat", 20.0)) - GAMMA_W
        if z_bgl <= wt_bgl:
            sigma += g_moist * (z_bgl - max_bot)
        elif max_bot >= wt_bgl:
            sigma += g_sub * (z_bgl - max_bot)
        else:
            sigma += g_moist * (wt_bgl - max_bot) + g_sub * (z_bgl - wt_bgl)

    return max(sigma, 0.0)


def effective_stress_profile(layers: List[Dict], wt_design_bgl: float, z_array, Df: float = 0.0):
    """
    Compute effective vertical stress σ′v0 (kPa) at depths z_array (m below footing base).
    """
    vals = [_sigma_v0_at_bgl(layers, float(z) + float(Df), float(wt_design_bgl)) for z in z_array]
    if np is not None:
        return np.array(vals, dtype=float)
    return vals
