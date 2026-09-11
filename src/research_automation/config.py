"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
import logging
from pathlib import Path

from dotenv import load_dotenv

from research_automation.notion_schema import DATABASE_ID_FIELDS

logger = logging.getLogger(__name__)


def _env_first(*names: str, default: str = "") -> str:
    """Return the first non-empty environment variable value from a list."""

    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def _env_csv(name: str, default: str) -> tuple[str, ...]:
    """Read a comma-delimited environment variable into a tuple."""

    raw_value = os.getenv(name, default)
    return tuple(item.strip() for item in raw_value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    """Runtime settings for local scripts."""

    notion_token: str = ""
    notion_source_registry_database_id: str = ""
    notion_article_queue_database_id: str = ""
    notion_dataset_meetings_database_id: str = ""
    notion_newsletters_database_id: str = ""
    notion_social_media_database_id: str = ""
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    openai_api_key: str = ""
    unsplash_access_key: str = ""
    brave_search_api_key: str = ""
    news_api_key: str = ""
    local_state_path: Path = Path(".local_state")
    log_level: str = "INFO"
    max_articles_per_run: int = 12
    minimum_article_relevance_score: int = 4
    max_articles_per_publisher_per_week: int = 2
    article_freshness_days: int = 7
    article_shortlist_initial_per_region: int = 6
    article_shortlist_max_per_region: int = 8
    news_discovery_providers: tuple[str, ...] = ("brave", "newsapi")
    image_discovery_providers: tuple[str, ...] = ("unsplash", "brave")
    article_queue_weekly_target_global: int = 3
    article_queue_weekly_target_uae: int = 4
    article_queue_weekly_target_ksa: int = 3
    article_queue_weekly_target_egypt: int = 2
    discovery_global_countries: tuple[str, ...] = ("ALL",)
    discovery_uae_countries: tuple[str, ...] = ("AE",)
    discovery_ksa_countries: tuple[str, ...] = ("SA",)
    discovery_egypt_countries: tuple[str, ...] = ("EG",)
    discovery_global_languages: tuple[str, ...] = ("en",)
    discovery_uae_languages: tuple[str, ...] = ("en", "ar")
    discovery_ksa_languages: tuple[str, ...] = ("en", "ar")
    discovery_egypt_languages: tuple[str, ...] = ("en", "ar")
    discovery_topics: tuple[str, ...] = (
        "food security",
        "water security",
        "net zero transition",
        "energy transition",
        "trade",
        "resilience",
        "regulation",
        "supply chains",
        "desalination",
        "agri-food",
    )
    brave_max_requests_per_run: int = 20
    newsapi_max_requests_per_run: int = 20

    @property
    def prompt_directory(self) -> Path:
        """Return the package prompt directory."""

        return Path(__file__).resolve().parent / "prompts"

    @property
    def seen_articles_path(self) -> Path:
        """Return the local dedupe store path."""

        return self.local_state_path / "seen_articles.json"

    @property
    def article_assets_path(self) -> Path:
        """Return the local image asset cache path."""

        return self.local_state_path / "article_assets.json"

    def database_id(self, alias: str) -> str:
        """Resolve a friendly database alias to its configured ID."""

        attr_name = DATABASE_ID_FIELDS[alias]
        return getattr(self, attr_name)

    @property
    def weekly_region_targets(self) -> dict[str, int]:
        """Return exact weekly quota targets by region label."""

        return {
            "Global": self.article_queue_weekly_target_global,
            "UAE": self.article_queue_weekly_target_uae,
            "KSA": self.article_queue_weekly_target_ksa,
            "Egypt": self.article_queue_weekly_target_egypt,
        }

    def discovery_countries(self, region: str) -> tuple[str, ...]:
        """Return configured discovery countries for a target region."""

        mapping = {
            "Global": self.discovery_global_countries,
            "UAE": self.discovery_uae_countries,
            "KSA": self.discovery_ksa_countries,
            "Egypt": self.discovery_egypt_countries,
        }
        return mapping.get(region, ("ALL",))

    def discovery_languages(self, region: str) -> tuple[str, ...]:
        """Return configured discovery languages for a target region."""

        mapping = {
            "Global": self.discovery_global_languages,
            "UAE": self.discovery_uae_languages,
            "KSA": self.discovery_ksa_languages,
            "Egypt": self.discovery_egypt_languages,
        }
        return mapping.get(region, ("en",))

    def validate(self) -> None:
        """Reject unsafe or internally inconsistent ingestion settings."""

        errors: list[str] = []
        if self.max_articles_per_run <= 0:
            errors.append("MAX_ARTICLES_PER_RUN must be greater than zero")
        if any(target <= 0 for target in self.weekly_region_targets.values()):
            errors.append("all ARTICLE_QUEUE_WEEKLY_TARGET_* values must be positive")
        if self.max_articles_per_publisher_per_week <= 0:
            errors.append("MAX_ARTICLES_PER_PUBLISHER_PER_WEEK must be greater than zero")
        if self.article_freshness_days <= 0:
            errors.append("ARTICLE_FRESHNESS_DAYS must be greater than zero")
        largest_target = max(self.weekly_region_targets.values())
        if self.article_shortlist_initial_per_region < largest_target:
            errors.append(
                "ARTICLE_SHORTLIST_INITIAL_PER_REGION must be at least the largest regional target"
            )
        if (
            self.article_shortlist_max_per_region
            < self.article_shortlist_initial_per_region
        ):
            errors.append(
                "ARTICLE_SHORTLIST_MAX_PER_REGION must be at least ARTICLE_SHORTLIST_INITIAL_PER_REGION"
            )
        if errors:
            raise ValueError("Invalid configuration:\n- " + "\n- ".join(errors))


def _env_int(name: str, default: int) -> int:
    """Read an integer from the environment with a fallback."""

    raw_value = os.getenv(name, str(default)).strip()
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer; received {raw_value!r}") from exc


def _publisher_cap() -> int:
    current = os.getenv("MAX_ARTICLES_PER_PUBLISHER_PER_WEEK", "").strip()
    if current:
        return _env_int("MAX_ARTICLES_PER_PUBLISHER_PER_WEEK", 2)
    legacy = os.getenv("MAX_ARTICLES_PER_SOURCE_PER_RUN", "").strip()
    if legacy:
        logger.warning(
            "MAX_ARTICLES_PER_SOURCE_PER_RUN is deprecated; use "
            "MAX_ARTICLES_PER_PUBLISHER_PER_WEEK."
        )
        return _env_int("MAX_ARTICLES_PER_SOURCE_PER_RUN", 2)
    return 2


def load_settings() -> Settings:
    """Load settings from .env and process environment."""

    load_dotenv()

    settings = Settings(
        notion_token=os.getenv("NOTION_TOKEN", ""),
        notion_source_registry_database_id=os.getenv(
            "NOTION_SOURCE_REGISTRY_DATABASE_ID", ""
        ),
        notion_article_queue_database_id=os.getenv(
            "NOTION_ARTICLE_QUEUE_DATABASE_ID", ""
        ),
        notion_dataset_meetings_database_id=os.getenv(
            "NOTION_DATASET_MEETINGS_DATABASE_ID", ""
        ),
        notion_newsletters_database_id=os.getenv(
            "NOTION_NEWSLETTERS_DATABASE_ID", ""
        ),
        notion_social_media_database_id=os.getenv(
            "NOTION_SOCIAL_MEDIA_DATABASE_ID", ""
        ),
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4.1-mini"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        unsplash_access_key=_env_first(
            "UNSPLASH_ACCESS_KEY",
            "Unsplash_Access_Key",
        ),
        brave_search_api_key=os.getenv("BRAVE_SEARCH_API_KEY", ""),
        news_api_key=os.getenv("NEWS_API_KEY", ""),
        local_state_path=Path(os.getenv("LOCAL_STATE_PATH", ".local_state")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        max_articles_per_run=_env_int("MAX_ARTICLES_PER_RUN", 12),
        minimum_article_relevance_score=_env_int(
            "MIN_ARTICLE_RELEVANCE_SCORE",
            4,
        ),
        max_articles_per_publisher_per_week=_publisher_cap(),
        article_freshness_days=_env_int("ARTICLE_FRESHNESS_DAYS", 7),
        article_shortlist_initial_per_region=_env_int(
            "ARTICLE_SHORTLIST_INITIAL_PER_REGION", 6
        ),
        article_shortlist_max_per_region=_env_int(
            "ARTICLE_SHORTLIST_MAX_PER_REGION", 8
        ),
        news_discovery_providers=_env_csv(
            "NEWS_DISCOVERY_PROVIDERS",
            "brave,newsapi",
        ),
        image_discovery_providers=_env_csv(
            "IMAGE_DISCOVERY_PROVIDERS",
            "unsplash,brave",
        ),
        article_queue_weekly_target_global=_env_int(
            "ARTICLE_QUEUE_WEEKLY_TARGET_GLOBAL",
            3,
        ),
        article_queue_weekly_target_uae=_env_int(
            "ARTICLE_QUEUE_WEEKLY_TARGET_UAE",
            4,
        ),
        article_queue_weekly_target_ksa=_env_int(
            "ARTICLE_QUEUE_WEEKLY_TARGET_KSA",
            3,
        ),
        article_queue_weekly_target_egypt=_env_int(
            "ARTICLE_QUEUE_WEEKLY_TARGET_EGYPT",
            2,
        ),
        discovery_global_countries=_env_csv(
            "DISCOVERY_GLOBAL_COUNTRIES",
            "ALL",
        ),
        discovery_uae_countries=_env_csv(
            "DISCOVERY_UAE_COUNTRIES",
            "AE",
        ),
        discovery_ksa_countries=_env_csv(
            "DISCOVERY_KSA_COUNTRIES",
            "SA",
        ),
        discovery_egypt_countries=_env_csv(
            "DISCOVERY_EGYPT_COUNTRIES",
            "EG",
        ),
        discovery_global_languages=_env_csv(
            "DISCOVERY_GLOBAL_LANGUAGES",
            "en",
        ),
        discovery_uae_languages=_env_csv(
            "DISCOVERY_UAE_LANGUAGES",
            "en,ar",
        ),
        discovery_ksa_languages=_env_csv(
            "DISCOVERY_KSA_LANGUAGES",
            "en,ar",
        ),
        discovery_egypt_languages=_env_csv(
            "DISCOVERY_EGYPT_LANGUAGES",
            "en,ar",
        ),
        discovery_topics=_env_csv(
            "DISCOVERY_TOPICS",
            (
                "food security,water security,net zero transition,energy transition,"
                "trade,resilience,regulation,supply chains,desalination,agri-food"
            ),
        ),
        brave_max_requests_per_run=_env_int("BRAVE_MAX_REQUESTS_PER_RUN", 20),
        newsapi_max_requests_per_run=_env_int("NEWSAPI_MAX_REQUESTS_PER_RUN", 20),
    )
    settings.validate()
    return settings
