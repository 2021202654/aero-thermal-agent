import numpy as np

# SiO2 catalytic recombination coefficient Arrhenius parameters
R = 8.314  # J/mol·K
E_a = 70000  # J/mol
gamma_0 = 1.5e-2

# Calculate at specific temperatures
gamma_1000 = gamma_0 * np.exp(-E_a/(R*1000))
gamma_2000 = gamma_0 * np.exp(-E_a/(R*2000))

print(f'γ(1000K) = {gamma_1000:.4e}')
print(f'γ(2000K) = {gamma_2000:.4e}')
print(f'Ratio γ(2000K)/γ(1000K) = {gamma_2000/gamma_1000:.3f}')
print(f'γ increases by factor of {gamma_2000/gamma_1000:.2f} from 1000K to 2000K')