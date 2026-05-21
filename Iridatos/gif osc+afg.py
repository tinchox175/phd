import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.collections import LineCollection 
import matplotlib.animation as animation
from scipy.signal import savgol_filter

# --- PLOTTING TOGGLES ---
IV_PLOT_MODE = 'RAW'  # Options: 'RAW', 'FILTERED', 'BOTH'
GENERATE_GIF = False    # Set to False if you just want the static dashboard

def plot_dashboard(df, freq, amp, shape="Unknown", cycles="Unknown"):
    """Generates the static multi-pane dashboard."""
    fig = plt.figure(figsize=(15, 10)) 
    gs = gridspec.GridSpec(3, 2, width_ratios=[1, 1], height_ratios=[1, 1, 1.2])
    
    time_ms = df['Time_s'] * 1e3 
    
    # --- Row 1: Drive Traces ---
    ax_drive = fig.add_subplot(gs[0, 0])
    ax_drive.plot(time_ms, df['CH1_V_Supply_Raw'], label='CH1: Supply (V)', color='C0')
    ax_drive.plot(time_ms, df['CH2_V_Resistor_Raw'], label='CH2: Across 1kΩ (V)', color='C1')
    ax_drive.set_ylabel('Amplitude (V)', fontweight='bold')
    ax_drive.set_title(f'Drive Signals ({freq}Hz, {amp}V, {shape}, {cycles} Cycles)', fontweight='bold')
    ax_drive.grid(True, linestyle='--', alpha=0.6)
    
    # --- Row 2: Sense Traces ---
    ax_sense = fig.add_subplot(gs[1, 0], sharex=ax_drive)
    ax_sense.plot(time_ms, df['CH3_V_SenseP_Raw'] * 1e3, label='CH3: Sense+ (mV)', color='C2')
    ax_sense.plot(time_ms, df['CH4_V_SenseN_Raw'] * 1e3, label='CH4: Sense- (mV)', color='C3')
    ax_sense.set_ylabel('Amplitude (mV)', fontweight='bold')
    ax_sense.set_title('4-Wire Sense Contacts', fontweight='bold')
    ax_sense.grid(True, linestyle='--', alpha=0.6)
    
    # --- Row 3: All 4 Channels Overlay ---
    ax_all_v = fig.add_subplot(gs[2, 0], sharex=ax_drive)
    ax_all_v.plot(time_ms, df['CH1_V_Supply_Raw'], label='CH1 (V)', color='C0', alpha=0.8)
    ax_all_v.plot(time_ms, df['CH2_V_Resistor_Raw'], label='CH2 (V)', color='C1', alpha=0.8)
    ax_all_v.set_xlabel('Time (ms)', fontweight='bold')
    ax_all_v.set_ylabel('Drive (V)', fontweight='bold')
    
    ax_all_mv = ax_all_v.twinx()
    ax_all_mv.plot(time_ms, df['CH3_V_SenseP_Raw'] * 1e3, label='CH3 (mV)', color='C2', linestyle='--')
    ax_all_mv.plot(time_ms, df['CH4_V_SenseN_Raw'] * 1e3, label='CH4 (mV)', color='C3', linestyle='--')
    ax_all_mv.set_ylabel('Sense (mV)', fontweight='bold')
    
    ax_all_v.set_title('All Channels Overlay', fontweight='bold')
    ax_all_v.grid(True, linestyle='--', alpha=0.6)
    
    lines_1, labels_1 = ax_all_v.get_legend_handles_labels()
    lines_2, labels_2 = ax_all_mv.get_legend_handles_labels()
    ax_all_v.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper right', fontsize='small', ncol=2)
    
    # --- Right Side: I-V Curve ---
    ax_iv = fig.add_subplot(gs[:, 1]) 
    
    if IV_PLOT_MODE in ['RAW', 'BOTH']:
        v_data_raw = df['V_Sample_V_Raw'] * 1e3
        i_data_raw = df['I_Sample_A_Raw'] * 1e6
        points_raw = np.array([v_data_raw, i_data_raw]).T.reshape(-1, 1, 2)
        segments_raw = np.concatenate([points_raw[:-1], points_raw[1:]], axis=1)
        
        if IV_PLOT_MODE == 'BOTH':
            lc_raw = LineCollection(segments_raw, colors='grey', alpha=0.25, linewidth=1)
            ax_iv.add_collection(lc_raw)
        else:
            lc_raw = LineCollection(segments_raw, cmap='plasma', alpha=0.9, linewidth=2)
            lc_raw.set_array(time_ms[:-1]) 
            ax_iv.add_collection(lc_raw)
            cbar = fig.colorbar(lc_raw, ax=ax_iv, pad=0.02)
            cbar.set_label('Time (ms)', fontweight='bold')

    if IV_PLOT_MODE in ['FILTERED', 'BOTH']:
        v_data_filt = df['V_Sample_V_Filt'] * 1e3
        i_data_filt = df['I_Sample_A_Filt'] * 1e6
        points_filt = np.array([v_data_filt, i_data_filt]).T.reshape(-1, 1, 2)
        segments_filt = np.concatenate([points_filt[:-1], points_filt[1:]], axis=1)
        
        lc_filt = LineCollection(segments_filt, cmap='plasma', alpha=0.9, linewidth=2)
        lc_filt.set_array(time_ms[:-1]) 
        ax_iv.add_collection(lc_filt)
        
        if IV_PLOT_MODE != 'RAW':
            cbar = fig.colorbar(lc_filt, ax=ax_iv, pad=0.02)
            cbar.set_label('Time (ms)', fontweight='bold')
    
    v_lim = df['V_Sample_V_Raw'] * 1e3 if IV_PLOT_MODE in ['RAW', 'BOTH'] else df['V_Sample_V_Filt'] * 1e3
    i_lim = df['I_Sample_A_Raw'] * 1e6 if IV_PLOT_MODE in ['RAW', 'BOTH'] else df['I_Sample_A_Filt'] * 1e6
        
    margin_v = max((v_lim.max() - v_lim.min()) * 0.05, 1.0)
    margin_i = max((i_lim.max() - i_lim.min()) * 0.05, 1.0)
    
    ax_iv.set_xlim(v_lim.min() - margin_v, v_lim.max() + margin_v)
    ax_iv.set_ylim(i_lim.min() - margin_i, i_lim.max() + margin_i)
    
    title_suffix = "(Raw Overlay + Filtered)" if IV_PLOT_MODE == 'BOTH' else f"({IV_PLOT_MODE.capitalize()})"
    ax_iv.set_xlabel('4-Wire Voltage Drop (mV)', fontweight='bold')
    ax_iv.set_ylabel('Sample Current (µA)', fontweight='bold')
    ax_iv.set_title(f'I-V Curve {title_suffix}', fontweight='bold')
    ax_iv.axhline(0, color='black', linewidth=1)
    ax_iv.axvline(0, color='black', linewidth=1)
    ax_iv.grid(True, linestyle='--', alpha=0.6)
    
    plt.tight_layout()

