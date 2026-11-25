"""
utils/bearing_capacity_presenter.py
Presenter & Plotly chart builder for IS 6403:1981 bearing capacity UI (SRP).

Separates visualization and display-table formatting from both pure-domain
calculations (`utils/bearing_capacity.py`) and Streamlit layout/widget binding
(`pages/3_🏗️_Bearing_Capacity.py`).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from utils.bearing_capacity import (
    BearingCapacityResult,
    FootingSpec,
    IS6403Solver,
    SoilFoundingState,
    compute_effective_overburden,
)


class BearingCapacityPresenter:
    """Builds tabular summaries and Plotly figures for IS 6403:1981 results."""

    @staticmethod
    def build_factors_dataframe(result: BearingCapacityResult) -> pd.DataFrame:
        """Format every IS 6403:1981 factor, geometry metric, and clause citation."""
        mode_ref = (
            "Cl. 5.1.3"
            if result.failure_mode == "undrained"
            else ("Cl. 5.1.2.2" if result.failure_mode == "local" else "Cl. 5.1.2")
        )
        rows = [
            ("Nc", f"{result.Nc:.4f}", "—", "Table 1 / Cl. 5.1.2"),
            ("Nq", f"{result.Nq:.4f}", "—", "Table 1 / Cl. 5.1.2"),
            ("Nγ (Vesic)", f"{result.Ngamma:.4f}", "—", "Table 1 / Cl. 5.1.2"),
            ("sc (shape, c-term)", f"{result.sc:.4f}", "—", "Cl. 5.1.2.1"),
            ("sq (shape, q-term)", f"{result.sq:.4f}", "—", "Cl. 5.1.2.1"),
            ("sγ (shape, γ-term)", f"{result.sgamma:.4f}", "—", "Cl. 5.1.2.1"),
            ("dc (depth, c-term)", f"{result.dc:.4f}", "—", "Cl. 5.1.2.1"),
            ("dq (depth, q-term)", f"{result.dq:.4f}", "—", "Cl. 5.1.2.1"),
            ("dγ (depth, γ-term)", f"{result.dgamma:.4f}", "—", "Cl. 5.1.2.1"),
            ("ic (inclination, c-term)", f"{result.ic:.4f}", "—", "Cl. 5.1.2.1"),
            ("iq (inclination, q-term)", f"{result.iq:.4f}", "—", "Cl. 5.1.2.1"),
            ("iγ (inclination, γ-term)", f"{result.igamma:.4f}", "—", "Cl. 5.1.2.1"),
            ("W′ (water-table factor)", f"{result.W_prime:.4f}", "—", "Cl. 5.1.2.3"),
            ("q (effective overburden at Df)", f"{result.q_eff:.3f}", "kPa", "Cl. 5.1.2"),
            ("γ (bulk/sat in Nγ term)", f"{result.gamma_ngamma:.3f}", "kN/m³", "Cl. 5.1.2.3"),
            ("B′ = min(B_eff, L_eff)", f"{result.B_prime:.3f}", "m", "Cl. 5.4"),
            ("L′ = max(B_eff, L_eff)", f"{result.L_prime:.3f}", "m", "Cl. 5.4"),
            ("A_eff (effective area)", f"{result.A_eff:.3f}", "m²", "Cl. 5.4"),
            ("c_used (mobilized)", f"{result.c_used:.2f}", "kPa", mode_ref),
            ("φ_used (mobilized)", f"{result.phi_used:.2f}", "°", mode_ref),
        ]
        return pd.DataFrame(rows, columns=["Parameter", "Value", "Unit", "IS 6403:1981 Clause"])

    @staticmethod
    def create_water_table_sensitivity_figure(
        solver: IS6403Solver,
        footing: FootingSpec,
        soil_template: SoilFoundingState,
        layers: Sequence[Mapping[str, Any]],
        FOS: float,
        failure_mode: str,
        use_profile_overburden: bool = True,
    ) -> go.Figure:
        """
        Plot qnu (kPa) and qns (kPa) against water-table depth (m bgl) per Cl. 5.1.2.3.
        """
        B_ref = footing.B
        wt_range = np.linspace(0.0, footing.Df + max(B_ref * 2.0, 2.0), 60)
        qnu_values: list[float] = []
        qns_values: list[float] = []

        for wt_i in wt_range:
            wt_val = float(wt_i)
            q_eff_i = (
                compute_effective_overburden(layers, footing.Df, wt_val)
                if use_profile_overburden and layers
                else None
            )
            soil_i = SoilFoundingState(
                c_prime=soil_template.c_prime,
                phi_prime_deg=soil_template.phi_prime_deg,
                gamma_moist=soil_template.gamma_moist,
                gamma_sat=soil_template.gamma_sat,
                wt_bgl=wt_val,
                q_eff=q_eff_i,
                is_undrained=soil_template.is_undrained,
                cu=soil_template.cu,
            )
            res_i = solver.solve(footing, soil_i, FOS=FOS, failure_mode=failure_mode)
            qnu_values.append(res_i.qnu)
            qns_values.append(res_i.qns)

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=wt_range,
                y=qnu_values,
                mode="lines+markers",
                name="qnu — Net Ultimate (kPa)",
                line=dict(color="#1f4e79", width=2.5),
                marker=dict(size=4),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=wt_range,
                y=qns_values,
                mode="lines",
                name=f"qns — Net Safe (kPa, FOS={FOS:.1f})",
                line=dict(color="#27ae60", width=2.0, dash="dash"),
            )
        )
        fig.add_vline(
            x=soil_template.wt_bgl,
            line_dash="dash",
            line_color="blue",
            annotation_text=f"Design WT = {soil_template.wt_bgl:.2f} m",
            annotation_position="top right",
        )
        fig.add_vline(
            x=footing.Df,
            line_dash="dot",
            line_color="orange",
            annotation_text=f"Footing base Df = {footing.Df:.2f} m",
            annotation_position="top left",
        )
        fig.update_layout(
            title="Bearing Capacity vs. Water Table Depth (IS 6403:1981 Cl. 5.1.2.3)",
            xaxis_title="Water Table Depth (m bgl)",
            yaxis_title="Bearing Capacity (kPa)",
            template="plotly_white",
            height=420,
            legend=dict(orientation="h", y=-0.2),
        )
        return fig

    @staticmethod
    def create_term_contribution_figure(result: BearingCapacityResult) -> go.Figure:
        """
        Plot the c, (Nq - 1), and Nγ contributions to net ultimate bearing capacity qnu (kPa).
        """
        c_term = result.c_used * result.Nc * result.sc * result.dc * result.ic
        q_term = (
            0.0
            if result.failure_mode == "undrained"
            else result.q_eff * (result.Nq - 1.0) * result.sq * result.dq * result.iq
        )
        gamma_term = (
            0.0
            if result.failure_mode == "undrained"
            else 0.5
            * result.B_prime
            * result.gamma_ngamma
            * result.Ngamma
            * result.sgamma
            * result.dgamma
            * result.igamma
            * result.W_prime
        )
        labels = ["Cohesion (c·Nc…)", "Overburden (q·(Nq−1)…)", "Self-weight (0.5·B′·γ·Nγ·W′…)"]
        vals = [c_term, q_term, gamma_term]

        fig = go.Figure(
            go.Bar(
                x=labels,
                y=vals,
                marker_color=["#2980b9", "#e67e22", "#16a085"],
                text=[f"{v:.1f} kPa" for v in vals],
                textposition="outside",
            )
        )
        fig.update_layout(
            title="IS 6403:1981 qnu Term Breakdown (kPa)",
            yaxis_title="Pressure Contribution (kPa)",
            template="plotly_white",
            height=340,
        )
        return fig
