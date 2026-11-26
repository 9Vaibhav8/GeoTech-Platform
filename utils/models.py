"""
utils/models.py
Typed pure-domain schema and shared physical invariants for the CE 402
Geotechnical Engineering Platform (IIT Mandi).

Design Principles (SOLID)
-------------------------
- Single Responsibility (SRP): Holds domain value objects, parameter schemas,
  result structures, and exact piecewise vertical-stress integration without any
  Streamlit/UI or plotting coupling.
- Open/Closed (OCP) & Liskov Substitution (LSP): Immutable/validated dataclasses
  expose clean `.from_dict()` / `.to_dict()` adapters so existing Streamlit
  session-state dicts interoperate seamlessly with typed domain services.

Units Convention (SI Throughout)
--------------------------------
- Length / Depth : m
- Force          : kN
- Stress / Pressure / Modulus : kPa  (= kN/m²)
- Unit Weight    : kN/m³
- Settlement     : m (internal), mm (reported outputs)
- Time           : s (internal), years (curve outputs)
- Consolidation Coefficient cv : m²/s
- Angles         : degrees (°)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Optional, Sequence

import numpy as np

# ---------------------------------------------------------------------------
# Physical & Code Constants (SI Units)
# ---------------------------------------------------------------------------
# Unit weight of water at 4 °C = 9.81 kN/m³ — IS 6403:1981 Cl. 5.2; Das (2016) Sec. 2.1
GAMMA_W: float = 9.81

# Conversion constant for Julian year to seconds: 365.25 d × 24 h × 3600 s
SECONDS_PER_YEAR: float = 365.25 * 24.0 * 3600.0

# Soil classification symbol groups per IS 1498:1970
GRANULAR_SYMBOLS: frozenset[str] = frozenset(
    {"SM", "SP", "SW", "SC", "GW", "GP", "GM", "GC", "Fill"}
)
GRAVEL_SYMBOLS: frozenset[str] = frozenset({"GW", "GP", "GM", "GC"})

# Fine saturated sands and silts susceptible to negative pore-pressure dilation
# during SPT sampling — IS 2131:1981 Cl. 4.6
DILATANCY_ELIGIBLE_SYMBOLS: frozenset[str] = frozenset({"SM", "ML", "SP"})

# Type aliases
FootingShape = Literal["strip", "square", "rectangular", "circular"]
DrainageCondition = Literal["one-way", "two-way"]
ConsolidationRegime = Literal["NC", "OC", "OC→NC", "No load"]


# ---------------------------------------------------------------------------
# Groundwater & Soil Layer Models
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GroundwaterProfile:
    """
    Groundwater conditions in metres below existing ground level (m bgl).

    Attributes
    ----------
    wt_measured_bgl : float
        Measured water-table depth during site investigation (m bgl).
    wt_design_bgl : float
        Design water-table depth, typically highest seasonal level (m bgl).
    ground_rl : float
        Reduced level (RL) of existing ground surface (m).
    """

    wt_measured_bgl: float
    wt_design_bgl: float
    ground_rl: float = 100.0

    def __post_init__(self) -> None:
        if self.wt_measured_bgl < 0.0:
            raise ValueError("wt_measured_bgl must be >= 0.0 m bgl.")
        if self.wt_design_bgl < 0.0:
            raise ValueError("wt_design_bgl must be >= 0.0 m bgl.")


@dataclass(frozen=True)
class ConsolidationParameters:
    """
    One-dimensional oedometer consolidation parameters for fine-grained strata.

    Attributes
    ----------
    Cc : float
        Compression index (virgin compression slope in e–log10 σ′v space).
    Cr : float
        Recompression / swell index (reloading/unloading slope).
    e0 : float
        In-situ initial void ratio (dimensionless).
    Pc_kPa : float
        Preconsolidation pressure σ′p (kPa).
    cv_m2s : float | None
        Coefficient of consolidation (m²/s).
    """

    Cc: float
    Cr: float
    e0: float
    Pc_kPa: float
    cv_m2s: Optional[float] = None

    def __post_init__(self) -> None:
        if self.Cc < 0.0:
            raise ValueError("Compression index Cc must be >= 0.")
        if self.Cr < 0.0:
            raise ValueError("Recompression index Cr must be >= 0.")
        if self.e0 < 0.0:
            raise ValueError("Initial void ratio e0 must be >= 0.")
        if self.Pc_kPa <= 0.0:
            raise ValueError("Preconsolidation pressure Pc_kPa must be > 0 kPa.")
        if self.cv_m2s is not None and self.cv_m2s < 0.0:
            raise ValueError("Coefficient of consolidation cv_m2s must be >= 0 m²/s.")


@dataclass(frozen=True)
class SoilLayer:
    """
    Typed representation of a single soil stratum in SI units.

    Matches the Streamlit session-state layer dictionary schema defined in
    `utils/constants.py` while enforcing core mathematical invariants.
    """

    depth_top: float
    depth_bot: float
    name: str = "Layer"
    symbol: str = "SM"
    gamma_moist: float = 18.0
    gamma_sat: float = 20.0
    c_prime: float = 0.0
    phi_prime: float = 30.0
    cu: float = 0.0
    is_undrained: bool = False
    N_field: Optional[int] = None
    N_corrected: Optional[int] = None
    Cc: Optional[float] = None
    Cr: Optional[float] = None
    e0: Optional[float] = None
    Pc_kPa: Optional[float] = None
    cv_m2s: Optional[float] = None
    is_clay: bool = False

    def __post_init__(self) -> None:
        if self.depth_top < 0.0:
            raise ValueError(f"depth_top ({self.depth_top} m) must be >= 0.")
        if self.depth_bot <= self.depth_top:
            raise ValueError(
                f"depth_bot ({self.depth_bot} m) must be > depth_top ({self.depth_top} m)."
            )
        if self.gamma_moist <= 0.0:
            raise ValueError(f"gamma_moist ({self.gamma_moist} kN/m³) must be > 0.")
        if self.gamma_sat <= 0.0:
            raise ValueError(f"gamma_sat ({self.gamma_sat} kN/m³) must be > 0.")
        if self.phi_prime < 0.0 or self.phi_prime > 60.0:
            raise ValueError(f"phi_prime ({self.phi_prime}°) must lie in [0, 60]°.")
        if self.c_prime < 0.0:
            raise ValueError(f"c_prime ({self.c_prime} kPa) must be >= 0.")
        if self.cu < 0.0:
            raise ValueError(f"cu ({self.cu} kPa) must be >= 0.")

    @property
    def thickness(self) -> float:
        """Layer thickness Δz (m)."""
        return self.depth_bot - self.depth_top

    @property
    def mid_depth(self) -> float:
        """Layer midpoint depth (m bgl)."""
        return 0.5 * (self.depth_top + self.depth_bot)

    @property
    def is_gravel(self) -> bool:
        """True if layer classification symbol is gravelly (IS 1498)."""
        return self.symbol in GRAVEL_SYMBOLS

    @property
    def is_granular(self) -> bool:
        """True if layer is treated as granular for Schmertmann settlement."""
        return (not self.is_clay) and (self.symbol in GRANULAR_SYMBOLS or not self.is_clay)

    @property
    def effective_N(self) -> Optional[int]:
        """Return corrected SPT N if available, otherwise field N."""
        return self.N_corrected if self.N_corrected is not None else self.N_field

    @property
    def consolidation_params(self) -> Optional[ConsolidationParameters]:
        """Extract validated ConsolidationParameters if clay and defined."""
        if not self.is_clay:
            return None
        return ConsolidationParameters(
            Cc=float(self.Cc) if self.Cc is not None else 0.3,
            Cr=float(self.Cr) if self.Cr is not None else 0.06,
            e0=float(self.e0) if self.e0 is not None else 0.9,
            Pc_kPa=float(self.Pc_kPa) if self.Pc_kPa is not None else 100.0,
            cv_m2s=float(self.cv_m2s) if self.cv_m2s is not None else None,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SoilLayer":
        """Construct a typed SoilLayer from a Streamlit session-state dict."""
        n_field = data.get("N_field")
        n_corr = data.get("N_corrected")
        return cls(
            depth_top=float(data["depth_top"]),
            depth_bot=float(data["depth_bot"]),
            name=str(data.get("name", data.get("symbol", "Layer"))),
            symbol=str(data.get("symbol", "SM")),
            gamma_moist=float(data.get("gamma_moist", 18.0)),
            gamma_sat=float(data.get("gamma_sat", 20.0)),
            c_prime=float(data.get("c_prime", 0.0)),
            phi_prime=float(data.get("phi_prime", 30.0)),
            cu=float(data.get("cu", 0.0) or 0.0),
            is_undrained=bool(data.get("is_undrained", False)),
            N_field=int(n_field) if n_field is not None else None,
            N_corrected=int(n_corr) if n_corr is not None else None,
            Cc=float(data["Cc"]) if data.get("Cc") is not None else None,
            Cr=float(data["Cr"]) if data.get("Cr") is not None else None,
            e0=float(data["e0"]) if data.get("e0") is not None else None,
            Pc_kPa=float(data["Pc_kPa"]) if data.get("Pc_kPa") is not None else None,
            cv_m2s=float(data["cv_m2s"]) if data.get("cv_m2s") is not None else None,
            is_clay=bool(data.get("is_clay", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize back to the canonical session-state dictionary format."""
        return {
            "depth_top": self.depth_top,
            "depth_bot": self.depth_bot,
            "name": self.name,
            "symbol": self.symbol,
            "gamma_moist": self.gamma_moist,
            "gamma_sat": self.gamma_sat,
            "c_prime": self.c_prime,
            "phi_prime": self.phi_prime,
            "cu": self.cu,
            "is_undrained": self.is_undrained,
            "N_field": self.N_field,
            "N_corrected": self.N_corrected,
            "Cc": self.Cc,
            "Cr": self.Cr,
            "e0": self.e0,
            "Pc_kPa": self.Pc_kPa,
            "cv_m2s": self.cv_m2s,
            "is_clay": self.is_clay,
        }


