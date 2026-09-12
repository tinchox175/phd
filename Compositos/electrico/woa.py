#%%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import os
import glob
import re

# Set universal font sizes
FONT_LABEL = 14
FONT_TITLE = 16
FONT_TICK = 12

def plot_bias_sweeps(directories):
    if len(directories) != 3:
        raise ValueError("Please provide exactly 3 directory paths.")
        
    fig = plt.figure(figsize=(22, 16))
    
    # 3 rows, 4 columns: [Nyquist, Bode Mag, Bode Phase, Colorbar]
    # width_ratios gives the colorbar a dedicated slim column with fixed separation
    gs = gridspec.GridSpec(3, 4, figure=fig, width_ratios=[1, 1, 1, 0.04], wspace=0.35, hspace=0.35)
    
    for row_idx, directory in enumerate(directories):
        dir_name = os.path.basename(os.path.normpath(directory))
        
        search_pattern = os.path.join(directory, '*.txt')
        file_list = glob.glob(search_pattern)
        
        sweep_data = []
        for filepath in file_list:
            match = re.search(r'Offset_([+-]?\d+(?:\.\d+)?)_mV', filepath)
            if match:
                v_dc = float(match.group(1))
                sweep_data.append({'voltage': v_dc, 'path': filepath})
                
        if not sweep_data:
            print(f"No valid files found in {directory}.")
            continue
            
        sweep_data = sorted(sweep_data, key=lambda x: x['voltage'])
        voltages = [item['voltage'] for item in sweep_data]
        
        cmap = cm.plasma
        norm = mcolors.Normalize(vmin=min(voltages), vmax=max(voltages))
        
        # Define subplot axes for this row
        ax_nyq = fig.add_subplot(gs[row_idx, 0])
        ax_mag = fig.add_subplot(gs[row_idx, 1])
        ax_phase = fig.add_subplot(gs[row_idx, 2])
        cax = fig.add_subplot(gs[row_idx, 3])  # Dedicated colorbar axis outside the plots
        
        for item in sweep_data:
            v_dc = item['voltage']
            filepath = item['path']
            color = cmap(norm(v_dc))
            
            data = pd.read_csv(filepath, skiprows=(1,3))
            freq = data['Frecuencia (Hz)']
            re_z = data['Mean A']
            im_z = data['Mean B']
            
            mag_z = np.sqrt(re_z**2 + im_z**2)
            phase_z = np.degrees(np.arctan2(im_z, re_z))
            
            # --- Nyquist ---
            ax_nyq.plot(re_z, -im_z, 'o-', color=color, mfc='none', markersize=5, linewidth=1.8, alpha=0.8)
            
            # --- Bode Mag ---
            ax_mag.plot(freq, re_z, 's-', color=color, markersize=4, linewidth=1.8, alpha=0.8)
            
            # --- Bode Phase ---
            ax_phase.plot(freq, im_z, '^-', color=color, markersize=4, linewidth=1.8, alpha=0.8)

        # Style Nyquist
        ax_nyq.set_title(f'[{dir_name}] Nyquist', fontsize=FONT_TITLE, fontweight='bold')
        ax_nyq.set_xlabel(r'Re(Z) [$\Omega$]', fontsize=FONT_LABEL)
        ax_nyq.set_ylabel(r'-Im(Z) [$\Omega$]', fontsize=FONT_LABEL)
        ax_nyq.tick_params(axis='both', labelsize=FONT_TICK)
        ax_nyq.grid(True, linestyle='--', alpha=0.5)
        ax_nyq.set_xlim(-26000, 10000)
        ax_nyq.set_ylim(-5000,34000)
        # ax_nyq.set_aspect('equal', adjustable='datalim')
        
        # Style Bode Mag
        ax_mag.set_title(f'[{dir_name}] Bode Mag', fontsize=FONT_TITLE, fontweight='bold')
        ax_mag.set_xlabel('Frequency [Hz]', fontsize=FONT_LABEL)
        ax_mag.set_ylabel(r'Re(Z) [$\Omega$]', fontsize=FONT_LABEL)
        ax_mag.set_xscale('log')
        # ax_mag.set_yscale('log')
        ax_mag.tick_params(axis='both', labelsize=FONT_TICK)
        ax_mag.grid(True, which='both', linestyle='--', alpha=0.5)
        
        # Style Bode Phase
        ax_phase.set_title(f'[{dir_name}] Bode Phase', fontsize=FONT_TITLE, fontweight='bold')
        ax_phase.set_xlabel('Frequency [Hz]', fontsize=FONT_LABEL)
        ax_phase.set_ylabel('Im(Z) [$\Omega$]', fontsize=FONT_LABEL)
        ax_phase.set_xscale('log')
        ax_phase.tick_params(axis='both', labelsize=FONT_TICK)
        ax_phase.grid(True, which='both', linestyle='--', alpha=0.5)

        # Draw Colorbar in its dedicated axis (cax)
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cax)
        cbar.set_label(r'$V_{\mathrm{DC}}$ Offset [mV]', fontsize=FONT_LABEL, fontweight='bold')
        cbar.ax.tick_params(labelsize=FONT_TICK)
    
    plt.show()

# --- Execution ---
if __name__ == "__main__":
    target_dirs = [
        r"/home/martin/LBT/phd/Compositos/electrico/Archivos/040926/EI 2w",
        r"/home/martin/LBT/phd/Compositos/electrico/Archivos/040926/EI 4w 1",
        r"/home/martin/LBT/phd/Compositos/electrico/Archivos/040926/EI 4w 2"
    ]
    plot_bias_sweeps(target_dirs)