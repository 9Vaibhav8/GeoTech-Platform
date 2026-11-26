"""
tests/test_geotech_benchmarks.py
Deterministic unit-test benchmark suite for the CE 402 Geotechnical Platform.

Verifies every backend module in `utils/` against published IS-code tables,
textbook hand calculations (Das 2016; Terzaghi 1943; Schmertmann et al. 1978),
and boundary/invariant conditions using SI units (kN, kPa, m, mm).
"""

from pathlib import Path
import math
import sys

import numpy as np
import pytest

# Ensure project root is importable regardless of pytest invocation CWD
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.spt_corrections import (
    effective_stress,
    overburden_correction,
    dilatancy_correction,
    correct_spt,
    fit_mohr_coulomb,
)
from utils.bearing_capacity import (
    bearing_capacity_factors,
    shape_factors,
    depth_factors,
    inclination_factors,
    water_table_factor,
    local_shear_params,
    effective_area,
    net_ultimate_bearing_capacity,
    net_safe_bearing_capacity,
)
from utils.stress_increase import (
    boussinesq_corner,
    stress_increase_centre,
    stress_increase_point,
    stress_increase_2to1,
)
from utils.settlement import (
    schmertmann_settlement,
    consolidation_settlement_layer,
    total_consolidation_settlement,
    degree_of_consolidation,
    time_factor,
)


# =============================================================================
# Fixtures: Assignment BH-1 Soil Profile (IIT Mandi CE 402)
# =============================================================================

@pytest.fixture
def bh1_profile():
    """
    BH-1 soil profile from CE 402 Assignment (near C4; Design WT = 1.0 m bgl,
    August seasonal high).
    """
    return [
        {
            "depth_top": 0.0, "depth_bot": 0.6, "name": "Fill", "symbol": "Fill",
            "gamma_moist": 16.5, "gamma_sat": 16.5, "c_prime": 0.0, "phi_prime": 26.0,
            "cu": 0.0, "is_undrained": False, "N_field": None, "N_corrected": None,
            "is_clay": False,
        },
        {
            "depth_top": 0.6, "depth_bot": 3.4, "name": "Silty Sand", "symbol": "SM",
            "gamma_moist": 18.0, "gamma_sat": 20.0, "c_prime": 5.0, "phi_prime": 31.0,
            "cu": 0.0, "is_undrained": False, "N_field": 16, "N_corrected": None,
            "is_clay": False,
        },
        {
            "depth_top": 3.4, "depth_bot": 5.8, "name": "Poorly Graded Sand", "symbol": "SP",
            "gamma_moist": 19.0, "gamma_sat": 20.4, "c_prime": 0.0, "phi_prime": 34.0,
            "cu": 0.0, "is_undrained": False, "N_field": 24, "N_corrected": None,
            "is_clay": False,
        },
        {
            "depth_top": 5.8, "depth_bot": 10.6, "name": "Silty Clay", "symbol": "CI",
            "gamma_moist": 18.6, "gamma_sat": 18.6, "c_prime": 5.0, "phi_prime": 22.0,
            "cu": 28.5, "is_undrained": True, "N_field": 22, "N_corrected": None,
            "Cc": 0.30, "Cr": 0.06, "e0": 0.918, "Pc_kPa": 120.0, "cv_m2s": 6.3e-8,
            "is_clay": True,
        },
    ]


# =============================================================================
# 1. IS 2131:1981 SPT Corrections & Mohr-Coulomb Fitting
# =============================================================================

