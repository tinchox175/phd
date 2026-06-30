#%%
import numpy as np
import re
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import concurrent.futures
import time
import itertools
from functools import partial # <--- ADD THIS
from scipy.stats import chi2 as chi2_stat

def fit_saved_model(circuit_string, f, Z, sigma_real, sigma_imag):
    """
    Fits a single known circuit string and returns the parameters.
    No need to pre-stack the data; this function handles it.
    """
    print(f"\nFitting saved model: {circuit_string}")
    
    # Stack the arrays internally
    f_stacked = np.hstack([f, f])
    Z_stacked = np.hstack([Z.real, Z.imag])
    sigma_stacked = np.hstack([sigma_real, sigma_imag])
    
    # Run the agnostic evaluator
    result = evaluate_circuit_agnostic(circuit_string, f_stacked, Z_stacked, sigma_stacked)
    
    if result['status'] == 'success':
        print(f"  ✅ Success! (Reduced Chi2: {result['error']:.4f})")
        print("  --- Parameters ---")
        for param, val in result['params'].items():
            print(f"     {param}: {val:.4e}")
        return result['params']
    else:
        print(f"  ❌ Fit Failed: {result['status']}")
        return None

def generate_smart_topologies():
    # ==========================================
    # 1. Branch Level
    # ==========================================
    components = ['C', 'L', 'R']
    branches = []
    
    for i in range(1, 4):
        for combo in itertools.combinations(components, i):
            branches.append("-".join(combo)) 
            
    # ==========================================
    # 2. Block Level (Parallel Groups)
    # ==========================================
    blocks = ['C', 'L', 'R'] 
    
    for i in range(2, 4):
        for combo in itertools.combinations_with_replacement(branches, i):
            
            # 🛑 MATHEMATICAL REDUNDANCY CHECK 1:
            # You cannot have multiple pure resistors, capacitors, 
            # or inductors in parallel. p(R,R) is just a single R.
            if combo.count('R') > 1 or combo.count('C') > 1 or combo.count('L') > 1:
                continue
                
            blocks.append(f"p({','.join(combo)})")
                
    # ==========================================
    # 3. Circuit Level (Series Blocks)
    # ==========================================
    generic_circuits = []
    
    for i in range(1, 4):
        for combo in itertools.combinations_with_replacement(blocks, i):
            
            # 🛑 MATHEMATICAL REDUNDANCY CHECK 2:
            # You cannot have multiple pure components in series.
            # R - R is just a single R.
            if combo.count('R') > 1 or combo.count('C') > 1 or combo.count('L') > 1:
                continue
                
            generic_circuits.append("-".join(combo))
            
    return generic_circuits

def assign_component_numbers(generic_circuit):
    """
    Translates a generic string like 'p(C,R)-L-p(C,C-R)' 
    into an exact string like 'p(C1,R1)-L1-p(C2,C3-R2)'
    """
    counts = {'R': 1, 'C': 1, 'L': 1}
    
    def replacer(match):
        comp = match.group(0) # 'R', 'C', or 'L'
        num = counts[comp]
        counts[comp] += 1
        return f"{comp}{num}"
        
    # Finds exactly R, C, or L and replaces them dynamically
    return re.sub(r'[RCL]', replacer, generic_circuit)

# ==========================================
# 4. The DRT Physics Filter
# ==========================================
def filter_by_physics(circuit_string):
    """
    Uses the insights gained from the DRT analysis to ruthlessly 
    prune the 295,000 possibilities down to what is physically viable.
    """
    c_count = circuit_string.count('C')
    l_count = circuit_string.count('L')
    r_count = circuit_string.count('R')
    
    # DRT Insight 1: We saw exactly ONE inductive valley.
    # Circuits with 0 inductors are wrong. Circuits with 2+ are overfitting.
    if l_count > 2: 
       return False
        
    # DRT Insight 2: We saw exactly TWO capacitive peaks (one massive, one small).
    # We should strictly enforce exactly 2 capacitors.
    if c_count > 2: 
        return False
        
    # Physical Assumption: Every energy storage element (L or C) needs 
    # a resistor to define its time constant (tau = RC or L/R).
    # With 3 elements (2 C's, 1 L), we likely need at least 3 Resistors.
    if r_count < 3:
        return False
    
    return True

