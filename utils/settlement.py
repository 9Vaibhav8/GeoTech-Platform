"""
utils/settlement.py
Pure-domain immediate settlement (Schmertmann et al. 1978) and 1D primary
consolidation settlement & time-rate curves (Terzaghi 1943; IS 8009:1976).

Design Principles (SOLID)
-------------------------
- Single Responsibility (SRP):
  * `SchmertmannModulusCorrelation` converts corrected SPT N to Es.
  * `SchmertmannStrainInfluence` computes Iz(z) and influence depths.
  * `SchmertmannSettlementCalculator` evaluates immediate granular settlement.
  * `ConsolidationSettlementCalculator` evaluates 1D NC/OC/OC→NC clay settlement.
  * `TimeRateConsolidationModel` evaluates Terzaghi U(Tv) and S(t) curves.
- Open/Closed (OCP) & Dependency Inversion (DIP):
  Calculators depend on abstract `SoilModulusCorrelation`, `StrainInfluenceProfile`,
  and `StressDistributionModel` interfaces, making correlations or stress theories
  swappable without editing calculation logic.

References
----------
- Schmertmann, J. H., Hartman, J. P., & Brown, P. R. (1978) — Improved strain
  influence factor diagrams, J. Geotech. Eng. Div., ASCE, 104(GT8), 1131–1135
- Meyerhof, G. G. (1956) — Penetration tests and bearing capacity of cohesionless soils
- Terzaghi, K. (1943) — Theoretical Soil Mechanics (1D consolidation theory)
- IS 8009:1976 Part 1 — Code of Practice for Calculation of Settlements of Foundations
- Das, B. M. (2016) — Principles of Foundation Engineering (8th ed.),
  Eq. 5.50–5.53, Table 5.6, Eq. 7.21–7.23, Eq. 7.56–7.57
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import math
from typing import Any, Mapping, Sequence

import numpy as np

from utils.models import (
    ConsolidationRegime,
    ConsolidationResult,
    ConsolidationSublayerResult,
    DrainageCondition,
    FootingGeometry,
    FoundationLoad,
    GAMMA_W,
    ProfileValidationReport,
    SECONDS_PER_YEAR,
    SchmertmannResult,
    SchmertmannSublayerResult,
    SoilLayer,
    SoilProfile,
    SoilProfileValidationError,
    TimeSettlementResult,
    validate_soil_layers,
)
from utils.stress_increase import BoussinesqCentreModel, StressDistributionModel


# ---------------------------------------------------------------------------
# Shared Net Foundation Pressure Helper
# ---------------------------------------------------------------------------
def compute_net_foundation_pressure(
    profile: SoilProfile,
    footing: FootingGeometry,
    load: FoundationLoad,
    wt_design_bgl: float | None = None,
) -> float:
    """
    Compute net foundation pressure Δp (kPa) at founding depth Df:
        Δp = P / (B · L) − σ′v0(Df)

    Uses effective vertical overburden at Df (accounting for water table if
    wt_design_bgl < Df), clamped to a small positive floor only when needed to
    prevent divide-by-zero in embedment factor C1.

    Cite: Schmertmann et al. (1978) Eq. 1; Das (2016) Eq. 5.50–5.51
    """
    q_gross = load.P_kN / footing.area
    # Effective overburden stress at founding base Df — Das (2016) Eq. 2.10
    sigma_v0_df = profile.effective_vertical_stress(footing.Df, wt_bgl=wt_design_bgl)
    # Net pressure Δp = q_gross − σ′v0(Df) — Schmertmann et al. (1978) Eq. 1
    delta_p = q_gross - sigma_v0_df
    return max(delta_p, 1.0)


# ---------------------------------------------------------------------------
# Strategy Interfaces (OCP / ISP / DIP)
# ---------------------------------------------------------------------------
class SoilModulusCorrelation(ABC):
    """Abstract correlation for equivalent elastic Young's modulus Es (kPa)."""

    @property
    @abstractmethod
    def citation(self) -> str:
        """Source citation for Es correlation."""

    @abstractmethod
    def estimate_Es_kPa(self, layer: SoilLayer) -> float:
        """Estimate drained elastic modulus Es (kPa) for a granular SoilLayer."""


