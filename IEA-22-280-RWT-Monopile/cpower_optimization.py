"""Example 1: Opening FLORIS and Computing Power

This example illustrates several of the key concepts in FLORIS. It demonstrates:

  1) Initializing a FLORIS model
  2) Changing the wind farm layout
  3) Changing the incoming wind speed, wind direction and turbulence intensity
  4) Running the FLORIS simulation
  5) Getting the power output of the turbines

Main concept is introduce FLORIS and illustrate essential structure of most-used FLORIS calls
"""


import numpy as np

from floris import FlorisModel
from bayes_opt import BayesianOptimization
import floris.flow_visualization as flowviz
import floris.layout_visualization as layoutviz
from floris import FlorisModel, TimeSeries
import matplotlib.pyplot as plt
# The FlorisModel class is the entry point for most usage.
# Initialize using an input yaml file


# Changing wind speed, wind direction, and turbulence intensity uses the set method
# as well. Note that the wind_speeds, wind_directions, and turbulence_intensities
# are all specified as arrays of the same length.
# fmodel.set(
#     wind_directions=np.array([270.0]), wind_speeds=[8.0], turbulence_intensities=np.array([0.06])
# )
# N=1
# yaw_angle = 20*np.array([np.ones(1), np.ones(1)]).T
# fmodel.set(
#             wind_directions=np.array([270.0]),    wind_speeds=[8.0],
#             turbulence_intensities=np.array([0.06]),
#             yaw_angles=yaw_angle,
#         )
# Note that typically all 3, wind_directions, wind_speeds and turbulence_intensities
# must be supplied to set.  However, the exception is if not changing the length
# of the arrays, then only one or two may be supplied.
# fmodel.set(turbulence_intensities=np.array([0.07]))

# The number of elements in the wind_speeds, wind_directions, and turbulence_intensities
# corresponds to the number of conditions to be simulated.  In FLORIS, each of these are
# tracked by a simple index called a findex.  There is no requirement that the values
# be unique.  Internally in FLORIS, most data structures will have the findex as their
# 0th dimension.  The value n_findex is the total number of conditions to be simulated.
# This command would simulate 4 conditions (n_findex = 4).
# fmodel.set(
#     wind_directions=np.array([270.0, 270.0, 270.0, 270.0]),
#     wind_speeds=[8.0, 8.0, 10.0, 10.0],
#     turbulence_intensities=np.array([0.06, 0.06, 0.06, 0.06]),
# )

# After the set method, the run method is called to perform the simulation
# fmodel.run()

# There are functions to get either the power of each turbine, or the farm power
# turbine_powers = fmodel.get_turbine_powers() / 1000.0
# farm_power = fmodel.get_farm_power() / 1000.0

from bayes_opt import BayesianOptimization
import numpy as np

# 黑箱函数
def black_box_function(*args):
    inputs = np.array(args)
    yaw_angle = np.array([x * np.ones(1) for x in inputs]).T
    fmodel = FlorisModel("inputs/gch.yaml")

    # Changing the wind farm layout uses FLORIS' set method to a two-turbine layout
    layoutx = [189.261, 206.855, 226.689, 245.849, 265.751,
               1018.616, 1044.876, 1069.098, 1093.450,
               1852.340, 1876.821, 1899.938, 1923.936,
               2682.215, 2704.316, 2725.803, 2751.756,
               3506.731, 3522.840, 3540.445, 3555.964, 3572.312,
               4369.382, 4384.888]
    layouty = [872.524, 1455.174, 2038.116, 2621.918, 3207.779,
               813.299, 1583.900, 2354.140, 3124.338,
               751.886, 1533.103, 2316.042, 3098.054,
               617.561, 1404.344, 2191.967, 2980.180,
               254.200, 858.357, 1463.690, 2068.679, 2672.758,
               1545.941, 2150.881]
    # Set the layout in fmodel
    # fmodel.set(
    #     layout_x=layout_x,
    #     layout_y=layout_y
    # )
    # The FlorisModel class is the entry point for most usage.
    # Initialize using an input yaml file

    # Changing the wind farm layout uses FLORIS' set method to a two-turbine layout
    fmodel.set(layout_x=layoutx, layout_y=layouty)
    # 假设 fmodel 是预定义的风场仿真模型
    fmodel.set(
        wind_directions=np.array([0]),
        wind_speeds=[10.0],
        turbulence_intensities=np.array([0.06]),
        yaw_angles=yaw_angle,
    )
    fmodel.run()
    farm_power = fmodel.get_farm_power() / 1000.0
    return float(np.sum(farm_power))

# 定义优化变量（剔除固定变量）
variable_indices = [1, 2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15, 16, 18, 19, 20, 21, 23]
pbounds = {f'x{i}': (-30, 30) for i in variable_indices}

# 包装黑箱函数，包含固定值
def wrapped_black_box_function(**kwargs):
    fixed_values = {'x5': 0, 'x9': 0, 'x13': 0, 'x17': 0, 'x22': 0, 'x24': 0}
    combined_params = {**kwargs, **fixed_values}
    args = [combined_params[f'x{i}'] for i in range(1, 25)]
    return black_box_function(*args)

# 初始化贝叶斯优化器
optimizer = BayesianOptimization(
    f=wrapped_black_box_function,
    pbounds=pbounds,
    random_state=42,
)


# Initialize Bayesian Optimization
# optimizer = BayesianOptimization(
#     f=wrapped_black_box_function,
#     pbounds=pbounds,
#     random_state=1,
# )

# Perform optimization
optimizer.maximize(
    init_points=50,
    n_iter=600,
)

print(optimizer.max)
# print("The turbine power matrix should be of dimensions 4 (n_findex) X 2 (n_turbines)")
# print(turbine_powers)
# print("Shape: ", turbine_powers.shape)
#
# print("The farm power should be a 1D array of length 4 (n_findex)")
# print(farm_power)
# print("Shape: ", farm_power.shape)
# fig, axarr = plt.subplots(1, 1, figsize=(10, 5), sharex=False)
# ax = axarr # Baseline aligned operation
# fmodel.reset_operation()
# fmodel.set(wind_directions=[0], wind_speeds=[10.0], turbulence_intensities=[0.06],)
# fmodel.run()
# horizontal_plane = fmodel.calculate_horizontal_plane(height=90.0)
# flowviz.visualize_cut_plane(horizontal_plane, ax=ax)
# layoutviz.plot_turbine_rotors(fmodel, ax=ax)
# ax.set_title("Turbines aligned")
# plt.show()