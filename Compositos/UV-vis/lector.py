#%%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
import os
import matplotlib as mpl
mpl.rcParams.update({
    'font.size': 20,
    'axes.titlesize': 20,
    'axes.labelsize': 20,
    'xtick.labelsize': 20,
    'ytick.labelsize': 20,
    'legend.fontsize': 16
})

FOLDER_PATH = os.path.expanduser('~/LBT/phd/Compositos/UV-vis/todos/')

def load_and_clean(filename, cutoff_wl=250):
    """Loads a spectrum, masks saturation > 5.95, trims UV noise, sets index."""
    filepath = os.path.join(FOLDER_PATH, filename)
    df = pd.read_csv(filepath, skiprows=1)
    
    df = df[df['Abs.'] <= 5.95]
    df = df[df['Wavelength nm.'] >= cutoff_wl]
    df = df[df['Wavelength nm.'] <= 840]
    df.set_index('Wavelength nm.', inplace=True)
    
    return df['Abs.']

def get_blank_for_sample(filename, cutoff_wl=250):
    """Automatically loads the correct background based on solvent keywords."""
    fn_lower = filename.lower()
    if 'agua' in fn_lower:
        blank_name = 'blanco agua.txt'
    elif 'm-cresol' in fn_lower:
        blank_name = 'Blanco m-cresol.txt'
    elif 'nmp' in fn_lower:
        blank_name = 'blanco NMP.txt'
    else:
        raise ValueError(f"No se pudo determinar el solvente para: {filename}")
        
    return load_and_clean(blank_name, cutoff_wl=cutoff_wl)

def filter_files(catalog, include_any=None, exclude_any=None, exclude_ids=None):
    """
    Filters a catalog dictionary {id: filename}.
    Now includes 'exclude_ids' for quick removal by numeric ID.
    """
    filtered = catalog.copy()
    
    # 1. Quick drop by ID
    if exclude_ids:
        for eid in exclude_ids:
            filtered.pop(eid, None)
            
    # 2. Filter by required keywords
    if include_any:
        filtered = {
            k: v for k, v in filtered.items() 
            if any(inc.lower() in v.lower() for inc in include_any)
        }
        
    # 3. Filter by forbidden keywords
    if exclude_any:
        filtered = {
            k: v for k, v in filtered.items() 
            if not any(exc.lower() in v.lower() for exc in exclude_any)
        }
        
    return filtered