class StrainInfluenceProfile(ABC):
    """Abstract vertical strain influence factor distribution Iz(z)."""

    @abstractmethod
    def influence_bounds(
        self, footing: FootingGeometry
    ) -> tuple[float, float, float]:
        """Return (Iz_surface, z1_peak_depth_m, z2_cutoff_depth_m)."""

    @abstractmethod
    def Iz_at(
        self, z: float, footing: FootingGeometry, Iz_peak: float
    ) -> float:
        """Evaluate strain influence factor Iz at depth z below footing base."""


# ---------------------------------------------------------------------------
# Concrete Strategies for Schmertmann (1978)
# ---------------------------------------------------------------------------
class SchmertmannModulusCorrelation(SoilModulusCorrelation):
    """
    SPT-based elastic modulus correlation for granular soils:
        Sand   : Es = 500  × (N_corr + 15)   [kPa]
        Gravel : Es = 1000 × (N_corr + 15)   [kPa]

    Cite: Meyerhof (1956); Schmertmann et al. (1978); Das (2016) Table 5.6
    """

    def __init__(self, default_N: int = 10) -> None:
        self.default_N = default_N

    @property
    def citation(self) -> str:
        return "Meyerhof (1956); Schmertmann et al. (1978); Das (2016) Table 5.6"

    def estimate_Es_kPa(self, layer: SoilLayer) -> float:
        n_val = layer.effective_N if layer.effective_N is not None else self.default_N
        return self.from_N(n_val, "gravel" if layer.is_gravel else "sand")

    @staticmethod
    def from_N(N_corrected: int | float | None, soil_type: str = "sand") -> float:
        """
        Compute Es (kPa) from corrected SPT N and granular soil class.

        Cite: Meyerhof (1956); Das (2016) Table 5.6
        """
        n_eff = max(1, int(round(N_corrected))) if N_corrected else 5
        if soil_type.lower() in ("gravel", "gw", "gp", "gm", "gc"):
            # Gravel modulus correlation: Es = 1000 * (N + 15) kPa — Das (2016) Table 5.6
            return 1000.0 * (n_eff + 15)
        # Sand modulus correlation: Es = 500 * (N + 15) kPa — Meyerhof (1956); Das (2016) Table 5.6
        return 500.0 * (n_eff + 15)


class SchmertmannStrainInfluence(StrainInfluenceProfile):
    """
    Schmertmann, Hartman & Brown (1978) bilinear strain influence diagram Iz(z):
      - Axisymmetric (square/circular, L/B = 1):
          Iz(0) = 0.1,  z1 = 0.5·B,  z2 = 2.0·B
      - Plane strain (strip, L/B >= 10):
          Iz(0) = 0.2,  z1 = 1.0·B,  z2 = 4.0·B
      - Rectangular (1 < L/B < 10):
          Optional smooth linear interpolation in L/B between axisymmetric and
          strip bounds, or discrete square/strip selection when disabled.

    Cite: Schmertmann et al. (1978) Fig. 4; Das (2016) Fig. 5.20 & Eq. 5.53
    """

    def __init__(self, interpolate_rectangular: bool = False) -> None:
        self.interpolate_rectangular = interpolate_rectangular

    def influence_bounds(
        self, footing: FootingGeometry
    ) -> tuple[float, float, float]:
        B = footing.B
        if footing.is_strip:
            # Plane strain (strip, L/B >= 10) — Schmertmann et al. (1978) Fig. 4
            return 0.2, 1.0 * B, 4.0 * B

        if self.interpolate_rectangular and 1.0 < footing.aspect_ratio < 10.0:
            # Linear interpolation between L/B=1 and L/B=10 — Schmertmann et al. (1978)
            w = (footing.aspect_ratio - 1.0) / 9.0
            iz0 = 0.1 + 0.1 * w
            z1 = (0.5 + 0.5 * w) * B
            z2 = (2.0 + 2.0 * w) * B
            return iz0, z1, z2

        # Axisymmetric (square/circular) — Schmertmann et al. (1978) Fig. 4
        return 0.1, 0.5 * B, 2.0 * B

    def Iz_at(
        self, z: float, footing: FootingGeometry, Iz_peak: float
    ) -> float:
        iz0, z1, z2 = self.influence_bounds(footing)
        if z <= 0.0:
            return iz0
        if z <= z1:
            # Ascending linear branch [0, z1] — Schmertmann et al. (1978) Fig. 4
            return iz0 + (Iz_peak - iz0) * (z / z1)
        if z <= z2:
            # Descending linear branch [z1, z2] — Schmertmann et al. (1978) Fig. 4
            return Iz_peak * (z2 - z) / (z2 - z1)
        return 0.0


