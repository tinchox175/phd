#%%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
%matplotlib inline
dirs = [
    r"E:\trabajo\phd\phd\Compositos\electrico\Archivos\Mediciones en temperatura\03-04 - 09\EI barrido umbral",
    r"E:\trabajo\phd\phd\Compositos\electrico\Archivos\Mediciones en temperatura\03-04 - 09\EI barrido umbral 2malo",
    r"E:\trabajo\phd\phd\Compositos\electrico\Archivos\Mediciones en temperatura\03-04 - 09\EI barrido umbral 3"
]

for d in dirs:
    print("Files in folder:", os.listdir(d))

def plot_impedance_data(dirs):
    import re
    import matplotlib.colors as mcolors

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    for idx, dir_path in enumerate(dirs):
        files_to_plot = []
        for filename in os.listdir(dir_path):
            if filename.endswith(".txt"):
                if ('100mVac') in filename:
                    full_path = os.path.join(dir_path, filename)
                    files_to_plot.append(full_path)

        parsed_files = []
        for filename in files_to_plot:
            match = re.search(r'(-?\d+(?:\.\d+)?)\s*_?mV(?![aA])', os.path.basename(filename))
            offset = float(match.group(1)) if match else 0.0
            parsed_files.append((offset, filename))
        
        parsed_files.sort(key=lambda x: x[0])
        offsets = [p[0] for p in parsed_files]
        
        if offsets:
            min_off, max_off = min(offsets), max(offsets)
            norm = mcolors.Normalize(vmin=min_off, vmax=max_off) if min_off != max_off else mcolors.Normalize(vmin=min_off-1, vmax=min_off+1)
        else:
            norm = mcolors.Normalize(0, 1)
            
        cmap = plt.get_cmap('viridis')

        ax1 = axes[idx, 0]
        ax2 = axes[idx, 1]
        ax3 = axes[idx, 2]
        
        for offset, filename in parsed_files:
            print(filename)
            data = pd.read_csv(filename, skiprows=range(1, 2), sep=',')
            print(data.head())
            
            freq = data['Frecuencia (Hz)']
            re_z = data['Mean A']
            im_z = data['Mean B']
            re_err = data['SD A']
            im_err = data['SD B']
            
            mag_z = np.sqrt(re_z**2 + im_z**2)
            phase_z = np.degrees(np.arctan2(im_z, re_z))
            
            label = f"{offset} mV"
            color = cmap(norm(offset))
            
            ax1.errorbar(re_z, -im_z, xerr=re_err, yerr=im_err, 
                         fmt='o', mfc='none', markersize=5, 
                         capsize=2, label=label, color=color)
            
            ax2.errorbar(freq, re_z, yerr=re_err,
                          fmt='s-', markersize=4, label=label, color=color)
            
            ax3.errorbar(freq, im_z, yerr=im_err,
                          fmt='^-', markersize=4, label=label, color=color)
        
        ax1.set_title(f'Nyquist Plot (Dir {idx+1})', fontweight='bold')
        ax1.set_xlabel('Re(Z) [Ω]')
        ax1.set_ylabel('-Im(Z) [Ω]')
        ax1.grid(True, linestyle='--', alpha=0.6)
        ax1.set_aspect('equal', adjustable='datalim') 
        
        ax2.set_title(f'Bode Plot: Re (Dir {idx+1})', fontweight='bold')
        ax2.set_xlabel('Frequency [Hz]')
        ax2.set_ylabel('R [Ω]')
        ax2.set_xscale('log')
        ax2.set_yscale('symlog')
        ax2.grid(True, which='both', linestyle='--', alpha=0.6)
        
        ax3.set_title(f'Bode Plot: Img (Dir {idx+1})', fontweight='bold')
        ax3.set_xlabel('Frequency [Hz]')
        ax3.set_ylabel('X [Ω]')
        ax3.set_xscale('log')
        ax3.grid(True, which='both', linestyle='--', alpha=0.6)
        
        handles, labels = ax1.get_legend_handles_labels()
        ax1.legend(handles, labels, loc='best', ncol=1, fontsize='small')

    plt.tight_layout()
    plt.show()

if dirs:
    plot_impedance_data(dirs)