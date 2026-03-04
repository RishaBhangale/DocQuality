"""
Application configuration module.

Loads environment variables and provides centralized configuration
for all application components.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


class Settings:
    """Centralized application settings loaded from environment variables."""

    # Azure Foundry LLM Configuration
    FOUNDRY_API_KEY: str = os.getenv("FOUNDRY_API_KEY", "")
    FOUNDRY_ENDPOINT: str = os.getenv("FOUNDRY_ENDPOINT", "")
    FOUNDRY_MODEL: str = os.getenv("FOUNDRY_MODEL", "")
    FOUNDRY_API_VERSION: str = os.getenv("FOUNDRY_API_VERSION", "")

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./document_quality.db")

    # Application Configuration
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "5"))
    MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # LLM Configuration
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    LLM_TEMPERATURE: float = 0.0

    # Supported file types
    SUPPORTED_FILE_TYPES: list[str] = [
        ".pdf", ".docx", ".png", ".jpg", ".jpeg",
        ".json", ".txt", ".csv", ".xml", ".html", ".htm", ".eml",
    ]

    # Core metric weights (apply to all documents)
    METRIC_WEIGHTS: dict[str, float] = {
        "completeness": 0.25,
        "validity": 0.20,
        "consistency": 0.20,
        "accuracy": 0.20,
        "timeliness": 0.10,
        "uniqueness": 0.05,
    }

    # Type-specific metric weights (per document type)
    TYPE_SPECIFIC_METRIC_WEIGHTS: dict[str, dict[str, float]] = {
        "contract": {
            "clause_completeness": 0.30,
            "signature_presence": 0.25,
            "metadata_completeness": 0.25,
            "risk_clause_detection": 0.20,
        },
        "invoice": {
            "field_completeness": 0.35,
            "ocr_confidence": 0.30,
            "amount_consistency": 0.35,
        },
        "json": {
            "schema_compliance": 0.25,
            "type_validation": 0.25,
            "cross_field_consistency": 0.25,
            "schema_drift_rate": 0.25,
        },
        "social_media": {
            "language_consistency": 0.30,
            "offensive_rate": 0.35,
            "spam_detection": 0.35,
        },
        "tabular": {
            "row_completeness": 0.25,
            "column_type_consistency": 0.25,
            "header_quality": 0.25,
            "null_empty_ratio": 0.25,
        },
        "markup": {
            "tag_validity": 0.30,
            "nesting_depth": 0.20,
            "attribute_completeness": 0.30,
            "encoding_consistency": 0.20,
        },
        "email": {
            "header_completeness": 0.30,
            "recipient_validation": 0.25,
            "body_quality": 0.25,
            "attachment_check": 0.20,
        },
        "general": {
            "structure_quality": 0.25,
            "readability_score": 0.25,
            "section_completeness": 0.25,
            "keyword_density": 0.25,
        },
    }

    # Upload directory
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

    @classmethod
    def validate(cls) -> list[str]:
        """Validate critical configuration. Returns list of warnings."""
        warnings = []
        if not cls.FOUNDRY_API_KEY or cls.FOUNDRY_API_KEY == "your-api-key-here":
            warnings.append("FOUNDRY_API_KEY is not configured. LLM features will be unavailable.")
        if not cls.FOUNDRY_ENDPOINT or "your-foundry-endpoint" in cls.FOUNDRY_ENDPOINT:
            warnings.append("FOUNDRY_ENDPOINT is not configured. LLM features will be unavailable.")
        return warnings


settings = Settings()
