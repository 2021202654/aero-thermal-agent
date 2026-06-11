"""
Physics Constraint Validation Layer — Gas-Solid Interface Core Physics Equations and Boundary Conditions

Pure-rule validation, no LLM dependency.
Used after hypothesis generation to verify compliance with physical laws and filter out hypotheses that violate basic constraints.
"""

from __future__ import annotations

from typing import Any


class PhysicsConstraintLayer:
    """Gas-solid interface physics constraint validation layer.

    Covers:
    - Parameter value range constraints (gamma, sigma_v, sigma_T must be within physical ranges)
    - Flow regime judgment constraints (Kn number → flow regime mapping)
    - Conservation law simplified checks (energy / mass / momentum)
    - Model applicability constraints (Fay-Riddell, DSMC, etc.)
    """

    # ── Parameter Physical Bounds ─────────────────────

    PARAM_BOUNDS: dict[str, dict[str, Any]] = {
        "catalytic_efficiency": {
            "symbol": "gamma",
            "min": 0.0,
            "max": 1.0,
            "unit": "-",
            "description": "Catalytic recombination efficiency, 0=fully non-catalytic, 1=fully catalytic",
        },
        "momentum_accommodation": {
            "symbol": "sigma_v",
            "min": 0.0,
            "max": 1.0,
            "unit": "-",
            "description": "Momentum accommodation coefficient",
        },
        "energy_accommodation": {
            "symbol": "sigma_T",
            "min": 0.0,
            "max": 1.0,
            "unit": "-",
            "description": "Energy accommodation coefficient (temperature jump coefficient)",
        },
        "knudsen": {
            "symbol": "Kn",
            "min": 0.0,
            "max": 1e6,
            "unit": "-",
            "description": "Knudsen number lambda/L",
        },
        "mach": {
            "symbol": "Ma",
            "min": 0.0,
            "max": 50.0,
            "unit": "-",
            "description": "Mach number; hypersonic typically Ma > 5",
        },
        "temperature": {
            "symbol": "T",
            "min": 0.0,
            "max": 50000.0,
            "unit": "K",
            "description": "Temperature",
        },
        "pressure": {
            "symbol": "p",
            "min": 0.0,
            "max": 1e9,
            "unit": "Pa",
            "description": "Pressure",
        },
        "heat_flux": {
            "symbol": "q_w",
            "min": 0.0,
            "max": 1e9,
            "unit": "W/m^2",
            "description": "Wall heat flux density",
        },
        "stagnation_enthalpy": {
            "symbol": "h_0",
            "min": 0.0,
            "max": 5e7,
            "unit": "J/kg",
            "description": "Stagnation enthalpy",
        },
    }

    # ── Kn → Flow Regime Mapping ───────────────────

    FLOW_REGIMES: list[dict[str, Any]] = [
        {"name": "continuum", "label": "Continuum", "kn_min": 0.0, "kn_max": 0.001,
         "model": "Navier-Stokes (no-slip BC)"},
        {"name": "slip", "label": "Slip Flow", "kn_min": 0.001, "kn_max": 0.1,
         "model": "NS + slip/temperature-jump BC"},
        {"name": "transition", "label": "Transition", "kn_min": 0.1, "kn_max": 10.0,
         "model": "DSMC / Boltzmann equation"},
        {"name": "free_molecular", "label": "Free Molecular", "kn_min": 10.0, "kn_max": 1e6,
         "model": "Free molecular flow theory"},
    ]

    # ── Model Applicability Ranges ─────────────────

    MODEL_RANGES: dict[str, dict[str, Any]] = {
        "fay_riddell": {
            "description": "Fay-Riddell stagnation-point heat flux formula",
            "applicable": "Equilibrium catalytic wall, continuum, laminar",
            "kn_max": 0.01,
            "requires": ["equilibrium_catalytic_wall"],
        },
        "sutton_graves": {
            "description": "Sutton-Graves simplified stagnation-point heat flux",
            "applicable": "Engineering estimate, fully catalytic wall",
            "kn_max": 0.01,
        },
        "dsmc": {
            "description": "Direct Simulation Monte Carlo",
            "applicable": "Rarefied gas, Kn > 0.01",
            "kn_min": 0.01,
        },
        "maxwell_slip": {
            "description": "Maxwell slip boundary condition",
            "applicable": "Slip flow regime, 0.001 < Kn < 0.1",
            "kn_min": 0.001,
            "kn_max": 0.1,
        },
    }

    # ── Initialization ─────────────────────────────

    def __init__(self):
        # Alias mapping: support multiple parameter name variants
        self._aliases: dict[str, str] = {
            "gamma": "catalytic_efficiency",
            "γ": "catalytic_efficiency",
            "sigma_v": "momentum_accommodation",
            "σ_v": "momentum_accommodation",
            "sigma_t": "energy_accommodation",
            "σ_t": "energy_accommodation",
            "σ_T": "energy_accommodation",
            "kn": "knudsen",
            "knudsen_number": "knudsen",
            "ma": "mach",
            "mach_number": "mach",
            "t": "temperature",
            "temp": "temperature",
            "p": "pressure",
            "q_w": "heat_flux",
            "q_wdot": "heat_flux",
            "heat_flux_density": "heat_flux",
            "h0": "stagnation_enthalpy",
            "h_0": "stagnation_enthalpy",
        }

    # ── Public Interface ───────────────────────────

    def validate_hypothesis(
        self,
        hypothesis_text: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Validate whether a hypothesis violates physical laws.

        Args:
            hypothesis_text: Hypothesis text
            params: Dict of physical parameters mentioned in the hypothesis

        Returns:
            (valid, reason): Whether it passes + reason explanation
        """
        if params is None:
            params = {}

        violations: list[str] = []

        # 1. Parameter value range check
        for param_name, value in params.items():
            ok, msg = self._check_value_bounds(param_name, value)
            if not ok:
                violations.append(msg)

        # 2. Flow regime consistency check
        kn = self._resolve_param(params, "knudsen")
        regime = params.get("flow_regime", "").lower() if isinstance(params.get("flow_regime"), str) else ""
        if kn is not None and regime:
            ok, msg = self._check_flow_regime(float(kn), regime)
            if not ok:
                violations.append(msg)

        # 3. Conservation law check
        ok, msg = self._check_conservation(params)
        if not ok:
            violations.append(msg)

        # 4. Text-level constraint check (keyword scan)
        text_violations = self._check_text_constraints(hypothesis_text)
        violations.extend(text_violations)

        if violations:
            reason = "; ".join(violations)
            return False, reason

        return True, "Passed physics constraint validation"

    def get_regime(self, kn: float) -> dict[str, Any]:
        """Return flow regime info given Kn number."""
        for regime in self.FLOW_REGIMES:
            if regime["kn_min"] <= kn < regime["kn_max"]:
                return regime
        # Kn extremely large
        return self.FLOW_REGIMES[-1]

    def get_model_applicability(self, model_name: str, kn: float | None = None) -> dict[str, Any]:
        """Check model applicability under given conditions."""
        model = self.MODEL_RANGES.get(model_name.lower().replace("-", "_"))
        if model is None:
            return {"applicable": None, "reason": f"Unknown model: {model_name}"}

        if kn is not None:
            kn_min = model.get("kn_min", 0.0)
            kn_max = model.get("kn_max", 1e6)
            if kn < kn_min or kn > kn_max:
                return {
                    "applicable": False,
                    "reason": f"{model['description']}: Kn={kn:.4e} outside applicable range [{kn_min}, {kn_max}]",
                }

        return {"applicable": True, "reason": model["applicable"]}

    def format_constraints_brief(self) -> str:
        """Return concise constraint summary for prompt injection."""
        lines = ["Gas-solid interface physics constraints:"]
        for key, info in self.PARAM_BOUNDS.items():
            lines.append(
                f"  {info['symbol']} ({key}) in [{info['min']}, {info['max']}] {info['unit']} -- {info['description']}"
            )
        lines.append("Flow regime determination:")
        for r in self.FLOW_REGIMES:
            lines.append(f"  Kn in [{r['kn_min']}, {r['kn_max']}) -> {r['label']} ({r['model']})")
        return "\n".join(lines)

    # ── Internal Methods ─────────────────────────────

    def _resolve_param(self, params: dict, canonical_name: str) -> Any | None:
        """Resolve value from parameter dict (supports aliases)."""
        if canonical_name in params:
            return params[canonical_name]
        for alias, canonical in self._aliases.items():
            if canonical == canonical_name and alias in params:
                return params[alias]
        return None

    def _check_value_bounds(self, param_name: str, value: Any) -> tuple[bool, str]:
        """Check whether parameter value is within physical range."""
        canonical = self._aliases.get(param_name, param_name)
        bounds = self.PARAM_BOUNDS.get(canonical)
        if bounds is None:
            return True, ""  # Unknown parameter, skip check

        try:
            v = float(value)
        except (TypeError, ValueError):
            return True, ""  # Non-numeric, skip

        if v < bounds["min"] or v > bounds["max"]:
            return (
                False,
                f"{bounds['symbol']} ({canonical}) = {v}, "
                f"outside physical range [{bounds['min']}, {bounds['max']}] {bounds['unit']} -- {bounds['description']}",
            )

        return True, ""

    def _check_flow_regime(self, kn: float, claimed_regime: str) -> tuple[bool, str]:
        """Check whether flow regime judgment is correct."""
        actual = self.get_regime(kn)
        actual_names = {actual["name"], actual["label"]}

        matched = False
        for name in actual_names:
            if name in claimed_regime:
                matched = True
                break

        if not matched:
            return (
                False,
                f"Kn={kn:.4e} corresponds to {actual['label']} ({actual['name']}), "
                f"but hypothesis claims '{claimed_regime}', flow regime judgment inconsistent",
            )

        return True, ""

    def _check_conservation(self, params: dict[str, Any]) -> tuple[bool, str]:
        """Conservation law simplified check."""
        # Energy conservation: q_w <= h_0 (wall heat flux cannot exceed stagnation enthalpy)
        q_w = self._resolve_param(params, "heat_flux")
        h0 = self._resolve_param(params, "stagnation_enthalpy")
        if q_w is not None and h0 is not None:
            try:
                if float(q_w) > float(h0):
                    return False, f"Wall heat flux q_w={q_w} exceeds stagnation enthalpy h_0={h0}, violates energy conservation"
            except (TypeError, ValueError):
                pass

        return True, ""

    def _check_text_constraints(self, text: str) -> list[str]:
        """Text-level constraint check (keyword scan)."""
        violations = []
        text_lower = text.lower()

        # Faster-than-light / super-physical constraints
        impossible_patterns = [
            ("faster than light", "Speed cannot exceed the speed of light"),
            ("perpetual motion", "Perpetual motion violates thermodynamics"),
            ("efficiency > 100%", "Efficiency cannot exceed 100%"),
        ]

        for pattern, reason in impossible_patterns:
            if pattern in text_lower:
                violations.append(reason)

        return violations
