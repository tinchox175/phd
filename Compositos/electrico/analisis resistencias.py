from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# %% 1. Load & plot curves
files = [
    r"/home/martin/LBT/phd/Compositos/electrico/Archivos/171126/PSS buena 2W 60s relajacion _bias_0p0mA_pulso_0p003mA_bias_0p0mA_pulso_0p003mA.csv",
]

fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 7))

for file in files:
    df = pd.read_csv(file)
    df["t_s"] = df["Tiempo (min)"] * 60

    pulse = df[df["I bias (mA)"].isna()]
    relax = df[df["I bias (mA)"].notna()].dropna(subset=["Vbias 1 (V)"])

    label = Path(file).stem
    ax1.plot(pulse["t_s"], pulse["Vinst 1 (V)"], ".-", label=label)
    ax2.plot(pulse["t_s"], pulse["Rinst 1 (Ohm)"] / 1e6, ".-", label=label)
    if not relax.empty:
        ax3.plot(relax["t_s"] - relax["t_s"].iloc[0], relax["Vbias 1 (V)"], ".-", label=label)

ax1.set_ylabel("Vinst 1 (V)")
ax2.set_ylabel("Rinst 1 (MΩ)")
ax3.set_ylabel("Vbias 1 (V)")
ax3.set_xlabel("Time (s)")

for ax in (ax1, ax2, ax3):
    ax.grid(True, alpha=0.3)
ax1.legend(fontsize=8)
plt.tight_layout()
plt.show()

# %% 2. Fit any function via curve_fit
df = pd.read_csv(files[0])
df["t_s"] = df["Tiempo (min)"] * 60

relax = df[df["I bias (mA)"].notna()].dropna(subset=["Vbias 1 (V)"])

t = relax["t_s"].to_numpy()
t = t - t[0]
y = relax["Vbias 1 (V)"].to_numpy()
# t, y = t[t < 560], y[t < 560]  # uncomment to slice time

def model(t, y0, A, tau, beta):
    return y0 + A * np.exp(-(t / tau) ** beta)

p0 = [0.0, -2.3, 60.0, 0.7]
sigma = 0.01  # measurement uncertainty (float or array), or None

popt, pcov = curve_fit(model, t, y, p0=p0, sigma=sigma, absolute_sigma=(sigma is not None))
perr = np.sqrt(np.diag(pcov))

residuals = y - model(t, *popt)
err = 1.0 if sigma is None else sigma
chi2r = np.sum((residuals / err) ** 2) / (len(y) - len(popt))

print(f"chi2r = {chi2r:.4g}")
for val, std in zip(popt, perr):
    print(f"  {val:.4} ± {std:.3}")

t_line = np.linspace(t[0], t[-1], 400)
plt.figure(figsize=(7, 4))
plt.plot(t, y, ".", alpha=0.5, label="Data")
plt.plot(t_line, model(t_line, *popt), "r-", lw=2, label=f"Fit (chi2r = {chi2r:.3g})")
plt.xlabel("Δt (s)")
plt.ylabel("Vbias 1 (V)")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.title('y0 + A * np.exp(-(t/tau)**beta')
plt.show()

# %% 2. Fit any function via curve_fit
df = pd.read_csv(files[0])
df["t_s"] = df["Tiempo (min)"] * 60

pulse = df[df["I bias (mA)"].isna()]

t = pulse["t_s"].to_numpy()
t = t - t[0]
y = pulse["Rinst 1 (Ohm)"].to_numpy()/1e6
# t, y = t[t < 560], y[t < 560]  # uncomment to slice time

def model(t, y0, A, tau, beta):
    return y0 + A * np.exp(-(t/tau)**beta)

p0 = [1.0, -1, 6.52, 0.5]
sigma = 0.01  # measurement uncertainty (float or array), or None

popt, pcov = curve_fit(model, t, y, p0=p0, sigma=sigma, absolute_sigma=(sigma is not None), maxfev=10000)
perr = np.sqrt(np.diag(pcov))

for i in popt:
    print(f"{i:.5g}+-{perr[np.where(popt==i)][0]:.2g}")

residuals = y - model(t, *popt)
err = 1.0 if sigma is None else sigma
chi2r = np.sum((residuals / err) ** 2) / (len(y) - len(popt))


t_line = np.linspace(t[0], t[-1], 400)
plt.figure(figsize=(7, 4))
plt.plot(t, y, ".", alpha=0.5, label="Data")
plt.plot(t_line, model(t_line, *popt), "r-", lw=2, label=f"Fit (chi2r = {chi2r:.3g})")
plt.xlabel("Δt (s)")
plt.ylabel("Rinst 1 (MΩ)")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.title('y0 + A * np.exp(-(t/tau)**beta')
plt.show()