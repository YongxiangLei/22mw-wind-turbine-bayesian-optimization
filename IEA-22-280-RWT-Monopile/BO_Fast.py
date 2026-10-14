import numpy as np
from scipy.interpolate import interp1d
from bayes_opt import BayesianOptimization
# from ROSCO_toolbox import write_discon
import subprocess
from pyFAST import postprocessing

# Original Kp and Ki values from DISCON.IN
kp_orig = np.array([
    -1.046190, -0.901036, -0.805977, -0.745262, -0.707832, -0.685800, -0.673301, 
    -0.665799, -0.659669, -0.651931, -0.640095, -0.622062, -0.596078, -0.560710, 
    -0.520237, -0.499699, -0.494331, -0.494887, -0.493553, -0.484701, -0.465216, 
    -0.434503, -0.394232, -0.347893, -0.300193, -0.256331, -0.221173, -0.198046, 
    -0.179791, -0.162502
])

ki_orig = np.array([
    -0.051508, -0.046341, -0.042337, -0.039171, -0.036619, -0.034521, -0.032760, 
    -0.031248, -0.029915, -0.028710, -0.027588, -0.026516, -0.025465, -0.024411, 
    -0.023691, -0.025004, -0.028299, -0.033386, -0.040099, -0.048202, -0.057342, 
    -0.067030, -0.076649, -0.085483, -0.092760, -0.097707, -0.099618, -0.098022, 
    -0.095359, -0.092836
])

pitch_angles = np.array([
    0.087533, 0.113396, 0.133855, 0.151322, 0.166895, 0.181166, 0.194493, 
    0.206974, 0.218758, 0.230122, 0.240990, 0.251436, 0.261678, 0.271430, 
    0.281074, 0.290366, 0.299532, 0.308435, 0.317215, 0.325775, 0.334240, 
    0.342494, 0.350699, 0.358678, 0.366667, 0.374396, 0.382139, 0.389697, 
    0.397208, 0.404630
])

# Parse from DISCON.IN to ensure consistency
def parse_discon_arrays():
    with open("IEA-22-280-RWT_DISCON.IN", "r") as f:
        lines = f.readlines()
    
    # Find PS_WindSpeeds and PS_BldPitchMin
    for i, line in enumerate(lines):
        if "PS_WindSpeeds" in line and not line.startswith('!'):
            ws_line = line.split('!')[0].strip()
            wind_speeds = np.array([float(x) for x in ws_line.split()])
        elif "PS_BldPitchMin" in line and not line.startswith('!'):
            bp_line = line.split('!')[0].strip()
            min_pitch = np.array([float(x) for x in bp_line.split()])
    
    # Handle length mismatch
    n = min(len(wind_speeds), len(min_pitch))
    return wind_speeds[:n], min_pitch[:n]

wind_speeds, min_pitch = parse_discon_arrays()
print(f"Parsed arrays: wind_speeds={len(wind_speeds)}, min_pitch={len(min_pitch)}")

# Find pitch angle at rated wind speed (11.4 m/s)
pitch_at_rated = interp1d(wind_speeds, min_pitch, kind='linear')(11.4)
print(f"Pitch at rated (11.4 m/s): {pitch_at_rated:.4f} rad")

# Identify indices for above-rated region
above_rated_indices = np.where(pitch_angles > pitch_at_rated)[0]
theta_above = pitch_angles[above_rated_indices]
print(f"Above-rated indices: {above_rated_indices}")

# Get original gains in above-rated region for reference
kp_above_orig = kp_orig[above_rated_indices]
ki_above_orig = ki_orig[above_rated_indices]

# Fit quadratic curves to original gains for initial bounds
def fit_quadratic(theta, gains):
    A = np.vstack([np.ones_like(theta), theta, theta**2]).T
    return np.linalg.lstsq(A, gains, rcond=None)[0]

# Fit original gains to get reference coefficients
kp_coeffs_orig = fit_quadratic(theta_above, kp_above_orig)
ki_coeffs_orig = fit_quadratic(theta_above, ki_above_orig)

# Set bounds for Bayesian optimization (±50% around original coefficients)
def get_bounds(coeffs, factor=0.5):
    bounds = []
    for c in coeffs:
        if c == 0:
            bounds.append((-1, 1))  # Special case for zero
        else:
            delta = factor * abs(c)
            bounds.append((c - delta, c + delta))
    return bounds

kp_bounds = get_bounds(kp_coeffs_orig)
ki_bounds = get_bounds(ki_coeffs_orig)
bounds_dict = {
    'a0': kp_bounds[0], 'a1': kp_bounds[1], 'a2': kp_bounds[2],
    'b0': ki_bounds[0], 'b1': ki_bounds[1], 'b2': ki_bounds[2]
}

