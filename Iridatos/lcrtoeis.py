import numpy as np
import matplotlib.pyplot as plt
import os

path = r'E:\trabajo\phd\phd\Iridatos\EI'
archivo_actual = path+r'\2X3_1234_100mVac_T290.00K_1635_Offset_0.00_mV.txt'
print(archivo_actual)
data = np.genfromtxt(archivo_actual, delimiter=',', skip_header=1, unpack=True)
f = data[0] #frecuencia
zreal = data[1] #lectura promedio A (Z real)
SD_A = data[2] #sigma A
zimag = -data[3] #lectura promedio B (Z img)
SD_B = data[4] #sigma B
Amp = data[5] #amplitud
output = open((archivo_actual.split('_')[-2])+'mV_eis.', 'w')
output.write(str(len(f)) + '\n' )
for i in np.arange(len(f)):
    output.write(f'{zreal[i]} {zimag[i]} {f[i]}\n')
output.close()