# ---------------------------------------------------------------------------
# Immediate Settlement Calculator — Schmertmann et al. (1978)
# ---------------------------------------------------------------------------
class SchmertmannSettlementCalculator:
    """
    Computes immediate elastic settlement S_i of footings over granular strata
    using sublayers <= 0.5 m thick.

    Cite: Schmertmann et al. (1978) Eq. 1–4; IS 8009:1976 Part 1; Das (2016) Eq. 5.50–5.53
    """

    def __init__(
        self,
        modulus_correlation: SoilModulusCorrelation | None = None,
        influence_profile: StrainInfluenceProfile | None = None,
        max_sublayer_thickness_m: float = 0.5,
    ) -> None:
        if max_sublayer_thickness_m <= 0.0 or max_sublayer_thickness_m > 0.5:
            raise ValueError("max_sublayer_thickness_m must lie in (0.0, 0.5] m.")
        self.modulus = modulus_correlation or SchmertmannModulusCorrelation()
        self.influence = influence_profile or SchmertmannStrainInfluence()
        self.max_sublayer_thickness_m = max_sublayer_thickness_m

    def calculate(
        self,
        profile: SoilProfile,
        footing: FootingGeometry,
        load: FoundationLoad,
        wt_design_bgl: float | None = None,
        t_years: float = 50.0,
    ) -> SchmertmannResult:
        _, z1_peak, z2_max = self.influence.influence_bounds(footing)
        # Validate continuous strata from 0.0 m through founding depth and 2B/4B influence depth
        profile.validate(
            required_start_m=0.0,
            founding_depth_m=footing.Df,
            required_end_m=footing.Df + z2_max,
        ).raise_if_invalid()

        delta_p = compute_net_foundation_pressure(
            profile, footing, load, wt_design_bgl=wt_design_bgl
        )
        sigma_v0 = profile.effective_vertical_stress(
            footing.Df, wt_bgl=wt_design_bgl
        )

        # Embedment correction factor C1 >= 0.5 — Schmertmann et al. (1978) Eq. 2; Das (2016) Eq. 5.51
        C1 = max(0.5, 1.0 - 0.5 * (sigma_v0 / delta_p))
        # Creep time correction factor C2 — Schmertmann et al. (1978) Eq. 3; Das (2016) Eq. 5.52
        C2 = 1.0 + 0.2 * math.log10(max(float(t_years), 0.1) / 0.1)

        # Effective vertical stress at peak influence depth (Df + z1) — Das (2016) Eq. 5.53
        sigma_vp = profile.effective_vertical_stress(
            footing.Df + z1_peak, wt_bgl=wt_design_bgl
        )
        if sigma_vp > 0.0 and delta_p > 0.0:
            # Peak strain influence factor Izp — Schmertmann et al. (1978) Eq. 4; Das (2016) Eq. 5.53
            Iz_peak = 0.5 + 0.1 * math.sqrt(delta_p / sigma_vp)
        else:
            Iz_peak = 0.6

        z_start = footing.Df
        z_end = footing.Df + z2_max
        sublayers: list[SchmertmannSublayerResult] = []
        sum_iz_over_es_dz = 0.0

        for lyr in profile.layers:
            seg_top = max(lyr.depth_top, z_start)
            seg_bot = min(lyr.depth_bot, z_end)
            if seg_top >= seg_bot:
                continue
            # Only granular (non-clay) layers contribute to immediate Schmertmann settlement
            if lyr.is_clay:
                continue

            Es = self.modulus.estimate_Es_kPa(lyr)
            z = seg_top
            while z < seg_bot - 1e-12:
                dz = min(self.max_sublayer_thickness_m, seg_bot - z)
                z_mid_bgl = z + 0.5 * dz
                z_mid = z_mid_bgl - footing.Df

                Iz = self.influence.Iz_at(z_mid, footing, Iz_peak)
                if Iz <= 0.0:
                    z += dz
                    continue

                # Sublayer contribution (Iz / Es) * Δz — Schmertmann et al. (1978) Eq. 1
                contrib = (Iz / Es) * dz
                sum_iz_over_es_dz += contrib
                sublayers.append(
                    SchmertmannSublayerResult(
                        z_top_m=z - footing.Df,
                        z_bot_m=(z + dz) - footing.Df,
                        z_mid_m=z_mid,
                        layer_name=lyr.name,
                        symbol=lyr.symbol,
                        Es_kPa=Es,
                        Iz=Iz,
                        Iz_over_Es=Iz / Es,
                        dz_m=dz,
                        contrib_m=contrib,
                    )
                )
                z += dz

        # Total immediate settlement Si (m) = C1 * C2 * Δp * Σ(Iz/Es * Δz)
        # Cite: Schmertmann et al. (1978) Eq. 1; Das (2016) Eq. 5.50
        S_i_m = C1 * C2 * delta_p * sum_iz_over_es_dz

        return SchmertmannResult(
            S_mm=S_i_m * 1000.0,
            C1=C1,
            C2=C2,
            delta_p_kPa=delta_p,
            Iz_peak=Iz_peak,
            sigma_v0_kPa=sigma_v0,
            sublayers=tuple(sublayers),
        )


