###Author: Yongxiang Lei###
###University of Warwick###
###Email:Yongxiang.Lei@warwick.ac.uk###
from pyFAST.input_output import FASTOutputFile
import matplotlib.pyplot as plt
import numpy as np

power_ref = 22000  # Reference power in kW

# 读取结果
df = FASTOutputFile('IEA-22-280-RWT-Monopile-BO.outb').toDataFrame()
df_bo = FASTOutputFile('IEA-22-280-RWT-Monopile.outb').toDataFrame()

# 仅保留 100–300 s
mask  = (df['Time_[s]'] >= 100.0) & (df['Time_[s]'] <= 300.0)
time  = df.loc[mask, 'Time_[s]'].values
power = df.loc[mask, 'GenPwr_[kW]'].values
power_bo = df_bo.loc[mask, 'GenPwr_[kW]'].values

# 计算 MSE（可选）
mse = np.mean((power - power_ref)**2)

# 绘图：实际功率 + 参考功率
plt.figure()
plt.plot(time, power, label='Actual Power', linewidth=1.2)
plt.plot(time, power_bo, label='Optimized Power', linewidth=1.2)
plt.plot(time, np.full_like(time, power_ref), '--', label=f'Reference ({power_ref/1000:.1f} MW)')
plt.xlabel('Time [s]')
plt.ylabel('Generator Power [kW]')
# plt.title('Generator Power vs Reference (100–300 s)')
plt.xlim([100, 300])
plt.ylim([20000, 25000])
plt.grid(True)
plt.legend()
# plt.text(0.01, 0.98, f"MSE = {mse:.2e} kW²", transform=plt.gca().transAxes,
#          va='top', ha='left')  # 想精简可删除此行
plt.tight_layout()
plt.savefig('generator_power_with_reference.png', dpi=1200)
plt.close()

# 绘图： Pitch Angle
plt.figure()
plt.plot(time, df.loc[mask, 'BldPitch1_[deg]'].values, label='Pitch Angle', color='orange', linewidth=1.2)
plt.plot(time, df_bo.loc[mask, 'BldPitch1_[deg]'].values, label='Optimized Pitch Angle', color='red', linewidth=1.2)
plt.xlabel('Time [s]')  
plt.ylabel('Pitch Angle [deg]')
# plt.title('Blade Pitch Angle (100–300 s)')        
plt.xlim([100, 300])
plt.ylim([11, 17])
plt.grid(True)  
plt.legend()
plt.tight_layout()
plt.savefig('blade_pitch_angle.png', dpi=1200)
plt.close()

# 绘图：wind speed
plt.figure()
plt.plot(time, df.loc[mask, 'Wind1VelX_[m/s]'].values, label='Wind Speed', color='green', linewidth=1.2)
plt.xlabel('Time [s]')      
plt.ylabel('Wind Speed [m/s]')
# plt.title('Wind Speed (100–300 s)')           
plt.xlim([100, 300])
plt.ylim([14, 25])      
plt.grid(True)  
# plt.legend()    
plt.tight_layout()
plt.savefig('windprofile.png', dpi=1200)