# ---------------------------------------------------------------------------
# Profile Continuity & Depth Coverage Validation
# ---------------------------------------------------------------------------
class SoilProfileValidationError(ValueError):
    """Raised when a soil profile violates thickness, continuity, or depth rules."""


@dataclass(frozen=True)
class ProfileValidationReport:
    """Structured validation outcome for a layered subsurface profile."""

    is_valid: bool
    errors: tuple[str, ...]
    overlaps: tuple[tuple[str, str, float, float], ...]
    gaps: tuple[tuple[float, float], ...]
    max_depth_m: float

    def raise_if_invalid(self) -> None:
        """Raise SoilProfileValidationError if any validation rule failed."""
        if not self.is_valid:
            raise SoilProfileValidationError("\n".join(self.errors))


def validate_soil_layers(
    layers: Sequence[Mapping[str, Any] | SoilLayer],
    required_start_m: float = 0.0,
    founding_depth_m: Optional[float] = None,
    required_end_m: Optional[float] = None,
    tol: float = 1e-6,
) -> ProfileValidationReport:
    """
    Validate layered soil profile geometry for geotechnical analysis:
      1. Reject empty profiles or layers with depth_bot <= depth_top (or depth_top < 0).
      2. Detect overlaps and gaps from required_start_m (default 0.0 m bgl).
      3. Require a valid layer covering founding_depth_m (when provided) and
         continuous strata through required_end_m (when provided).
    """
    errors: list[str] = []
    overlaps: list[tuple[str, str, float, float]] = []
    gaps: list[tuple[float, float]] = []

    if not layers:
        errors.append("Soil profile is empty. Add at least one soil layer.")
        return ProfileValidationReport(
            is_valid=False,
            errors=tuple(errors),
            overlaps=(),
            gaps=(),
            max_depth_m=0.0,
        )

    valid_entries: list[tuple[int, str, float, float]] = []
    for idx, raw in enumerate(layers, start=1):
        if isinstance(raw, SoilLayer):
            d_top, d_bot = raw.depth_top, raw.depth_bot
            name = raw.name
        else:
            d_top = float(raw["depth_top"])
            d_bot = float(raw["depth_bot"])
            name = str(raw.get("name", raw.get("symbol", f"Layer {idx}")))

        if d_top < -tol:
            errors.append(
                f"Layer {idx} ({name}): depth_top ({d_top:.2f} m) must be >= 0.00 m bgl."
            )
            continue
        if d_bot <= d_top + tol:
            errors.append(
                f"Layer {idx} ({name}): depth_bot ({d_bot:.2f} m) must be greater than "
                f"depth_top ({d_top:.2f} m) (positive thickness required)."
            )
            continue
        valid_entries.append((idx, name, d_top, d_bot))

    if not valid_entries:
        return ProfileValidationReport(
            is_valid=False,
            errors=tuple(errors),
            overlaps=(),
            gaps=(),
            max_depth_m=0.0,
        )

    ordered = sorted(valid_entries, key=lambda item: (item[2], item[3]))
    first_idx, first_name, first_top, first_bot = ordered[0]

    if first_top > required_start_m + tol:
        gaps.append((required_start_m, first_top))
        errors.append(
            f"Gap from {required_start_m:.2f} m to {first_top:.2f} m bgl: "
            f"profile must start continuously at ground level ({required_start_m:.2f} m)."
        )

    prev_idx, prev_name, prev_top, prev_end = first_idx, first_name, first_top, first_bot
    for curr_idx, curr_name, curr_top, curr_bot in ordered[1:]:
        if curr_top < prev_end - tol:
            ov_end = min(prev_end, curr_bot)
            overlaps.append(
                (f"Layer {prev_idx} ({prev_name})", f"Layer {curr_idx} ({curr_name})", curr_top, ov_end)
            )
            errors.append(
                f"Overlap between Layer {prev_idx} ({prev_name}: {prev_top:.2f}–{prev_end:.2f} m) "
                f"and Layer {curr_idx} ({curr_name}: {curr_top:.2f}–{curr_bot:.2f} m) "
                f"over {curr_top:.2f}–{ov_end:.2f} m."
            )
        elif curr_top > prev_end + tol:
            gaps.append((prev_end, curr_top))
            errors.append(
                f"Gap between Layer {prev_idx} ({prev_name}, ends {prev_end:.2f} m) "
                f"and Layer {curr_idx} ({curr_name}, starts {curr_top:.2f} m) "
                f"over {prev_end:.2f}–{curr_top:.2f} m."
            )
        if curr_bot > prev_end:
            prev_idx, prev_name, prev_top, prev_end = curr_idx, curr_name, curr_top, curr_bot

    max_depth = max(item[3] for item in ordered)

    if founding_depth_m is not None:
        if founding_depth_m < -tol:
            errors.append(
                f"Founding depth Df ({founding_depth_m:.2f} m) must be >= 0.00 m bgl."
            )
        else:
            covers_df = any(
                (top - tol <= founding_depth_m < bot - tol)
                for _, _, top, bot in ordered
            )
            in_gap = any(g_start - tol <= founding_depth_m <= g_end + tol for g_start, g_end in gaps)
            if not covers_df or in_gap:
                errors.append(
                    f"No valid soil layer covers founding depth Df = {founding_depth_m:.2f} m bgl "
                    f"(profile extends to {max_depth:.2f} m bgl)."
                )

    if required_end_m is not None and max_depth < required_end_m - tol:
        errors.append(
            f"Insufficient profile depth: profile ends at {max_depth:.2f} m bgl, "
            f"but required analysis depth is {required_end_m:.2f} m bgl."
        )

    return ProfileValidationReport(
        is_valid=(len(errors) == 0),
        errors=tuple(errors),
        overlaps=tuple(overlaps),
        gaps=tuple(gaps),
        max_depth_m=max_depth,
    )