class TestIS2131SPT:
    """Benchmarks for utils/spt_corrections.py (IS 2131:1981 Annex B & Cl. 4.6)."""

    @pytest.mark.parametrize("sigma_v_kpa", [0.0, 5.0, 15.0, 24.99])
    def test_cn_upper_clamp_low_overburden(self, sigma_v_kpa):
        """IS 2131:1981 Annex B — C_N capped at 2.0 for σ′v < 25 kPa."""
        assert overburden_correction(sigma_v_kpa) == pytest.approx(2.0, abs=1e-9)

    @pytest.mark.parametrize("sigma_v_kpa", [450.0, 600.0, 1000.0, 2000.0])
    def test_cn_lower_clamp_high_overburden(self, sigma_v_kpa):
        """IS 2131:1981 Annex B — C_N clamped at 0.5 for high overburden stress."""
        assert overburden_correction(sigma_v_kpa) == pytest.approx(0.5, abs=1e-9)

    def test_cn_bounds_and_peck_values(self):
        """Verify Peck et al. (1974) formula 0.77*log10(2000/σ′v) and [0.5, 2.0] bounds."""
        # Exact hand-calculated benchmarks
        assert overburden_correction(25.0) == pytest.approx(0.77 * math.log10(80.0), rel=1e-6)
        assert overburden_correction(100.0) == pytest.approx(0.77 * math.log10(20.0), rel=1e-6)
        assert overburden_correction(200.0) == pytest.approx(0.77, rel=1e-6)

        for sv in np.linspace(0.0, 1500.0, 151):
            cn = overburden_correction(float(sv))
            assert 0.5 <= cn <= 2.0

    @pytest.mark.parametrize("symbol", ["SM", "SP", "ML"])
    def test_dilatancy_threshold_at_15_not_triggered(self, symbol):
        """IS 2131:1981 Cl. 4.6 — N' = 15 below WT must NOT trigger dilatancy."""
        n_corr, applied = dilatancy_correction(N_corr1=15, symbol=symbol, depth_m=3.0, wt_bgl=1.0)
        assert applied is False
        assert n_corr == 15

    @pytest.mark.parametrize(
        "symbol,n_prime,expected_n",
        [
            ("SM", 16, 16),   # round(15 + 0.5*1) = 16; applied flag must still be True
            ("SM", 17, 16),   # 15 + 0.5*(17 - 15) = 16
            ("SP", 25, 20),   # 15 + 0.5*(25 - 15) = 20
            ("ML", 21, 18),   # 15 + 0.5*(21 - 15) = 18
        ],
    )
    def test_dilatancy_triggered_above_15_below_wt(self, symbol, n_prime, expected_n):
        """IS 2131:1981 Cl. 4.6 — N' > 15 below WT in SM/SP/ML triggers N = 15 + 0.5(N' - 15)."""
        n_corr, applied = dilatancy_correction(N_corr1=n_prime, symbol=symbol, depth_m=3.0, wt_bgl=1.0)
        assert applied is True
        assert n_corr == expected_n

    @pytest.mark.parametrize("depth_m,wt_bgl", [(1.0, 2.0), (2.0, 2.0)])
    def test_dilatancy_not_triggered_above_or_at_wt(self, depth_m, wt_bgl):
        """Dilatancy correction applies strictly below the design water table (depth > WT)."""
        n_corr, applied = dilatancy_correction(N_corr1=28, symbol="SM", depth_m=depth_m, wt_bgl=wt_bgl)
        assert applied is False
        assert n_corr == 28

    @pytest.mark.parametrize("clay_symbol", ["CI", "CL", "CH"])
    def test_dilatancy_non_trigger_in_clay(self, clay_symbol):
        """IS 2131:1981 Cl. 4.6 — Dilatancy correction must NOT trigger in cohesive clay (CI/CL/CH)."""
        n_corr, applied = dilatancy_correction(N_corr1=26, symbol=clay_symbol, depth_m=8.0, wt_bgl=1.0)
        assert applied is False
        assert n_corr == 26

    def test_correct_spt_chain_on_bh1_profile(self, bh1_profile):
        """End-to-end IS 2131 chain on BH-1: verifies σ′v, C_N, dilatancy on SP, and non-trigger in CI."""
        wt_design = 1.0  # August seasonal highest WT for BH-1
        # Mid-depth of SP (3.4-5.8 m) is 4.6 m:
        # 0.0-0.6: 0.6*16.5 = 9.90
        # 0.6-1.0: 0.4*18.0 = 7.20
        # 1.0-3.4: 2.4*(20.0 - 9.81) = 24.456
        # 3.4-4.6: 1.2*(20.4 - 9.81) = 12.708 -> sum = 54.264 kPa
        sv_sp = effective_stress(bh1_profile, depth_m=4.6, wt_bgl=wt_design)
        assert sv_sp == pytest.approx(54.264, abs=1e-3)

        records = correct_spt(bh1_profile, wt_design_bgl=wt_design)
        assert len(records) == 3  # SM, SP, CI (Fill has N_field=None)

        sm_rec, sp_rec, ci_rec = records
        # SM mid=2.0 m, σ′v = 9.9 + 7.2 + 1.0*(20-9.81) = 27.29 kPa, CN ≈ 1.436 -> N'=23 > 15 -> 19
        assert sm_rec["dilatancy_applied"] is True
        assert sm_rec["N_corrected"] == 19
        # SP mid=4.6 m, CN = 0.77*log10(2000/54.264) ≈ 1.206 -> N'=29 > 15 -> 22
        assert sp_rec["dilatancy_applied"] is True
        assert sp_rec["N_corrected"] == 22
        # CI clay mid=8.2 m, even with N_field=22 (cobble hit), dilatancy must NOT trigger
        assert ci_rec["dilatancy_applied"] is False
        assert ci_rec["N_corrected"] == ci_rec["N_corr1"]

    def test_fit_mohr_coulomb_exact_and_bh1_ds1(self):
        """Verify least-squares Mohr-Coulomb fit on exact envelope and BH-1 DS-1 lab data."""
        sigma_n = [50.0, 100.0, 150.0]
        c_true, phi_true = 12.0, 30.0
        tau_exact = [c_true + s * math.tan(math.radians(phi_true)) for s in sigma_n]
        c_fit, phi_fit, r2 = fit_mohr_coulomb(sigma_n, tau_exact)
        assert c_fit == pytest.approx(c_true, abs=1e-6)
        assert phi_fit == pytest.approx(phi_true, abs=1e-6)
        assert r2 == pytest.approx(1.0, abs=1e-9)

        # BH-1 DS-1 Soaked direct shear data (Assignment p. 6): (50, 29.8), (100, 58.9), (150, 87.5)
        c_ds, phi_ds, r2_ds = fit_mohr_coulomb([50.0, 100.0, 150.0], [29.8, 58.9, 87.5])
        assert phi_ds == pytest.approx(math.degrees(math.atan(0.577)), abs=0.05)
        assert c_ds == pytest.approx(1.033, abs=0.1)
        assert r2_ds > 0.9999


