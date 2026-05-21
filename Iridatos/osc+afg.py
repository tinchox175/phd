#%%
import pyvisa
import numpy as np
import pandas as pd
import time
import os
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.signal import savgol_filter
from matplotlib.collections import LineCollection 

# --- CONFIGURATION ---
R_LIMIT = 1000.0  
MAX_VOLTAGE = 0.4 
NUM_CYCLES = 1      
WAVE_SHAPE = 'SQU'  # Options: 'SQU', 'PULS', 'RAMP'  
PULSE_WIDTH = 2000e-9     
EDGE_TIME = 50e-9           

# --- NEW TIMING TOGGLE ---
PULSE_ZOOM_FACTOR = 10.0   # Captures the pulse + a tail 9x longer than the pulse

# --- PLOTTING TOGGLES ---
IV_PLOT_MODE = 'BOTH'  # Options: 'RAW', 'FILTERED', 'BOTH'

AFG_ADDR = 'GPIB0::10::INSTR'  
SCOPE_ADDR = 'USB0::0x0699::0x0413::C012302::0::INSTR'    

# ⚠️ SET TO TRUE IF YOU CONNECTED THE AGILENT 'SYNC' PORT TO THE SCOPE 'AUX IN/EXT' PORT
USE_SYNC_CABLE = False 

def initialize_instruments():
    rm = pyvisa.ResourceManager()
    afg = rm.open_resource(AFG_ADDR)
    scope = rm.open_resource(SCOPE_ADDR)
    
    scope.timeout = 10000 
    afg.timeout = 5000
    
    # --- GENERATOR WAVEFORM SETUP ---
    afg.write('OUTP:LOAD INF') 
    afg.write(f'FUNC {WAVE_SHAPE}')
    
    if WAVE_SHAPE == 'RAMP':
        afg.write('FUNC:RAMP:SYMM 50') 
        
    afg.write('BURS:MODE TRIG')
    afg.write(f'BURS:NCYC {NUM_CYCLES}') 
    afg.write('BURS:STAT ON')
    afg.write('TRIG:SOUR BUS') 
    
    # Configure Scope Coupling
    scope.write('SEL:CH1 ON'); scope.write('CH1:COUP DC'); scope.write('CH1:BWL 20')
    scope.write('SEL:CH2 ON'); scope.write('CH2:COUP DC'); scope.write('CH2:BWL 20')
    scope.write('SEL:CH3 ON'); scope.write('CH3:COUP AC'); scope.write('CH3:BWL 20') 
    scope.write('SEL:CH4 ON'); scope.write('CH4:COUP AC'); scope.write('CH4:BWL 20') 
        
    scope.write('ACQ:MOD HIR') 
    scope.write('HOR:RECO 10000') 
    
    return afg, scope

