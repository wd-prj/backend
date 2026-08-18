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
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5431/wtf"

    # Security & Auth
    SECRET_KEY: str = "dev_secret_key_leave_orchestration_platform_change_in_production_987654321"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    SESSION_COOKIE_NAME: str = "wtf_session"
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: str = "lax"

    # Bootstrap HR Admin
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@zenithhr.com"
    BOOTSTRAP_ADMIN_PASSWORD: str = "ZenithAdmin2026!"

    # Email & Resend Provider
    EMAIL_PROVIDER: str = "resend"  # "resend" | "mock" | "console"
    RESEND_API_KEY: str = "re_gWX4zeKa_J1H2Tns9m81hQZM31Nituqbe"
    EMAIL_FROM: str = "ZenithHR <onboarding@resend.dev>"
    APP_URL: str = "http://localhost:3000"
    INVITATION_EXPIRE_HOURS: int = 48

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

    # LLM & AI Provider Configuration
    LLM_PROVIDER: str = "mock"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_TEMPERATURE: float = 0.0


settings = Settings()
