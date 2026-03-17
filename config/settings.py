"""
Market Intelligence Terminal — Central Configuration

Uses pydantic-settings to load and validate all environment variables.
Variables are read from the .env file at project root.

LLM Role Architecture:
    - LLM_ANALYST_MODEL (llama3)  → Deep financial reasoning, answers
      user questions about market history, company analysis, etc.
    - LLM_ROUTER_MODEL  (mistral) → Fast intent classification, routes
      incoming queries to the correct handler (finance, data, history).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    All configuration is loaded from environment variables.
    Copy .env.example to .env and fill in your values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql://market_user:market_pass_2024@localhost:5432/market_intelligence",
        description="PostgreSQL connection string (TimescaleDB enabled)",
    )

    # ── Ollama (Local LLM Runtime) ──────────────────────────
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for the Ollama API server",
    )
    llm_analyst_model: str = Field(
        default="llama3",
        description="Model for deep market analysis and financial Q&A",
    )
    llm_router_model: str = Field(
        default="mistral",
        description="Model for fast query intent classification / routing",
    )

    # ── API Server ──────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # ── Data Pipeline ───────────────────────────────────────
    data_start_date: str = Field(
        default="1990-01-01",
        description="Earliest date for historical data ingestion",
    )
    sp500_enabled: bool = Field(
        default=True,
        description="Enable S&P 500 stock data ingestion",
    )
    crypto_enabled: bool = Field(
        default=True,
        description="Enable cryptocurrency data ingestion",
    )

    # ── Scheduler ─────────────────────────────────────────
    scheduler_enabled: bool = Field(
        default=True,
        description="Enable daily auto-update scheduler",
    )
    scheduler_hour: int = Field(
        default=16,
        description="Hour to run daily update (24h format, ET timezone)",
    )
    scheduler_minute: int = Field(
        default=30,
        description="Minute to run daily update",
    )

    # ── Derived helpers (not from env) ──────────────────────

    @property
    def database_url_async(self) -> str:
        """Async variant of DATABASE_URL for async SQLAlchemy sessions."""
        return self.database_url.replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )


# Singleton — import this everywhere
settings = Settings()
