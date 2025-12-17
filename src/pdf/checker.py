"""PDF availability checker."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests


@dataclass
class PDFStatus:
    """Status of PDF availability for a paper."""

    paper_id: str
    available: bool
    url: Optional[str] = None
    local_path: Optional[str] = None
    error: Optional[str] = None
    size_bytes: Optional[int] = None


class PDFChecker:
    """Check PDF availability and download PDFs."""

    def __init__(
        self,
        download_dir: str = "outputs/pdfs",
        max_size_mb: int = 50,
        timeout: int = 30,
    ):
        """Initialize the PDF checker.

        Args:
            download_dir: Directory to store downloaded PDFs.
            max_size_mb: Maximum file size to download (in MB).
            timeout: Request timeout in seconds.
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "AcademicPaperPipeline/1.0 (Research Tool; Contact: researcher@example.com)"
        )

    def check_availability(self, pdf_url: Optional[str]) -> tuple[bool, Optional[str]]:
        """Check if a PDF is available at the given URL.

        Args:
            pdf_url: URL to check.

        Returns:
            Tuple of (is_available, error_message).
        """
        if not pdf_url:
            return False, "No PDF URL provided"

        try:
            response = self.session.head(
                pdf_url,
                timeout=self.timeout,
                allow_redirects=True,
            )

            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")
                if "pdf" in content_type.lower() or pdf_url.lower().endswith(".pdf"):
                    return True, None
                return False, f"Not a PDF (Content-Type: {content_type})"

            return False, f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            return False, "Request timed out"
        except requests.exceptions.RequestException as e:
            return False, str(e)

    def download(
        self,
        paper_id: str,
        pdf_url: str,
        filename: Optional[str] = None,
    ) -> PDFStatus:
        """Download a PDF file.

        Args:
            paper_id: Unique identifier for the paper.
            pdf_url: URL to download from.
            filename: Optional custom filename.

        Returns:
            PDFStatus with download result.
        """
        if not filename:
            # Sanitize paper_id for filename
            safe_id = "".join(c if c.isalnum() else "_" for c in paper_id)
            filename = f"{safe_id}.pdf"

        local_path = self.download_dir / filename

        # Check if already downloaded
        if local_path.exists():
            return PDFStatus(
                paper_id=paper_id,
                available=True,
                url=pdf_url,
                local_path=str(local_path),
                size_bytes=local_path.stat().st_size,
            )

        try:
            # Stream download to handle large files
            response = self.session.get(
                pdf_url,
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()

            # Check content length
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > self.max_size_bytes:
                return PDFStatus(
                    paper_id=paper_id,
                    available=False,
                    url=pdf_url,
                    error=f"File too large ({int(content_length) / 1024 / 1024:.1f} MB)",
                )

            # Download in chunks
            downloaded_size = 0
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    downloaded_size += len(chunk)
                    if downloaded_size > self.max_size_bytes:
                        f.close()
                        local_path.unlink()  # Delete partial file
                        return PDFStatus(
                            paper_id=paper_id,
                            available=False,
                            url=pdf_url,
                            error=f"File exceeded size limit during download",
                        )
                    f.write(chunk)

            return PDFStatus(
                paper_id=paper_id,
                available=True,
                url=pdf_url,
                local_path=str(local_path),
                size_bytes=downloaded_size,
            )

        except requests.exceptions.Timeout:
            return PDFStatus(
                paper_id=paper_id,
                available=False,
                url=pdf_url,
                error="Download timed out",
            )
        except requests.exceptions.RequestException as e:
            return PDFStatus(
                paper_id=paper_id,
                available=False,
                url=pdf_url,
                error=str(e),
            )

    def check_and_download(
        self,
        paper_id: str,
        pdf_url: Optional[str],
    ) -> PDFStatus:
        """Check availability and download if available.

        Args:
            paper_id: Unique identifier for the paper.
            pdf_url: URL to the PDF.

        Returns:
            PDFStatus with result.
        """
        available, error = self.check_availability(pdf_url)

        if not available:
            return PDFStatus(
                paper_id=paper_id,
                available=False,
                url=pdf_url,
                error=error,
            )

        return self.download(paper_id, pdf_url)