# ---------------------------------------------------------------------------
# 1D Consolidation Settlement Calculator — Terzaghi (1943) / IS 8009:1976
# ---------------------------------------------------------------------------
class ConsolidationSettlementCalculator:
    """
    Computes 1D primary consolidation settlement S_c for NC, OC, and OC→NC
    clay sublayers (<= 0.5 m thick) using an injected `StressDistributionModel`.

    Cite: Terzaghi (1943); IS 8009:1976 Part 1 Cl. 5; Das (2016) Eq. 7.21–7.23
    """

    def __init__(
        self,
        stress_model: StressDistributionModel | None = None,
        max_sublayer_thickness_m: float = 0.5,
    ) -> None:
        if max_sublayer_thickness_m <= 0.0 or max_sublayer_thickness_m > 0.5:
            raise ValueError("max_sublayer_thickness_m must lie in (0.0, 0.5] m.")
        self.stress_model = stress_model or BoussinesqCentreModel()
        self.max_sublayer_thickness_m = max_sublayer_thickness_m

    @staticmethod
    def compute_sublayer(
        H_m: float,
        e0: float,
        Cc: float,
        Cr: float,
        sigma_v0_kPa: float,
        Pc_kPa: float,
        delta_sigma_kPa: float,
    ) -> tuple[float, ConsolidationRegime]:
        """
        Compute 1D consolidation settlement (m) of one clay sublayer of thickness H_m.

        Cite: Terzaghi (1943); Das (2016) Eq. 7.21–7.23; IS 8009:1976 Part 1 Cl. 5
        """
        sigma_f = sigma_v0_kPa + delta_sigma_kPa
        factor = H_m / (1.0 + e0)

        if sigma_v0_kPa <= 0.0 or sigma_f <= sigma_v0_kPa:
            return 0.0, "No load"

        if sigma_v0_kPa >= Pc_kPa:
            # Case 1 — Normally Consolidated (σ′v0 >= Pc): Das (2016) Eq. 7.21
            sc = Cc * factor * math.log10(sigma_f / sigma_v0_kPa)
            return sc, "NC"

        if sigma_f <= Pc_kPa:
            # Case 2 — Overconsolidated remaining OC (σ′v0 + Δσ <= Pc): Das (2016) Eq. 7.22
            sc = Cr * factor * math.log10(sigma_f / sigma_v0_kPa)
            return sc, "OC"

        # Case 3 — Overconsolidated crossing Pc (σ′v0 < Pc < σ′v0 + Δσ): Das (2016) Eq. 7.23
        sc = (
            Cr * factor * math.log10(Pc_kPa / sigma_v0_kPa)
            + Cc * factor * math.log10(sigma_f / Pc_kPa)
        )
        return sc, "OC→NC"

    def calculate(
        self,
        profile: SoilProfile,
        footing: FootingGeometry,
        load: FoundationLoad,
        wt_design_bgl: float | None = None,
        sublayer_thickness: float | None = None,
        required_depth_m: float | None = None,
    ) -> ConsolidationResult:
        dz_limit = (
            float(sublayer_thickness)
            if sublayer_thickness is not None
            else self.max_sublayer_thickness_m
        )
        if dz_limit <= 0.0 or dz_limit > 0.5:
            raise ValueError(
                f"sublayer_thickness ({dz_limit} m) must satisfy 0 < dz <= 0.5 m per spec."
            )

        max_clay_bot = max(
            (lyr.depth_bot for lyr in profile.layers if lyr.is_clay),
            default=footing.Df,
        )
        req_end = (
            float(required_depth_m)
            if required_depth_m is not None
            else max(footing.Df, max_clay_bot)
        )
        # Validate continuous strata from 0.0 m through Df and required clay analysis depth
        profile.validate(
            required_start_m=0.0,
            founding_depth_m=footing.Df,
            required_end_m=req_end,
        ).raise_if_invalid()

        delta_p = compute_net_foundation_pressure(
            profile, footing, load, wt_design_bgl=wt_design_bgl
        )
        sublayers: list[ConsolidationSublayerResult] = []
        s_total_m = 0.0

        for lyr in profile.layers:
            if not lyr.is_clay:
                continue
            params = lyr.consolidation_params
            if params is None:
                continue

            lyr_top = max(lyr.depth_top, footing.Df)
            lyr_bot = lyr.depth_bot
            if lyr_top >= lyr_bot:
                continue

            z = lyr_top
            while z < lyr_bot - 1e-12:
                dz = min(dz_limit, lyr_bot - z)
                z_mid_bgl = z + 0.5 * dz
                z_below_footing = z_mid_bgl - footing.Df

                sigma_v0 = profile.effective_vertical_stress(
                    z_mid_bgl, wt_bgl=wt_design_bgl
                )
                # Stress increment Δσz at clay sublayer midpoint — Das (2016) Eq. 5.37 / Sec. 5.5
                delta_sigma = float(
                    self.stress_model.delta_sigma(
                        delta_p, footing.B, footing.L, z_below_footing
                    )
                )

                sc_m, regime = self.compute_sublayer(
                    dz, params.e0, params.Cc, params.Cr, sigma_v0, params.Pc_kPa, delta_sigma
                )
                s_total_m += sc_m
                sublayers.append(
                    ConsolidationSublayerResult(
                        z_mid_bgl_m=z_mid_bgl,
                        z_below_footing_m=z_below_footing,
                        layer_name=lyr.name,
                        sigma_v0_kPa=sigma_v0,
                        delta_sigma_kPa=delta_sigma,
                        sigma_f_kPa=sigma_v0 + delta_sigma,
                        Pc_kPa=params.Pc_kPa,
                        case=regime,
                        Sc_mm=sc_m * 1000.0,
                        dz_m=dz,
                    )
                )
                z += dz

        return ConsolidationResult(
            S_total_mm=s_total_m * 1000.0,
            sublayers=tuple(sublayers),
        )


