
Wind Turbine Controller Optimization Results
============================================
Date: 2025-09-17 04:50:23

Best Parameters Found:
- omega_pc1: 0.1202
- omega_pc2: 0.1091
- omega_pc3: 0.2260

Best Objective (negative MSE): -37327.5755
Best MSE: 37327.5755

Total Iterations: 10
Total Time: 149559.30 seconds

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