# =============================================================================
# 2. IS 6403:1981 Bearing Capacity
# =============================================================================

class TestIS6403BearingCapacity:
    """Benchmarks for utils/bearing_capacity.py (IS 6403:1981 Table 1, Table 2, Cl. 5 & 6)."""

    @pytest.mark.parametrize(
        "phi_deg,nc_ref,nq_ref,ngamma_ref",
        [
            (0.0, 5.14, 1.00, 0.00),
            (20.0, 14.83, 6.40, 5.39),
            (30.0, 30.14, 18.40, 22.40),
            (35.0, 46.12, 33.30, 48.03),
        ],
    )
    def test_table1_bearing_capacity_factors(self, phi_deg, nc_ref, nq_ref, ngamma_ref):
        """IS 6403:1981 Table 1 — Verify Nc, Nq, Nγ at φ = 0°, 20°, 30°, 35°."""
        nc, nq, ngamma = bearing_capacity_factors(phi_deg)
        assert nc == pytest.approx(nc_ref, abs=0.01)
        assert nq == pytest.approx(nq_ref, abs=0.01)
        assert ngamma == pytest.approx(ngamma_ref, abs=0.01)

    def test_table2_shape_factors(self):
        """IS 6403:1981 Table 2 — Verify shape factors for square, circular, strip, rectangular."""
        assert shape_factors("square", 2.0, 2.0) == pytest.approx((1.3, 1.2, 0.8))
        assert shape_factors("circular", 2.0, 2.0) == pytest.approx((1.3, 1.2, 0.6))
        assert shape_factors("strip", 2.0, 1e6) == pytest.approx((1.0, 1.0, 1.0))
        # Rectangular B=2.0, L=4.0 -> B/L=0.5 -> sc=sq=1.1, sgamma=0.8
        assert shape_factors("rectangular", 2.0, 4.0) == pytest.approx((1.1, 1.1, 0.8))

    @pytest.mark.parametrize(
        "wt_bgl,expected_w_prime",
        [
            (0.5, 0.5),     # WT < Df
            (1.5, 0.5),     # WT == Df
            (2.5, 0.75),    # WT == Df + 0.5*B (Df=1.5, B=2.0)
            (3.5, 1.0),     # WT == Df + B
            (6.0, 1.0),     # WT > Df + B
        ],
    )
    def test_water_table_factor_boundaries(self, wt_bgl, expected_w_prime):
        """IS 6403:1981 Cl. 5.1.2.3 — Verify W′ boundaries and midpoint interpolation."""
        assert water_table_factor(Df=1.5, B=2.0, wt_bgl=wt_bgl) == pytest.approx(expected_w_prime, abs=1e-9)

    def test_depth_inclination_local_shear_and_eccentricity(self):
        """Verify Cl. 5.1.2.1 depth factors, inclination factors, Cl. 5.1.3 local shear, Cl. 5.0.1 effective area."""
        # Depth factors: phi <= 10 -> dq = dgamma = 1.0
        dc0, dq0, dg0 = depth_factors(Df=1.5, B=2.0, phi_deg=0.0)
        assert dc0 == pytest.approx(1.0 + 0.2 * 1.0 * (1.5 / 2.0))
        assert (dq0, dg0) == (1.0, 1.0)

        # Depth factors: phi = 30 -> sqrt(Kp) = tan(60) = sqrt(3)
        dc30, dq30, dg30 = depth_factors(Df=1.5, B=2.0, phi_deg=30.0)
        s3 = math.sqrt(3.0)
        assert dc30 == pytest.approx(1.0 + 0.2 * s3 * 0.75)
        assert dq30 == pytest.approx(1.0 + 0.1 * s3 * 0.75)
        assert dg30 == pytest.approx(dq30)

        # Inclination factors at alpha = 0 -> (1, 1, 1); alpha = 15, phi = 30
        assert inclination_factors(0.0, 30.0) == pytest.approx((1.0, 1.0, 1.0))
        ic, iq, ig = inclination_factors(15.0, 30.0)
        assert ic == pytest.approx((1.0 - 15.0 / 90.0) ** 2)
        assert iq == pytest.approx(ic)
        assert ig == pytest.approx((1.0 - 15.0 / 30.0) ** 2)

        # Local shear modification
        c_loc, phi_loc = local_shear_params(30.0, 30.0)
        assert c_loc == pytest.approx(20.0)
        assert phi_loc == pytest.approx(math.degrees(math.atan((2.0 / 3.0) * math.tan(math.radians(30.0)))))

        # Effective area (eccentric loading)
        b_eff, l_eff, a_eff = effective_area(B=3.0, L=4.0, ex=0.25, ey=0.5)
        assert (b_eff, l_eff, a_eff) == pytest.approx((2.5, 3.0, 7.5))

    def test_net_ultimate_and_safe_bearing_capacity_hand_check(self):
        """Hand-calculated check for IS 6403 Cl. 5.1 & Cl. 6 (FOS = 3.0)."""
        # Drained cohesionless square footing: c'=0, phi'=30, gamma_m=18, gamma_sat=20, Df=1.5, B=2.0, WT=1.0
        res = net_ultimate_bearing_capacity(
            c_prime=0.0, phi_prime_deg=30.0, gamma_moist=18.0, gamma_sat=20.0,
            Df=1.5, B=2.0, L=2.0, wt_bgl=1.0, footing_shape="square", failure_mode="general",
        )
        # Hand calc: q_eff = 18*1.0 + (20 - 9.81)*0.5 = 23.095 kPa; W' = 0.5 (since WT < Df)
        q_eff_hand = 18.0 * 1.0 + (20.0 - 9.81) * 0.5
        nc, nq, ng = bearing_capacity_factors(30.0)
        dc, dq, dg = depth_factors(1.5, 2.0, 30.0)
        qnu_hand = q_eff_hand * (nq - 1.0) * 1.2 * dq + 0.5 * 18.0 * 2.0 * ng * 0.8 * dg * 0.5
        assert res["q_eff"] == pytest.approx(q_eff_hand, rel=1e-6)
        assert res["W_prime"] == pytest.approx(0.5)
        assert res["qnu"] == pytest.approx(qnu_hand, rel=1e-6)
        assert net_safe_bearing_capacity(res["qnu"], FOS=3.0) == pytest.approx(qnu_hand / 3.0, rel=1e-6)

        # Undrained clay (phi=0, cu=30 kPa), square B=2.0, Df=1.5
        res_u = net_ultimate_bearing_capacity(
            c_prime=0.0, phi_prime_deg=0.0, gamma_moist=18.5, gamma_sat=18.5,
            Df=1.5, B=2.0, L=2.0, wt_bgl=1.0, footing_shape="square",
            is_undrained=True, cu=30.0,
        )
        qnu_u_hand = 30.0 * 5.14 * 1.3 * (1.0 + 0.2 * 0.75)
        assert res_u["qnu"] == pytest.approx(qnu_u_hand, rel=1e-6)


