#%%
import pyvisa
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ==========================================
# 1. PARAMETERS & GPIB ADDRESSES
# ==========================================
K224_ADDR = "GPIB0::02::INSTR"    # Keithley 224 Current Source
A34420A_ADDR = "GPIB0::07::INSTR" # Agilent 34420A Nanovoltmeter

START_I = -1e-3  # Starting current in Amps (-1 mA)
STOP_I = 1e-3    # Stopping current in Amps (1 mA)
STEPS = 50       # Number of sweep points
DELAY = 0.5      # Settling time (seconds) between stepping and measuring

# ==========================================
# 2. INSTRUMENT INITIALIZATION
# ==========================================
rm = pyvisa.ResourceManager()
source = rm.open_resource(K224_ADDR)
meter = rm.open_resource(A34420A_ADDR)

# Agilent 34420A (Standard SCPI syntax)
meter.write("*RST")
meter.write("CONF:VOLT:DC")

# Keithley 224 (Pre-SCPI syntax requires 'X' as an execute command)
source.write("F0X")   # F0 = Output OFF (Standby)
source.write("V10X")  # V10 = Set voltage compliance limit to 10V (adjust as needed)
#%%
# ==========================================
# 3. EXECUTE SWEEP
# ==========================================
currents = np.linspace(START_I, STOP_I, STEPS)
voltages = []

print(f"Starting sweep from {START_I} A to {STOP_I} A...")
source.write("F1X")   # F1 = Output ON (Operate)

for i in currents:
    # Set current on K224: Requires scientific notation string ending in 'X'
    # e.g., 1mA becomes "I1.000000E-03X"
    source.write(f"I{i:E}X")
    
    # Wait for the sample to settle and the meter to integrate
    time.sleep(DELAY)
    
    # Trigger measurement and read from Agilent
    v_str = meter.query("READ?")
    voltages.append(float(v_str))

# Turn off the source output immediately after the sweep
source.write("F0X")
print("Sweep complete.")

# ==========================================
# 4. SAVE & PLOT DATA
# ==========================================
# Store in a Pandas DataFrame for easy CSV saving
df = pd.DataFrame({
    "Current_A": currents,
    "Voltage_V": voltages
})

df.to_csv("iv_curve_data.csv", index=False)
print("Data saved to 'iv_curve_data.csv'")

# Generate plot (Standard V on X-axis, I on Y-axis)
plt.figure(figsize=(8, 6))
plt.plot(df["Voltage_V"], df["Current_A"], marker='o', linestyle='-', color='black', markersize=4)

plt.xlabel("Voltage (V)")
plt.ylabel("Current (A)")
plt.title("I-V Characterization")
plt.grid(True, which='both', linestyle='--', alpha=0.6)
plt.axhline(0, color='black', linewidth=1)
plt.axvline(0, color='black', linewidth=1)
plt.tight_layout()

# Save the figure locally
plt.savefig("iv_curve_plot.png", dpi=300)
print("Plot saved to 'iv_curve_plot.png'")

plt.show()

# ==========================================
# 5. CLEAN UP
# ==========================================
#%%
source.close()
meter.close()
rm.close()