@dataclass(frozen=True)
class SoilProfile:
    """
    Ordered subsurface profile with shared effective-stress integration.

    Single source of truth for vertical total stress, pore-water pressure, and
    effective vertical stress across SPT, stress-increase, and settlement modules.
    """

    layers: tuple[SoilLayer, ...]
    groundwater: Optional[GroundwaterProfile] = None
    borehole_name: str = "BH-1"

    def __post_init__(self) -> None:
        sorted_layers = tuple(sorted(self.layers, key=lambda lyr: lyr.depth_top))
        object.__setattr__(self, "layers", sorted_layers)

    @classmethod
    def from_dicts(
        cls,
        layers: Sequence[Mapping[str, Any]],
        wt_design_bgl: float = 0.0,
        wt_measured_bgl: Optional[float] = None,
        ground_rl: float = 100.0,
        borehole_name: str = "BH-1",
    ) -> "SoilProfile":
        """Build a SoilProfile from a sequence of session-state layer dicts."""
        wt_meas = wt_design_bgl if wt_measured_bgl is None else wt_measured_bgl
        gw = GroundwaterProfile(
            wt_measured_bgl=float(wt_meas),
            wt_design_bgl=float(wt_design_bgl),
            ground_rl=float(ground_rl),
        )
        typed_layers = tuple(SoilLayer.from_dict(d) for d in layers)
        return cls(layers=typed_layers, groundwater=gw, borehole_name=borehole_name)

    def _resolve_wt(self, wt_bgl: Optional[float]) -> float:
        if wt_bgl is not None:
            return float(wt_bgl)
        if self.groundwater is not None:
            return self.groundwater.wt_design_bgl
        return 0.0

    def total_vertical_stress(
        self, depth_m: float, wt_bgl: Optional[float] = None
    ) -> float:
        """
        Compute total vertical overburden stress σv (kPa) at depth_m (m bgl),
        using γ_moist above the water table and γ_sat below.

        Cite: Das (2016) Eq. 2.1–2.2
        """
        if depth_m <= 0.0 or not self.layers:
            return 0.0

        wt = self._resolve_wt(wt_bgl)
        sigma_v = 0.0

        for lyr in self.layers:
            if lyr.depth_top >= depth_m:
                break
            seg_top = lyr.depth_top
            seg_bot = min(lyr.depth_bot, depth_m)
            if seg_bot <= seg_top:
                continue

            # Exact piecewise split across the water table within the stratum
            dz_above = max(0.0, min(seg_bot, wt) - seg_top)
            dz_below = max(0.0, seg_bot - max(seg_top, wt))
            sigma_v += lyr.gamma_moist * dz_above + lyr.gamma_sat * dz_below  # Das (2016) Eq. 2.1-2.2

        return max(sigma_v, 0.0)

    def pore_water_pressure(
        self, depth_m: float, wt_bgl: Optional[float] = None, gamma_w: float = GAMMA_W
    ) -> float:
        """
        Compute hydrostatic pore-water pressure u (kPa) at depth_m (m bgl).

        Cite: Das (2016) Eq. 2.9
        """
        wt = self._resolve_wt(wt_bgl)
        if depth_m <= wt:
            return 0.0
        return gamma_w * (depth_m - wt)  # Das (2016) Eq. 2.9: u = γw * hw

    def effective_vertical_stress(
        self, depth_m: float, wt_bgl: Optional[float] = None, gamma_w: float = GAMMA_W
    ) -> float:
        """
        Compute vertical effective stress σ′v0 (kPa) at depth_m (m bgl):
            σ′v0 = Σ(γ_moist · Δz_above) + Σ((γ_sat − γw) · Δz_below)

        Uses exact piecewise splitting if a stratum straddles the water table.

        Cite: Terzaghi (1936); Das (2016) Eq. 2.10; IS 2131:1981 Annex B
        """
        if depth_m <= 0.0 or not self.layers:
            return 0.0

        wt = self._resolve_wt(wt_bgl)
        sigma_eff = 0.0

        for lyr in self.layers:
            if lyr.depth_top >= depth_m:
                break
            seg_top = lyr.depth_top
            seg_bot = min(lyr.depth_bot, depth_m)
            if seg_bot <= seg_top:
                continue

            dz_above = max(0.0, min(seg_bot, wt) - seg_top)
            dz_below = max(0.0, seg_bot - max(seg_top, wt))

            # Das (2016) Eq. 2.10: σ′v = σv − u = γ_moist*z_above + (γ_sat − γw)*z_below
            sigma_eff += (
                lyr.gamma_moist * dz_above
                + (lyr.gamma_sat - gamma_w) * dz_below
            )

        return max(sigma_eff, 0.0)

    def layer_at_depth(self, depth_m: float) -> Optional[SoilLayer]:
        """Return the layer containing depth_m (m bgl), or deepest layer below."""
        for lyr in self.layers:
            if lyr.depth_top <= depth_m < lyr.depth_bot:
                return lyr
        return self.layers[-1] if self.layers else None

    def validate(
        self,
        required_start_m: float = 0.0,
        founding_depth_m: Optional[float] = None,
        required_end_m: Optional[float] = None,
    ) -> ProfileValidationReport:
        """Validate continuity, thickness, founding depth, and analysis depth."""
        return validate_soil_layers(
            self.layers,
            required_start_m=required_start_m,
            founding_depth_m=founding_depth_m,
            required_end_m=required_end_m,
        )


