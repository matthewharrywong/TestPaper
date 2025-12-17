"""Report generation for paper analysis results."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..search.semantic_scholar import Paper
from ..analysis.analyzer import PaperAnalysis


class ReportGenerator:
    """Generate reports from paper analysis results."""

    def __init__(self, output_dir: str = "outputs/reports"):
        """Initialize the report generator.

        Args:
            output_dir: Directory to save reports.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_paper_report(
        self,
        paper: Paper,
        analysis: Optional[PaperAnalysis],
        pdf_available: bool,
    ) -> str:
        """Generate a markdown report for a single paper.

        Args:
            paper: Paper metadata.
            analysis: Analysis results (if available).
            pdf_available: Whether PDF was available.

        Returns:
            Markdown content.
        """
        lines = [
            f"# {paper.title}",
            "",
            "## Metadata",
            "",
            f"- **Authors**: {', '.join(paper.authors[:5])}" + (" et al." if len(paper.authors) > 5 else ""),
            f"- **Year**: {paper.year or 'Unknown'}",
            f"- **Journal**: {paper.journal or 'Unknown'}",
            f"- **Citations**: {paper.citation_count}",
            f"- **DOI**: {paper.doi or 'N/A'}",
            f"- **URL**: [{paper.url}]({paper.url})",
            f"- **PDF Available**: {'Yes' if pdf_available else 'No'}",
            f"- **Open Access**: {'Yes' if paper.open_access else 'No'}",
            "",
        ]

        if paper.abstract:
            lines.extend([
                "## Abstract",
                "",
                paper.abstract,
                "",
            ])

        if analysis and analysis.success:
            lines.extend([
                "## AI-Generated Summary",
                "",
                analysis.summary or "No summary available.",
                "",
            ])

            if analysis.key_findings:
                lines.extend([
                    "### Key Findings",
                    "",
                ])
                for finding in analysis.key_findings:
                    lines.append(f"- {finding}")
                lines.append("")

            if analysis.ai_techniques:
                lines.extend([
                    "### AI Techniques Used",
                    "",
                ])
                for technique in analysis.ai_techniques:
                    lines.append(f"- {technique}")
                lines.append("")

            lines.extend([
                "## Methodology Evaluation",
                "",
                analysis.methodology_evaluation or "No methodology evaluation available.",
                "",
            ])

            if analysis.strengths:
                lines.extend([
                    "### Strengths",
                    "",
                ])
                for strength in analysis.strengths:
                    lines.append(f"- {strength}")
                lines.append("")

            if analysis.limitations:
                lines.extend([
                    "### Limitations",
                    "",
                ])
                for limitation in analysis.limitations:
                    lines.append(f"- {limitation}")
                lines.append("")

        elif analysis and not analysis.success:
            lines.extend([
                "## Analysis",
                "",
                f"**Analysis failed**: {analysis.error}",
                "",
            ])
        else:
            lines.extend([
                "## Analysis",
                "",
                "No analysis available (PDF not accessible).",
                "",
            ])

        lines.extend([
            "---",
            f"*Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ])

        return "\n".join(lines)

    def generate_summary_report(
        self,
        papers: list[Paper],
        analyses: dict[str, PaperAnalysis],
        pdf_statuses: dict[str, bool],
        search_config: dict,
    ) -> str:
        """Generate a summary report for all papers.

        Args:
            papers: List of papers.
            analyses: Dictionary of paper_id to analysis results.
            pdf_statuses: Dictionary of paper_id to PDF availability.
            search_config: Search configuration used.

        Returns:
            Markdown content.
        """
        total = len(papers)
        pdfs_available = sum(1 for v in pdf_statuses.values() if v)
        analyzed = sum(1 for a in analyses.values() if a.success)

        lines = [
            "# Academic Paper Analysis Summary Report",
            "",
            f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "## Search Configuration",
            "",
            f"- **Journals**: {', '.join(search_config.get('journals', []))}",
            f"- **Keywords**: {', '.join(search_config.get('keywords', []))}",
            f"- **Year Range**: {search_config.get('start_year', 'Any')} - {search_config.get('end_year', 'Present')}",
            "",
            "## Summary Statistics",
            "",
            f"- **Total Papers Found**: {total}",
            f"- **PDFs Available**: {pdfs_available} ({pdfs_available/total*100:.1f}%)" if total > 0 else "- **PDFs Available**: 0",
            f"- **Successfully Analyzed**: {analyzed} ({analyzed/total*100:.1f}%)" if total > 0 else "- **Successfully Analyzed**: 0",
            "",
            "## Papers by Journal",
            "",
        ]

        # Count papers by journal
        journal_counts = {}
        for paper in papers:
            journal = paper.journal or "Unknown"
            journal_counts[journal] = journal_counts.get(journal, 0) + 1

        for journal, count in sorted(journal_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- {journal}: {count}")

        lines.extend([
            "",
            "## Top Papers by Citations",
            "",
        ])

        # Top 10 by citations
        sorted_papers = sorted(papers, key=lambda p: p.citation_count, reverse=True)[:10]
        for i, paper in enumerate(sorted_papers, 1):
            status = "✓" if analyses.get(paper.paper_id, PaperAnalysis(paper.paper_id, False)).success else "○"
            lines.append(f"{i}. {status} **{paper.title}** ({paper.year}) - {paper.citation_count} citations")

        lines.extend([
            "",
            "## Common AI Techniques",
            "",
        ])

        # Aggregate AI techniques
        technique_counts = {}
        for analysis in analyses.values():
            if analysis.success and analysis.ai_techniques:
                for technique in analysis.ai_techniques:
                    # Normalize technique names
                    technique_lower = technique.lower()
                    technique_counts[technique] = technique_counts.get(technique, 0) + 1

        for technique, count in sorted(technique_counts.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"- {technique}: {count} papers")

        lines.extend([
            "",
            "## All Papers",
            "",
            "| Title | Year | Journal | Citations | PDF | Analyzed |",
            "|-------|------|---------|-----------|-----|----------|",
        ])

        for paper in sorted_papers[:50]:  # Limit to 50 in table
            pdf_status = "✓" if pdf_statuses.get(paper.paper_id) else "✗"
            analysis_status = "✓" if analyses.get(paper.paper_id, PaperAnalysis(paper.paper_id, False)).success else "✗"
            title = paper.title[:60] + "..." if len(paper.title) > 60 else paper.title
            lines.append(f"| {title} | {paper.year or 'N/A'} | {paper.journal or 'N/A'} | {paper.citation_count} | {pdf_status} | {analysis_status} |")

        lines.extend([
            "",
            "---",
            "",
            "## Legend",
            "",
            "- ✓ = Available/Successful",
            "- ✗ = Not available/Failed",
            "- ○ = Not analyzed",
        ])

        return "\n".join(lines)

    def save_paper_report(self, paper: Paper, content: str) -> str:
        """Save an individual paper report.

        Args:
            paper: Paper metadata.
            content: Report content.

        Returns:
            Path to saved file.
        """
        # Create safe filename
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in paper.title)[:50]
        safe_title = safe_title.strip().replace(" ", "_")
        filename = f"{paper.paper_id[:20]}_{safe_title}.md"

        filepath = self.output_dir / "papers" / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return str(filepath)

    def save_summary_report(self, content: str) -> str:
        """Save the summary report.

        Args:
            content: Report content.

        Returns:
            Path to saved file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"summary_report_{timestamp}.md"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return str(filepath)

    def export_json(
        self,
        papers: list[Paper],
        analyses: dict[str, PaperAnalysis],
        pdf_statuses: dict[str, bool],
    ) -> str:
        """Export all data as JSON.

        Args:
            papers: List of papers.
            analyses: Dictionary of analyses.
            pdf_statuses: Dictionary of PDF availability.

        Returns:
            Path to saved file.
        """
        data = {
            "generated_at": datetime.now().isoformat(),
            "total_papers": len(papers),
            "papers": [],
        }

        for paper in papers:
            paper_data = paper.to_dict()
            paper_data["pdf_available"] = pdf_statuses.get(paper.paper_id, False)

            analysis = analyses.get(paper.paper_id)
            if analysis:
                paper_data["analysis"] = analysis.to_dict()
            else:
                paper_data["analysis"] = None

            data["papers"].append(paper_data)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"papers_data_{timestamp}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return str(filepath)