def calculate_drt_pure_math(f, Z, regularization_lambda=1e-3, padding_decades=1):
    omega = 2 * np.pi * f
    
    # 1. Pad the tau vector 
    tau_min = 1.0 / np.max(omega)
    tau_max = 1.0 / np.min(omega)
    tau = np.logspace(np.log10(tau_min) - padding_decades, 
                      np.log10(tau_max) + padding_decades, 
                      num=len(omega) * 2)
    
    # 2. Build the structural matrices
    omega_tau = omega[:, np.newaxis] * tau[np.newaxis, :]
    A_real = 1.0 / (1.0 + omega_tau**2)
    A_imag = -omega_tau / (1.0 + omega_tau**2)
    
    # Explicit R_inf column (1s for Real, 0s for Imag)
    R_col_real = np.ones((len(omega), 1))
    R_col_imag = np.zeros((len(omega), 1))
    
    # Explicit L_0 column (0s for Real, omega for Imag)
    L_col_real = np.zeros((len(omega), 1))
    L_col_imag = omega[:, np.newaxis]
    
    # Assemble the Full A matrix
    # Columns map to: [gamma_1, ..., gamma_N, R_inf, L_0]
    A_full_real = np.hstack((A_real, R_col_real, L_col_real))
    A_full_imag = np.hstack((A_imag, R_col_imag, L_col_imag))
    
    # Stack for the solver
    A_stacked = np.vstack((A_full_real, A_full_imag))
    Z_stacked = np.hstack((Z.real, Z.imag))
    
    # ---------------------------------------------------------
    # 3. The Magic: Custom Tikhonov Regularization
    # ---------------------------------------------------------
    num_params = A_stacked.shape[1]
    
    # Create an Identity matrix for the penalty
    Reg_Matrix = np.eye(num_params)
    
    # CRITICAL FIX: Do NOT penalize R_inf and L_0 (the last two columns)
    Reg_Matrix[-1, -1] = 0.0  # Zero penalty for Inductance
    Reg_Matrix[-2, -2] = 0.0  # Zero penalty for Series Resistance
    
    # Solve the Normal Equations: (A^T * A + lambda * Reg) * x = A^T * y
    ATA = A_stacked.T @ A_stacked
    ATZ = A_stacked.T @ Z_stacked
    
    # np.linalg.solve is incredibly fast and exact
    x = np.linalg.solve(ATA + regularization_lambda * Reg_Matrix, ATZ)
    
    # Unpack the results
    gamma = x[:-2]  # Everything except the last two
    R_inf = x[-2]   # The second to last
    L_0 = x[-1]     # The last one
    
    return tau, gamma, R_inf, L_0

# 1. The Parallel Math Function
def p(*args):
    """Calculates equivalent impedance of parallel branches."""
    # Double protection: prevents div-by-zero on the inside AND the outside
    return 1.0 / (sum(1.0 / (z + 1e-15) for z in args) + 1e-15)

# 2. The Circuit Translator
def build_circuit_function(circuit_string):
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
                
        # Catch internal math errors without crashing
        try:
            Z_complex = eval(eval_string, {"__builtins__": None}, local_env) * np.ones_like(omega)
        except ZeroDivisionError:
            Z_complex = np.ones_like(omega) * 1e10 # Artificial heavy penalty
        
        # CRITICAL FIX: Sanitize the output. 
        # If any NaNs or Infs made it through, convert them to massive numbers 
        # so SciPy rejects the guess instead of segfaulting.
        Z_real = np.nan_to_num(Z_complex.real, nan=1e10, posinf=1e10, neginf=-1e10)
        Z_imag = np.nan_to_num(Z_complex.imag, nan=1e10, posinf=1e10, neginf=-1e10)
        
        return np.hstack([Z_real, Z_imag])
        
    return Z_model_scipy, components

