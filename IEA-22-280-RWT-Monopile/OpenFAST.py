"""
Optimize KP and KI gains for a wind turbine controller using Bayesian optimization.
$ pip install bayesian-optimization
------------------ 
Load a turbine model and tune the controller
In this test:

* Read a .yaml file
* Load a turbine model from OpenFAST
* Tune a controller
* Write a controller input file
* Run the optimization
* Plot gain schedule
"""

import matplotlib.pyplot as plt
import os

import subprocess
# ROSCO toolbox modules
from rosco.toolbox import controller, turbine
from rosco.toolbox.utilities import write_DISCON
from rosco.toolbox.inputs.validation import load_rosco_yaml



if __name__ == "__main__":
    this_dir = os.path.dirname(os.path.abspath(__file__))
    # Load turbine model from YAML file
    #parameter_filename = load_rosco_yaml("IEA-22-280-RWT-Monopile.yaml")
    parameter_filename = os.path.join("optimization_logs_20250915_111744/IEA-22-280-RWT-Monopile.yaml")
    
    inps = load_rosco_yaml(parameter_filename)
    path_params         = inps['path_params']
    turbine_params      = inps['turbine_params']
    controller_params   = inps['controller_params']

        # Instantiate turbine, controller, and file processing classes
    turbine         = turbine.Turbine(turbine_params)
    controller      = controller.Controller(controller_params)

    # Load turbine data from OpenFAST and rotor performance text file
    cp_filename = path_params['rotor_performance_filename']
    turbine.load_from_fast(
        path_params['FAST_InputFile'],
        path_params['FAST_directory'],
        rot_source='txt',txt_filename= cp_filename
        )

    # Tune controller 
    controller.tune_controller(turbine)

    # Write parameter input file
    param_file = os.path.join(this_dir,'IEA-22-280-RWT_DISCON.IN')
    write_DISCON(turbine,controller,
    param_file=param_file, 
    txt_filename=cp_filename
    )

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
    plt.savefig('new_pitch_gains.png')
    plt.close()


