"""
假设生成器 —— AI Scientist 核心模块

从文献 Gap 到可验证科学假设，融入物理方程约束验证。
流程：文献检索 → Gap 识别 → 假设生成 → 物理约束验证 → 评分排序
"""

from __future__ import annotations

import json
from typing import Any

from core.action import Action
from core.llm import LLMInterface
from core.message import Message
from .physics_constraints import PhysicsConstraintLayer
from .search import LiteratureSearchTool
from .web_search import WebSearchTool


# ── Prompt 模板 ──────────────────────────────────────

HYPOTHESIS_GENERATION_PROMPT = """\
你是一名高超声速气固界面耦合研究领域的假设生成专家。

# 文献综述
{literature_review}

# 已知知识边界
{knowledge_boundary}

# 物理约束
{physics_constraints}

# 任务
1. 识别文献综述中的研究 Gap（使用层次化框架）
2. 为每个 Gap 生成可验证的科学假设
3. 用物理约束验证每个假设
4. 评分并排序

# Gap 识别框架
- Level 1 矛盾点：不同文献对同一现象给出矛盾结论
- Level 2 未覆盖区域：某些参数范围或工况缺乏数据
- Level 3 过度简化：现有模型忽略了重要的物理效应
- Level 4 跨尺度不一致：连续介质假设在稀薄区域失效

# 假设生成原则
- 必须可验证（通过计算、实验或文献对比）
- 必须符合物理定律（能量守恒、质量守恒、动量守恒）
- 必须有明确的成功判据
- 预测结果应尽可能具体（数值或趋势）

# 评分标准
- innovation_score（0-100）：与现有文献的差异度，越高越新颖
- feasibility_score（0-100）：验证所需资源是否可及，越高越可行
- scientific_value_score（0-100）：解决实际问题的程度，越高越有价值

# 输出格式（严格 JSON，不要多余文字）
{{
  "gap_analysis": [
    {{
      "level": 1,
      "description": "Gap 描述",
      "evidence": ["支持证据1", "支持证据2"],
      "hypotheses": [
        {{
          "hypothesis": "假设陈述",
          "prediction": "具体预测结果（数值或趋势）",
          "validation_method": "验证方法",
          "physics_constraints_involved": ["涉及的物理方程/约束"],
          "parameters": [
            {{"name": "参数名", "value": 数值或null}}
          ],
          "innovation_score": 80,
          "feasibility_score": 85,
          "scientific_value_score": 75
        }}
      ]
    }}
  ],
  "top_hypothesis_index": {{"gap": 0, "hypothesis": 0}}
}}
"""


# ── 假设生成器工具 ──────────────────────────────────


