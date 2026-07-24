from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


# -- API
class APISettings(BaseModel):
    title: str = "Multi-Armed Bandit Optimization API"
    version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = Field(
        default=8000,
        ge=1,
        le=65_535,
    )
    debug: bool = False
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"


# -- Database
class DatabaseSettings(BaseModel):
    path: str = "bandit.db"
    echo: bool = False

    @property
    def url(self) -> str:
        database_path = Path(self.path)

        if not database_path.is_absolute():
            database_path = (
                PROJECT_ROOT / database_path
            )

        return (
            "sqlite+aiosqlite:///"
            f"{database_path.as_posix()}"
        )


# -- Bandit Algorithm
class ThompsonSamplingSettings(BaseModel):
    simulations: int = Field(
        default=10_000,
        ge=1,
    )
    prior_alpha: float = Field(
        default=1.0,
        gt=0,
    )
    prior_beta: float = Field(
        default=1.0,
        gt=0,
    )
    random_seed: int | None = None


# -- Traffic Allocation Rules
class AllocationSettings(BaseModel):
    minimum_allocation: float = Field(
        default=0.05,
        ge=0,
        lt=1,
    )
    percentage_precision: int = Field(
        default=2,
        ge=0,
        le=6,
    )

    def validate_for_variant_count(
        self,
        variant_count: int,
    ) -> None:
        if variant_count <= 0:
            raise ValueError(
                "Variant count must be greater than zero."
            )

        if (
            self.minimum_allocation
            * variant_count
            > 1
        ):
            raise ValueError(
                "Minimum allocation is too high "
                "for the number of variants."
            )


# -- Logging
class LoggingSettings(BaseModel):
    level: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "INFO"

    json_logs: bool = False


# -- Global Settings
class Settings(BaseSettings):
    environment: Literal[
        "local",
        "test",
        "development",
        "staging",
        "production",
    ] = "local"

    api: APISettings = APISettings()
    database: DatabaseSettings = DatabaseSettings()
    thompson_sampling: ThompsonSamplingSettings = (
        ThompsonSamplingSettings()
    )
    allocation: AllocationSettings = (
        AllocationSettings()
    )
    logging: LoggingSettings = LoggingSettings()

    model_config = SettingsConfigDict(
        # Resolve the file from the project root so configuration works even
        # when the application is started from another working directory.
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_environment_settings(
        self,
    ) -> "Settings":
        if (
            self.environment == "production"
            and self.api.debug
        ):
            raise ValueError(
                "API debug mode must be disabled "
                "in production."
            )

        return self


settings = Settings()