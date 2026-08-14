#%%
import re
import time
import itertools
import concurrent.futures
from functools import partial

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from scipy.optimize import curve_fit
from scipy.stats import chi2 as chi2_stat

# =============================================================================
# 1. MATHEMATICAL CORE & STRING TRANSLATORS
# =============================================================================
def p(*args):
    """Calculates equivalent impedance of parallel branches."""
    return 1.0 / (sum(1.0 / (z + 1e-15) for z in args) + 1e-15)

def build_circuit_function(circuit_string):
    """Translates a generic string into a SciPy-compatible complex math function."""
    components = list(dict.fromkeys(re.findall(r'[RCL]\d+', circuit_string)))
    eval_string = circuit_string.replace('-', '+')
    
    def Z_model_scipy(f_stacked, *params):
        f = f_stacked[:len(f_stacked)//2]
        omega = 2 * np.pi * f
        local_env = {'p': p, 'np': np}
        
        for comp, val in zip(components, params):
            if comp.startswith('R'):
                local_env[comp] = val 
            elif comp.startswith('C'):
                local_env[comp] = 1.0 / (1j * omega * val + 1e-15)
            elif comp.startswith('L'):
                local_env[comp] = 1j * omega * val
                
        try:
            Z_complex = eval(eval_string, {"__builtins__": None}, local_env) * np.ones_like(omega)
        except ZeroDivisionError:
            Z_complex = np.ones_like(omega) * 1e10 
        
        Z_real = np.nan_to_num(Z_complex.real, nan=1e10, posinf=1e10, neginf=-1e10)
        Z_imag = np.nan_to_num(Z_complex.imag, nan=1e10, posinf=1e10, neginf=-1e10)
        
        return np.hstack([Z_real, Z_imag])
        
    return Z_model_scipy, components

def assign_component_numbers(generic_circuit):
    """Translates 'p(C,R)-L' into 'p(C1,R1)-L1'"""
    counts = {'R': 1, 'C': 1, 'L': 1}
    def replacer(match):
        comp = match.group(0) 
        num = counts[comp]
        counts[comp] += 1
        return f"{comp}{num}"
    return re.sub(r'[RCL]', replacer, generic_circuit)


# =============================================================================
# 2. TOPOLOGY GENERATORS & PHYSICS FILTERS
# =============================================================================
def generate_smart_topologies():
    """Generates mathematically unique, non-redundant circuit topologies."""
    components = ['C', 'L', 'R']
    branches = ["-".join(combo) for i in range(1, 4) for combo in itertools.combinations(components, i)]
            
    blocks = ['C', 'L', 'R'] 
    for i in range(2, 4):
        for combo in itertools.combinations_with_replacement(branches, i):
            if combo.count('R') > 1 or combo.count('C') > 1 or combo.count('L') > 1:
                continue
            blocks.append(f"p({','.join(combo)})")
                
    generic_circuits = []
    for i in range(1, 4):
        for combo in itertools.combinations_with_replacement(blocks, i):
            if combo.count('R') > 1 or combo.count('C') > 1 or combo.count('L') > 1:
                continue
            generic_circuits.append("-".join(combo))
            
    return generic_circuits

def filter_by_physics(circuit_string):
    """Prunes possibilities based on DRT assumptions."""
    if circuit_string.count('L') > 2: return False
    if circuit_string.count('C') > 2: return False
    if circuit_string.count('R') < 3: return False
    return True

def generate_fhn_test_suite():
    """
    Generates targeted solid-state topologies. 
    Strictly enforces a series Resistor (Rs) to capture the high-frequency Re(Z) offset,
    preventing parallel blocks from warping to fit the real axis.
    """
    parasitic_blocks = [
        'R',                 # Rs + FHN Core (The absolute baseline)
        'R-L',               # Rs + Wiring Inductance + FHN Core
        'p(C,R)',            # Grain Boundary/Contact Interface + FHN Core
        'R-p(C,R)',          # Rs + Grain Boundary/Contact Interface + FHN Core
        'R-L-p(C,R)',        # Rs + Wiring + Interface + FHN Core (Max complexity)
    ]
    
    test_cases = []
    
    for p_block in parasitic_blocks:
        raw_string = f"{p_block}-p(C,R,L-R)"
        numbered_circuit = assign_component_numbers(raw_string)
        
        match = re.search(r'p\((C\d+),(R\d+),(L\d+)-(R\d+)\)$', numbered_circuit)
        
        if match:
            test_cases.append({
                'circuit': numbered_circuit,
                'fhn_parallel_R': match.group(2), 
                'fhn_series_R': match.group(4)    
            })
            
    return test_cases


# =============================================================================
# 3. FITTING ENGINES
# =============================================================================
def evaluate_circuit_agnostic(circuit_string, f_stacked, Z_stacked, sigma_stacked):
    """The master fitting engine for general, blind sweeps."""
    try:
        Z_model, comp_names = build_circuit_function(circuit_string)
        resistors = [comp for comp in comp_names if comp.startswith('R')]
        
        best_coarse_chi2, winner_popt, winner_lows, winner_highs, winner_candidate = np.inf, None, None, None, None
        
        for neg_candidate in resistors:
            guesses, lows, highs = [], [], []
            for comp in comp_names:
                if comp == neg_candidate:
                    guesses.append(-10.0); lows.append(-3000); highs.append(0.0)
                elif comp.startswith('R'):
                    guesses.append(10.0); lows.append(0.0); highs.append(5000)
                elif comp.startswith('C'):
                    guesses.append(1e-9); lows.append(0.0); highs.append(10)
                elif comp.startswith('L'):
                    guesses.append(10); lows.append(1e-10); highs.append(100)

            popt_coarse, _ = curve_fit(Z_model, f_stacked, Z_stacked, p0=guesses, bounds=(lows, highs), sigma=sigma_stacked, absolute_sigma=True, maxfev=100)
            chi2_coarse = np.sum(((Z_model(f_stacked, *popt_coarse) - Z_stacked) / sigma_stacked)**2) / (len(Z_stacked) - len(comp_names))
            
            if chi2_coarse < best_coarse_chi2:
                best_coarse_chi2, winner_popt, winner_lows, winner_highs, winner_candidate = chi2_coarse, popt_coarse, lows, highs, neg_candidate

        if best_coarse_chi2 > 1e4:
            return {'circuit': circuit_string, 'status': 'failed_pass_1', 'error': best_coarse_chi2}

        popt_fine, _ = curve_fit(Z_model, f_stacked, Z_stacked, p0=winner_popt, bounds=(winner_lows, winner_highs), sigma=sigma_stacked, absolute_sigma=True, maxfev=10000)
        
        chi2_val = np.sum(((Z_model(f_stacked, *popt_fine) - Z_stacked) / sigma_stacked)**2)
        dof = len(Z_stacked) - len(comp_names)
        k_params = len(comp_names)
        
        return {
            'circuit': circuit_string, 'status': 'success', 
            'error': chi2_val / dof, 'chi2_abs': chi2_val,
            'bic': chi2_val + k_params * np.log(len(Z_stacked)),
            'k_params': k_params, 'p_value': chi2_stat.sf(chi2_val, dof),
            'params': dict(zip(comp_names, popt_fine)),
            'negative_resistor_used': winner_candidate
        }
    except Exception as e:
        return {'circuit': circuit_string, 'status': f'error: {str(e)}', 'error': np.inf}

from scipy.optimize import least_squares

from scipy.optimize import least_squares

def test_fhn_hypothesis(circuit_string, forced_neg_resistor, f_stacked, Z_stacked, sigma_stacked, p0_dict=None, smoothness_weight=0.05):
    Z_model, comp_names = build_circuit_function(circuit_string)
    
    # --- SMART INITIAL GUESSES ---
    real_data = Z_stacked[:len(Z_stacked)//2]
    min_re = max(np.min(real_data), 1e-3)
    first_re = real_data[0]
    arc_width = max(np.max(real_data) - min_re, 1e-3)
    
    guesses, lows, highs = [], [], []
    for comp in comp_names:
        if comp == forced_neg_resistor:
            guess = -2 if p0_dict is None else p0_dict.get(comp)
            guesses.append(guess)
            lows.append(-1e6)
            highs.append(-1e-3)

        elif comp.startswith('R'):
            guess = 0.1 if p0_dict is None else p0_dict.get(comp)
            guesses.append(guess)
            lows.append(1e-2)
            highs.append(1e6)
            
        elif comp.startswith('C'):
            guess = 1e-10 if p0_dict is None else p0_dict.get(comp)
            guesses.append(guess)
            lows.append(1e-12)
            highs.append(1e-5)
            
        elif comp.startswith('L'):
            guess = 0.1 if p0_dict is None else p0_dict.get(comp)
            guesses.append(guess)
            lows.append(1e-10)
            highs.append(10) 

    # --- CALCULATE WEIGHTS GLOBALLY FOR THE FUNCTION ---
    # Moved outside the cost function so the final chi2 calculation can use it
    modulus_floor = np.abs(Z_stacked) * 0.02
    effective_weight = np.sqrt(sigma_stacked**2 + modulus_floor**2)

    def cost_function(params):
        z_pred = Z_model(f_stacked, *params)
        eis_residuals = (z_pred - Z_stacked) / effective_weight
        
        if p0_dict is None or smoothness_weight == 0:
            return eis_residuals
            
        smoothness_residuals = []
        for idx, comp in enumerate(comp_names):
            prev_val = p0_dict.get(comp, params[idx])
            curr_log = np.log(max(abs(params[idx]), 1e-12))
            prev_log = np.log(max(abs(prev_val), 1e-12))
            
            diff = smoothness_weight * (curr_log - prev_log)
            smoothness_residuals.append(diff)
            
        return np.concatenate([eis_residuals, np.array(smoothness_residuals)])

    try:
        result = least_squares(
            cost_function, 
            x0=guesses, 
            bounds=(lows, highs), 
            method='trf', 
            max_nfev=15000, 
            diff_step=1e-4 
        )
        
        popt = result.x
        z_final = Z_model(f_stacked, *popt)
        pure_eis_res = (z_final - Z_stacked) / effective_weight
        chi2_val = np.sum(pure_eis_res**2)
        dof = len(Z_stacked) - len(comp_names)
        
        return {
            'status': 'success', 
            'error': chi2_val / dof if dof > 0 else chi2_val, 
            'bic': chi2_val + len(comp_names) * np.log(len(Z_stacked)),
            'params': dict(zip(comp_names, popt))
        }
    except Exception as e:
        return {'status': f'failed_to_converge: {str(e)}'}

# =============================================================================
# 4. VISUALIZATION & PLOTTING
# =============================================================================
def plot_eis_results(f, Z, Z_fit, title):
    """Abstracted 3-panel plotting function to reduce redundancy."""
    fig = plt.figure(figsize=(12, 5))
    gs = GridSpec(2, 3, figure=fig)
    
    ax_real = fig.add_subplot(gs[0, 0])
    ax_imag = fig.add_subplot(gs[1, 0], sharex=ax_real)
    ax_nyq = fig.add_subplot(gs[:, 1:])
    
    ax_real.semilogx(f, Z.real, 'o', color='black', markersize=5, mfc='none', label='Data')
    ax_real.semilogx(f, Z_fit.real, '-', color='red', linewidth=2, label='Fit')
    ax_real.set_ylabel(r"Re(Z) [$\Omega$]")
    ax_real.grid(True, which='both', ls='--', alpha=0.5)
    ax_real.legend(loc='best')
    plt.setp(ax_real.get_xticklabels(), visible=False)
    
    ax_imag.semilogx(f, -Z.imag, 'o', color='black', markersize=5, mfc='none')
    ax_imag.semilogx(f, -Z_fit.imag, '-', color='red', linewidth=2)
    ax_imag.set_xlabel("Frequency [Hz]")
    ax_imag.set_ylabel(r"-Im(Z) [$\Omega$]")
    ax_imag.grid(True, which='both', ls='--', alpha=0.5)
    
    ax_nyq.scatter(Z.real, -Z.imag, color='black', s=40, edgecolor='black', alpha=0.85, label='Data')
    ax_nyq.plot(Z_fit.real, -Z_fit.imag, '-', color='red', linewidth=2, label='Fit')
    # ax_nyq.set_aspect('equal', adjustable='datalim') 
    ax_nyq.set_title(title, fontweight='bold')
    ax_nyq.set_xlabel(r"Re(Z) [$\Omega$]")
    ax_nyq.set_ylabel(r"-Im(Z) [$\Omega$]")
    ax_nyq.grid(True, ls='--', alpha=0.5)
    ax_nyq.legend(loc='best')
    
    plt.tight_layout()
    plt.show()

def test_manual_circuit(circuit_string, f_stacked, Z_stacked, sigma_stacked):
    """Evaluates a single string and plots the result."""
    print(f"\n{'='*50}\n MANUAL TEST: {circuit_string}\n{'='*50}")
    res = evaluate_circuit_agnostic(circuit_string, f_stacked, Z_stacked, sigma_stacked)
    
    if res['status'] != 'success':
        print(f"❌ Fit Failed. Reason: {res['status']}"); return
        
    print(f"✅ Fit Successful!\n  BIC Score: {res['bic']:.4e}  |  Reduced Chi-Square: {res['error']:.4f}\n  --- Parameters ---")
    for p, v in res['params'].items(): print(f"     {p}: {v:.4e}")
        
    Z_model, comp_names = build_circuit_function(circuit_string)
    Z_fit_stacked = Z_model(f_stacked, *[res['params'][c] for c in comp_names])
    
    plot_eis_results(f_stacked[:len(f_stacked)//2], 
                     Z_stacked[:len(Z_stacked)//2] + 1j * Z_stacked[len(Z_stacked)//2:], 
                     Z_fit_stacked[:len(Z_fit_stacked)//2] + 1j * Z_fit_stacked[len(Z_fit_stacked)//2:], 
                     f"Manual Fit: {circuit_string}")
import os
import glob

def load_temperature_series(base_directory):
    """
    Scans a directory (and subdirectories) for EIS text files.
    Extracts the temperature from the filename and builds a dictionary of stacked datasets.
    """
    thermal_data = {}
    search_pattern = os.path.join(base_directory, '**', '*.txt')
    file_list = glob.glob(search_pattern, recursive=True)
    print(file_list)
    for filepath in file_list:
        temp_match = re.search(r'\(?\s*(\d+(?:\.\d+)?)\s*\)?\s*K', filepath)
        if not temp_match:
            continue 
            
        temp_val = float(temp_match.group(1))
        
        try:
            data = np.genfromtxt(filepath, unpack=True, delimiter=',', skip_header=1)
            i = 1
            l = min(500, len(data[0]))
            
            f = data[0][i:l]
            Z = data[1][i:l] + 1j*data[3][i:l]
            
            # FIXED: Slice from [0:l] to match f and Z shapes
            sigma_real = data[2][i:l]
            sigma_imag = data[4][i:l]
            
            # Protect against exact 0.0 errors from the device
            sigma_real = np.where(sigma_real <= 0, 1e-5, sigma_real)
            sigma_imag = np.where(sigma_imag <= 0, 1e-5, sigma_imag)
            
            f_stacked = np.hstack([f, f])
            Z_stacked = np.hstack([Z.real, Z.imag])
            sigma_stacked = np.hstack([sigma_real, sigma_imag])
            
            thermal_data[temp_val] = (f_stacked, Z_stacked, sigma_stacked)
            
        except Exception as e:
            print(f"Skipped {filepath}: {e}")
            
    # Sort strictly from Highest Temperature to Lowest Temperature (Cooling down)
    sorted_thermal_data = {k: thermal_data[k] for k in sorted(thermal_data.keys(), reverse=True)}
    print(f"Successfully loaded {len(sorted_thermal_data)} temperature datasets.")
    
    return sorted_thermal_data
# # =============================================================================
# # 5. DATA LOADING
# # =============================================================================
dire = r'E:\trabajo\tesis 3\tesisfisica/IVs/2011/ZdeW_1234_16-11-24/0V dc'
# data = np.genfromtxt(rf'{dire}/ZdeW_1234_Temperatura_280.79_K_0534/Offset_0.00_mV.txt', unpack=True, delimiter=',', skip_header=1)

# l = 2000
# f = data[0][1:l]
# Z = data[1][1:l] + 1j*data[3][1:l]


# f_stacked = np.hstack([f, f])
# Z_stacked = np.hstack([Z.real, Z.imag])
# sigma_stacked = np.hstack([sigma_real, sigma_imag])


# =============================================================================
# 6. MASTER EXECUTION DASHBOARD
# =============================================================================
# Set to 'MANUAL', 'BLIND_SWEEP', or 'FHN_SWEEP'
RUN_MODE = 'GLOBAL_CONSENSUS' 
RUN_MODE = 'MANUAL'  # <-- For testing a single topology

if RUN_MODE == 'MANUAL':
    target_circuit = 'p(C1,R1)-p(C2,R2,L1-R3)'
    print(f"\n{'='*60}\n MANUAL GLOBAL THERMAL TEST: {target_circuit}\n{'='*60}")
    
    print("Scanning directories for thermal data...")
    # Uses the 'dire' variable defined in your data loading section
    thermal_data = load_temperature_series(dire) 
    
    _, comp_names = build_circuit_function(target_circuit)
    resistors = [comp for comp in comp_names if comp.startswith('R')]
    
    best_global_bic = np.inf
    best_history = None
    best_neg_r = None
    
    print(f"Testing {len(resistors)} negative resistor hypotheses for this topology...\n")
    
    # Test every resistor in the string as the potential negative component
    for neg_r in resistors:
        total_bic = 0
        failed = False
        p0 = None
        history = {}
        
        for temp, (f_st, Z_st, sig_st) in thermal_data.items():
            if temp > 400:
                continue
            res = test_fhn_hypothesis(
                target_circuit, neg_r, f_st, Z_st, sig_st, 
                p0_dict=p0, smoothness_weight=0.8
            )
            if res['status'] == 'success':
                total_bic += res['bic']
                p0 = res['params']  # Chain the parameters to the next temperature
                history[temp] = res['params']
            else:
                failed = True
                break
                
        # If this resistor hypothesis survived the thermal chain and beat the best score
        if not failed and total_bic < best_global_bic:
            best_global_bic = total_bic
            best_history = history
            best_neg_r = neg_r
            
    if best_history is None:
        print("❌ Manual Fit Failed: Could not maintain a stable fit across all temperatures.")
    else:
        print(f"✅ Fit Successful! Best Negative Resistor: {best_neg_r}")
        print(f"  Total Cumulative BIC : {best_global_bic:.4e}")
        
        # ==========================================
        # PRINT PARAMETER EVOLUTION TABLE
        # ==========================================
        print(f"\n{'='*60}")
        print(f" FULL THERMAL PARAMETER EVOLUTION (NDR: {best_neg_r})")
        print(f"{'='*60}")
        
        comps = list(best_history[list(best_history.keys())[0]].keys())
        header = f"{'Temp (K)':<10} | " + " | ".join([f"{c:<12}" for c in comps])
        print(header)
        print("-" * len(header))
        
        for temp, params in best_history.items():
            row_str = f"{temp:<10.2f} | " + " | ".join([f"{params[c]:<12.4e}" for c in comps])
            print(row_str)

        # ==========================================
        # VISUALIZE INDIVIDUAL TEMPERATURE FITS
        # ==========================================
        print(f"\nGenerating visual fits for each temperature...")
        
        # Rebuild the mathematical model for the target circuit
        Z_model, _ = build_circuit_function(target_circuit)
        temps = list(best_history.keys())
            
        for temp in temps[1:]:
            # Get the saved parameters and original data for this specific temperature
            params = [best_history[temp][comp] for comp in comp_names]
            f_st, Z_st, _ = thermal_data[temp]
            
            # Calculate the mathematical fit
            Z_fit_st = Z_model(f_st, *params)
            
            # Unstack the arrays for plotting
            half_idx = len(f_st) // 2
            f_plot = f_st[:half_idx]
            Z_plot = Z_st[:half_idx] + 1j * Z_st[half_idx:]
            Z_fit_plot = Z_fit_st[:half_idx] + 1j * Z_fit_st[half_idx:]
            
            # Draw the 3-panel plot
            plot_eis_results(
                f_plot, 
                Z_plot, 
                Z_fit_plot, 
                f"Manual Fit @ {temp:.2f}K | {target_circuit} | NDR: {best_neg_r}"
            )
            
        # ==========================================
        # FEATURE 1: PARAMETER EVOLUTION PLOTS
        # ==========================================
        print(f"\nGenerating Parameter Evolution Plots...")
        import matplotlib.cm as cm
        
        plot_temps = sorted(list(best_history.keys()))
        fig_evol, axs_evol = plt.subplots(1, 3, figsize=(15, 5))
        
        # Resistors
        for comp in comp_names:
            if comp.startswith('R'):
                vals = [best_history[t][comp] for t in plot_temps]
                axs_evol[0].plot(plot_temps, vals, 'o-', label=comp, markersize=5)
                
        axs_evol[0].set_yscale('symlog', linthresh=1e-1)
        axs_evol[0].set_title("Resistors vs Temperature")
        axs_evol[0].set_xlabel("Temperature [K]")
        axs_evol[0].set_ylabel(r"Resistance [$\Omega$]")
        axs_evol[0].grid(True, which='both', ls='--', alpha=0.5)
        axs_evol[0].legend()
        
        # Capacitors
        for comp in comp_names:
            if comp.startswith('C'):
                vals = [best_history[t][comp] for t in plot_temps]
                axs_evol[1].plot(plot_temps, vals, '^--', label=comp, markersize=5)
                
        axs_evol[1].set_yscale('log')
        axs_evol[1].set_title("Capacitors vs Temperature")
        axs_evol[1].set_xlabel("Temperature [K]")
        axs_evol[1].set_ylabel("Capacitance [F]")
        axs_evol[1].grid(True, which='both', ls='--', alpha=0.5)
        if any(c.startswith('C') for c in comp_names): axs_evol[1].legend()
        
        # Inductors
        for comp in comp_names:
            if comp.startswith('L'):
                vals = [best_history[t][comp] for t in plot_temps]
                axs_evol[2].plot(plot_temps, vals, 's-.', label=comp, markersize=5)
                
        axs_evol[2].set_yscale('log')
        axs_evol[2].set_title("Inductors vs Temperature")
        axs_evol[2].set_xlabel("Temperature [K]")
        axs_evol[2].set_ylabel("Inductance [H]")
        axs_evol[2].grid(True, which='both', ls='--', alpha=0.5)
        if any(c.startswith('L') for c in comp_names): axs_evol[2].legend()
        
        plt.tight_layout()
        plt.show()

        # ==========================================
        # FEATURE 2: GLOBAL NYQUIST OVERLAY
        # ==========================================
        print(f"Generating Global Nyquist Overlay...")
        
        fig_global, ax_global = plt.subplots(figsize=(10, 8))
        colors = cm.coolwarm(np.linspace(0, 1, len(plot_temps)))
        
        for idx, temp in enumerate(plot_temps):
            color = colors[idx]
            
            f_st, Z_st, _ = thermal_data[temp]
            params = [best_history[temp][comp] for comp in comp_names]
            Z_fit_st = Z_model(f_st, *params)
            
            half_idx = len(f_st) // 2
            Z_plot = Z_st[:half_idx] + 1j * Z_st[half_idx:]
            Z_fit_plot = Z_fit_st[:half_idx] + 1j * Z_fit_st[half_idx:]
            
            ax_global.plot(Z_plot.real, -Z_plot.imag, 'o', mfc='none', mec=color, alpha=0.3, markersize=4)
            ax_global.plot(Z_fit_plot.real, -Z_fit_plot.imag, '-', color=color, linewidth=2, label=f"{temp:.1f} K")
            
        ax_global.set_title(f"Manual Thermal Overlay: {target_circuit} | NDR: {best_neg_r}", fontweight='bold')
        ax_global.set_xlabel(r"Re(Z) [$\Omega$]")
        ax_global.set_ylabel(r"-Im(Z) [$\Omega$]")
        ax_global.set_xlim(1.5, 4)
        ax_global.set_ylim(-2, 5)
        ax_global.grid(True, ls='--', alpha=0.5)
        ax_global.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0., fontsize='small', ncol=2)
        
        plt.tight_layout()
        plt.show()
    
elif RUN_MODE == 'GLOBAL_CONSENSUS':
    print("\nScanning directories for thermal data...")
    base_dir = 'E:/trabajo/phd/phd/Iridatos/EI' 
    thermal_data = load_temperature_series(dire)
    
    fhn_cases = generate_fhn_test_suite()
    print(f"\nInitiating Global Consensus Sweep across {len(fhn_cases)} FHN topologies...")
    
    def global_worker(case):
        c_string = case['circuit']
        total_bic_type1, total_bic_type2 = 0, 0
        failed_type1, failed_type2 = False, False
        
        # Variables to hold the chaining state
        p0_t1, p0_t2 = None, None
        history_t1, history_t2 = {}, {}
        
        for temp, (f_st, Z_st, sig_st) in thermal_data.items():
            
            # --- Type 1 Test ---
            if not failed_type1:
                res1 = test_fhn_hypothesis(
                    c_string, case['fhn_parallel_R'], f_st, Z_st, sig_st, 
                    p0_dict=p0_t1, smoothness_weight=0.7  # <-- ADD THIS (Relaxed from 0.5)
                )
                if res1['status'] == 'success':
                    total_bic_type1 += res1['bic']
                    p0_t1 = res1['params']  
                    history_t1[temp] = res1['params']
                else:
                    failed_type1 = True
                    total_bic_type1 = np.inf
                    
            # --- Type 2 Test ---
            if not failed_type2:
                res2 = test_fhn_hypothesis(
                    c_string, case['fhn_series_R'], f_st, Z_st, sig_st, 
                    p0_dict=p0_t2, smoothness_weight=0.05  # <-- ADD THIS (Relaxed from 0.5)
                )
                if res2['status'] == 'success':
                    total_bic_type2 += res2['bic']
                    p0_t2 = res2['params']  
                    history_t2[temp] = res2['params']
                else:
                    failed_type2 = True
                    total_bic_type2 = np.inf
                    
        # ALWAYS append both results with the 'history' key, even if they failed
        results = []
        results.append({
            'circuit': c_string, 'type': 'Type 1', 'target': case['fhn_parallel_R'], 
            'global_bic': total_bic_type1, 'history': history_t1
        })
        results.append({
            'circuit': c_string, 'type': 'Type 2', 'target': case['fhn_series_R'], 
            'global_bic': total_bic_type2, 'history': history_t2
        })
            
        return results

    # 3. Execute the sweep in parallel and STREAM the results LIVE
    global_results = []
    print("\n" + "="*60)
    print(" LIVE THERMAL SWEEP FEED")
    print("="*60)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(global_worker, case) for case in fhn_cases]
        
        # as_completed() yields the results instantly as each thread finishes
        for future in concurrent.futures.as_completed(futures):
            res_list = future.result()
            global_results.extend(res_list)
            
            for res in res_list:
                # Only try to print the history if the run was successful AND history actually exists
                if res['global_bic'] != np.inf and len(res['history']) > 0:
                    print(f"\n✅ [LIVE] {res['circuit']} | {res['type']}")
                    print(f"   Global Score : {res['global_bic']:.4e}")
                    
                    temps = list(res['history'].keys())
                    t_high, t_low = temps[0], temps[-1]
                    
                    high_str = " | ".join([f"{k}: {v:.2e}" for k, v in res['history'][t_high].items()])
                    low_str  = " | ".join([f"{k}: {v:.2e}" for k, v in res['history'][t_low].items()])
                    
                    print(f"   Fit @ {t_high:>6.2f}K : {high_str}")
                    print(f"   Fit @ {t_low:>6.2f}K : {low_str}")
                else:
                    print(f"\n❌ [LIVE] {res['circuit']} | {res['type']}")
                    print("   -> Dropped: Failed to maintain a stable physical fit across all temperatures.")
            
    # 4. Sort and Display the Final Winners
    # Keep only successful fits, then sort by score
    valid_results = [r for r in global_results if r['global_bic'] != np.inf]
    valid_results.sort(key=lambda x: x['global_bic'])
    
    print(f"\n" + "="*60)
    print(f"--- TOP 3 GLOBAL CONSENSUS TOPOLOGIES ---")
    for i in range(min(3, len(valid_results))):
        best = valid_results[i]
        print(f"\n#{i+1}: {best['circuit']}  |  {best['type']} [{best['target']} < 0]")
        print(f"  Total Cumulative BIC : {best['global_bic']:.4e}")
        
    # --- Print the Full Parameter Evolution for the #1 Winner ---
    if valid_results:
        winner = valid_results[0]
        print(f"\n{'='*60}")
        print(f" FULL THERMAL PARAMETER EVOLUTION (Winner: {winner['circuit']})")
        print(f"{'='*60}")
        
        comps = list(winner['history'][list(winner['history'].keys())[0]].keys())
        header = f"{'Temp (K)':<10} | " + " | ".join([f"{c:<12}" for c in comps])
        print(header)
        print("-" * len(header))
        
        for temp, params in winner['history'].items():
            row_str = f"{temp:<10.2f} | " + " | ".join([f"{params[c]:<12.4e}" for c in comps])
            print(row_str)

        # ==========================================
        # VISUALIZE THE GLOBAL WINNER
        # ==========================================
        print(f"\nGenerating visual fits for the #1 Global Winner...")
        
        # Rebuild the mathematical model for the winning string
        Z_model, comp_names = build_circuit_function(winner['circuit'])
        
        # Grab High, Mid, and Low temperatures to prevent Matplotlib popup spam
        temps = list(winner['history'].keys())
            
        for temp in temps:
            # Get the saved parameters and original data for this specific temperature
            params = [winner['history'][temp][comp] for comp in comp_names]
            f_st, Z_st, _ = thermal_data[temp]
            
            # Calculate the mathematical fit
            Z_fit_st = Z_model(f_st, *params)
            
            # Unstack the arrays for plotting
            half_idx = len(f_st) // 2
            f_plot = f_st[:half_idx]
            Z_plot = Z_st[:half_idx] + 1j * Z_st[half_idx:]
            Z_fit_plot = Z_fit_st[:half_idx] + 1j * Z_fit_st[half_idx:]
            
            # Draw the 3-panel plot
            plot_eis_results(
                f_plot, 
                Z_plot, 
                Z_fit_plot, 
                f"Global Winner @ {temp:.2f}K | {winner['circuit']} | {winner['type']}"
            )
        # ==========================================
        # FEATURE 1: PARAMETER EVOLUTION (R, C, L vs T)
        # ==========================================
        print(f"\nGenerating Parameter Evolution Plots...")
        import matplotlib.cm as cm
        
        # Sort temperatures for plotting (cold to hot)
        plot_temps = sorted(list(winner['history'].keys()))
        
        fig_evol, axs_evol = plt.subplots(1, 3, figsize=(15, 5))
        
        # Plot Resistors (Using Symlog for the negative NDR component)
        for comp in comp_names:
            if comp.startswith('R'):
                vals = [winner['history'][t][comp] for t in plot_temps]
                axs_evol[0].plot(plot_temps, vals, 'o-', label=comp, markersize=5)
        
        axs_evol[0].set_yscale('symlog', linthresh=1e-1) # linthresh defines the linear region around zero
        axs_evol[0].set_title("Resistors vs Temperature")
        axs_evol[0].set_xlabel("Temperature [K]")
        axs_evol[0].set_ylabel(r"Resistance [$\Omega$]")
        axs_evol[0].grid(True, which='both', ls='--', alpha=0.5)
        axs_evol[0].legend()
        
        # Plot Capacitors (Standard Log)
        for comp in comp_names:
            if comp.startswith('C'):
                vals = [winner['history'][t][comp] for t in plot_temps]
                axs_evol[1].plot(plot_temps, vals, '^--', label=comp, markersize=5)
                
        axs_evol[1].set_yscale('log')
        axs_evol[1].set_title("Capacitors vs Temperature")
        axs_evol[1].set_xlabel("Temperature [K]")
        axs_evol[1].set_ylabel("Capacitance [F]")
        axs_evol[1].grid(True, which='both', ls='--', alpha=0.5)
        axs_evol[1].legend()
        
        # Plot Inductors (Standard Log)
        for comp in comp_names:
            if comp.startswith('L'):
                vals = [winner['history'][t][comp] for t in plot_temps]
                axs_evol[2].plot(plot_temps, vals, 's-.', label=comp, markersize=5)
                
        axs_evol[2].set_yscale('log')
        axs_evol[2].set_title("Inductors vs Temperature")
        axs_evol[2].set_xlabel("Temperature [K]")
        axs_evol[2].set_ylabel("Inductance [H]")
        axs_evol[2].grid(True, which='both', ls='--', alpha=0.5)
        axs_evol[2].legend()
        
        plt.tight_layout()
        plt.show()

        # ==========================================
        # FEATURE 2: GLOBAL NYQUIST OVERLAY
        # ==========================================
        print(f"Generating Global Nyquist Overlay...")
        
        fig_global, ax_global = plt.subplots(figsize=(10, 8))
        
        # Generate a colormap based on the number of temperatures (Cold = Blue, Hot = Red)
        colors = cm.coolwarm(np.linspace(0, 1, len(plot_temps)))
        
        for idx, temp in enumerate(plot_temps):
            color = colors[idx]
            
            # Get the data and calculate the fit
            f_st, Z_st, _ = thermal_data[temp]
            params = [winner['history'][temp][comp] for comp in comp_names]
            Z_fit_st = Z_model(f_st, *params)
            
            # Unstack arrays
            half_idx = len(f_st) // 2
            Z_plot = Z_st[:half_idx] + 1j * Z_st[half_idx:]
            Z_fit_plot = Z_fit_st[:half_idx] + 1j * Z_fit_st[half_idx:]
            
            # Scatter for raw data (faded), solid line for fit
            ax_global.plot(Z_plot.real, -Z_plot.imag, 'o', mfc='none', mec=color, alpha=0.3, markersize=4)
            ax_global.plot(Z_fit_plot.real, -Z_fit_plot.imag, '-', color=color, linewidth=2, label=f"{temp:.1f} K")
            
        #ax_global.set_aspect('equal', adjustable='datalim')
        ax_global.set_xlim(1.5, 4)
        ax_global.set_ylim(-2, 5)
        ax_global.set_title(f"Thermal Evolution Overlay: {winner['circuit']}", fontweight='bold')
        ax_global.set_xlabel(r"Re(Z) [$\Omega$]")
        ax_global.set_ylabel(r"-Im(Z) [$\Omega$]")
        ax_global.grid(True, ls='--', alpha=0.5)
        
        # Place legend outside the plot so it doesn't cover the arcs
        ax_global.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0., fontsize='small', ncol=2)
        
        plt.tight_layout()
        plt.show()
#%%
elif RUN_MODE == 'FHN_SWEEP':
    fhn_cases = generate_fhn_test_suite()
    print(f"\nInitiating Strict FHN Sweep across {len(fhn_cases)} parasitic combinations...")
    
    def fhn_worker(case):
        c_string = case['circuit']
        res1 = test_fhn_hypothesis(c_string, case['fhn_parallel_R'], f_stacked, Z_stacked, sigma_stacked)
        res2 = test_fhn_hypothesis(c_string, case['fhn_series_R'], f_stacked, Z_stacked, sigma_stacked)
        
        results = []
        if res1['status'] == 'success':
            res1.update({'circuit': c_string, 'type': 'Type 1 (Voltage-Controlled)', 'target': case['fhn_parallel_R']})
            results.append(res1)
        if res2['status'] == 'success':
            res2.update({'circuit': c_string, 'type': 'Type 2 (Recovery-Controlled)', 'target': case['fhn_series_R']})
            results.append(res2)
        return results

    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        for res_list in executor.map(fhn_worker, fhn_cases):
            all_results.extend(res_list)
            
    # --- THE SANITY CHECK SORTER ---
    def rank_by_physics(res):
        # Relaxed lower bound to 1e-5 to allow for highly accurate fits
        if res['error'] < 1e-5 or res['error'] > 1e3:
            return float('inf')
        return res['bic']

    all_results.sort(key=rank_by_physics)
    
    print(f"\n--- TOP 3 FHN HYPOTHESES ---")
    for i in range(min(3, len(all_results))):
        best = all_results[i]
        print(f"\n#{i+1}: {best['circuit']}  |  {best['type']} [{best['target']} < 0]")
        print(f"  BIC Score          : {best['bic']:.4e}")
        print(f"  Reduced Chi-Square : {best['error']:.4f}")
        print("  --- Parameters ---")
        for param, val in best['params'].items():
            print(f"     {param}: {val:.4e}")

    # ==========================================
    # PLOT THE #1 WINNER FROM THE SWEEP
    # ==========================================
        best = all_results[i]
        print(f"\nGenerating plot for the #{i} Winner: {best['circuit']}")
        
        # Rebuild the math model for the winner
        Z_model, comp_names = build_circuit_function(best['circuit'])
        popt = [best['params'][comp] for comp in comp_names]
        Z_fit_stacked = Z_model(f_stacked, *popt)
        
        # Unstack the data for plotting
        f_plot = f_stacked[:len(f_stacked)//2]
        Z_plot = Z_stacked[:len(f_plot)] + 1j * Z_stacked[len(f_plot):]
        Z_fit_plot = Z_fit_stacked[:len(f_plot)] + 1j * Z_fit_stacked[len(f_plot):]
        
        # Call the visualization function
        plot_eis_results(
            f_plot, 
            Z_plot, 
            Z_fit_plot, 
            f"FHN Winner: {best['circuit']} | {best['type']}"
        )

elif RUN_MODE == 'BLIND_SWEEP':
    circuit_list = [assign_component_numbers(c) for c in generate_smart_topologies() if filter_by_physics(assign_component_numbers(c))]
    print(f"\nStarting Blind Sweep across {len(circuit_list)} physics-filtered circuits...")
    
    t0 = time.time()
    worker_func = partial(evaluate_circuit_agnostic, f_stacked=f_stacked, Z_stacked=Z_stacked, sigma_stacked=sigma_stacked)
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(worker_func, circuit_list))
            
    successful = sorted([r for r in results if r['status'] == 'success'], key=lambda x: x['bic'])
    print(f"Sweep completed in {time.time() - t0:.2f} seconds.\n\n--- TOP 3 CIRCUITS ---")
    for i in range(min(3, len(successful))):
        best = successful[i]
        print(f"\n#{i+1}: {best['circuit']}\nBIC: {best['bic']:.4e} | Chi2: {best['error']:.4f}")

elif RUN_MODE == 'GLOBAL_CONSENSUS':
    print("\nScanning directories for thermal data...")
    base_dir = 'E:/trabajo/phd/phd/Iridatos/EI' 
    thermal_data = load_temperature_series(base_dir)
    
    fhn_cases = generate_fhn_test_suite()
    print(f"\nInitiating Global Consensus Sweep across {len(fhn_cases)} FHN topologies...")
    
    def global_worker(case):
        c_string = case['circuit']
        total_bic_type1, total_bic_type2 = 0, 0
        failed_type1, failed_type2 = False, False
        
        # Variables to hold the chaining state
        p0_t1, p0_t2 = None, None
        history_t1, history_t2 = {}, {}
        
        for temp, (f_st, Z_st, sig_st) in thermal_data.items():
            
            # --- Type 1 Test ---
            if not failed_type1:
                res1 = test_fhn_hypothesis(c_string, case['fhn_parallel_R'], f_st, Z_st, sig_st, p0_dict=p0_t1)
                if res1['status'] == 'success':
                    total_bic_type1 += res1['bic']
                    p0_t1 = res1['params']  # Pass parameters to the next temperature
                    history_t1[temp] = res1['params']
                else:
                    failed_type1 = True
                    total_bic_type1 = np.inf
                    
            # --- Type 2 Test ---
            if not failed_type2:
                res2 = test_fhn_hypothesis(c_string, case['fhn_series_R'], f_st, Z_st, sig_st, p0_dict=p0_t2)
                if res2['status'] == 'success':
                    total_bic_type2 += res2['bic']
                    p0_t2 = res2['params']  # Pass parameters to the next temperature
                    history_t2[temp] = res2['params']
                else:
                    failed_type2 = True
                    total_bic_type2 = np.inf
                    
        results = []
        if not failed_type1:
            results.append({'circuit': c_string, 'type': 'Type 1', 'target': case['fhn_parallel_R'], 'global_bic': total_bic_type1, 'history': history_t1})
        if not failed_type2:
            results.append({'circuit': c_string, 'type': 'Type 2', 'target': case['fhn_series_R'], 'global_bic': total_bic_type2, 'history': history_t2})
            
        return results

    global_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        for res_list in executor.map(global_worker, fhn_cases):
            global_results.extend(res_list)
            
    global_results.sort(key=lambda x: x['global_bic'])
    
    print(f"\n--- TOP 3 GLOBAL CONSENSUS TOPOLOGIES ---")
    for i in range(min(3, len(global_results))):
        best = global_results[i]
        print(f"\n#{i+1}: {best['circuit']}  |  {best['type']} [{best['target']} < 0]")
        print(f"  Total Cumulative BIC : {best['global_bic']:.4e}")
        
    # --- Print the Parameter Evolution for the #1 Winner ---
    if global_results:
        winner = global_results[0]
        print(f"\n{'='*60}")
        print(f" THERMAL PARAMETER EVOLUTION (Winner: {winner['circuit']})")
        print(f"{'='*60}")
        
        comps = list(winner['history'][list(winner['history'].keys())[0]].keys())
        header = f"{'Temp (K)':<10} | " + " | ".join([f"{c:<12}" for c in comps])
        print(header)
        print("-" * len(header))
        
        for temp, params in winner['history'].items():
            row_str = f"{temp:<10.2f} | " + " | ".join([f"{params[c]:<12.4e}" for c in comps])
            print(row_str)
# %%
