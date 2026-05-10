"""
Unified Configuration Module.

Provides shared settings, environment variables, and configuration classes
for both workspaces. Domain-specific configurations (like Banking's thresholds)
will subclass this base Settings.
"""

import os
from dataclasses import dataclass, field
from pydantic_settings import BaseSettings

# ─── Data Classes for Rules & Standards ─────────────────────────────────────

@dataclass
class LinkedStandardRef:
    """A specific clause from a standard linked to a metric."""
    standard_id: str
    control_id: str
    clause: str
    description: str


@dataclass
class MetricDefinition:
    """Definition of a quality metric with its rule logic and linked standards."""
    id: str
    name: str
    category: str
    weight: float
    rule_fn: str
    description: str
    linked_standards: list[LinkedStandardRef] = field(default_factory=list)


# ─── Base Configuration ──────────────────────────────────────────────────────

class Settings(BaseSettings):
    """Core configuration shared by all workspaces."""
    
    # Server
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    UNIFIED_DB_DIR: str = os.path.join(DATA_DIR, "unified")
    
    # We leave UPLOAD_DIR abstract here, as each workspace can set its own
    UPLOAD_DIR: str = os.path.join(DATA_DIR, "uploads")
    
    # LLM Settings (Azure Foundry)
    FOUNDRY_API_KEY: str = os.getenv("FOUNDRY_API_KEY", "")
    FOUNDRY_ENDPOINT: str = os.getenv("FOUNDRY_ENDPOINT", "")
    FOUNDRY_MODEL: str = os.getenv("FOUNDRY_MODEL", "gpt-4o")
    FOUNDRY_API_VERSION: str = os.getenv("FOUNDRY_API_VERSION", "2024-08-01-preview")
    
    # LLM Processing
    LLM_TEMPERATURE: float = 0.0
    # Chunking config from Banking
    LLM_CHUNK_SIZE: int = 15000
    LLM_CHUNK_OVERLAP: int = 1000
    LLM_MAX_CHUNKS: int = 10
    
    # Generic Settings
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "5"))
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    KB_CHUNK_SIZE: int = int(os.getenv("KB_CHUNK_SIZE", "1000"))
    KB_CHUNK_OVERLAP: int = int(os.getenv("KB_CHUNK_OVERLAP", "200"))
    KB_MAX_RETRIEVAL_CHUNKS: int = int(os.getenv("KB_MAX_RETRIEVAL_CHUNKS", "5"))
    
    # Database URL format
    DATABASE_URL: str = "" # Set by subclasses or using core.database defaults
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

    def validate(self) -> list[str]:
        """Validate critical configuration settings and return warnings."""
        warnings = []
        if not self.FOUNDRY_API_KEY:
            warnings.append("FOUNDRY_API_KEY is not set.")
        if not self.FOUNDRY_ENDPOINT:
            warnings.append("FOUNDRY_ENDPOINT is not set.")
        return warnings

# A default instance for shared usage where workspace isn't specified
settings = Settings()
