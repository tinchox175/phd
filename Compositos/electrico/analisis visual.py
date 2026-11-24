# %% 1. Imports & Global Settings
import subprocess
import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector
from scipy.ndimage import gaussian_filter1d
from tqdm import tqdm

%matplotlib qt

VIDEO = "E:/trabajo/phd/phd/Compositos/electrico/Archivos/171126/3uAx60s relajacion.mkv"
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


# %% 3. Fast CIELAB Kymograph Extraction (Auto-FFmpeg + OpenCV Fallback)
import os
import shutil
import subprocess

start_s = 0          # Start time in video (s)
length_s = 660        # Duration to read (s)
channel = "a"        # "L" (lightness), "a" (green <-> magenta), or "b" (blue <-> yellow)
subtract_t0 = False  # True to plot color change relative to t = 0 (ΔL*, Δa*, Δb*)
use_blur = False     # True to apply 5x5 spatial Gaussian blur per frame

CHANNELS = {
    "L": (0, 0.0,   "CIELAB L* (0 Dark | 255 Bright)"),
    "a": (1, 128.0, "CIELAB a* (< 0 Green | > 0 Magenta)"),
    "b": (2, 128.0, "CIELAB b* (< 0 Blue | > 0 Yellow)"),
}
ch_idx, ch_offset, ch_label = CHANNELS[channel]

# Find ffmpeg in system PATH, or fall back to pip's imageio-ffmpeg binary
ffmpeg_exe = shutil.which("ffmpeg")
if ffmpeg_exe is None:
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        ffmpeg_exe = None

probe = cv2.VideoCapture(VIDEO)
fps = probe.get(cv2.CAP_PROP_FPS)
probe.release()

n_frames = int(length_s * fps)
profiles = []

if ffmpeg_exe is not None:
    w, h = x2 - x1, y2 - y1
    frame_bytes = w * h * 3
    cmd = [
        ffmpeg_exe,
        "-hwaccel", "auto",
        "-threads", "0",
        "-ss", str(start_s),
        "-t", str(length_s),
        "-i", VIDEO,
        "-vf", f"crop={w}:{h}:{x1}:{y1}",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-v", "error",
        "-",
    ]
    pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=frame_bytes * 16)
    for _ in tqdm(range(n_frames), desc="Reading frames (ffmpeg)"):
        raw = pipe.stdout.read(frame_bytes)
        if len(raw) < frame_bytes:
            break
        strip = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 3))
        img = cv2.GaussianBlur(strip, (5, 5), 0) if use_blur else strip
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        profiles.append(np.mean(lab[:, :, ch_idx] - ch_offset, axis=0))
    pipe.stdout.close()
    pipe.wait()
else:
    cap = cv2.VideoCapture(
        VIDEO,
        cv2.CAP_FFMPEG,
        [
            cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY,
            cv2.CAP_PROP_N_THREADS, os.cpu_count() or 4,
        ],
    )
    cap.set(cv2.CAP_PROP_POS_MSEC, start_s * 1000)
    for _ in tqdm(range(n_frames), desc="Reading frames (OpenCV)"):
        ok, frame = cap.read()
        if not ok:
            break
        strip = frame[y1:y2, x1:x2]
        img = cv2.GaussianBlur(strip, (5, 5), 0) if use_blur else strip
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        profiles.append(np.mean(lab[:, :, ch_idx] - ch_offset, axis=0))
    cap.release()

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
num_bins = 80           # Number of spatial bins along the strip
smooth_sigma = 2        # 1D Gaussian smoothing across bins
method = "threshold"    # "gradient" (steepest edge) or "threshold" (level crossing)
threshold_val = -14.0   # Used only if method == "threshold"

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
        # Last bin where channel value rises above threshold (flip to <= if tracking drop)
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

# %% 5. Diffusion Model Fit: Frontier Position vs. Time
from scipy.optimize import curve_fit

# --- Fit Window & Onset Settings ---
t0 = 0.0          # Pulse or relaxation start time (s) (e.g., 0.0 or 41.55)
t_fit_min = 0   # Start of region to fit (s)
t_fit_max = 41.0  # End of region to fit (s) (use np.inf to fit until the end)

# --- Model Definition (edit or swap this function to test other laws) ---
def diffusion_model(t, x0, k):
    """Fickian front propagation: x(t) = x0 + k * sqrt(t - t0)"""
    return  + k * np.sqrt(t)

# Example alternative to tinker with (general power law):
def diffusion_model(t, x0, k, n):
    return x0 + k * np.maximum(t - t0, 0.0) ** n

# 1. Select valid points within the chosen time window
valid = (~np.isnan(frontier_um)) & (t_s >= t_fit_min) & (t_s <= t_fit_max)
t_fit = t_s[valid]
x_fit = frontier_um[valid]

# 2. Fit the model & compute parameter uncertainties
p0 = [x_fit[0], 10.0]  # Initial guess: [x0 (µm), k (µm / s^0.5)]
popt, pcov = curve_fit(diffusion_model, t_fit, x_fit, p0=p0)
perr = np.sqrt(np.diag(pcov))

x0_fit, k_fit = popt
x0_err, k_err = perr

# Goodness of fit (R²) and characteristic diffusivity estimate (L² ~ 2 D t)
x_pred = diffusion_model(t_fit, *popt)
r2 = 1.0 - np.sum((x_fit - x_pred) ** 2) / np.sum((x_fit - np.mean(x_fit)) ** 2)
D_um2_s = 0.5 * k_fit**2
D_cm2_s = D_um2_s * 1e-8

print(f"x0   = {x0_fit:.2f} ± {x0_err:.2f} µm")
print(f"k    = {k_fit:.3f} ± {k_err:.3f} µm / s^0.5")
print(f"D_eff ≈ {D_um2_s:.2f} µm²/s ({D_cm2_s:.2e} cm²/s)  [using k = sqrt(2 D)]")
print(f"R²   = {r2:.4f}")

# 3. Plot Data, Fit, and Linearized sqrt(t - t0) Check
t_smooth = np.linspace(t_fit[0], t_fit[-1], 300)
x_smooth = diffusion_model(t_smooth, *popt)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))

# Left: Frontier vs. Time
ax1.plot(t_s, frontier_um, ".", color="lightgray", label="All frames")
ax1.plot(t_fit, x_fit, "o", color="crimson", markersize=4, label="Fitted window")
ax1.plot(
    t_smooth, x_smooth, "-", color="black", linewidth=2,
    label=f"Fit: {x0_fit:.1f} + {k_fit:.2f}√(t - {t0})  (R²={r2:.3f})"
)
ax1.set_xlabel("Time elapsed (s)")
ax1.set_ylabel("Frontier Position (µm)")
ax1.set_title("Diffusion Front Fit")
ax1.legend()
ax1.grid(True, alpha=0.3)

# Right: Frontier vs. sqrt(t - t0) (should appear straight if purely diffusive)
ax2.plot(np.sqrt(t_fit - t0), x_fit, "o", color="crimson", markersize=4, label="Data")
ax2.plot(np.sqrt(t_smooth - t0), x_smooth, "-", color="black", linewidth=2, label="Linear √t trend")
ax2.set_xlabel(rf"$\sqrt{{t - {t0:.2f}}} (s^{1/2})$")
ax2.set_ylabel("Frontier Position (µm)")
ax2.set_title(r"Linearity Check in $\sqrt{t}$")
ax2.legend()
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()