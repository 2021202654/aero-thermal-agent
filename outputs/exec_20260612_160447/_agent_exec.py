import numpy as np
# Recalculate with more appropriate characteristic length for surface processes
# Characteristic length for surface processes: mean free path or adsorption site spacing ~ 1e-9 m (nanometer scale)
L_surface = 1e-9  # m (atomic scale)
V = 7000  # m/s

t_flow_surface = L_surface / V
print(f'Surface flow time scale t_flow = {t_flow_surface:.2e} s')

# Molecular collision time in boundary layer
# Mean free path lambda = 2.724e-6 m (from previous Kn calculation)
lambda_mfp = 2.724e-6  # m

t_collision = lambda_mfp / V
print(f'Collision time t_collision = {t_collision:.2e} s')

# Surface residence time from literature
# For atomic oxygen on SiO2: 10^-12 to 10^-9 s (ps to ns)
# For atomic oxygen on SiC: 10^-13 to 10^-10 s
# For atomic oxygen on Pt: 10^-14 to 10^-11 s

tau_ads_SiO2_min = 1e-12  # s (1 ps)
tau_ads_SiO2_max = 1e-9   # s (1 ns)
tau_ads_SiC_min = 1e-13   # s (0.1 ps)
tau_ads_SiC_max = 1e-10   # s (0.1 ns)

tau_ads_Pt_min = 1e-14    # s (0.01 ps)
tau_ads_Pt_max = 1e-11    # s (0.01 ns)

print(f'Adsorption time SiO2 range: {tau_ads_SiO2_min:.2e} to {tau_ads_SiO2_max:.2e} s')
print(f'Adsorption time SiC range: {tau_ads_SiC_min:.2e} to {tau_ads_SiC_max:.2e} s')
print(f'Adsorption time Pt range: {tau_ads_Pt_min:.2e} to {tau_ads_Pt_max:.2e} s')

# Check overlap between t_collision and tau_ads ranges
print(f't_collision within SiO2 adsorption range: {tau_ads_SiO2_min <= t_collision <= tau_ads_SiO2_max}')
print(f't_collision within SiC adsorption range: {tau_ads_SiC_min <= t_collision <= tau_ads_SiC_max}')
print(f't_collision within Pt adsorption range: {tau_ads_Pt_min <= t_collision <= tau_ads_Pt_max}')