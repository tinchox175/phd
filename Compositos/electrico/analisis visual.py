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

# %% 4. Spatial Smoothing, Sub-Pixel Frontier Tracking & Diagnostic Probing
from scipy.signal import savgol_filter

# --- Tracking Settings ---
bin_px = 1              # 1 or 2 px (avoids coarse staircase quantization)
smooth_sigma_um = 5.0   # Physical Gaussian smoothing width (µm)
method = "threshold"    # "threshold" (sub-pixel level crossing) or "gradient"
threshold_val = -14.0   # Used only if method == "threshold"

# --- Active-Pulse Probing Window ---
t0_probe = 2          # Pulse onset (s)
t_probe_min = 0.5       # Start of probing window (s) (must be > t0_probe for log)
t_probe_max = 41.0      # End of active current pulse (s)
vel_smooth_s = 1.5      # Savitzky-Golay smoothing window for dx/dt (s)

# 1. Optional fine binning & physical-scale smoothing along space (axis=1)
num_bins = kymo.shape[1] // bin_px
trim_len = num_bins * bin_px
binned_kymo = kymo[:, :trim_len].reshape(len(t_s), num_bins, bin_px).mean(axis=2)
x_bins_um = x_um[:trim_len].reshape(num_bins, bin_px).mean(axis=1)

sigma_bins = smooth_sigma_um / (bin_px * UM_PER_PX)
smoothed_kymo = gaussian_filter1d(binned_kymo, sigma=sigma_bins, axis=1)

# 2. Extract frontier position per frame
frontier_um = np.full(len(t_s), np.nan)
for i, profile in enumerate(smoothed_kymo):
    if method == "gradient":
        idx = np.argmax(np.abs(np.gradient(profile)))
        frontier_um[i] = x_bins_um[idx]
    elif method == "threshold":
        reacted = np.where(profile >= threshold_val)[0]
        if len(reacted) > 0:
            idx = reacted[-1]
            # Linear sub-pixel interpolation between idx and idx + 1
            if idx < len(profile) - 1:
                p0_val, p1_val = profile[idx], profile[idx + 1]
                frac = (threshold_val - p0_val) / (p1_val - p0_val) if p1_val != p0_val else 0.0
                frontier_um[i] = x_bins_um[idx] + frac * (x_bins_um[idx + 1] - x_bins_um[idx])
            else:
                frontier_um[i] = x_bins_um[idx]

# 3. Plot Kymograph & Full Trajectory
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))

ax1.imshow(
    smoothed_kymo,
    aspect="auto",
    origin="lower",
    cmap="coolwarm",
    extent=[x_bins_um[0], x_bins_um[-1], t_s[0], t_s[-1]],
)
ax1.plot(frontier_um, t_s, color="black", linewidth=1.8, label="Tracked Frontier")
ax1.set_xlabel("Position along strip (µm)")
ax1.set_ylabel("Time elapsed (s)")
ax1.set_title("Smoothed CIELAB Kymograph")
ax1.legend()

ax2.plot(t_s, frontier_um, color="crimson", linewidth=1.5)
ax2.axvspan(t_probe_min, t_probe_max, color="gold", alpha=0.2, label="Probing window")
ax2.set_xlabel("Time elapsed (s)")
ax2.set_ylabel("Frontier Position (µm)")
ax2.set_title("Reaction Front Trajectory")
ax2.legend()
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

# 4. Probing Plots (Active Pulse Phase)
valid = (~np.isnan(frontier_um)) & (t_s >= t_probe_min) & (t_s <= t_probe_max)
t_p, x_p = t_s[valid], frontier_um[valid]

