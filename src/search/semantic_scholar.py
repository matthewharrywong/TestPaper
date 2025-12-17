"""Semantic Scholar API integration for paper search."""

import time
from dataclasses import dataclass, field
from typing import Optional
import requests
from ratelimit import limits, sleep_and_retry


@dataclass
class Paper:
    """Represents an academic paper."""

    paper_id: str
    title: str
    abstract: Optional[str]
    authors: list[str]
    year: Optional[int]
    journal: Optional[str]
    doi: Optional[str]
    url: str
    citation_count: int
    pdf_url: Optional[str] = None
    open_access: bool = False
    fields_of_study: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "year": self.year,
            "journal": self.journal,
            "doi": self.doi,
            "url": self.url,
            "citation_count": self.citation_count,
            "pdf_url": self.pdf_url,
            "open_access": self.open_access,
            "fields_of_study": self.fields_of_study,
        }


class SemanticScholarSearch:
    """Search for papers using Semantic Scholar API."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    FIELDS = "paperId,title,abstract,authors,year,venue,externalIds,url,citationCount,isOpenAccess,openAccessPdf,fieldsOfStudy"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the search client.

        Args:
            api_key: Optional Semantic Scholar API key for higher rate limits.
        """
        self.session = requests.Session()
        if api_key:
            self.session.headers["x-api-key"] = api_key

    @sleep_and_retry
    @limits(calls=10, period=1)  # 10 requests per second (conservative)
    def _make_request(self, endpoint: str, params: dict) -> dict:
        """Make a rate-limited request to the API."""
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def search_journal(
        self,
        journal: str,
        keywords: list[str],
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        max_results: int = 100,
        min_citations: int = 0,
    ) -> list[Paper]:
        """Search for papers in a specific journal matching keywords.

        Args:
            journal: Journal name to search in.
            keywords: List of keywords to search for.
            start_year: Minimum publication year.
            end_year: Maximum publication year.
            max_results: Maximum number of papers to return.
            min_citations: Minimum citation count filter.

        Returns:
            List of Paper objects matching the criteria.
        """
        papers = []
        seen_ids = set()

        for keyword in keywords:
            # Build query: keyword + journal
            query = f"{keyword} venue:{journal}"

            # Build year filter
            year_filter = ""
            if start_year and end_year:
                year_filter = f"{start_year}-{end_year}"
            elif start_year:
                year_filter = f"{start_year}-"
            elif end_year:
                year_filter = f"-{end_year}"

            offset = 0
            limit = min(100, max_results)  # API limit is 100 per request

            while len(papers) < max_results:
                params = {
                    "query": query,
                    "fields": self.FIELDS,
                    "offset": offset,
                    "limit": limit,
                }

                if year_filter:
                    params["year"] = year_filter

                try:
                    data = self._make_request("paper/search", params)
                except requests.exceptions.HTTPError as e:
                    print(f"Warning: API error for query '{query}': {e}")
                    break

                results = data.get("data", [])
                if not results:
                    break

                for item in results:
                    paper_id = item.get("paperId")
                    if not paper_id or paper_id in seen_ids:
                        continue

                    # Apply citation filter
                    citation_count = item.get("citationCount", 0) or 0
                    if citation_count < min_citations:
                        continue

                    seen_ids.add(paper_id)

                    # Extract author names
                    authors = [
                        a.get("name", "Unknown")
                        for a in item.get("authors", [])
                    ]

                    # Extract DOI
                    external_ids = item.get("externalIds", {}) or {}
                    doi = external_ids.get("DOI")

                    # Extract PDF URL
                    open_access_pdf = item.get("openAccessPdf")
                    pdf_url = open_access_pdf.get("url") if open_access_pdf else None

                    # Extract fields of study
                    fields = item.get("fieldsOfStudy") or []

                    paper = Paper(
                        paper_id=paper_id,
                        title=item.get("title", "Unknown Title"),
                        abstract=item.get("abstract"),
                        authors=authors,
                        year=item.get("year"),
                        journal=item.get("venue"),
                        doi=doi,
                        url=item.get("url", f"https://www.semanticscholar.org/paper/{paper_id}"),
                        citation_count=citation_count,
                        pdf_url=pdf_url,
                        open_access=item.get("isOpenAccess", False),
                        fields_of_study=fields,
                    )
                    papers.append(paper)

                    if len(papers) >= max_results:
                        break

                offset += limit
                if offset >= data.get("total", 0):
                    break

                # Small delay between paginated requests
                time.sleep(0.1)

        return papers

    def search_journals(
        self,
        journals: list[str],
        keywords: list[str],
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        max_results: int = 100,
        min_citations: int = 0,
    ) -> list[Paper]:
        """Search for papers across multiple journals.

        Args:
            journals: List of journal names to search.
            keywords: List of keywords to search for.
            start_year: Minimum publication year.
            end_year: Maximum publication year.
            max_results: Maximum total number of papers to return.
            min_citations: Minimum citation count filter.

        Returns:
            List of Paper objects matching the criteria, deduplicated.
        """
        all_papers = []
        seen_ids = set()

        # Calculate papers per journal to distribute evenly
        papers_per_journal = max(10, max_results // len(journals))

        for journal in journals:
            print(f"Searching journal: {journal}")
            journal_papers = self.search_journal(
                journal=journal,
                keywords=keywords,
                start_year=start_year,
                end_year=end_year,
                max_results=papers_per_journal,
                min_citations=min_citations,
            )

            for paper in journal_papers:
                if paper.paper_id not in seen_ids:
                    seen_ids.add(paper.paper_id)
                    all_papers.append(paper)

            print(f"  Found {len(journal_papers)} papers")

        # Sort by citation count (most cited first)
        all_papers.sort(key=lambda p: p.citation_count, reverse=True)

        # Trim to max_results
        return all_papers[:max_results]
