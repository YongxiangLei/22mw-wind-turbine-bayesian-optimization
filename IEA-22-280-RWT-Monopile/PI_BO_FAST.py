"""
Fine-tune omega_pc to optimize KP and KI gains for a wind turbine controller using Bayesian optimization.
Author: Yongxiang Lei
University of Warwick
Email:Yongxiang.Lei@warwick.ac.uk
"""

# Python modules
import matplotlib.pyplot as plt
import os
import subprocess
import numpy as np

from pyFAST.input_output import FASTOutputFile

# ROSCO toolbox modules 
from rosco.toolbox import controller as ROSCO_controller
from rosco.toolbox import turbine as ROSCO_turbine
from rosco.toolbox.utilities import write_DISCON
from rosco.toolbox.inputs.validation import load_rosco_yaml

# Bayesian optimization modules
from bayes_opt import BayesianOptimization

def run_openfast_and_get_power():
    """Run OpenFAST and return objective power."""
    res = subprocess.run(
        ['openfast_x64.exe', 'IEA-22-280-RWT-Monopile.fst'],
        capture_output=True,
        text=True,
    )

    df = FASTOutputFile('IEA-22-280-RWT-Monopile.outb').toDataFrame()
    N = min(500, len(df))  # Limit to last 500 rows for performance
    gen_power = df['GenPwr_[kW]'].tail(N)
    ref_power = 22000
    mse = np.mean((gen_power - ref_power) ** 2)
    #return df['GenPwr_[kW]'].tail(N).mean()  # last value in GenPwr column
    return -mse  # We want to minimize MSE, so return negative for maximization

# Define black-box function to optimize
def black_box_function(omega_pc1, omega_pc2, omega_pc3, parameter_yaml='IEA-22-280-RWT-Monopile.yaml'):
    """
    Receives candidate omega_pc values from BayesianOptimization,
    rebuilds the controller, writes DISCON, runs OpenFAST, and returns power.
    """
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
    write_DISCON(turbine, controller, param_file='IEA-22-280-RWT_DISCON.IN', txt_filename=path_params['rotor_performance_filename'])

    # Plot gain schedule
    fig, ax = plt.subplots(2, 2, constrained_layout=True, sharex=True)
    ax = ax.flatten()
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

    plt.suptitle('Pitch Controller Gains')
    plt.savefig('pitch_gains.png')
    plt.close()
    #plt.show()

    # Run OpenFAST and return generated power as objective
    return run_openfast_and_get_power()

def main():
    this_dir = os.path.dirname(os.path.abspath(__file__))
    parameter_yaml = os.path.join(this_dir, 'IEA-22-280-RWT-Monopile.yaml')
    inps = load_rosco_yaml(parameter_yaml)
    path_params       = inps['path_params']
    turbine_params    = inps['turbine_params']
    controller_params = inps['controller_params']

    print("path_params:", path_params)

    pbounds = {
        'omega_pc1': (0.1, 0.2),
        'omega_pc2': (0.1, 0.2),
        'omega_pc3': (0.1, 0.5),
    }
    optimizer = BayesianOptimization(
    f=black_box_function,
    pbounds=pbounds,
    random_state=42,
)
    optimizer.maximize(
        init_points=10,  # Initial exploration       
        n_iter=10,      # Number of iterations  
    )

  
    best_params = optimizer.max['params']
    print("Best parameters found:", best_params)

if __name__ == "__main__":
    main()
