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
    Generates FHN cores embedded with an expanded suite of 
    physically rigorous solid-state and probe-station parasitics.
    """
    parasitic_blocks = [
        # --- TIER 1: Ideal & Trivial ---
        '',               # Perfect FHN core (No parasitics)
        'R',              # Pure contact resistance (e.g., silver paint/wire)
        'L',              # Pure stray wiring inductance
        'R-L',            # Standard resistive + inductive cable 
        
        # --- TIER 2: Single Interface (Schottky or Contact) ---
        'p(C,R)',         # Simple non-neural interface
        'p(L,R)',         # Damped high-frequency wiring (coaxial artifacts)
        'R-p(C,R)',       # Contact R + Interface RC
        'L-p(C,R)',       # Wiring L + Interface RC
        'R-p(L,R)',       # Contact R + Damped Wiring
        
        # --- TIER 3: Complex Probe & Cable Models ---
        'L-R-p(C,R)',     # Full Cable (R+L) + Interface RC
        'p(C,R)-p(L,R)',  # Interface RC + Damped Wiring
        
        # --- TIER 4: Multi-Interface (Bulk + Grain Boundaries + Contacts) ---
        'p(C,R)-p(C,R)',          # e.g., Contact RC + Bulk/Grain Boundary RC
        'R-p(C,R)-p(C,R)',        # Series R + Contact RC + Bulk RC
        'L-p(C,R)-p(C,R)',        # Wiring L + Contact RC + Bulk RC
        'L-R-p(C,R)-p(C,R)'       # The "Kitchen Sink" (Full probe + Dual Interface)
    ]
    
    test_cases = []
    
    for p_block in parasitic_blocks:
        # Build the raw string with the FHN block strictly at the end
        if p_block == '':
            raw_string = 'p(C,R,L-R)'
        else:
            raw_string = f"{p_block}-p(C,R,L-R)"
            
        numbered_circuit = assign_component_numbers(raw_string)
        
        # Find the FHN block at the absolute end of the string
        # This regex matches the exact p(C,R,L-R) structure and captures the numbered names
        match = re.search(r'p\((C\d+),(R\d+),(L\d+)-(R\d+)\)$', numbered_circuit)
        
        if match:
            test_cases.append({
                'circuit': numbered_circuit,
                'fhn_parallel_R': match.group(2), # Target for Type 1
                'fhn_series_R': match.group(4)    # Target for Type 2
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
                    guesses.append(-100.0); lows.append(-3000); highs.append(0.0)
                elif comp.startswith('R'):
                    guesses.append(100.0); lows.append(0.0); highs.append(5000)
                elif comp.startswith('C'):
                    guesses.append(1e-9); lows.append(0.0); highs.append(10)
                elif comp.startswith('L'):
                    guesses.append(0.1); lows.append(1e-10); highs.append(100)

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

def test_fhn_hypothesis(circuit_string, forced_neg_resistor, f_stacked, Z_stacked, sigma_stacked):
    """Forces a specific FHN resistor to be strictly negative."""
    Z_model, comp_names = build_circuit_function(circuit_string)
    guesses, lows, highs = [], [], []
    
    for comp in comp_names:
        if comp == forced_neg_resistor:
            guesses.append(-100.0); lows.append(-np.inf); highs.append(0.0)
        elif comp.startswith('R'):
            guesses.append(100.0); lows.append(0.0); highs.append(np.inf)
        elif comp.startswith('C'):
            guesses.append(1e-5); lows.append(0.0); highs.append(0.1)
        elif comp.startswith('L'):
            guesses.append(1); lows.append(0.0); highs.append(1000)

    try:
        popt, _ = curve_fit(Z_model, f_stacked, Z_stacked, p0=guesses, bounds=(lows, highs), sigma=sigma_stacked, absolute_sigma=True, maxfev=15000)
        chi2_val = np.sum(((Z_model(f_stacked, *popt) - Z_stacked) / sigma_stacked)**2)
        return {
            'status': 'success', 
            'error': chi2_val / (len(Z_stacked) - len(comp_names)), 
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
    
    ax_nyq.plot(Z.real, -Z.imag, 'o', color='black', markersize=6, mfc='none', label='Data')
    ax_nyq.plot(Z_fit.real, -Z_fit.imag, '-', color='red', linewidth=2, label='Fit')
    ax_nyq.set_aspect('equal', adjustable='datalim') 
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
#%%
import os
import glob

def load_temperature_series(base_directory, noise_floor=0.02):
    """
    Scans a directory (and subdirectories) for EIS text files.
    Extracts the temperature from the filename and builds a dictionary of stacked datasets.
    Assumes filenames contain a temperature string like 'T290.00K'.
    """
    thermal_data = {}
    
    # Search for all text files recursively in the base directory
    search_pattern = os.path.join(base_directory, '**', '*.txt')
    file_list = glob.glob(search_pattern, recursive=True)
    
    for filepath in file_list:
        # Use regex to find the temperature in the filename (e.g., T290.00K)
        temp_match = re.search(r'T(\d+\.\d+)K', filepath)
        if not temp_match:
            continue # Skip files that don't match the format
            
        temp_val = float(temp_match.group(1))
        
        # Load the data
        try:
            data = np.genfromtxt(filepath, unpack=True, delimiter=',', skip_header=1)
            l = min(500, len(data[0])) # Safeguard in case some files are shorter
            f = data[0][0:l]
            Z = data[1][0:l] + 1j*data[3][0:l]
            
            # Apply proportional error weighting
            sigma_real = data[2][1:l]
            sigma_imag = data[4][1:l]
            
            # Stack the arrays
            f_stacked = np.hstack([f, f])
            Z_stacked = np.hstack([Z.real, Z.imag])
            sigma_stacked = np.hstack([sigma_real, sigma_imag])
            
            thermal_data[temp_val] = (f_stacked, Z_stacked, sigma_stacked)
            
        except Exception as e:
            print(f"Skipped {filepath}: {e}")
            
    # Sort the dictionary keys so we evaluate from highest to lowest temp (or vice versa)
    sorted_thermal_data = {k: thermal_data[k] for k in sorted(thermal_data.keys(), reverse=True)}
    print(f"Successfully loaded {len(sorted_thermal_data)} temperature datasets.")
    
    return sorted_thermal_data

# # =============================================================================
# # 5. DATA LOADING
# # =============================================================================
# dire = r'E:\trabajo\tesis 3\tesisfisica\IVs\2011\ZdeW_1234_16-11-24'
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
RUN_MODE = 'FHN_SWEEP' 

if RUN_MODE == 'MANUAL':
    test_manual_circuit('R1-p(C1,R2)-p(C2,R3,L1-R4)', f_stacked, Z_stacked, sigma_stacked)
    
elif RUN_MODE == 'GLOBAL_CONSENSUS':
    # 1. Load the entire folder structure
    print("\nScanning directories for thermal data...")
    base_dir = 'E:/trabajo/phd/phd/Iridatos/EI' # <-- Point this to your main folder
    thermal_data = load_temperature_series(base_dir)
    
    # 2. Generate the topologies to test
    # (You can use either the FHN suite or the Blind suite here)
    fhn_cases = generate_fhn_test_suite()
    print(f"\nInitiating Global Consensus Sweep across {len(fhn_cases)} FHN topologies...")
    
    def global_worker(case):
        c_string = case['circuit']
        total_bic_type1 = 0
        total_bic_type2 = 0
        failed_type1 = False
        failed_type2 = False
        
        # Test the topology against EVERY temperature
        for temp, (f_st, Z_st, sig_st) in thermal_data.items():
            
            # Type 1 Test
            if not failed_type1:
                res1 = test_fhn_hypothesis(c_string, case['fhn_parallel_R'], f_st, Z_st, sig_st)
                if res1['status'] == 'success':
                    total_bic_type1 += res1['bic']
                else:
                    failed_type1 = True
                    total_bic_type1 = np.inf
                    
            # Type 2 Test
            if not failed_type2:
                res2 = test_fhn_hypothesis(c_string, case['fhn_series_R'], f_st, Z_st, sig_st)
                if res2['status'] == 'success':
                    total_bic_type2 += res2['bic']
                else:
                    failed_type2 = True
                    total_bic_type2 = np.inf
                    
        results = []
        if not failed_type1:
            results.append({'circuit': c_string, 'type': 'Type 1', 'target': case['fhn_parallel_R'], 'global_bic': total_bic_type1})
        if not failed_type2:
            results.append({'circuit': c_string, 'type': 'Type 2', 'target': case['fhn_series_R'], 'global_bic': total_bic_type2})
            
        return results

    # 3. Execute the sweep in parallel
    global_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        for res_list in executor.map(global_worker, fhn_cases):
            global_results.extend(res_list)
            
    # 4. Sort and Display Winners
    global_results.sort(key=lambda x: x['global_bic'])
    
    print(f"\n--- TOP 3 GLOBAL CONSENSUS TOPOLOGIES ---")
    for i in range(min(3, len(global_results))):
        best = global_results[i]
        print(f"\n#{i+1}: {best['circuit']}  |  {best['type']} [{best['target']} < 0]")
        print(f"  Total Cumulative BIC : {best['global_bic']:.4e}")

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
# %%
