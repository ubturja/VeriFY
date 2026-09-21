from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = Field(default="local", alias="VERIFY_ENV")
    log_level: str = Field(default="INFO", alias="VERIFY_LOG_LEVEL")
    api_host: str = Field(default="0.0.0.0", alias="VERIFY_API_HOST")
    api_port: int = Field(default=8000, alias="VERIFY_API_PORT")
    cors_origins: str = Field(default="http://localhost:5173", alias="VERIFY_CORS_ORIGINS")

    data_dir: Path = Field(default=Path("../../sdoc-hackathon-bundle"), alias="VERIFY_DATA_DIR")
    ground_truth: Path | None = Field(default=None, alias="VERIFY_GROUND_TRUTH")
    inbox_url: str | None = Field(default=None, alias="VERIFY_INBOX_URL")

    database_url: str = Field(
        default="postgresql+asyncpg://verify:verify@localhost:5432/verify",
        alias="VERIFY_DATABASE_URL",
    )

    blob_backend: str = Field(default="local", alias="VERIFY_BLOB_BACKEND")
    local_blob_dir: Path = Field(default=Path("./artifacts/blob"), alias="VERIFY_LOCAL_BLOB_DIR")

    queue_backend: str = Field(default="inmemory", alias="VERIFY_QUEUE_BACKEND")

    llm_primary: str = Field(default="gemini", alias="VERIFY_LLM_PRIMARY")
    llm_fallback: str = Field(default="groq", alias="VERIFY_LLM_FALLBACK")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_classify_model: str = Field(default="gemini-2.5-flash-lite", alias="GEMINI_CLASSIFY_MODEL")
    gemini_extract_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_EXTRACT_MODEL")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_text_model: str = Field(default="openai/gpt-oss-120b", alias="GROQ_TEXT_MODEL")
    groq_vision_model: str = Field(
        default="meta-llama/llama-4-scout-17b-16e-instruct",
        alias="GROQ_VISION_MODEL",
    )

    ocr_backend: str = Field(default="tesseract", alias="VERIFY_OCR_BACKEND")
    azure_document_intelligence_endpoint: str = Field(default="", alias="AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    azure_document_intelligence_key: str = Field(default="", alias="AZURE_DOCUMENT_INTELLIGENCE_KEY")

    mail_source: str = Field(default="hackathon", alias="VERIFY_MAIL_SOURCE")
    imap_host: str = Field(default="imap.gmail.com", alias="IMAP_HOST")
    imap_port: int = Field(default=993, alias="IMAP_PORT")
    imap_username: str = Field(default="", alias="IMAP_USERNAME")
    imap_app_password: str = Field(default="", alias="IMAP_APP_PASSWORD")
    imap_folder: str = Field(default="INBOX", alias="IMAP_FOLDER")
    imap_poll_seconds: int = Field(default=30, alias="IMAP_POLL_SECONDS")
    imap_autopoll: bool = Field(default=True, alias="VERIFY_IMAP_AUTOPOLL")

    auth_mode: str = Field(default="session", alias="VERIFY_AUTH_MODE")
    tenants_dir: Path = Field(default=Path("artifacts/tenants"), alias="VERIFY_TENANTS_DIR")
    secret_key: str = Field(default="", alias="VERIFY_SECRET_KEY")
    require_secret_key: bool = Field(default=False, alias="VERIFY_REQUIRE_SECRET_KEY")
    state_path: Path | None = Field(default=Path("artifacts/state.json"), alias="VERIFY_STATE_PATH")

    @field_validator(
        "data_dir",
        "local_blob_dir",
        "ground_truth",
        "state_path",
        "tenants_dir",
        mode="before",
    )
    @classmethod
    def expand_path(cls, value: str | Path | None) -> Path | None:
        if value in (None, "", "None"):
            return None
        path = Path(str(value)).expanduser()
        if not path.is_absolute():
            path = (REPO_ROOT / path).resolve()
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.gemini_api_key or self.groq_api_key)


def get_settings() -> Settings:
    return Settings()
