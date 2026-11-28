"""
utils/Is1904.py — IS 1904:1986 settlement-compliance helpers (no Streamlit dependency)

Pure functions so they can be unit-tested and reused by the P5 page.

Sources (cite these in the report):
  [1] IS 1904:1986, Code of practice for design and construction of foundations
      in soils: general requirements — Table 1 (permissible settlement,
      differential settlement and angular distortion).  Table 1, printed p. 19 (checked against scanned 1986 edition).
  [2] Skempton & MacDonald (1956), "The allowable settlements of buildings",
      Proc. ICE 5(3) — origin of angular-distortion criteria (δ/L).
  [3] IS 1904:1986 Cl. 16.3.5: maximum/minimum settlements and their separation.
      Adjacent-column checks are additional local screening checks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from string import ascii_uppercase

# ── IS 1904:1986 Table 1 — isolated footings, RC framed structure ───────────
# (sand & hard clay | plastic clay).  Values as tabulated in the commonly
# reproduced form of Table 1 (isolated foundation, RCC):
#   max settlement  : 50 mm | 75 mm
#   differential    : 0.0015 L (both soils)
#   angular distort.: 1/666 (both soils)
ISOLATED_RC = {
    "sand": {"total_mm": 50.0, "diff_ratio": 0.0015, "ang_limit": 1.0 / 666.0},
    "clay": {"total_mm": 75.0, "diff_ratio": 0.0015, "ang_limit": 1.0 / 666.0},
}
# Raft foundation, RCC (for the "alternative foundation" comparison)
RAFT_RC = {
    "sand": {"total_mm": 75.0, "diff_ratio": 0.0021, "ang_limit": 1.0 / 500.0},
    "clay": {"total_mm": 100.0, "diff_ratio": 0.002, "ang_limit": 1.0 / 500.0},
}

# Table 1 item iii(a): multistoreyed RC/steel frames with panel walls.
ISOLATED_MULTISTOREY = {
    "sand": {"total_mm": 60.0, "diff_ratio": 0.002, "ang_limit": 1.0 / 500.0},
    "clay": {"total_mm": 75.0, "diff_ratio": 0.002, "ang_limit": 1.0 / 500.0},
}
RAFT_MULTISTOREY = {
    "sand": {"total_mm": 75.0, "diff_ratio": 0.0025, "ang_limit": 1.0 / 400.0},
    "clay": {"total_mm": 125.0, "diff_ratio": 0.0033, "ang_limit": 1.0 / 300.0},
}


def _finite(value, label):
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be a finite number.") from exc
    if not math.isfinite(x):
        raise ValueError(f"{label} must be a finite number.")
    return x


def _integer(value, label, minimum=0):
    x = _finite(value, label)
    if not x.is_integer() or x < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}.")
    return int(x)


def _positive(value, label):
    x = _finite(value, label)
    if x <= 0:
        raise ValueError(f"{label} must be positive.")
    return x


def _grid(nx, ny):
    nx, ny = _integer(nx, "nx", 1), _integer(ny, "ny", 1)
    if ny > 26:
        raise ValueError("Grid row names A-Z support at most 26 rows.")
    return nx, ny


def lambda_factor(g: float) -> float:
    """Load multiplier λ = 1 + g/100 (assignment statement)."""
    return 1.0 + _integer(g, "Group number") / 100.0


def column_name(i: int, j: int) -> str:
    """i = grid line number (1-based, along length), j = row index (0 → 'A')."""
    i, j = _integer(i, "Grid line", 1), _integer(j, "Row index")
    if j >= 26:
        raise ValueError("Row index must be in 0..25.")
    return f"{ascii_uppercase[j]}{i}"


def parse_name(name: str):
    """'C4' -> (i=4, j=2). Returns None if the label is malformed."""
    if not isinstance(name, str):
        return None
    name = name.strip().upper()
    if len(name) < 2 or name[0] not in ascii_uppercase or not name[1:].isascii() or not name[1:].isdigit():
        return None
    try:
        i = int(name[1:])
    except ValueError:
        return None
    return (i, ascii_uppercase.index(name[0])) if i >= 1 else None


def classify(i: int, j: int, nx: int, ny: int) -> str:
    """Corner / Edge / Interior on an nx × ny column grid (lines 1..nx, rows A..)."""
    nx, ny = _grid(nx, ny)
    i, j = _integer(i, "Grid line", 1), _integer(j, "Row index")
    if i > nx or j >= ny:
        raise ValueError("Column lies outside the grid.")
    on_x = i in (1, nx)
    on_y = j in (0, ny - 1)
    if on_x and on_y:
        return "Corner"
    if on_x or on_y:
        return "Edge"
    return "Interior"


def zone_of_line(i: int, zones: list[dict]):
    """Return the unique matching zone, or None if the line is uncovered."""
    i = _integer(i, "Grid line", 1)
    matches = []
    for z in zones:
        first, last = _integer(z["first"], "First line", 1), _integer(z["last"], "Last line", 1)
        if first > last:
            raise ValueError("Reversed zoning interval.")
        if first <= i <= last:
            matches.append(z["name"])
    if len(matches) > 1:
        raise ValueError(f"Overlapping zones on grid line {i}.")
    return matches[0] if matches else None


def validate_zones(zones, nx):
    """Require exactly one zone on each grid line; no implicit fallback."""
    nx = _integer(nx, "nx", 1)
    for z in zones:
        first, last = _integer(z["first"], "First line", 1), _integer(z["last"], "Last line", 1)
        if first > last or last > nx:
            raise ValueError("Invalid zoning interval.")
        if not isinstance(z["name"], str) or not z["name"].strip():
            raise ValueError("Zone name is required.")
    for i in range(1, nx + 1):
        if zone_of_line(i, zones) is None:
            raise ValueError(f"No zone assigned to grid line {i}.")


def adjacent_pairs(nx: int, ny: int, span_x: float, span_y: float):
    """
    Yield ((i1,j1),(i2,j2),L) for every pair of columns joined by a grid line
    (beam). span_x = spacing between grid lines 1..nx; span_y = spacing A..D.
    """
    nx, ny = _grid(nx, ny)
    span_x, span_y = _positive(span_x, "span_x"), _positive(span_y, "span_y")
    for j in range(ny):
        for i in range(1, nx + 1):
            if i < nx:
                yield (i, j), (i + 1, j), span_x
            if j < ny - 1:
                yield (i, j), (i, j + 1), span_y


@dataclass
class PairResult:
    a: str
    b: str
    L_m: float
    S_a_mm: float
    S_b_mm: float
    delta_mm: float
    ratio: float          # δ / L  (dimensionless)
    limit_mm: float       # diff_ratio · L
    ok_diff: bool
    ok_ang: bool


def check_pairs(settle_mm: dict, nx: int, ny: int, span_x: float, span_y: float,
                limits: dict) -> list[PairResult]:
    """
    settle_mm : {(i,j): total settlement in mm}
    limits    : one entry of ISOLATED_RC / RAFT_RC
    δ = |S_a − S_b| [mm];  L [m];  β = δ/(L·1000)  [IS 1904 Table 1, Skempton–MacDonald]
    """
    nx, ny = _grid(nx, ny)
    values = _settlements(settle_mm, nx, ny)
    return [_pair(a, b, L, values, limits)
            for a, b, L in adjacent_pairs(nx, ny, span_x, span_y)]


def _settlements(settle_mm, nx, ny):
    expected = {(i, j) for j in range(ny) for i in range(1, nx + 1)}
    if set(settle_mm) != expected:
        raise ValueError("Settlement data must contain exactly every grid column.")
    return {k: _finite(v, f"Settlement at {column_name(*k)}") for k, v in settle_mm.items()}


def _pair(a, b, L, values, limits):
    L = _positive(L, "Column separation")
    diff_ratio = _positive(limits["diff_ratio"], "Differential settlement ratio")
    ang_limit = _positive(limits["ang_limit"], "Angular distortion limit")
    Sa, Sb = values[a], values[b]
    d = abs(Sa - Sb)
    # IS 1904:1986 Cl. 16.3.5 and Table 1: convert span m to mm.
    beta = d / (L * 1000.0)
    lim = diff_ratio * L * 1000.0
    return PairResult(column_name(*a), column_name(*b), L, Sa, Sb, d, beta, lim,
                      d <= lim + 1e-9, beta <= ang_limit + 1e-12)


def check_extreme_pair(settle_mm, nx, ny, span_x, span_y, limits):
    """Global maximum/minimum settlement pair per Cl. 16.3.5.
    For ties, select the closest distinct pair (most restrictive ratio).
    Straight-line separation on the uniform rectangular grid is assumed.
    Returns None for a single-column grid.
    """
    nx, ny = _grid(nx, ny)
    sx, sy = _positive(span_x, "span_x"), _positive(span_y, "span_y")
    values = _settlements(settle_mm, nx, ny)
    if len(values) == 1:
        return None
    lo, hi = min(values.values()), max(values.values())
    lows = [k for k,v in values.items() if v == lo]
    highs = [k for k,v in values.items() if v == hi]
    def separation(a, b):
        return math.hypot((a[0]-b[0])*sx, (a[1]-b[1])*sy)
    if lo == hi:
        a, b, L = next(adjacent_pairs(nx, ny, sx, sy))
    else:
        a, b = min(((a,b) for a in lows for b in highs), key=lambda ab: separation(*ab))
        L = separation(a,b)
    return _pair(a, b, L, values, limits)


def fmt_ratio(beta: float) -> str:
    """Angular distortion as '1/n' (or 'nil')."""
    beta = _finite(beta, "Angular distortion")
    if beta < 0:
        raise ValueError("Angular distortion must be nonnegative.")
    if beta == 0:
        return "nil"
    inv = 1.0 / beta
    return f"1/{int(round(inv))}" if math.isfinite(inv) and inv >= 1 else f"{beta:.3g}"


def sqrt_size(P_kN: float, q_kPa: float, step: float = 0.1) -> float:
    """Square footing side for a given gross bearing pressure, rounded UP to `step` (m)."""
    P_kN, q_kPa, step = _positive(P_kN, "Load"), _positive(q_kPa, "Pressure"), _positive(step, "Sizing increment")
    side = math.sqrt(P_kN / q_kPa)
    result = math.ceil(side / step) * step
    if result < side:
        result += step
    return result
