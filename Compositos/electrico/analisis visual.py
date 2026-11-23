# %% 1. Imports & Global Settings
import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector
from scipy.ndimage import gaussian_filter1d
from tqdm import tqdm

%matplotlib qt

VIDEO = "/home/martin/LBT/phd/Compositos/electrico/Archivos/171126/3uAx60s relajacion.mkv"
UM_PER_PX = 1.0  # Calibration: 1 px = 1 µm

# Strip coordinates (updated automatically in memory if you run Cell 2)
x1, x2 = 670, 1270  # Left and right contact edges (px)
y1, y2 = 500, 570   # Top and bottom of the strip (px)


# %% 2. Compressed Box Selector (run only when picking a new ROI)
cap = cv2.VideoCapture(VIDEO)
cap.set(cv2.CAP_PROP_POS_MSEC, 28 * 1000)
_, frame = cap.read()
cap.release()

def on_select(e1, e2):
    global x1, x2, y1, y2
    x1, x2 = sorted([int(e1.xdata), int(e2.xdata)])
    y1, y2 = sorted([int(e1.ydata), int(e2.ydata)])
    print(f"x1, x2 = {x1}, {x2}\ny1, y2 = {y1}, {y2}\n")

fig, ax = plt.subplots()
ax.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
ax.set_title("Drag box over strip, then close window")
selector = RectangleSelector(ax, on_select, interactive=True)
plt.show()


# %% 3. CIELAB Kymograph Extraction
start_s = 0          # Start time in video (s)
length_s = 80       # Duration to read (s)
channel = "a"        # "L" (lightness), "a" (green <-> magenta), or "b" (blue <-> yellow)
subtract_t0 = False  # True to plot color change relative to t = 0 (ΔL*, Δa*, Δb*)

CHANNELS = {
    "L": (0, 0.0,   "CIELAB L* (0 Dark | 255 Bright)"),
    "a": (1, 128.0, "CIELAB a* (< 0 Green | > 0 Magenta)"),
    "b": (2, 128.0, "CIELAB b* (< 0 Blue | > 0 Yellow)"),
}
ch_idx, ch_offset, ch_label = CHANNELS[channel]

cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS)
cap.set(cv2.CAP_PROP_POS_MSEC, start_s * 1000)

profiles = []
for _ in tqdm(range(int(length_s * fps)), desc="Reading frames"):
    ok, frame = cap.read()
    if not ok:
        break

    strip = frame[y1:y2, x1:x2]
    blurred = cv2.GaussianBlur(strip, (5, 5), 0)
    blurred = strip  # Use unblurred strip if you prefer
    lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB).astype(np.float32)

    signal_2d = lab[:, :, ch_idx] - ch_offset
    profiles.append(np.mean(signal_2d, axis=0))  # Collapse vertically -> 1D spatial profile

cap.release()

# Core arrays saved in memory for Cell 4 (and any future fits)
kymo = np.array(profiles)
if subtract_t0:
    kymo = kymo - kymo[0]
    ch_label = "Δ " + ch_label

x_um = np.arange(kymo.shape[1]) * UM_PER_PX
t_s = np.arange(kymo.shape[0]) / fps + start_s

fig, ax = plt.subplots(figsize=(8, 5))
im = ax.imshow(
    kymo,
    aspect="auto",
    origin="lower",
    cmap="coolwarm",
    extent=[x_um[0], x_um[-1], t_s[0], t_s[-1]],
)
ax.set_xlabel("Position along strip (µm)")
ax.set_ylabel("Time elapsed (s)")
ax.hlines(41.55, x_um[0], x_um[-1], color="black", linestyle="--", alpha=0.5)
fig.colorbar(im, ax=ax, label=ch_label)
plt.tight_layout()
plt.show()


# %% 4. Spatial Binning & Frontier Tracking (runs directly on `kymo`)
num_bins = 80          # Number of spatial bins along the strip
smooth_sigma = 1     # 1D Gaussian smoothing across bins
method = "threshold"    # "gradient" (steepest edge) or "threshold" (level crossing)
threshold_val = -19.0   # Used only if method == "threshold" (e.g., b* <= -5 for blue front)

# Bin both the kymograph columns and the spatial coordinate axis
trim_len = (kymo.shape[1] // num_bins) * num_bins
binned_kymo = kymo[:, :trim_len].reshape(len(t_s), num_bins, -1).mean(axis=2)
x_bins_um = x_um[:trim_len].reshape(num_bins, -1).mean(axis=1)

# Smooth along the spatial axis (axis=1) for every frame at once
smoothed_kymo = gaussian_filter1d(binned_kymo, sigma=smooth_sigma, axis=1)

frontier_um = np.full(len(t_s), np.nan)
for i, profile in enumerate(smoothed_kymo):
    if method == "gradient":
        # Inflection point where color changes fastest along the strip
        idx = np.argmax(np.abs(np.gradient(profile)))
        frontier_um[i] = x_bins_um[idx]
    elif method == "threshold":
        # Last bin where b* drops below threshold (use >= if tracking yellow)
        reacted = np.where(profile >= threshold_val)[0]
        if len(reacted) > 0:
            frontier_um[i] = x_bins_um[reacted[-1]]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

ax1.imshow(
    smoothed_kymo,
    aspect="auto",
    origin="lower",
    cmap="coolwarm",
    extent=[x_bins_um[0], x_bins_um[-1], t_s[0], t_s[-1]],
)
ax1.plot(frontier_um, t_s, color="black", linewidth=2, label="Tracked Frontier")
ax1.set_xlabel("Position along strip (µm)")
ax1.set_ylabel("Time elapsed (s)")
ax1.set_title("Binned CIELAB Kymograph")
ax1.legend()

ax2.plot(t_s, frontier_um, color="crimson", linewidth=1.5)
ax2.set_xlabel("Time elapsed (s)")
ax2.set_ylabel("Frontier Position (µm)")
ax2.set_title("Reaction Front Trajectory")
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()