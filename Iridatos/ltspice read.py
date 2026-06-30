import numpy as np
import matplotlib.pyplot as plt

# 1. Load the LTspice export
# LTspice exports AC data in the format: Freq, Re, Im
filename = 'Draft1.txt'
data = np.genfromtxt(filename, skip_header=1, delimiter='	', unpack=True, dtype=str)

f_sim = [float(freq) for freq in data[0]]  # Frequency in Hz
Re_Z = np.array([float(i.split(',')[0]) for i in data[1]])  # Real part of impedance
Im_Z = np.array([float(i.split(',')[1]) for i in data[1]])  # Imaginary part of impedance

# 2. Plot the perfect Nyquist curve
plt.figure(figsize=(6, 6))
plt.plot(Re_Z, -Im_Z, '-', color='blue', linewidth=2, label='LTspice Simulation')

# Force a 1:1 aspect ratio so semicircles are perfectly round
plt.gca().set_aspect('equal', adjustable='datalim')

plt.title("LTspice Nyquist Simulation", fontweight='bold')
plt.xlabel(r"Re(Z) [$\Omega$]")
plt.ylabel(r"-Im(Z) [$\Omega$]")
plt.grid(True, ls='--', alpha=0.5)
plt.legend()
plt.tight_layout()
plt.show()