"""
Built-in Tool Set — Domain Tools Ready to Use for Agent

- LiteratureSearchTool    : FAISS semantic retrieval + CSV keyword search (local 3,326 paper literature database)
- WebSearchTool            : OpenAlex API external literature search (global 250 million+ papers)
- AeroThermalComputeTool   : Aero-thermal parameter computation (stagnation heat flux / Knudsen / catalytic / boundary layer)
- CodeExecutionTool        : Python subprocess sandbox execution (computation + plotting + verification)
- CitationResolverTool     : CrossRef/OpenAlex DOI resolution + BibTeX generation
- PDFAnalysisTool          : PDF paper parsing (text/metadata/sections/parameter identification)
- ReportTool               : Structured Markdown research report generation
- ExportFindingTool        : Single finding record
- PandocExportTool         : Markdown → LaTeX/DOCX/PDF format export
- HypothesisGenerator      : AI Scientist core — literature Gap identification + hypothesis generation + physics constraint verification
- PhysicsConstraintLayer   : Gas-solid interface physics constraint verification layer (parameter bounds/flow regime/conservation laws)
"""

from .search import LiteratureSearchTool
from .compute import AeroThermalComputeTool
from .web_search import WebSearchTool
from .code_exec import CodeExecutionTool
from .citation import CitationResolverTool
from .pdf_parser import PDFAnalysisTool
from .report import ReportTool, ExportFindingTool
from .pandoc_export import PandocExportTool
from .hypothesis import HypothesisGenerator
from .physics_constraints import PhysicsConstraintLayer

__all__ = [
    "LiteratureSearchTool",
    "WebSearchTool",
    "AeroThermalComputeTool",
    "CodeExecutionTool",
    "CitationResolverTool",
    "PDFAnalysisTool",
    "ReportTool",
    "ExportFindingTool",
    "PandocExportTool",
    "HypothesisGenerator",
    "PhysicsConstraintLayer",
]
