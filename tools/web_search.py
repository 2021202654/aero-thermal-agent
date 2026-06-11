"""
External Literature Search Tool — Search global academic literature via OpenAlex API

OpenAlex is an open academic literature index covering 250M+ papers.
- Free, no authentication required, REST API
- Rate limit: 100k requests/day
- Supports multi-dimensional search: keywords, DOI, topics, year, etc.

Difference from LiteratureSearchTool:
- LiteratureSearchTool: Local 3,326-paper corpus (CSV + FAISS)
- WebSearchTool: Global open academic literature (OpenAlex API)
"""

from __future__ import annotations

from typing import Any

import httpx

from core.action import Action


class WebSearchTool(Action):
    """External Literature Search — Search global academic literature via OpenAlex API."""

    name = "web_search"
    description = (
        "Search the OpenAlex global academic literature index (covering 250M+ papers). "
        "Use cases: finding latest research progress, supplementing locally uncovered papers, "
        "precise DOI lookup, citation verification. "
        "Supports keyword search, year/topic filtering, sorting by citation count."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search keyword (in English), supports Boolean operators AND/OR. "
                    "For example: 'catalytic recombination coefficient SiO2' or 'shock wave boundary layer interaction hypersonic'"
                ),
            },
            "search_type": {
                "type": "string",
                "enum": ["keyword", "doi", "title"],
                "description": "Search type: keyword=keyword search, doi=precise DOI lookup (only accepts DOI format like 10.xxxx/xxxxx, for report numbers/plain text use keyword), title=title search",
                "default": "keyword",
            },
            "per_page": {
                "type": "integer",
                "description": "Number of results to return, default 5, maximum 25",
                "default": 5,
            },
            "year_from": {
                "type": "integer",
                "description": "Start publication year (inclusive), e.g., 2020",
            },
            "year_to": {
                "type": "integer",
                "description": "End publication year (inclusive), e.g., 2025",
            },
            "sort": {
                "type": "string",
                "enum": ["relevance_score:desc", "cited_by_count:desc", "publication_date:desc"],
                "description": "Sort method: relevance_score:desc=relevance, cited_by_count:desc=citations, publication_date:desc=newest",
                "default": "relevance_score:desc",
            },
        },
        "required": ["query"],
    }

    BASE_URL = "https://api.openalex.org"

    def __init__(self, email: str = ""):
        self._email = email  # OpenAlex courtesy parameter, can provide email address
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def run(
        self,
        query: str,
        search_type: str = "keyword",
        per_page: int = 5,
        year_from: int | None = None,
        year_to: int | None = None,
        sort: str = "relevance_score:desc",
    ) -> str:
        per_page = min(per_page, 25)

        try:
            client = await self._get_client()
        except Exception as e:
            return f"[Network Error] Failed to create HTTP client: {e}"

        # ── Build Request ────────────────────────────────
        if search_type == "doi":
            results = await self._lookup_by_doi(client, query)
            return self._format_results(query, results, search_type)
        elif search_type == "title":
            return await self._search_by_title(client, query, per_page)
        else:
            results = await self._search_keyword(
                client, query, per_page, year_from, year_to, sort
            )
            return self._format_results(query, results, search_type)

    # ── Search Implementation ────────────────────────────────────

    async def _search_keyword(
        self,
        client: httpx.AsyncClient,
        query: str,
        per_page: int,
        year_from: int | None = None,
        year_to: int | None = None,
        sort: str = "relevance",
    ) -> list[dict[str, Any]]:
        """OpenAlex keyword search."""
        url = f"{self.BASE_URL}/works"

        # Build filter
        filters = []
        if year_from:
            filters.append(f"publication_year:{year_from}")
        if year_to:
            if year_from:
                filters.insert(-1 if filters else 0, f"publication_year:{year_from}-{year_to}")
                # Rebuild
                filters = [f for f in filters if not f.startswith(f"publication_year:{year_from}") or "-" in f]
                filters = [f for f in filters if not (f.startswith(f"publication_year:{year_from}") and not "-" in f)]
        if year_from and year_to:
            filters = [f for f in filters if f == filters[-1] or not f.startswith("publication_year:")]
            filters.append(f"publication_year:{year_from}-{year_to}")
        elif year_from:
            filters.append(f"publication_year:{year_from}")
        # else: no year filter

        # Simplified filter logic
        filter_str = ""
        if year_from and year_to:
            filter_str = f"publication_year:{year_from}-{year_to}"
        elif year_from:
            filter_str = f"publication_year:{year_from}"
        elif year_to:
            filter_str = f"publication_year:1900-{year_to}"

        params: dict[str, Any] = {
            "search": query,
            "per_page": per_page,
            "sort": sort,
        }
        if filter_str:
            params["filter"] = filter_str
        if self._email:
            params["mailto"] = self._email

        headers = {"User-Agent": "AeroThermalExpert-Agent/1.0"}

        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            return [{"error": f"OpenAlex API request failed: {e}"}]
        except Exception as e:
            return [{"error": f"Failed to parse response: {e}"}]

        return self._parse_works(data.get("results", []))

    async def _lookup_by_doi(
        self, client: httpx.AsyncClient, doi: str
    ) -> list[dict[str, Any]]:
        """Precise DOI lookup."""
        # Clean DOI prefix
        clean_doi = doi.strip()
        if clean_doi.startswith("https://doi.org/"):
            clean_doi = clean_doi[16:]
        elif clean_doi.startswith("http://doi.org/"):
            clean_doi = clean_doi[15:]
        url = f"{self.BASE_URL}/works/doi:{httpx.URL('https://doi.org/' + clean_doi).path.split('/')[-1] if '/' not in clean_doi else clean_doi}"
        # Simplify: encode DOI directly
        import urllib.parse
        encoded_doi = urllib.parse.quote(clean_doi, safe="")
        url = f"{self.BASE_URL}/works/doi:{encoded_doi}"
        headers = {"User-Agent": "AeroThermalExpert-Agent/1.0"}

        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                return [{"error": f"DOI not found: '{doi}'. If this is a report number or keyword (not a DOI), retry with search_type='keyword'."}]
            resp.raise_for_status()
            data = resp.json()
            return self._parse_works([data]) if data.get("id") else [{"error": "No results"}]
        except httpx.HTTPError as e:
            return [{"error": f"Request failed: {e}"}]

    async def _search_by_title(
        self, client: httpx.AsyncClient, title: str, per_page: int
    ) -> str:
        """Search by title (using filter for exact match)."""
        url = f"{self.BASE_URL}/works"
        params: dict[str, Any] = {
            "filter": f"title.search:{title}",
            "per_page": per_page,
        }
        headers = {"User-Agent": "AeroThermalExpert-Agent/1.0"}

        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            results = self._parse_works(data.get("results", []))
            return self._format_results(title, results, "title")
        except Exception as e:
            return f"[Search Error] {e}"

    # ── Parsing ────────────────────────────────────────

    def _parse_works(self, works: list[dict]) -> list[dict[str, Any]]:
        """Parse OpenAlex work objects into unified format."""
        parsed = []
        for w in works:
            if "error" in w:
                parsed.append(w)
                continue

            # Extract authors (first 5)
            authorships = w.get("authorships", [])
            authors = [
                a.get("author", {}).get("display_name", "Unknown")
                for a in authorships[:5]
            ]

            # Extract journal/conference name
            primary_loc = w.get("primary_location", {}) or {}
            source = primary_loc.get("source", {}) or {}
            journal = source.get("display_name", "")

            # Abstract (OpenAlex provides inverted abstract → reconstruct to plain text)
            abstract = ""
            abstract_inverted = w.get("abstract_inverted_index", None)
            if abstract_inverted:
                abstract = self._reconstruct_abstract(abstract_inverted)
            # Truncate to first 500 characters
            if len(abstract) > 500:
                abstract = abstract[:500] + "..."

            doi = w.get("doi", "")
            doi_clean = doi.replace("https://doi.org/", "") if doi else ""

            parsed.append({
                "title": w.get("title", "Untitled"),
                "authors": authors,
                "year": str(w.get("publication_year", "?")),
                "journal": journal or "Unknown journal",
                "doi": doi_clean,
                "cited_by": w.get("cited_by_count", 0),
                "type": w.get("type", "unknown"),
                "abstract": abstract,
                "openalex_url": w.get("id", ""),
                "is_open_access": w.get("open_access", {}).get("is_oa", False),
            })
        return parsed

    @staticmethod
    def _reconstruct_abstract(inverted: dict) -> str:
        """Reconstruct OpenAlex inverted-index abstract to plain text."""
        if not inverted:
            return ""
        # Build {position: word} mapping
        positions: dict[int, str] = {}
        for word, pos_list in inverted.items():
            for pos in pos_list:
                positions[pos] = word
        # Sort by position and join
        return " ".join(positions[i] for i in sorted(positions))

    # ── Formatting ──────────────────────────────────────

    def _format_results(
        self, query: str, results: list[dict[str, Any]], search_type: str
    ) -> str:
        """Format search results as Markdown."""
        if not results:
            return f"[web_search] No results for '{query}'."

        if len(results) == 1 and "error" in results[0]:
            return f"[web_search] Failed: {results[0]['error']}"

        lines = [
            f"## Web Search: '{query}'",
            f"**Source**: OpenAlex | **Results**: {len(results)} papers\n",
        ]

        for i, r in enumerate(results, 1):
            if "error" in r:
                continue

            authors = ", ".join(r.get("authors", [])[:3])
            if len(r.get("authors", [])) > 3:
                authors += " et al."

            doi = r.get("doi", "")
            doi_link = f"https://doi.org/{doi}" if doi else ""

            lines.append(f"### {i}. {r['title']}")
            lines.append(f"- **Authors**: {authors}")
            lines.append(f"- **Journal**: {r.get('journal', '?')} ({r.get('year', '?')})")
            if doi_link:
                lines.append(f"- **DOI**: [{doi}]({doi_link})")
            lines.append(f"- **Citations**: {r.get('cited_by', 0)}")
            if r.get("is_open_access"):
                lines.append(f"- **OA**: ✅ Open Access")
            if r.get("abstract"):
                lines.append(f"- **Abstract**: {r['abstract']}")
            lines.append("")

        return "\n".join(lines)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
