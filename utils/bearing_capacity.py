"""
utils/bearing_capacity.py
Pure-domain IS 6403:1981 Bearing Capacity of Shallow Foundations.
All computations strictly in SI units (kN, kPa, m, kN/m³, °).

Design Principles (SOLID)
-------------------------
- Single Responsibility (SRP):
  * `FootingSpec`, `SoilFoundingState`, `BearingCapacityResult` encapsulate typed
    domain inputs and full intermediate outputs without UI/plotting dependencies.
  * `IS6403FactorCalculator` isolates dimensionless IS 6403:1981 table/clause factors.
  * `IS6403Solver` orchestrates overburden, water-table, eccentricity, and capacity.
- Open/Closed (OCP) & Liskov Substitution (LSP):
  `IS6403ShearStrategy` defines the failure-mode contract implemented by:
    1. `GeneralShearStrategy`      (IS 6403:1981 Cl. 5.1.2)
    2. `LocalShearStrategy`        (IS 6403:1981 Cl. 5.1.2.2)
    3. `UndrainedCohesiveStrategy` (IS 6403:1981 Cl. 5.1.3)
- Dependency Inversion (DIP):
  `IS6403Solver` delegates failure-mode parameter/factor resolution to any
  injected `IS6403ShearStrategy`, and delegates multi-layer overburden stress
  integration to `SoilProfile` from `utils.models`.

References
----------
- IS 6403:1981 — Code of Practice for Determination of Bearing Capacity of
  Shallow Foundations (Cl. 5.1.2, Cl. 5.1.2.1, Cl. 5.1.2.2, Cl. 5.1.2.3, Cl. 5.1.3,
  Cl. 5.4, Cl. 6, Table 1)
- Vesic, A. S. (1973) — Analysis of ultimate loads of shallow foundations
  (Nγ = 2(Nq + 1)tan φ adopted in IS 6403:1981 Table 1)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

from utils.models import FootingShape, GAMMA_W, SoilLayer, SoilProfile


# ---------------------------------------------------------------------------
# 1. Typed Domain Dataclasses (SRP)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FootingSpec:
    """
    Shallow footing geometry, embedment, and load eccentricity/inclination (SI).

    Attributes
    ----------
    B : float
        Footing width (m). For circular footings, diameter B (m).
    L : float
        Footing length (m). Equal to B for square/circular; large for strip.
    Df : float
        Founding depth below existing ground level (m).
    footing_shape : FootingShape
        One of 'strip', 'square', 'rectangular', 'circular'.
    ex : float
        Load eccentricity parallel to B dimension (m).
    ey : float
        Load eccentricity parallel to L dimension (m).
    alpha_deg : float
        Inclination of resultant load from vertical (degrees, 0–90).
    """

    B: float
    L: float
    Df: float
    footing_shape: FootingShape = "square"
    ex: float = 0.0
    ey: float = 0.0
    alpha_deg: float = 0.0

    def __post_init__(self) -> None:
        if self.B <= 0.0:
            raise ValueError(f"Footing width B ({self.B} m) must be > 0.")
        if self.L <= 0.0:
            raise ValueError(f"Footing length L ({self.L} m) must be > 0.")
        if self.Df < 0.0:
            raise ValueError(f"Founding depth Df ({self.Df} m) must be >= 0.")
        if self.ex < 0.0 or self.ey < 0.0:
            raise ValueError("Eccentricities ex and ey must be >= 0 m.")
        if self.alpha_deg < 0.0 or self.alpha_deg >= 90.0:
            raise ValueError("Load inclination alpha_deg must lie in [0, 90)°.")

    @property
    def nominal_dimensions(self) -> tuple[float, float]:
        """Return nominal (B, L) consistent with `footing_shape`."""
        if self.footing_shape in ("square", "circular"):
            return self.B, self.B
        if self.footing_shape == "strip":
            return self.B, max(self.L, 1.0e6)
        return self.B, self.L

    def effective_dimensions(self) -> tuple[float, float, float, float, float, bool]:
        """
        IS 6403:1981 Cl. 5.4 — Effective dimensions for eccentric loading,
        normalized so B′ <= L′ for bearing capacity factor evaluation.

        Returns
        -------
        (B_eff, L_eff, B_prime, L_prime, A_eff, kern_warning)
        """
        B_nom, L_nom = self.nominal_dimensions
        if self.footing_shape in ("strip", "circular"):
            B_eff, L_eff = B_nom, L_nom
            if self.footing_shape == "strip" and self.ex > 0.0:
                # IS 6403:1981 Cl. 5.4: one-way eccentricity on strip footing
                B_eff = B_nom - 2.0 * self.ex
            A_eff = B_eff * L_eff if self.footing_shape == "strip" else math.pi * (B_nom ** 2) / 4.0
            kern_warn = (self.ex >= B_nom / 6.0)
            return B_eff, L_eff, B_eff, L_eff, A_eff, kern_warn

        # IS 6403:1981 Cl. 5.4: B_eff = B - 2*ex, L_eff = L - 2*ey
        B_eff = B_nom - 2.0 * self.ex
        L_eff = L_nom - 2.0 * self.ey
        A_eff = B_eff * L_eff

        # Normalize B′ = min(B_eff, L_eff) and L′ = max(B_eff, L_eff) so B′/L′ <= 1
        # IS 6403:1981 Cl. 5.1.2.1 / Cl. 5.4
        B_prime = min(B_eff, L_eff)
        L_prime = max(B_eff, L_eff)

        # Middle-third kern rule (tension / lift-off check): ex >= B/6 or ey >= L/6
        kern_warning = (self.ex >= B_nom / 6.0) or (self.ey >= L_nom / 6.0)
        return B_eff, L_eff, B_prime, L_prime, A_eff, kern_warning


@dataclass(frozen=True)
class SoilFoundingState:
    """
    Soil strength, unit weight, and groundwater/overburden state at founding depth Df.

    Attributes
    ----------
    c_prime : float
        Drained effective cohesion c′ (kPa).
    phi_prime_deg : float
        Drained effective friction angle φ′ (degrees).
    gamma_moist : float
        Moist/bulk unit weight of bearing stratum below Df (kN/m³).
    gamma_sat : float
        Saturated unit weight of bearing stratum below Df (kN/m³).
    wt_bgl : float
        Design water-table depth below ground level (m bgl).
    q_eff : float | None
        Pre-integrated effective overburden stress at Df (kPa). When None,
        computed from `gamma_moist`/`gamma_sat` over [0, Df].
    is_undrained : bool
        True for undrained φ = 0 (cu) analysis per IS 6403:1981 Cl. 5.1.3.
    cu : float
        Undrained shear strength cu (kPa).
    """

    c_prime: float
    phi_prime_deg: float
    gamma_moist: float
    gamma_sat: float
    wt_bgl: float
    q_eff: float | None = None
    is_undrained: bool = False
    cu: float = 0.0

    def __post_init__(self) -> None:
        if self.gamma_moist <= 0.0 or self.gamma_sat <= 0.0:
            raise ValueError("Unit weights gamma_moist and gamma_sat must be > 0 kN/m³.")
        if self.wt_bgl < 0.0:
            raise ValueError("wt_bgl must be >= 0 m bgl.")
        if self.phi_prime_deg < 0.0 or self.phi_prime_deg > 60.0:
            raise ValueError("phi_prime_deg must lie in [0, 60]°.")

    def resolved_overburden_q(self, Df: float) -> float:
        """
        Return effective overburden pressure q (kPa) at founding depth Df.
        If `q_eff` was integrated over a multi-layer SoilProfile, return it;
        otherwise integrate homogeneous overburden above Df.

        Cite: IS 6403:1981 Cl. 5.1.2; Das (2016) Eq. 2.10
        """
        if self.q_eff is not None:
            return max(float(self.q_eff), 0.0)
        if Df <= 0.0:
            return 0.0
        if self.wt_bgl >= Df:
            return self.gamma_moist * Df  # IS 6403:1981 Cl. 5.1.2 (WT below Df)
        # Homogeneous fallback when WT above Df: moist above WT + submerged below WT
        return (
            self.gamma_moist * self.wt_bgl
            + (self.gamma_sat - GAMMA_W) * (Df - self.wt_bgl)
        )

    @classmethod
    def from_profile(
        cls,
        profile: SoilProfile,
        Df: float,
        wt_bgl: float | None = None,
        override_layer: SoilLayer | None = None,
    ) -> "SoilFoundingState":
        """
        Construct SoilFoundingState by integrating ALL strata above Df for `q_eff`
        and extracting bearing-stratum properties at depth Df.

        Cite: IS 6403:1981 Cl. 5.1.2; Das (2016) Eq. 2.10
        """
        wt = (
            float(wt_bgl)
            if wt_bgl is not None
            else (profile.groundwater.wt_design_bgl if profile.groundwater else 0.0)
        )
        bearing_layer = override_layer or profile.layer_at_depth(Df)
        if bearing_layer is None:
            raise ValueError("SoilProfile contains no layers.")
        q_integrated = profile.effective_vertical_stress(Df, wt_bgl=wt)
        return cls(
            c_prime=bearing_layer.c_prime,
            phi_prime_deg=bearing_layer.phi_prime,
            gamma_moist=bearing_layer.gamma_moist,
            gamma_sat=bearing_layer.gamma_sat,
            wt_bgl=wt,
            q_eff=q_integrated,
            is_undrained=bearing_layer.is_undrained,
            cu=bearing_layer.cu,
        )


@dataclass(frozen=True)
class BearingCapacityResult:
    """Complete IS 6403:1981 bearing capacity evaluation output (all SI units)."""

    Nc: float
    Nq: float
    Ngamma: float
    sc: float
    sq: float
    sgamma: float
    dc: float
    dq: float
    dgamma: float
    ic: float
    iq: float
    igamma: float
    W_prime: float
    q_eff: float
    gamma_ngamma: float
    qf: float
    qnu: float
    qns: float
    FOS: float
    c_used: float
    phi_used: float
    B: float
    L: float
    B_eff: float
    L_eff: float
    B_prime: float
    L_prime: float
    A_eff: float
    kern_warning: bool
    footing_shape: str
    failure_mode: str
    strategy_name: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for seamless tabular/UI inspection."""
        return {
            "Nc": self.Nc,
            "Nq": self.Nq,
            "Ngamma": self.Ngamma,
            "sc": self.sc,
            "sq": self.sq,
            "sgamma": self.sgamma,
            "dc": self.dc,
            "dq": self.dq,
            "dgamma": self.dgamma,
            "ic": self.ic,
            "iq": self.iq,
            "igamma": self.igamma,
            "W_prime": self.W_prime,
            "q_eff": self.q_eff,
            "gamma_ngamma": self.gamma_ngamma,
            "qf": self.qf,
            "qnu": self.qnu,
            "qns": self.qns,
            "FOS": self.FOS,
            "c_used": self.c_used,
            "phi_used": self.phi_used,
            "B": self.B,
            "L": self.L,
            "B_eff": self.B_eff,
            "L_eff": self.L_eff,
            "B_prime": self.B_prime,
            "L_prime": self.L_prime,
            "A_eff": self.A_eff,
            "kern_warning": self.kern_warning,
            "footing_shape": self.footing_shape,
            "failure_mode": self.failure_mode,
            "strategy_name": self.strategy_name,
        }