def evaluate_circuit_agnostic(circuit_string, f_stacked, Z_stacked, sigma_stacked):
    try:
        Z_model, comp_names = build_circuit_function(circuit_string)
        resistors = [comp for comp in comp_names if comp.startswith('R')]
        
        # --- THE COARSE TOURNAMENT ---
        # Variables to track the winner of Pass 1
        best_coarse_chi2 = np.inf
        winner_popt = None
        winner_lows = None
        winner_highs = None
        winner_candidate = None
        
        for neg_candidate in resistors:
            guesses, lows, highs = [], [], []
            
            for comp in comp_names:
                if comp == neg_candidate:
                    guesses.append(-100.0) 
                    lows.append(-3000)
                    highs.append(0.0)
                elif comp.startswith('R'):
                    guesses.append(1000.0)  
                    lows.append(0.0)
                    highs.append(5000)
                elif comp.startswith('C'):
                    guesses.append(1e-9)
                    lows.append(0.0)
                    highs.append(1)
                elif comp.startswith('L'):
                    guesses.append(10)
                    lows.append(0.0)
                    highs.append(100)

            # Pass 1: Cheap 100-iteration fit
            popt_coarse, _ = curve_fit(
                Z_model, f_stacked, Z_stacked, 
                p0=guesses, bounds=(lows, highs), 
                sigma=sigma_stacked, absolute_sigma=True, 
                maxfev=1000
            )
            
            # Judge the performance
            Z_fit_coarse = Z_model(f_stacked, *popt_coarse)
            dof = len(Z_stacked) - len(comp_names)
            chi2_coarse = np.sum(((Z_fit_coarse - Z_stacked) / sigma_stacked)**2) / dof
            
            # If this is the best coarse fit we've seen, crown it the current winner
            if chi2_coarse < best_coarse_chi2:
                best_coarse_chi2 = chi2_coarse
                winner_popt = popt_coarse
                winner_lows = lows
                winner_highs = highs
                winner_candidate = neg_candidate

        # --- THE DEEP FIT (Only for the Winner) ---
        # If even the winner is total garbage, kill the circuit early
        if best_coarse_chi2 > 1e4:
            return {'circuit': circuit_string, 'status': 'failed_pass_1', 'error': best_coarse_chi2}

        # Run the heavy 10,000-iteration fit ONCE
        popt_fine, _ = curve_fit(
            Z_model, f_stacked, Z_stacked, 
            p0=winner_popt, bounds=(winner_lows, winner_highs), 
            sigma=sigma_stacked, absolute_sigma=True,
            maxfev=10000 
        )
        
        # Calculate final stats
        Z_fit_fine = Z_model(f_stacked, *popt_fine)
        
        chi2_val = np.sum(((Z_fit_fine - Z_stacked) / sigma_stacked)**2)
        chi2_reduced = chi2_val / dof
        p_value = chi2_stat.sf(chi2_val, dof)
        
        # 💥 NEW: Calculate the Bayesian Information Criterion (BIC)
        n_data = len(Z_stacked)
        k_params = len(comp_names)
        bic = chi2_val + k_params * np.log(n_data)
        
        fitted_parameters = dict(zip(comp_names, popt_fine))
        
        return {
            'circuit': circuit_string, 
            'status': 'success', 
            'error': chi2_reduced, 
            'chi2_abs': chi2_val,
            'bic': bic,            # <--- Pass the penalty score out
            'k_params': k_params,  # <--- Track component count
            'p_value': p_value,
            'params': fitted_parameters,
            'negative_resistor_used': winner_candidate
        }

    except RuntimeError:
        return {'circuit': circuit_string, 'status': 'failed_to_converge', 'error': np.inf}
    except Exception as e:
        return {'circuit': circuit_string, 'status': f'error: {str(e)}', 'error': np.inf}

