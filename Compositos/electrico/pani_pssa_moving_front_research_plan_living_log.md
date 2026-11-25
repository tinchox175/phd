# PANI:PSSa Lateral Redox Fronts — Research Plan & Living Log

> **Purpose:** Single source of truth for physical hypotheses, literature context, experimental constraints, and analysis milestones. Designed to be updated iteratively and loaded directly into coding agents (e.g., Antigravity) so analysis scripts stay tightly scoped to physical questions.

---

## 1. System Identity & Constraints

* **Material:** Single-layer **PANI:PSSa** (polyaniline doped with poly(4-styrenesulfonic acid)) — an internal polyelectrolyte complex acting as a solid-state **Organic Mixed Ionic–Electronic Conductor (OMIEC)**.
* **Charge Carriers:**
  * **Electronic:** Holes / polarons along the PANI backbone (high conductivity in emeraldine salt, low conductivity in over-oxidized pernigraniline and reduced leucoemeraldine).
  * **Ionic:** Immobile sulfonate anions ($-\text{SO}_3^-$) covalently bound to the PSS backbone; **mobile protons ($\text{H}^+$)** migrating through hydrated excess acid domains ($-\text{SO}_3\text{H}$ / absorbed ambient $\text{H}_2\text{O}$).
* **Device Geometry:** Planar, two-terminal micro-contact configuration probed on an optical probe station (no external liquid electrolyte bath, no separate solid-electrolyte overlayer).
* **Current Dataset & Calibration:**
  * Optical microscopy videos at $1\,\mu\text{m/px}$ spatial scale (e.g., `3uAx30s relajacion.mkv`, `3uAx60s relajacion.mkv`, with active pulse cutoff around $t \approx 41.55\,\text{s}$ and open-circuit relaxation up to $660\,\text{s}$).
  * Driving mode: Galvanostatic (constant current, e.g., $I = 3\,\mu\text{A}$).
* **Hard Working Constraints (Current Phase):**
  * **No new experiments** at the moment; goal is deep physical insight from existing ambient recordings.
  * **No humidity chamber** (combining micro-scale probe-station optics with humidity control is currently impractical). Ambient relative humidity is treated as fixed over each $\sim 10\,\text{min}$ recording.

---

## 2. Physical Picture: Why Two-Terminal PANI:PSSa Is Distinct

In most moving-front studies, the polymer is interfaced with an external liquid or solid polymer electrolyte. Your film differs in three fundamental ways:

1. **Closed Internal Proton Budget:** With no external ion reservoir, total mobile $\text{H}^+$ is conserved inside the strip. Oxidation at the anode (green emeraldine salt $\to$ purple/blue pernigraniline) **releases $\text{H}^+$**, which must drift laterally through the hydrated PSSa matrix toward the cathode to maintain electroneutrality.
2. **Co-Linear Mixed Transport & Current Partitioning:** Both $\text{H}^+$ and electronic carriers travel laterally across the same inter-electrode gap. Unlike a bilayer with an electronically insulating electrolyte overlayer, electronic current can leak directly through the converted zone in parallel with Faradaic redox conversion.
3. **Conductor-to-Insulator Switching Behind the Front:** Converting conductive green emeraldine salt into less-conductive purple pernigraniline increases local electronic resistance behind the moving boundary, dynamically redistributing the internal electric field $E(x, t)$ as the front advances.

---

## 3. Literature Landscape & Genuine Research Gaps

### Key Reference Lineage

