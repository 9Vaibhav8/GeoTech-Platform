# CE 402 — Geotechnical Engineering Platform
**IIT Mandi · School of Civil and Environmental Engineering**

A web-based geotechnical engineering platform for foundation design of a G+3 student hostel in Mandi, Himachal Pradesh (Seismic Zone V).

URL - https://geotech-platformgit-5hgqwskkbpyo8z2zykgfiq.streamlit.app/

---

## Modules

| Module | Description | IS Code |
|--------|-------------|---------|
| **P1** Soil Profile | Enter layered soil profile, measured & design water tables, draw borehole log | IS 1498:1970 |
| **P2** SPT Corrections | Overburden ($C_N$) and dilatancy corrections on field SPT $N$ with step-by-step trace | [IS 2131:1981](https://law.resource.org/pub/in/bis/S03/is.2131.1981.pdf) (Annex B, Cl. 4.6) |
| **P2** Laboratory — Direct Shear | Least-squares Mohr–Coulomb fit ($c'$, $\phi'$) from drained shear-box test data | [IS 2720 (Part 13):1986](https://law.resource.org/pub/in/bis/S03/is.2720.13.1986.pdf) |
| **P2** Laboratory — UU Triaxial | Undrained shear strength ($c_u$, $\phi_u = 0^\circ$) from unconsolidated undrained triaxial tests | [IS 2720 (Part 11):1993](https://law.resource.org/pub/in/bis/S03/is.2720.11.1993.pdf) |
| **P3** Bearing Capacity | Net ultimate & safe bearing capacity ($q_{nu}$, $q_{ns}$), eccentric effective area, footing sizing | IS 6403:1981 |
| **P4** Stress Increase | Boussinesq rectangular load (centre/corner superposition), 2:1 method | IS 8009:1976 Part 1 |
| **P5** Settlement | Schmertmann immediate + 1D consolidation (NC/OC), time–settlement, IS 1904 check | IS 1904:1986, IS 8009:1976 Part 1 |

### P2 Parameter Tools Breakdown
- **Field SPT Correction Tool (`IS 2131:1981`):** Applies overburden pressure correction ($C_N$ per Annex B) and saturated fine-sand/silt dilatancy correction (Cl. 4.6) to field SPT $N$ values, displaying intermediate $\sigma'_v$, $C_N$, $N'$, and final corrected $N$.
- **Laboratory Strength Tools (`IS 2720 Part 13:1986` & `IS 2720 Part 11:1993`):**
  - *Direct Shear Box (`IS 2720 Part 13:1986`):* Fits effective cohesion $c'$ and friction angle $\phi'$ ($\tau_f = c' + \sigma_n \tan\phi'$) by ordinary least-squares regression.
  - *UU Triaxial Compression (`IS 2720 Part 11:1993`):* Computes undrained shear strength $c_u = (\sigma_1 - \sigma_3)_f / 2$ assuming $\phi_u = 0^\circ$ for saturated cohesive specimens.

---

## How to Run Locally

### 1. Clone the repository
```bash
git clone https://github.com/9Vaibhav8/GeoTech-Platform.git
cd GeoTech-Platform
```

### 2. Create and activate a virtual environment (recommended)
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Launch the app
```bash
streamlit run Home.py
```

The app opens at **http://localhost:8501** in your browser.

---

## Project Structure

```
GeoTech-Platform/
├── Home.py                                # Landing page & navigation
├── pages/
│   ├── 1_🗺️_Soil_Profile.py              # P1 — Soil profile input & visualisation
│   ├── 2_⚙️_Parameters.py                # P2 — IS 2131 SPT & IS 2720 lab fitting
│   ├── 3_🏗️_Bearing_Capacity.py          # P3 — IS 6403:1981 bearing capacity
│   ├── 4_📊_Stress_Increase.py           # P4 — Boussinesq / 2:1 stress increase
│   └── 5_📐_Settlement.py                # P5 — Schmertmann + 1D consolidation
├── utils/
│   ├── constants.py                       # Shared session state & defaults
│   ├── models.py                          # Typed pure-domain schema & stress invariants
│   ├── bearing_capacity.py                # IS 6403:1981 pure-domain solver
│   ├── bearing_capacity_presenter.py      # Plotly charts & factor table presenter
│   ├── spt_corrections.py                 # IS 2131:1981 SPT & Mohr-Coulomb OLS
│   ├── stress_increase.py                 # Boussinesq & 2:1 vertical stress increase
│   └── settlement.py                      # Schmertmann (1978) + Terzaghi (1943)
├── requirements.txt
├── .streamlit/config.toml                 # Theme & server config
└── README.md
```

---

## Group Information

| Parameter | Value |
|---|---|
| Group number g | **3** |
| Load factor λ | **1.03** (= 1 + 3/100) |
| Corner load | **669.5 kN** |
| Edge load | **1 030 kN** |
| Interior load | **1 493.5 kN** |
| Design WT (BH-1) | 1.0 m bgl (Aug. highest) |
| Design WT (BH-2) | 1.7 m bgl (Aug. highest) |
| Design WT (BH-3) | 0.6 m bgl (Aug. highest) |

---

## Key Engineering References

- **IS 6403:1981** — Code of practice for determination of bearing capacity of shallow foundations
- **IS 2131:1981** — Method for standard penetration test for soils
- **[IS 2720 (Part 13):1986](https://law.resource.org/pub/in/bis/S03/is.2720.13.1986.pdf)** — Methods of test for soils: Direct shear test
- **[IS 2720 (Part 11):1993](https://law.resource.org/pub/in/bis/S03/is.2720.11.1993.pdf)** — Methods of test for soils: Determination of shear strength parameters of a specimen tested in unconsolidated undrained triaxial compression without the measurement of pore water pressure
- **IS 8009:1976** Part 1 — Code of practice for calculation of settlements of foundations
- **IS 1904:1986** — Code of practice for design and construction of foundations in soils: general requirements
- Schmertmann, J.H., Hartman, J.P. & Brown, P.R. (1978). *Improved strain influence factor diagrams.* JGED ASCE 104(8), 1131–1135.
- Terzaghi, K. (1943). *Theoretical Soil Mechanics.* Wiley.
- Das, B.M. (2016). *Principles of Foundation Engineering*, 8th ed. Cengage.

---

## AI Use Log
See Appendix A of the submitted report for the full AI interaction log and audit.

---

## License
For academic use only — IIT Mandi CE 402, November 2026.