def simulate_fixed_circuit(circuit_string, fixed_params, f_stacked, Z_stacked, sigma_stacked):
    """
    Simulates and plots a circuit using exact values provided by the user, 
    bypassing the solver entirely.
    """
    print(f"\n" + "="*50)
    print(f" FIXED SIMULATION: {circuit_string}")
    print("="*50)

    # 1. Rebuild the math model
    Z_model, comp_names = build_circuit_function(circuit_string)

    # Ensure all required components are in the dictionary
    missing = [c for c in comp_names if c not in fixed_params]
    if missing:
        print(f"❌ Error: Your dictionary is missing values for: {missing}")
        return

    # Extract values in the exact order the mathematical model expects
    popt = [fixed_params[comp] for comp in comp_names]

    # 2. Calculate the fixed curve
    Z_fit_stacked = Z_model(f_stacked, *popt)

    # 3. Calculate Error Statistics
    dof = len(Z_stacked) - len(comp_names)
    chi2_val = np.sum(((Z_fit_stacked - Z_stacked) / sigma_stacked)**2)
    chi2_reduced = chi2_val / dof
    p_value = chi2_stat.sf(chi2_val, dof)

    print(f"  Reduced Chi-Square : {chi2_reduced:.4f}")
    print(f"  Absolute Chi-Square: {chi2_val:.4e}")
    print(f"  p-value            : {p_value:.4e}")
    
    # ==========================================
    # 4. GENERATE THE 3-PANEL PLOT
    # ==========================================
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    # Unstack data for plotting
    f = f_stacked[:len(f_stacked)//2]
    Z = Z_stacked[:len(f)] + 1j * Z_stacked[len(f):]
    Z_fit = Z_fit_stacked[:len(f)] + 1j * Z_fit_stacked[len(f):]

    fig = plt.figure(figsize=(12, 5))
    gs = GridSpec(2, 3, figure=fig)
    
    ax_real = fig.add_subplot(gs[0, 0])
    ax_imag = fig.add_subplot(gs[1, 0], sharex=ax_real)
    ax_nyq = fig.add_subplot(gs[:, 1:])
    
    # Top Left: Real vs Freq
    ax_real.semilogx(f, Z.real, 'o', color='black', markersize=5, mfc='none', label='Data')
    ax_real.semilogx(f, Z_fit.real, '-', color='blue', linewidth=2, label='Simulation')
    ax_real.set_ylabel(r"Re(Z) [$\Omega$]")
    ax_real.grid(True, which='both', ls='--', alpha=0.5)
    ax_real.legend(loc='best')
    plt.setp(ax_real.get_xticklabels(), visible=False)
    
    # Bottom Left: Imag vs Freq
    ax_imag.semilogx(f, -Z.imag, 'o', color='black', markersize=5, mfc='none')
    ax_imag.semilogx(f, -Z_fit.imag, '-', color='blue', linewidth=2)
    ax_imag.set_xlabel("Frequency [Hz]")
    ax_imag.set_ylabel(r"-Im(Z) [$\Omega$]")
    ax_imag.grid(True, which='both', ls='--', alpha=0.5)
    
    # Right: Nyquist
    ax_nyq.plot(Z.real, -Z.imag, 'o', color='black', markersize=6, mfc='none', label='Data')
    ax_nyq.plot(Z_fit.real, -Z_fit.imag, '-', color='blue', linewidth=2, label='Simulation')
    ax_nyq.set_aspect('equal', adjustable='datalim') 
    ax_nyq.set_title(f"Fixed Sim: {circuit_string}", fontweight='bold')
    ax_nyq.set_xlabel(r"Re(Z) [$\Omega$]")
    ax_nyq.set_ylabel(r"-Im(Z) [$\Omega$]")
    ax_nyq.grid(True, ls='--', alpha=0.5)
    ax_nyq.legend(loc='best')
    
    plt.tight_layout()
    plt.show()

def test_manual_circuit(circuit_string, f_stacked, Z_stacked, sigma_stacked):
    """
    Manually tests a single circuit string, prints the statistics, 
    and generates a 3-panel plot if successful.
    """
    print(f"\n" + "="*50)
    print(f" MANUAL TEST: {circuit_string}")
    print("="*50)
    
    # 💥 FIXED: Now calling the Agnostic engine and dropping the exceptions argument
    result = evaluate_circuit_agnostic(circuit_string, f_stacked, Z_stacked, sigma_stacked)
    
    if result['status'] != 'success':
        print(f"\n❌ Fit Failed.")
        print(f"Reason: {result['status']}")
        if result['error'] != np.inf:
            print(f"Error value at failure: {result['error']:.4e}")
        return
        
    # 2. Print the final statistics and parameters
    print(f"\n✅ Fit Successful!")
    print(f"  Components (k)     : {result['k_params']}")
    print(f"  BIC Score          : {result['bic']:.4e}")
    print(f"  Reduced Chi-Square : {result['error']:.4f}")
    print(f"  Absolute Chi-Square: {result['chi2_abs']:.4e}")
    print(f"  p-value            : {result['p_value']:.4e}")
    print("\n  --- Optimized Parameters ---")
    for param, val in result['params'].items():
        print(f"     {param}: {val:.4e}")
        
    # ==========================================
    # 3. GENERATE THE 3-PANEL PLOT
    # ==========================================
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    # Unstack the original data for plotting
    f = f_stacked[:len(f_stacked)//2]
    Z = Z_stacked[:len(f)] + 1j * Z_stacked[len(f):]
    
    # Rebuild the mathematical model to generate the fitted curve
    Z_model, comp_names = build_circuit_function(circuit_string)
    popt = [result['params'][comp] for comp in comp_names]
    Z_fit_stacked = Z_model(f_stacked, *popt)
    Z_fit = Z_fit_stacked[:len(f)] + 1j * Z_fit_stacked[len(f):]
    
    # Setup the layout
    fig = plt.figure(figsize=(12, 5))
    gs = GridSpec(2, 3, figure=fig)
    
    ax_real = fig.add_subplot(gs[0, 0])
    ax_imag = fig.add_subplot(gs[1, 0], sharex=ax_real)
    ax_nyq = fig.add_subplot(gs[:, 1:])
    
    # Top Left: Real vs Freq
    ax_real.semilogx(f, Z.real, 'o', color='black', markersize=5, mfc='none', label='Data')
    ax_real.semilogx(f, Z_fit.real, '-', color='red', linewidth=2, label='Fit')
    ax_real.set_ylabel(r"Re(Z) [$\Omega$]")
    ax_real.grid(True, which='both', ls='--', alpha=0.5)
    ax_real.legend(loc='best')
    plt.setp(ax_real.get_xticklabels(), visible=False)
    
    # Bottom Left: Imag vs Freq
    ax_imag.semilogx(f, -Z.imag, 'o', color='black', markersize=5, mfc='none')
    ax_imag.semilogx(f, -Z_fit.imag, '-', color='red', linewidth=2)
    ax_imag.set_xlabel("Frequency [Hz]")
    ax_imag.set_ylabel(r"-Im(Z) [$\Omega$]")
    ax_imag.grid(True, which='both', ls='--', alpha=0.5)
    
    # Right: Nyquist
    ax_nyq.plot(Z.real, -Z.imag, 'o', color='black', markersize=6, mfc='none', label='Data')
    ax_nyq.plot(Z_fit.real, -Z_fit.imag, '-', color='red', linewidth=2, label='Fit')
    ax_nyq.set_aspect('equal', adjustable='datalim') 
    ax_nyq.set_title(f"Manual Fit: {circuit_string}", fontweight='bold')
    ax_nyq.set_xlabel(r"Re(Z) [$\Omega$]")
    ax_nyq.set_ylabel(r"-Im(Z) [$\Omega$]")
    ax_nyq.grid(True, ls='--', alpha=0.5)
    ax_nyq.legend(loc='best')
    
    plt.tight_layout()
    plt.show()

#%%
dire = 'E:/trabajo/phd/phd/Iridatos'
dire = '/home/martin/LBT/phd/Iridatos'
data = np.genfromtxt(f'{dire}/EI/2X3_1234_100mVac_T290.00K_1635_Offset_0.00_mV.txt', unpack=True, delimiter=',', skip_header=1)

l = 500
f = data[0][0:l]
Z = data[1][0:l] + 1j*data[3][0:l]

# Error limits setup
sigma_real = np.concatenate([np.ones_like(f[0:5]) * 1, np.ones_like(f[5:10]) * 6, np.ones_like(f[10:500]) * 6])  
sigma_imag = sigma_real.copy() 

sigma_real = np.where(sigma_real <= 0, 1, sigma_real)
sigma_imag = np.where(sigma_imag <= 0, 1, sigma_imag)

# Stack the arrays for SciPy
f_stacked = np.hstack([f, f])
Z_stacked = np.hstack([Z.real, Z.imag])
sigma_stacked = np.hstack([sigma_real, sigma_imag])

# (Assuming your f, Z, and sigma arrays are already loaded and stacked)

RUN_FIXED_SIMULATION = True

if RUN_FIXED_SIMULATION:
    target_circuit = 'p(L1,R1)-p(L2,C1-R2)-p(R3,C2-R4)'
    
    # Paste your saved values here
    saved_values = {
       'R1': -4.99e2,
       'C1': 0.9-6,
       'L1': 11.1e1,
       'R2': 4.16e2,
       'C2': 4.28e-8,
       'R3': 5.01e2,
       'R4': 7.8e-1,
       'L2': 9.74e-3
    }
    
    simulate_fixed_circuit(target_circuit, saved_values, f_stacked, Z_stacked, sigma_stacked)
else:
    RUN_MANUAL_TEST = True
#%%
if RUN_MANUAL_TEST:
    target_circuit = 'p(L1,R1)-p(L2,C1-R2)-p(R3,C2-R4)'
    test_manual_circuit(target_circuit, f_stacked, Z_stacked, sigma_stacked)
    
else:
    print("Generating mathematically unique generic topologies...")
    all_generics = generate_smart_topologies()
    
    print("Numbering components and applying DRT Physics Filter...")
    circuit_list = []
    for generic in all_generics:
        numbered_circuit = assign_component_numbers(generic)
        if filter_by_physics(numbered_circuit):
            circuit_list.append(numbered_circuit)
            
    print(f"Sweep space successfully reduced to {len(circuit_list)} highly-probable circuits.\n")

    print(f"Starting parallel sweep across {len(circuit_list)} circuits...")
    t0 = time.time()
    
    results = []
    worker_func = partial(
        evaluate_circuit_agnostic, 
        f_stacked=f_stacked, 
        Z_stacked=Z_stacked, 
        sigma_stacked=sigma_stacked,
    )
    
    # 💥 CHANGED TO THREADS 💥 
    # This completely bypasses the Windows multiprocessing crash in Jupyter
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = executor.map(worker_func, circuit_list)
        for res in futures:
            results.append(res)
            
    tf = time.time()
    print(f"\nSweep completed in {tf - t0:.2f} seconds.")
    
    # Sort strictly by the BIC score
    successful_fits = [r for r in results if r['status'] == 'success']
    successful_fits.sort(key=lambda x: x['bic'])
    
    print(f"\n--- TOP 3 CIRCUITS OUT OF {len(successful_fits)} SUCCESSFUL FITS ---")
    for i in range(min(3, len(successful_fits))):
        best = successful_fits[i]
        print(f"\n#{i+1}: {best['circuit']}")
        print(f"  Components (k)     : {best['k_params']}")
        print(f"  BIC Score          : {best['bic']:.4e}")
        print(f"  Reduced Chi-Square : {best['error']:.4f}")
        for param, val in best['params'].items():
            print(f"     {param}: {val:.4e}")
# %%