def auto_scale_scope(scope, afg, freq, amp):
    period = 1.0 / freq
    
    if WAVE_SHAPE == 'PULS':
        # 1. Scope needs to calculate the TRUE pulse size using the Agilent's hardware rules
        target_width = max(PULSE_WIDTH, 8e-9)
        max_allowed_edge = 0.625 * target_width
        actual_edge = min(EDGE_TIME, max_allowed_edge)
        actual_edge = max(actual_edge, 5e-9)
        
        max_safe_width = period - (1.6 * actual_edge)
        actual_width = min(target_width, max_safe_width)
        
        # 2. Zoom based on the TRUE physical pulse time
        active_pulse_time = (actual_edge * 2) + actual_width
        total_time_needed = active_pulse_time * PULSE_ZOOM_FACTOR
        
        # Failsafes: Don't zoom out past the period, and don't zoom in past hardware limits (1ns/div)
        total_time_needed = min(total_time_needed, period)
        total_time_needed = max(total_time_needed, 10e-9) 
    else:
        # Standard framing for continuous-like waves (Sine, Triangle/Ramp)
        total_time_needed = (NUM_CYCLES + 1.5) * period
        
    t_div = total_time_needed / 10.0
    scope.write(f'HOR:SCA {t_div}')
    
    scope.write('HOR:DEL:MOD OFF') 
    scope.write('HOR:POS 20')  
    
    # --- TRIGGER ROUTING ---
    scope.write('TRIG:A:TYP EDGE') 
    scope.write('TRIG:A:EDGE:SLO RISE') 
    
    if USE_SYNC_CABLE:
        scope.write('TRIG:A:SOUR EXT') 
        scope.write('TRIG:A:LEV 1.0')  
    else:
        scope.write('TRIG:A:SOUR CH1')
        scope.write('TRIG:A:EDGE:COUP DC') 
        # For ultra-fast pulses, catching it lower (20%) is safer than 50%
        scope.write(f'TRIG:A:LEV {amp * 0.2}') 
    
    safe_scale = amp / 4.0 
    for ch in [1, 2, 3, 4]:
        scope.write(f'CH{ch}:SCA {safe_scale}')
        scope.write(f'CH{ch}:POS 0') 
        
    scope.write('ACQ:STOPA SEQ') 
    scope.write('ACQ:STATE ON')
    time.sleep(0.2)   
    afg.write('*TRG') 
    
    timeout = time.time()
    while int(scope.query('BUSY?')) == 1:
        time.sleep(0.05)
        if time.time() - timeout > 2.0: break
    
    for ch in [1, 2, 3, 4]:
        try:
            scope.write(f'DAT:SOU CH{ch}')
            scope.write('DAT:ENC ASCI')
            scope.write('DAT:WID 1')
            time.sleep(0.05)
            
            y_mult = float(scope.query('WFMPre:YMULT?'))
            y_zero = float(scope.query('WFMPre:YZERO?'))
            y_off = float(scope.query('WFMPre:YOFF?'))
            
            raw_data = np.array(scope.query_ascii_values('CURV?'))
            volts = (raw_data - y_off) * y_mult + y_zero
            
            vpp = np.max(volts) - np.min(volts)
            
            if vpp > 0: 
                optimal_scale = max(vpp / 4.0, 0.001) 
                scope.write(f'CH{ch}:SCA {optimal_scale}')
                
        except Exception:
            pass 
            
    time.sleep(0.2)

def get_waveform(scope, channel):
    scope.write(f'DAT:SOU CH{channel}')
    scope.write('DAT:ENC ASCI')
    scope.write('DAT:WID 1')
    
    time.sleep(0.05) 
    
    y_mult = float(scope.query('WFMPre:YMULT?'))
    y_zero = float(scope.query('WFMPre:YZERO?'))
    y_off = float(scope.query('WFMPre:YOFF?'))
    x_incr = float(scope.query('WFMPre:XINCR?'))
    
    raw_data = np.array(scope.query_ascii_values('CURV?'))
    volts = (raw_data - y_off) * y_mult + y_zero
    
    return volts, x_incr

