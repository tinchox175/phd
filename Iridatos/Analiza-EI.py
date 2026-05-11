#%%
from asyncio import exceptions

import numpy as np
from scipy.optimize import curve_fit
import os
import matplotlib.pyplot as plt
from natsort import natsorted
import csv
from impedance import preprocessing
from impedance.models.circuits import CustomCircuit
import re
import csv
%matplotlib inline
dire = 'E:/trabajo/phd/phd/Iridatos'
#os.chdir('E://tesis 3/tesisfisica/IVs/')
def get_files_with_path(folder):
    print(folder)
    return natsorted([os.path.join(folder, file) for file in os.listdir(folder) if os.path.isfile(os.path.join(folder, file))])
def list_folders_in_folder(folder_path):
    # List only directories in the given folder
    return natsorted([name for name in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, name))])
def build_bounds(circuit_string, custom_settings=None):
    custom_settings = custom_settings or {}
    
    # Extracts all R, C, or L followed by numbers (e.g., ['R1', 'R2', 'C1'])
    components = re.findall(r'[RCL]\d+', circuit_string)
    
    initial_guess, boundlow, boundhigh = [], [], []
    
    for comp in components:
        # Default: guess=1.0, low=0.0, high=np.inf
        # If the component is in custom_settings, it uses those values instead
        guess, low, high = custom_settings.get(comp, (1.0, 0.0, np.inf))
        
        initial_guess.append(guess)
        boundlow.append(low)
        boundhigh.append(high)
        
    return initial_guess, boundlow, boundhigh
#files = (list_folders_in_folder('E://tesis 3/tesisfisica/IVs/2011/ZdeW_1234_16-11-24/'))
#%%
with open('Parametros_ajustados_290K_100mVac.csv', mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['T', 'R1', 'C1'])
t = ['290']
l=34
import time
t0 = time.time()
for i in t:
    data = np.genfromtxt(f'{dire}/EI/2X3_1234_100mVac_T290.00K_1635_Offset_0.00_mV.txt', unpack=True, delimiter=',', skip_header=1)
    f = data[0][1:l]
    Z = data[1][1:l] - 1j*data[3][1:l]
    circuit = 'p(R1,L1)-p(R3,C1-R2)-p(R7,L7)'
    exceptions = {
    'R3': (300.0, 0, np.inf),
    'C1': (3.8e-4, 0, np.inf),
    'L1': (7e-4, 0, np.inf),
    'R1': (-1000.0, -np.inf, 0.0),
    'C3': (1e-9, -np.inf, np.inf),    # Just a custom initial guess for a capacitor
    'L7': (30, 0, np.inf),
    'R7': (0.0, -np.inf, np.inf)
                }
    guesses, lows, highs = build_bounds(circuit, exceptions)
    
    #initial_guess = [2000, 3e-9]
    circuit = CustomCircuit(circuit, initial_guess=guesses)
    circuit.fit(f, Z, 
                bounds=(lows,
                        highs))

    paramteres = circuit.parameters_
    initial_guess = circuit.parameters_
    with open('Parametros_ajustados.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([i] + list(paramteres))
    print(f'T = {i}K')
    circuit.plot(f_data=f, Z_data=Z, kind='nyquist')
    circuit.plot(f_data=f, Z_data=Z, kind='bode')
    print(circuit)
    # break
tf = time.time()
print(f'Tiempo total: {tf - t0:.2f} segundos')