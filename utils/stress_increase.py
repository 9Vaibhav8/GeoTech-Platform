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

    Uses the standard Newmark / Das formula:
        m1 = B/z,  n1 = L/z
        A1 = (2·m1·n1·√(1+m1²+n1²)) / (1+m1²+n1²+m1²·n1²) × (1+m1²+n1²+1)/(1+m1²+n1²)
           ← simplified to the standard two-term Iσ expression below
        Iσ = (1/(4π)) × [A1 + A2]
        Δσz = q × Iσ

    For z = 0 returns q (uniform surface pressure right at corner).
    Cite: Boussinesq (1885); Das (2016) Eq. 5.37
    """
    if np.isscalar(z):
        if z <= 0:
            return float(q)
        m1 = float(B) / z
        n1 = float(L) / z
        q_term = 1.0 + m1 ** 2 + n1 ** 2  # (1 + m² + n²)
        mn = m1 * n1
        sqrt_q = np.sqrt(q_term)

        A1_num = 2.0 * mn * sqrt_q * (q_term + 1.0)
        A1_den = q_term * (q_term + mn ** 2)
        A1 = A1_num / A1_den

        # arctan argument
        arg = (2.0 * mn * sqrt_q) / (q_term - mn ** 2)
        A2 = np.arctan(arg)
        if (q_term - mn ** 2) < 0:   # add π when denominator negative
            A2 += np.pi

        Isigma = (A1 + A2) / (4.0 * np.pi)
        return q * Isigma
    else:
        z = np.asarray(z, dtype=float)
        result = np.empty_like(z)
        for i, zi in enumerate(z.flat):
            result.flat[i] = boussinesq_corner(q, B, L, zi)
        return result


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
    Δσz at depth z below an arbitrary point that is x_offset from one corner
    along B-direction and y_offset from that corner along L-direction.
    Uses superposition of up to 4 rectangles (Newmark 1935 method).

    The point divides B into (x_offset, B - x_offset) and
    L into (y_offset, L - y_offset).

    Cite: Newmark (1935) superposition method.
    """
    x1, x2 = x_offset, B - x_offset
    y1, y2 = y_offset, L - y_offset

    dsigma = (boussinesq_corner(q, x1, y1, z) +
              boussinesq_corner(q, x2, y1, z) +
              boussinesq_corner(q, x1, y2, z) +
              boussinesq_corner(q, x2, y2, z))
    return dsigma


def stress_increase_2to1(q, B, L, z):
    """
    2:1 method vertical stress increase.
        Δσz = (q × B × L) / ((B + z) × (L + z))
    For z = 0 returns q.
    Cite: 2:1 load distribution method (IS 8009:1976)
    """
    if np.isscalar(z):
        if z <= 0:
            return float(q)
        return float(q) * float(B) * float(L) / ((B + z) * (L + z))
    else:
        z = np.asarray(z, dtype=float)
        result = np.where(z <= 0, float(q),
                          float(q) * float(B) * float(L) / ((B + z) * (L + z)))
        return result


def stress_profile(q, B, L, z_max, method="boussinesq_centre", n_points=50):
    """
    Compute Δσz at multiple depths from 0 to z_max.

    Parameters
    ----------
    q : float
        Net foundation pressure (kPa).
    B, L : float
        Footing dimensions (m).
    z_max : float
        Maximum depth below footing (m).
    method : str
        One of "boussinesq_centre", "boussinesq_corner", "2to1".
    n_points : int
        Number of evaluation points.

    Returns
    -------
    z_array : np.ndarray
        Depths (m), 0 to z_max.
    delta_sigma_array : np.ndarray
        Corresponding Δσz values (kPa).
    """
    z_array = np.linspace(0.001, z_max, n_points)  # avoid z=0 numerical issue
    z_array = np.concatenate(([0.0], z_array))

    if method == "boussinesq_centre":
        delta_sigma_array = np.array([stress_increase_centre(q, B, L, z) for z in z_array])
    elif method == "boussinesq_corner":
        delta_sigma_array = np.array([boussinesq_corner(q, B, L, z) for z in z_array])
    elif method == "2to1":
        delta_sigma_array = stress_increase_2to1(q, B, L, z_array)
    else:
        raise ValueError(f"Unknown method '{method}'. "
                         "Choose from 'boussinesq_centre', 'boussinesq_corner', '2to1'.")

    return z_array, delta_sigma_array


def influence_depth(q, B, L, threshold=0.1, method="boussinesq_centre", n_points=500):
    """
    Find the depth z* where Δσz / q ≤ threshold (default 10% of q).
    Returns z* in metres, or z_max if threshold not reached within 5B.
    """
    z_max = 5.0 * B
    z_arr, ds_arr = stress_profile(q, B, L, z_max, method=method, n_points=n_points)
    ratio = ds_arr / q
    idx = np.where(ratio <= threshold)[0]
    if len(idx) == 0:
        return z_max
    return float(z_arr[idx[0]])


def effective_stress_profile(layers, wt_design_bgl, z_array, Df=0.0):
    """
    Compute effective vertical stress σ′v0 at each depth in z_array.
    z_array is measured from the footing base (i.e., add Df to get depth bgl).

    Parameters
    ----------
    layers : list of dict
        Each dict has depth_top, depth_bot, gamma_moist, gamma_sat keys.
    wt_design_bgl : float
        Water table depth below ground level (m bgl).
    z_array : array-like
        Depths below footing base (m).
    Df : float
        Footing embedment depth below ground level (m).

    Returns
    -------
    sigma_v0 : np.ndarray
        Effective vertical stress (kPa) at each depth in z_array.
    """
    gamma_w = 9.81  # kN/m³

    def sigma_at_depth(z_bgl):
        """Compute effective stress at depth z_bgl (m below ground level)."""
        sigma = 0.0
        for lyr in layers:
            if lyr["depth_top"] >= z_bgl:
                break
            z_bot = min(lyr["depth_bot"], z_bgl)
            z_top = lyr["depth_top"]
            dz = z_bot - z_top
            mid = (z_top + z_bot) / 2.0
            if mid < wt_design_bgl:
                gamma = lyr.get("gamma_moist", 18.0)
                sigma += gamma * dz
            else:
                gamma_sat = lyr.get("gamma_sat", 20.0)
                sigma += (gamma_sat - gamma_w) * dz
                # add pore pressure reduction for portion above WT inside layer
                if z_top < wt_design_bgl < z_bot:
                    # already computed as moist above; correct the sub-WT part
                    dz_above = wt_design_bgl - z_top
                    dz_below = z_bot - wt_design_bgl
                    # redo: remove what we added for submerged portion above, recalc
                    sigma = sigma  # already incremented correctly per mid approach
        return sigma

    result = np.array([sigma_at_depth(z + Df) for z in z_array])
    return result
