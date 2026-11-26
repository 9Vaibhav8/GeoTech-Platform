"""
utils/stress_increase.py
Boussinesq and 2:1 vertical stress increase calculations.
Cite: Boussinesq (1885); Das (2016) Principles of Foundation Engineering;
      IS 8009:1976 Part 1.
"""

import numpy as np


def boussinesq_corner(q, B, L, z):
    """
    Boussinesq vertical stress increase Δσz at depth z below the CORNER
    of a uniformly loaded rectangle (B × L) with pressure q (kPa).
    """
    if B <= 0 or L <= 0:
        raise ValueError(f"Footing dimensions B and L must be positive, got B={B}, L={L}")

    is_scalar = np.isscalar(z)
    z_arr = np.atleast_1d(np.asarray(z, dtype=float))

    if np.any(z_arr < 0):
        raise ValueError("Depth z must be non-negative (z >= 0).")

    result = np.empty_like(z_arr, dtype=float)
    zero_mask = (z_arr == 0.0)
    result[zero_mask] = 0.25 * float(q)  # exact Boussinesq corner limit as z -> 0+

    pos_mask = ~zero_mask
    if np.any(pos_mask):
        z_pos = z_arr[pos_mask]
        m1 = float(B) / z_pos
        n1 = float(L) / z_pos
        q_term = 1.0 + m1 ** 2 + n1 ** 2
        mn = m1 * n1
        sqrt_q = np.sqrt(q_term)

        A1 = (2.0 * mn * sqrt_q * (q_term + 1.0)) / (q_term * (q_term + mn ** 2))
        A2 = np.arctan2(2.0 * mn * sqrt_q, q_term - mn ** 2)

        result[pos_mask] = float(q) * (A1 + A2) / (4.0 * np.pi)

    return float(result[0]) if is_scalar else result


def stress_increase_centre(q, B, L, z):
    """
    Δσz at depth z below the CENTRE of a uniformly loaded rectangle B × L.
    Uses superposition of 4 corner contributions, each of area (B/2 × L/2).
        Δσz_centre = 4 × boussinesq_corner(q, B/2, L/2, z)
    Cite: Principle of superposition, Das (2016) Sec. 5.5
    """
    return 4.0 * boussinesq_corner(q, B / 2.0, L / 2.0, z)


def stress_increase_point(q, B, L, x_offset, y_offset, z):
    """
    Δσz at depth z below an arbitrary point (x_offset, y_offset) relative to
    one corner of a uniformly loaded rectangle (B × L).
    Works for interior, edge, corner, and exterior points via Newmark (1935)
    signed superposition.
    """
    if B <= 0 or L <= 0:
        raise ValueError(f"Footing dimensions B and L must be positive, got B={B}, L={L}")

    x_parts = (x_offset, B - x_offset)
    y_parts = (y_offset, L - y_offset)

    dsigma = 0.0 if np.isscalar(z) else np.zeros_like(np.asarray(z, dtype=float))

    for dx in x_parts:
        if dx == 0.0:
            continue
        for dy in y_parts:
            if dy == 0.0:
                continue
            sign = (1.0 if dx > 0 else -1.0) * (1.0 if dy > 0 else -1.0)
            dsigma = dsigma + sign * boussinesq_corner(q, abs(dx), abs(dy), z)

    return float(dsigma) if np.isscalar(z) else dsigma


def stress_increase_2to1(q, B, L, z):
    """
    2:1 (2V:1H) approximate vertical stress increase below a rectangular
    loaded area (B × L) with uniform pressure q (kPa):
        Δσz = (q × B × L) / ((B + z) × (L + z))
    """
    if B <= 0 or L <= 0:
        raise ValueError(f"Footing dimensions B and L must be positive, got B={B}, L={L}")

    if np.isscalar(z):
        if z < 0:
            raise ValueError(f"Depth z must be non-negative, got {z}")
        return float(q) * float(B) * float(L) / ((B + z) * (L + z))

    z_arr = np.asarray(z, dtype=float)
    if np.any(z_arr < 0):
        raise ValueError("Depth z must be non-negative (z >= 0).")

    return float(q) * float(B) * float(L) / ((B + z_arr) * (L + z_arr))

