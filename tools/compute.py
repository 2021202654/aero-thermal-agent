"""
气动热参数计算工具 —— 领域专用数值计算

覆盖：驻点热流 / Knudsen数 / 催化系数 / 单位换算 / 边界层厚度
所有公式标注出处，符合 Agent 约束"计算可验证"。
"""

from __future__ import annotations

import math

from core.action import Action


class AeroThermalComputeTool(Action):
    """气动热参数计算 —— 执行高超声速领域常用工程计算。"""

    name = "compute_aerothermal"
    description = (
        "执行高超声速气动热领域的工程计算。"
        "可计算驻点热流密度（Fay-Riddell/Sutton-Graves公式）、"
        "Knudsen数（流态判断：连续/过渡/自由分子流）、"
        "催化复合系数速查（SiO₂/SiC/Al₂O₃/Pt等）、"
        "单位换算（W/m²↔kW/m², Pa↔atm, K↔°C等）、"
        "边界层厚度估算。"
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
                "description": "计算类型",
            },
            "params": {
                "type": "object",
                "description": (
                    "计算参数，按 calc_type 不同：\n"
                    "- stagnation_heat_flux: velocity(m/s), radius(m), density(kg/m³)\n"
                    "- knudsen_number: characteristic_length(m), 可选 temperature(K), pressure(Pa)\n"
                    "- catalytic_coefficient: material(SiO₂/SiC/Al₂O₃/Pt/quartz/RCG), temperature(K)\n"
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
            return f"[错误] 未知计算类型: {calc_type}。可选: {list(handlers.keys())}"
        try:
            return handler(params)
        except Exception as e:
            return f"[计算错误] {calc_type}: {e}"

    # ── Fay-Riddell / Sutton-Graves 驻点热流 ────────

    def _calc_stagnation_heat_flux(self, p: dict) -> str:
        v = float(p.get("velocity", 0))
        r = float(p.get("radius", 1.0))
        rho = float(p.get("density", 1.2))

        k = 1.83e-4  # 地球大气常数 (W/m² units)
        q_w = k * math.sqrt(rho / r) * v**3

        return (
            f"**驻点热流密度（Sutton-Graves 简化式）**\n"
            f"输入：V = {v:.0f} m/s, R_n = {r:.3f} m, ρ = {rho:.4f} kg/m³\n"
            f"q_w = {q_w:.2e} W/m² = {q_w/1e3:.2f} kW/m² = {q_w/1e6:.4f} MW/m²\n\n"
            f"Ref: Fay & Riddell, J. Aeronaut. Sci. 25(2), 1958\n"
            f"     Sutton & Graves, NASA TR R-376, 1973\n"
            f"⚠️ 假设：平衡催化壁面，完全气体，层流。精确计算需考虑真实气体效应。"
        )

    # ── Knudsen 数 ──────────────────────────────────

    def _calc_knudsen(self, p: dict) -> str:
        L = float(p.get("characteristic_length", 1.0))
        T = float(p.get("temperature", 300))
        pressure = float(p.get("pressure", 101325))

        k_B = 1.380649e-23
        d_air = 3.7e-10
        mfp = k_B * T / (math.sqrt(2) * math.pi * d_air**2 * pressure)

        kn = mfp / L

        if kn < 0.001:
            regime = "连续流（NS 方程适用）"
        elif kn < 0.1:
            regime = "滑移流（需速度滑移+温度跳跃边界条件）"
        elif kn < 10:
            regime = "过渡流（DSMC 适用，NS 失效）"
        else:
            regime = "自由分子流"

        return (
            f"**Knudsen 数**\n"
            f"λ = {mfp:.3e} m（T={T:.0f} K, p={pressure:.0f} Pa）\n"
            f"L = {L:.3e} m\n"
            f"Kn = {kn:.4e} → **{regime}**\n\n"
            f"参考：Bird, Molecular Gas Dynamics and DSMC, 1994"
        )

    # ── 催化复合系数速查 ────────────────────────────

    def _lookup_catalytic(self, p: dict) -> str:
        material = p.get("material", "SiO2").strip()
        T = float(p.get("temperature", 1500))
        species = p.get("species", "O").strip().upper()  # O / N / mixed

        # ═══════════════════════════════════════════════════════
        # 催化复合系数数据库
        #
        # 格式：γ_300, γ_2000, T_act(K), info, references
        # 模型：γ(T) ≈ γ_300 * exp(T_act * (1/300 - 1/T))
        #
        # IMPORTANT LIMITATIONS:
        # 1. 默认数据为 O-atom 复合（N-atom 一般低 2-5×）
        # 2. 单物种测量 ≠ 多物种共存（表面位点竞争效应）
        # 3. γ 强烈依赖表面状态、气压、来流组分、测量方法
        # 4. 不同实验装置（电弧/ICP/shock tube）结果可有数量级差异
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
            # (γ_O_300, γ_O_2000, T_act_O, info, refs)
            "sio2":  (8e-4, 1.5e-2, 800,
                      "SiO2/石英/HRSI 表面 O-atom 复合 (Scott AIAA 80-1477; Nasuti AIAA 96-1888)",
                      "Scott AIAA 80-1477 (1980); Nasuti et al. AIAA 96-1888 (1996); Stewart AIAA 2011-3750"),
            "sio2_o":(8e-4, 1.5e-2, 800,
                      "SiO2 表面 O-atom 复合",
                      "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "sio2_n":(2e-4, 3e-3, 600,
                      "SiO2 表面 N-atom 复合 (γ_N 通常比 γ_O 低 2-5x)",
                      "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "sio₂":  (8e-4, 1.5e-2, 800,
                      "SiO2/石英/HRSI 表面 O-atom 复合",
                      "Scott AIAA 80-1477; Nasuti AIAA 96-1888; Stewart AIAA 2011-3750"),
            "quartz":(5e-4, 8e-3, 700,
                      "石英 (熔融石英) O-atom 复合，低催化活性",
                      "Scott AIAA 80-1477; Balat-Pichelin JECS 2006"),
            "rcg":   (8e-4, 1.2e-2, 750,
                      "Reaction Cured Glass (HRSI 涂层) O-atom 复合",
                      "Stewart AIAA 2011-3750; Scott AIAA 80-1477"),
            "sic":   (8e-3, 8e-2, 1200,
                      "SiC 表面 O-atom 复合 (He et al. Appl Surf Sci 2024)",
                      "Scott AIAA 80-1477; He et al. Appl Surf Sci 664, 2024, 160263"),
            "sic_o": (8e-3, 8e-2, 1200,
                      "SiC 表面 O-atom 复合",
                      "Scott AIAA 80-1477; He et al. 2024"),
            "sic_n": (2e-3, 2e-2, 1000,
                      "SiC 表面 N-atom 复合",
                      "Scott AIAA 80-1477; estimated"),
            "al2o3": (3e-3, 4e-2, 1000,
                      "Al2O3 表面 O-atom 复合，中等催化活性",
                      "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "al2o3_o":(3e-3, 4e-2, 1000,
                       "Al2O3 表面 O-atom 复合",
                       "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "al₂o₃": (3e-3, 4e-2, 1000,
                      "Al2O3 表面 O-atom 复合，中等催化活性",
                      "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "pt":    (5e-2, 3e-1, -2000,
                      "Pt 表面 (高催化活性，高温饱和效应 γ 下降)",
                      "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "platinum":(5e-2, 3e-1, -2000,
                        "Pt 表面 (高催化活性，高温饱和效应 γ 下降)",
                        "Scott AIAA 80-1477; Nasuti AIAA 96-1888"),
            "si₃n₄": (1e-3, 6e-3, 900,
                      "Si3N4 表面 O-atom 复合 (文献数据稀少，待补充验证)",
                      "待补充验证"),
        }

        key = material.lower().strip()
        if species == "N":
            # 尝试匹配 N-specific 条目
            n_key = f"{key}_n"
            if n_key in DB:
                γ_300, γ_2000, T_act, info, ref = DB[n_key]
            else:
                # fallback: 用 O 数据但标注清楚
                γ_300, γ_2000, T_act, info, ref = DB.get(key, DB.get(f"{key}_o", None) or DB["sio2"])
                info += " [WARNING: using O-atom data for N-atom query; N gamma typically 2-5x lower]"
        elif species == "O":
            o_key = f"{key}_o"
            if o_key in DB:
                γ_300, γ_2000, T_act, info, ref = DB[o_key]
            else:
                γ_300, γ_2000, T_act, info, ref = DB.get(key, DB["sio2"])
        else:
            # mixed / unspecified
            γ_300, γ_2000, T_act, info, ref = DB.get(key, DB["sio2"])

        # Arrhenius 预测
        T_clamped = max(300, min(3000, T))
        try:
            γ_T = γ_300 * math.exp(T_act * (1/300 - 1/T_clamped))
        except OverflowError:
            γ_T = γ_2000 if T_act > 0 else γ_300

        # 钳制
        γ_low = min(γ_300, γ_2000) * 0.5
        γ_high = max(γ_300, γ_2000) * 2.0
        γ_T = max(γ_low, min(γ_high, γ_T))

        # 流态 + 不确定度提示
        regime_notes = []
        if T > 2000:
            regime_notes.append("T > 2000K: 离解效应显著，Arrhenius 外推不确定性增大")
        if T < 300:
            regime_notes.append("T < 300K: 低温数据稀少，外推不可靠")
        species_note = ""
        if species not in ("O", "N"):
            species_note = (
                "\n[IMPORTANT] Species not specified. Defaulting to O-atom recombination."
                "\nActual gamma depends on whether recombining species is O, N, or O+N mixture."
                "\nN-atom gamma is typically 2-5x lower than O-atom on oxide surfaces."
                "\nUnder multi-species conditions, competitive surface coverage reduces individual gamma values."
            )

        return (
            f"**{material} 催化复合系数 (Species: {species})**\n"
            f"T = {T:.0f} K -> gamma = {γ_T:.2e} (Arrhenius model estimate)\n"
            f"Reference range: gamma(300K) = {γ_300:.2e} to gamma(2000K) = {γ_2000:.2e}\n"
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

    # ── 单位换算 ────────────────────────────────────

    def _convert_units(self, p: dict) -> str:
        value = float(p.get("value", 0))
        from_unit = p.get("from_unit", "")
        to_unit = p.get("to_unit", "")

        conversions = {
            ("W/m²", "kW/m²"): 1e-3,
            ("kW/m²", "W/m²"): 1e3,
            ("W/m²", "MW/m²"): 1e-6,
            ("MW/m²", "W/m²"): 1e6,
            ("kW/m²", "MW/m²"): 1e-3,
            ("MW/m²", "kW/m²"): 1e3,
            ("Pa", "atm"): 1 / 101325,
            ("atm", "Pa"): 101325,
            ("Pa", "Torr"): 0.00750062,
            ("Torr", "Pa"): 133.322,
            ("m/s", "km/s"): 1e-3,
            ("km/s", "m/s"): 1e3,
        }

        # 温度特殊处理
        if from_unit == "K" and to_unit == "°C":
            return f"**单位换算**：{value} K = **{value - 273.15:.2f} °C**"
        if from_unit == "°C" and to_unit == "K":
            return f"**单位换算**：{value} °C = **{value + 273.15:.2f} K**"

        factor = conversions.get((from_unit, to_unit))
        if factor is None:
            supported = "W/m², kW/m², MW/m², Pa, atm, Torr, m/s, km/s, K, °C"
            return f"[错误] 不支持的换算: {from_unit} → {to_unit}\n支持：{supported}"

        result = value * factor
        return f"**单位换算**：{value} {from_unit} = **{result:.6g} {to_unit}**"

    # ── 边界层厚度 ──────────────────────────────────

    def _calc_boundary_layer(self, p: dict) -> str:
        x = float(p.get("x", 1.0))
        re = float(p.get("reynolds", 1e6))

        delta_lam = 5.0 * x / math.sqrt(re)
        delta_turb = 0.37 * x / (re**0.2)
        regime = "湍流" if re > 5e5 else "层流"

        return (
            f"**边界层厚度（平板，零压力梯度）**\n"
            f"x = {x:.3f} m, Re_x = {re:.2e}（{regime}）\n"
            f"层流 δ = {delta_lam:.4e} m\n"
            f"湍流 δ = {delta_turb:.4e} m\n\n"
            f"参考：Schlichting & Gersten, Boundary-Layer Theory, 7th ed."
        )