# ---------------------------------------------------------------------------
# Terzaghi Time-Rate Consolidation Model
# ---------------------------------------------------------------------------
class TimeRateConsolidationModel:
    """
    Terzaghi (1943) 1D time-rate consolidation solver.

    Cite: Terzaghi (1943); Das (2016) Eq. 7.56–7.57; IS 8009:1976 Part 1
    """

    @staticmethod
    def drainage_path(H_clay_m: float, drainage: DrainageCondition) -> float:
        """
        Compute maximum drainage path Hdr (m):
          - "one-way" (single drainage) : Hdr = H
          - "two-way" (double drainage) : Hdr = H / 2

        Cite: Terzaghi (1943); Das (2016) Sec. 7.11
        """
        if H_clay_m <= 0.0:
            raise ValueError("H_clay_m must be > 0 m.")
        if drainage == "two-way":
            return 0.5 * H_clay_m
        if drainage == "one-way":
            return float(H_clay_m)
        raise ValueError(f"Unknown drainage condition '{drainage}'. Use 'one-way' or 'two-way'.")

    @staticmethod
    def time_factor(cv_m2s: float, t_seconds: float, Hdr_m: float) -> float:
        """
        Dimensionless time factor Tv = (cv · t) / Hdr².

        Cite: Terzaghi (1943); Das (2016) Eq. 7.49; IS 8009:1976 Part 1
        """
        if Hdr_m <= 0.0 or t_seconds <= 0.0 or cv_m2s <= 0.0:
            return 0.0
        # Terzaghi (1943); Das (2016) Eq. 7.49: Tv = cv * t / Hdr²
        return float(cv_m2s) * float(t_seconds) / (float(Hdr_m) ** 2)

    @staticmethod
    def degree_of_consolidation(Tv: float | np.ndarray) -> float | np.ndarray:
        """
        Average degree of consolidation U(Tv) in [0, 1]:
          - For U <= 0.60 (Tv <= π/4 · 0.6² ≈ 0.2827): U = sqrt(4·Tv / π)
          - For U >  0.60 (Tv >  0.2827):              U = 1 − (8 / π²) · exp(−π²·Tv / 4)

        Cite: Terzaghi (1943); Das (2016) Eq. 7.56–7.57
        """
        # Threshold Tv_crit = (π/4) * 0.60² ≈ 0.282743 — Das (2016) Eq. 7.56
        if np.isscalar(Tv):
            tv_val = max(0.0, float(Tv))
            u_low = math.sqrt(4.0 * tv_val / math.pi)  # Das (2016) Eq. 7.56
            if u_low <= 0.60:
                return min(max(u_low, 0.0), 1.0)
            # Das (2016) Eq. 7.57 (single-term Fourier series for U > 60%)
            u_high = 1.0 - (8.0 / (math.pi ** 2)) * math.exp(-(math.pi ** 2) * tv_val / 4.0)
            return min(max(u_high, 0.0), 1.0)

        tv_arr = np.maximum(np.asarray(Tv, dtype=float), 0.0)
        u_low = np.sqrt(4.0 * tv_arr / np.pi)  # Das (2016) Eq. 7.56
        u_high = 1.0 - (8.0 / (np.pi ** 2)) * np.exp(-(np.pi ** 2) * tv_arr / 4.0)  # Das (2016) Eq. 7.57
        u = np.where(u_low <= 0.60, u_low, u_high)
        return np.clip(u, 0.0, 1.0)

    def generate_curve(
        self,
        Sc_total_m: float,
        cv_m2s: float,
        Hdr_m: float,
        t_max_years: float = 50.0,
        n_points: int = 200,
        drainage: DrainageCondition = "two-way",
    ) -> TimeSettlementResult:
        """
        Generate S(t) = U(Tv(t)) · Sc_total curve over [0, t_max_years].

        Cite: Terzaghi (1943); IS 8009:1976 Part 1
        """
        t_years = np.linspace(0.0, float(t_max_years), n_points)
        t_seconds = t_years * SECONDS_PER_YEAR
        if Hdr_m <= 0.0:
            tv = np.zeros_like(t_seconds)
        else:
            # Das (2016) Eq. 7.49: Tv = cv * t / Hdr²
            tv = float(cv_m2s) * t_seconds / (float(Hdr_m) ** 2)
        u = np.asarray(self.degree_of_consolidation(tv), dtype=float)
        # S(t) = U(t) * Sc_ultimate — Das (2016) Eq. 7.47
        s_mm = u * float(Sc_total_m) * 1000.0
        return TimeSettlementResult(
            t_years=t_years,
            U=u,
            S_mm=s_mm,
            Hdr_m=float(Hdr_m),
            cv_m2s=float(cv_m2s),
            drainage=drainage,
        )