| Work | System & Geometry | Core Mechanism / Contribution |
| :--- | :--- | :--- |
| **Aoki, Tezuka et al.** (*J. Electroanal. Chem.* 1992–1995) | PANI / PPy in liquid electrolyte | First quantitative optical tracking of lateral "conducting-zone propagation" governed by insulator–conductor percolation. |
| **Johansson, Persson & Inganäs** (*J. Electrochem. Soc.* 2004) | Polythiophenes, lateral electrochemistry in electrolyte | Modeled moving redox fronts as electrochemical **shock waves** triggered by sharp conductivity transitions. |
| **Wang, Shapiro & Smela** (*J. Phys. Chem. C* 2009) | Polypyrrole in liquid electrolyte | Continuum drift–diffusion model proving pure diffusion cannot produce sharp fronts; electric-field drift is required. |
| **Stavrinidou, Malliaras et al.** (*J. Appl. Phys.* 2013; *AIP Adv.* 2014; *J. Mater. Chem. C* 2016) | PEDOT:PSS with aqueous electrolyte reservoir (1D SU-8 ion barrier) | Series-resistor drift model under constant voltage yielding $\ell(t) = \sqrt{2\mu_{\text{ion}} V t}$, directly linking optical front length to electrical impedance $R(t) \propto \sqrt{t}$. |
| **Keene, Rao, Malliaras et al.** (*Nature Materials* 2023) | PEDOT:PSS & polythiophenes, operando optical microscopy in aqueous electrolyte | Showed fronts can be **hole-limited** rather than ion-limited depending on microstructural disorder; used $\partial (\Delta T)/\partial t$ maps to locate where ionic and electronic currents converge. |
| **Kazaryan, Godovsky, Erokhin et al.** (*Mater. Today Commun.* 2023) | PANI + separate liquid/solid polymer electrolyte on Au electrodes | Framed lateral PANI redox fronts as state variables for multibit ReRAM and spiking/rate-based neuromorphic circuits. |
| **Recent PANI:PSS Studies** (*Langmuir* 2024; *RSC Adv.* 2025; *Mater. Horiz.* 2026) | PANI:PSS thin films & composites | Mapped core–shell PSS/PANI dopant heterogeneity and protonation-controlled memristive switching, mostly via bulk electrical or static AFM/EFM probes rather than operando moving-front microscopy. |

### Four Literature Gaps Accessible With Your Existing Ambient Data

1. **Gap 1 — Electrolyte-Free, Solid-State Two-Terminal Moving Fronts in PANI:PSSa:**
   Almost all quantitative moving-front physics (Aoki, Smela, Stavrinidou, Keene) relies on an external **liquid electrolyte reservoir**, while neuromorphic PANI fronts (Kazaryan/Erokhin) rely on an **overlaid polymer electrolyte**. Quantitative operando optical transport analysis of a *self-contained, single-layer PANI:PSSa film in ambient air* is largely absent.
2. **Gap 2 — Galvanostatic (Constant-$I$) Front Dynamics & Current Partitioning:**
   Stavrinidou's $\sqrt{2\mu V t}$ law assumes constant voltage and negligible electronic leakage across the switched region. Under constant current ($I = 3\,\mu\text{A}$), an ideal 1D Faradaic front should move at constant speed ($v = \text{const}$). Measuring how both the front position $x_f(t)$ and integrated optical conversion $M(t)$ deviate from linearity directly quantifies **Faradaic efficiency vs. electronic leakage** in real time.
3. **Gap 3 — Competition Between Front Advance and Plateau Deepening:**
   Standard moving-front models assume a binary step (unconverted vs. fully converted). Your preliminary data already show the color plateau behind the front (`s_left`) deepening continuously for $\sim 20\,\text{s}$ *while* the front moves, coupled to a simultaneous change in front velocity — suggesting finite local redox kinetics or mixed electronic/ionic limitation (analogous to Keene et al. 2023).
4. **Gap 4 — Open-Circuit Relaxation Mode (Volatile vs. Non-Volatile Retention):**
   Most PANI memristor papers report bulk resistance decay $R(t)$ without knowing *spatially* how the memory state erases. Your $660\,\text{s}$ relaxation tail can directly distinguish **lateral proton back-diffusion** (front retreats toward the anode; retention scales as $L^2 / D_{\text{H}^+}$) from **homogeneous bulk fading** (whole converted region fades in place with a position-independent time constant $\tau$).

---

## 4. Baseline Audit: What Current Data (`3uAx60s relajacion.mkv`) Already Shows

From the initial 4-panel CIELAB $a^*$ `erf`-fit diagnostic on the active pulse ($t \in [6.5, 41.0]\,\text{s}$):

