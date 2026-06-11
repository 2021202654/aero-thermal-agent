"""
PDF Paper Parsing Tool — Text Extraction / Metadata / Section Structure / Key Parameter Identification

Based on PyMuPDF (fitz), 3-5x faster than pdfplumber.
Supported modes:
- metadata: title/author/creation date
- full: full text
- sections: section heading structure
- parameters: automatic aero-thermal key parameter identification
- search: keyword location
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.action import Action


class PDFAnalysisTool(Action):
    """PDF Paper Parsing — Text/Metadata/Section/Parameter Extraction."""

    name = "parse_pdf"
    description = (
        "Parse PDF paper files, extract text content, metadata, section structure, and key parameters. "
        "Supported modes: metadata (title/author), full (full text), sections (section headings), "
        "parameters (aero-thermal parameter auto-identification), search (keyword location). "
        "Applicable: reading papers, data extraction, citation verification, literature review."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path or path relative to project root for the PDF file. Example: '06_论文工作区/01_参考文献/HMT-D-26-01279.pdf'",
            },
            "mode": {
                "type": "string",
                "enum": ["metadata", "full", "sections", "parameters", "search"],
                "description": (
                    "Parsing mode:\n"
                    "- metadata: extract metadata such as title, author, creation date\n"
                    "- full: extract all text content\n"
                    "- sections: extract section heading structure\n"
                    "- parameters: auto-identify aero-thermal key parameters (temperature, pressure, heat flux, catalytic coefficient, etc.)\n"
                    "- search: search for specified keywords in PDF"
                ),
                "default": "metadata",
            },
            "keyword": {
                "type": "string",
                "description": "Search keyword when mode='search'. Example: 'catalytic recombination'",
            },
            "max_pages": {
                "type": "integer",
                "description": "Maximum number of pages to parse. Default 50, 0 means all. Used to limit parsing scope for large files.",
                "default": 50,
            },
            "extract_tables": {
                "type": "boolean",
                "description": "Whether to attempt table extraction (only valid when mode='full'). May be slow.",
                "default": False,
            },
        },
        "required": ["file_path"],
    }

    # ── Aero-thermal Parameter Regex Patterns ──────────────────────────
    PARAM_PATTERNS = {
        "Temperature": [
            (r"(\d+\.?\d*)\s*[Kk]\b", "K"),
            (r"(\d+\.?\d*)\s*°C", "°C"),
            (r"(\d+\.?\d*)\s*℃", "°C"),
            (r"temperature[:\s]*(\d+\.?\d*)\s*[Kk]", "K"),
        ],
        "Heat Flux Density": [
            (r"(\d+\.?\d*)\s*[Ww]/[m㎡][²2]\b", "W/m²"),
            (r"(\d+\.?\d*)\s*[kK][Ww]/[m㎡][²2]\b", "kW/m²"),
            (r"(\d+\.?\d*)\s*[Mm][Ww]/[m㎡][²2]\b", "MW/m²"),
            (r"heat\s*flux[:\s]*(\d+\.?\d*)", "W/m²"),
        ],
        "Pressure": [
            (r"(\d+\.?\d*)\s*[Pp][Aa]\b", "Pa"),
            (r"(\d+\.?\d*)\s*[kK][Pp][Aa]\b", "kPa"),
            (r"(\d+\.?\d*)\s*[aA][tT][mM]\b", "atm"),
            (r"(\d+\.?\d*)\s*[bB][aA][rR]\b", "bar"),
        ],
        "Velocity": [
            (r"(\d+\.?\d*)\s*[mM]/[sS]\b", "m/s"),
            (r"(\d+\.?\d*)\s*[kK][mM]/[sS]\b", "km/s"),
            (r"Mach\s*(\d+\.?\d*)", "Ma"),
        ],
        "Catalytic Recombination Coefficient": [
            (r"[γγ][_ ]?\w*\s*[=≈～~]\s*(\d+\.?\d*(?:[eE][+-]?\d+)?)", ""),
            (r"catalytic[-\s]?\w*\s*coefficient[:\s]*(\d+\.?\d*(?:[eE][+-]?\d+)?)", ""),
            (r"recombination[-\s]?\w*\s*coefficient[:\s]*(\d+\.?\d*(?:[eE][+-]?\d+)?)", ""),
        ],
        "Altitude/Distance": [
            (r"(\d+\.?\d*)\s*[kK][mM]\b", "km"),
            (r"(\d+\.?\d*)\s*[mM][mM]\b", "mm"),
            (r"(\d+\.?\d*)\s*[μµm][mM]\b", "μm"),
        ],
        "Knudsen Number": [
            (r"[Kk]nudsen[-\s]?\w*\s*[=≈～~]?\s*(\d+\.?\d*(?:[eE][+-]?\d+)?)", ""),
            (r"[Kk][Nn]\s*[=≈～~]\s*(\d+\.?\d*(?:[eE][+-]?\d+)?)", ""),
        ],
    }

    def __init__(self):
        self._fitz = None

    def _ensure_fitz(self):
        """Lazily import PyMuPDF."""
        if self._fitz is None:
            try:
                import fitz
                self._fitz = fitz
            except ImportError:
                raise ImportError(
                    "PyMuPDF is required: pip install pymupdf\n"
                    "Or use conda: conda install -c conda-forge pymupdf"
                )

    async def run(
        self,
        file_path: str,
        mode: str = "metadata",
        keyword: str = "",
        max_pages: int = 50,
        extract_tables: bool = False,
    ) -> str:
        # ── Path Resolution ──────────────────────────────────
        pdf_path = Path(file_path)
        if not pdf_path.is_absolute():
            # Relative path, based on Agent directory (05_AI_Agent/)
            agent_dir = Path(__file__).parent.parent
            pdf_path = (agent_dir / file_path).resolve()

        if not pdf_path.exists():
            return f"✗ File not found: {pdf_path}"

        if pdf_path.suffix.lower() != ".pdf":
            return f"✗ Not a PDF file: {pdf_path.name}"

        try:
            self._ensure_fitz()
        except ImportError as e:
            return f"✗ {e}"

        # ── Open PDF ──────────────────────────────────
        try:
            doc = self._fitz.open(str(pdf_path))
        except Exception as e:
            return f"✗ Cannot open PDF: {e}"

        result = ""

        try:
            if mode == "metadata":
                result = self._extract_metadata(doc, pdf_path)
            elif mode == "full":
                result = self._extract_full_text(doc, pdf_path, max_pages)
            elif mode == "sections":
                result = self._extract_sections(doc, pdf_path, max_pages)
            elif mode == "parameters":
                result = self._extract_parameters(doc, pdf_path, max_pages)
            elif mode == "search":
                result = self._search_keyword(doc, pdf_path, keyword, max_pages)
            else:
                result = f"✗ Unknown mode: {mode}"
        finally:
            doc.close()

        return result

    # ── Mode: metadata ───────────────────────────────

    def _extract_metadata(self, doc, pdf_path: Path) -> str:
        """Extract PDF metadata."""
        meta = doc.metadata
        toc = doc.get_toc()  # table of contents
        pages = doc.page_count

        title = meta.get("title", "Unknown")
        author = meta.get("author", "Unknown")
        subject = meta.get("subject", "")
        creator = meta.get("creator", "")
        creation_date = meta.get("creationDate", "")

        lines = [
            f"## PDF Metadata: {pdf_path.name}",
            f"",
            f"**Title**: {title}",
            f"**Author**: {author}",
            f"**Pages**: {pages}",
        ]
        if subject:
            lines.append(f"**Subject**: {subject}")
        if creation_date:
            lines.append(f"**Creation Date**: {creation_date[:10]}")
        if creator:
            lines.append(f"**Creator**: {creator}")

        if toc:
            lines.append(f"\n### Table of Contents (first 15 entries)")
            for level, heading, page_num in toc[:15]:
                indent = "  " * (level - 1)
                lines.append(f"{indent}- [{heading}] → Page {page_num}")

        return "\n".join(lines)

    # ── Mode: full ───────────────────────────────────

    def _extract_full_text(self, doc, pdf_path: Path, max_pages: int) -> str:
        """Extract full text."""
        pages_to_read = min(doc.page_count, max_pages) if max_pages > 0 else doc.page_count

        lines = [
            f"## {pdf_path.name}",
            f"**Total Pages**: {doc.page_count} | **Read**: {pages_to_read} pages\n",
        ]

        total_chars = 0
        char_limit = 15000  # avoid returning excessively long content

        for page_num in range(pages_to_read):
            page = doc[page_num]
            text = page.get_text("text")

            if text.strip():
                lines.append(f"### ── Page {page_num + 1} ──")
                if total_chars + len(text) > char_limit:
                    remaining = char_limit - total_chars
                    lines.append(text[:remaining])
                    lines.append(f"\n⚠️ **Text truncated**: Reached {char_limit} character limit, remaining pages not read.")
                    break
                lines.append(text)
                total_chars += len(text)

        return "\n".join(lines)

    # ── Mode: sections ───────────────────────────────

    def _extract_sections(self, doc, pdf_path: Path, max_pages: int) -> str:
        """Extract section heading structure."""
        pages_to_read = min(doc.page_count, max_pages) if max_pages > 0 else doc.page_count

        lines = [
            f"## Section Structure: {pdf_path.name}",
            f"",
        ]

        section_pattern = re.compile(
            r"^(\d+(?:\.\d+)*)\s+(.+)|"
            r"^(Abstract|Introduction|Method|Experiment|Result|Discussion|Conclusion|Reference|Appendix|"
            r"Nomenclature|Acknowledgment)",
            re.IGNORECASE
        )

        found_sections: list[tuple[int, str]] = []

        for page_num in range(pages_to_read):
            page = doc[page_num]
            # Check table of contents first
            blocks = page.get_text("blocks")
            for block in blocks:
                text = block[4] if len(block) > 4 else ""  # block format: (x0,y0,x1,y1,text,block_no,block_type)

                # Only take text blocks with larger font (likely headings)
                # block[2]-block[0] = x range, block[3]-block[1] = y range
                is_bold = False  # fitz does not provide font info directly, use heuristic
                text_stripped = text.strip()

                if 10 < len(text_stripped) < 150:  # heading length
                    match = section_pattern.match(text_stripped)
                    if match:
                        found_sections.append((page_num + 1, text_stripped))

        if found_sections:
            for page, section in found_sections:
                lines.append(f"- [Page {page}] {section}")
        else:
            lines.append("No explicit section headings detected. Consider using 'full' mode to view full text.")

        return "\n".join(lines)

    # ── Mode: parameters ─────────────────────────────

    def _extract_parameters(self, doc, pdf_path: Path, max_pages: int) -> str:
        """Auto-identify aero-thermal key parameters."""
        pages_to_read = min(doc.page_count, max_pages) if max_pages > 0 else doc.page_count

        lines = [
            f"## Aero-thermal Parameter Identification: {pdf_path.name}",
            f"**Scanned Pages**: {pages_to_read}\n",
        ]

        full_text = ""
        for page_num in range(pages_to_read):
            full_text += doc[page_num].get_text("text") + "\n"

        found_any = False
        for category, patterns in self.PARAM_PATTERNS.items():
            category_results = []
            for pattern, unit in patterns:
                for match in re.finditer(pattern, full_text, re.IGNORECASE):
                    value = match.group(1) if match.lastindex else match.group(0)
                    # Get context (40 chars before and after)
                    start = max(0, match.start() - 40)
                    end = min(len(full_text), match.end() + 40)
                    context = full_text[start:end].replace("\n", " ").strip()
                    # Highlight matched value
                    display = f"{value} {unit}".strip() if unit else value
                    category_results.append((display, context))

            if category_results:
                found_any = True
                lines.append(f"### {category}")
                # Deduplicate (take first 10 unique values)
                seen = set()
                unique = []
                for val, ctx in category_results:
                    if val not in seen:
                        seen.add(val)
                        unique.append((val, ctx))
                for val, ctx in unique[:10]:
                    lines.append(f"- **{val}** — `...{ctx}...`")
                if len(unique) > 10:
                    lines.append(f"  *... {len(unique) - 10} more matches*")
                lines.append("")

        if not found_any:
            lines.append("No aero-thermal related parameters identified. May be a non-aero-thermal paper, or PDF text extraction quality is low.")

        return "\n".join(lines)

    # ── Mode: search ─────────────────────────────────

    def _search_keyword(self, doc, pdf_path: Path, keyword: str, max_pages: int) -> str:
        """Search for keywords in PDF."""
        if not keyword:
            return "✗ Please provide a search keyword (keyword parameter)."

        pages_to_read = min(doc.page_count, max_pages) if max_pages > 0 else doc.page_count

        lines = [
            f"## Search '{keyword}' — {pdf_path.name}",
            f"**Scanned Pages**: {pages_to_read}\n",
        ]

        found_count = 0
        for page_num in range(pages_to_read):
            page = doc[page_num]
            text = page.get_text("text")

            if keyword.lower() in text.lower():
                found_count += 1
                # Extract matching context
                idx = text.lower().find(keyword.lower())
                start = max(0, idx - 80)
                end = min(len(text), idx + len(keyword) + 80)
                snippet = text[start:end].replace("\n", " ").strip()

                lines.append(f"**Page {page_num + 1}**: `...{snippet}...`")

                if found_count >= 20:
                    lines.append(f"\n⚠️ Showing first 20 matches, there may be more.")
                    break

        if found_count == 0:
            lines.append(f"'{keyword}' not found.")

        return "\n".join(lines)