def objective_function(a0, a1, a2, b0, b1, b2):
    """Objective function for Bayesian optimization with quadratic parameterization"""
    # Compute new gains for above-rated region
    kp_above = a0 + a1 * theta_above + a2 * theta_above**2
    ki_above = b0 + b1 * theta_above + b2 * theta_above**2
    
    # Ensure gains are negative (physical constraint)
    if any(gain >= 0 for gain in kp_above) or any(gain >= 0 for gain in ki_above):
        return -1e6  # Large penalty for positive gains
    
    # Create full gain arrays
    kp_new = kp_orig.copy()
    ki_new = ki_orig.copy()
    kp_new[above_rated_indices] = kp_above
    ki_new[above_rated_indices] = ki_above
    
    # Update DISCON.IN with new gains
    with open("IEA-22-280-RWT_DISCON.IN", "r") as f:
        discon = f.readlines()
    
    # Locate Kp/Ki sections and replace values
    kp_idx = None
    ki_idx = None
    for i, line in enumerate(discon):
        if "PC_GS_KP" in line and not line.startswith('!'):
            kp_idx = i
        elif "PC_GS_KI" in line and not line.startswith('!'):
            ki_idx = i
    
    if kp_idx is None or ki_idx is None:
        raise ValueError("Could not find Kp/Ki gain lines in DISCON.IN")
    
    discon[kp_idx] = " ".join(f"{x:.6f}" for x in kp_new) + "\n"
    discon[ki_idx] = " ".join(f"{x:.6f}" for x in ki_new) + "\n"
    
    with open("IEA-22-280-RWT_DISCON.IN", "w") as f:
        f.writelines(discon)
    
    # Run OpenFAST simulation
    result = subprocess.run(["openfast_x64", "IEA-22-280-RWT-Monopile.fst"], 
                           capture_output=True, text=True)
    if result.returncode != 0:
        print(f"OpenFAST failed with error:\n{result.stderr}")
        return -1e6  # Large penalty for simulation failure
    
    # Process output
    try:
        data = postprocessing.ReadFASTBinary("IEA-22-280-RWT-Monopile.outb")
        df = data.toDataFrame()
    except Exception as e:
        print(f"Error processing output: {e}")
        return -1e6
    
    # Calculate cost components (minimize std dev of these quantities)
    std_gen_speed = df["GenSpeed"].std()
    std_tower_moment = df["TwrBsMyt"].std()
    cost = std_gen_speed + 0.1 * std_tower_moment
    
    # Return negative cost since we're using maximize()
    return -cost

# Initialize and run Bayesian optimization
optimizer = BayesianOptimization(
    f=objective_function,
    pbounds=bounds_dict,
    random_state=42,
    verbose=2
)

optimizer.maximize(
    init_points=5,
    n_iter=15,
)

# Print best results
print("\nBest parameters found:")
best_params = optimizer.max['params']
for k, v in best_params.items():
    print(f"{k}: {v:.6f}")

# Calculate final gains using best parameters
a0, a1, a2 = best_params['a0'], best_params['a1'], best_params['a2']
b0, b1, b2 = best_params['b0'], best_params['b1'], best_params['b2']

kp_above_best = a0 + a1 * theta_above + a2 * theta_above**2
ki_above_best = b0 + b1 * theta_above + b2 * theta_above**2

print("\nOptimized gains for above-rated region:")
print("Pitch angle (rad) | Kp (s)         | Ki (-)")
for theta, kp, ki in zip(theta_above, kp_above_best, ki_above_best):
    print(f"{theta:.6f}        | {kp:.6f}    | {ki:.6f}")

# Save final DISCON.IN with optimized gains
kp_final = kp_orig.copy()
ki_final = ki_orig.copy()
kp_final[above_rated_indices] = kp_above_best
ki_final[above_rated_indices] = ki_above_best

with open("IEA-22-280-RWT_DISCON.IN", "r") as f:
    discon = f.readlines()

# Update Kp/Ki lines
kp_idx = None
ki_idx = None
for i, line in enumerate(discon):
    if "PC_GS_KP" in line and not line.startswith('!'):
        kp_idx = i
    elif "PC_GS_KI" in line and not line.startswith('!'):
        ki_idx = i

if kp_idx is not None and ki_idx is not None:
    discon[kp_idx] = " ".join(f"{x:.6f}" for x in kp_final) + "\n"
    discon[ki_idx] = " ".join(f"{x:.6f}" for x in ki_final) + "\n"
    
    with open("IEA-22-280-RWT_DISCON.IN", "w") as f:
        f.writelines(discon)
    print("\nSaved optimized gains to DISCON.IN")
else:
    print("\nWarning: Could not update DISCON.IN - gain lines not found")