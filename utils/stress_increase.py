"""
utils/stress_increase.py
Pure-domain vertical stress increase models (Boussinesq 1885 & 2:1 method)
and arbitrary-point Newmark (1935) superposition.

Design Principles (SOLID)
-------------------------
- Single Responsibility (SRP):
  * `StressDistributionModel` subclasses each encapsulate one analytical stress
    dispersion law (Boussinesq corner, Boussinesq centre, 2:1 method).
  * `SuperpositionStressCalculator` handles arbitrary-point and multi-footing
    superposition using signed corner rectangles.
  * `StressProfileAnalyzer` handles depth profiles and influence-depth queries.
- Open/Closed (OCP) & Liskov Substitution (LSP):
  Any concrete `StressDistributionModel` (e.g., Westergaard in future) can be
  substituted wherever `StressDistributionModel` is injected, including into
  `ConsolidationSettlementCalculator`.
- Dependency Inversion (DIP):
  `StressProfileAnalyzer` and `utils.settlement` depend on the abstract
  `StressDistributionModel` interface rather than hard-coded conditionals.

References
----------
- Boussinesq, J. (1885) — Application des potentiels à l'étude de l'équilibre
  et du mouvement des solides élastiques
- Newmark, N. M. (1935) — Simplified computation of vertical pressures in elastic
  foundations, Univ. of Illinois Eng. Exp. Stn. Circular 24
- Das, B. M. (2016) — Principles of Foundation Engineering (8th ed.), Sec. 5.5, Eq. 5.37
- IS 8009:1976 Part 1 — Code of Practice for Calculation of Settlements of Foundations
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import math
from typing import Any, Mapping, Sequence

import numpy as np

from utils.models import SoilProfile, StressProfileResult


# ---------------------------------------------------------------------------
# Strategy Interface (OCP / LSP / DIP)
# ---------------------------------------------------------------------------
class StressDistributionModel(ABC):
    """Abstract vertical stress increase model Δσz(q, B, L, z)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable method identifier."""

    @property
    @abstractmethod
    def citation(self) -> str:
        """Exact standard clause or textbook reference."""

    @abstractmethod
    def delta_sigma(
        self, q: float, B: float, L: float, z: float | np.ndarray
    ) -> float | np.ndarray:
        """
        Compute vertical stress increase Δσz (kPa) at depth z (m) below
        a uniformly loaded rectangle (B × L, m) carrying pressure q (kPa).
        """


# ---------------------------------------------------------------------------
# Concrete Stress Distribution Models
# ---------------------------------------------------------------------------
class BoussinesqCornerModel(StressDistributionModel):
    """
    Exact Boussinesq (1885) vertical stress increase below the CORNER of a
    uniformly loaded flexible rectangular area B × L.

    Cite: Boussinesq (1885); Newmark (1935); Das (2016) Eq. 5.37
    """

    @property
    def name(self) -> str:
        return "boussinesq_corner"

    @property
    def citation(self) -> str:
        return "Boussinesq (1885); Das (2016) Eq. 5.37"

    @staticmethod
    def _corner_scalar(q: float, B: float, L: float, z: float) -> float:
        if B <= 0.0 or L <= 0.0 or q == 0.0:
            return 0.0
        if z <= 0.0:
            # Surface boundary limit right under loaded corner (z → 0+):
            # Iσ → 0.25 at exact corner of infinite half-space, or q inside loaded area;
            # preserved as q at z=0 to match profile continuity convention at z=0+.
            return float(q)

        # Das (2016) Eq. 5.37 dimensionless geometry ratios: m1 = B/z, n1 = L/z
        m1 = float(B) / float(z)
        n1 = float(L) / float(z)
        m2_n2_1 = 1.0 + m1 * m1 + n1 * n1  # (1 + m1² + n1²)
        mn = m1 * n1
        sqrt_term = math.sqrt(m2_n2_1)

        # First term of Das (2016) Eq. 5.37:
        # [2*m1*n1*sqrt(1+m1²+n1²) / (1+m1²+n1²+m1²*n1²)] * [(2+m1²+n1²)/(1+m1²+n1²)]
        term1 = (2.0 * mn * sqrt_term * (m2_n2_1 + 1.0)) / (
            m2_n2_1 * (m2_n2_1 + mn * mn)
        )

        # Second term of Das (2016) Eq. 5.37:
        # arctan(2*m1*n1*sqrt(1+m1²+n1²) / (1+m1²+n1² - m1²*n1²))
        # Using atan2(num, den) naturally places angle in [0, π] when den <= 0,
        # which is equivalent to adding π when (1 + m1² + n1² - m1²*n1²) < 0.
        num2 = 2.0 * mn * sqrt_term
        den2 = m2_n2_1 - mn * mn
        term2 = math.atan2(num2, den2)  # Das (2016) Eq. 5.37 (continuous in [0, π])

        # Influence factor Iσ = (term1 + term2) / (4π) — Das (2016) Eq. 5.37
        i_sigma = (term1 + term2) / (4.0 * math.pi)
        # Δσz = q · Iσ — Das (2016) Eq. 5.37
        return float(q) * i_sigma

    def delta_sigma(
        self, q: float, B: float, L: float, z: float | np.ndarray
    ) -> float | np.ndarray:
        if np.isscalar(z):
            return self._corner_scalar(q, B, L, float(z))
        z_arr = np.asarray(z, dtype=float)
        out = np.empty_like(z_arr)
        for idx, zi in enumerate(z_arr.flat):
            out.flat[idx] = self._corner_scalar(q, B, L, float(zi))
        return out


class BoussinesqCentreModel(StressDistributionModel):
    """
    Boussinesq vertical stress increase below the CENTRE of a uniformly loaded
    rectangle B × L via Newmark (1935) superposition of 4 (B/2 × L/2) quadrants.

    Cite: Newmark (1935); Das (2016) Sec. 5.5
    """

    def __init__(self, corner_model: BoussinesqCornerModel | None = None) -> None:
        self._corner = corner_model or BoussinesqCornerModel()

    @property
    def name(self) -> str:
        return "boussinesq_centre"

    @property
    def citation(self) -> str:
        return "Boussinesq (1885); Newmark (1935) superposition; Das (2016) Sec. 5.5"

    def delta_sigma(
        self, q: float, B: float, L: float, z: float | np.ndarray
    ) -> float | np.ndarray:
        # Superposition of 4 symmetric corner rectangles of size (B/2 × L/2) — Das (2016) Sec. 5.5
        return 4.0 * self._corner.delta_sigma(q, B / 2.0, L / 2.0, z)


class TwoToOneMethodModel(StressDistributionModel):
    """
    Approximate 2V:1H stress dispersion method:
        Δσz = (q · B · L) / ((B + z) · (L + z))

    Cite: IS 8009:1976 Part 1; Das (2016) Eq. 5.41
    """

    @property
    def name(self) -> str:
        return "2to1"

    @property
    def citation(self) -> str:
        return "IS 8009:1976 Part 1; Das (2016) Eq. 5.41 (2:1 load spread)"

    def delta_sigma(
        self, q: float, B: float, L: float, z: float | np.ndarray
    ) -> float | np.ndarray:
        if np.isscalar(z):
            zf = float(z)
            if zf <= 0.0:
                return float(q)
            # IS 8009:1976 Part 1; Das (2016) Eq. 5.41: Δσz = q·B·L / ((B+z)(L+z))
            return float(q) * float(B) * float(L) / ((float(B) + zf) * (float(L) + zf))

        z_arr = np.asarray(z, dtype=float)
        # Vectorized 2:1 stress dispersion — Das (2016) Eq. 5.41
        return np.where(
            z_arr <= 0.0,
            float(q),
            float(q) * float(B) * float(L) / ((float(B) + z_arr) * (float(L) + z_arr)),
        )


# ---------------------------------------------------------------------------
# Superposition & Profile Analysis Services
# ---------------------------------------------------------------------------
class SuperpositionStressCalculator:
    """
    Computes Boussinesq vertical stress increase under any plan coordinate (x, y)
    inside or outside a loaded rectangle [0, B] × [0, L] using signed corner
    superposition.

    Cite: Newmark (1935); Das (2016) Sec. 5.5
    """

    def __init__(self, corner_model: BoussinesqCornerModel | None = None) -> None:
        self._corner = corner_model or BoussinesqCornerModel()

    def _signed_corner(self, q: float, u: float, v: float, z: float) -> float:
        if u == 0.0 or v == 0.0:
            return 0.0
        sign = 1.0 if (u * v) > 0.0 else -1.0
        return sign * float(self._corner.delta_sigma(q, abs(u), abs(v), z))

    def at_point(
        self, q: float, B: float, L: float, x_offset: float, y_offset: float, z: float
    ) -> float:
        """
        Δσz at depth z below (x_offset, y_offset) relative to rectangle corner (0, 0).
        Valid for interior, edge, corner, and exterior points via algebraic
        corner superposition:
            Δσz = Σ signed_corner(B - x, L - y) − ...

        Cite: Newmark (1935) superposition; Das (2016) Sec. 5.5
        """
        if z <= 0.0:
            inside = (0.0 <= x_offset <= B) and (0.0 <= y_offset <= L)
            return float(q) if inside else 0.0

        a1, a2 = -float(x_offset), float(B) - float(x_offset)
        b1, b2 = -float(y_offset), float(L) - float(y_offset)

        # Signed 4-corner algebraic superposition — Newmark (1935)
        return (
            self._signed_corner(q, a2, b2, z)
            - self._signed_corner(q, a1, b2, z)
            - self._signed_corner(q, a2, b1, z)
            + self._signed_corner(q, a1, b1, z)
        )


class StressProfileAnalyzer:
    """
    Produces Δσz(z) depth profiles and stress-bulb influence depths using any
    injected `StressDistributionModel` (DIP).
    """

    _MODEL_REGISTRY: dict[str, StressDistributionModel] = {
        "boussinesq_centre": BoussinesqCentreModel(),
        "boussinesq_corner": BoussinesqCornerModel(),
        "2to1": TwoToOneMethodModel(),
    }

    @classmethod
    def get_model(cls, method: str) -> StressDistributionModel:
        """Resolve method key to a StressDistributionModel instance."""
        if method not in cls._MODEL_REGISTRY:
            raise ValueError(
                f"Unknown method '{method}'. Choose from {tuple(cls._MODEL_REGISTRY.keys())}."
            )
        return cls._MODEL_REGISTRY[method]

    def compute_profile(
        self,
        model: StressDistributionModel,
        q: float,
        B: float,
        L: float,
        z_max: float,
        n_points: int = 50,
    ) -> StressProfileResult:
        """Evaluate Δσz along [0, z_max] with `n_points` evenly spaced depths."""
        if z_max <= 0.0:
            raise ValueError(f"z_max ({z_max} m) must be > 0.")
        if n_points < 2:
            raise ValueError("n_points must be >= 2.")

        z_arr = np.linspace(0.0, float(z_max), n_points)
        ds_arr = np.asarray(model.delta_sigma(q, B, L, z_arr), dtype=float)
        return StressProfileResult(
            z_m=z_arr,
            delta_sigma_kPa=ds_arr,
            method_name=model.name,
            q_net_kPa=float(q),
        )

    def influence_depth(
        self,
        model: StressDistributionModel,
        q: float,
        B: float,
        L: float,
        threshold: float = 0.1,
        n_points: int = 500,
    ) -> float:
        """
        Find depth z* below footing base where Δσz / q <= threshold (default 0.10,
        i.e., the 10% pressure-bulb depth per IS 8009:1976 Part 1).
        """
        z_max = 5.0 * float(B)
        if q <= 0.0:
            return z_max
        profile = self.compute_profile(model, q, B, L, z_max, n_points=n_points)
        ratio = profile.delta_sigma_kPa / float(q)
        idx = np.where(ratio <= threshold)[0]
        if len(idx) == 0:
            return z_max
        return float(profile.z_m[idx[0]])


# ---------------------------------------------------------------------------
# Functional Facade (100% Backward-Compatible with Streamlit P4 & P5 UI)
# ---------------------------------------------------------------------------
_CORNER_MODEL = BoussinesqCornerModel()
_CENTRE_MODEL = BoussinesqCentreModel(_CORNER_MODEL)
_TWO_TO_ONE_MODEL = TwoToOneMethodModel()
_SUPERPOS_CALC = SuperpositionStressCalculator(_CORNER_MODEL)
_PROFILE_ANALYZER = StressProfileAnalyzer()


def boussinesq_corner(
    q: float, B: float, L: float, z: float | np.ndarray
) -> float | np.ndarray:
    """
    Boussinesq vertical stress increase Δσz below the corner of rectangle B × L.

    Cite: Boussinesq (1885); Das (2016) Eq. 5.37
    """
    return _CORNER_MODEL.delta_sigma(q, B, L, z)


def stress_increase_centre(
    q: float, B: float, L: float, z: float | np.ndarray
) -> float | np.ndarray:
    """
    Boussinesq vertical stress increase Δσz below the centre of rectangle B × L.

    Cite: Newmark (1935) superposition; Das (2016) Sec. 5.5
    """
    return _CENTRE_MODEL.delta_sigma(q, B, L, z)


def stress_increase_point(
    q: float, B: float, L: float, x_offset: float, y_offset: float, z: float
) -> float:
    """
    Boussinesq vertical stress increase Δσz below an arbitrary plan offset.

    Cite: Newmark (1935) superposition; Das (2016) Sec. 5.5
    """
    return _SUPERPOS_CALC.at_point(q, B, L, x_offset, y_offset, z)


def stress_increase_2to1(
    q: float, B: float, L: float, z: float | np.ndarray
) -> float | np.ndarray:
    """
    2:1 approximate vertical stress increase Δσz.

    Cite: IS 8009:1976 Part 1; Das (2016) Eq. 5.41
    """
    return _TWO_TO_ONE_MODEL.delta_sigma(q, B, L, z)


def stress_profile(
    q: float,
    B: float,
    L: float,
    z_max: float,
    method: str = "boussinesq_centre",
    n_points: int = 50,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute (z_array, delta_sigma_array) from z = 0 to z_max for the chosen method.
    """
    model = StressProfileAnalyzer.get_model(method)
    res = _PROFILE_ANALYZER.compute_profile(model, q, B, L, z_max, n_points=n_points)
    return res.z_m, res.delta_sigma_kPa