if len(t_p) >= 5:
    dt = np.median(np.diff(t_p))
    win = max(5, int(vel_smooth_s / dt) | 1)  # Force odd window >= 5
    if win > len(x_p):
        win = max(5, (len(x_p) - 1) | 1)

    # Savitzky-Golay preserves boundary slopes better than Gaussian smoothing
    x_p_smooth = savgol_filter(x_p, window_length=win, polyorder=2)
    v_p = np.gradient(x_p_smooth, t_p)

    pos_dt = t_p > t0_probe
    pos_v = v_p > 0

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))

    # (a) Diffusion check: linear if x ~ sqrt(t - t0)
    axes[0, 0].plot(np.sqrt(t_p[pos_dt] - t0_probe), x_p[pos_dt], ".", ms=3, color="crimson")
    axes[0, 0].set_xlabel(rf"$\sqrt{{t - {t0_probe:.1f}}}$ ($\mathrm{{s}}^{{1/2}}$)")
    axes[0, 0].set_ylabel("x (µm)")
    axes[0, 0].set_title(r"Diffusion Check: $x$ vs $\sqrt{t - t_0}$")
    axes[0, 0].grid(True, alpha=0.3)

    # (b) Logarithmic / Elovich check: linear if x ~ ln(t - t0)
    axes[0, 1].plot(np.log(t_p[pos_dt] - t0_probe), x_p[pos_dt], ".", ms=3, color="navy")
    axes[0, 1].set_xlabel(rf"$\ln(t - {t0_probe:.1f})$")
    axes[0, 1].set_ylabel("x (µm)")
    axes[0, 1].set_title(r"Logarithmic Check: $x$ vs $\ln(t - t_0)$")
    axes[0, 1].grid(True, alpha=0.3)

    # (c) Phase portrait (linear): straight downward line => exponential saturation
    axes[1, 0].plot(x_p_smooth, v_p, "-", lw=1.5, color="darkgreen")
    axes[1, 0].axhline(0, color="gray", ls="--", lw=0.8)
    axes[1, 0].set_xlabel("Smoothed position x (µm)")
    axes[1, 0].set_ylabel("Velocity dx/dt (µm/s)")
    axes[1, 0].set_title(r"Phase Portrait (no $t_0$): $\dot{x}$ vs $x$")
    axes[1, 0].grid(True, alpha=0.3)

    # (d) Phase portrait (semi-log): straight downward line => Elovich (dx/dt ~ exp(-x/λ))
    axes[1, 1].plot(x_p_smooth[pos_v], v_p[pos_v], "-", lw=1.5, color="purple")
    axes[1, 1].set_yscale("log")
    axes[1, 1].set_xlabel("Smoothed position x (µm)")
    axes[1, 1].set_ylabel("Velocity dx/dt (µm/s, log)")
    axes[1, 1].set_title(r"Elovich Check (no $t_0$): $\log(\dot{x})$ vs $x$")
    axes[1, 1].grid(True, which="both", alpha=0.3)

    plt.tight_layout()
    plt.show()
else:
    print("Not enough valid frontier points in the probing window.")

# %% 5. Diffusion Model Fit: Frontier Position vs. Time
from scipy.optimize import curve_fit

# --- Fit Window & Onset Settings ---
t0 = 0.0          # Pulse or relaxation start time (s) (e.g., 0.0 or 41.55)
t_fit_min = 0   # Start of region to fit (s)
t_fit_max = 57.0  # End of region to fit (s) (use np.inf to fit until the end)

# --- Model Definition (edit or swap this function to test other laws) ---
def diffusion_model(t, x0, k):
    """Fickian front propagation: x(t) = x0 + k * sqrt(t - t0)"""
    return x0 + k * np.sqrt(t)

# Example alternative to tinker with (general power law):
def diffusion_model(t, x0, k, n):
    return x0 + k * np.maximum(t - t0, 0.0) ** n

# 1. Select valid points within the chosen time window
valid = (~np.isnan(frontier_um)) & (t_s >= t_fit_min) & (t_s <= t_fit_max)
t_fit = t_s[valid]
x_fit = frontier_um[valid]

# 2. Fit the model & compute parameter uncertainties
try:
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
except:
    p0 = [x_fit[0], 10.0, 0.5]  # Initial guess: [x0 (µm), k (µm / s^0.5), n]
    popt, pcov = curve_fit(diffusion_model, t_fit, x_fit, p0=p0)
    perr = np.sqrt(np.diag(pcov))

    x0_fit, k_fit, n_fit = popt
    x0_err, k_err, n_err = perr

    # Goodness of fit (R²) and characteristic diffusivity estimate (L² ~ 2 D t)
    x_pred = diffusion_model(t_fit, *popt)
    r2 = 1.0 - np.sum((x_fit - x_pred) ** 2) / np.sum((x_fit - np.mean(x_fit)) ** 2)
    D_umn_s = 0.5 * k_fit**n_fit
    D_cmn_s = D_umn_s * 1e-8

    print(f"x0   = {x0_fit:.2f} ± {x0_err:.2f} µm")
    print(f"k    = {k_fit:.3f} ± {k_err:.3f} µm / s^0.5")
    print(f"n    = {n_fit:.3f} ± {n_err:.3f}")
    print(f"D_eff ≈ {D_umn_s:.2f} µm²/s ({D_cmn_s:.2e} cm²/s)  [using k = sqrt(2 D)]")
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
    label=rf"Fit: {x0_fit:.1f} + {k_fit:.2f}$\sqrt{{t - {t0:.2f}}}$"
)
ax1.set_xlabel("Time elapsed (s)")
ax1.set_ylabel("Frontier Position (µm)")
ax1.set_title("Diffusion Front Fit")
ax1.legend()
ax1.grid(True, alpha=0.3)

