"""
Fine-tune omega_pc to optimize KP and KI gains for a wind turbine controller using Bayesian optimization.
Enhanced with comprehensive training logs - Compatible with all bayes_opt versions.
Author: Yongxiang Lei
University of Warwick
Email:Yongxiang.Lei@warwick.ac.uk
"""

# Python modules
import matplotlib.pyplot as plt
import os
import subprocess
import numpy as np
import time
import datetime as dt
import json
import csv
import logging
import shutil
import traceback

from pyFAST.input_output import FASTOutputFile

# ROSCO toolbox modules 
from rosco.toolbox import controller as ROSCO_controller
from rosco.toolbox import turbine as ROSCO_turbine
from rosco.toolbox.utilities import write_DISCON
from rosco.toolbox.inputs.validation import load_rosco_yaml

# Bayesian optimization modules
from bayes_opt import BayesianOptimization

# Global variables for logging
iteration_counter = 0
log_dir = None
logger = None
csv_writer = None
csv_file = None
optimizer_results = []  # Store results manually

def setup_logging():
    """Setup logging directory and logger."""
    global log_dir, logger, csv_writer, csv_file
    
    # Create timestamped log directory
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = f"optimization_logs_{timestamp}"
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(os.path.join(log_dir, "iterations"), exist_ok=True)
    
    # Setup Python logger
    logger = logging.getLogger("wind_turbine_opt")
    logger.setLevel(logging.INFO)
    
    # File handler
    fh = logging.FileHandler(os.path.join(log_dir, "optimization.log"))
    fh.setLevel(logging.INFO)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    # Setup CSV logger for iterations
    csv_path = os.path.join(log_dir, "iterations.csv")
    csv_file = open(csv_path, 'w', newline='')
    csv_writer = csv.DictWriter(csv_file, fieldnames=[
        'iteration', 'omega_pc1', 'omega_pc2', 'omega_pc3', 
        'objective', 'mse', 'status', 'execution_time'
    ])
    csv_writer.writeheader()
    
    logger.info(f"Logging initialized. Log directory: {log_dir}")
    return log_dir

def run_openfast_and_get_power():
    """Run OpenFAST and return objective power."""
    global iteration_counter, logger
    
    start_time = time.time()
    iter_dir = os.path.join(log_dir, "iterations", f"iter_{iteration_counter:03d}")
    os.makedirs(iter_dir, exist_ok=True)
    
    try:
        # Run OpenFAST and capture output
        logger.info(f"Running OpenFAST for iteration {iteration_counter}")
        res = subprocess.run(
            ['openfast_x64.exe', 'IEA-22-280-RWT-Monopile.fst'],
            capture_output=True,
            text=True,
        )
        
        # Save OpenFAST output
        with open(os.path.join(iter_dir, "openfast_stdout.txt"), 'w') as f:
            f.write(res.stdout)
        with open(os.path.join(iter_dir, "openfast_stderr.txt"), 'w') as f:
            f.write(res.stderr)
        
        # Analyze results
        df = FASTOutputFile('IEA-22-280-RWT-Monopile.outb').toDataFrame()
        N = min(500, len(df))  # Limit to last 500 rows for performance
        gen_power = df['GenPwr_[kW]'].tail(N)
        ref_power = 22000
        mse = np.mean((gen_power - ref_power) ** 2)
        objective = -mse  # We want to minimize MSE, so return negative for maximization
        
        # Save power data
        gen_power.to_csv(os.path.join(iter_dir, "gen_power_tail.csv"), index=False)
        
        execution_time = time.time() - start_time
        logger.info(f"Iteration {iteration_counter} completed: MSE={mse:.2f}, Time={execution_time:.2f}s")
        
        # Log iteration result
        return objective, mse, "SUCCESS", execution_time
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Error in iteration {iteration_counter}: {str(e)}")
        
        # Save error details
        with open(os.path.join(iter_dir, "error.txt"), 'w') as f:
            f.write(f"Error: {str(e)}\n\n")
            f.write(traceback.format_exc())
        
        return -1e10, 1e10, "FAILED", execution_time  # Return large penalty on failure