def stress_profile(q, B, L, z_max, method="boussinesq_centre", n_points=50):
    """
    Compute Δσz at n_points depths uniformly spaced from 0 to z_max.
    """
    if z_max <= 0:
        raise ValueError(f"z_max must be positive, got {z_max}")
    if n_points < 2:
        raise ValueError(f"n_points must be at least 2, got {n_points}")

    z_array = np.linspace(0.0, float(z_max), int(n_points))

    if method == "boussinesq_centre":
        delta_sigma_array = stress_increase_centre(q, B, L, z_array)
    elif method == "boussinesq_corner":
        delta_sigma_array = boussinesq_corner(q, B, L, z_array)
    elif method == "2to1":
        delta_sigma_array = stress_increase_2to1(q, B, L, z_array)
    else:
        raise ValueError(
            f"Unknown method '{method}'. "
            "Choose from 'boussinesq_centre', 'boussinesq_corner', '2to1'."
        )

    return z_array, delta_sigma_array

def influence_depth(q, B, L, threshold=0.1, method="boussinesq_centre", tol=1e-4):
    """
    Find the exact depth z* (m) where Δσz / q == threshold using adaptive
    bracketing and bisection (no arbitrary 5B cutoff).
    """
    if q <= 0:
        raise ValueError(f"Pressure q must be positive, got {q}")
    if B <= 0 or L <= 0:
        raise ValueError(f"Footing dimensions B and L must be positive, got B={B}, L={L}")
    if not (0.0 < threshold < 1.0):
        raise ValueError(f"threshold must be in (0, 1), got {threshold}")

    method_map = {
        "boussinesq_centre": stress_increase_centre,
        "boussinesq_corner": boussinesq_corner,
        "2to1": stress_increase_2to1,
    }
    if method not in method_map:
        raise ValueError(
            f"Unknown method '{method}'. "
            "Choose from 'boussinesq_centre', 'boussinesq_corner', '2to1'."
        )
    fn = method_map[method]

    # Ratio at surface z = 0 (1.0 for centre/2:1, 0.25 for corner)
    if fn(1.0, B, L, 0.0) <= threshold:
        return 0.0

    # Adaptively bracket z* by doubling z_hi until ratio <= threshold
    z_lo, z_hi = 0.0, float(B)
    while fn(1.0, B, L, z_hi) > threshold:
        z_lo = z_hi
        z_hi *= 2.0

    # Bisection (exact since Δσz(z) is strictly decreasing)
    while (z_hi - z_lo) > tol:
        z_mid = 0.5 * (z_lo + z_hi)
        if fn(1.0, B, L, z_mid) > threshold:
            z_lo = z_mid
        else:
            z_hi = z_mid

    return 0.5 * (z_lo + z_hi)


def effective_stress_profile(layers, wt_design_bgl, z_array, Df=0.0):
    """
    Compute vertical effective overburden stress σ'v0 (kPa) at depths (z + Df)
    below ground level across a stratified soil profile.
    """
    if not layers:
        raise ValueError("layers must be a non-empty sequence of soil layer dicts.")

    gamma_w = 9.81  # kN/m³
    sorted_layers = sorted(layers, key=lambda lyr: lyr["depth_top"])
    max_depth = sorted_layers[-1]["depth_bot"]

    def sigma_at_depth(z_bgl):
        if z_bgl < 0:
            raise ValueError(f"Depth below ground level must be non-negative, got {z_bgl}")
        if z_bgl > max_depth:
            raise ValueError(
                f"Requested depth {z_bgl:.2f} m exceeds profile bottom {max_depth:.2f} m."
            )

        sigma = 0.0
        for lyr in sorted_layers:
            z_top = lyr["depth_top"]
            if z_top >= z_bgl:
                break
            z_bot = min(lyr["depth_bot"], z_bgl)
            if z_bot <= z_top:
                continue

            # Exact split of the layer segment [z_top, z_bot] at the water table
            z_split = min(max(wt_design_bgl, z_top), z_bot)
            dz_above = z_split - z_top
            dz_below = z_bot - z_split

            gamma_moist = lyr.get("gamma_moist", 18.0)
            gamma_sat = lyr.get("gamma_sat", 20.0)
            sigma += gamma_moist * dz_above + (gamma_sat - gamma_w) * dz_below

        return sigma

    z_arr = np.asarray(z_array, dtype=float)
    return np.array([sigma_at_depth(float(z) + Df) for z in z_arr], dtype=float)