def plot_spectra(catalog, title="Espectros UV-Vis", cutoff_wl=250, use_filtered=True, solv='agua', stacker=False):
    """
    Processes and plots experimental and literature spectra.
    Files with 'paper' in the name bypass backgrounds and filtering, 
    and are styled distinctively (red, dashed).
    """
    if not catalog:
        print("No hay archivos para graficar con estos filtros.")
        return

    processed_data = []
    
    # --- PHASE 1: Unified Processing ---
    for file_id, fn in catalog.items():
        is_paper = 'paper' in fn.lower()
        
        # Everyone uses the exact same loading infrastructure
        data = load_and_clean(fn, cutoff_wl=cutoff_wl)
        
        if is_paper:
            # Literature curves don't need backgrounds or filtering
            final_series = data 
        else:
            # Experimental curves get background subtraction and filtering
            blank = get_blank_for_sample(fn, cutoff_wl=cutoff_wl)
            data = data - blank
            data.dropna(inplace=True)
            
            if use_filtered:
                data = pd.Series(savgol_filter(data, window_length=15, polyorder=3), index=data.index)
            
            final_series = data
            
        processed_data.append((file_id, fn, final_series, is_paper))
        
    # --- PHASE 2: Normalization to Last Peak and Plot ---
    from scipy.signal import find_peaks

    use_offset = stacker  
    offset_step = 0.8  # Increased slightly since primary peaks will now go higher than 1.0
    peak_prominence = 0.05
    peak_distance = 100     

    fig_height = 6 + (len(processed_data) * 1) if use_offset else 4
    if stacker == False:
        fig, ax = plt.subplots(figsize=(16, 8))
    else:
        fig, ax = plt.subplots(figsize=(8, 10))
    
    exp_count = sum(1 for _, _, _, is_paper in processed_data if not is_paper)
    exp_colors = plt.cm.viridis(np.linspace(0, 0.9, max(1, exp_count)))
    exp_idx = 0 
    
    paper_styles = ['--', ':', '-.'] 
    paper_idx = 0
    
    for idx, (file_id, fn, data, is_paper) in enumerate(processed_data):
        
        local_min = data.min()
        
        # 1. Temporary standard normalization just to find the peaks reliably
        temp_norm = (data - local_min) / (data.max() - local_min)
        peaks, _ = find_peaks(temp_norm, prominence=peak_prominence, distance=peak_distance)
        
        # 2. Identify the reference value (The Last Peak)
        if len(peaks) > 0:
            last_peak_idx = peaks[-1] # Grabs the last index in the peak array
            ref_max = data.iloc[last_peak_idx]
        else:
            ref_max = data.max() # Safe fallback if a curve is flat/featureless
            
        # 3. Final Normalization: Scales the curve so the LAST peak is exactly 1.0
        normalized_data = (data - local_min) / (ref_max - local_min)
        
        # Styling branch
        if is_paper:
            line_color = 'red'
            line_style = paper_styles[paper_idx % len(paper_styles)] 
            line_weight = 2.0
            paper_idx += 1
        else:
            line_color = exp_colors[exp_idx]
            line_style = '-'
            line_weight = 1.5
            exp_idx += 1
            
        current_offset = (idx * offset_step) if use_offset else 0
        plot_data = normalized_data + current_offset
        
        label_name = f"[{file_id}] {fn.replace('.txt', '').replace('.csv', '')}"
        ax.plot(data.index, plot_data, color=line_color, linestyle=line_style, 
                linewidth=line_weight, label=label_name)

        # --- VISUAL IDENTIFIER: Reuse the peaks we already found! ---
        for p in peaks:
            peak_x = data.index[p]
            peak_y = plot_data.iloc[p]
            
            ax.plot(peak_x, peak_y, marker='o', markersize=4, color=line_color, alpha=0.7)
            y_nudge = 15 + (15 * (idx % 3) if not use_offset else 0)
            
            ax.annotate(f'{peak_x:.0f}', 
                        xy=(peak_x, peak_y),
                        xytext=(0, y_nudge), 
                        textcoords='offset points',
                        ha='center', va='bottom',
                        fontsize=18, color=line_color, fontweight='bold',
                        arrowprops=dict(arrowstyle='-', color=line_color, alpha=0.5))

    # Formatting
    filter_status = "Filtrados" if use_filtered else "s/ Filtrar"
    offset_status = " (Apilados)" if use_offset else ""
    
    ax.set_title(f"{title} ({filter_status}){offset_status}")
    ax.set_xlabel(r'$\lambda$ (nm)')
    
    if use_offset:
        ax.set_yticks([]) 
        ax.set_ylabel('Absorbancia Normalizada al Último Pico (Offset)')
    else:
        ax.set_ylabel('Absorbancia Normalizada al Último Pico')
        
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.set_xlim(cutoff_wl, 850)
    
    # loc='upper center' anchors the top middle of the legend box
    # bbox_to_anchor=(0.5, -0.15) places it horizontally centered (0.5) and just below the x-axis (-0.15)
    # ncol=3 splits the labels into 3 columns so it stays compact
    if stacker == True:
        pass
    else:
        ax.legend(frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=3)
    plt.tight_layout()
    plt.show()

# ==========================================
# EXAMPLES OF FLEXIBILITY WITH IDs
# ==========================================
#%%
# 1. Base list of raw filenames
all_samples = [f for f in os.listdir(FOLDER_PATH) if f.endswith('.txt') and 'blanco' not in f.lower()]

# 2. Create the file catalog: {0: 'PANI_EB_1.txt', 1: 'PANI_ES_agua.txt', ...}
file_catalog = {i: filename for i, filename in enumerate(all_samples)}

filtered_catalog = filter_files(file_catalog, include_any=['pss'], #pss agua s/acetona
    exclude_any=['acetona','uzuncar', 'morarad'], exclude_ids=[14, 17, 18, 24, 5, 20, 19, 7])

# filtered_catalog = filter_files(file_catalog, include_any=['pss'], #pss todos
#     exclude_any=['uzuncar', 'morarad'], exclude_ids=[14, 18, 24])

filtered_catalog = filter_files(file_catalog, include_any=['m-cresol'], #nmp todos
    exclude_any=[], exclude_ids=[27, 3])

# # Plotting
plot_spectra(filtered_catalog, cutoff_wl=300, title="EB m-cresol", use_filtered=False, solv='m-cresol', stacker=True)