def generate_iv_gif(df, freq, amp, save_folder, fps=20, max_frames=200):
    """Generates and saves an animated GIF of the I-V curve."""
    v_data = df['V_Sample_V_Raw'].values * 1e3 
    i_data = df['I_Sample_A_Raw'].values * 1e6 

    fig, ax = plt.subplots(figsize=(8, 6))
    
    margin_v = max((v_data.max() - v_data.min()) * 0.05, 1.0)
    margin_i = max((i_data.max() - i_data.min()) * 0.05, 1.0)
    ax.set_xlim(v_data.min() - margin_v, v_data.max() + margin_v)
    ax.set_ylim(i_data.min() - margin_i, i_data.max() + margin_i)

    ax.axhline(0, color='black', linewidth=1)
    ax.axvline(0, color='black', linewidth=1)
    ax.set_xlabel('4-Wire Voltage Drop (mV)', fontweight='bold')
    ax.set_ylabel('Sample Current (µA)', fontweight='bold')
    ax.set_title(f'I-V Curve Temporal Evolution ({freq}Hz, {amp}V)', fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.6)

    history_line, = ax.plot([], [], color='grey', alpha=0.6, linewidth=2, zorder=2)
    head_marker, = ax.plot([], [], marker='o', color='purple', markersize=8, zorder=3)

    step = max(1, len(v_data) // max_frames)
    frame_indices = list(range(0, len(v_data), step))
    if frame_indices[-1] != len(v_data) - 1:
        frame_indices.append(len(v_data) - 1) 

    def init():
        history_line.set_data([], [])
        head_marker.set_data([], [])
        return history_line, head_marker

    def update(frame_idx):
        history_line.set_data(v_data[:frame_idx+1], i_data[:frame_idx+1])
        head_marker.set_data([v_data[frame_idx]], [i_data[frame_idx]]) 
        return history_line, head_marker

    filename = os.path.join(save_folder, f"iv_animation_{freq}_{amp}.gif")
    print(f"Rendering GIF... This may take a few seconds.")
    
    ani = animation.FuncAnimation(
        fig, update, frames=frame_indices, 
        init_func=init, blit=True, interval=1000/fps
    )

    ani.save(filename, writer='pillow', fps=fps)
    plt.close(fig) 
    print(f"✓ GIF saved to {filename}")

def analyze_offline_file(filepath):
    print(f"\n--- Loading: {os.path.basename(filepath)} ---")
    
    freq, amp, cycles, wave_shape = "???", "???", "???", "???"
    
    # ... (Keep your existing header parsing and CSV loading here) ...
    df = pd.read_csv(filepath, comment='#')
    
    # ... (Keep your existing Savitzky-Golay filter fallback here) ...
        
    # Generate the standard time-domain plots
    plot_dashboard(df, freq, amp, wave_shape, cycles)
    
    if GENERATE_GIF:
        generate_iv_gif(df, freq, amp, os.path.dirname(filepath))
        
    # --- NEW: Run the Fourier Analysis ---
    # Calculate the time step (dt) by subtracting the first time point from the second
    dt = df['Time_s'].iloc[1] - df['Time_s'].iloc[0]
    
    print(f"Running FFT Analysis (dt = {dt:.2e} seconds)...")
    plot_impedance_spectrum(df, dt)

from scipy.fft import rfft, rfftfreq

def plot_impedance_spectrum(df, dt):
    # 1. Extract the raw time-domain arrays (Use RAW, not filtered, to preserve high frequencies!)
    v_time = df['CH4_V_SenseN_Raw'].values - df['CH3_V_SenseP_Raw'].values
    i_time = (df['CH1_V_Supply_Raw'].values - df['CH2_V_Resistor_Raw'].values) / 1000.0
    
    # 2. Perform the Fast Fourier Transform
    N = len(v_time)
    V_freq = rfft(v_time)
    I_freq = rfft(i_time)
    
    # 3. Calculate Complex Impedance
    # (Add a tiny epsilon to I_freq to prevent division by zero at DC)
    Z_freq = V_freq / (I_freq + 1e-12) 
    
    # Calculate the frequency bins
    frequencies = rfftfreq(N, d=dt)
    
    # Calculate Magnitude (Ohms) and Phase (Degrees)
    Z_mag = np.abs(Z_freq)
    Z_phase = np.angle(Z_freq, deg=True)
    
    # --- PLOTTING ---
    fig, (ax_mag, ax_phase) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    
    # Magnitude Plot
    ax_mag.loglog(frequencies, Z_mag, color='blue')
    ax_mag.set_ylabel('Impedance Magnitude |Z| ($\Omega$)', fontweight='bold')
    ax_mag.set_title('Bode Plot: Frequency Response of DUT', fontweight='bold')
    ax_mag.grid(True, which="both", ls="--", alpha=0.5)
    
    # Phase Plot
    ax_phase.semilogx(frequencies, Z_phase, color='red')
    ax_phase.set_xlabel('Frequency (Hz)', fontweight='bold')
    ax_phase.set_ylabel('Phase Angle ($\circ$)', fontweight='bold')
    ax_phase.grid(True, which="both", ls="--", alpha=0.5)
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    # ---------------------------------------------------------
    # PASTE THE PATH TO YOUR FILE OR FOLDER HERE
    # ---------------------------------------------------------
    # Example 1: A specific file
    # DATA_PATH = "Sweep_Data_20260505_132752/burst_20Hz_0.3V.csv"
    
    # Example 2: A whole folder!
    DATA_PATH = "C:\\LBT\\phd\\Iridatos\\SQU_1000Hz_1000Hz_Sweep_Data_20260518_195409\\burst_1000Hz_0.15V.csv" # <-- Update this to your actual folder name
    
    if os.path.isfile(DATA_PATH):
        # Process a single file
        analyze_offline_file(DATA_PATH)
        plt.show()
        
    elif os.path.isdir(DATA_PATH):
        # Process all CSVs in a folder automatically
        csv_files = glob.glob(os.path.join(DATA_PATH, "*.csv"))
        if not csv_files:
            print(f"No CSV files found in {DATA_PATH}")
        else:
            for file in csv_files:
                analyze_offline_file(file)
            plt.show() # Display all generated dashboards simultaneously
            
    else:
        print("Path not found. Please update DATA_PATH to a valid file or folder.")