# ---------------------------------------------------------------------------
# Functional Facade (100% Backward-Compatible with Streamlit P5 UI)
# ---------------------------------------------------------------------------
_SCHMERTMANN_CALC = SchmertmannSettlementCalculator()
_CONSOLIDATION_CALC = ConsolidationSettlementCalculator()
_TIME_RATE_MODEL = TimeRateConsolidationModel()


def schmertmann_Es_from_N(
    N_corrected: int | float | None, soil_type: str = "sand"
) -> float:
    """
    Estimate elastic modulus Es (kPa) from corrected SPT N.

    Cite: Meyerhof (1956); Schmertmann et al. (1978); Das (2016) Table 5.6
    """
    return SchmertmannModulusCorrelation.from_N(N_corrected, soil_type=soil_type)


def strain_influence_factor(
    z: float,
    B: float,
    L: float | None = None,
    footing_type: str = "square",
    Iz_peak: float = 0.6,
) -> float:
    """
    Schmertmann et al. (1978) bilinear strain influence factor Iz(z).

    Cite: Schmertmann et al. (1978) Fig. 4
    """
    l_eff = float(L) if L is not None else (10.0 * float(B) if footing_type == "strip" else float(B))
    shape = "strip" if (footing_type == "strip" or l_eff / float(B) >= 10.0) else "square"
    footing = FootingGeometry(B=float(B), L=l_eff, Df=0.0, shape=shape)
    return _SCHMERTMANN_CALC.influence.Iz_at(float(z), footing, float(Iz_peak))


