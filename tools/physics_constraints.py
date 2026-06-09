"""
物理约束验证层 —— 气固界面核心物理方程与边界条件

纯规则验证，不依赖 LLM。
用于在假设生成后检验是否符合物理定律，过滤违反基本约束的假设。
"""

from __future__ import annotations

from typing import Any


class PhysicsConstraintLayer:
    """气固界面物理约束验证层。

    覆盖：
    - 参数值域约束（γ, σ_v, σ_T 等必须在物理范围内）
    - 流态判断约束（Kn 数 → 流态映射）
    - 守恒律简化检验（能量/质量/动量）
    - 模型适用范围约束（Fay-Riddell, DSMC 等）
    """

    # ── 参数物理边界 ──────────────────────────────

    PARAM_BOUNDS: dict[str, dict[str, Any]] = {
        "catalytic_efficiency": {
            "symbol": "γ",
            "min": 0.0,
            "max": 1.0,
            "unit": "-",
            "description": "催化复合效率，0=完全非催化，1=完全催化",
        },
        "momentum_accommodation": {
            "symbol": "σ_v",
            "min": 0.0,
            "max": 1.0,
            "unit": "-",
            "description": "动量协调系数",
        },
        "energy_accommodation": {
            "symbol": "σ_T",
            "min": 0.0,
            "max": 1.0,
            "unit": "-",
            "description": "能量协调系数（温度跳跃系数）",
        },
        "knudsen": {
            "symbol": "Kn",
            "min": 0.0,
            "max": 1e6,
            "unit": "-",
            "description": "克努森数 λ/L",
        },
        "mach": {
            "symbol": "Ma",
            "min": 0.0,
            "max": 50.0,
            "unit": "-",
            "description": "马赫数，高超声速通常 Ma > 5",
        },
        "temperature": {
            "symbol": "T",
            "min": 0.0,
            "max": 50000.0,
            "unit": "K",
            "description": "温度",
        },
        "pressure": {
            "symbol": "p",
            "min": 0.0,
            "max": 1e9,
            "unit": "Pa",
            "description": "压力",
        },
        "heat_flux": {
            "symbol": "q_w",
            "min": 0.0,
            "max": 1e9,
            "unit": "W/m²",
            "description": "壁面热流密度",
        },
        "stagnation_enthalpy": {
            "symbol": "h_0",
            "min": 0.0,
            "max": 5e7,
            "unit": "J/kg",
            "description": "驻点焓",
        },
    }

    # ── Kn → 流态映射 ──────────────────────────────

    FLOW_REGIMES: list[dict[str, Any]] = [
        {"name": "continuum", "label": "连续流", "kn_min": 0.0, "kn_max": 0.001,
         "model": "Navier-Stokes（无滑移边界）"},
        {"name": "slip", "label": "滑移流", "kn_min": 0.001, "kn_max": 0.1,
         "model": "NS + 滑移/温度跳跃边界条件"},
        {"name": "transition", "label": "过渡流", "kn_min": 0.1, "kn_max": 10.0,
         "model": "DSMC / Boltzmann 方程"},
        {"name": "free_molecular", "label": "自由分子流", "kn_min": 10.0, "kn_max": 1e6,
         "model": "自由分子流理论"},
    ]

    # ── 模型适用范围 ──────────────────────────────

    MODEL_RANGES: dict[str, dict[str, Any]] = {
        "fay_riddell": {
            "description": "Fay-Riddell 驻点热流公式",
            "applicable": "平衡催化壁面，连续流，层流",
            "kn_max": 0.01,
            "requires": ["equilibrium_catalytic_wall"],
        },
        "sutton_graves": {
            "description": "Sutton-Graves 简化驻点热流",
            "applicable": "工程估算，完全催化壁面",
            "kn_max": 0.01,
        },
        "dsmc": {
            "description": "直接仿真蒙特卡罗",
            "applicable": "稀薄气体，Kn > 0.01",
            "kn_min": 0.01,
        },
        "maxwell_slip": {
            "description": "Maxwell 滑移边界条件",
            "applicable": "滑移流，0.001 < Kn < 0.1",
            "kn_min": 0.001,
            "kn_max": 0.1,
        },
    }

    # ── 初始化 ────────────────────────────────────

    def __init__(self):
        # 别名映射：支持多种参数名写法
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

    # ── 公开接口 ──────────────────────────────────

    def validate_hypothesis(
        self,
        hypothesis_text: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """验证假设是否违反物理定律。

        Args:
            hypothesis_text: 假设文本
            params: 假设中涉及的物理参数 dict

        Returns:
            (valid, reason): 是否通过 + 原因说明
        """
        if params is None:
            params = {}

        violations: list[str] = []

        # 1. 参数值域检查
        for param_name, value in params.items():
            ok, msg = self._check_value_bounds(param_name, value)
            if not ok:
                violations.append(msg)

        # 2. 流态一致性检查
        kn = self._resolve_param(params, "knudsen")
        regime = params.get("flow_regime", "").lower() if isinstance(params.get("flow_regime"), str) else ""
        if kn is not None and regime:
            ok, msg = self._check_flow_regime(float(kn), regime)
            if not ok:
                violations.append(msg)

        # 3. 守恒律检查
        ok, msg = self._check_conservation(params)
        if not ok:
            violations.append(msg)

        # 4. 文本级约束检查（关键词扫描）
        text_violations = self._check_text_constraints(hypothesis_text)
        violations.extend(text_violations)

        if violations:
            reason = "；".join(violations)
            return False, reason

        return True, "通过物理约束检验"

    def get_regime(self, kn: float) -> dict[str, Any]:
        """根据 Kn 数返回流态信息。"""
        for regime in self.FLOW_REGIMES:
            if regime["kn_min"] <= kn < regime["kn_max"]:
                return regime
        # Kn 极大
        return self.FLOW_REGIMES[-1]

    def get_model_applicability(self, model_name: str, kn: float | None = None) -> dict[str, Any]:
        """检查模型在给定条件下的适用性。"""
        model = self.MODEL_RANGES.get(model_name.lower().replace("-", "_"))
        if model is None:
            return {"applicable": None, "reason": f"未知模型: {model_name}"}

        if kn is not None:
            kn_min = model.get("kn_min", 0.0)
            kn_max = model.get("kn_max", 1e6)
            if kn < kn_min or kn > kn_max:
                return {
                    "applicable": False,
                    "reason": f"{model['description']}：Kn={kn:.4e} 不在适用范围 [{kn_min}, {kn_max}]",
                }

        return {"applicable": True, "reason": model["applicable"]}

    def format_constraints_brief(self) -> str:
        """返回约束简述，供 prompt 注入。"""
        lines = ["气固界面物理约束："]
        for key, info in self.PARAM_BOUNDS.items():
            lines.append(
                f"  {info['symbol']}（{key}）∈ [{info['min']}, {info['max']}] {info['unit']} — {info['description']}"
            )
        lines.append("流态判定：")
        for r in self.FLOW_REGIMES:
            lines.append(f"  Kn ∈ [{r['kn_min']}, {r['kn_max']}) → {r['label']}（{r['model']}）")
        return "\n".join(lines)

    # ── 内部方法 ──────────────────────────────────

    def _resolve_param(self, params: dict, canonical_name: str) -> Any | None:
        """从参数 dict 中解析值（支持别名）。"""
        if canonical_name in params:
            return params[canonical_name]
        for alias, canonical in self._aliases.items():
            if canonical == canonical_name and alias in params:
                return params[alias]
        return None

    def _check_value_bounds(self, param_name: str, value: Any) -> tuple[bool, str]:
        """检查参数值是否在物理范围内。"""
        canonical = self._aliases.get(param_name, param_name)
        bounds = self.PARAM_BOUNDS.get(canonical)
        if bounds is None:
            return True, ""  # 未知参数，不检查

        try:
            v = float(value)
        except (TypeError, ValueError):
            return True, ""  # 非数值，跳过

        if v < bounds["min"] or v > bounds["max"]:
            return (
                False,
                f"{bounds['symbol']}（{canonical}）= {v}，"
                f"超出物理范围 [{bounds['min']}, {bounds['max']}] {bounds['unit']} — {bounds['description']}",
            )

        return True, ""

    def _check_flow_regime(self, kn: float, claimed_regime: str) -> tuple[bool, str]:
        """检查流态判断是否正确。"""
        actual = self.get_regime(kn)
        # 宽松匹配：claimed_regime 包含 actual name 或 label
        actual_names = {actual["name"], actual["label"]}

        matched = False
        for name in actual_names:
            if name in claimed_regime:
                matched = True
                break

        if not matched:
            return (
                False,
                f"Kn={kn:.4e} 对应 {actual['label']}（{actual['name']}），"
                f"但假设声称 '{claimed_regime}'，流态判断不一致",
            )

        return True, ""

    def _check_conservation(self, params: dict[str, Any]) -> tuple[bool, str]:
        """守恒律简化检验。"""
        # 能量守恒：q_w ≤ h_0（壁面热流不能超过驻点焓）
        q_w = self._resolve_param(params, "heat_flux")
        h0 = self._resolve_param(params, "stagnation_enthalpy")
        if q_w is not None and h0 is not None:
            try:
                if float(q_w) > float(h0):
                    return False, f"壁面热流 q_w={q_w} 超过驻点焓 h_0={h0}，违反能量守恒"
            except (TypeError, ValueError):
                pass

        return True, ""

    def _check_text_constraints(self, text: str) -> list[str]:
        """文本级约束检查（关键词扫描）。"""
        violations = []
        text_lower = text.lower()

        # 超光速 / 超物理约束
        impossible_patterns = [
            ("超过光速", "速度不能超过光速"),
            ("perpetual motion", "永动机违反热力学定律"),
            ("永动机", "永动机违反热力学定律"),
            ("efficiency > 100%", "效率不能超过 100%"),
            ("效率 > 100%", "效率不能超过 100%"),
        ]

        for pattern, reason in impossible_patterns:
            if pattern in text_lower:
                violations.append(reason)

        return violations