# Define black-box function to optimize
def black_box_function(omega_pc1, omega_pc2, omega_pc3, parameter_yaml='IEA-22-280-RWT-Monopile.yaml'):
    """
    Receives candidate omega_pc values from BayesianOptimization,
    rebuilds the controller, writes DISCON, runs OpenFAST, and returns power.
    """
    global iteration_counter, logger, csv_writer, optimizer_results
    
    iteration_counter += 1
    iter_dir = os.path.join(log_dir, "iterations", f"iter_{iteration_counter:03d}")
    os.makedirs(iter_dir, exist_ok=True)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Starting iteration {iteration_counter}")
    logger.info(f"Testing omega_pc = [{omega_pc1:.4f}, {omega_pc2:.4f}, {omega_pc3:.4f}]")
    
    # Save iteration parameters
    params = {
        'iteration': iteration_counter,
        'omega_pc1': omega_pc1,
        'omega_pc2': omega_pc2,
        'omega_pc3': omega_pc3,
        'timestamp': dt.datetime.now().isoformat()
    }
    with open(os.path.join(iter_dir, "parameters.json"), 'w') as f:
        json.dump(params, f, indent=2)
    
    # Load inputs each call (simple & safe; you can cache for speed)
    inps = load_rosco_yaml(parameter_yaml)
    path_params       = inps['path_params']
    turbine_params    = inps['turbine_params']
    controller_params = inps['controller_params']

    # Inject the candidate pitch filter corner frequencies
    controller_params['omega_pc'] = [omega_pc1, omega_pc2, omega_pc3]
    print("Controller parameters:", controller_params['omega_pc'])

    # Instantiate turbine and controller
    turbine    = ROSCO_turbine.Turbine(turbine_params)
    controller = ROSCO_controller.Controller(controller_params)

    # Load turbine aerodynamics
    turbine.load_from_fast(
        path_params['FAST_InputFile'],
        path_params['FAST_directory'],
        rot_source='txt', txt_filename=path_params['rotor_performance_filename']
    )

    # Tune controller with the candidate omegas
    controller.tune_controller(turbine)

    # Write DISCON next to the .fst
    discon_filename = 'IEA-22-280-RWT_DISCON.IN'
    write_DISCON(turbine, controller, param_file=discon_filename, 
                 txt_filename=path_params['rotor_performance_filename'])
    
    # Copy DISCON to iteration directory
    shutil.copy2(discon_filename, os.path.join(iter_dir, discon_filename))
    logger.info(f"DISCON file saved for iteration {iteration_counter}")

    plt.rcParams.update({
        'font.family': 'serif',
        'font.size': 20,
        'axes.titlesize': 20,
        'axes.labelsize': 20,
        'xtick.labelsize': 20,
        'ytick.labelsize': 20,
        'legend.fontsize': 20,
        'figure.titlesize': 20})

    # Plot gain schedule
    fig, ax = plt.subplots(2, 2, constrained_layout=True, sharex=True)
    ax = ax.flatten()
    for a in ax:
        a.grid(True, which='major', linestyle='-', linewidth=0.75, alpha=0.25)
        a.minorticks_on()
        a.grid(True, which='minor', linestyle='-', linewidth=0.25, alpha=0.15)
        a.set_axisbelow(True)
    ax[0].plot(controller.v[len(controller.v_below_rated)+1:], controller.omega_pc_U)
    ax[0].set_ylabel('omega_pc')

    ax[1].plot(controller.v[len(controller.v_below_rated)+1:], controller.zeta_pc_U)
    ax[1].set_ylabel('zeta_pc')

    ax[2].plot(controller.v[len(controller.v_below_rated)+1:], controller.pc_gain_schedule.Kp)
    ax[2].set_xlabel('Wind Speed')
    ax[2].set_ylabel('Proportional Gain')

    ax[3].plot(controller.v[len(controller.v_below_rated)+1:], controller.pc_gain_schedule.Ki)
    ax[3].set_xlabel('Wind Speed')
    ax[3].set_ylabel('Integral Gain')

    plt.suptitle(f'Pitch Controller Gains - Iteration {iteration_counter}')
    
    # Save plot to iteration directory
    plot_path = os.path.join(iter_dir, 'pitch_gains.png')
    plot_path = os.path.join(iter_dir, 'pitch_gains.pdf')
    plot_path = os.path.join(iter_dir, 'pitch_gains.svg')
    plt.savefig(plot_path)
    plt.close()
    logger.info(f"Gain schedule plot saved for iteration {iteration_counter}")

    # Run OpenFAST and return generated power as objective
    objective, mse, status, exec_time = run_openfast_and_get_power()
    
    # Write to CSV
    csv_writer.writerow({
        'iteration': iteration_counter,
        'omega_pc1': omega_pc1,
        'omega_pc2': omega_pc2,
        'omega_pc3': omega_pc3,
        'objective': objective,
        'mse': mse,
        'status': status,
        'execution_time': exec_time
    })
    csv_file.flush()
    
    # Save iteration summary
    summary = {
        'iteration': iteration_counter,
        'parameters': {'omega_pc1': omega_pc1, 'omega_pc2': omega_pc2, 'omega_pc3': omega_pc3},
        'results': {'objective': objective, 'mse': mse, 'status': status},
        'execution_time': exec_time,
        'timestamp': dt.datetime.now().isoformat()
    }
    with open(os.path.join(iter_dir, "summary.json"), 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Store result manually for final logging
    optimizer_results.append({
        'target': objective,
        'params': {'omega_pc1': omega_pc1, 'omega_pc2': omega_pc2, 'omega_pc3': omega_pc3}
    })
    
    # Save cumulative bayes_opt log
    with open(os.path.join(log_dir, "bayes_opt_log.json"), 'w') as f:
        json.dump(optimizer_results, f, indent=2)
    
    return objective

def main():
    global csv_file
    
    # Setup logging
    setup_logging()
    
    this_dir = os.path.dirname(os.path.abspath(__file__))
    parameter_yaml = os.path.join(this_dir, 'IEA-22-280-RWT-Monopile.yaml')
    
    # Copy yaml to log directory for reference
    shutil.copy2(parameter_yaml, os.path.join(log_dir, 'IEA-22-280-RWT-Monopile.yaml'))
    
    inps = load_rosco_yaml(parameter_yaml)
    path_params       = inps['path_params']
    turbine_params    = inps['turbine_params']
    controller_params = inps['controller_params']

    print("path_params:", path_params)
    logger.info(f"Starting optimization with parameter file: {parameter_yaml}")
    logger.info(f"Path parameters: {path_params}")

    # Define optimization bounds
    pbounds = {
        'omega_pc1': (0.1, 0.2),
        'omega_pc2': (0.1, 0.2),
        'omega_pc3': (0.1, 0.5),
    }
    
    # Log optimization setup
    opt_config = {
        'bounds': pbounds,
        'init_points': 5,
        'n_iter': 5,
        'random_state': 42,
        'timestamp': dt.datetime.now().isoformat()
    }
    with open(os.path.join(log_dir, 'optimization_config.json'), 'w') as f:
        json.dump(opt_config, f, indent=2)
    
    # Create optimizer
    optimizer = BayesianOptimization(
        f=black_box_function,
        pbounds=pbounds,
        random_state=42,
    )
    
    # Run optimization
    start_time = time.time()
    logger.info("Starting Bayesian optimization...")
    
    optimizer.maximize(
        init_points=5,  # Initial exploration       
        n_iter=5,      # Number of iterations  
    )
    
    total_time = time.time() - start_time
    
    # Get best results
    best_params = optimizer.max['params']
    best_value = optimizer.max['target']
    
    print("\n" + "="*60)
    print("OPTIMIZATION COMPLETE")
    print("="*60)
    print("Best parameters found:", best_params)
    print(f"Best objective value: {best_value:.4f}")
    print(f"Total optimization time: {total_time:.2f} seconds")
    print(f"Logs saved to: {log_dir}")
    
    logger.info("="*60)
    logger.info("OPTIMIZATION COMPLETE")
    logger.info(f"Best parameters: {best_params}")
    logger.info(f"Best objective: {best_value:.4f}")
    logger.info(f"Total time: {total_time:.2f} seconds")
    
    # Save final results
    final_results = {
        'best_parameters': best_params,
        'best_objective': best_value,
        'best_mse': -best_value,  # Convert back to MSE
        'total_iterations': iteration_counter,
        'total_time': total_time,
        'timestamp': dt.datetime.now().isoformat(),
        'all_results': optimizer.res
    }
    with open(os.path.join(log_dir, 'final_results.json'), 'w') as f:
        json.dump(final_results, f, indent=2)
    
    # Close CSV file
    if csv_file:
        csv_file.close()
    
    # Create README for the log directory
    readme_content = f"""
Wind Turbine Controller Optimization Results
============================================
Date: {dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Best Parameters Found:
- omega_pc1: {best_params['omega_pc1']:.4f}
- omega_pc2: {best_params['omega_pc2']:.4f}
- omega_pc3: {best_params['omega_pc3']:.4f}

Best Objective (negative MSE): {best_value:.4f}
Best MSE: {-best_value:.4f}

Total Iterations: {iteration_counter}
Total Time: {total_time:.2f} seconds

Files in this directory:
- optimization.log: Main log file with all events
- iterations.csv: Summary of all iterations
- bayes_opt_log.json: Optimization history
- final_results.json: Final optimization results
- optimization_config.json: Optimization configuration
- iterations/: Directory containing detailed logs for each iteration
  - iter_XXX/: Each iteration folder contains:
    - parameters.json: Input parameters
    - pitch_gains.png: Gain schedule plot
    - IEA-22-280-RWT_DISCON.IN: DISCON file
    - openfast_stdout.txt: OpenFAST output
    - openfast_stderr.txt: OpenFAST errors
    - gen_power_tail.csv: Power generation data
    - summary.json: Iteration summary
"""
    
    with open(os.path.join(log_dir, 'README.txt'), 'w') as f:
        f.write(readme_content)
    
    logger.info(f"README file created in {log_dir}")

if __name__ == "__main__":
    main()