"""Main pipeline orchestrator."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from tqdm import tqdm

from .search import SemanticScholarSearch
from .search.semantic_scholar import Paper
from .pdf import PDFChecker, PDFExtractor, EZProxyConfig
from .analysis import PaperAnalyzer
from .analysis.analyzer import PaperAnalysis
from .reports import ReportGenerator


@dataclass
class PipelineConfig:
    """Pipeline configuration."""

    # Journals
    journals: list[str]

    # Search settings
    keywords: list[str]
    max_results: int = 100
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    min_citations: int = 0

    # PDF settings
    pdf_download_dir: str = "outputs/pdfs"
    pdf_max_size_mb: int = 50
    pdf_timeout: int = 30

    # EZproxy settings
    ezproxy_enabled: bool = False
    ezproxy_prefix: str = ""
    ezproxy_try_direct_first: bool = True
    ezproxy_use_doi_urls: bool = True

    # LLM settings
    llm_model: str = "claude-sonnet-4-20250514"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.3

    # Report settings
    reports_output_dir: str = "outputs/reports"
    individual_reports: bool = True
    summary_report: bool = True
    export_json: bool = True

    @classmethod
    def from_yaml(cls, path: str) -> "PipelineConfig":
        """Load configuration from YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        return cls(
            journals=data.get("journals", []),
            keywords=data.get("search", {}).get("keywords", ["artificial intelligence"]),
            max_results=data.get("search", {}).get("max_results", 100),
            start_year=data.get("search", {}).get("start_year"),
            end_year=data.get("search", {}).get("end_year"),
            min_citations=data.get("search", {}).get("min_citations", 0),
            pdf_download_dir=data.get("pdf", {}).get("download_dir", "outputs/pdfs"),
            pdf_max_size_mb=data.get("pdf", {}).get("max_size_mb", 50),
            pdf_timeout=data.get("pdf", {}).get("timeout", 30),
            ezproxy_enabled=data.get("pdf", {}).get("ezproxy", {}).get("enabled", False),
            ezproxy_prefix=data.get("pdf", {}).get("ezproxy", {}).get("prefix", ""),
            ezproxy_try_direct_first=data.get("pdf", {}).get("ezproxy", {}).get("try_direct_first", True),
            ezproxy_use_doi_urls=data.get("pdf", {}).get("ezproxy", {}).get("use_doi_urls", True),
            llm_model=data.get("llm", {}).get("model", "claude-sonnet-4-20250514"),
            llm_max_tokens=data.get("llm", {}).get("max_tokens", 4096),
            llm_temperature=data.get("llm", {}).get("temperature", 0.3),
            reports_output_dir=data.get("reports", {}).get("output_dir", "outputs/reports"),
            individual_reports=data.get("reports", {}).get("individual_reports", True),
            summary_report=data.get("reports", {}).get("summary_report", True),
            export_json=data.get("reports", {}).get("export_json", True),
        )