def schmertmann_settlement(
    layers: Sequence[Mapping[str, Any]],
    Df: float,
    B: float,
    L: float,
    P_kN: float,
    wt_design_bgl: float,
    t_years: float = 50.0,
) -> dict[str, Any]:
    """
    Schmertmann et al. (1978) immediate settlement for granular layers.
    Validates continuous profile through Df + influence zone depth (2B or 4B).

    Cite: Schmertmann et al. (1978) Eq. 1–4; IS 8009:1976 Part 1
    """
    validate_soil_layers(layers, required_start_m=0.0, founding_depth_m=Df).raise_if_invalid()
    profile = SoilProfile.from_dicts(layers, wt_design_bgl=wt_design_bgl)
    shape = "strip" if L / B >= 10.0 else ("square" if abs(L - B) < 1e-9 else "rectangular")
    footing = FootingGeometry(B=float(B), L=float(L), Df=float(Df), shape=shape)
    load = FoundationLoad(P_kN=float(P_kN))
    return _SCHMERTMANN_CALC.calculate(
        profile, footing, load, wt_design_bgl=wt_design_bgl, t_years=t_years
    ).to_dict()


def consolidation_settlement_layer(
    H_m: float,
    e0: float,
    Cc: float,
    Cr: float,
    sigma_v0_kPa: float,
    Pc_kPa: float,
    delta_sigma_kPa: float,
) -> tuple[float, ConsolidationRegime]:
    """
    1D consolidation settlement (m) for a single clay sublayer.

    Cite: Terzaghi (1943); Das (2016) Eq. 7.21–7.23
    """
    return ConsolidationSettlementCalculator.compute_sublayer(
        H_m, e0, Cc, Cr, sigma_v0_kPa, Pc_kPa, delta_sigma_kPa
    )


def total_consolidation_settlement(
    layers: Sequence[Mapping[str, Any]],
    Df: float,
    B: float,
    L: float,
    P_kN: float,
    wt_design_bgl: float,
    sublayer_thickness: float = 0.5,
    required_depth_m: float | None = None,
) -> dict[str, Any]:
    """
    Total 1D consolidation settlement across clay sublayers (<= 0.5 m thick).
    Validates continuous profile through Df and required clay analysis depth.

    Cite: IS 8009:1976 Part 1 Cl. 5; Terzaghi (1943)
    """
    validate_soil_layers(
        layers,
        required_start_m=0.0,
        founding_depth_m=Df,
        required_end_m=required_depth_m,
    ).raise_if_invalid()
    profile = SoilProfile.from_dicts(layers, wt_design_bgl=wt_design_bgl)
    shape = "strip" if L / B >= 10.0 else ("square" if abs(L - B) < 1e-9 else "rectangular")
    footing = FootingGeometry(B=float(B), L=float(L), Df=float(Df), shape=shape)
    load = FoundationLoad(P_kN=float(P_kN))
    return _CONSOLIDATION_CALC.calculate(
        profile,
        footing,
        load,
        wt_design_bgl=wt_design_bgl,
        sublayer_thickness=sublayer_thickness,
        required_depth_m=required_depth_m,
    ).to_dict()


def degree_of_consolidation(Tv: float | np.ndarray) -> float | np.ndarray:
    """
    Terzaghi (1943) average degree of consolidation U vs time factor Tv.

    Cite: Terzaghi (1943); Das (2016) Eq. 7.56–7.57
    """
    return TimeRateConsolidationModel.degree_of_consolidation(Tv)


def time_factor(cv_m2s: float, t_seconds: float, Hdr_m: float) -> float:
    """
    Dimensionless time factor Tv = cv * t / Hdr².

    Cite: Terzaghi (1943); Das (2016) Eq. 7.49; IS 8009:1976 Part 1
    """
    return TimeRateConsolidationModel.time_factor(cv_m2s, t_seconds, Hdr_m)


def time_settlement_curve(
    Sc_total_m: float,
    cv_m2s: float,
    Hdr_m: float,
    t_max_years: float = 50.0,
    n_points: int = 200,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate (t_years_array, S_mm_array) using Terzaghi 1D consolidation theory.

    Cite: Terzaghi (1943); IS 8009:1976 Part 1
    """
    res = _TIME_RATE_MODEL.generate_curve(
        Sc_total_m=Sc_total_m,
        cv_m2s=cv_m2s,
        Hdr_m=Hdr_m,
        t_max_years=t_max_years,
        n_points=n_points,
    )
    return res.t_years, res.S_mm
