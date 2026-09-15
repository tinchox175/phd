import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# 1. Load all CSV files in the folder
FOLDER_PATH = Path('/home/martin/LBT/phd/Compositos/electrico/tests/pruebas sistematizacion tongi/c2')
MIN_FREQ = 20  # Set your cutoff frequency here (Hz).
REF_FILE_PATH = None  # e.g. '/path/to/reference.csv' or set to None to disable reference overlay
FILE_MARKERS = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'X', 'h', 'H', 'P', '8']

csv_files = sorted(FOLDER_PATH.glob('*.csv'))
if not csv_files:
    raise FileNotFoundError(f'No CSV files found in: {FOLDER_PATH}')

# 2. Setup the canvas: 1 row, 3 columns
fig, (ax_nyq, ax_r, ax_x) = plt.subplots(1, 3, figsize=(20, 11))

# 3. Plot every CSV file in the folder
df_ref = None
if REF_FILE_PATH is not None:
    ref_path = Path(REF_FILE_PATH)
    if ref_path.exists():
        df_ref = pd.read_csv(ref_path)
        df_ref = df_ref[df_ref['Frecuencia (Hz)'] >= MIN_FREQ]

for file_index, csv_file in enumerate(csv_files):
    mk = FILE_MARKERS[file_index % len(FILE_MARKERS)]
    df = pd.read_csv(csv_file)
    df = df.dropna(subset=['R_ch1 (Ohm)'])
    df = df[df['Freq (Hz)'] >= MIN_FREQ]

    # 4. Identify all unique Vdc biases applied during the measurement
    vdc_values = df['Vdc (V)'].unique()
    print(f"{csv_file.name}: detected Vdc sweeps = {vdc_values}")

    # Generate a discrete palette with 20 unique colors (or more if needed)
    n_colors = max(20, len(vdc_values))
    colors = plt.get_cmap('tab20', n_colors)(np.arange(n_colors))

    # 5. Loop through each Vdc and plot automatically
    for i, vdc in enumerate(vdc_values):
        df_vdc = df[df['Vdc (V)'] == vdc].sort_values('Freq (Hz)')

        freq = df_vdc['Freq (Hz)']
        r1 = df_vdc['R_ch1 (Ohm)']
        x1 = df_vdc['X_ch1 (Ohm)']

        # Check if Channel 2 data exists (Matrix was used)
        if 'R_ch2 (Ohm)' in df_vdc.columns and not df_vdc['R_ch2 (Ohm)'].isna().all():
            r2 = df_vdc['R_ch2 (Ohm)']
            x2 = df_vdc['X_ch2 (Ohm)']

            # Calculate the pure sample segment (CH1 - CH2)
            r_plot = r1 - r2
            x_plot = x1 - x2
        else:
            # Fallback if it's an old file without Matrix data
            r_plot = r1
            x_plot = x1

        label_text = f'{csv_file.stem} | {vdc}V'

        # Plot Nyquist (-Reactance vs Resistance)
        ax_nyq.plot(r_plot, -x_plot, marker=mk, markersize=8,
                    linestyle='-', color=colors[i], label=label_text)

        # Plot Bode: Resistance (Log X, Linear Y)
        ax_r.semilogx(freq, r_plot, marker=mk, markersize=8,
                      linestyle='-', color=colors[i], label=label_text)

        # Plot Bode: Reactance (Log X, Linear Y)
        ax_x.semilogx(freq, x_plot, marker=mk, markersize=8,
                      linestyle='-', color=colors[i], label=label_text)

# Add fixed reference guides with highest z-order
for r_level in [10, 100, 1000, 10000, 100000, 1000000]:
    ax_r.axhline(r_level, color='gray', linestyle='--', linewidth=1.0,
                 alpha=0.7, zorder=1000)

for ax in (ax_r, ax_x):
    ax.axvline(50, color='black', linestyle=':', linewidth=1.5,
               alpha=0.8, zorder=1000)

# 6. Plot the reference file on top, if available
if df_ref is not None:
    freq_ref = df_ref['Frecuencia (Hz)']
    r_ref = df_ref['Mean A']  # Real part
    x_ref = df_ref['Mean B']  # Imaginary part

    ax_nyq.plot(r_ref, -x_ref, marker=mk, markersize=6, linestyle='--',
                color='black', label='Reference', zorder=10)
    ax_r.semilogx(freq_ref, r_ref, marker=mk, markersize=6, linestyle='--',
                  color='black', label='Reference', zorder=10)
    ax_x.semilogx(freq_ref, x_ref, marker=mk, markersize=6, linestyle='--',
                  color='black', label='Reference', zorder=10)

# 7. Formatting Nyquist
ax_nyq.set_title('Nyquist Plot')
ax_nyq.set_xlabel("Z' (Real) [Ω]")
ax_nyq.set_ylabel("-Z'' (Imaginary) [Ω]")
ax_nyq.grid(True, alpha=0.4)
ax_nyq.set_aspect('equal', adjustable='datalim')
plt.tight_layout()

ax_r.legend(fontsize='large', ncol=6, loc='lower center', bbox_to_anchor=(0.5, -0.27))

# 8. Formatting Bode Resistance
ax_r.set_title('Bode: Resistance')
ax_r.set_xlabel('Frequency [Hz]')
ax_r.set_ylabel('R [Ω]')
ax_r.set_yscale('log')
ax_r.grid(True, alpha=0.4)

# 9. Formatting Bode Reactance
ax_x.set_title('Bode: Reactance')
ax_x.set_xlabel('Frequency [Hz]')
ax_x.set_ylabel('X [Ω]')
ax_x.set_yscale('symlog')
ax_x.grid(True, alpha=0.4)

plt.show()