class AcademicPaperPipeline:
    """Main pipeline for academic paper analysis."""

    def __init__(self, config: PipelineConfig):
        """Initialize the pipeline.

        Args:
            config: Pipeline configuration.
        """
        self.config = config

        # Initialize components
        self.searcher = SemanticScholarSearch()

        # Configure EZproxy if enabled
        ezproxy_config = EZProxyConfig(
            enabled=config.ezproxy_enabled,
            prefix=config.ezproxy_prefix,
            try_direct_first=config.ezproxy_try_direct_first,
            use_doi_urls=config.ezproxy_use_doi_urls,
        )

        self.pdf_checker = PDFChecker(
            download_dir=config.pdf_download_dir,
            max_size_mb=config.pdf_max_size_mb,
            timeout=config.pdf_timeout,
            ezproxy_config=ezproxy_config,
        )
        self.pdf_extractor = PDFExtractor()
        self.analyzer = PaperAnalyzer(
            model=config.llm_model,
            max_tokens=config.llm_max_tokens,
            temperature=config.llm_temperature,
        )
        self.report_generator = ReportGenerator(output_dir=config.reports_output_dir)

        # Results storage
        self.papers: list[Paper] = []
        self.pdf_statuses: dict[str, bool] = {}
        self.analyses: dict[str, PaperAnalysis] = {}

    def search_papers(self) -> list[Paper]:
        """Search for papers across configured journals.

        Returns:
            List of found papers.
        """
        print(f"\n📚 Searching for papers in {len(self.config.journals)} journals...")
        print(f"   Keywords: {', '.join(self.config.keywords)}")

        self.papers = self.searcher.search_journals(
            journals=self.config.journals,
            keywords=self.config.keywords,
            start_year=self.config.start_year,
            end_year=self.config.end_year,
            max_results=self.config.max_results,
            min_citations=self.config.min_citations,
        )

        print(f"\n✓ Found {len(self.papers)} papers")
        return self.papers

    def check_and_download_pdfs(self) -> dict[str, bool]:
        """Check PDF availability and download available PDFs.

        Returns:
            Dictionary of paper_id to availability status.
        """
        print(f"\n📄 Checking PDF availability for {len(self.papers)} papers...")
        if self.config.ezproxy_enabled:
            print(f"   Using EZproxy: {self.config.ezproxy_prefix[:50]}...")

        for paper in tqdm(self.papers, desc="Checking PDFs"):
            status = self.pdf_checker.check_and_download(
                paper_id=paper.paper_id,
                pdf_url=paper.pdf_url,
                doi=paper.doi,  # Pass DOI for proxy-based access
            )
            self.pdf_statuses[paper.paper_id] = status.available

        available_count = sum(1 for v in self.pdf_statuses.values() if v)
        print(f"\n✓ {available_count}/{len(self.papers)} PDFs available")
        return self.pdf_statuses

    def analyze_papers(self) -> dict[str, PaperAnalysis]:
        """Analyze all papers using LLM.

        Returns:
            Dictionary of paper_id to analysis results.
        """
        print(f"\n🤖 Analyzing papers with Claude...")

        for paper in tqdm(self.papers, desc="Analyzing"):
            # Check if we have PDF
            if self.pdf_statuses.get(paper.paper_id):
                # Extract text from PDF
                safe_id = "".join(c if c.isalnum() else "_" for c in paper.paper_id)
                pdf_path = Path(self.config.pdf_download_dir) / f"{safe_id}.pdf"

                if pdf_path.exists():
                    extracted = self.pdf_extractor.extract(str(pdf_path), paper.paper_id)

                    if extracted.success:
                        analysis = self.analyzer.analyze(
                            paper_text=extracted.text,
                            paper_id=paper.paper_id,
                            title=paper.title,
                        )
                        self.analyses[paper.paper_id] = analysis
                        continue

            # Fall back to abstract-only analysis
            if paper.abstract:
                analysis = self.analyzer.analyze_from_abstract(
                    abstract=paper.abstract,
                    paper_id=paper.paper_id,
                    title=paper.title,
                )
                self.analyses[paper.paper_id] = analysis

        analyzed_count = sum(1 for a in self.analyses.values() if a.success)
        print(f"\n✓ Successfully analyzed {analyzed_count}/{len(self.papers)} papers")
        return self.analyses

    def generate_reports(self) -> dict[str, str]:
        """Generate all configured reports.

        Returns:
            Dictionary of report type to file path.
        """
        print(f"\n📝 Generating reports...")
        report_paths = {}

        # Individual paper reports
        if self.config.individual_reports:
            print("   Generating individual paper reports...")
            for paper in tqdm(self.papers, desc="Paper reports"):
                analysis = self.analyses.get(paper.paper_id)
                pdf_available = self.pdf_statuses.get(paper.paper_id, False)

                content = self.report_generator.generate_paper_report(
                    paper=paper,
                    analysis=analysis,
                    pdf_available=pdf_available,
                )
                path = self.report_generator.save_paper_report(paper, content)
                report_paths[f"paper_{paper.paper_id}"] = path

        # Summary report
        if self.config.summary_report:
            print("   Generating summary report...")
            search_config = {
                "journals": self.config.journals,
                "keywords": self.config.keywords,
                "start_year": self.config.start_year,
                "end_year": self.config.end_year,
            }
            content = self.report_generator.generate_summary_report(
                papers=self.papers,
                analyses=self.analyses,
                pdf_statuses=self.pdf_statuses,
                search_config=search_config,
            )
            path = self.report_generator.save_summary_report(content)
            report_paths["summary"] = path

        # JSON export
        if self.config.export_json:
            print("   Exporting JSON data...")
            path = self.report_generator.export_json(
                papers=self.papers,
                analyses=self.analyses,
                pdf_statuses=self.pdf_statuses,
            )
            report_paths["json"] = path

        print(f"\n✓ Reports saved to {self.config.reports_output_dir}")
        return report_paths

    def run(self) -> dict[str, str]:
        """Run the complete pipeline.

        Returns:
            Dictionary of report paths.
        """
        print("=" * 60)
        print("Academic Paper Analysis Pipeline")
        print("=" * 60)

        # Step 1: Search
        self.search_papers()

        if not self.papers:
            print("\n⚠ No papers found. Exiting.")
            return {}

        # Step 2: Check/Download PDFs
        self.check_and_download_pdfs()

        # Step 3: Analyze
        self.analyze_papers()

        # Step 4: Generate Reports
        report_paths = self.generate_reports()

        print("\n" + "=" * 60)
        print("Pipeline Complete!")
        print("=" * 60)

        return report_paths
