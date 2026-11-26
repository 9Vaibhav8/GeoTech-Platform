"""
utils/constants.py
Shared session state keys, default layer structure, and soil symbols.
"""
import streamlit as st

# IS 1498 soil symbols available in the app
SOIL_SYMBOLS = ["Fill", "SM", "SP", "SW", "SC", "ML", "CL", "CI", "CH", "MH", "GW", "GP", "GM", "GC"]

# Default layer structure — every layer dict follows this schema
# Default layer structure — every layer dict follows this schema
DEFAULT_LAYER = {
    "depth_top": 0.0,      # m bgl (below ground level)
    "depth_bot": 1.5,      # m bgl
    "name": "Layer",       # descriptive name
    "symbol": "SM",        # IS 1498 symbol
    "gamma_moist": 18.0,   # kN/m³
    "gamma_sat": 20.0,     # kN/m³
    "c_prime": 0.0,        # kPa  — drained cohesion c'
    "phi_prime": 30.0,     # degrees — drained friction angle φ'
    "cu": 0.0,             # kPa  — undrained shear strength (0 if N/A)
    "is_undrained": False, # True for UU analysis of clay
    "Es_kPa": None,        # Elastic modulus Es in kPa (None if not entered / use SPT correlation)
    "N_field": None,       # Observed SPT N (None if not tested)
    "N_corrected": None,   # IS 2131 corrected N (filled by P2)
    # Consolidation params (clay layers only; None if not applicable)
    "Cc": None,            # Compression index
    "Cr": None,            # Recompression index
    "e0": None,            # Initial void ratio
    "Pc_kPa": None,        # Preconsolidation pressure kPa
    "cv_m2s": None,        # Coefficient of consolidation m²/s
    "is_clay": False,      # True if consolidation settlement applies
}


def init_session_state():
    """Initialize all session state keys if not already set."""
    if "layers" not in st.session_state:
        # Default: a simple 3-layer profile
        st.session_state.layers = [
            {**DEFAULT_LAYER, "depth_top": 0.0, "depth_bot": 1.5,
             "name": "Sandy Silt Fill", "symbol": "SM",
             "gamma_moist": 16.5, "gamma_sat": 19.0,
             "c_prime": 0.0, "phi_prime": 28.0, "N_field": 10},
            {**DEFAULT_LAYER, "depth_top": 1.5, "depth_bot": 5.0,
             "name": "Medium Dense Sand", "symbol": "SP",
             "gamma_moist": 19.0, "gamma_sat": 20.5,
             "c_prime": 0.0, "phi_prime": 32.0, "N_field": 25},
            {**DEFAULT_LAYER, "depth_top": 5.0, "depth_bot": 10.0,
             "name": "Silty Clay", "symbol": "CI",
             "gamma_moist": 18.5, "gamma_sat": 18.5,
             "c_prime": 5.0, "phi_prime": 20.0, "cu": 30.0,
             "is_undrained": True, "is_clay": True,
             "Cc": 0.31, "Cr": 0.06, "e0": 0.918, "Pc_kPa": 200.0,
             "cv_m2s": 6.3e-8},
        ]
    if "wt_measured_bgl" not in st.session_state:
        st.session_state.wt_measured_bgl = 2.6   # m bgl
    if "wt_design_bgl" not in st.session_state:
        st.session_state.wt_design_bgl = 1.0     # m bgl (worst case — highest seasonal)
    if "ground_rl" not in st.session_state:
        st.session_state.ground_rl = 100.0        # m RL
    if "borehole_name" not in st.session_state:
        st.session_state.borehole_name = "BH-1"
