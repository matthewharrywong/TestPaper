#!/usr/bin/env python3
"""CLI entry point for the Academic Paper Analysis Pipeline."""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import AcademicPaperPipeline, PipelineConfig


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze academic papers on AI research from medical journals.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default config
  python run.py

  # Run with custom config file
  python run.py --config my_config.yaml

  # Override specific settings
  python run.py --max-results 50 --journals "Neurology" "JAMA Neurology"

  # Add custom keywords
  python run.py --keywords "deep learning" "transformer" "computer vision"

  # Use university library proxy for paywalled papers
  python run.py --ezproxy "https://ezproxy.library.edu/login?url="
        """,
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config/settings.yaml",
        help="Path to configuration file (default: config/settings.yaml)",
    )

    parser.add_argument(
        "--journals",
        "-j",
        nargs="+",
        help="Journals to search (overrides config)",
    )

    parser.add_argument(
        "--keywords",
        "-k",
        nargs="+",
        help="Keywords to search for (overrides config)",
    )

    parser.add_argument(
        "--max-results",
        "-m",
        type=int,
        help="Maximum number of papers to analyze (overrides config)",
    )

    parser.add_argument(
        "--start-year",
        type=int,
        help="Start year for search (overrides config)",
    )

    parser.add_argument(
        "--end-year",
        type=int,
        help="End year for search (overrides config)",
    )

    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF download and use abstracts only",
    )

    parser.add_argument(
        "--search-only",
        action="store_true",
        help="Only search for papers, don't analyze",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing",
    )

    parser.add_argument(
        "--ezproxy",
        type=str,
        help="EZproxy prefix URL for university library access (e.g., 'https://ezproxy.library.edu/login?url=')",
    )

    args = parser.parse_args()

    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        print("Please create a config file or specify a valid path with --config")
        sys.exit(1)

    config = PipelineConfig.from_yaml(str(config_path))

    # Apply command-line overrides
    if args.journals:
        config.journals = args.journals

    if args.keywords:
        config.keywords = args.keywords

    if args.max_results:
        config.max_results = args.max_results

    if args.start_year:
        config.start_year = args.start_year

    if args.end_year:
        config.end_year = args.end_year

    if args.ezproxy:
        config.ezproxy_enabled = True
        config.ezproxy_prefix = args.ezproxy

    # Validate config
    if not config.journals:
        print("Error: No journals specified")
        sys.exit(1)

    if not config.keywords:
        print("Error: No keywords specified")
        sys.exit(1)

    # Dry run - show configuration
    if args.dry_run:
        print("=" * 60)
        print("DRY RUN - Configuration Preview")
        print("=" * 60)
        print(f"\nJournals to search:")
        for journal in config.journals:
            print(f"  - {journal}")
        print(f"\nKeywords:")
        for keyword in config.keywords:
            print(f"  - {keyword}")
        print(f"\nSettings:")
        print(f"  Max results: {config.max_results}")
        print(f"  Year range: {config.start_year or 'any'} - {config.end_year or 'present'}")
        print(f"  LLM model: {config.llm_model}")
        print(f"\nEZproxy:")
        if config.ezproxy_enabled:
            print(f"  Enabled: Yes")
            print(f"  Prefix: {config.ezproxy_prefix}")
            print(f"  Try direct first: {config.ezproxy_try_direct_first}")
            print(f"  Use DOI URLs: {config.ezproxy_use_doi_urls}")
        else:
            print(f"  Enabled: No (only open access PDFs will be downloaded)")
        print(f"\nOutput:")
        print(f"  Reports: {config.reports_output_dir}")
        print(f"  PDFs: {config.pdf_download_dir}")
        return

    # Run pipeline
    try:
        pipeline = AcademicPaperPipeline(config)

        if args.search_only:
            # Search only mode
            papers = pipeline.search_papers()
            print(f"\nFound {len(papers)} papers:")
            for i, paper in enumerate(papers[:20], 1):
                pdf_mark = "📄" if paper.pdf_url else "  "
                print(f"{i:3}. {pdf_mark} [{paper.year}] {paper.title[:70]}...")
            if len(papers) > 20:
                print(f"     ... and {len(papers) - 20} more")
        elif args.no_pdf:
            # Abstract-only mode
            pipeline.search_papers()
            if pipeline.papers:
                # Skip PDF step, analyze abstracts directly
                print(f"\n🤖 Analyzing papers using abstracts only...")
                for paper in pipeline.papers:
                    if paper.abstract:
                        analysis = pipeline.analyzer.analyze_from_abstract(
                            abstract=paper.abstract,
                            paper_id=paper.paper_id,
                            title=paper.title,
                        )
                        pipeline.analyses[paper.paper_id] = analysis
                        pipeline.pdf_statuses[paper.paper_id] = False
                pipeline.generate_reports()
        else:
            # Full pipeline
            pipeline.run()

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except ValueError as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