# Right: Frontier vs. sqrt(t - t0) (should appear straight if purely diffusive)
ax2.plot(np.sqrt(t_fit - t0), x_fit, "o", color="crimson", markersize=4, label="Data")
ax2.plot(np.sqrt(t_smooth - t0), x_smooth, "-", color="black", linewidth=2, label=r"Linear $\sqrt{t}$ trend")
ax2.set_xlabel(rf"$\sqrt{{t - {t0:.2f}}}$" + r" ($s^{1/2}$)")
ax2.set_ylabel("Frontier Position (µm)")
ax2.set_title(r"Linearity Check in $\sqrt{t}$")
ax2.legend()
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

#%%# %% 6. POC: Per-Frame 1D Spatial Profile Fitting (erf Front Position + Width)
from scipy.optimize import curve_fit
from scipy.special import erf

# --- POC Window & Spatial Crop Settings ---
t_poc_min = 1.0        # Start fitting once front has visibly entered strip (s)
t_poc_max = 41.0       # End of active pulse (s)
n_samples = 360         # Number of frames to sample across [t_poc_min, t_poc_max]
x_fit_min = 60        # Spatial crop for fit (µm) — increase if left contact bleaches/turns back
x_fit_max = x_um[-1]   # Spatial crop end (µm)

def erf_front(x, s_left, s_right, xf, w):
    """
    Smooth step profile transitioning from s_left (x << xf) to s_right (x >> xf).
    xf = center of the front (µm), where the spatial gradient is steepest.
    w  = characteristic half-width of the front (µm); in pure 1D diffusion, w = sqrt(2 D t).
    """
    return s_right + 0.5 * (s_left - s_right) * (1.0 - erf((x - xf) / (np.sqrt(2.0) * w)))

# Select spatial mask and evenly spaced frames inside the active pulse
x_mask = (x_um >= x_fit_min) & (x_um <= x_fit_max)
x_sub = x_um[x_mask]

pulse_idx = np.where((t_s >= t_poc_min) & (t_s <= t_poc_max))[0]
sample_idx = pulse_idx[np.linspace(0, len(pulse_idx) - 1, n_samples, dtype=int)]

t_poc = t_s[sample_idx]
xf_poc = np.full(n_samples, np.nan)
w_poc = np.full(n_samples, np.nan)
s_left_poc = np.full(n_samples, np.nan)
s_right_poc = np.full(n_samples, np.nan)
r2_poc = np.full(n_samples, np.nan)
fitted_curves = {}  # Store a few snapshots for visual inspection

# Bounds: [s_left, s_right, xf (µm), w (µm)]
lower_bounds = [-128.0, -128.0, x_sub[0], 1.0]
upper_bounds = [ 128.0,  128.0, x_sub[-1], 0.5 * (x_sub[-1] - x_sub[0])]

# Initial guess from the first sampled frame
first_prof = kymo[sample_idx[0], x_mask]
init_xf = frontier_um[sample_idx[0]] if not np.isnan(frontier_um[sample_idx[0]]) else np.median(x_sub)
init_xf = np.clip(init_xf, x_sub[0] + 5.0, x_sub[-1] - 5.0)
p_curr = [np.mean(first_prof[:15]), np.mean(first_prof[-15:]), init_xf, 20.0]

snapshot_slots = set(np.linspace(0, n_samples - 1, 6, dtype=int))

