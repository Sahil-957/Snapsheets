from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bulk OCR Extractor API"
    debug: bool = Field(default=False)
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    storage_root: Path = Path("storage")
    uploads_dir_name: str = "uploads"
    outputs_dir_name: str = "outputs"
    temp_dir_name: str = "temp"
    tesseract_confidence_threshold: float = 80.0
    max_workers: int = 4
    batch_size: int = 10
    upload_max_files: int = 10000
    tesseract_cmd: str | None = None
    google_application_credentials: str | None = None

    @field_validator("debug", mode="before")
    @classmethod
    def coerce_debug(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on", "debug"}:
                return True
            if lowered in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def uploads_path(self) -> Path:
        return self.storage_root / self.uploads_dir_name

    @property
    def outputs_path(self) -> Path:
        return self.storage_root / self.outputs_dir_name

    @property
    def temp_path(self) -> Path:
        return self.storage_root / self.temp_dir_name


settings = Settings()