* **Pure Fickian diffusion is ruled out:** The front advances $\Delta x_f \approx 320\,\mu\text{m}$ (from $150\,\mu\text{m}$ to $470\,\mu\text{m}$) over $34.5\,\text{s}$, while the front half-width remains narrow ($w \approx 15\text{--}45\,\mu\text{m} \ll x_f$). The broadening scale $\frac{1}{2}\Delta(w^2)/\Delta t \approx 30\,\mu\text{m}^2/\text{s}$ ($3 \times 10^{-7}\,\text{cm}^2/\text{s}$) is roughly $50\times$ smaller than the propagation scale $\Delta x^2 / (2\Delta t) \approx 1500\,\mu\text{m}^2/\text{s}$. This is a **drift-dominated (electric-field-driven) wave** with secondary diffusive broadening.
* **Two velocity regimes synchronized with plateau saturation:**
  * *Early regime ($6.5\text{--}18\,\text{s}$):* Faster front ($v \approx 13.6\,\mu\text{m/s}$) while the converted plateau `s_left` rises rapidly from $-17.5$ toward $-5$.
  * *Late regime ($20\text{--}41\,\text{s}$):* Once `s_left` saturates near $-2.5$, $x_f(t)$ becomes nearly **linear** ($v \approx 7.2\,\mu\text{m/s}$) — consistent with steady galvanostatic Faradaic propagation (or reduced effective ionic current fraction).
* **Why free power-law fitting failed ($n \approx 0.1$, unphysical $x_0$):** Fitting $x_0 + k t^n$ across a two-regime curve (that already starts at $x_f = 150\,\mu\text{m}$ at $t = 6.5\,\text{s}$) forces $n \to 0$ to mimic rapid early bending (e.g., 2D radial spreading near a micro-contact or induction transient) followed by a shallower slope.
* **Static film morphology artifact:** Fixed spatial peaks/valleys appear at identical positions ($x \approx 120, 200, 300, 500\,\mu\text{m}$) across all timestamps because `subtract_t0 = False`. As the front sweeps past these static features, numerical derivatives ($\dot{x}$) and $w^2(t)$ oscillate artificially. **Fix:** Always analyze $\Delta a^*(x, t) = a^*(x, t) - a^*(x, 0)$ (and/or normalize by local optical contrast).

---

## 5. Core Research Questions & Testable Hypotheses (Existing Data Only)

### RQ1 — Write Phase: What Governs Front Propagation Under Constant Current?
* **H1a (2D-to-1D Geometric Spreading):** Near micro-contacts, current spreads radially in 2D first ($\text{area} \propto I t \implies r \propto \sqrt{t}$) before transitioning to quasi-1D channel propagation ($x_f \propto t$).
* **H1b (Dynamic Current Partitioning):** Total injected current $I = I_{\text{ionic}}(t) + I_{\text{electronic}}(t)$ shifts from predominantly Faradaic redox conversion early on to partial electronic leakage once `s_left` saturates.
* **Decisive Tests on Existing Data:**
  1. Inspect 2D difference frames $\Delta a^*(x, y, t)$ at $t = 2, 5, 10, 20, 40\,\text{s}$ to determine whether the front is a flat 1D wall, a circular 2D arc, or filamentary fingers.
  2. Compute spatially integrated optical conversion $M(t) = \int \Delta a^*(x, t)\,dx$ (or 2D integral $\iint \Delta a^*\,dx\,dy$) vs. injected charge $Q(t) = I t$. Linear $M(t)$ proves constant Faradaic efficiency even if $x_f(t)$ bends; sub-linear $M(t)$ directly quantifies leakage onset.
  3. Plot the time-derivative map $\partial(\Delta a^*)/\partial t$ (Keene et al. 2023 method) to visualize the exact spatial zone where ionic and electronic currents converge at each instant.

### RQ2 — Relaxation Phase ($t > 41.55\,\text{s}$): How Does the Converted State Erase?
* **H2a (Lateral Proton Back-Diffusion):** Trapped protons diffuse back laterally against their concentration gradient; the purple/green boundary retreats backward toward the anode, and regions farthest from the anode recover first.
* **H2b (Homogeneous Bulk / Ambient Equilibration):** The entire converted zone fades in place uniformly (e.g., via local chemical relaxation or vertical equilibration with ambient $\text{H}_2\text{O}$/$\text{O}_2$), with a position-independent decay constant $\tau$.
* **Decisive Tests on Existing Data:**
  1. Inspect full $660\,\text{s}$ background-subtracted kymograph $\Delta a^*(x, t)$ and 2D relaxation snapshots ($t = 45, 80, 150, 300, 600\,\text{s}$).
  2. Extract normalized decay traces $\Delta a^*(x_k, t) / \Delta a^*(x_k, t_{\text{off}})$ at fixed positions ($x_k = 100, 250, 400\,\mu\text{m}$). Overlap $\implies$ **H2b**; staggered recovery from far edge inward $\implies$ **H2a**.
  3. Compare total integrated state $M(t)$ decay functional form (single exponential vs. stretched exponential $\exp[-(t/\tau)^\beta]$ vs. $t^{-1/2}$ diffusive tail).

