"""
Report Generation Tool -- Outputs Agent research findings as structured Markdown reports

Supports two modes:
1. generate_report: Generate complete research report (with title, timestamp, content, references)
2. export_finding:  Append a single structured research finding to the current workspace

All reports are saved to 05_AI_Agent/reports/ directory.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.action import Action


class ReportTool(Action):
    """Research report generation -- persists Agent reasoning results as Markdown reports."""

    name = "generate_report"
    description = (
        "Generates a structured Markdown report from current research task findings, computation process, "
        "and literature references, saving to reports/ directory. Suitable for: research conclusion archival, "
        "experimental records, literature review synthesis. "
        "Reports are automatically timestamped; literature references should include DOI."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Report title, concise and clear. Example: 'SiO2 Catalytic Recombination Coefficient Literature Review'",
            },
            "content": {
                "type": "string",
                "description": (
                    "Report body, supports Markdown format. Should include: research background, methods/tools, "
                    "main findings, numerical results (if any), references (with DOI), "
                    "uncertainty notes, conclusions and recommendations."
                ),
            },
            "findings": {
                "type": "array",
                "description": "Optional list of structured research findings, each containing claim/evidence/confidence/source",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string", "description": "Research finding or conclusion, summarized in one sentence"},
                        "evidence": {"type": "string", "description": "Evidence or reasoning supporting this conclusion"},
                        "confidence": {
                            "type": "string",
                            "enum": ["High", "Medium", "Low"],
                            "description": "Confidence level: High=directly supported by literature or verified by computation, Medium=indirect inference, Low=unverified speculation",
                        },
                        "source": {"type": "string", "description": "Evidence source (DOI, literature title, or tool name)"},
                    },
                    "required": ["claim", "confidence"],
                },
            },
            "references": {
                "type": "array",
                "description": "List of references cited in the report",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Literature title"},
                        "doi": {"type": "string", "description": "DOI (without https://doi.org/ prefix)"},
                        "year": {"type": "string", "description": "Publication year"},
                        "relevance": {"type": "string", "description": "Relevance to this research"},
                    },
                    "required": ["title"],
                },
            },
        },
        "required": ["title", "content"],
    }

    def __init__(self, output_dir: str | Path | None = None):
        if output_dir:
            self._output_dir = Path(output_dir)
        else:
            self._output_dir = Path(__file__).parent.parent / "reports"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        title: str,
        content: str,
        findings: list[dict] | None = None,
        references: list[dict] | None = None,
    ) -> str:
        """Generate Markdown report and save.

        If references is empty but content contains DOI strings,
        auto-extracts them as fallback references.
        """
        timestamp = datetime.now()
        safe_title = self._sanitize_filename(title)
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{safe_title}.md"
        filepath = self._output_dir / filename

        # ── Auto-extract DOIs from content as fallback ──
        effective_refs = references or []
        if not effective_refs and content:
            extracted = self._extract_dois_from_text(content)
            if extracted:
                effective_refs = [
                    {"title": f"DOI: {doi}", "doi": doi, "year": "?"}
                    for doi in extracted
                ]

        report = self._build_report(
            title=title,
            content=content,
            findings=findings or [],
            references=effective_refs,
            timestamp=timestamp,
        )

        filepath.write_text(report, encoding="utf-8")

        return (
            f"Report generated: {filename}\n"
            f"Save path: {filepath}\n"
            f"Report length: {len(report)} characters\n"
            f"Structured findings: {len(findings or [])} entries\n"
            f"References: {len(references or [])} citations"
        )

    # ── Internal Methods ────────────────────────────────────

    def _build_report(
        self,
        title: str,
        content: str,
        findings: list[dict],
        references: list[dict],
        timestamp: datetime,
    ) -> str:
        lines = [
            f"# {title}",
            "",
            f"**Generated at**: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Generated by**: AeroThermalExpert Agent (ReportTool)",
            "",
            "---",
            "",
            "## Research Content",
            "",
            content,
        ]

        if findings:
            lines.extend([
                "",
                "---",
                "",
                "## Structured Findings",
                "",
                "| # | Conclusion | Confidence | Evidence Source |",
                "|---|------|--------|----------|",
            ])
            for i, f in enumerate(findings, 1):
                claim = f.get("claim", "--")
                confidence = f.get("confidence", "--")
                evidence = f.get("evidence", "")
                source = f.get("source", "")
                ev_src = f"{evidence} ({source})" if source else evidence
                lines.append(f"| {i} | {claim} | **{confidence}** | {ev_src} |")
            lines.append("")

        if references:
            lines.extend([
                "---",
                "",
                "## References",
                "",
            ])
            for i, ref in enumerate(references, 1):
                title = ref.get("title", "Unknown title")
                doi = ref.get("doi", "")
                year = ref.get("year", "?")
                relevance = ref.get("relevance", "")
                doi_str = f" [{doi}](https://doi.org/{doi})" if doi else ""
                lines.append(f"{i}. **{title}**{doi_str} ({year})")
                if relevance:
                    lines.append(f"   - Relevance: {relevance}")
                lines.append("")

        lines.extend([
            "---",
            "",
            f"*This report was automatically generated by the Gas-Solid Thermal Coupling AI Agent. Content requires human review and verification.*",
        ])

        return "\n".join(lines)

    @staticmethod
    def _sanitize_filename(title: str) -> str:
        """Sanitize illegal characters from filename."""
        safe = title.replace("/", "_").replace("\\", "_").replace(":", ":")
        safe = safe.replace("*", "").replace("?", "").replace('"', "")
        safe = safe.replace("<", "").replace(">", "").replace("|", "")
        # Limit length
        if len(safe) > 60:
            safe = safe[:60]
        return safe.strip()

    @staticmethod
    def _extract_dois_from_text(text: str) -> list[str]:
        """Extract DOI strings from arbitrary text.

        Handles common formats:
          - https://doi.org/10.1038/nature12373
          - doi:10.1038/nature12373
          - 10.1038/nature12373
          - DOI: 10.1038/nature12373
        Returns deduplicated list of bare DOIs (no prefix).
        """
        import re

        # Match 10.XXXX/... pattern, allowing for newline/space separators
        pattern = r'(?:https?://(?:dx\.)?doi\.org/)?(?:doi:?\s*)?(10\.\d{4,}/[^\s一-鿿.,;:()\]\'\"。；：""''（）【】]+)'
        matches = re.findall(pattern, text, re.IGNORECASE)
        seen = set()
        dois = []
        for m in matches:
            # Strip trailing punctuation that commonly follows DOI
            cleaned = re.sub(r'[\.,;:)\]\'"。、《》]+$', '', m.strip())
            if cleaned and cleaned not in seen and len(cleaned) > 8:
                seen.add(cleaned)
                dois.append(cleaned)
        return dois


class ExportFindingTool(Action):
    """Single finding export -- lightweight, suitable for recording findings one by one in ReAct loop."""

    name = "export_finding"
    description = (
        "Appends a single research conclusion to a Markdown log in the findings/ directory. "
        "Suitable for gradually recording findings during reasoning, instead of generating a full report after completion."
    )
    parameters = {
        "type": "object",
        "properties": {
            "claim": {
                "type": "string",
                "description": "Research finding or conclusion, summarized in one sentence",
            },
            "evidence": {
                "type": "string",
                "description": "Supporting evidence (literature citation, computation result, logical reasoning)",
            },
            "confidence": {
                "type": "string",
                "enum": ["High", "Medium", "Low"],
                "description": "Confidence level: High/Medium/Low",
            },
            "source": {
                "type": "string",
                "description": "Evidence source (DOI, literature title, or tool name)",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Classification tags, e.g. ['catalytic', 'SiO2', 'experiment']",
            },
        },
        "required": ["claim", "confidence"],
    }

    def __init__(self, output_dir: str | Path | None = None):
        if output_dir:
            self._output_dir = Path(output_dir)
        else:
            self._output_dir = Path(__file__).parent.parent / "findings"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._output_dir / "findings_log.md"

    async def run(
        self,
        claim: str,
        confidence: str = "Medium",
        evidence: str = "",
        source: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """Append a finding to the findings log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tags_str = " ".join(f"`{t}`" for t in (tags or []))

        entry = (
            f"### {claim}\n"
            f"- **Timestamp**: {timestamp}\n"
            f"- **Confidence**: {confidence}\n"
        )
        if evidence:
            entry += f"- **Evidence**: {evidence}\n"
        if source:
            entry += f"- **Source**: {source}\n"
        if tags_str:
            entry += f"- **Tags**: {tags_str}\n"
        entry += "\n"

        # Append write
        with open(self._log_file, "a", encoding="utf-8") as f:
            # If file doesn't exist or is empty, write header
            if not self._log_file.exists() or self._log_file.stat().st_size == 0:
                f.write("# Research Findings Log\n\n> Automatically recorded by AeroThermalExpert Agent\n\n")
            f.write(entry)

        return (
            f"Finding recorded\n"
            f"Conclusion: {claim}\n"
            f"Confidence: {confidence}\n"
            f"Log file: {self._log_file}"
        )