def influence_depth(
    q: float,
    B: float,
    L: float,
    threshold: float = 0.1,
    method: str = "boussinesq_centre",
    n_points: int = 500,
) -> float:
    """
    Depth z* (m) below footing base where Δσz / q <= threshold (default 10%).

    Cite: IS 8009:1976 Part 1 (significant influence depth criterion)
    """
    model = StressProfileAnalyzer.get_model(method)
    return _PROFILE_ANALYZER.influence_depth(
        model, q, B, L, threshold=threshold, n_points=n_points
    )


def effective_stress_profile(
    layers: Sequence[Mapping[str, Any]],
    wt_design_bgl: float,
    z_array: Sequence[float] | np.ndarray,
    Df: float = 0.0,
) -> np.ndarray:
    """
    Compute effective vertical stress σ′v0 (kPa) at depths `z_array` below footing
    base (i.e., `z + Df` m bgl) using exact piecewise water-table integration.

    Cite: Terzaghi (1936); Das (2016) Eq. 2.10
    """
    profile = SoilProfile.from_dicts(layers, wt_design_bgl=wt_design_bgl)
    z_arr = np.asarray(z_array, dtype=float)
    return np.array(
        [
            profile.effective_vertical_stress(float(z) + float(Df), wt_bgl=wt_design_bgl)
            for z in z_arr
        ],
        dtype=float,
    )