### RQ3 — Opto-Electrical Coupling *(Pending Synchronized $V(t)$ Data)*
* **H3a (Moving-Boundary Series Resistor):** $R(t) = V(t)/I$ scales directly with converted length $x_f(t)$ (analogous to Stavrinidou 2013/2014).
* **H3b (Local Oxidation Depth / Interface Dominated):** $R(t)$ tracks `s_left(t)` or jumps before $x_f(t)$ moves significantly, indicating contact-barrier or local conductivity-percolation control.
* **Decisive Test:** Plot $V(t)$ (and $R(t)$) directly against $x_f(t)$, `s_left(t)`, and $M(t)$ on the same time axis.

### RQ4 — Redox Pathway Symmetry in $(a^*, b^*)$ Space
* **Question:** Does open-circuit relaxation simply reverse the exact same optical/redox trajectory taken during the current pulse, or is there path hysteresis (e.g., trapping in an intermediate state or asymmetric green $\leftrightarrow$ purple $\leftrightarrow$ yellow transitions near the opposite contact)?
* **Decisive Test:** Track the mean $(a^*(t), b^*(t))$ trajectory of representative patches near the anode, channel center, and cathode during pulse vs. relaxation.

---

## 6. Clean Analysis Roadmap (Zero New Experiments)

To keep the codebase lean and modular (ideal for Antigravity), split analysis into **two decoupled layers**:

1. **Layer 1 — Extractor (`extract_kymo.py`, ~50 lines):** Reads video once via `ffmpeg`, saves `kymo_L`, `kymo_a`, `kymo_b`, `x_um`, `t_s`, `fps`, and ROI metadata into a compressed `.npz` cache file per video. No plotting or fitting inside the extractor.
2. **Layer 2 — Focused Physics Audits (one short script/notebook per question):**
   - [ ] **Step 1 — Geometry & Artifact Audit:** Plot 2D difference frames $\Delta a^*(x, y, t)$ (pulse + relaxation) to verify 1D vs. 2D front shape, check what happens at the *opposite* contact, and confirm whether `subtract_t0 = True` removes the static bumps in $w(t)$ and $\dot{x}$.
   - [ ] **Step 2 — Faradaic Integral Test (RQ1):** Plot $M(t) = \int \Delta a^*\,dx$, $x_f(t)$, `s_left(t)`, and $\partial(\Delta a^*)/\partial t$ side by side for `3uAx60s` and `3uAx30s` (checking reproducibility across pulse durations).
   - [ ] **Step 3 — Relaxation Mode Audit (RQ2):** Analyze the $t = 41.55\text{--}660\,\text{s}$ tail via normalized fixed-position decay traces $\Delta a^*(x_k, t)$ and $M(t)$ relaxation fits.
   - [ ] **Step 4 — Color-Plane & Electrical Coupling (RQ3 & RQ4):** Plot $(a^*, b^*)$ hysteresis loops and overlay synchronized $V(t)$ data if recorded for these runs.

---

## 7. Running Log & Open Items

### Dataset Inventory
* [x] `3uAx30s relajacion.mkv` — recorded, initial crop tested.
* [x] `3uAx60s relajacion.mkv` — $660\,\text{s}$ extracted; pulse ends at $t \approx 41.55\,\text{s}$; active-pulse `erf` diagnostic completed.
* [ ] *Add remaining existing videos (currents, pulse lengths, contact spacings) here.*
* [ ] *Confirm which videos have matching $V(t)$ electrical log files.*

### Open Questions to Confirm Before Step 1
1. **Contact geometry:** Are the micro-contacts parallel metal lines or probe tips / pads (1D vs. 2D field)?
2. **Opposite contact behavior:** Does any complementary color change (e.g., yellow leucoemeraldine reduction) appear at the cathode during the pulse?
3. **Electrical logs:** Do synchronized $V(t)$ traces exist for the `3uAx30s` and `3uAx60s` videos?