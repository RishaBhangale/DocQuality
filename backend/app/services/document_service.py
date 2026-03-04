"""
Document processing service.

Handles file validation, text extraction from PDF, DOCX, image files,
JSON, TXT, CSV, XML, HTML, and EML, plus text normalization.
"""

import csv
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Optional

import pdfplumber
from docx import Document as DocxDocument
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

# Try to import pytesseract; it requires Tesseract-OCR to be installed
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available. OCR features will be disabled.")


class DocumentService:
    """
    Service for document file handling and text extraction.

    Supports PDF, DOCX, and image file formats with proper
    validation and error handling.
    """

    SUPPORTED_EXTENSIONS: set[str] = set(settings.SUPPORTED_FILE_TYPES)

    def __init__(self) -> None:
        """Initialize the document service."""
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    def validate_file_type(self, filename: str) -> bool:
        """
        Validate that the file extension is supported.

        Args:
            filename: Original filename to validate.

        Returns:
            True if the file type is supported.

        Raises:
            ValueError: If the file type is not supported.
        """
        ext = Path(filename).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: '{ext}'. "
                f"Supported types: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )
        return True

    def validate_file_size(self, file_size: int) -> bool:
        """
        Validate that the file size is within limits.

        Args:
            file_size: Size of the file in bytes.

        Returns:
            True if the file size is within limits.

        Raises:
            ValueError: If the file exceeds the maximum size.
        """
        if file_size > settings.MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File size ({file_size / 1024 / 1024:.2f} MB) exceeds "
                f"maximum allowed size ({settings.MAX_FILE_SIZE_MB} MB)."
            )
        return True

    def extract_text(self, file_path: str) -> str:
        """
        Extract text from a file based on its extension.

        Args:
            file_path: Path to the uploaded file.

        Returns:
            Extracted and normalized text content.

        Raises:
            ValueError: If the file type is not supported.
            RuntimeError: If text extraction fails.
        """
        ext = Path(file_path).suffix.lower()

        try:
            if ext == ".pdf":
                raw_text = self.extract_text_from_pdf(file_path)
            elif ext == ".docx":
                raw_text = self.extract_text_from_docx(file_path)
            elif ext in {".png", ".jpg", ".jpeg"}:
                raw_text = self.extract_text_from_image(file_path)
            elif ext == ".json":
                raw_text = self.extract_text_from_json(file_path)
            elif ext == ".txt":
                raw_text = self.extract_text_from_txt(file_path)
            elif ext == ".csv":
                raw_text = self.extract_text_from_csv(file_path)
            elif ext == ".xml":
                raw_text = self.extract_text_from_xml(file_path)
            elif ext in {".html", ".htm"}:
                raw_text = self.extract_text_from_html(file_path)
            elif ext == ".eml":
                raw_text = self.extract_text_from_eml(file_path)
            else:
                raise ValueError(f"Unsupported file extension: {ext}")

            normalized = self.normalize_text(raw_text)
            logger.info(
                "Extracted %d characters from %s (normalized: %d)",
                len(raw_text), file_path, len(normalized)
            )
            return normalized

        except Exception as e:
            logger.error("Text extraction failed for %s: %s", file_path, str(e))
            raise RuntimeError(f"Failed to extract text from file: {str(e)}") from e

    def extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extract text from a PDF file using pdfplumber.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Concatenated text from all pages.
        """
        text_parts: list[str] = []
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                else:
                    logger.debug("No text extracted from page %d of %s", page_num, file_path)
        return "\n".join(text_parts)

    def extract_text_from_docx(self, file_path: str) -> str:
        """
        Extract text from a DOCX file using python-docx.

        Args:
            file_path: Path to the DOCX file.

        Returns:
            Concatenated text from all paragraphs.
        """
        doc = DocxDocument(file_path)
        text_parts: list[str] = []

        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)

        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    text_parts.append(row_text)

        return "\n".join(text_parts)

    def extract_text_from_image(self, file_path: str) -> str:
        """
        Extract text from an image file using OCR (Tesseract).

        Args:
            file_path: Path to the image file.

        Returns:
            OCR-extracted text.

        Raises:
            RuntimeError: If Tesseract is not available.
        """
        if not TESSERACT_AVAILABLE:
            raise RuntimeError(
                "OCR is not available. Install Tesseract-OCR and pytesseract to process images."
            )

        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        return text

    def extract_text_from_json(self, file_path: str) -> str:
        """
        Extract text from a JSON file by flattening all values.

        Args:
            file_path: Path to the JSON file.

        Returns:
            Flattened text representation of the JSON data.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self._flatten_json(data)

    def extract_raw_json(self, file_path: str) -> Any:
        """
        Load and return the raw parsed JSON object.
        Used by type-specific JSON metrics.

        Args:
            file_path: Path to the JSON file.

        Returns:
            Parsed JSON data (dict or list).
        """
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def extract_text_from_txt(self, file_path: str) -> str:
        """
        Extract text from a plain text file.

        Args:
            file_path: Path to the TXT file.

        Returns:
            File contents as text.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def extract_text_from_csv(self, file_path: str) -> str:
        """
        Extract text from a CSV file by joining all cells.

        Args:
            file_path: Path to the CSV file.

        Returns:
            Text with each row on a new line.
        """
        text_parts = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                text_parts.append(" ".join(row))
        return "\n".join(text_parts)

    def extract_text_from_xml(self, file_path: str) -> str:
        """
        Extract all text nodes from an XML file.

        Args:
            file_path: Path to the XML file.

        Returns:
            Concatenated text from all XML elements.
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            texts = []
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    texts.append(elem.text.strip())
                if elem.tail and elem.tail.strip():
                    texts.append(elem.tail.strip())
            return "\n".join(texts)
        except ET.ParseError:
            logger.warning("XML ParseError in %s. Falling back to BeautifulSoup text extraction.", file_path)
            return self.extract_text_from_html(file_path)

    def extract_text_from_html(self, file_path: str) -> str:
        """
        Extract text from an HTML file by stripping tags.

        Args:
            file_path: Path to the HTML file.

        Returns:
            Plain text extracted from HTML.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise RuntimeError("beautifulsoup4 is required for HTML parsing. Install with: pip install beautifulsoup4")
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        return soup.get_text(separator="\n", strip=True)

    def extract_text_from_eml(self, file_path: str) -> str:
        """
        Extract text from an email (.eml) file.

        Args:
            file_path: Path to the EML file.

        Returns:
            Email subject + body as text.
        """
        with open(file_path, "rb") as f:
            msg = BytesParser(policy=policy.default).parse(f)
        parts = []
        subject = msg.get("subject", "")
        if subject:
            parts.append(f"Subject: {subject}")
        sender = msg.get("from", "")
        if sender:
            parts.append(f"From: {sender}")
        body = msg.get_body(preferencelist=("plain", "html"))
        if body:
            content = body.get_content()
            if body.get_content_type() == "text/html":
                try:
                    from bs4 import BeautifulSoup
                    content = BeautifulSoup(content, "html.parser").get_text(separator="\n", strip=True)
                except ImportError:
                    pass
            parts.append(content)
        return "\n".join(parts)

    def _flatten_json(self, data: Any, prefix: str = "") -> str:
        """Recursively flatten JSON into readable text."""
        parts = []
        if isinstance(data, dict):
            for key, value in data.items():
                parts.append(self._flatten_json(value, prefix=f"{prefix}{key}: "))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                parts.append(self._flatten_json(item, prefix=f"{prefix}[{i}] "))
        else:
            parts.append(f"{prefix}{data}")
        return "\n".join(parts)

    def normalize_text(self, text: str) -> str:
        """
        Clean and normalize extracted text.

        - Removes excessive whitespace
        - Normalizes line endings
        - Strips leading/trailing whitespace

        Args:
            text: Raw extracted text.

        Returns:
            Cleaned and normalized text.
        """
        if not text:
            return ""

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Collapse multiple blank lines into one
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Collapse multiple spaces into one (but preserve newlines)
        text = re.sub(r"[^\S\n]+", " ", text)

        # Strip each line
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        return text.strip()

    async def save_upload(self, filename: str, content: bytes) -> str:
        """
        Save uploaded file content to disk.

        Args:
            filename: Original filename.
            content: File content as bytes.

        Returns:
            Full path to the saved file.
        """
        import uuid
        safe_name = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(settings.UPLOAD_DIR, safe_name)

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info("Saved upload: %s -> %s", filename, file_path)
        return file_path

    def cleanup_file(self, file_path: str) -> None:
        """
        Remove a temporary file from disk.

        Args:
            file_path: Path to the file to remove.
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug("Cleaned up file: %s", file_path)
        except OSError as e:
            logger.warning("Failed to clean up file %s: %s", file_path, str(e))
