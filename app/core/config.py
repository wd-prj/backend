import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "ZenithHR Enterprise Leave & PTO Orchestration Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:swetha4106%23@db.xaunicirtzzklpmmenfa.supabase.co:5432/postgres",
    )

    @field_validator("DATABASE_URL", mode="before")
    def assemble_db_connection(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgresql://") and not v.startswith("postgresql+"):
                v = v.replace("postgresql://", "postgresql+psycopg://", 1)
            if "swetha4106#" in v:
                v = v.replace("swetha4106#", "swetha4106%23")
        return v

    # Security & Auth
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "zenith-enterprise-secure-jwt-production-token-2026"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    SESSION_COOKIE_NAME: str = "wtf_session"
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: str = "lax"

    # Bootstrap HR Admin
    BOOTSTRAP_ADMIN_EMAIL: str = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@zenithhr.com")
    BOOTSTRAP_ADMIN_PASSWORD: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "ZenithAdmin2026!")

    # Email & Resend Provider
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "resend")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "ZenithHR <onboarding@resend.dev>")
    APP_URL: str = os.getenv("APP_URL", "https://zenithhr-platform.netlify.app")
    INVITATION_EXPIRE_HOURS: int = 48

    # CORS
    CORS_ORIGINS: List[str] = [
        "https://zenithhr-platform.netlify.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

    # LLM & AI Provider Configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "mimo-v2.5-free")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://opencode.ai/zen/v1")
    LLM_TEMPERATURE: float = 0.0


settings = Settings()
