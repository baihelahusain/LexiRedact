"""
PDF extraction for document chunking.
"""

from typing import Dict, Any
from pathlib import Path


class PDFLoader:
    """Load and extract text from PDF files."""

    def __init__(self, use_ocr: bool = False):
        """
        Initialize PDF loader.

        Args:
            use_ocr: Use OCR for scanned PDFs (requires pytesseract)
        """
        self.use_ocr = use_ocr

    @staticmethod
    def extract_text(pdf_path: str | Path) -> str:
        """
        Extract text from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text

        Raises:
            ImportError: If pypdf not installed
            FileNotFoundError: If PDF not found
        """
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError(
                "PDF support requires pypdf. "
                "Install with: pip install pypdf"
            )

        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        text = []
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                text.append(page.extract_text())

        return '\n\n'.join(text)

    @staticmethod
    def extract_metadata(pdf_path: str | Path) -> Dict[str, Any]:
        """
        Extract metadata from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Metadata dictionary
        """
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("PDF support requires pypdf")

        pdf_path = Path(pdf_path)
        metadata = {}

        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            if reader.metadata:
                metadata = {
                    "title": reader.metadata.get("/Title", ""),
                    "author": reader.metadata.get("/Author", ""),
                    "subject": reader.metadata.get("/Subject", ""),
                    "pages": len(reader.pages),
                    "pdf_file": str(pdf_path.name),
                }

        return metadata
