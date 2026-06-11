"""
Aerothermal Parameter Computation Tool -- Domain-Specific Numerical Computation

Covers: stagnation heat flux / Knudsen number / catalytic coefficient / unit conversion / boundary layer thickness
All formulas are annotated with references, compliant with Agent constraint "computations must be verifiable".
"""

from __future__ import annotations

import math

from core.action import Action


class AeroThermalComputeTool(Action):
    """Aerothermal parameter computation -- executes common hypersonic engineering calculations."""

    name = "compute_aerothermal"
    description = (
        "Executes engineering calculations in the hypersonic aerothermal domain. "
        "Computes stagnation heat flux density (Fay-Riddell/Sutton-Graves formulas), "
        "Knudsen number (flow regime assessment: continuum/transition/free molecular), "
        "catalytic recombination coefficient lookup (SiO2/SiC/Al2O3/Pt, etc.), "
        "unit conversion (W/m2<->kW/m2, Pa<->atm, K<->C, etc.), "
        "and boundary layer thickness estimation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "calc_type": {
                "type": "string",
                "enum": [
                    "stagnation_heat_flux",
                    "knudsen_number",
                    "catalytic_coefficient",
                    "unit_conversion",
                    "boundary_layer",
                ],
                "description": "Calculation type",
            },
            "params": {
                "type": "object",
                "description": (
                    "Calculation parameters, varies by calc_type:\n"
                    "- stagnation_heat_flux: velocity(m/s), radius(m), density(kg/m3)\n"
                    "- knudsen_number: characteristic_length(m), optional temperature(K), pressure(Pa)\n"
                    "- catalytic_coefficient: material(SiO2/SiC/Al2O3/Pt/quartz/RCG), temperature(K)\n"
                    "- unit_conversion: value(float), from_unit, to_unit\n"
                    "- boundary_layer: x(m), reynolds(float)"
                ),
            },
        },
        "required": ["calc_type", "params"],
    }

    async def run(self, calc_type: str, params: dict) -> str:
        handlers = {
            "stagnation_heat_flux": self._calc_stagnation_heat_flux,
            "knudsen_number": self._calc_knudsen,
            "catalytic_coefficient": self._lookup_catalytic,
            "unit_conversion": self._convert_units,
            "boundary_layer": self._calc_boundary_layer,
        }
        handler = handlers.get(calc_type)
        if handler is None:
            return f"[ERROR] Unknown calculation type: {calc_type}. Available: {list(handlers.keys())}"
        try:
            return handler(params)
        except Exception as e:
            return f"[COMPUTATION ERROR] {calc_type}: {e}"

    # ── Fay-Riddell / Sutton-Graves Stagnation Heat Flux ────────

    def _calc_stagnation_heat_flux(self, p: dict) -> str:
        v = float(p.get("velocity", 0))
        r = float(p.get("radius", 1.0))
        rho = float(p.get("density", 1.2))

        k = 1.83e-4  # Earth atmospheric constant (W/m² units)
        q_w = k * math.sqrt(rho / r) * v**3

        return (
            f"**Stagnation Heat Flux Density (Sutton-Graves Simplified Formula)**\n"
            f"Input: V = {v:.0f} m/s, R_n = {r:.3f} m, rho = {rho:.4f} kg/m3\n"
            f"q_w = {q_w:.2e} W/m2 = {q_w/1e3:.2f} kW/m2 = {q_w/1e6:.4f} MW/m2\n\n"
            f"Ref: Fay & Riddell, J. Aeronaut. Sci. 25(2), 1958\n"
            f"     Sutton & Graves, NASA TR R-376, 1973\n"
            f"NOTE: Assumes equilibrium catalytic wall, ideal gas, laminar flow. Accurate computation requires real gas effects."
        )

    # ── Knudsen Number ──────────────────────────────────

    def _calc_knudsen(self, p: dict) -> str:
        L = float(p.get("characteristic_length", 1.0))
        T = float(p.get("temperature", 300))
        pressure = float(p.get("pressure", 101325))

        k_B = 1.380649e-23
        d_air = 3.7e-10
        mfp = k_B * T / (math.sqrt(2) * math.pi * d_air**2 * pressure)

        kn = mfp / L

        if kn < 0.001:
            regime = "Continuum flow (Navier-Stokes applicable)"
        elif kn < 0.1:
            regime = "Slip flow (requires velocity slip + temperature jump boundary conditions)"
        elif kn < 10:
            regime = "Transition flow (DSMC applicable, Navier-Stokes fails)"
        else:
            regime = "Free molecular flow"

        return (
            f"**Knudsen Number**\n"
            f"lambda = {mfp:.3e} m (T={T:.0f} K, p={pressure:.0f} Pa)\n"
            f"L = {L:.3e} m\n"
            f"Kn = {kn:.4e} --> **{regime}**\n\n"
            f"Reference: Bird, Molecular Gas Dynamics and DSMC, 1994"
        )

    # ── Catalytic Recombination Coefficient Lookup ────────────────────────────

    def _lookup_catalytic(self, p: dict) -> str:
        material = p.get("material", "SiO2").strip()
        T = float(p.get("temperature", 1500))
        species = p.get("species", "O").strip().upper()  # O / N / mixed

        # ═══════════════════════════════════════════════════════
        # Catalytic recombination coefficient database
        #
        # Format: gamma_300, gamma_2000, T_act(K), info, references
        # Model: gamma(T) ~= gamma_300 * exp(T_act * (1/300 - 1/T))
        #
        # IMPORTANT LIMITATIONS:
        # 1. Default data is for O-atom recombination (N-atom typically 2-5x lower)
        # 2. Single-species measurements != multi-species coexistence (surface site competition)
        # 3. gamma strongly depends on surface state, gas pressure, flow composition, measurement method
        # 4. Different experimental facilities (arc-jet/ICP/shock tube) can yield order-of-magnitude differences
        #
        # Verified references:
        # [S1] Scott, "Catalytic Recombination of N and O on HRSI",
        #      AIAA Paper 80-1477, 1980 (NASA accession 19800057279)
        # [S2] Nasuti, Barbato & Bruno, "Material-Dependent Catalytic
        #      Recombination Modeling for Hypersonic Flows", AIAA 96-1888, 1996
        # [S3] Stewart et al., "Catalytic Recombination on TPS Materials",
        #      AIAA 2011-3750, 2011
        # [S4] Balat-Pichelin et al., "Recombination coefficient of atomic
        #      oxygen on ceramic materials", J. Eur. Ceram. Soc., 2006
        # [S5] Arasa, Gamallo & Sayos, "Adsorption of Atomic O and N at
        #      beta-Cristobalite (100): A DFT Study", JPCB 109(31), 2005
        # ═══════════════════════════════════════════════════════

        DB = {
            # (gamma_O_300, gamma_O_2000, T_act_O, info, refs)
            "sio2":  (8e-4, 1.5e-2, 800,
                      "SiO2/quartz/HRSI surface O-atom recombination (Scott AIAA 80-1477; Nasuti AIAA 96-1888)",
                      "Scott AIAA 80-1477 (1980); Nasuti et al. AIAA 96-1888 (1996); Stewart AIAA 2011-3750"),
            "sio2_o":(8e-4, 1.5e-2, 800,
                      "SiO2 surface O-atom recombination",
                      "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "sio2_n":(2e-4, 3e-3, 600,
                      "SiO2 surface N-atom recombination (gamma_N typically 2-5x lower than gamma_O)",
                      "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "sio2":  (8e-4, 1.5e-2, 800,
                      "SiO2/quartz/HRSI surface O-atom recombination",
                      "Scott AIAA 80-1477; Nasuti AIAA 96-1888; Stewart AIAA 2011-3750"),
            "quartz":(5e-4, 8e-3, 700,
                      "Quartz (fused silica) O-atom recombination, low catalytic activity",
                      "Scott AIAA 80-1477; Balat-Pichelin JECS 2006"),
            "rcg":   (8e-4, 1.2e-2, 750,
                      "Reaction Cured Glass (HRSI coating) O-atom recombination",
                      "Stewart AIAA 2011-3750; Scott AIAA 80-1477"),
            "sic":   (8e-3, 8e-2, 1200,
                      "SiC surface O-atom recombination (He et al. Appl Surf Sci 2024)",
                      "Scott AIAA 80-1477; He et al. Appl Surf Sci 664, 2024, 160263"),
            "sic_o": (8e-3, 8e-2, 1200,
                      "SiC surface O-atom recombination",
                      "Scott AIAA 80-1477; He et al. 2024"),
            "sic_n": (2e-3, 2e-2, 1000,
                      "SiC surface N-atom recombination",
                      "Scott AIAA 80-1477; estimated"),
            "al2o3": (3e-3, 4e-2, 1000,
                      "Al2O3 surface O-atom recombination, moderate catalytic activity",
                      "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "al2o3_o":(3e-3, 4e-2, 1000,
                       "Al2O3 surface O-atom recombination",
                       "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "al2o3": (3e-3, 4e-2, 1000,
                      "Al2O3 surface O-atom recombination, moderate catalytic activity",
                      "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "pt":    (5e-2, 3e-1, -2000,
                      "Pt surface (high catalytic activity, gamma decreases at high T due to saturation)",
                      "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "platinum":(5e-2, 3e-1, -2000,
                        "Pt surface (high catalytic activity, gamma decreases at high T due to saturation)",
                        "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "si3n4": (1e-3, 6e-3, 900,
                      "Si3N4 surface O-atom recombination (limited literature data, pending verification)",
                      "Pending verification"),
        }

        key = material.lower().strip()
        if species == "N":
            # Try to match N-specific entry
            n_key = f"{key}_n"
            if n_key in DB:
                gamma_300, gamma_2000, T_act, info, ref = DB[n_key]
            else:
                # fallback: use O data but annotate clearly
                gamma_300, gamma_2000, T_act, info, ref = DB.get(key, DB.get(f"{key}_o", None) or DB["sio2"])
                info += " [WARNING: using O-atom data for N-atom query; N gamma typically 2-5x lower]"
        elif species == "O":
            o_key = f"{key}_o"
            if o_key in DB:
                gamma_300, gamma_2000, T_act, info, ref = DB[o_key]
            else:
                gamma_300, gamma_2000, T_act, info, ref = DB.get(key, DB["sio2"])
        else:
            # mixed / unspecified
            gamma_300, gamma_2000, T_act, info, ref = DB.get(key, DB["sio2"])

        # Arrhenius prediction
        T_clamped = max(300, min(3000, T))
        try:
            gamma_T = gamma_300 * math.exp(T_act * (1/300 - 1/T_clamped))
        except OverflowError:
            gamma_T = gamma_2000 if T_act > 0 else gamma_300

        # Clamping
        gamma_low = min(gamma_300, gamma_2000) * 0.5
        gamma_high = max(gamma_300, gamma_2000) * 2.0
        gamma_T = max(gamma_low, min(gamma_high, gamma_T))

        # Flow regime + uncertainty notes
        regime_notes = []
        if T > 2000:
            regime_notes.append("T > 2000K: Dissociation effects significant, Arrhenius extrapolation uncertainty increases")
        if T < 300:
            regime_notes.append("T < 300K: Limited low-temperature data, extrapolation unreliable")
        species_note = ""
        if species not in ("O", "N"):
            species_note = (
                "\n[IMPORTANT] Species not specified. Defaulting to O-atom recombination."
                "\nActual gamma depends on whether recombining species is O, N, or O+N mixture."
                "\nN-atom gamma is typically 2-5x lower than O-atom on oxide surfaces."
                "\nUnder multi-species conditions, competitive surface coverage reduces individual gamma values."
            )

        return (
            f"**{material} Catalytic Recombination Coefficient (Species: {species})**\n"
            f"T = {T:.0f} K -> gamma = {gamma_T:.2e} (Arrhenius model estimate)\n"
            f"Reference range: gamma(300K) = {gamma_300:.2e} to gamma(2000K) = {gamma_2000:.2e}\n"
            f"Activation: T_act = {T_act:.0f} K "
            f"{'-> gamma increases with T' if T_act > 0 else '-> gamma decreases with T (saturation)'}\n"
            f"Info: {info}{species_note}\n"
            f"{chr(10).join(regime_notes) if regime_notes else ''}"
            f"\n"
            f"[WARNING] These are CONDITIONAL ESTIMATES, not verified literature constants.\n"
            f"  - gamma depends on: surface state (roughness, contamination, oxidation),\n"
            f"    partial pressure, flow composition, and measurement method.\n"
            f"  - Different experimental facilities (arc-jet, ICP, shock tube) can give\n"
            f"    order-of-magnitude differences for the same nominal material.\n"
            f"  - Single-species data overestimates gamma under multi-species conditions.\n"
            f"  - Always verify against primary literature for critical applications.\n"
            f"[Refs] {ref}"
        )

    # ── Unit Conversion ────────────────────────────────────

    def _convert_units(self, p: dict) -> str:
        value = float(p.get("value", 0))
        from_unit = p.get("from_unit", "")
        to_unit = p.get("to_unit", "")

        conversions = {
            ("W/m2", "kW/m2"): 1e-3,
            ("kW/m2", "W/m2"): 1e3,
            ("W/m2", "MW/m2"): 1e-6,
            ("MW/m2", "W/m2"): 1e6,
            ("kW/m2", "MW/m2"): 1e-3,
            ("MW/m2", "kW/m2"): 1e3,
            ("Pa", "atm"): 1 / 101325,
            ("atm", "Pa"): 101325,
            ("Pa", "Torr"): 0.00750062,
            ("Torr", "Pa"): 133.322,
            ("m/s", "km/s"): 1e-3,
            ("km/s", "m/s"): 1e3,
        }

        # Temperature special handling
        if from_unit == "K" and to_unit == "C":
            return f"**Unit Conversion**: {value} K = **{value - 273.15:.2f} C**"
        if from_unit == "C" and to_unit == "K":
            return f"**Unit Conversion**: {value} C = **{value + 273.15:.2f} K**"

        factor = conversions.get((from_unit, to_unit))
        if factor is None:
            supported = "W/m2, kW/m2, MW/m2, Pa, atm, Torr, m/s, km/s, K, C"
            return f"[ERROR] Unsupported conversion: {from_unit} -> {to_unit}\nSupported: {supported}"

        result = value * factor
        return f"**Unit Conversion**: {value} {from_unit} = **{result:.6g} {to_unit}**"

    # ── Boundary Layer Thickness ──────────────────────────────────

    def _calc_boundary_layer(self, p: dict) -> str:
        x = float(p.get("x", 1.0))
        re = float(p.get("reynolds", 1e6))

        delta_lam = 5.0 * x / math.sqrt(re)
        delta_turb = 0.37 * x / (re**0.2)
        regime = "turbulent" if re > 5e5 else "laminar"

        return (
            f"**Boundary Layer Thickness (flat plate, zero pressure gradient)**\n"
            f"x = {x:.3f} m, Re_x = {re:.2e} ({regime})\n"
            f"Laminar delta = {delta_lam:.4e} m\n"
            f"Turbulent delta = {delta_turb:.4e} m\n\n"
            f"Reference: Schlichting & Gersten, Boundary-Layer Theory, 7th ed."
        )
