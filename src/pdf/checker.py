"""PDF availability checker with EZproxy support."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlparse

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
    used_proxy: bool = False


@dataclass
class EZProxyConfig:
    """EZproxy configuration."""

    enabled: bool = False
    prefix: str = ""
    try_direct_first: bool = True
    use_doi_urls: bool = True

    def get_proxied_url(self, url: str) -> str:
        """Convert a URL to use EZproxy.

        Args:
            url: Original URL.

        Returns:
            Proxied URL.
        """
        if not self.enabled or not self.prefix:
            return url

        # URL-encode the target URL and append to prefix
        return f"{self.prefix}{quote(url, safe='')}"

    def get_doi_url(self, doi: str) -> str:
        """Get a proxied DOI resolver URL.

        Args:
            doi: DOI string (e.g., "10.1234/example").

        Returns:
            Proxied DOI URL.
        """
        doi_url = f"https://doi.org/{doi}"
        if self.enabled and self.prefix:
            return self.get_proxied_url(doi_url)
        return doi_url


class PDFChecker:
    """Check PDF availability and download PDFs with EZproxy support."""

    # Known publisher PDF URL patterns
    PUBLISHER_PDF_PATTERNS = {
        "sciencedirect.com": "/pdfft?",
        "wiley.com": "/pdfdirect/",
        "nature.com": ".pdf",
        "springer.com": ".pdf",
        "nejm.org": "/pdf/",
        "jamanetwork.com": "/fullarticle/",
        "neurology.org": ".pdf",
        "lww.com": "/fulltext/",
    }

    def __init__(
        self,
        download_dir: str = "outputs/pdfs",
        max_size_mb: int = 50,
        timeout: int = 30,
        ezproxy_config: Optional[EZProxyConfig] = None,
    ):
        """Initialize the PDF checker.

        Args:
            download_dir: Directory to store downloaded PDFs.
            max_size_mb: Maximum file size to download (in MB).
            timeout: Request timeout in seconds.
            ezproxy_config: EZproxy configuration for library access.
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.timeout = timeout
        self.ezproxy = ezproxy_config or EZProxyConfig()

        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        # Accept cookies for proxy authentication
        self.session.headers["Accept"] = "application/pdf,*/*"

    def _try_url(self, url: str) -> tuple[bool, Optional[str], Optional[requests.Response]]:
        """Try to access a URL and check if it returns a PDF.

        Args:
            url: URL to check.

        Returns:
            Tuple of (success, error_message, response).
        """
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=True,
                stream=True,
            )

            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")
                if "pdf" in content_type.lower():
                    return True, None, response
                # Check if we got an HTML page (might be login page)
                if "html" in content_type.lower():
                    return False, "Got HTML instead of PDF (may require authentication)", None

            return False, f"HTTP {response.status_code}", None

        except requests.exceptions.Timeout:
            return False, "Request timed out", None
        except requests.exceptions.RequestException as e:
            return False, str(e), None

    def _construct_doi_pdf_url(self, doi: str) -> Optional[str]:
        """Try to construct a direct PDF URL from a DOI.

        Args:
            doi: DOI string.

        Returns:
            Potential PDF URL or None.
        """
        # Common patterns for converting DOI to PDF URL
        # These are publisher-specific heuristics
        doi_lower = doi.lower()

        if "10.1056" in doi:  # NEJM
            return f"https://www.nejm.org/doi/pdf/{doi}"
        elif "10.1001" in doi:  # JAMA
            return f"https://jamanetwork.com/journals/jamaneurology/articlepdf/{doi}"
        elif "10.1212" in doi:  # Neurology (AAN)
            return f"https://n.neurology.org/content/neurology/early/doi/{doi}.full.pdf"
        elif "10.1002/ana" in doi:  # Annals of Neurology (Wiley)
            return f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}"

        return None

    def check_availability(
        self,
        pdf_url: Optional[str],
        doi: Optional[str] = None,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Check if a PDF is available, trying multiple sources.

        Args:
            pdf_url: Direct PDF URL (if known).
            doi: DOI for the paper (optional, for fallback).

        Returns:
            Tuple of (is_available, working_url, error_message).
        """
        urls_to_try = []

        # Strategy 1: Try direct open access URL first (if available and configured)
        if pdf_url and self.ezproxy.try_direct_first:
            urls_to_try.append(("direct", pdf_url))

        # Strategy 2: Try proxied version of the open access URL
        if pdf_url and self.ezproxy.enabled:
            proxied = self.ezproxy.get_proxied_url(pdf_url)
            if proxied != pdf_url:
                urls_to_try.append(("proxy", proxied))

        # Strategy 3: Try DOI-based URLs through proxy
        if doi and self.ezproxy.enabled and self.ezproxy.use_doi_urls:
            # Try constructed publisher PDF URL
            doi_pdf_url = self._construct_doi_pdf_url(doi)
            if doi_pdf_url:
                urls_to_try.append(("doi_pdf_proxy", self.ezproxy.get_proxied_url(doi_pdf_url)))

            # Try generic DOI resolver through proxy
            urls_to_try.append(("doi_proxy", self.ezproxy.get_doi_url(doi)))

        if not urls_to_try:
            return False, None, "No PDF URL or DOI available"

        last_error = None
        for url_type, url in urls_to_try:
            success, error, _ = self._try_url(url)
            if success:
                return True, url, None
            last_error = f"{url_type}: {error}"

        return False, None, last_error

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

            # Verify we got a PDF
            content_type = response.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower() and not pdf_url.lower().endswith(".pdf"):
                return PDFStatus(
                    paper_id=paper_id,
                    available=False,
                    url=pdf_url,
                    error=f"Not a PDF (Content-Type: {content_type})",
                )

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
                            error="File exceeded size limit during download",
                        )
                    f.write(chunk)

            # Verify the file is actually a PDF
            with open(local_path, "rb") as f:
                header = f.read(8)
                if not header.startswith(b"%PDF"):
                    local_path.unlink()
                    return PDFStatus(
                        paper_id=paper_id,
                        available=False,
                        url=pdf_url,
                        error="Downloaded file is not a valid PDF",
                    )

            used_proxy = self.ezproxy.enabled and self.ezproxy.prefix in pdf_url

            return PDFStatus(
                paper_id=paper_id,
                available=True,
                url=pdf_url,
                local_path=str(local_path),
                size_bytes=downloaded_size,
                used_proxy=used_proxy,
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
        doi: Optional[str] = None,
    ) -> PDFStatus:
        """Check availability and download if available.

        Args:
            paper_id: Unique identifier for the paper.
            pdf_url: URL to the PDF (optional).
            doi: DOI for the paper (optional, for fallback).

        Returns:
            PDFStatus with result.
        """
        available, working_url, error = self.check_availability(pdf_url, doi)

        if not available:
            return PDFStatus(
                paper_id=paper_id,
                available=False,
                url=pdf_url,
                error=error,
            )

        return self.download(paper_id, working_url)