# ---------------------------------------------------------------------------
# Footing & Load Domain Models
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FootingGeometry:
    """
    Shallow foundation geometry in SI units (m).
    """

    B: float
    L: float
    Df: float = 0.0
    shape: FootingShape = "rectangular"

    def __post_init__(self) -> None:
        if self.B <= 0.0:
            raise ValueError(f"Footing width B ({self.B} m) must be > 0.")
        if self.L <= 0.0:
            raise ValueError(f"Footing length L ({self.L} m) must be > 0.")
        if self.Df < 0.0:
            raise ValueError(f"Founding depth Df ({self.Df} m) must be >= 0.")

    @property
    def area(self) -> float:
        """Plan area B × L (m²)."""
        return self.B * self.L

    @property
    def aspect_ratio(self) -> float:
        """L / B ratio (dimensionless)."""
        return self.L / self.B

    @property
    def is_strip(self) -> bool:
        """True if strip footing or L/B >= 10 (Schmertmann et al. 1978 Fig. 4)."""
        return self.shape == "strip" or self.aspect_ratio >= 10.0


@dataclass(frozen=True)
class FoundationLoad:
    """
    Column service load acting at footing founding level.
    """

    P_kN: float
    ex: float = 0.0
    ey: float = 0.0
    alpha_deg: float = 0.0

    def __post_init__(self) -> None:
        if self.P_kN < 0.0:
            raise ValueError(f"Vertical load P_kN ({self.P_kN} kN) must be >= 0.")
        if self.ex < 0.0 or self.ey < 0.0:
            raise ValueError("Eccentricities ex and ey must be >= 0 m.")
        if self.alpha_deg < 0.0 or self.alpha_deg >= 90.0:
            raise ValueError("Load inclination alpha_deg must lie in [0, 90)°.")


