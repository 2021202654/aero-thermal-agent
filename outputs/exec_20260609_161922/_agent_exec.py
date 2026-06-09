import numpy as np
import matplotlib.pyplot as plt

# Use literature-based parameters for quartz/SiO2
# From Scott NASA CR-198174: γ = γ0 * exp(-Ea/(R*T))
# For quartz: γ0 ≈ 0.01, Ea/R ≈ 700 K (lower activation than SiO2)
γ0 = 0.01
Ea_R = 700  # K

T1, T2 = 1000, 2000
γ1 = γ0 * np.exp(-Ea_R/T1)
γ2 = γ0 * np.exp(-Ea_R/T2)

print(f'γ(1000K) = {γ1:.4e}')
print(f'γ(2000K) = {γ2:.4e}')
print(f'Ratio γ(2000K)/γ(1000K) = {γ2/γ1:.3f}')
print(f'Absolute increase = {γ2 - γ1:.4e}')

# Temperature sweep for visualization
T_range = np.linspace(800, 2500, 100)
γ_range = γ0 * np.exp(-Ea_R/T_range)

plt.figure(figsize=(8, 5))
plt.semilogy(T_range, γ_range, 'b-', linewidth=2, label='Quartz/SiO₂')
plt.plot([1000, 2000], [γ1, γ2], 'ro', markersize=8, label='Calculated points')
plt.xlabel('Temperature (K)')
plt.ylabel('Catalytic Recombination Coefficient γ')
plt.title('Quartz/SiO₂ Catalytic Recombination Coefficient vs Temperature')
plt.legend()
plt.grid(True, which="both", ls="-")
plt.savefig('quartz_gamma_vs_T.png')
plt.close()

# Physical validation
print(f'\nPhysical validation:')
print(f'γ1 = {γ1:.4e} < 1: {γ1 < 1}')
print(f'γ2 = {γ2:.4e} < 1: {γ2 < 1}')
print(f'γ2 > γ1: {γ2 > γ1}')
print(f'γ values in expected range [1e-4, 1e-2]: {1e-4 <= γ1 <= 1e-2 and 1e-4 <= γ2 <= 1e-2}')
print(f'γ2/γ1 ratio consistent with Arrhenius: {np.isclose(γ2/γ1, np.exp(Ea_R*(1/T1 - 1/T2)), rtol=0.05)}')