"""PDF text extraction."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pdfplumber


@dataclass
class ExtractedText:
    """Extracted text from a PDF."""

    paper_id: str
    success: bool
    text: Optional[str] = None
    page_count: int = 0
    error: Optional[str] = None


class PDFExtractor:
    """Extract text from PDF files."""

    def __init__(self, max_pages: int = 100):
        """Initialize the extractor.

        Args:
            max_pages: Maximum number of pages to extract.
        """
        self.max_pages = max_pages

    def extract(self, pdf_path: str, paper_id: str) -> ExtractedText:
        """Extract text from a PDF file.

        Args:
            pdf_path: Path to the PDF file.
            paper_id: Unique identifier for the paper.

        Returns:
            ExtractedText with the result.
        """
        path = Path(pdf_path)

        if not path.exists():
            return ExtractedText(
                paper_id=paper_id,
                success=False,
                error=f"File not found: {pdf_path}",
            )

        try:
            text_parts = []
            page_count = 0

            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages):
                    if i >= self.max_pages:
                        break

                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"--- Page {i + 1} ---\n{page_text}")
                    page_count += 1

            full_text = "\n\n".join(text_parts)

            if not full_text.strip():
                return ExtractedText(
                    paper_id=paper_id,
                    success=False,
                    page_count=page_count,
                    error="No text could be extracted (possibly scanned/image PDF)",
                )

            return ExtractedText(
                paper_id=paper_id,
                success=True,
                text=full_text,
                page_count=page_count,
            )

        except Exception as e:
            return ExtractedText(
                paper_id=paper_id,
                success=False,
                error=f"Extraction failed: {str(e)}",
            )

    def extract_sections(self, text: str) -> dict[str, str]:
        """Attempt to identify common paper sections.

        Args:
            text: Full extracted text.

        Returns:
            Dictionary mapping section names to content.
        """
        sections = {}
        current_section = "preamble"
        current_content = []

        # Common section headers
        section_keywords = [
            "abstract",
            "introduction",
            "background",
            "methods",
            "methodology",
            "materials and methods",
            "results",
            "discussion",
            "conclusion",
            "conclusions",
            "references",
            "acknowledgments",
            "acknowledgements",
        ]

        for line in text.split("\n"):
            line_lower = line.lower().strip()

            # Check if this line is a section header
            is_header = False
            for keyword in section_keywords:
                if line_lower == keyword or line_lower.startswith(f"{keyword}:"):
                    # Save current section
                    if current_content:
                        sections[current_section] = "\n".join(current_content)

                    current_section = keyword
                    current_content = []
                    is_header = True
                    break

            if not is_header:
                current_content.append(line)

        # Save final section
        if current_content:
            sections[current_section] = "\n".join(current_content)

        return sections
