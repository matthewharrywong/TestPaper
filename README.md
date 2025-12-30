# Academic Paper Analysis Pipeline

A Python pipeline for searching, downloading, and analyzing academic papers on AI research from medical journals using Claude LLM.

## Features

- **Journal Search**: Search across multiple medical/neurology journals via Semantic Scholar API
- **PDF Handling**: Automatic PDF availability checking, downloading, and text extraction
- **EZproxy Support**: Access paywalled papers through your university library proxy
- **LLM Analysis**: Summarization and methodology evaluation using Claude
- **Flexible Reports**: Markdown reports per paper, summary reports, and JSON data export
- **Configurable**: Easy-to-modify YAML configuration for journals, keywords, and settings

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd TestPaper

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### API Key

Set your Anthropic API key as an environment variable:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

### Settings

Edit `config/settings.yaml` to customize:

```yaml
# Journals to search (easily modify this list)
journals:
  - "Neurology"
  - "JAMA Neurology"
  - "Annals of Neurology"
  - "New England Journal of Medicine"

# Search settings
search:
  keywords:
    - "artificial intelligence"
    - "machine learning"
    - "deep learning"
  max_results: 100
  start_year: 2020
```

## Usage

### Basic Usage

```bash
# Run with default configuration
python run.py

# Dry run (preview what will happen)
python run.py --dry-run
```

### Command Line Options

```bash
# Custom configuration file
python run.py --config my_config.yaml

# Override journals
python run.py --journals "Neurology" "JAMA Neurology"

# Override keywords
python run.py --keywords "transformer" "computer vision"

# Limit results
python run.py --max-results 25

# Filter by year
python run.py --start-year 2022 --end-year 2024

# Search only (no analysis)
python run.py --search-only

# Use abstracts only (skip PDF download)
python run.py --no-pdf

# Use university library proxy for paywalled papers
python run.py --ezproxy "https://ezproxy.library.edu/login?url="
```

## EZproxy Configuration

To access paywalled papers through your university library, configure EZproxy in `config/settings.yaml`:

```yaml
pdf:
  ezproxy:
    # Enable EZproxy
    enabled: true

    # Your university's EZproxy prefix URL
    prefix: "https://ezproxy.youruniversity.edu/login?url="

    # Try direct URL first (recommended - faster for open access papers)
    try_direct_first: true

    # Use DOI-based URLs when direct PDF link isn't available
    use_doi_urls: true
```

Or use the command-line option:

```bash
python run.py --ezproxy "https://ezproxy.youruniversity.edu/login?url="
```

### How It Works

1. **Direct access first**: If enabled, tries the open access URL directly
2. **Proxied URL**: Routes the PDF URL through your library's EZproxy
3. **DOI fallback**: For papers without direct PDF links, constructs publisher-specific URLs using the DOI and routes them through the proxy

### Finding Your EZproxy URL

Your university library's EZproxy prefix is typically in one of these formats:
- `https://ezproxy.library.edu/login?url=`
- `https://proxy.library.edu/login?url=`
- `https://libproxy.university.edu/login?url=`

Check your library's website or ask a librarian for the correct prefix.

## Output

The pipeline generates outputs in the `outputs/` directory:

```
outputs/
├── pdfs/              # Downloaded PDF files
└── reports/
    ├── papers/        # Individual paper reports (Markdown)
    ├── summary_report_*.md    # Overall summary report
    └── papers_data_*.json     # Raw data export
```

### Individual Paper Reports

Each paper gets a detailed Markdown report including:
- Metadata (authors, year, journal, citations)
- Abstract
- AI-generated summary
- Key findings
- AI techniques identified
- Methodology evaluation (strengths/limitations)

### Summary Report

The summary report includes:
- Search configuration used
- Statistics (total papers, PDFs available, analyzed)
- Papers by journal breakdown
- Top papers by citations
- Common AI techniques across papers
- Full paper listing table

## Architecture

```
src/
├── search/
│   └── semantic_scholar.py   # Semantic Scholar API client
├── pdf/
│   ├── checker.py            # PDF availability & download
│   └── extractor.py          # Text extraction from PDFs
├── analysis/
│   └── analyzer.py           # Claude LLM analysis
├── reports/
│   └── generator.py          # Report generation
└── pipeline.py               # Main orchestrator
```

## API Rate Limits

- **Semantic Scholar**: 10 requests/second (no API key needed)
- **Anthropic Claude**: Based on your plan tier

## Adding New Journals

Simply edit `config/settings.yaml`:

```yaml
journals:
  - "Neurology"
  - "JAMA Neurology"
  - "Annals of Neurology"
  - "New England Journal of Medicine"
  - "Lancet Neurology"        # Add new journals here
  - "Brain"
```

## Limitations

- PDF access depends on open access availability or EZproxy configuration
- Some papers may only be analyzed via abstract if PDF is not accessible
- Journal name matching in Semantic Scholar may vary (use exact names)
- EZproxy requires valid institutional credentials (typically via browser session)
