"""
utils/constants.py
Shared session state keys, editable example profile, and soil symbols.
All initial soil/site values are illustrative, not measured data or calculation constants.
"""
import streamlit as st

# IS 1498 soil symbols available in the app
SOIL_SYMBOLS = ["Fill", "SM", "SP", "SW", "SC", "ML", "CL", "CI", "CH", "MH", "GW", "GP", "GM", "GC"]

# Editable starter layer — values are illustrative, not measured soil properties.
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
    "Es_kPa": None,        # Elastic modulus Es in kPa (None if not entered; optional SPT estimate used)
    "N_field": None,       # Observed SPT N (None if not tested)
    "N_corrected": None,   # IS 2131 corrected N (filled by P2)
    "N_refusal": False,    # Refusal is not an exact SPT N
    "N_refusal_note": "", # Reported blows / penetration, if applicable
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
        # Synthetic editable example (not the assignment borehole).
        # Retain a nonempty profile for existing modules that expect layers.
        st.session_state.layers = [
            {**DEFAULT_LAYER, "depth_top": 0.0, "depth_bot": 1.5,
             "name": "Example silty sand", "symbol": "SM",
             "gamma_moist": 17.0, "gamma_sat": 19.5,
             "c_prime": 0.0, "phi_prime": 28.0, "N_field": 10},
            {**DEFAULT_LAYER, "depth_top": 1.5, "depth_bot": 5.0,
             "name": "Example medium dense sand", "symbol": "SP",
             "gamma_moist": 19.0, "gamma_sat": 20.5,
             "c_prime": 0.0, "phi_prime": 32.0, "N_field": 25},
            {**DEFAULT_LAYER, "depth_top": 5.0, "depth_bot": 10.0,
             "name": "Example silty clay", "symbol": "CI",
             "gamma_moist": 18.5, "gamma_sat": 18.5,
             "c_prime": 5.0, "phi_prime": 20.0, "cu": 30.0,
             "is_undrained": True, "is_clay": True,
             "Cc": 0.25, "Cr": 0.04, "e0": 0.85, "Pc_kPa": 150.0,
             "cv_m2s": 5.0e-8},
        ]
    if "wt_measured_bgl" not in st.session_state:
        st.session_state.wt_measured_bgl = 3.0   # m bgl, illustrative
    if "wt_design_bgl" not in st.session_state:
        st.session_state.wt_design_bgl = 2.0   # m bgl, illustrative design water level
    if "ground_rl" not in st.session_state:
        st.session_state.ground_rl = 0.0   # m RL, illustrative datum
    if "borehole_name" not in st.session_state:
        st.session_state.borehole_name = "Example profile (edit before design)"
    if "foundation_depth" not in st.session_state:
        st.session_state.foundation_depth = 1.5  # m, editable P1 preview default
