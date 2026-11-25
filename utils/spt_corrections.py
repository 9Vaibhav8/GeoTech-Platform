"""
utils/spt_corrections.py
Pure-domain IS 2131:1981 SPT correction pipeline and Mohr-Coulomb regression.

Design Principles (SOLID)
-------------------------
- Single Responsibility (SRP):
  * `OverburdenCorrectionStrategy` isolates C_N overburden correction.
  * `DilatancyCorrectionStrategy` isolates saturated fine-sand/silt dilatancy.
  * `SPTCorrector` orchestrates the step-by-step SPT correction chain.
  * `MohrCoulombLeastSquaresFitter` handles OLS regression of shear-box tests.
- Open/Closed (OCP) & Liskov Substitution (LSP):
  New overburden formulas (e.g., `LiaoWhitmanOverburden`) or dilatancy rules
  can be plugged in by subclassing the ABCs without changing `SPTCorrector`.
- Dependency Inversion (DIP):
  `SPTCorrector` depends on abstract strategy interfaces (`OverburdenCorrectionStrategy`,
  `DilatancyCorrectionStrategy`) and `SoilProfile` from `utils.models`.

References
----------
- IS 2131:1981 — Method for Standard Penetration Test for Soils:
  * Annex B : Overburden pressure correction (Peck, Hanson & Thornburn 1974)
  * Clause 4.6 : Dilatancy correction (Terzaghi & Peck 1967)
- Liao, S. S. C., & Whitman, R. V. (1986) — Overburden correction factors for SPT
- Das, B. M. (2016) — Principles of Foundation Engineering (8th ed.)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import math
from typing import Any, Mapping, Sequence

import numpy as np

from utils.models import (
    DILATANCY_ELIGIBLE_SYMBOLS,
    MohrCoulombFitResult,
    SPTCorrectionStep,
    SoilProfile,
)


# ---------------------------------------------------------------------------
# Strategy Interfaces (OCP / ISP / DIP)
# ---------------------------------------------------------------------------
class OverburdenCorrectionStrategy(ABC):
    """Abstract strategy for SPT overburden correction factor C_N."""

    @property
    @abstractmethod
    def citation(self) -> str:
        """Code clause or literature source for traceability."""

    @abstractmethod
    def compute_CN(self, sigma_v_kPa: float) -> float:
        """Compute dimensionless overburden correction factor C_N."""


class DilatancyCorrectionStrategy(ABC):
    """Abstract strategy for SPT pore-pressure/dilatancy correction."""

    @property
    @abstractmethod
    def citation(self) -> str:
        """Code clause or literature source for traceability."""

    @abstractmethod
    def apply(
        self, N_corr1: int, symbol: str, depth_m: float, wt_bgl: float
    ) -> tuple[int, bool]:
        """Return (N_corrected, dilatancy_applied)."""


class StrengthEnvelopeFitter(ABC):
    """Abstract interface for shear-strength envelope parameter fitting."""

    @abstractmethod
    def fit(
        self, sigma_n_arr: Sequence[float] | np.ndarray, tau_arr: Sequence[float] | np.ndarray
    ) -> MohrCoulombFitResult:
        """Fit failure envelope parameters to laboratory test data."""


# ---------------------------------------------------------------------------
# Concrete Overburden Strategies
# ---------------------------------------------------------------------------
class PeckHansonThornburnOverburden(OverburdenCorrectionStrategy):
    """
    IS 2131:1981 Annex B — Peck, Hanson & Thornburn (1974) overburden correction.

    Formula (in SI units, σ′v in kPa):
        C_N = 0.77 × log10(2000 / σ′v)   for σ′v >= 25 kPa
        C_N = 2.0                         for σ′v < 25 kPa  (low-stress cap)
        Clamped to [0.5, 2.0].
    """

    def __init__(
        self,
        cn_min: float = 0.5,
        cn_max: float = 2.0,
        sigma_threshold_kPa: float = 25.0,
    ) -> None:
        self.cn_min = cn_min
        self.cn_max = cn_max
        self.sigma_threshold_kPa = sigma_threshold_kPa

    @property
    def citation(self) -> str:
        return "IS 2131:1981 Annex B (Peck, Hanson & Thornburn 1974)"

    def compute_CN(self, sigma_v_kPa: float) -> float:
        if sigma_v_kPa < 0.0:
            raise ValueError(f"Effective stress sigma_v_kPa ({sigma_v_kPa}) cannot be negative.")
        if sigma_v_kPa < self.sigma_threshold_kPa:
            # IS 2131:1981 Annex B low-overburden cap (σ′v < 25 kPa)
            return self.cn_max
        # IS 2131:1981 Annex B; Peck, Hanson & Thornburn (1974): C_N = 0.77*log10(2000/σ′v)
        cn = 0.77 * math.log10(2000.0 / sigma_v_kPa)
        # IS 2131:1981 Annex B practical bounds [0.5, 2.0]
        return max(self.cn_min, min(cn, self.cn_max))


class LiaoWhitmanOverburden(OverburdenCorrectionStrategy):
    """
    Optional alternative overburden strategy (Liao & Whitman 1986) for OCP comparison.

        C_N = sqrt(Pa / σ′v)   where Pa = 100 kPa, capped at 2.0.
    """

    def __init__(self, pa_kPa: float = 100.0, cn_max: float = 2.0) -> None:
        self.pa_kPa = pa_kPa
        self.cn_max = cn_max

    @property
    def citation(self) -> str:
        return "Liao & Whitman (1986) Eq. 4; Das (2016) Eq. 2.26"

    def compute_CN(self, sigma_v_kPa: float) -> float:
        if sigma_v_kPa <= 0.0:
            return self.cn_max
        # Liao & Whitman (1986) Eq. 4: C_N = sqrt(Pa / σ′v), Pa ≈ 100 kPa
        cn = math.sqrt(self.pa_kPa / sigma_v_kPa)
        return min(cn, self.cn_max)


# ---------------------------------------------------------------------------
# Concrete Dilatancy Strategy
# ---------------------------------------------------------------------------
class IS2131DilatancyCorrection(DilatancyCorrectionStrategy):
    """
    IS 2131:1981 Clause 4.6 — Terzaghi & Peck (1967) dilatancy correction.

    Applied ONLY when all three conditions hold:
      1. Fine sand or silt classification (`symbol` in {'SM', 'ML', 'SP'})
      2. Test elevation lies below design water table (`depth_m > wt_bgl`)
      3. Overburden-corrected blow count `N_corr1 > 15`

    Formula:
        N_corrected = 15 + 0.5 × (N_corr1 − 15)
    """

    def __init__(
        self,
        eligible_symbols: frozenset[str] = DILATANCY_ELIGIBLE_SYMBOLS,
        threshold_N: int = 15,
    ) -> None:
        self.eligible_symbols = eligible_symbols
        self.threshold_N = threshold_N

    @property
    def citation(self) -> str:
        return "IS 2131:1981 Cl. 4.6 (Terzaghi & Peck 1967)"

    def apply(
        self, N_corr1: int, symbol: str, depth_m: float, wt_bgl: float
    ) -> tuple[int, bool]:
        should_apply = (
            symbol in self.eligible_symbols
            and depth_m > wt_bgl
            and N_corr1 > self.threshold_N
        )
        if should_apply:
            # IS 2131:1981 Cl. 4.6; Terzaghi & Peck (1967) Art. 54: N_cor = 15 + 0.5*(N' - 15)
            n_corr = int(round(self.threshold_N + 0.5 * (N_corr1 - self.threshold_N)))
            return n_corr, True
        return int(N_corr1), False


# ---------------------------------------------------------------------------
# Orchestrator Service: SPTCorrector (SRP + DIP)
# ---------------------------------------------------------------------------
class SPTCorrector:
    """
    Applies the two-stage IS 2131:1981 SPT correction pipeline across a SoilProfile.
    """

    def __init__(
        self,
        overburden_strategy: OverburdenCorrectionStrategy | None = None,
        dilatancy_strategy: DilatancyCorrectionStrategy | None = None,
    ) -> None:
        self.overburden = overburden_strategy or PeckHansonThornburnOverburden()
        self.dilatancy = dilatancy_strategy or IS2131DilatancyCorrection()

    def correct_profile(
        self, profile: SoilProfile, wt_design_bgl: float | None = None
    ) -> list[SPTCorrectionStep]:
        """
        Compute intermediate and final corrected SPT values for every tested layer.
        Does NOT mutate the input SoilProfile (pure-domain function).
        """
        wt = (
            float(wt_design_bgl)
            if wt_design_bgl is not None
            else (profile.groundwater.wt_design_bgl if profile.groundwater else 0.0)
        )
        steps: list[SPTCorrectionStep] = []

        for idx, layer in enumerate(profile.layers):
            if layer.N_field is None:
                continue

            depth_mid = layer.mid_depth
            # Das (2016) Eq. 2.10; IS 2131:1981 Annex B effective overburden stress
            sigma_v = profile.effective_vertical_stress(depth_mid, wt_bgl=wt)
            cn = self.overburden.compute_CN(sigma_v)
            # IS 2131:1981 Annex B: N' = round(C_N * N_field)
            n_corr1 = int(round(cn * layer.N_field))

            n_corrected, dil_applied = self.dilatancy.apply(
                n_corr1, layer.symbol, depth_mid, wt
            )

            steps.append(
                SPTCorrectionStep(
                    layer_idx=idx,
                    depth_mid_m=depth_mid,
                    sigma_v_kPa=sigma_v,
                    CN=cn,
                    N_field=layer.N_field,
                    N_corr1=n_corr1,
                    dilatancy_applied=dil_applied,
                    N_corrected=n_corrected,
                    overburden_method=self.overburden.citation,
                    dilatancy_method=self.dilatancy.citation,
                )
            )

        return steps


# ---------------------------------------------------------------------------
# Mohr-Coulomb Least-Squares Regression Service
# ---------------------------------------------------------------------------
class MohrCoulombLeastSquaresFitter(StrengthEnvelopeFitter):
    """
    Ordinary least-squares fit of the linear Mohr-Coulomb failure envelope:
        τf = c′ + σn · tan(φ′)

    Cite: Coulomb (1776); Das (2016) Eq. 3.4; IS 2720 Part 13 (Direct shear)
    """

    def fit(
        self, sigma_n_arr: Sequence[float] | np.ndarray, tau_arr: Sequence[float] | np.ndarray
    ) -> MohrCoulombFitResult:
        sigma_n = np.asarray(sigma_n_arr, dtype=float)
        tau = np.asarray(tau_arr, dtype=float)

        if sigma_n.ndim != 1 or tau.ndim != 1:
            raise ValueError("sigma_n_arr and tau_arr must be 1D arrays.")
        if len(sigma_n) != len(tau):
            raise ValueError("sigma_n_arr and tau_arr must have equal length.")
        if len(sigma_n) < 2:
            raise ValueError("At least 2 data points are required for fitting.")
        if np.allclose(sigma_n, sigma_n[0]):
            raise ValueError("Normal stress values must have non-zero variance.")

        # Design matrix A = [1, σn] for OLS model τ = β0 + β1·σn (Das 2016 Eq. 3.4)
        A = np.column_stack([np.ones_like(sigma_n), sigma_n])
        # Normal equations solved via QR/SVD least squares: β = argmin ||Aβ - τ||₂
        beta, _, _, _ = np.linalg.lstsq(A, tau, rcond=None)
        c_prime = float(beta[0])
        tan_phi = float(beta[1])
        # Mohr-Coulomb slope relation: φ′ = arctan(dτ/dσn) — Das (2016) Eq. 3.4
        phi_prime_deg = float(math.degrees(math.atan(tan_phi)))

        # Residuals & coefficient of determination R²
        tau_pred = c_prime + sigma_n * tan_phi
        residuals = tau - tau_pred
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((tau - np.mean(tau)) ** 2))
        # Coefficient of determination R² = 1 − SS_res / SS_tot
        r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 1.0

        return MohrCoulombFitResult(
            c_prime_kPa=c_prime,
            phi_prime_deg=phi_prime_deg,
            r_squared=r_squared,
            n_points=len(sigma_n),
            residuals_kPa=tuple(float(r) for r in residuals),
        )


# ---------------------------------------------------------------------------
# Functional Facade (100% Backward-Compatible with Streamlit P2 UI)
# ---------------------------------------------------------------------------
_DEFAULT_CORRECTOR = SPTCorrector()
_DEFAULT_MC_FITTER = MohrCoulombLeastSquaresFitter()


def effective_stress(
    layers: Sequence[Mapping[str, Any]], depth_m: float, wt_bgl: float
) -> float:
    """
    Compute effective vertical stress σ′v (kPa) at depth_m (m bgl).
    Uses exact piecewise integration across strata and water table.

    Cite: Terzaghi (1936); Das (2016) Eq. 2.10; IS 2131:1981 Annex B
    """
    profile = SoilProfile.from_dicts(layers, wt_design_bgl=wt_bgl)
    return profile.effective_vertical_stress(depth_m, wt_bgl=wt_bgl)


def overburden_correction(sigma_v_kPa: float) -> float:
    """
    IS 2131:1981 Annex B — Peck, Hanson & Thornburn (1974) overburden factor C_N.
    """
    return _DEFAULT_CORRECTOR.overburden.compute_CN(sigma_v_kPa)


def dilatancy_correction(
    N_corr1: int, symbol: str, depth_m: float, wt_bgl: float
) -> tuple[int, bool]:
    """
    IS 2131:1981 Cl. 4.6 — Terzaghi & Peck (1967) dilatancy correction.
    """
    return _DEFAULT_CORRECTOR.dilatancy.apply(N_corr1, symbol, depth_m, wt_bgl)


def correct_spt(
    layers: list[dict[str, Any]], wt_design_bgl: float
) -> list[dict[str, Any]]:
    """
    Apply full IS 2131:1981 correction chain to session-state layer dicts.
    Updates `layer["N_corrected"]` in place for downstream P5 settlement usage
    and returns step-by-step trace dictionaries for P2 display.
    """
    profile = SoilProfile.from_dicts(layers, wt_design_bgl=wt_design_bgl)
    steps = _DEFAULT_CORRECTOR.correct_profile(profile, wt_design_bgl=wt_design_bgl)

    results: list[dict[str, Any]] = []
    for step in steps:
        layers[step.layer_idx]["N_corrected"] = step.N_corrected
        results.append(step.to_dict())
    return results


def fit_mohr_coulomb(
    sigma_n_arr: Sequence[float] | np.ndarray,
    tau_arr: Sequence[float] | np.ndarray,
) -> tuple[float, float, float]:
    """
    Least-squares fit of τ = c′ + σn · tan(φ′).
    Returns (c_prime_kPa, phi_prime_deg, r_squared).

    Cite: Das (2016) Eq. 3.4; IS 2131:1981 (shear-box calibration)
    """
    res = _DEFAULT_MC_FITTER.fit(sigma_n_arr, tau_arr)
    return res.c_prime_kPa, res.phi_prime_deg, res.r_squared
