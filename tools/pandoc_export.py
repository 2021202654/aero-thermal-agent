"""
Pandoc Format Export Tool — Markdown Report → LaTeX / DOCX / PDF

In DSW Linux environment, invokes system pandoc to convert Agent-generated Markdown research reports
into LaTeX, DOCX, or PDF formats ready for academic paper use.

Dependencies: pandoc must be installed (apt-get install pandoc)
             texlive-xetex required for PDF output (apt-get install texlive-xetex)
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from core.action import Action


class PandocExportTool(Action):
    """Markdown → LaTeX/DOCX/PDF Format Export."""

    name = "export_document"
    description = (
        "Convert Markdown research reports to LaTeX, DOCX, or PDF format. "
        "Depends on system pandoc (must be pre-installed). "
        "LaTeX output supports XeLaTeX engine (CJK Chinese compatible), with optional templates and .bib bibliography files. "
        "Applicable: paper draft export, citation formatting, integration with Overleaf/Word workflows."
    )
    parameters = {
        "type": "object",
        "properties": {
            "input_path": {
                "type": "string",
                "description": (
                    "Input Markdown file path (relative to Agent directory or absolute path). "
                    "Example: 'reports/20260602_190824_report.md'"
                ),
            },
            "output_format": {
                "type": "string",
                "enum": ["latex", "docx", "pdf"],
                "description": (
                    "Output format:\n"
                    "- latex: LaTeX source file (.tex), suitable for Overleaf or local editing\n"
                    "- docx: Word document, suitable for supervisor annotations, submission conversion\n"
                    "- pdf: directly generate PDF (requires system texlive-xetex)"
                ),
                "default": "latex",
            },
            "template": {
                "type": "string",
                "description": (
                    "Optional LaTeX template file path. Only effective when output_format='latex' or 'pdf'. "
                    "Example Elsevier template: 'templates/elsevier.latex'"
                ),
            },
            "reference_docx": {
                "type": "string",
                "description": (
                    "Optional DOCX reference style file path. Only effective when output_format='docx'. "
                    "Used to control font/paragraph/margin styles of the output Word document."
                ),
            },
            "bibliography": {
                "type": "string",
                "description": (
                    "Optional .bib bibliography file path. pandoc will automatically use --citeproc to process citations. "
                    "Example: 'refs.bib'"
                ),
            },
            "output_dir": {
                "type": "string",
                "description": "Output directory. Default is exports/ subdirectory under the Markdown file's directory.",
            },
        },
        "required": ["input_path", "output_format"],
    }

    # ── Format → Extension + pandoc Parameter Mapping ──────────────

    FORMAT_MAP = {
        "latex": {
            "ext": ".tex",
            "pandoc_fmt": "latex",
            "extra_args": ["--pdf-engine=xelatex"],
            "standalone": True,
        },
        "docx": {
            "ext": ".docx",
            "pandoc_fmt": "docx",
            "extra_args": [],
            "standalone": True,
        },
        "pdf": {
            "ext": ".pdf",
            "pandoc_fmt": "pdf",
            "extra_args": [
                "--pdf-engine=xelatex",
                "-V", "CJKmainfont=Noto Serif CJK SC",
                "-V", "CJKsansfont=Noto Sans CJK SC",
                "-V", "CJKmonofont=Noto Sans Mono CJK SC",
            ],
            "standalone": True,
        },
    }

    def __init__(self):
        self._pandoc_path: str | None = None

    def _find_pandoc(self) -> str:
        """Find pandoc executable path."""
        if self._pandoc_path:
            return self._pandoc_path

        # Try which first
        found = shutil.which("pandoc")
        if found:
            self._pandoc_path = found
            return found

        raise FileNotFoundError(
            "pandoc not found. Please install first:\n"
            "  Ubuntu/Debian: sudo apt-get install pandoc\n"
            "  Conda:         conda install -c conda-forge pandoc\n"
            "  Windows:       winget install Pandoc.Pandoc"
        )

    async def run(
        self,
        input_path: str,
        output_format: str = "latex",
        template: str = "",
        reference_docx: str = "",
        bibliography: str = "",
        output_dir: str = "",
    ) -> str:
        # ── Check pandoc ───────────────────────────────
        try:
            pandoc = self._find_pandoc()
        except FileNotFoundError as e:
            return f"✗ {e}"

        # ── Path Resolution ──────────────────────────────────
        md_path = Path(input_path)
        if not md_path.is_absolute():
            agent_dir = Path(__file__).parent.parent
            md_path = (agent_dir / input_path).resolve()

        if not md_path.exists():
            return f"✗ Input file does not exist: {md_path}"

        if md_path.suffix.lower() not in (".md", ".markdown", ".txt"):
            return f"⚠ Input file is not Markdown format: {md_path.name} (will still attempt conversion)"

        # ── Output Path ──────────────────────────────────
        fmt_cfg = self.FORMAT_MAP[output_format]
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = md_path.parent / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = md_path.stem
        out_path = out_dir / f"{stem}{fmt_cfg['ext']}"

        # ── Template Path Resolution ──────────────────────────────
        if template:
            tmpl_path = Path(template)
            if not tmpl_path.is_absolute():
                agent_dir = Path(__file__).parent.parent
                tmpl_path = (agent_dir / template).resolve()
            if not tmpl_path.exists():
                return f"✗ Template file does not exist: {tmpl_path}"

        if reference_docx:
            ref_path = Path(reference_docx)
            if not ref_path.is_absolute():
                agent_dir = Path(__file__).parent.parent
                ref_path = (agent_dir / reference_docx).resolve()
            if not ref_path.exists():
                return f"✗ Reference style file does not exist: {ref_path}"

        if bibliography:
            bib_path = Path(bibliography)
            if not bib_path.is_absolute():
                agent_dir = Path(__file__).parent.parent
                bib_path = (agent_dir / bibliography).resolve()
            if not bib_path.exists():
                return f"✗ Bibliography file does not exist: {bib_path}"

        # ── Build pandoc Command ──────────────────────────
        cmd = [
            pandoc,
            str(md_path),
            "-f", "markdown+smart",
            "-t", fmt_cfg["pandoc_fmt"],
            "-o", str(out_path),
        ]

        if fmt_cfg["standalone"]:
            cmd.append("--standalone")
        cmd.extend(fmt_cfg["extra_args"])

        # Metadata
        cmd.extend(["--metadata", f"title={stem.replace('_', ' ')}"])
        cmd.extend(["--metadata", "date=\\today"])

        # Bibliography processing
        if bibliography:
            cmd.append("--citeproc")
            cmd.extend(["--bibliography", str(bib_path)])

        # Template
        if template and output_format in ("latex", "pdf"):
            cmd.extend(["--template", str(tmpl_path)])

        # DOCX reference style
        if reference_docx and output_format == "docx":
            cmd.extend(["--reference-doc", str(ref_path)])

        # ── Execute ─────────────────────────────────────
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # pandoc is usually fast, but large files + citeproc may be slow
            )
        except subprocess.TimeoutExpired:
            return "⏱ Pandoc conversion timeout (120s). File may be too large, or citeproc processing complex citations took too long."
        except Exception as e:
            return f"✗ Pandoc execution error: {e}"

        # ── Result Analysis ─────────────────────────────────
        lines = []
        if proc.returncode != 0:
            lines.append(f"✗ **Conversion failed** (exit code {proc.returncode})")
            stderr = proc.stderr.strip()
            if stderr:
                lines.append(f"```\n{stderr[:1000]}\n```")
            return "\n".join(lines)

        # Success
        file_size = out_path.stat().st_size
        lines.extend([
            f"✓ **Export successful**",
            f"",
            f"| Item | Details |",
            f"|------|---------|",
            f"| Input | {md_path.name}",
            f"| Output | {out_path.name}",
            f"| Format | {output_format.upper()}",
            f"| Size | {file_size:,} bytes",
            f"| Path | {out_path}",
        ])

        if output_format == "latex":
            lines.extend([
                "",
                "📝 **Next steps**:",
                f"- Overleaf online editing: upload `{out_path.name}` to Overleaf project",
                f"- Local compilation: `xelatex {out_path.name}`",
                "- For use with .bib file: set bibliography parameter to automatically process citations",
            ])
        elif output_format == "docx":
            lines.extend([
                "",
                "📝 **Next steps**:",
                f"- Open `{out_path.name}` with Word/WPS to continue editing",
                "- For custom styles, first save a docx in Word as reference_docx",
            ])
        elif output_format == "pdf":
            lines.extend([
                "",
                "📝 **Next steps**:",
                f"- PDF ready for viewing: `{out_path.name}`",
                "- For layout adjustments, modify the Markdown source and re-export",
            ])

        if proc.stderr.strip():
            stderr_preview = proc.stderr.strip()[:500]
            lines.extend(["", f"⚠ **stderr output** (non-fatal):", f"```\n{stderr_preview}\n```"])

        return "\n".join(lines)
