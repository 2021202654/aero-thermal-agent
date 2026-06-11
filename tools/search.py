"""
Literature Search Tool — Core capability of the Agent

Supports two retrieval pathways:
1. Vector Semantic Search (FAISS): Semantic relevance without exact keyword matching
2. CSV Title Keyword Search: Exact title matching (fallback when FAISS is unavailable)
"""

from __future__ import annotations

import csv
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from core.action import Action


class LiteratureSearchTool(Action):
    """Literature Search Tool — Search within the 3,326-paper gas-solid thermal conduction literature corpus."""

    name = "search_literature"
    description = (
        "Search the literature corpus in the field of gas-solid thermal conduction (3,326 papers total, covering "
        "aerothermodynamics, catalytic recombination, shock wave boundary layer interaction, non-equilibrium "
        "flows, thermal protection, and related areas). "
        "Input search keywords (in English), return the most relevant paper titles, years, journals, and DOIs."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keyword or phrase, in English. For example: 'catalytic recombination coefficient SiO2'",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return, default 5, maximum 20",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(
        self,
        faiss_index_dir: str | Path | None = None,
        csv_path: str | Path | None = None,
    ):
        self._index_dir = Path(faiss_index_dir) if faiss_index_dir else None
        self._csv_path = Path(csv_path) if csv_path else None
        self._index = None
        self._metadata = None
        self._csv_rows: list[dict[str, str]] = []

    # ── Path Resolution ────────────────────────────────────

    @property
    def index_dir(self) -> Path:
        if self._index_dir:
            return self._index_dir
        project = Path(__file__).parent.parent.parent
        return project / "03_知识工程" / "05_向量索引" / "faiss_index"

    @property
    def csv_path(self) -> Path:
        if self._csv_path:
            return self._csv_path
        project = Path(__file__).parent.parent.parent
        return project / "03_知识工程" / "03_文献库" / "Final_Merged_Literature.csv"

    # ── Lazy Loading ────────────────────────────────────

    def _ensure_index_loaded(self):
        if self._index is not None:
            return
        faiss_file = self.index_dir / "index.faiss"
        pkl_file = self.index_dir / "index.pkl"
        if faiss_file.exists() and pkl_file.exists():
            try:
                import faiss
                self._index = faiss.read_index(str(faiss_file))
                with open(pkl_file, "rb") as f:
                    self._metadata = pickle.load(f)
            except Exception:
                pass  # Silent fallback to CSV search

    def _ensure_csv_loaded(self):
        if self._csv_rows:
            return
        csv_file = self.csv_path
        if not csv_file.exists():
            return
        # Auto-detect encoding: try UTF-8 → Latin-1 → GBK in order
        for encoding in ("utf-8", "latin-1", "gbk"):
            try:
                with open(csv_file, "r", encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    self._csv_rows = list(reader)
                break  # Load successful, exit encoding attempts
            except (UnicodeDecodeError, UnicodeError):
                continue

    # ── Search Entry Point ────────────────────────────────────

    async def run(self, query: str, top_k: int = 5) -> str:
        top_k = min(top_k, 20)
        results: list[dict[str, Any]] = []
        seen_titles: set[str] = set()

        # Pathway 1: FAISS Semantic Search
        try:
            self._ensure_index_loaded()
            if self._index is not None:
                faiss_results = self._faiss_search(query, top_k)
                for r in faiss_results:
                    if r.get("title", "") not in seen_titles:
                        results.append(r)
                        seen_titles.add(r.get("title", ""))
        except Exception as e:
            pass  # Silent fallback

        # Pathway 2: CSV Keyword Search (supplement/fallback)
        try:
            self._ensure_csv_loaded()
            if self._csv_rows and len(results) < top_k:
                csv_results = self._csv_keyword_search(query, top_k - len(results))
                for r in csv_results:
                    if r.get("title", "") not in seen_titles:
                        results.append(r)
                        seen_titles.add(r.get("title", ""))
        except Exception:
            pass

        if not results:
            return f"No literature found related to '{query}'. Try broader keywords or check the literature corpus path configuration."

        # Filter: results without DOI are not allowed to pass to LLM (preventing hallucinated citations)
        valid_results = [r for r in results[:top_k] if r.get("doi", "").strip()]
        invalid_count = len(results[:top_k]) - len(valid_results)
        if invalid_count > 0:
            filtered_note = f"(filtered {invalid_count} records without DOI)"
        else:
            filtered_note = ""

        if not valid_results:
            return f"No literature found related to '{query}' with DOI. Try different keywords.{filtered_note}"

        return self._format_results(query, valid_results) + filtered_note

    # ── Search Implementation ────────────────────────────────────

    def _faiss_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """FAISS semantic search. Requires embedding model configuration to activate."""
        # Uncomment the following code for actual deployment:
        # import openai
        # client = openai.OpenAI(base_url="...", api_key="...")
        # q_vec = client.embeddings.create(model="text-embedding-3-small", input=query)
        # vec = np.array([q_vec.data[0].embedding], dtype=np.float32)
        # D, I = self._index.search(vec, top_k)
        # results = []
        # for i, idx in enumerate(I[0]):
        #     if idx >= 0 and self._metadata:
        #         meta = self._metadata[idx]
        #         results.append({
        #             "title": meta.get("title", ""),
        #             "year": str(meta.get("year", "?")),
        #             "journal": meta.get("journal", ""),
        #             "doi": meta.get("doi", ""),
        #             "score": f"Semantic similarity {1-D[0][i]:.2f}",
        #         })
        # return results
        return []  # Currently falling back to CSV search

    def _csv_keyword_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """CSV title + abstract keyword matching."""
        keywords = query.lower().split()
        scored: list[tuple[int, dict[str, str]]] = []

        for row in self._csv_rows:
            title = row.get("Title", "")
            journal = row.get("Journal", "")
            text = (title + " " + journal).lower()
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "title": row.get("Title", "Untitled").strip('"'),
                "year": row.get("Year", "?"),
                "journal": row.get("Journal", "Unknown journal").strip('"'),
                "doi": row.get("DOI", ""),
                "score": f"Keyword hit {score}/{len(keywords)}",
            }
            for score, row in scored[:top_k]
        ]

    def _format_results(self, query: str, results: list[dict[str, Any]]) -> str:
        lines = [f"[search] '{query}' — {len(results)} results:\n"]
        for i, r in enumerate(results, 1):
            doi = r.get("doi", "")
            doi_link = f"https://doi.org/{doi}" if doi else "No DOI"
            lines.append(
                f"{i}. **{r['title']}**\n"
                f"   {r.get('journal', '?')} ({r.get('year', '?')})\n"
                f"   DOI: {doi_link}\n"
                f"   {r.get('score', '')}\n"
            )
        return "\n".join(lines)
