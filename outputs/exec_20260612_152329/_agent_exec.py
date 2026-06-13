import numpy as np
import matplotlib.pyplot as plt

# Define the hypothesis function
Kn_values = np.logspace(-1, 0.7, 50)  # From 0.1 to 5.0
gamma_0 = 0.05  # baseline catalytic coefficient

# Hypothesis: gamma_eff = gamma_0 * exp(-0.85 * Kn^0.62)
gamma_eff = gamma_0 * np.exp(-0.85 * Kn_values**0.62)

# Calculate physical constraints
# Check limit behavior
limit_Kn0 = gamma_0 * np.exp(-0.85 * 0.001**0.62)  # Kn->0+
limit_Kn5 = gamma_0 * np.exp(-0.85 * 5.0**0.62)  # Kn=5.0

print(f'At Kn=0.1: gamma_eff/gamma_0 = {gamma_eff[0]/gamma_0:.3f}')
print(f'At Kn=0.5: gamma_eff/gamma_0 = {gamma_eff[24]/gamma_0:.3f}')
print(f'At Kn=3.0: gamma_eff/gamma_0 = {gamma_eff[42]/gamma_0:.3f}')
print(f'At Kn=5.0: gamma_eff/gamma_0 = {limit_Kn5/gamma_0:.3f}')
print(f'Limit as Kn->0+: gamma_eff/gamma_0 = {limit_Kn0/gamma_0:.3f}')
print(f'Limit as Kn->inf: gamma_eff/gamma_0 -> 0')

# Verify dimensional consistency
# The exponent -0.85*Kn^0.62 must be dimensionless
# Since Kn is dimensionless, this is satisfied

# Physical constraint check: gamma_eff must be between 0 and gamma_0
print(f'All gamma_eff values are physically valid: {np.all((gamma_eff >= 0) & (gamma_eff <= gamma_0))}')