# ---------------------------------------------------------------------------
# 2. IS 6403:1981 Core Factor Calculator (SRP)
# ---------------------------------------------------------------------------
class IS6403FactorCalculator:
    """
    Pure static/stateless evaluator of all IS 6403:1981 Table 1 & Clause 5.1 factors.
    """

    @staticmethod
    def bearing_capacity_factors(phi_deg: float) -> tuple[float, float, float]:
        """
        IS 6403:1981 Cl. 5.1.2 / Table 1 — Bearing capacity factors Nc, Nq, Nγ.

            Nq  = exp(π · tan φ) · tan²(45° + φ/2)
            Nc  = (Nq − 1) · cot φ     for φ > 0°;   5.14  for φ = 0°
            Nγ  = 2 · (Nq + 1) · tan φ  (Vesic, tabulated in IS 6403:1981 Table 1)
        """
        if phi_deg <= 0.0:
            # IS 6403:1981 Table 1 / Cl. 5.1.3 (φ = 0°): Nc = 5.14, Nq = 1.0, Nγ = 0.0
            return 5.14, 1.0, 0.0

        phi_rad = math.radians(phi_deg)
        tan_phi = math.tan(phi_rad)
        # IS 6403:1981 Table 1: Nq = exp(π·tan φ)·tan²(45° + φ/2)
        Nq = math.exp(math.pi * tan_phi) * (math.tan(math.radians(45.0 + phi_deg / 2.0)) ** 2)
        # IS 6403:1981 Table 1: Nc = (Nq - 1) · cot φ
        Nc = (Nq - 1.0) / tan_phi
        # IS 6403:1981 Table 1 (Vesic): Nγ = 2 · (Nq + 1) · tan φ
        Ngamma = 2.0 * (Nq + 1.0) * tan_phi
        return Nc, Nq, Ngamma

    @staticmethod
    def shape_factors(
        B: float,
        L: float,
        footing_shape: str = "rectangular",
    ) -> tuple[float, float, float]:
        """
        IS 6403:1981 Cl. 5.1.2.1 — Shape factors sc, sq, sγ (independent of φ):
          - Strip       : sc = 1.0,            sq = 1.0,            sγ = 1.0
          - Square      : sc = 1.3,            sq = 1.2,            sγ = 0.8
          - Circular    : sc = 1.3,            sq = 1.2,            sγ = 0.6
          - Rectangular : sc = 1 + 0.2·(B/L),  sq = 1 + 0.2·(B/L),  sγ = 1 − 0.4·(B/L)
                          (with B normalized <= L)
        """
        shape = footing_shape.lower()
        if shape == "strip" or L <= 0.0 or L > 1.0e5:
            # IS 6403:1981 Cl. 5.1.2.1 — Strip footing
            return 1.0, 1.0, 1.0
        if shape == "square":
            # IS 6403:1981 Cl. 5.1.2.1 — Square footing
            return 1.3, 1.2, 0.8
        if shape == "circular":
            # IS 6403:1981 Cl. 5.1.2.1 — Circular footing
            return 1.3, 1.2, 0.6

        # Rectangular (normalize B <= L so ratio B/L <= 1.0)
        b_min, l_max = min(B, L), max(B, L)
        ratio = b_min / l_max if l_max > 0.0 else 1.0
        # IS 6403:1981 Cl. 5.1.2.1 — Rectangular footing shape factors
        sc = 1.0 + 0.2 * ratio
        sq = 1.0 + 0.2 * ratio
        sgamma = 1.0 - 0.4 * ratio
        return sc, sq, sgamma

    @staticmethod
    def depth_factors(Df: float, B: float, phi_deg: float) -> tuple[float, float, float]:
        """
        IS 6403:1981 Cl. 5.1.2.1 — Depth factors dc, dq, dγ:
          - For φ > 10° : dc = 1 + 0.2·√Kp·(Df/B),  dq = dγ = 1 + 0.1·√Kp·(Df/B)
          - For φ <= 10°: dc = 1 + 0.2·(Df/B),      dq = dγ = 1.0
          where Kp = tan²(45° + φ/2).
        """
        if B <= 0.0 or Df <= 0.0:
            return 1.0, 1.0, 1.0

        ratio = Df / B
        if phi_deg > 10.0:
            # IS 6403:1981 Cl. 5.1.2.1 (φ > 10°): Kp = tan²(45° + φ/2)
            sqrt_kp = math.tan(math.radians(45.0 + phi_deg / 2.0))
            dc = 1.0 + 0.2 * sqrt_kp * ratio
            dq = 1.0 + 0.1 * sqrt_kp * ratio
            dgamma = dq
        else:
            # IS 6403:1981 Cl. 5.1.2.1 (φ <= 10°)
            dc = 1.0 + 0.2 * ratio
            dq = 1.0
            dgamma = 1.0
        return dc, dq, dgamma

    @staticmethod
    def inclination_factors(alpha_deg: float, phi_deg: float) -> tuple[float, float, float]:
        """
        IS 6403:1981 Cl. 5.1.2.1 — Inclination factors ic, iq, iγ:
          - ic = iq = (1 − α / 90°)²
          - iγ = (1 − α / φ)²  for φ > 0° (0 if α >= φ);  0 if φ = 0° and α > 0°
        """
        if alpha_deg <= 0.0:
            return 1.0, 1.0, 1.0

        # IS 6403:1981 Cl. 5.1.2.1: ic = iq = (1 - α/90)²
        ic = (1.0 - alpha_deg / 90.0) ** 2
        iq = ic
        if phi_deg > 0.0:
            # IS 6403:1981 Cl. 5.1.2.1: iγ = (1 - α/φ)²
            igamma = (1.0 - alpha_deg / phi_deg) ** 2 if alpha_deg < phi_deg else 0.0
        else:
            igamma = 0.0
        return ic, iq, igamma

    @staticmethod
    def water_table_factor(Df: float, B: float, wt_bgl: float) -> float:
        """
        IS 6403:1981 Cl. 5.1.2.3 — Water table correction factor W′:
          - wt_bgl <= Df      → W′ = 0.5
          - wt_bgl >= Df + B  → W′ = 1.0
          - Df < wt < Df + B  → W′ = 0.5 + 0.5 · (wt_bgl − Df) / B
        """
        if wt_bgl <= Df or B <= 0.0:
            # IS 6403:1981 Cl. 5.1.2.3 (WT at or above footing base)
            return 0.5
        if wt_bgl >= Df + B:
            # IS 6403:1981 Cl. 5.1.2.3 (WT at or deeper than B below base)
            return 1.0
        # IS 6403:1981 Cl. 5.1.2.3 (linear interpolation within [Df, Df + B])
        return 0.5 + 0.5 * (wt_bgl - Df) / B

    @staticmethod
    def bulk_gamma_below_footing(
        gamma_moist: float, gamma_sat: float, Df: float, B: float, wt_bgl: float
    ) -> float:
        """
        Determine the bulk/saturated soil unit weight γ (kN/m³) in the failure
        wedge [Df, Df + B] for the Nγ term, WITHOUT subtracting γw (because W′
        already accounts for water-table reduction per IS 6403:1981 Cl. 5.1.2.3):
          - wt_bgl <= Df     → γ_sat
          - wt_bgl >= Df + B → γ_moist
          - in between       → thickness-weighted bulk/saturated γ over [Df, Df + B]
        """
        if wt_bgl <= Df or B <= 0.0:
            return gamma_sat
        if wt_bgl >= Df + B:
            return gamma_moist
        frac_above = (wt_bgl - Df) / B
        return frac_above * gamma_moist + (1.0 - frac_above) * gamma_sat


