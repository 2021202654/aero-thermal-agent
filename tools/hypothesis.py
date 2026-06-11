"""
Hypothesis Generator — AI Scientist Core Module

From literature Gap to verifiable scientific hypotheses, incorporating physics equation constraint validation.
Flow: Literature Retrieval → Gap Identification → Hypothesis Generation → Physics Constraint Validation → Scoring & Ranking
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


# ── Prompt Template ───────────────────────────────────

HYPOTHESIS_GENERATION_PROMPT = """\
You are a hypothesis generation expert in the field of hypersonic gas-solid interface coupling. Identify research gaps from literature review and generate verifiable hypotheses.

# Literature Review
{literature_review}

# Known Knowledge Boundaries
{knowledge_boundary}

# Physics Constraints
{physics_constraints}

# Gap Identification Framework
- L1 Contradiction: Different papers give conflicting conclusions on the same phenomenon
- L2 Uncovered Region: Parameter range or operating conditions lacking data
- L3 Over-simplification: Model ignores important physical effects
- L4 Cross-scale Inconsistency: Continuum assumption fails in rarefied regime

# Requirements
- Hypotheses must be verifiable, comply with physical laws, have clear success criteria
- description ≤ 50 characters, evidence ≤ 2 items, hypothesis ≤ 80 characters
- Output strict JSON only, no extra text

