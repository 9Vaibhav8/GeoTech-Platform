"""
utils/is1904.py — IS 1904:1986 settlement-compliance helpers (no Streamlit dependency)

Pure functions so they can be unit-tested and reused by the P5 page.

Sources (cite these in the report):
  [1] IS 1904:1986, Code of practice for design and construction of foundations
      in soils: general requirements — Table 1 (permissible settlement,
      differential settlement and angular distortion).  VERIFY the numbers
      below against your own copy of the standard before submission.
  [2] Skempton & MacDonald (1956), "The allowable settlements of buildings",
      Proc. ICE 5(3) — origin of angular-distortion criteria (δ/L).
  [3] IS 1904:1986 definition: differential settlement is taken between
      ADJACENT columns; angular distortion = δ / L, L = distance between them.
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
    "sand": {"total_mm": 75.0, "diff_ratio": 0.002, "ang_limit": 1.0 / 500.0},
    "clay": {"total_mm": 100.0, "diff_ratio": 0.002, "ang_limit": 1.0 / 500.0},
}


def lambda_factor(g: float) -> float:
    """Load multiplier λ = 1 + g/100 (assignment statement)."""
    return 1.0 + float(g) / 100.0


def column_name(i: int, j: int) -> str:
    """i = grid line number (1-based, along length), j = row index (0 → 'A')."""
    return f"{ascii_uppercase[j]}{i}"


def parse_name(name: str):
    """'C4' -> (i=4, j=2). Returns None if the label is malformed."""
    name = name.strip().upper()
    if len(name) < 2 or name[0] not in ascii_uppercase or not name[1:].isdigit():
        return None
    return int(name[1:]), ascii_uppercase.index(name[0])


def classify(i: int, j: int, nx: int, ny: int) -> str:
    """Corner / Edge / Interior on an nx × ny column grid (lines 1..nx, rows A..)."""
    on_x = i in (1, nx)
    on_y = j in (0, ny - 1)
    if on_x and on_y:
        return "Corner"
    if on_x or on_y:
        return "Edge"
    return "Interior"


def zone_of_line(i: int, zones: list[dict]):
    """zones = [{'name':..., 'first':int, 'last':int}, ...]; first match wins."""
    for z in zones:
        if z["first"] <= i <= z["last"]:
            return z["name"]
    return None


def adjacent_pairs(nx: int, ny: int, span_x: float, span_y: float):
    """
    Yield ((i1,j1),(i2,j2),L) for every pair of columns joined by a grid line
    (beam). span_x = spacing between grid lines 1..nx; span_y = spacing A..D.
    """
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
    out = []
    for a, b, L in adjacent_pairs(nx, ny, span_x, span_y):
        Sa, Sb = settle_mm[a], settle_mm[b]
        d = abs(Sa - Sb)
        beta = d / (L * 1000.0)
        lim = limits["diff_ratio"] * L * 1000.0
        out.append(PairResult(
            column_name(*a), column_name(*b), L, Sa, Sb, d, beta, lim,
            d <= lim + 1e-9, beta <= limits["ang_limit"] + 1e-12,
        ))
    return out


def fmt_ratio(beta: float) -> str:
    """Angular distortion as '1/n' (or 'nil')."""
    return "nil" if beta <= 0 else f"1/{int(round(1.0 / beta))}"


def sqrt_size(P_kN: float, q_kPa: float, step: float = 0.1) -> float:
    """Square footing side for a given gross bearing pressure, rounded UP to `step` (m)."""
    return math.ceil(math.sqrt(P_kN / q_kPa) / step - 1e-9) * step