# ---------------------------------------------------------------------------
# 3. Shear Failure Strategies (OCP + LSP)
# ---------------------------------------------------------------------------
class IS6403ShearStrategy(ABC):
    """
    Abstract IS 6403:1981 shear-failure strategy controlling mobilized strength
    parameters and ultimate net bearing capacity formulation.
    """

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Human-readable strategy label and IS 6403 clause reference."""

    @property
    @abstractmethod
    def failure_mode_key(self) -> str:
        """Canonical failure mode key ('general', 'local', or 'undrained')."""

    @abstractmethod
    def mobilize_strength(self, soil: SoilFoundingState) -> tuple[float, float]:
        """Return mobilized (c_used_kPa, phi_used_deg)."""

    @abstractmethod
    def compute_net_ultimate(
        self,
        c_used: float,
        phi_used: float,
        q_eff: float,
        gamma_ngamma: float,
        B_prime: float,
        Nc: float,
        Nq: float,
        Ngamma: float,
        sc: float,
        sq: float,
        sgamma: float,
        dc: float,
        dq: float,
        dgamma: float,
        ic: float,
        iq: float,
        igamma: float,
        W_prime: float,
    ) -> float:
        """Compute net ultimate bearing capacity qnu (kPa)."""


class GeneralShearStrategy(IS6403ShearStrategy):
    """
    IS 6403:1981 Cl. 5.1.2 — General shear failure for c′–φ′ soils:
        qnu = c·Nc·sc·dc·ic + q·(Nq − 1)·sq·dq·iq + 0.5·B·γ·Nγ·sγ·dγ·iγ·W′
    """

    @property
    def strategy_name(self) -> str:
        return "General Shear (IS 6403:1981 Cl. 5.1.2)"

    @property
    def failure_mode_key(self) -> str:
        return "general"

    def mobilize_strength(self, soil: SoilFoundingState) -> tuple[float, float]:
        return float(soil.c_prime), float(soil.phi_prime_deg)

    def compute_net_ultimate(
        self,
        c_used: float,
        phi_used: float,
        q_eff: float,
        gamma_ngamma: float,
        B_prime: float,
        Nc: float,
        Nq: float,
        Ngamma: float,
        sc: float,
        sq: float,
        sgamma: float,
        dc: float,
        dq: float,
        dgamma: float,
        ic: float,
        iq: float,
        igamma: float,
        W_prime: float,
    ) -> float:
        # IS 6403:1981 Cl. 5.1.2:
        # qnu = c·Nc·sc·dc·ic + q·(Nq - 1)·sq·dq·iq + 0.5·B·γ·Nγ·sγ·dγ·iγ·W'
        c_term = c_used * Nc * sc * dc * ic
        q_term = q_eff * (Nq - 1.0) * sq * dq * iq
        gamma_term = 0.5 * B_prime * gamma_ngamma * Ngamma * sgamma * dgamma * igamma * W_prime
        return c_term + q_term + gamma_term


class LocalShearStrategy(GeneralShearStrategy):
    """
    IS 6403:1981 Cl. 5.1.2.2 — Local shear failure modification:
        cm = (2/3) · c′
        φm = arctan((2/3) · tan φ′)
    """

    @property
    def strategy_name(self) -> str:
        return "Local Shear (IS 6403:1981 Cl. 5.1.2.2)"

    @property
    def failure_mode_key(self) -> str:
        return "local"

    def mobilize_strength(self, soil: SoilFoundingState) -> tuple[float, float]:
        # IS 6403:1981 Cl. 5.1.2.2: cm = (2/3) * c', φm = arctan((2/3) * tan φ')
        c_local = (2.0 / 3.0) * float(soil.c_prime)
        phi_local = math.degrees(
            math.atan((2.0 / 3.0) * math.tan(math.radians(float(soil.phi_prime_deg))))
        )
        return c_local, phi_local


class UndrainedCohesiveStrategy(IS6403ShearStrategy):
    """
    IS 6403:1981 Cl. 5.1.3 — Purely cohesive saturated soil (φu = 0°):
        qnu = cu · Nc · sc · dc · ic     (Nc = 5.14, Nq = 1, Nγ = 0)
    """

    @property
    def strategy_name(self) -> str:
        return "Undrained Cohesive φ=0 (IS 6403:1981 Cl. 5.1.3)"

    @property
    def failure_mode_key(self) -> str:
        return "undrained"

    def mobilize_strength(self, soil: SoilFoundingState) -> tuple[float, float]:
        # IS 6403:1981 Cl. 5.1.3: c = cu, φ = 0°
        return float(soil.cu), 0.0

    def compute_net_ultimate(
        self,
        c_used: float,
        phi_used: float,
        q_eff: float,
        gamma_ngamma: float,
        B_prime: float,
        Nc: float,
        Nq: float,
        Ngamma: float,
        sc: float,
        sq: float,
        sgamma: float,
        dc: float,
        dq: float,
        dgamma: float,
        ic: float,
        iq: float,
        igamma: float,
        W_prime: float,
    ) -> float:
        # IS 6403:1981 Cl. 5.1.3: qnu = cu · Nc · sc · dc · ic  (Nq = 1 ⇒ Nq - 1 = 0, Nγ = 0)
        return c_used * Nc * sc * dc * ic


# ---------------------------------------------------------------------------
# 4. Solver Orchestrator (DIP)
# ---------------------------------------------------------------------------
class IS6403Solver:
    """
    Stateless IS 6403:1981 solver orchestrating geometry normalization (Cl. 5.4),
    strategy dispatch (Cl. 5.1.2 / 5.1.2.2 / 5.1.3), factor evaluation (Cl. 5.1.2.1),
    water-table correction (Cl. 5.1.2.3), and safe bearing capacity (Cl. 6).
    """

    def __init__(self, factor_calc: IS6403FactorCalculator | None = None) -> None:
        self.factors = factor_calc or IS6403FactorCalculator()

    @staticmethod
    def resolve_strategy(
        soil: SoilFoundingState, failure_mode: str = "general"
    ) -> IS6403ShearStrategy:
        """Select concrete IS6403ShearStrategy from soil state and failure mode."""
        if soil.is_undrained:
            return UndrainedCohesiveStrategy()
        if failure_mode == "local":
            return LocalShearStrategy()
        if failure_mode == "general":
            return GeneralShearStrategy()
        raise ValueError(f"Unknown failure_mode '{failure_mode}'. Use 'general' or 'local'.")

    def solve(
        self,
        footing: FootingSpec,
        soil: SoilFoundingState,
        FOS: float = 3.0,
        failure_mode: str = "general",
        strategy: IS6403ShearStrategy | None = None,
    ) -> BearingCapacityResult:
        """Evaluate IS 6403:1981 bearing capacity for a FootingSpec & SoilFoundingState."""
        if FOS <= 0.0:
            raise ValueError(f"Factor of safety FOS ({FOS}) must be > 0.")

        strat = strategy or self.resolve_strategy(soil, failure_mode=failure_mode)
        B_nom, L_nom = footing.nominal_dimensions
        B_eff, L_eff, B_prime, L_prime, A_eff, kern_warning = footing.effective_dimensions()

        if B_eff <= 0.0 or L_eff <= 0.0:
            raise ValueError(
                f"Effective dimensions must be positive (B_eff={B_eff:.3f} m, L_eff={L_eff:.3f} m)."
            )

        # Effective shape for factor evaluation when eccentric loading makes B_eff != L_eff
        shape_for_factors = footing.footing_shape
        if footing.footing_shape in ("square", "rectangular") and (footing.ex > 0.0 or footing.ey > 0.0):
            shape_for_factors = "square" if abs(B_prime - L_prime) < 1e-9 else "rectangular"

        c_used, phi_used = strat.mobilize_strength(soil)

        Nc, Nq, Ngamma = self.factors.bearing_capacity_factors(phi_used)
        sc, sq, sgamma = self.factors.shape_factors(B_prime, L_prime, shape_for_factors)
        dc, dq, dgamma = self.factors.depth_factors(footing.Df, B_prime, phi_used)
        ic, iq, igamma = self.factors.inclination_factors(footing.alpha_deg, phi_used)

        W_prime = self.factors.water_table_factor(footing.Df, B_prime, soil.wt_bgl)
        gamma_ngamma = self.factors.bulk_gamma_below_footing(
            soil.gamma_moist, soil.gamma_sat, footing.Df, B_prime, soil.wt_bgl
        )
        q_eff = soil.resolved_overburden_q(footing.Df)

        qnu = strat.compute_net_ultimate(
            c_used=c_used,
            phi_used=phi_used,
            q_eff=q_eff,
            gamma_ngamma=gamma_ngamma,
            B_prime=B_prime,
            Nc=Nc,
            Nq=Nq,
            Ngamma=Ngamma,
            sc=sc,
            sq=sq,
            sgamma=sgamma,
            dc=dc,
            dq=dq,
            dgamma=dgamma,
            ic=ic,
            iq=iq,
            igamma=igamma,
            W_prime=W_prime,
        )
        # IS 6403:1981 Cl. 5.1.2: qf = qnu + q
        qf = qnu + q_eff
        # IS 6403:1981 Cl. 6: qns = qnu / FOS
        qns = qnu / float(FOS)

        return BearingCapacityResult(
            Nc=Nc,
            Nq=Nq,
            Ngamma=Ngamma,
            sc=sc,
            sq=sq,
            sgamma=sgamma,
            dc=dc,
            dq=dq,
            dgamma=dgamma,
            ic=ic,
            iq=iq,
            igamma=igamma,
            W_prime=W_prime,
            q_eff=q_eff,
            gamma_ngamma=gamma_ngamma,
            qf=qf,
            qnu=qnu,
            qns=qns,
            FOS=float(FOS),
            c_used=c_used,
            phi_used=phi_used,
            B=B_nom,
            L=L_nom,
            B_eff=B_eff,
            L_eff=L_eff,
            B_prime=B_prime,
            L_prime=L_prime,
            A_eff=A_eff,
            kern_warning=kern_warning,
            footing_shape=footing.footing_shape,
            failure_mode=strat.failure_mode_key,
            strategy_name=strat.strategy_name,
        )

    def required_footing_size(
        self,
        P_kN: float,
        soil: SoilFoundingState,
        Df: float,
        FOS: float = 3.0,
        footing_shape: FootingShape = "square",
        failure_mode: str = "general",
        alpha_deg: float = 0.0,
        aspect_ratio_L_over_B: float = 1.5,
        n_iter: int = 15,
    ) -> dict[str, float]:
        """
        Iterative IS 6403:1981 Cl. 6 footing sizing under service load P_kN.
        Rounds B up to the nearest 0.05 m construction increment.
        """
        if P_kN <= 0.0:
            raise ValueError("P_kN must be > 0 kN.")

        B = max(0.5, math.sqrt(P_kN / 150.0))
        for _ in range(n_iter):
            L = (
                B
                if footing_shape in ("square", "circular")
                else (1.0e6 if footing_shape == "strip" else B * aspect_ratio_L_over_B)
            )
            spec = FootingSpec(
                B=B, L=L, Df=Df, footing_shape=footing_shape, alpha_deg=alpha_deg
            )
            res = self.solve(spec, soil, FOS=FOS, failure_mode=failure_mode)
            qns = max(res.qns, 1.0)
            if footing_shape == "circular":
                B = math.sqrt((4.0 * P_kN) / (math.pi * qns))
            elif footing_shape == "rectangular":
                B = math.sqrt(P_kN / (aspect_ratio_L_over_B * qns))
            elif footing_shape == "strip":
                B = P_kN / qns
            else:
                B = math.sqrt(P_kN / qns)

        B_rounded = math.ceil(B / 0.05) * 0.05
        L_final = (
            B_rounded
            if footing_shape in ("square", "circular")
            else (
                1.0e6
                if footing_shape == "strip"
                else math.ceil((B_rounded * aspect_ratio_L_over_B) / 0.05) * 0.05
            )
        )
        final_spec = FootingSpec(
            B=B_rounded, L=L_final, Df=Df, footing_shape=footing_shape, alpha_deg=alpha_deg
        )
        final_res = self.solve(final_spec, soil, FOS=FOS, failure_mode=failure_mode)
        applied_q = P_kN / final_res.A_eff
        actual_fos = final_res.qnu / applied_q if applied_q > 0.0 else float("inf")

        return {
            "B": B_rounded,
            "L": L_final,
            "qns": final_res.qns,
            "qnu": final_res.qnu,
            "actual_FOS": actual_fos,
        }


# ---------------------------------------------------------------------------
# 5. Functional Facade (Backward-Compatible Helpers)
# ---------------------------------------------------------------------------
_DEFAULT_SOLVER = IS6403Solver()


def bearing_capacity_factors(phi_deg: float) -> tuple[float, float, float]:
    """IS 6403:1981 Cl. 5.1.2 / Table 1 — Nc, Nq, Nγ (Vesic)."""
    return IS6403FactorCalculator.bearing_capacity_factors(phi_deg)


def shape_factors(
    B: float,
    L: float,
    phi_deg: float = 0.0,
    footing_shape: str = "rectangular",
) -> tuple[float, float, float]:
    """IS 6403:1981 Cl. 5.1.2.1 — Shape factors sc, sq, sγ."""
    _ = phi_deg  # IS 6403 Cl. 5.1.2.1 shape factors depend solely on shape and B/L
    return IS6403FactorCalculator.shape_factors(B, L, footing_shape=footing_shape)


def depth_factors(Df: float, B: float, phi_deg: float) -> tuple[float, float, float]:
    """IS 6403:1981 Cl. 5.1.2.1 — Depth factors dc, dq, dγ."""
    return IS6403FactorCalculator.depth_factors(Df, B, phi_deg)


def inclination_factors(alpha_deg: float, phi_deg: float) -> tuple[float, float, float]:
    """IS 6403:1981 Cl. 5.1.2.1 — Inclination factors ic, iq, iγ."""
    return IS6403FactorCalculator.inclination_factors(alpha_deg, phi_deg)


def water_table_factor(Df: float, B: float, wt_bgl: float) -> float:
    """IS 6403:1981 Cl. 5.1.2.3 — Water table correction factor W′."""
    return IS6403FactorCalculator.water_table_factor(Df, B, wt_bgl)


def local_shear_params(c_prime: float, phi_prime_deg: float) -> tuple[float, float]:
    """IS 6403:1981 Cl. 5.1.2.2 — Mobilized local shear parameters cm, φm."""
    dummy_soil = SoilFoundingState(
        c_prime=c_prime,
        phi_prime_deg=phi_prime_deg,
        gamma_moist=18.0,
        gamma_sat=20.0,
        wt_bgl=10.0,
    )
    return LocalShearStrategy().mobilize_strength(dummy_soil)


def effective_area(B: float, L: float, ex: float, ey: float) -> tuple[float, float, float]:
    """IS 6403:1981 Cl. 5.4 — Effective footing dimensions (B_eff, L_eff, A_eff)."""
    spec = FootingSpec(B=B, L=L, Df=0.0, footing_shape="rectangular", ex=ex, ey=ey)
    b_eff, l_eff, _, _, a_eff, _ = spec.effective_dimensions()
    return b_eff, l_eff, a_eff


def compute_effective_overburden(
    layers: Sequence[Mapping[str, Any]], Df: float, wt_bgl: float
) -> float:
    """
    Integrate effective vertical overburden stress q (kPa) across ALL layers
    above founding depth Df using γ_moist above WT and (γ_sat - γw) below WT.

    Cite: IS 6403:1981 Cl. 5.1.2; Das (2016) Eq. 2.10
    """
    profile = SoilProfile.from_dicts(layers, wt_design_bgl=wt_bgl)
    return profile.effective_vertical_stress(Df, wt_bgl=wt_bgl)


def net_ultimate_bearing_capacity(
    c_prime: float,
    phi_prime_deg: float,
    gamma_moist: float,
    gamma_sat: float,
    Df: float,
    B: float,
    L: float,
    wt_bgl: float,
    footing_shape: FootingShape = "square",
    failure_mode: str = "general",
    alpha_deg: float = 0.0,
    is_undrained: bool = False,
    cu: float = 0.0,
    ex: float = 0.0,
    ey: float = 0.0,
    FOS: float = 3.0,
    layers: Sequence[Mapping[str, Any]] | None = None,
    q_eff_override: float | None = None,
) -> dict[str, Any]:
    """Functional facade delegating to `IS6403Solver` and returning result dict."""
    q_eff = q_eff_override
    if q_eff is None and layers is not None:
        q_eff = compute_effective_overburden(layers, Df, wt_bgl)

    spec = FootingSpec(
        B=B,
        L=L,
        Df=Df,
        footing_shape=footing_shape,
        ex=ex,
        ey=ey,
        alpha_deg=alpha_deg,
    )
    soil = SoilFoundingState(
        c_prime=c_prime,
        phi_prime_deg=phi_prime_deg,
        gamma_moist=gamma_moist,
        gamma_sat=gamma_sat,
        wt_bgl=wt_bgl,
        q_eff=q_eff,
        is_undrained=is_undrained,
        cu=cu,
    )
    return _DEFAULT_SOLVER.solve(spec, soil, FOS=FOS, failure_mode=failure_mode).to_dict()


def net_safe_bearing_capacity(qnu: float, FOS: float = 3.0) -> float:
    """IS 6403:1981 Cl. 6 — Net safe bearing capacity qns = qnu / FOS (kPa)."""
    return float(qnu) / float(FOS)


def required_footing_size(
    P_kN: float,
    c_prime: float,
    phi_prime_deg: float,
    gamma_moist: float,
    gamma_sat: float,
    Df: float,
    wt_bgl: float,
    FOS: float = 3.0,
    footing_shape: FootingShape = "square",
    failure_mode: str = "general",
    alpha_deg: float = 0.0,
    is_undrained: bool = False,
    cu: float = 0.0,
    n_iter: int = 15,
    layers: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, float]:
    """Functional facade for iterative IS 6403:1981 footing sizing."""
    q_eff = compute_effective_overburden(layers, Df, wt_bgl) if layers is not None else None
    soil = SoilFoundingState(
        c_prime=c_prime,
        phi_prime_deg=phi_prime_deg,
        gamma_moist=gamma_moist,
        gamma_sat=gamma_sat,
        wt_bgl=wt_bgl,
        q_eff=q_eff,
        is_undrained=is_undrained,
        cu=cu,
    )
    return _DEFAULT_SOLVER.required_footing_size(
        P_kN=P_kN,
        soil=soil,
        Df=Df,
        FOS=FOS,
        footing_shape=footing_shape,
        failure_mode=failure_mode,
        alpha_deg=alpha_deg,
        n_iter=n_iter,
    )
