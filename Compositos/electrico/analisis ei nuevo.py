import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.cm as cm

# 1. Load the data
file_path = '/home/martin/LBT/phd/Compositos/electrico/Archivos/090926/PSS_plasma_3W34_100mVac_T290_1709.csv'  # Replace with your actual file name
REF_FILE_PATH = '/home/martin/LBT/phd/Compositos/electrico/Archivos/Mediciones en temperatura/03-04 - 09/EI barrido umbral 3/PSS_plasma_Z1234_100mVac_T290.00K_2036.txt_Offset_0.00_mV.txt' # New file
MIN_FREQ = 300                    # Set your cutoff frequency here (Hz). 

# 1. Load the data
df = pd.read_csv(file_path)

# Drop any rows where the measurement failed or returned NaN
df = df.dropna(subset=['R_ch1 (Ohm)'])

# 2. Load the reference data (Plasma IS)
df_ref = pd.read_csv(REF_FILE_PATH)
df_ref = df_ref[df_ref['Frecuencia (Hz)'] >= MIN_FREQ]

# --- THE FILTER ---
# This single line drops all data points below your threshold for every curve
df = df[df['Freq (Hz)'] >= MIN_FREQ]

# 2. Identify all unique Vdc biases applied during the measurement
vdc_values = df['Vdc (V)'].unique()
print(f"Detected Vdc sweeps: {vdc_values}")

# Generate a colormap to clearly distinguish different Vdc curves
colors = cm.berlin(np.linspace(0, 1, len(vdc_values)))

# 3. Setup the canvas: 1 row, 3 columns
fig, (ax_nyq, ax_r, ax_x) = plt.subplots(1, 3, figsize=(16, 5))

# 4. Loop through each Vdc and plot automatically
for i, vdc in enumerate(vdc_values):
    # Isolate the data for this specific Vdc and ensure frequencies are ordered
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
        label_text = f'ΔZ ({vdc}V)'
        marker_style = '^'
    else:
        # Fallback if it's an old file without Matrix data
        r_plot = r1
        x_plot = x1
        label_text = f'CH1 ({vdc}V)'
        marker_style = 'o'

    # Plot Nyquist (-Reactance vs Resistance)
    ax_nyq.plot(r_plot, -x_plot, marker=marker_style, markersize=5, 
                linestyle='-', color=colors[i], label=label_text)
    
    # Plot Bode: Resistance (Log X, Linear Y)
    ax_r.semilogx(freq, r_plot, marker=marker_style, markersize=5, 
                  linestyle='-', color=colors[i], label=label_text)
    
    # Plot Bode: Reactance (Log X, Linear Y)
    ax_x.semilogx(freq, x_plot, marker=marker_style, markersize=5, 
                  linestyle='-', color=colors[i], label=label_text)

# 6. PLOT THE REFERENCE FILE ON TOP
freq_ref = df_ref['Frecuencia (Hz)']
r_ref = df_ref['Mean A'] # Real part
x_ref = df_ref['Mean B'] # Imaginary part
# Added zorder=10 to guarantee it draws visually on top of the plasma curves
ax_nyq.plot(r_ref, -x_ref, marker='s', markersize=6, linestyle='--', 
            color='black', label='4W', zorder=10)
ax_r.semilogx(freq_ref, r_ref, marker='s', markersize=6, linestyle='--', 
              color='black', label='4W', zorder=10)
ax_x.semilogx(freq_ref, x_ref, marker='s', markersize=6, linestyle='--', 
              color='black', label='4W', zorder=10)

# 5. Formatting Nyquist
ax_nyq.set_title('Nyquist Plot')
ax_nyq.set_xlabel("Z' (Real) [Ω]")
ax_nyq.set_ylabel("-Z'' (Imaginary) [Ω]")
ax_nyq.grid(True, alpha=0.4)
ax_nyq.set_aspect('equal', adjustable='datalim') # Forces true semicircles
ax_nyq.legend(fontsize='small')

# 6. Formatting Bode Resistance
ax_r.set_title('Bode: Resistance')
ax_r.set_xlabel("Frequency [Hz]")
ax_r.set_ylabel("R [Ω]")
ax_r.grid(True, alpha=0.4)

# 7. Formatting Bode Reactance
ax_x.set_title('Bode: Reactance')
ax_x.set_xlabel("Frequency [Hz]")
ax_x.set_ylabel("X [Ω]")
ax_x.grid(True, alpha=0.4)

plt.tight_layout()
plt.show()