# Output Format
{{
  "gap_analysis": [
    {{
      "level": 1,
      "description": "Gap description (≤50 chars)",
      "evidence": ["Evidence 1"],
      "hypotheses": [
        {{
          "hypothesis": "Hypothesis (≤80 chars)",
          "prediction": "Prediction (value or trend)",
          "validation_method": "Validation method",
          "innovation_score": 80,
          "feasibility_score": 80,
          "scientific_value_score": 80
        }}
      ]
    }}
  ]
}}
"""


# ── Hypothesis Generator Tool ─────────────────────────


class HypothesisGenerator(Action):
    """Hypothesis Generator — generates verifiable scientific hypotheses based on literature gaps.

    Core entry point for AI Scientist. Transitions from passive Q&A to active hypothesis generation.
    """

    name = "generate_hypothesis"
    description = (
        "Based on gas-solid thermal conduction domain literature, identify research gaps and generate verifiable scientific hypotheses. "
        "Supports 4-level gap identification (contradiction / uncovered / over-simplified / cross-scale inconsistent), "
        "automatically performs physics constraint validation (catalytic efficiency, Kn number, conservation laws, etc.), "
        "outputs structured hypothesis list (including innovation / feasibility / scientific value scores). "
        "Input research topic keywords, return ranked hypotheses."
    )
    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": (
                    "Research topic keywords, in English. "
                    "Example: 'catalytic recombination modeling gap', "
                    "'gas-surface interaction Knudsen transition', "
                    "'TPS material comparison'"
                ),
            },
            "max_hypotheses": {
                "type": "integer",
                "description": "Maximum number of hypotheses, default 5, max 10",
                "default": 5,
            },
            "gap_level": {
                "type": "integer",
                "description": "Gap level filter: 0=all, 1=contradiction, 2=uncovered, 3=over-simplified, 4=cross-scale",
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
        """Constructor injects LLM instance and optional retrieval tools.

        Args:
            llm: LLM interface for gap analysis and hypothesis generation
            search_tool: Local literature retrieval tool; None creates internally
            web_tool: OpenAlex external retrieval tool; None creates internally
        """
        # Hypothesis generation requires longer output; create dedicated LLM instance (max_tokens=4096)
        from core.llm import LLMConfig
        self.llm = llm
        hyp_config = LLMConfig(
            base_url=llm.config.base_url,
            api_key=llm.config.api_key,
            model=llm.config.model,
            temperature=llm.config.temperature,
            max_tokens=8192,  # Hypothesis JSON is verbose; need sufficient space
            timeout=llm.config.timeout,
        )
        self._hypothesis_llm = LLMInterface(hyp_config)
        self.search_tool = search_tool or LiteratureSearchTool()
        self.web_tool = web_tool or WebSearchTool()
        self.physics = PhysicsConstraintLayer()

    # ── Main Entry ───────────────────────────────────

    async def run(self, topic: str, max_hypotheses: int = 5, gap_level: int = 0) -> str:
        """Execute hypothesis generation pipeline."""
        max_hypotheses = min(max_hypotheses, 10)
        gap_level = max(0, min(gap_level, 4))

        # Step 1: Local literature retrieval
        try:
            lit_results = await self.search_tool.run(query=topic, top_k=10)
        except Exception as e:
            lit_results = f"[Literature retrieval error] {e}"

        # Step 2: OpenAlex supplement for latest research
        try:
            web_results = await self.web_tool.run(query=topic)
        except Exception as e:
            web_results = f"[OpenAlex retrieval error] {e}"

        # Step 3: Assemble literature review
        literature_review = f"## Local Literature Database Retrieval Results\n{lit_results}\n\n## OpenAlex Latest Research\n{web_results}"

        # Step 4: Build prompt
        knowledge_boundary = self._build_knowledge_boundary(topic)
        physics_constraints = self.physics.format_constraints_brief()

        prompt = HYPOTHESIS_GENERATION_PROMPT.format(
            literature_review=literature_review,
            knowledge_boundary=knowledge_boundary,
            physics_constraints=physics_constraints,
        )

        # Step 5: LLM generate hypotheses (using dedicated long-output instance)
        try:
            response = await self._hypothesis_llm.chat([Message.user(prompt)])
            raw_content = response.content
        except Exception as e:
            return json.dumps(
                {"error": f"LLM call failed: {e}", "literature_review": literature_review},
                indent=2,
                ensure_ascii=False,
            )

        # Step 6: Parse LLM output
        parsed = self._parse_llm_output(raw_content)

        # Step 7: Physics constraint validation
        parsed = self._validate_with_physics(parsed)

        # Step 8: Gap level filtering
        if gap_level > 0:
            parsed = self._filter_by_gap_level(parsed, gap_level)

        # Step 9: Truncate and rank
        parsed = self._rank_and_truncate(parsed, max_hypotheses)

        # Step 10: Format output
        return self._format_output(parsed, topic)

    # ── Internal Methods ─────────────────────────────

    def _build_knowledge_boundary(self, topic: str) -> str:
        """Build known knowledge boundary description (concise version)."""
        return (
            f"Topic: {topic}\n"
            "Known boundaries: gamma in [0,1]; sigma_v, sigma_T in [0,1]; continuum Kn<0.01; "
            "Fay-Riddell only applicable for equilibrium catalytic wall; hypersonic Ma in [5,30]; "
            "TPS materials: SiO2, SiC, Al2O3, C-Phenolic, RCG; T>2000K high-temperature effects significant"
        )

    def _parse_llm_output(self, raw: str) -> dict[str, Any]:
        """Parse LLM output as JSON. Supports truncated JSON repair."""
        text = raw.strip()

        # Remove markdown code block wrapper
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try finding JSON brace range
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        # Try repairing truncated JSON: complete unclosed brackets
        if start >= 0:
            snippet = text[start:]
            repaired = self._repair_json(snippet)
            if repaired is not None:
                return repaired

        # Parse failed, return raw text
        return {
            "gap_analysis": [],
            "raw_output": text,
            "parse_error": "LLM output could not be parsed as JSON",
        }

    def _repair_json(self, snippet: str) -> dict[str, Any] | None:
        """Attempt to repair truncated JSON (complete brackets)."""
        # Count unclosed brackets
        open_braces = snippet.count("{") - snippet.count("}")
        open_brackets = snippet.count("[") - snippet.count("]")

        if open_braces < 0 or open_brackets < 0:
            return None  # Extra closing brackets, not simple truncation

        # Complete: close unclosed strings then brackets
        repaired = snippet.rstrip()

        # Try trimming last incomplete key-value pair
        for trim_pattern in [",\n", ",\r\n", ",", "\n", "\r\n"]:
            idx = repaired.rfind(trim_pattern)
            if idx > 0:
                repaired = repaired[:idx]
                break

        # Complete unclosed quotes
        if repaired.count('"') % 2 != 0:
            repaired += '"'

        # Complete brackets
        repaired += "]" * max(0, open_brackets)
        repaired += "}" * max(0, open_braces)

        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None

    def _validate_with_physics(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """Validate each hypothesis against physics constraints."""
        for gap in parsed.get("gap_analysis", []):
            for hyp in gap.get("hypotheses", []):
                # Collect parameters
                params = {}
                for p in hyp.get("parameters", []):
                    if p.get("value") is not None:
                        params[p["name"]] = p["value"]

                # Validate
                valid, reason = self.physics.validate_hypothesis(
                    hyp.get("hypothesis", ""), params
                )
                hyp["physics_validation"] = {
                    "valid": valid,
                    "reason": reason,
                }

        return parsed

    def _filter_by_gap_level(self, parsed: dict[str, Any], gap_level: int) -> dict[str, Any]:
        """Filter by gap level."""
        filtered = [
            gap for gap in parsed.get("gap_analysis", [])
            if gap.get("level") == gap_level
        ]
        parsed["gap_analysis"] = filtered
        return parsed

    def _rank_and_truncate(self, parsed: dict[str, Any], max_h: int) -> dict[str, Any]:
        """Score, rank, and truncate."""
        all_hypotheses = []

        for gap_idx, gap in enumerate(parsed.get("gap_analysis", [])):
            for hyp_idx, hyp in enumerate(gap.get("hypotheses", [])):
                # Composite score = weighted average
                inn = hyp.get("innovation_score", 50)
                fea = hyp.get("feasibility_score", 50)
                sci = hyp.get("scientific_value_score", 50)
                # Weights: innovation 0.35 + feasibility 0.30 + value 0.35
                composite = 0.35 * inn + 0.30 * fea + 0.35 * sci

                # Penalize if physics validation failed
                if not hyp.get("physics_validation", {}).get("valid", True):
                    composite *= 0.5

                hyp["composite_score"] = round(composite, 1)
                hyp["_gap_idx"] = gap_idx
                hyp["_hyp_idx"] = hyp_idx
                all_hypotheses.append(hyp)

        # Sort by composite score descending
        all_hypotheses.sort(key=lambda h: h.get("composite_score", 0), reverse=True)

        # Truncate
        parsed["ranked_hypotheses"] = all_hypotheses[:max_h]

        # Update top_hypothesis_index
        if all_hypotheses:
            top = all_hypotheses[0]
            parsed["top_hypothesis_index"] = {
                "gap": top.get("_gap_idx", 0),
                "hypothesis": top.get("_hyp_idx", 0),
                "composite_score": top.get("composite_score", 0),
            }

        return parsed

    def _format_output(self, parsed: dict[str, Any], topic: str) -> str:
        """Format output as human-readable + JSON mixed format."""
        # If parse failed, return clean summary (avoid polluting LLM context with truncated JSON)
        if "parse_error" in parsed:
            raw = parsed.get("raw_output", "")
            preview = raw[:300].replace("\n", " ") if raw else ""
            return (
                f"Hypothesis generation encountered an issue: {parsed['parse_error']}. "
                f"LLM output may have been truncated. "
                f"Try narrowing the search scope or reducing max_hypotheses."
                f"\n\nOutput preview (first 300 chars): {preview}..."
                f"\n\nPlease adjust the topic parameter or lower max_hypotheses and retry."
            )

        # Human-readable summary
        lines = [f"Hypothesis Generation Report -- {topic}\n"]

        gap_analysis = parsed.get("gap_analysis", [])
        lines.append(f"Identified {len(gap_analysis)} research Gap(s):\n")

        for i, gap in enumerate(gap_analysis):
            level = gap.get("level", "?")
            desc = gap.get("description", "No description")
            evidence = gap.get("evidence", [])
            level_labels = {1: "Contradiction", 2: "Uncovered Region", 3: "Over-simplified", 4: "Cross-scale Inconsistent"}
            level_label = level_labels.get(level, f"Level {level}")

            lines.append(f"### Gap {i+1} ({level_label})")
            lines.append(f"{desc}")
            if evidence:
                lines.append(f"Evidence: {'; '.join(evidence[:3])}")
            lines.append("")

            for j, hyp in enumerate(gap.get("hypotheses", [])):
                score = hyp.get("composite_score", "N/A")
                valid = hyp.get("physics_validation", {}).get("valid", True)
                status = "[OK]" if valid else "[WARN]"
                lines.append(f"  {status} Hypothesis {j+1} (Composite Score: {score})")
                lines.append(f"  {hyp.get('hypothesis', '—')}")
                lines.append(f"  Prediction: {hyp.get('prediction', '—')}")
                lines.append(f"  Validation Method: {hyp.get('validation_method', '—')}")
                if not valid:
                    reason = hyp.get("physics_validation", {}).get("reason", "")
                    lines.append(f"  [WARN] Physics constraint warning: {reason}")
                lines.append("")

        # Ranked top hypotheses
        ranked = parsed.get("ranked_hypotheses", [])
        if ranked:
            lines.append("---")
            lines.append(f"Top {len(ranked)} Hypotheses (ranked by composite score):\n")
            for i, hyp in enumerate(ranked):
                score = hyp.get("composite_score", 0)
                valid = hyp.get("physics_validation", {}).get("valid", True)
                status = "[OK]" if valid else "[WARN]"
                lines.append(f"{i+1}. {status} [{score}] {hyp.get('hypothesis', '—')}")
                lines.append(f"   Prediction: {hyp.get('prediction', '—')}")
            lines.append("")

        # Append raw JSON (for downstream parsing)
        lines.append("---")
        lines.append("Structured Data (JSON):")
        clean = self._clean_for_output(parsed)
        lines.append(json.dumps(clean, indent=2, ensure_ascii=False))

        return "\n".join(lines)

    def _clean_for_output(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """Remove internal fields, output clean JSON."""
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
