"""Axiom backend configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Axiom"
    app_version: str = "1.3.2"
    debug: bool = True

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    database_url: str = (
        f"sqlite:///{Path(__file__).resolve().parent.parent.parent / 'database' / 'axiom.db'}"
    )
    upload_dir: Path = Path(__file__).resolve().parent.parent / "uploads"
    vision_upload_dir: Path = Path(__file__).resolve().parent.parent / "uploads" / "vision"
    document_upload_dir: Path = Path(__file__).resolve().parent.parent / "uploads" / "documents"

    # Local single-user mode
    default_user_id: int = 1
    default_user_name: str = "Student"
    default_user_email: str = "student@axiom.local"

    # Text ModelProvider (Brain). Phase 2: ollama live; openai/anthropic later.
    # See docs/AXIOM_PRODUCT_ARCHITECTURE.md — Model ≠ product; Axiom understands the learner.
    ai_provider: str = "ollama"  # ollama | openai | anthropic | cloud(deprecated)
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2:latest"

    # VisionProvider — v0.3 phase 1
    # Default mock until user confirms pulling a local VLM (recommended: moondream)
    vision_provider: str = "mock"  # mock | ollama | cloud
    ollama_vision_model: str = "moondream:latest"
    max_image_bytes: int = 5 * 1024 * 1024

    # Upload / document ingestion
    max_upload_size: int = 20 * 1024 * 1024
    max_pdf_pages: int = 200
    chunk_size: int = 900
    chunk_overlap: int = 120

    # Agent / providers
    max_agent_steps: int = 6
    model_timeout_seconds: float = 120.0
    vision_timeout_seconds: float = 180.0
    tool_timeout_seconds: float = 5.0
    python_timeout_seconds: float = 3.0
    python_output_limit: int = 20_000

    # Vision confidence boundaries
    vision_high_confidence_threshold: float = 0.75
    vision_low_confidence_threshold: float = 0.35

    # Local deterministic embeddings (no extra model download)
    embedding_provider: str = "local_hash"
    embedding_dimensions: int = 256


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.vision_upload_dir.mkdir(parents=True, exist_ok=True)
settings.document_upload_dir.mkdir(parents=True, exist_ok=True)
(Path(__file__).resolve().parent.parent.parent / "database").mkdir(parents=True, exist_ok=True)
