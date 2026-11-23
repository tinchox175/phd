#%%
import pandas as pd
import matplotlib.pyplot as plt
%matplotlib qt
df = pd.read_csv('/home/martin/LBT/phd/Compositos/electrico/Archivos/171126/PSS buena 2W 60s no inversa_bias_0p0mA_pulso_0p003mA.csv')

df['Time_s'] = df['Tiempo (min)'] * 60.0

df_pulse = df[df['Vbias 1 (V)'].isna()]
df_relax = df[df['Vbias 1 (V)'].notna()]
t_cutoff = df_relax['Time_s'].iloc[0]

fig, (ax_r, ax_v) = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True, constrained_layout=True)

# Top: Rinst 1 vs Time
ax_r.plot(
    df['Time_s'],
    df['Rinst 1 (Ohm)'] / 1e6,
    'o-',
    color='#2ca02c',
    markersize=2.0,
    linewidth=1.1,
    alpha=0.85,
    label=r'$R_{\mathrm{inst},1}$'
)
ax_r.axvline(t_cutoff, color='0.35', linestyle='--', linewidth=1.1, alpha=0.8,
             label=f'End of pulse ($t = {t_cutoff:.2f}\\ \\mathrm{{s}}$)')
ax_r.set_ylabel(r'$R_{\mathrm{inst},1}$ ($\mathrm{M\Omega}$)')
ax_r.set_title(r'PSS 2W (60 s Pulse, No Reverse) — $R_{\mathrm{inst},1}$ and $V_{\mathrm{inst},1} \rightarrow V_{\mathrm{bias},1}$ vs. Time')
ax_r.grid(True, linestyle='--', alpha=0.35)
ax_r.legend(loc='lower right')

# Bottom: Vinst 1 (pulse) -> Vbias 1 (relaxation) vs Time
ax_v.plot(
    df_pulse['Time_s'],
    df_pulse['Vinst 1 (V)'],
    'o-',
    color='#1f77b4',
    markersize=2.0,
    linewidth=1.1,
    alpha=0.9,
    label=r'$V_{\mathrm{inst},1}$ (Pulse, $I_{\mathrm{pulse}} = 3\ \mu\mathrm{A}$)'
)
ax_v.plot(
    df_relax['Time_s'],
    df_relax['Vbias 1 (V)'],
    'o-',
    color='#ff7f0e',
    markersize=2.0,
    linewidth=1.1,
    alpha=0.9,
    label=r'$V_{\mathrm{bias},1}$ (Relaxation, $I_{\mathrm{bias}} = 0\ \mathrm{mA}$)'
)
ax_v.axvline(t_cutoff, color='0.35', linestyle='--', linewidth=1.1, alpha=0.8,
             label=f'Switch at $t = {t_cutoff:.2f}\\ \\mathrm{{s}}$')
ax_v.set_xlabel('Time (s)')
ax_v.set_ylabel('Voltage (V)')
ax_v.set_xlim(0, df['Time_s'].max())
ax_v.grid(True, linestyle='--', alpha=0.35)
ax_v.legend(loc='upper right')

plt.savefig('/home/martin/LBT/phd/Compositos/electrico/Archivos/171126/pss_60s_r_and_v.png', dpi=150)
plt.show()