# =============================================================================
# 3. Boussinesq Vertical Stress Increase
# =============================================================================

class TestBoussinesqStressIncrease:
    """Benchmarks for utils/stress_increase.py (Das 2016 Table 5.x & superposition)."""

    @pytest.mark.parametrize(
        "m,n,expected_i_sigma",
        [
            # Acute-angle branch: m^2 * n^2 <= 1 + m^2 + n^2 (Das 2016 Table 5.x)
            (0.1, 0.1, 0.0047),
            (0.5, 0.5, 0.0840),
            (0.4, 1.0, 0.1013),
            (1.0, 1.0, 0.1752),
            (1.5, 1.5, 0.2157),
            # Obtuse-angle branch: m^2 * n^2 > 1 + m^2 + n^2 (arctan + pi required)
            (2.0, 2.0, 0.2325),
            (2.0, 3.0, 0.2378),
            (3.0, 3.0, 0.2439),
        ],
    )
    def test_corner_influence_factor_das_2016(self, m, n, expected_i_sigma):
        """
        Verify corner I_sigma = Δσz / q against Das (2016) Table 5.2 / 5.4,
        explicitly covering both acute and obtuse (m^2 n^2 > 1 + m^2 + n^2) branches.
        """
        i_sigma = boussinesq_corner(q=1.0, B=m, L=n, z=1.0)
        assert i_sigma > 0.0
        assert i_sigma == pytest.approx(expected_i_sigma, abs=1e-4)

        # Symmetry check: I_sigma(m, n) == I_sigma(n, m)
        assert boussinesq_corner(q=1.0, B=n, L=m, z=1.0) == pytest.approx(i_sigma, rel=1e-12)

    def test_obtuse_branch_pi_offset_guard(self):
        """
        Verify m^2*n^2 > 1 + m^2 + n^2 returns the positive obtuse-angle result (~0.2325)
        rather than the erroneous negative value (~ -0.0175) obtained if pi is omitted.
        """
        m, n = 2.0, 2.0
        assert (m ** 2) * (n ** 2) > (1.0 + m ** 2 + n ** 2)
        i_sigma = boussinesq_corner(q=1.0, B=m, L=n, z=1.0)
        assert 0.20 < i_sigma < 0.25

    def test_centre_equals_four_times_quarter_corner(self):
        """Das (2016) Sec. 5.5 — Centre stress = 4 × corner(B/2, L/2)."""
        q, B, L = 200.0, 3.0, 5.0
        for z in [0.0, 0.5, 1.5, 3.0, 6.0]:
            centre = stress_increase_centre(q, B, L, z)
            four_corners = 4.0 * boussinesq_corner(q, B / 2.0, L / 2.0, z)
            point_centre = stress_increase_point(q, B, L, B / 2.0, L / 2.0, z)
            assert centre == pytest.approx(four_corners, rel=1e-12)
            assert point_centre == pytest.approx(centre, rel=1e-12)

    def test_superposition_invariance_under_rigid_translation_and_partition(self):
        """
        Verify superposition invariance:
        1. Rigid translation of both footing origin (x0, y0) and evaluation point (xp, yp)
           by an arbitrary vector (dx, dy) preserves Δσz identically.
        2. Partitioning a rectangle [0, B] × [0, L] at arbitrary internal lines (xs, ys)
           into 4 sub-rectangles and summing `stress_increase_point` equals the whole footing.
        """
        q, B, L, z = 150.0, 4.0, 6.0, 2.5

        def eval_global(x0, y0, xp, yp):
            return stress_increase_point(q, B, L, xp - x0, yp - y0, z)

        # Test interior, edge, corner, and exterior evaluation points
        test_points = [(2.0, 3.0), (1.1, 4.7), (0.0, 2.5), (0.0, 0.0), (5.2, -1.3)]
        shifts = [(10.5, -4.2), (-100.0, 250.0), (3.14, 2.71)]

        for xp, yp in test_points:
            base_val = eval_global(0.0, 0.0, xp, yp)
            for dx, dy in shifts:
                shifted_val = eval_global(dx, dy, xp + dx, yp + dy)
                assert shifted_val == pytest.approx(base_val, rel=1e-12, abs=1e-12)

        # Arbitrary sub-rectangle partition superposition
        xs, ys = 1.3, 2.2
        sub_rects = [
            (0.0, 0.0, xs, ys),
            (xs, 0.0, B - xs, ys),
            (0.0, ys, xs, L - ys),
            (xs, ys, B - xs, L - ys),
        ]
        for xp, yp in test_points:
            direct = stress_increase_point(q, B, L, xp, yp, z)
            superposed = sum(
                stress_increase_point(q, w, h, xp - rx, yp - ry, z)
                for rx, ry, w, h in sub_rects
            )
            assert superposed == pytest.approx(direct, rel=1e-12, abs=1e-12)

    def test_2to1_method_exact(self):
        """Verify 2:1 stress distribution Δσz = q·B·L / ((B + z)(L + z))."""
        assert stress_increase_2to1(200.0, 2.0, 3.0, 2.0) == pytest.approx(
            200.0 * 2.0 * 3.0 / (4.0 * 5.0), rel=1e-12
        )


