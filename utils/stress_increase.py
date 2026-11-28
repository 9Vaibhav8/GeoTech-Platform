"""
utils/stress_increase.py
Boussinesq and 2:1 vertical stress increase calculations.
Cite: Boussinesq (1885); Das (2016) Principles of Foundation Engineering;
      IS 8009:1976 Part 1.
"""

import numpy as np

from .bearing_capacity import validate_profile, effective_overburden_pressure


def _finite(value, name, *, positive=False, nonnegative=False):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number.") from exc
    if not np.isfinite(value) or (positive and value <= 0) or (nonnegative and value < 0):
        raise ValueError(f"Invalid {name}: {value}")
    return value


def _inputs(q, B, L, z):
    # Signed pressure is supported mathematically (negative = unloading).
    q = _finite(q, "Pressure q")
    B = _finite(B, "Width B", positive=True)
    L = _finite(L, "Length L", positive=True)
    z = np.asarray(z, dtype=float)
    if not np.all(np.isfinite(z)) or np.any(z < 0):
        raise ValueError("Depth z must be finite and nonnegative.")
    return q, B, L, z


def _return_shape(result, z):
    return float(result) if z.ndim == 0 else result



def boussinesq_corner(q, B, L, z):
    """
    Boussinesq vertical stress increase Δσz at depth z below the CORNER
    of a uniformly loaded rectangle (B × L) with pressure q (kPa).
    """
    q, B, L, z = _inputs(q, B, L, z)
    # Algebraically equivalent integrated Boussinesq rectangle solution
    # (Das 2016, Eq. 5.37); use normalized dimensions to avoid B/z overflow.
    scale = np.maximum(np.maximum(B, L), z)
    b, l, d = B / scale, L / scale, z / scale
    r = np.hypot(np.hypot(b, l), d)
    # atan2 gives the correct quadrant and the corner surface limit pi/2.
    angle = np.arctan2(b * l, d * r)
    with np.errstate(divide="ignore", invalid="ignore"):
        term = (l / r) * (b / np.hypot(b, d)) * (d / np.hypot(b, d))
        term += (b / r) * (l / np.hypot(l, d)) * (d / np.hypot(l, d))
    result = np.where(z == 0, q / 4.0, q * (angle + term) / (2.0 * np.pi))
    if not np.all(np.isfinite(result)):
        raise ValueError("Stress calculation exceeds numerical range.")
    return _return_shape(result, z)


def stress_increase_centre(q, B, L, z):
    """
    Δσz at depth z below the CENTRE of a uniformly loaded rectangle B × L.
    Uses superposition of 4 corner contributions, each of area (B/2 × L/2).
        Δσz_centre = 4 × boussinesq_corner(q, B/2, L/2, z)
    Cite: Principle of superposition, Das (2016) Sec. 5.5
    """
    q, B, L, z = _inputs(q, B, L, z)
    return 4.0 * boussinesq_corner(q, B / 2.0, L / 2.0, z)


def stress_increase_point(q, B, L, x_offset, y_offset, z):
    """
    Δσz at depth z below an arbitrary point (x_offset, y_offset) relative to
    one corner of a uniformly loaded rectangle (B × L).
    Works for interior, edge, corner, and exterior points via Newmark (1935)
    signed superposition.
    """
    q, B, L, z = _inputs(q, B, L, z)
    x_offset = _finite(x_offset, "Observation x")
    y_offset = _finite(y_offset, "Observation y")
    x_parts = (x_offset, B - x_offset)
    y_parts = (y_offset, L - y_offset)
    dsigma = np.zeros_like(z, dtype=float)
    # Signed superposition of four rectangles (Newmark 1935).
    for dx in x_parts:
        if dx == 0.0:
            continue
        for dy in y_parts:
            if dy == 0.0:
                continue
            sign = np.sign(dx) * np.sign(dy)
            dsigma += sign * boussinesq_corner(q, abs(dx), abs(dy), z)
    # Eliminate tiny opposite-sign residuals from floating-point cancellation.
    dsigma = np.clip(dsigma, min(0., q), max(0., q))
    return _return_shape(dsigma, z)


def stress_increase_2to1(q, B, L, z):
    """
    2:1 (2V:1H) approximate vertical stress increase below a rectangular
    loaded area (B × L) with uniform pressure q (kPa):
        Δσz = (q × B × L) / ((B + z) × (L + z))
    """
    q, B, L, z = _inputs(q, B, L, z)
    # 2:1 spread approximation; equivalent to qBL/((B+z)(L+z)).
    with np.errstate(over="ignore"):
        result = q * (1.0 / (1.0 + z / B)) * (1.0 / (1.0 + z / L))
    return _return_shape(result, z)


def stress_profile(q, B, L, z_max, method="boussinesq_centre", n_points=50):
    """
    Compute Δσz at n_points depths uniformly spaced from 0 to z_max.
    """
    z_max = _finite(z_max, "Maximum plot depth", positive=True)
    n_points = _finite(n_points, "Number of points", positive=True)
    if not n_points.is_integer() or n_points < 2:
        raise ValueError("n_points must be an integer of at least 2.")

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
    Find the numerical depth z* (m) where Δσz / q == threshold to within the requested tolerance using adaptive
    bracketing and bisection (no arbitrary 5B cutoff).
    """
    q = _finite(q, "Pressure q", positive=True)
    B = _finite(B, "Width B", positive=True)
    L = _finite(L, "Length L", positive=True)
    threshold = _finite(threshold, "Threshold", positive=True)
    tol = _finite(tol, "Tolerance", positive=True)
    if threshold >= 1.0:
        raise ValueError("Threshold must be less than 1.")

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

    # Adaptive bracketing and bisection, with finite iteration guards.
    z_lo, z_hi = 0.0, min(B, L)
    for _ in range(2048):
        if fn(1.0, B, L, z_hi) <= threshold:
            break
        z_lo = z_hi
        z_hi *= 2.0
        if not np.isfinite(z_hi):
            raise ValueError("Influence depth exceeds numerical range.")
    else:
        raise ValueError("Could not bracket influence depth.")
    for _ in range(2048):
        z_mid = z_lo + 0.5 * (z_hi - z_lo)
        if z_hi - z_lo <= tol or z_mid in (z_lo, z_hi):
            return z_mid
        if fn(1.0, B, L, z_mid) > threshold:
            z_lo = z_mid
        else:
            z_hi = z_mid
    raise ValueError("Influence-depth solver did not converge.")


def effective_stress_profile(layers, wt_design_bgl, z_array, Df=0.0):
    """
    Compute vertical effective overburden stress σ'v0 (kPa) at depths (z + Df)
    below ground level across a stratified soil profile.
    """
    Df = _finite(Df, "Founding depth", nonnegative=True)
    wt_design_bgl = _finite(wt_design_bgl, "Design water table", nonnegative=True)
    z = np.asarray(z_array, dtype=float)
    if np.any(z < 0) or not np.all(np.isfinite(z)):
        raise ValueError("Depth below footing must be finite and nonnegative.")
    depths = z + Df
    ordered = validate_profile(layers, float(np.max(depths)) if depths.size else Df)
    # Reuse P3's exact groundwater splitting and explicit unit-weight validation.
    values = [effective_overburden_pressure(ordered, float(depth), wt_design_bgl)[0]
              for depth in depths.flat]
    return np.asarray(values, dtype=float).reshape(z.shape)