def run_sweep(afg, scope, frequencies, amplitudes, save_folder):
    results = {}
    
    for freq in frequencies:
        for raw_amp in amplitudes:
            
            amp = MAX_VOLTAGE if raw_amp > MAX_VOLTAGE else raw_amp
            print(f"\nSweeping: Freq = {freq} Hz, Amp = {amp} V, Shape = {WAVE_SHAPE}, Cycles = {NUM_CYCLES}")
            
            afg.write(f'SOUR:FREQ {freq}')
            
            if WAVE_SHAPE in ['SQU', 'PULS']:
                # Unipolar (0V to Max)
                afg.write(f'SOUR:VOLT:HIGH {amp}') 
                afg.write('SOUR:VOLT:LOW 0')   
                
                # Apply custom pulse width and edges safely
                if WAVE_SHAPE == 'PULS':
                    period = 1.0 / freq
                    
                    # 1. Calculate the final safe targets
                    target_width = max(PULSE_WIDTH, 8e-9)
                    max_allowed_edge = 0.625 * target_width
                    actual_edge = min(EDGE_TIME, max_allowed_edge)
                    actual_edge = max(actual_edge, 5e-9)
                    
                    max_safe_width = period - (1.6 * actual_edge)
                    actual_width = min(target_width, max_safe_width)
                    
                    # 2. BREAK THE CATCH-22: Enter the "Safe State"
                    # We temporarily stretch the pulse width to a massive 10% of the period.
                    # This guarantees the old edge times won't trigger an error.
                    safe_buffer_width = period * 0.1 
                    afg.write(f'SOUR:PULS:WIDT {safe_buffer_width}') 
                    
                    # 3. Now that the width is huge, it is 100% safe to shrink the edges down
                    afg.write(f'SOUR:PULS:TRAN:LEAD {actual_edge}') 
                    afg.write(f'SOUR:PULS:TRAN:TRA {actual_edge}')  
                    
                    # 4. Finally, snap the width down to your actual nanosecond target
                    afg.write(f'SOUR:PULS:WIDT {actual_width}')
                    
            else:
                # Bipolar (Negative to Positive)
                afg.write(f'SOUR:VOLT {amp}')
                afg.write('SOUR:VOLT:OFFS 0')
                
            afg.write('OUTP ON')
            
            auto_scale_scope(scope, afg, freq, amp)
            
            scope.write('ACQ:STOPA SEQ') 
            scope.write('ACQ:STATE ON')  
            time.sleep(0.2) 
            
            afg.write('*TRG')            
            time.sleep(0.1) 
            
            timeout_start = time.time()
            trigger_success = True
            
            while int(scope.query('BUSY?')) == 1:
                time.sleep(0.05)
                if time.time() - timeout_start > 5.0: 
                    print(f"⚠️ Trigger Timeout! Scope missed the pulse at {freq}Hz, {amp}V.")
                    scope.write('ACQ:STATE OFF') 
                    trigger_success = False
                    break
                
            afg.write('OUTP OFF')
            
            if not trigger_success:
                continue
            
            v1, dt = get_waveform(scope, 1)
            v2, _ = get_waveform(scope, 2)
            v3, _ = get_waveform(scope, 3)
            v4, _ = get_waveform(scope, 4)
            
            time_axis = np.arange(len(v1)) * dt
            
            # --- PHYSICS ---
            current = (v1 - v2) / R_LIMIT
            v_dut = v4 - v3  
            
            # --- FILTERING ---
            window_len = min(101, len(time_axis))
            if window_len % 2 == 0: window_len -= 1 
            poly_order = 3
            
            v_dut_filt = savgol_filter(v_dut, window_len, poly_order)
            current_filt = savgol_filter(current, window_len, poly_order)
            
            df = pd.DataFrame({
                'Time_s': time_axis,
                'CH1_V_Supply_Raw': v1,
                'CH2_V_Resistor_Raw': v2,
                'CH3_V_SenseP_Raw': v3,
                'CH4_V_SenseN_Raw': v4,
                'I_Sample_A_Raw': current,
                'V_Sample_V_Raw': v_dut,
                'I_Sample_A_Filt': current_filt,
                'V_Sample_V_Filt': v_dut_filt
            })
            
            # --- SAVE DATA TO CSV ---
            filename = os.path.join(save_folder, f"burst_{freq}Hz_{amp}V.csv")
            
            metadata = (
                f"# --- BURST CONFIGURATION LOG ---\n"
                f"# Waveform Shape: {WAVE_SHAPE}\n"
                f"# Frequency (Hz): {freq}\n"
                f"# Amplitude Applied (V): {amp}\n"
                f"# Burst Cycles: {NUM_CYCLES}\n"
                f"# Limiting Resistor (Ohm): {R_LIMIT}\n"
                f"# Hard Max Voltage Limit (V): {MAX_VOLTAGE}\n"
                f"# Sense Channels AC Coupled: True\n"
                f"# V_Sample Calculation: CH4 - CH3\n"
                f"# Savitzky-Golay Filter: Window={window_len}, Poly={poly_order}\n"
                f"# -------------------------------\n"
            )
            
            with open(filename, 'w') as f:
                f.write(metadata)
            
            df.to_csv(filename, mode='a', index=False)
            
            results[(freq, amp)] = df
            print(f"✓ Data acquired and saved to {filename}")
            
    return results