# =============================================================================
# 4. Schmertmann (1978) & 1D Consolidation (Terzaghi 1943)
# =============================================================================

class TestSchmertmannAndConsolidation:
    """Benchmarks for utils/settlement.py (Schmertmann 1978; Terzaghi 1943; IS 8009)."""

    def test_schmertmann_c1_clamp_and_sublayer_discretization(self):
        """Verify C1 >= 0.5 clamp under high overburden / low Δp and sublayer thickness <= 0.5 m."""
        sand_profile = [
            {
                "depth_top": 0.0, "depth_bot": 12.0, "name": "Uniform Sand", "symbol": "SP",
                "gamma_moist": 19.0, "gamma_sat": 20.5, "N_field": 20, "N_corrected": 20,
                "is_clay": False,
            }
        ]
        # Deep footing Df=3.0 m, B=L=2.5 m, small load P=300 kN -> q_gross=48 kPa, σ′v0(3m) > Δp
        res_clamped = schmertmann_settlement(
            sand_profile, Df=3.0, B=2.5, L=2.5, P_kN=300.0, wt_design_bgl=1.0, t_years=50
        )
        assert res_clamped["C1"] == pytest.approx(0.5, abs=1e-9)
        assert all(row["dz_m"] <= 0.5 for row in res_clamped["sublayer_data"])

        # Normal load where C1 > 0.5 and <= 1.0
        res_normal = schmertmann_settlement(
            sand_profile, Df=1.5, B=2.0, L=2.0, P_kN=1000.0, wt_design_bgl=5.0, t_years=50
        )
        assert 0.5 < res_normal["C1"] <= 1.0
        assert all(0.0 < row["dz_m"] <= 0.5 for row in res_normal["sublayer_data"])
        assert res_normal["S_mm"] > 0.0

    def test_consolidation_three_branches(self):
        """
        Verify all three 1D consolidation branches in consolidation_settlement_layer:
        1. NC (σ′v0 >= Pc)
        2. OC (σ′v0 + Δσ <= Pc)
        3. OC -> NC (σ′v0 < Pc < σ′v0 + Δσ)
        """
        H, e0, Cc, Cr = 0.5, 0.9, 0.30, 0.06
        factor = H / (1.0 + e0)

        # 1. Normally Consolidated (σ′v0 = 150 >= Pc = 120)
        sc_nc, label_nc = consolidation_settlement_layer(H, e0, Cc, Cr, 150.0, 120.0, 50.0)
        expected_nc = Cc * factor * math.log10(200.0 / 150.0)
        assert label_nc == "NC"
        assert sc_nc == pytest.approx(expected_nc, rel=1e-12)

        # 2. Overconsolidated staying OC (σ′v0 = 80, Δσ = 30, σf = 110 <= Pc = 150)
        sc_oc, label_oc = consolidation_settlement_layer(H, e0, Cc, Cr, 80.0, 150.0, 30.0)
        expected_oc = Cr * factor * math.log10(110.0 / 80.0)
        assert label_oc == "OC"
        assert sc_oc == pytest.approx(expected_oc, rel=1e-12)

        # 3. Overconsolidated yielding into NC (σ′v0 = 80 < Pc = 120 < σf = 180)
        sc_oc_nc, label_oc_nc = consolidation_settlement_layer(H, e0, Cc, Cr, 80.0, 120.0, 100.0)
        expected_oc_nc = (
            Cr * factor * math.log10(120.0 / 80.0)
            + Cc * factor * math.log10(180.0 / 120.0)
        )
        assert label_oc_nc == "OC→NC"
        assert sc_oc_nc == pytest.approx(expected_oc_nc, rel=1e-12)

    def test_consolidation_sublayer_discretization_max_05m(self, bh1_profile):
        """IS 8009 / P5 Spec — Clay sublayers must never exceed 0.5 m even if larger thickness is passed."""
        # Request sublayer_thickness=2.0 m; backend must clamp to <= 0.5 m
        res = total_consolidation_settlement(
            bh1_profile, Df=1.5, B=2.5, L=2.5, P_kN=1493.5, wt_design_bgl=1.0, sublayer_thickness=2.0
        )
        sublayers = res["sublayer_data"]
        # BH-1 clay is 5.8-10.6 m (H = 4.8 m) -> at <= 0.5 m, needs at least ceil(4.8/0.5) = 10 sublayers
        assert len(sublayers) >= 10
        assert all(0.0 < row["dz_m"] <= 0.5 for row in sublayers)
        assert sum(row["dz_m"] for row in sublayers) == pytest.approx(4.8, abs=1e-6)
        assert res["S_total_mm"] > 0.0

    def test_terzaghi_degree_of_consolidation_benchmarks(self):
        """Terzaghi (1943) — Verify U(Tv=0.197) ≈ 0.50, U(Tv=0.848) ≈ 0.90, and drainage path ratio."""
        assert degree_of_consolidation(0.0) == pytest.approx(0.0, abs=1e-9)
        assert degree_of_consolidation(0.197) == pytest.approx(0.50, abs=1e-3)
        assert degree_of_consolidation(0.848) == pytest.approx(0.90, abs=1e-3)

        # Monotonicity check
        u_vals = degree_of_consolidation([0.0, 0.05, 0.197, 0.5, 0.848, 2.0])
        assert np.all(np.diff(u_vals) > 0.0)

        # Two-way drainage (Hdr = H/2) gives 4x Tv of one-way drainage (Hdr = H)
        cv, t_sec, H = 6.3e-8, 365.25 * 24 * 3600, 4.8
        tv_one_way = time_factor(cv, t_sec, H)
        tv_two_way = time_factor(cv, t_sec, H / 2.0)
        assert tv_two_way == pytest.approx(4.0 * tv_one_way, rel=1e-12)
