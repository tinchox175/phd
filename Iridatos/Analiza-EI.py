#%%
import numpy as np
from scipy.optimize import curve_fit
import os
import matplotlib.pyplot as plt
from natsort import natsorted
import csv
from impedance import preprocessing
from impedance.models.circuits import CustomCircuit
import csv
%matplotlib inline
#dire = 'E://tesis 3/tesisfisica/IVs/2011/ZdeW_1234_16-11-24/'
#os.chdir('E://tesis 3/tesisfisica/IVs/')
def get_files_with_path(folder):
    print(folder)
    return natsorted([os.path.join(folder, file) for file in os.listdir(folder) if os.path.isfile(os.path.join(folder, file))])
def list_folders_in_folder(folder_path):
    # List only directories in the given folder
    return natsorted([name for name in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, name))])
#files = (list_folders_in_folder('E://tesis 3/tesisfisica/IVs/2011/ZdeW_1234_16-11-24/'))
#%%
with open('Parametros_ajustados_290K_100mVac.csv', mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['T', 'R1', 'C1'])
t = ['290']
initial_guess = [2000, 3e-9]
l=30
for i in t:
    data = np.genfromtxt(f'C:/LBT/Iridatos/EI/2X3_1234_100mVac_T290.00K_1635_Offset_0.00_mV.txt', unpack=True, delimiter=',', skip_header=1)
    f = data[0][1:l]
    Z = data[1][1:l] - 1j*data[3][1:l]
    circuit = 'p(R1-L1-C1,R2-C2,C3)'
    boundlow = []
    boundhigh = []
    initial_guess = []
    for i in circuit.split('-'):
        if ('p') in i:
            for j in i.split('(')[1].split(')')[0].split(','):
                if ('R2') in i:
                    initial_guess.append(-2000)
                    boundlow.append(-np.inf)
                    boundhigh.append(0)
                    continue
                if ('R') in j:
                    initial_guess.append(2000)
                elif ('C') in j:
                    initial_guess.append(3e-9)
                elif ('L') in j:
                    initial_guess.append(1e-3)
                boundlow.append(0)
                boundhigh.append(np.inf)    
            continue
        if ('R2') in i:
            initial_guess.append(-2000)
            boundlow.append(-np.inf)
            boundhigh.append(0)
            continue
        if ('R') in i:
            initial_guess.append(2000)
        elif ('C') in i:
            initial_guess.append(3e-9)
        elif ('L') in i:
            initial_guess.append(1e-3)
        boundlow.append(0)
        boundhigh.append(np.inf)
    #initial_guess = [2000, 3e-9]
    circuit = CustomCircuit(circuit, initial_guess=initial_guess)
    circuit.fit(f, Z, 
                bounds=(boundlow,
                        boundhigh))

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