def plot_dashboard(df, freq, amp):
    fig = plt.figure(figsize=(15, 10)) 
    gs = gridspec.GridSpec(3, 2, width_ratios=[1, 1], height_ratios=[1, 1, 1.2])
    
    time_ms = df['Time_s'] * 1e3 
    
    # --- Row 1: Drive Traces ---
    ax_drive = fig.add_subplot(gs[0, 0])
    ax_drive.plot(time_ms, df['CH1_V_Supply_Raw'], label='CH1: Supply (V)', color='C0')
    ax_drive.plot(time_ms, df['CH2_V_Resistor_Raw'], label='CH2: Across 1kΩ (V)', color='C1')
    ax_drive.set_ylabel('Amplitude (V)', fontweight='bold')
    ax_drive.set_title(f'Drive Signals ({freq}Hz, {amp}V, {WAVE_SHAPE}, {NUM_CYCLES} Cycles)', fontweight='bold')
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
    
    # --- Right Side: I-V Curve (Toggle Implementation) ---
    ax_iv = fig.add_subplot(gs[:, 1]) 
    
    # 1. Plot RAW Data if requested (or if 'BOTH' is selected)
    if IV_PLOT_MODE in ['RAW', 'BOTH']:
        v_data_raw = df['V_Sample_V_Raw'] * 1e3
        i_data_raw = df['I_Sample_A_Raw'] * 1e6
        
        points_raw = np.array([v_data_raw, i_data_raw]).T.reshape(-1, 1, 2)
        segments_raw = np.concatenate([points_raw[:-1], points_raw[1:]], axis=1)
        
        # If both are plotting, make the raw trace a transparent background cloud
        if IV_PLOT_MODE == 'BOTH':
            lc_raw = LineCollection(segments_raw, colors='grey', alpha=0.25, linewidth=1)
            ax_iv.add_collection(lc_raw)
        else:
            # If only raw, give it the full colormap
            lc_raw = LineCollection(segments_raw, cmap='plasma', alpha=0.9, linewidth=2)
            lc_raw.set_array(time_ms[:-1]) 
            ax_iv.add_collection(lc_raw)
            cbar = fig.colorbar(lc_raw, ax=ax_iv, pad=0.02)
            cbar.set_label('Time (ms)', fontweight='bold')

    # 2. Plot FILTERED Data if requested
    if IV_PLOT_MODE in ['FILTERED', 'BOTH']:
        v_data_filt = df['V_Sample_V_Filt'] * 1e3
        i_data_filt = df['I_Sample_A_Filt'] * 1e6
        
        points_filt = np.array([v_data_filt, i_data_filt]).T.reshape(-1, 1, 2)
        segments_filt = np.concatenate([points_filt[:-1], points_filt[1:]], axis=1)
        
        lc_filt = LineCollection(segments_filt, cmap='plasma', alpha=0.9, linewidth=2)
        lc_filt.set_array(time_ms[:-1]) 
        ax_iv.add_collection(lc_filt)
        
        # Only add colorbar here if we didn't already add it for RAW
        if IV_PLOT_MODE != 'RAW':
            cbar = fig.colorbar(lc_filt, ax=ax_iv, pad=0.02)
            cbar.set_label('Time (ms)', fontweight='bold')
    
    # Calculate limits dynamically depending on what we plotted
    if IV_PLOT_MODE in ['RAW', 'BOTH']:
        v_lim = df['V_Sample_V_Raw'] * 1e3
        i_lim = df['I_Sample_A_Raw'] * 1e6
    else:
        v_lim = df['V_Sample_V_Filt'] * 1e3
        i_lim = df['I_Sample_A_Filt'] * 1e6
        
    margin_v = (v_lim.max() - v_lim.min()) * 0.05
    margin_i = (i_lim.max() - i_lim.min()) * 0.05
    
    # Fallback bounds in case of completely flat traces (0 volts)
    margin_v = margin_v if margin_v > 0 else 1.0
    margin_i = margin_i if margin_i > 0 else 1.0
    
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
#%%
if __name__ == "__main__":
    test_frequencies = [1000] 
    test_amplitudes = [0.15]  
    
    # --- CREATE SAVE DIRECTORY ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_folder = f"{WAVE_SHAPE}_{np.min(test_frequencies)}Hz_{np.max(test_frequencies)}Hz_Sweep_Data_{timestamp}"
    os.makedirs(save_folder, exist_ok=True)
    print(f"Data will be saved to: {os.path.abspath(save_folder)}")
    
    afg, scope = initialize_instruments()
    
    try:
        dataset = run_sweep(afg, scope, test_frequencies, test_amplitudes, save_folder)
        
        if dataset:
            print(f"\nPlotting {len(dataset)} acquired datasets...")
            for (freq, amp), df_plot in dataset.items():
                plot_dashboard(df_plot, freq, amp)
            
            plt.show()
        else:
            print("No data was acquired to plot. Check trigger settings.")

    finally:
        afg.write('OUTP OFF')
        afg.close()
        scope.close()
        print("Instruments successfully closed.")