for k, frame_i in enumerate(sample_idx):
    prof = kymo[frame_i, x_mask]
    try:
        popt, _ = curve_fit(
            erf_front, x_sub, prof,
            p0=p_curr,
            bounds=(lower_bounds, upper_bounds),
            maxfev=4000,
        )
        pred = erf_front(x_sub, *popt)
        ss_res = np.sum((prof - pred) ** 2)
        ss_tot = np.sum((prof - np.mean(prof)) ** 2)
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan

        # Accept fit and warm-start the next frame if the step fit is reasonable
        if r2 >= 0.65:
            s_left_poc[k], s_right_poc[k], xf_poc[k], w_poc[k] = popt
            r2_poc[k] = r2
            p_curr = popt  # Warm start: next frame starts from this solution
            if k in snapshot_slots:
                fitted_curves[k] = (t_s[frame_i], prof, pred, popt, r2)
    except RuntimeError:
        pass

# --- Visualization: 4-Panel Diagnostic ---
fig, axes = plt.subplots(2, 2, figsize=(12, 8.5))

# 1. Raw 1D spatial profiles + erf fits at 6 timestamps (sanity check!)
cmap = plt.cm.viridis(np.linspace(0.1, 0.95, max(len(fitted_curves), 1)))
for color, (k, (ts_val, prof, pred, popt, r2)) in zip(cmap, fitted_curves.items()):
    axes[0, 0].plot(x_sub, prof, ".", ms=2, alpha=0.35, color=color)
    axes[0, 0].plot(x_sub, pred, "-", lw=2, color=color, label=f"t={ts_val:.1f}s (R²={r2:.2f})")
axes[0, 0].set_xlabel("Position along strip (µm)")
axes[0, 0].set_ylabel(ch_label)
axes[0, 0].set_title("1. Spatial Snapshots & erf Fits (Shape Check)")
axes[0, 0].legend(fontsize=8)
axes[0, 0].grid(True, alpha=0.3)

# 2. Front center xf(t) compared directly against Cell 4's threshold frontier
axes[0, 1].plot(t_s[pulse_idx], frontier_um[pulse_idx], "-", alpha=0.45, color="crimson", label="Cell 4 (threshold)")
axes[0, 1].plot(t_poc, xf_poc, "o-", ms=4, lw=1.5, color="black", label="Cell 6 (erf center xf)")
axes[0, 1].set_xlabel("Time elapsed (s)")
axes[0, 1].set_ylabel("Front Position (µm)")
axes[0, 1].set_title("2. erf Front Position vs. Threshold Method")
axes[0, 1].legend()
axes[0, 1].grid(True, alpha=0.3)

# 3. Front width w(t) and w²(t) vs time (linear w² => Fickian broadening)
ax_w = axes[1, 0]
ax_w2 = ax_w.twinx()
l1 = ax_w.plot(t_poc, w_poc, "o-", ms=4, color="teal", label="Width w(t) [µm]")
l2 = ax_w2.plot(t_poc, w_poc**2, "s--", ms=3, alpha=0.7, color="darkorange", label="w²(t) [µm²]")
ax_w.set_xlabel("Time elapsed (s)")
ax_w.set_ylabel("Front Width w (µm)", color="teal")
ax_w2.set_ylabel("Squared Width w² (µm²)", color="darkorange")
ax_w.set_title(r"3. Front Broadening ($w^2 \propto 2Dt$ if diffusive)")
lines = l1 + l2
ax_w.legend(lines, [l.get_label() for l in lines], loc="upper left", fontsize=8)
ax_w.grid(True, alpha=0.3)

# 4. Baseline drift check: do the color plateaus shift during the pulse?
axes[1, 1].plot(t_poc, s_left_poc, "o-", ms=3, color="purple", label="s_left (behind front)")
axes[1, 1].plot(t_poc, s_right_poc, "o-", ms=3, color="green", label="s_right (ahead of front)")
axes[1, 1].axhline(threshold_val, color="crimson", ls="--", lw=1, label=f"Cell 4 threshold ({threshold_val})")
axes[1, 1].set_xlabel("Time elapsed (s)")
axes[1, 1].set_ylabel(ch_label)
axes[1, 1].set_title("4. Plateau Color Evolution (Baseline Drift Check)")
axes[1, 1].legend(fontsize=8)
axes[1, 1].grid(True, alpha=0.3)

plt.tight_layout()
plt.show()