class HypothesisGenerator(Action):
    """假设生成器 —— 基于文献 Gap 生成可验证的科学假设。

    AI Scientist 的核心入口。从被动问答跃迁到主动假设生成。
    """

    name = "generate_hypothesis"
    description = (
        "基于气固热导领域文献，识别研究 Gap 并生成可验证的科学假设。"
        "支持 4 级 Gap 识别（矛盾/未覆盖/过度简化/跨尺度不一致），"
        "自动进行物理约束验证（催化效率、Kn数、守恒律等），"
        "输出结构化假设列表（含创新性/可行性/科学价值评分）。"
        "输入研究主题关键词，返回排序后的假设。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": (
                    "研究主题关键词，英文。"
                    "例如: 'catalytic recombination modeling gap', "
                    "'gas-surface interaction Knudsen transition', "
                    "'TPS material comparison'"
                ),
            },
            "max_hypotheses": {
                "type": "integer",
                "description": "最大假设数量，默认5，最多10",
                "default": 5,
            },
            "gap_level": {
                "type": "integer",
                "description": "Gap 层级过滤：0=全部，1=矛盾，2=未覆盖，3=过度简化，4=跨尺度",
                "default": 0,
            },
        },
        "required": ["topic"],
    }

    def __init__(
        self,
        llm: LLMInterface,
        search_tool: LiteratureSearchTool | None = None,
        web_tool: WebSearchTool | None = None,
    ):
        """构造器注入 LLM 实例和可选的检索工具。

        Args:
            llm: LLM 接口，用于 Gap 分析和假设生成
            search_tool: 本地文献检索工具，None 则内部创建
            web_tool: OpenAlex 外部检索工具，None 则内部创建
        """
        self.llm = llm
        self.search_tool = search_tool or LiteratureSearchTool()
        self.web_tool = web_tool or WebSearchTool()
        self.physics = PhysicsConstraintLayer()

    # ── 主入口 ────────────────────────────────────

    async def run(self, topic: str, max_hypotheses: int = 5, gap_level: int = 0) -> str:
        """执行假设生成流程。"""
        max_hypotheses = min(max_hypotheses, 10)
        gap_level = max(0, min(gap_level, 4))

        # Step 1: 本地文献检索
        try:
            lit_results = await self.search_tool.run(query=topic, top_k=10)
        except Exception as e:
            lit_results = f"[文献检索异常] {e}"

        # Step 2: OpenAlex 补充最新研究
        try:
            web_results = await self.web_tool.run(query=topic)
        except Exception as e:
            web_results = f"[OpenAlex 检索异常] {e}"

        # Step 3: 组装文献综述
        literature_review = f"## 本地文献库检索结果\n{lit_results}\n\n## OpenAlex 最新研究\n{web_results}"

        # Step 4: 构建 prompt
        knowledge_boundary = self._build_knowledge_boundary(topic)
        physics_constraints = self.physics.format_constraints_brief()

        prompt = HYPOTHESIS_GENERATION_PROMPT.format(
            literature_review=literature_review,
            knowledge_boundary=knowledge_boundary,
            physics_constraints=physics_constraints,
        )

        # Step 5: LLM 生成假设
        try:
            response = await self.llm.chat([Message.user(prompt)])
            raw_content = response.content
        except Exception as e:
            return json.dumps(
                {"error": f"LLM 调用失败: {e}", "literature_review": literature_review},
                indent=2,
                ensure_ascii=False,
            )

        # Step 6: 解析 LLM 输出
        parsed = self._parse_llm_output(raw_content)

        # Step 7: 物理约束验证
        parsed = self._validate_with_physics(parsed)

        # Step 8: Gap 层级过滤
        if gap_level > 0:
            parsed = self._filter_by_gap_level(parsed, gap_level)

        # Step 9: 截断并排序
        parsed = self._rank_and_truncate(parsed, max_hypotheses)

        # Step 10: 格式化输出
        return self._format_output(parsed, topic)

    # ── 内部方法 ──────────────────────────────────

    def _build_knowledge_boundary(self, topic: str) -> str:
        """构建已知知识边界描述。"""
        return (
            f"研究主题：{topic}\n"
            "已知边界：\n"
            "- 气固界面催化复合系数通常 γ ∈ [0, 1]\n"
            "- 连续介质假设在 Kn < 0.01 时成立\n"
            "- Fay-Riddell 公式仅适用于平衡催化壁面\n"
            "- 高超声速再入通常 Ma ∈ [5, 30]\n"
            "- 常见 TPS 材料：SiO₂, SiC, Al₂O₃, C-Phenolic, RCG\n"
            "- 高温气体效应在 T > 2000K 时显著\n"
        )

    def _parse_llm_output(self, raw: str) -> dict[str, Any]:
        """解析 LLM 输出为 JSON。"""
        # 尝试提取 JSON 块
        text = raw.strip()

        # 去掉 markdown 代码块包裹
        if text.startswith("```"):
            lines = text.split("\n")
            # 去首尾 ```行
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试找 JSON 花括号范围
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass

            # 解析失败，返回原始文本
            return {
                "gap_analysis": [],
                "raw_output": text,
                "parse_error": "LLM 输出无法解析为 JSON",
            }

    def _validate_with_physics(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """用物理约束验证每个假设。"""
        for gap in parsed.get("gap_analysis", []):
            for hyp in gap.get("hypotheses", []):
                # 收集参数
                params = {}
                for p in hyp.get("parameters", []):
                    if p.get("value") is not None:
                        params[p["name"]] = p["value"]

                # 验证
                valid, reason = self.physics.validate_hypothesis(
                    hyp.get("hypothesis", ""), params
                )
                hyp["physics_validation"] = {
                    "valid": valid,
                    "reason": reason,
                }

        return parsed

    def _filter_by_gap_level(self, parsed: dict[str, Any], gap_level: int) -> dict[str, Any]:
        """按 Gap 层级过滤。"""
        filtered = [
            gap for gap in parsed.get("gap_analysis", [])
            if gap.get("level") == gap_level
        ]
        parsed["gap_analysis"] = filtered
        return parsed

    def _rank_and_truncate(self, parsed: dict[str, Any], max_h: int) -> dict[str, Any]:
        """评分排序并截断。"""
        all_hypotheses = []

        for gap_idx, gap in enumerate(parsed.get("gap_analysis", [])):
            for hyp_idx, hyp in enumerate(gap.get("hypotheses", [])):
                # 综合评分 = 加权平均
                inn = hyp.get("innovation_score", 50)
                fea = hyp.get("feasibility_score", 50)
                sci = hyp.get("scientific_value_score", 50)
                # 权重：创新 0.35 + 可行 0.30 + 价值 0.35
                composite = 0.35 * inn + 0.30 * fea + 0.35 * sci

                # 物理验证未通过则降权
                if not hyp.get("physics_validation", {}).get("valid", True):
                    composite *= 0.5

                hyp["composite_score"] = round(composite, 1)
                hyp["_gap_idx"] = gap_idx
                hyp["_hyp_idx"] = hyp_idx
                all_hypotheses.append(hyp)

        # 按综合评分降序
        all_hypotheses.sort(key=lambda h: h.get("composite_score", 0), reverse=True)

        # 截断
        parsed["ranked_hypotheses"] = all_hypotheses[:max_h]

        # 更新 top_hypothesis_index
        if all_hypotheses:
            top = all_hypotheses[0]
            parsed["top_hypothesis_index"] = {
                "gap": top.get("_gap_idx", 0),
                "hypothesis": top.get("_hyp_idx", 0),
                "composite_score": top.get("composite_score", 0),
            }

        return parsed

    def _format_output(self, parsed: dict[str, Any], topic: str) -> str:
        """格式化输出为人类可读 + JSON 混合格式。"""
        # 如果解析失败，直接返回
        if "parse_error" in parsed:
            return (
                f"⚠️ 假设生成遇到问题：{parsed['parse_error']}\n\n"
                f"原始输出：\n{parsed.get('raw_output', '')}"
            )

        # 人类可读摘要
        lines = [f"🔬 假设生成报告 —— {topic}\n"]

        gap_analysis = parsed.get("gap_analysis", [])
        lines.append(f"识别到 {len(gap_analysis)} 个研究 Gap：\n")

        for i, gap in enumerate(gap_analysis):
            level = gap.get("level", "?")
            desc = gap.get("description", "无描述")
            evidence = gap.get("evidence", [])
            level_labels = {1: "矛盾点", 2: "未覆盖区域", 3: "过度简化", 4: "跨尺度不一致"}
            level_label = level_labels.get(level, f"Level {level}")

            lines.append(f"### Gap {i+1}（{level_label}）")
            lines.append(f"{desc}")
            if evidence:
                lines.append(f"证据：{'；'.join(evidence[:3])}")
            lines.append("")

            for j, hyp in enumerate(gap.get("hypotheses", [])):
                score = hyp.get("composite_score", "N/A")
                valid = hyp.get("physics_validation", {}).get("valid", True)
                status = "✅" if valid else "⚠️"
                lines.append(f"  {status} 假设 {j+1}（综合评分: {score}）")
                lines.append(f"  {hyp.get('hypothesis', '—')}")
                lines.append(f"  预测：{hyp.get('prediction', '—')}")
                lines.append(f"  验证方法：{hyp.get('validation_method', '—')}")
                if not valid:
                    reason = hyp.get("physics_validation", {}).get("reason", "")
                    lines.append(f"  ⚠️ 物理约束警告：{reason}")
                lines.append("")

        # 排序后的 Top 假设
        ranked = parsed.get("ranked_hypotheses", [])
        if ranked:
            lines.append("---")
            lines.append(f"🏆 Top {len(ranked)} 假设（按综合评分排序）：\n")
            for i, hyp in enumerate(ranked):
                score = hyp.get("composite_score", 0)
                valid = hyp.get("physics_validation", {}).get("valid", True)
                status = "✅" if valid else "⚠️"
                lines.append(f"{i+1}. {status} [{score}] {hyp.get('hypothesis', '—')}")
                lines.append(f"   预测：{hyp.get('prediction', '—')}")
            lines.append("")

        # 追加原始 JSON（供下游解析）
        lines.append("---")
        lines.append("📊 结构化数据（JSON）：")
        # 清理内部字段
        clean = self._clean_for_output(parsed)
        lines.append(json.dumps(clean, indent=2, ensure_ascii=False))

        return "\n".join(lines)

    def _clean_for_output(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """清理内部字段，输出干净 JSON。"""
        clean = {
            "gap_analysis": [],
            "ranked_hypotheses": [],
        }

        for gap in parsed.get("gap_analysis", []):
            gap_clean = {
                "level": gap.get("level"),
                "description": gap.get("description"),
                "evidence": gap.get("evidence", []),
                "hypotheses": [],
            }
            for hyp in gap.get("hypotheses", []):
                hyp_clean = {k: v for k, v in hyp.items() if not k.startswith("_")}
                gap_clean["hypotheses"].append(hyp_clean)
            clean["gap_analysis"].append(gap_clean)

        for hyp in parsed.get("ranked_hypotheses", []):
            hyp_clean = {k: v for k, v in hyp.items() if not k.startswith("_")}
            clean["ranked_hypotheses"].append(hyp_clean)

        if "top_hypothesis_index" in parsed:
            clean["top_hypothesis_index"] = parsed["top_hypothesis_index"]

        return clean
