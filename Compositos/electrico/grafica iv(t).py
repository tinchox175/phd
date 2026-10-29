import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

FILE = "/home/martin/LBT/phd/Compositos/electrico/Archivos/191026/PSS Noleti deriva.csv"
# --- choose columns here ---
X  = "Tiempo (min)"       # use "I pulso (mA)" etc. to plot against something else
Y1 = "Rrem 2 (Ohm)"      # left axis
Y2 = "Rrem 1 (Ohm)"      # right axis
Y3 = "I pulso (mA)"      # left axis


df = pd.read_csv(FILE)
#df["Tiempo (s)"] = df["Tiempo (min)"] * 60   # min -> s
df["I pulso (uA)"] = df["I pulso (mA)"]*1000  # make current positive
Y3 = "I pulso (uA)"  # left axis

fig, ax1 = plt.subplots(figsize=(8, 5))
ax2 = ax1.twinx()  # shares the same x axis, second y axis on the right

ax1.plot(df[X], df[Y1], color="#223647", label="Rrem 2W")
ax2.plot(df[X], df[Y2], color="#B54D4D", label="Rrem 3W")

ax1.set_xlabel(X)
ax1.set_ylabel("Rrem 2W", color="#223647")
ax2.set_ylabel("Rrem 3W", color="#B54D4D")
ax1.tick_params(axis="y", colors="#223647")
ax2.tick_params(axis="y", colors="#B54D4D")
ax1.grid(alpha=0.3)
ax1.legend(frameon=False)
ax2.legend(frameon=False, loc=(-0,0.86))

fig, ax1 = plt.subplots(figsize=(8, 5))
ax2 = ax1.twinx()  # shares the same x axis, second y axis on the right

ax1.plot(df[Y3], df[Y1], color="#223647", label="Rrem 2W")
ax2.plot(df[Y3], df[Y2], color="#B54D4D", label="Rrem 3W")

ax1.set_xlabel(Y3)
ax1.set_ylabel("Rrem 2W", color="#223647")
ax2.set_ylabel("Rrem 3W", color="#B54D4D")
ax1.tick_params(axis="y", colors="#223647")
ax2.tick_params(axis="y", colors="#B54D4D")
ax1.grid(alpha=0.3)
ax1.legend(frameon=False)
ax2.legend(frameon=False, loc=(0.8,0.86))

fig.tight_layout()
plt.show()