# ---------------------------------------------------------------------------
# Typed Computation Result Value Objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SPTCorrectionStep:
    """Step-by-step IS 2131:1981 SPT correction trace for a single stratum."""

    layer_idx: int
    depth_mid_m: float
    sigma_v_kPa: float
    CN: float
    N_field: int
    N_corr1: int
    dilatancy_applied: bool
    N_corrected: int
    overburden_method: str = "IS 2131:1981 Annex B (Peck et al. 1974)"
    dilatancy_method: str = "IS 2131:1981 Cl. 4.6 (Terzaghi & Peck 1967)"

    def to_dict(self) -> dict[str, Any]:
        """Adapter to legacy dictionary keys expected by P2 UI."""
        return {
            "layer_idx": self.layer_idx,
            "depth_mid": self.depth_mid_m,
            "sigma_v": self.sigma_v_kPa,
            "CN": self.CN,
            "N_field": self.N_field,
            "N_corr1": self.N_corr1,
            "dilatancy_applied": self.dilatancy_applied,
            "N_corrected": self.N_corrected,
        }


@dataclass(frozen=True)
class MohrCoulombFitResult:
    """Least-squares linear regression output for τ = c′ + σn · tan(φ′)."""

    c_prime_kPa: float
    phi_prime_deg: float
    r_squared: float
    n_points: int
    residuals_kPa: tuple[float, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StressProfileResult:
    """Vertical stress increase profile Δσz(z) beneath a loaded footing."""

    z_m: np.ndarray
    delta_sigma_kPa: np.ndarray
    method_name: str
    q_net_kPa: float


@dataclass(frozen=True)
class SchmertmannSublayerResult:
    """Per-sublayer breakdown for Schmertmann et al. (1978) settlement."""

    z_top_m: float
    z_bot_m: float
    z_mid_m: float
    layer_name: str
    symbol: str
    Es_kPa: float
    Iz: float
    Iz_over_Es: float
    dz_m: float
    contrib_m: float

    def to_dict(self) -> dict[str, Any]:
        """Adapter to dictionary keys expected by P5 UI."""
        return {
            "z_top_m": round(self.z_top_m, 3),
            "z_bot_m": round(self.z_bot_m, 3),
            "z_mid_m": round(self.z_mid_m, 3),
            "layer_name": self.layer_name,
            "symbol": self.symbol,
            "Es_kPa": round(self.Es_kPa, 1),
            "Iz": round(self.Iz, 4),
            "Iz_over_Es": round(self.Iz_over_Es, 8),
            "dz_m": round(self.dz_m, 3),
            "contrib_m": round(self.contrib_m, 8),
        }


@dataclass(frozen=True)
class SchmertmannResult:
    """Complete Schmertmann et al. (1978) immediate settlement result."""

    S_mm: float
    C1: float
    C2: float
    delta_p_kPa: float
    Iz_peak: float
    sigma_v0_kPa: float
    sublayers: tuple[SchmertmannSublayerResult, ...]

    def to_dict(self) -> dict[str, Any]:
        """Adapter to dictionary keys expected by P5 UI."""
        return {
            "S_mm": round(self.S_mm, 2),
            "C1": round(self.C1, 4),
            "C2": round(self.C2, 4),
            "delta_p": round(self.delta_p_kPa, 2),
            "Iz_peak": round(self.Iz_peak, 4),
            "sigma_v0": round(self.sigma_v0_kPa, 2),
            "sublayer_data": [s.to_dict() for s in self.sublayers],
        }


@dataclass(frozen=True)
class ConsolidationSublayerResult:
    """Per-sublayer breakdown for 1D Terzaghi primary consolidation settlement."""

    z_mid_bgl_m: float
    z_below_footing_m: float
    layer_name: str
    sigma_v0_kPa: float
    delta_sigma_kPa: float
    sigma_f_kPa: float
    Pc_kPa: float
    case: ConsolidationRegime
    Sc_mm: float
    dz_m: float

    def to_dict(self) -> dict[str, Any]:
        """Adapter to dictionary keys expected by P5 UI."""
        return {
            "z_mid_bgl_m": round(self.z_mid_bgl_m, 3),
            "z_below_footing_m": round(self.z_below_footing_m, 3),
            "layer_name": self.layer_name,
            "sigma_v0_kPa": round(self.sigma_v0_kPa, 2),
            "delta_sigma_kPa": round(self.delta_sigma_kPa, 2),
            "sigma_f_kPa": round(self.sigma_f_kPa, 2),
            "Pc_kPa": round(self.Pc_kPa, 2),
            "case": self.case,
            "Sc_mm": round(self.Sc_mm, 3),
            "dz_m": round(self.dz_m, 3),
        }


@dataclass(frozen=True)
class ConsolidationResult:
    """Total 1D primary consolidation settlement result across clay strata."""

    S_total_mm: float
    sublayers: tuple[ConsolidationSublayerResult, ...]

    def to_dict(self) -> dict[str, Any]:
        """Adapter to dictionary keys expected by P5 UI."""
        return {
            "S_total_mm": round(self.S_total_mm, 2),
            "sublayer_data": [s.to_dict() for s in self.sublayers],
        }


@dataclass(frozen=True)
class TimeSettlementResult:
    """Terzaghi 1D time-rate consolidation curve output."""

    t_years: np.ndarray
    U: np.ndarray
    S_mm: np.ndarray
    Hdr_m: float
    cv_m2s: float
    drainage: DrainageCondition
