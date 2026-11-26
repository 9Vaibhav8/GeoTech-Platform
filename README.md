# CE 402 Geotechnical Engineering Platform

An academic Streamlit application for exploring geotechnical inputs and foundation analyses developed for the CE 402 hostel foundation assignment at IIT Mandi.

**Hosted app:** [Open the platform](https://geotech-platformgit-5hgqwskkbpyo8z2zykgfiq.streamlit.app/)

The application is organized as five modules. Soil profile inputs are held in Streamlit session state and used by the relevant analysis pages. Check each page's displayed assumptions and inputs before relying on a result; this project is an academic analysis aid, not a substitute for engineering review.

## Modules

| Page | Purpose | Main references shown in the app |
| --- | --- | --- |
| **P1 — Soil Profile** | Enter borehole details, water-table depths, soil layers, classifications, unit weights, and strength or laboratory parameters; view the soil profile. | IS 1498 |
| **P2 — Parameters** | Calculate SPT corrections, fit drained Mohr–Coulomb parameters from direct-shear data, and estimate undrained shear strength from UU test data. | IS 2131:1981; laboratory test data |
| **P3 — Bearing Capacity** | Estimate shallow-foundation bearing capacity, examine water-table effects, and size footings using the inputs on the page. | IS 6403:1981 |
| **P4 — Stress Increase** | Estimate vertical stress increase below loaded areas using Boussinesq rectangular-load and 2:1 methods, including superposition of loaded areas. | IS 8009:1976 (as referenced by the app) |
| **P5 — Settlement** | Estimate immediate and consolidation settlement, explore settlement over time, and compare results with selected permissible-settlement limits. | Schmertmann method; Terzaghi 1-D consolidation; IS 8009:1976; IS 1904:1986 |

The pages contain editable inputs and example defaults. Defaults are examples only: enter and verify the data appropriate to your case. Inputs on one analysis page should not be assumed to update every other page unless the page explicitly indicates that they are shared.

## Run locally

### Requirements

- Python 3.10 or newer
- `pip`

### Setup

Clone the repository and enter its directory:

```bash
git clone https://github.com/9Vaibhav8/GeoTech-Platform.git
cd GeoTech-Platform
```

Create and activate a virtual environment, then install dependencies:

```bash
# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS / Linux
python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Start the Streamlit app:

```bash
streamlit run Home.py
```

Streamlit will print the local URL, usually [http://localhost:8501](http://localhost:8501).

## Recommended workflow

1. **P1 — Soil Profile:** Review the example profile or enter the borehole and layer data for your analysis. Check layer depths, soil symbols, unit weights, strength parameters, and measured/design water-table depths.
2. **P2 — Parameters:** Enter or review SPT and laboratory data. Inspect the correction assumptions and apply fitted values to a layer only after checking that they are appropriate.
3. **P3 — Bearing Capacity:** Enter footing geometry, founding depth, loading, and design conditions. Review the intermediate values and water-table assumptions.
4. **P4 — Stress Increase:** Enter the loaded-area geometry, load or pressure, and evaluation depth. Use superposition when modeling multiple loaded areas.
5. **P5 — Settlement:** Enter or review the column loads, footing sizes, grid, drainage, compressibility, and time-rate inputs. Inspect the differential-settlement comparisons and selected code limits.

Use the displayed equations, assumptions, and cited references to check whether each method suits the problem and the supplied data.

## Repository layout

```text
GeoTech-Platform/
├── Home.py
├── pages/
│   ├── 1_🗺️_Soil_Profile.py
│   ├── 2_⚙️_Parameters.py
│   ├── 3_🏗️_Bearing_Capacity.py
│   ├── 4_📊_Stress_Increase.py
│   └── 5_📐_Settlement.py
├── utils/
│   ├── constants.py
│   ├── bearing_capacity.py
│   ├── spt_corrections.py
│   ├── stress_increase.py
│   └── settlement.py
├── requirements.txt
└── README.md
```

## Dependencies

Python package requirements are listed in [`requirements.txt`](requirements.txt). The app uses Streamlit for the interface, NumPy and SciPy for numerical work, Pandas for tabular inputs, Matplotlib for plots, and Plotly for interactive charts.

## References

- IS 1498 — *Classification and identification of soils for general engineering purposes*.
- IS 2131:1981 — *Method for standard penetration test for soils*.
- IS 6403:1981 — *Code of practice for determination of bearing capacity of shallow foundations*.
- IS 8009:1976, Part 1 — *Calculation of settlements of foundations*.
- IS 1904:1986 — *Code of practice for design and construction of foundations in soils: General requirements*.
- Schmertmann, J. H., Hartman, J. P., & Brown, P. R. (1978). “Improved strain influence factor diagrams.” *Journal of the Geotechnical Engineering Division*, 104(GT8), 1131–1135.
- Terzaghi, K. (1943). *Theoretical Soil Mechanics*. John Wiley & Sons.
- Das, B. M. (2016). *Principles of Foundation Engineering*, 8th ed. Cengage Learning.

## Academic context

Developed for IIT Mandi CE 402 coursework. See the submitted assignment report for the project-specific design brief and any required AI-use disclosure.
