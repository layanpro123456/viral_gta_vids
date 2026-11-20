"""Configuration loading and validation via Pydantic and TOML."""

import os
from pathlib import Path
import tomllib
from typing import Any, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from viceclip.domain.entities import ScoringWeights


class DiscoverySettings(BaseModel):
    """Configuration for discovery adapters and scoring thresholds."""
    keywords: List[str] = Field(default_factory=lambda: ["GTA 6", "Grand Theft Auto VI", "#GTA6", "Vice City"])
    exclude_keywords: List[str] = Field(default_factory=lambda: ["prank", "mod showcase", "clickbait"])
    max_age_hours: float = 48.0
    min_virality_score: float = 3.5
    weight_views: float = 0.7
    weight_engagement: float = 0.3

    @property
    def scoring_weights(self) -> ScoringWeights:
        return ScoringWeights(w1=self.weight_views, w2=self.weight_engagement)


class ArchiverSettings(BaseModel):
    """Configuration for media downloader and filesystem storage."""
    output_dir: str = "./archive"
    max_resolution: int = 1080
    max_duration_seconds: int = 300
    concurrent_downloads: int = 2
    rate_limit_sleep_seconds: float = 2.0


class DatabaseSettings(BaseModel):
    """Configuration for SQLite storage."""
    db_path: str = "./viceclip.db"


class FacebookSettings(BaseModel):
    """Configuration for Facebook discovery and page tracking."""
    page_ids: List[str] = Field(default_factory=lambda: ["GTA6News", "RockstarGames"])
    access_token: Optional[str] = None


class AppConfig(BaseSettings):
    """Application-wide settings aggregating TOML config and environment variables."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Credentials from Environment
    youtube_api_key: Optional[str] = Field(default=None, alias="YOUTUBE_API_KEY")
    reddit_client_id: Optional[str] = Field(default=None, alias="REDDIT_CLIENT_ID")
    reddit_client_secret: Optional[str] = Field(default=None, alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="ViceClipArchiver/0.1.0", alias="REDDIT_USER_AGENT")
    facebook_access_token: Optional[str] = Field(default=None, alias="FACEBOOK_ACCESS_TOKEN")

    # DB override from Environment
    viceclip_db_path: Optional[str] = Field(default=None, alias="VICECLIP_DB_PATH")

    # Nested Section Settings
    discovery: DiscoverySettings = Field(default_factory=DiscoverySettings)
    archiver: ArchiverSettings = Field(default_factory=ArchiverSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    facebook: FacebookSettings = Field(default_factory=FacebookSettings)

    @classmethod
    def load(cls, config_path: str | Path = "config.toml") -> "AppConfig":
        """Load settings from config.toml (if present) merged with environment variables."""
        cfg_file = Path(config_path)
        toml_data: dict[str, Any] = {}
        if cfg_file.is_file():
            with open(cfg_file, "rb") as f:
                toml_data = tomllib.load(f)

        # Environment variable override for db_path
        env_db = os.environ.get("VICECLIP_DB_PATH")
        if env_db:
            if "database" not in toml_data:
                toml_data["database"] = {}
            toml_data["database"]["db_path"] = env_db

        return cls(**toml_data)
