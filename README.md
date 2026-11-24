# CE 402 — Geotechnical Engineering Platform
**IIT Mandi · School of Civil and Environmental Engineering**

A web-based geotechnical engineering platform for foundation design of a G+3 student hostel in Mandi, Himachal Pradesh (Seismic Zone V).

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-name.streamlit.app)

---

## Modules

| Module | Description | IS Code |
|--------|-------------|---------|
| **P1** Soil Profile | Enter layered soil profile, draw log | IS 1498 |
| **P2** Parameter Tools | IS 2131 SPT corrections, Mohr-Coulomb fit, UU triaxial cu | IS 2131:1981 |
| **P3** Bearing Capacity | Net ultimate & safe bearing capacity, footing sizing | IS 6403:1981 |
| **P4** Stress Increase | Boussinesq rectangular load, 2:1 method, superposition | IS 8009:1976 |
| **P5** Settlement | Schmertmann immediate + 1D consolidation, time-settlement, IS 1904 check | IS 1904:1986, IS 8009:1976 |

---

## How to Run Locally

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/geotech-platform.git
cd geotech-platform
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
geotech-platform/
├── Home.py                          # Landing page & navigation
├── pages/
│   ├── 1_🗺️_Soil_Profile.py        # P1 — Soil profile input & visualisation
│   ├── 2_⚙️_Parameters.py          # P2 — SPT corrections & shear parameter fit
│   ├── 3_🏗️_Bearing_Capacity.py    # P3 — IS 6403:1981 bearing capacity
│   ├── 4_📊_Stress_Increase.py     # P4 — Boussinesq / 2:1 stress increase
│   └── 5_📐_Settlement.py          # P5 — Schmertmann + 1D consolidation
├── utils/
│   ├── constants.py                 # Shared session state & defaults
│   ├── bearing_capacity.py          # IS 6403:1981 implementation
│   ├── spt_corrections.py           # IS 2131:1981 implementation
│   ├── stress_increase.py           # Boussinesq rectangular load
│   └── settlement.py                # Schmertmann (1978) + Terzaghi (1943)
├── requirements.txt
├── .streamlit/config.toml           # Theme & server config
└── README.md
```

---

## Deployment to Streamlit Cloud

1. Push this repository to GitHub (make sure it is **public** or you have Streamlit Cloud access to private repos)
2. Go to **[share.streamlit.io](https://share.streamlit.io)** → "New app"
3. Connect your GitHub account and select:
   - **Repository:** `<your-username>/geotech-platform`
   - **Branch:** `main`
   - **Main file:** `Home.py`
4. Click **Deploy** — the app gets a permanent URL like `https://geotech-platform.streamlit.app`

> Every `git push` to `main` triggers an automatic redeploy.

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
