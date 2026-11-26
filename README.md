# CE 402 — Geotechnical Engineering Platform

**IIT Mandi · School of Civil and Environmental Engineering**

An interactive web platform for shallow foundation analysis and design of a **G+3 students' hostel** in Mandi, Himachal Pradesh (Seismic Zone V). Built in Python and Streamlit with modular, code-traceable geotechnical solvers in SI units (`kN`, `kPa`, `m`, `mm`).

> **Live Deployment (Streamlit Community Cloud):**  
https://geotech-platformgit-5hgqwskkbpyo8z2zykgfiq.streamlit.app/ 


---

## Architecture Overview (SOLID Module Map)

The codebase separates presentation/UI (`Home.py`, `pages/`) from pure, deterministic engineering solvers (`utils/`) and automated benchmark verification (`tests/`):

```text
GeoTech-Platform/
├── Home.py                             # Landing page, workflow guide & session initialization
├── pages/                              # Presentation Layer (Streamlit UI — SRP per module)
│   ├── 1_🗺️_Soil_Profile.py           # P1: Layered soil profile editor & borehole log plot
│   ├── 2_⚙️_Parameters.py             # P2: IS 2131 SPT corrections & Mohr-Coulomb / UU fit
│   ├── 3_🏗️_Bearing_Capacity.py       # P3: IS 6403 bearing capacity & footing sizing
│   ├── 4_📊_Stress_Increase.py        # P4: Boussinesq & 2:1 stress-bulb visualization
│   └── 5_📐_Settlement.py             # P5: Schmertmann + 1D consolidation & IS 1904 checks
├── utils/                              # Domain / Solver Layer (pure NumPy/math, Streamlit-free)
│   ├── constants.py                    # Shared DEFAULT_LAYER schema, IS 1498 symbols, state init
│   ├── spt_corrections.py              # IS 2131:1981 overburden (CN), dilatancy & LSQ fitting
│   ├── bearing_capacity.py             # IS 6403:1981 Nc/Nq/Nγ, shape/depth/inclination/W′, sizing
│   ├── stress_increase.py              # Boussinesq corner/centre/point superposition & 2:1 method
│   └── settlement.py                   # Schmertmann (1978) Iz, Terzaghi (1943) 1D consolidation & U(Tv)
├── tests/                              # Verification Layer
│   └── test_geotech_benchmarks.py      # Deterministic pytest benchmarks vs IS codes & textbooks
├── .streamlit/config.toml              # Theme & server configuration
├── requirements.txt                    # Pinned compatible dependencies
└── README.md                           # Project documentation & deployment guide
```

### SOLID Design Principles Applied
- **Single Responsibility (SRP):** Each module in `utils/` owns one geotechnical standard or analytical domain (`spt_corrections`, `bearing_capacity`, `stress_increase`, `settlement`), independent of Streamlit widgets.
- **Open/Closed (OCP):** Stress profiles (`boussinesq_centre`, `boussinesq_corner`, `2to1`) and bearing-capacity shape/failure modes dispatch cleanly through parameterised mappings without altering core solvers.
- **Interface Segregation & Dependency Inversion:** UI pages consume pure function interfaces accepting explicit lists/scalars (`layers`, `Df`, `B`, `L`, `wt_bgl`) matching the shared `DEFAULT_LAYER` dictionary contract in `utils/constants.py`.

---

## IS Code & Literature References

| Standard / Reference | Scope in Platform |
|---|---|
| **IS 1498:1970** | Soil classification symbols (`SM`, `SP`, `CI`, `GW`, `Fill`) |
| **IS 2131:1981** | SPT corrections — Annex B overburden $C_N$ (Peck et al., 1974), Cl. 4.6 dilatancy ($N' > 15$ below WT in `SM`/`SP`/`ML`) |
| **IS 6403:1981** | Shallow foundation bearing capacity — Table 1 ($N_c, N_q, N_\gamma$), Table 2 shape factors, Cl. 5.1.2.1 depth factors, Cl. 5.1.2.3 water-table factor $W'$, Cl. 5.1.3 local shear, Cl. 5.0.1 effective area, Cl. 6 $\text{FOS} = 3.0$ |
| **IS 8009 (Part 1):1976** | Settlement computation & stress distribution (`2:1` and Boussinesq) |
| **IS 1904:1986** | Permissible total settlement, differential settlement & angular distortion limits for RC framed buildings |
| **Schmertmann et al. (1978)** | Strain influence factor $I_z$ method for granular layers (*JGED ASCE* 104(GT8)); $E_s$ correlations via Bowles (1996) |
| **Terzaghi (1943) & Das (2016)** | 1D consolidation (NC, OC, OC$\to$NC; sublayers $\le 0.5\text{ m}$), time factor $T_v(U)$, Boussinesq corner $I_\sigma$ (incl. obtuse-angle $\pi + \arctan$ branch) |

---

## Local Installation & Running

### 1. Clone and create a virtual environment
```bash
git clone https://github.com/9Vaibhav8/GeoTech-Platform.git
cd GeoTech-Platform

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Streamlit application
```bash
streamlit run Home.py
```
The app opens locally at `http://localhost:8501`.

### 4. Run the benchmark verification suite
```bash
pytest -v
```

---

## Assignment Design Basis (CE 402 · Group 3)

| Parameter | Design Value |
|---|---|
| Group number $g$ / Load factor $\lambda$ | $g = 3$, $\lambda = 1 + g/100 = 1.03$ |
| Factored service column loads ($\lambda P$) | Corner: `669.5 kN` · Edge: `1030.0 kN` · Interior: `1493.5 kN` |
| Minimum founding depth $D_f$ | `1.5 m` bgl |
| Borehole zoning | BH-2 (grids 1–2), BH-1 (grids 3–5), BH-3 (grids 6–7) |
| Design groundwater levels (August high) | BH-1: `1.0 m` · BH-2: `1.7 m` · BH-3: `0.6 m` bgl |
| Bearing capacity FOS | `3.0` on net ultimate bearing capacity (IS 6403:1981) |

---

## Team Contribution Table

| Member | GitHub Handle | Primary Ownership & Modules |
|---|---|---|
| Vaibhav Pal | `@9Vaibhav8` / `@Ingenuity49_` | Architecture, `Home.py`, P1 Soil Profile, P2 Parameters, DevContainer & Streamlit deployment |
| Shubham Anand | `@Shubham2310D` | P3 Bearing Capacity (`utils/bearing_capacity.py`), P2/P5 initial solvers & LaTeX fixes |
| Sumit | `@Sumit` | P4 Stress Increase (`utils/stress_increase.py`, `4_📊_Stress_Increase.py`) |
| Satendar | `@GitMaster45-tech` | P5 Settlement (`utils/settlement.py`, `5_📐_Settlement.py`), IS 1904 grid checks, QA & Benchmarks |

---

## Academic Use & AI Audit
Submitted for **CE 402 Geotechnical Engineering (IIT Mandi, November 2026)**. See the project report Appendix for the verbatim AI interaction log and engineering audit.
