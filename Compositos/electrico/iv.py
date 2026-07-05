#%%
%matplotlib inline
import pyvisa
import time
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, clear_output  # <-- REQUIRED FOR JUPYTER

# ==========================================
# 1. PARAMETERS & TIMING
# ==========================================
K224_ADDR = "GPIB0::02::INSTR"
A34420A_ADDR = "GPIB0::07::INSTR"


# Generate a unique timestamp for filenames (Format: YYYYMMDD_HHMMSS)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
csv_filename = f"par contactos 2{timestamp}.csv"
png_filename = f"par contactos 2{timestamp}.png"

# ==========================================
# 2. INSTRUMENT INITIALIZATION
# ==========================================
rm = pyvisa.ResourceManager()
source = rm.open_resource(K224_ADDR)
meter = rm.open_resource(A34420A_ADDR)

# Agilent 34420A Setup
meter.write("*RST")
meter.write("CONF:VOLT:DC")
meter.write(f"VOLT:DC:RANG 100")
meter.write("VOLT:DC:NPLC 10") 

# Keithley 224 Setup
source.write("F0X")   
source.write("V30X")  

# ==========================================
# 3. BUILD CLOSED-LOOP CURRENT ARRAY
# ==========================================

I_MAX_pos = 1e-6              # Maximum current magnitude in Amps (1 mA)
I_MAX_neg = 1e-6            # Maximum current magnitude in Amps (1 mA)
STEPS_PER_QUADRANT = 80   # Points per leg. Total loop will be ~76 points.

# The small, non-disturbing "lecture" current to measure Remanent R
I_READ = 1e-6

# Pulse Timing Configuration
PULSE_WIDTH = 0.5    
SETTLE_TIME = 0.15   
COOL_DOWN = 0.2      

p1 = np.linspace(0, I_MAX_pos, STEPS_PER_QUADRANT)
p2 = np.linspace(I_MAX_pos, 0, STEPS_PER_QUADRANT)[1:]
p3 = np.linspace(0, -I_MAX_neg, STEPS_PER_QUADRANT)[1:]
p4 = np.linspace(-I_MAX_neg, 0, STEPS_PER_QUADRANT)[1:]

write_currents_array = np.concatenate([p1, p2, p3, p4])
#%%
# ==========================================
# 4. LIVE PLOT INITIALIZATION
# ==========================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

line_iv, = ax1.plot([], [], marker='o', linestyle='-', color='black', markersize=4)
ax1.set_xlabel("Tensión (V)")
ax1.set_ylabel("Corriente (A)")
ax1.set_title("I-V Loop")
ax1.grid(True, which='both', linestyle='--', alpha=0.6)
ax1.axhline(0, color='black', linewidth=1)
ax1.axvline(0, color='black', linewidth=1)

# Plot 2: Resistance vs Write Current
line_r_inst, = ax2.plot([], [], marker='^', linestyle='-', color='blue', markersize=4, label='Instantaneous R')
line_r_rem, = ax2.plot([], [], marker='o', linestyle='-', color='red', markersize=4, label='Remanent R')
ax2.set_xlabel("Corriente Pulso (A)")
ax2.set_ylabel("Resistencia (Ohms)")
ax2.set_title("Resistencias")
ax2.set_yscale('log') # Log scale is usually best for resistive switching
ax2.grid(True, which='both', linestyle='--', alpha=0.6)
ax2.legend()

dh = display(fig, display_id=True)

# ==========================================
# 5. EXECUTE READ/WRITE SWEEP
# ==========================================
measured_i_write = [] 
measured_v_write = []
r_inst_list = []
r_rem_list = []

print(f"Starting Read/Write loop. Saving to: {csv_filename}")

for i_w in write_currents_array:
    # ----------------------------------------
    # PHASE A: THE WRITE PULSE
    # ----------------------------------------
    source.write(f"I{i_w:E}X")
    source.write("F1X")
    t_start_w = time.time()
    
    time.sleep(SETTLE_TIME)
    v_w_str = meter.query("READ?")
    v_w = float(v_w_str)
    
    # Calculate Instantaneous R (prevent divide-by-zero)
    r_inst = abs(v_w / i_w) if i_w != 0 else np.nan
    
    # Pad write pulse time
    t_elapsed_w = time.time() - t_start_w
    if t_elapsed_w < PULSE_WIDTH:
        time.sleep(PULSE_WIDTH - t_elapsed_w)
        
    source.write("F0X")
    time.sleep(COOL_DOWN)

    # ----------------------------------------
    # PHASE B: THE READ (LECTURE) PULSE
    # ----------------------------------------
    source.write(f"I{I_READ:E}X")
    source.write("F1X")
    t_start_r = time.time()
    
    time.sleep(SETTLE_TIME)
    v_r_str = meter.query("READ?")
    v_r = float(v_r_str)
    
    # Calculate Remanent R
    r_rem = abs(v_r / I_READ)
    
    # Pad read pulse time
    t_elapsed_r = time.time() - t_start_r
    if t_elapsed_r < PULSE_WIDTH:
        time.sleep(PULSE_WIDTH - t_elapsed_r)
        
    source.write("F0X")
    time.sleep(COOL_DOWN)

    # ----------------------------------------
    # DATA STORAGE & PLOT UPDATE
    # ----------------------------------------
    measured_i_write.append(i_w)
    measured_v_write.append(v_w)
    r_inst_list.append(r_inst)
    r_rem_list.append(r_rem)
    
    # Update IV Curve
    line_iv.set_xdata(measured_v_write)
    line_iv.set_ydata(measured_i_write)
    ax1.relim()            
    ax1.autoscale_view()   
    
    # Update Resistance Curves
    line_r_inst.set_xdata(measured_i_write)
    line_r_inst.set_ydata(r_inst_list)
    line_r_rem.set_xdata(measured_i_write)
    line_r_rem.set_ydata(r_rem_list)
    ax2.relim()
    ax2.autoscale_view()
    
    dh.update(fig)

print("Sweep complete.")
# ==========================================
# 6. SAVE DATA & CLEAN UP
# ==========================================
df = pd.DataFrame({
    "Write_Current_A": measured_i_write,
    "Write_Voltage_V": measured_v_write,
    "Inst_Resistance_Ohm": r_inst_list,
    "Rem_Resistance_Ohm": r_rem_list
})

df.to_csv(csv_filename, index=False)
print(f"Data saved to '{csv_filename}'")

plt.tight_layout()
plt.savefig(png_filename, dpi=300)
print(f"Plot saved to '{png_filename}'")

source.close()
meter.close()
rm.close()
#%%
data = np.loadtxt("PSS IV 2 2726.txt", delimiter='\t', skiprows=1, unpack=True)
v = data[2]
i = data[3]
plt.scatter(v,i)
plt.xlabel("Voltage (V)")
plt.ylabel("Current (mA)")
plt.grid(True)
plt.show()