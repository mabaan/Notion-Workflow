from pathlib import Path

import research_automation.config as config_module
import pytest

from research_automation.config import Settings, load_settings


def test_load_settings_accepts_unsplash_key_variants(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.setenv("Unsplash_Access_Key", "access-key")
    monkeypatch.setenv("Unsplash_Secret_Key", "secret-key")
    monkeypatch.setenv("LOCAL_STATE_PATH", str(tmp_path))

    settings = load_settings()

    assert settings.unsplash_access_key == "access-key"
    assert settings.unsplash_secret_key == "secret-key"


def test_load_settings_defaults_to_unsplash_then_brave(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv("IMAGE_DISCOVERY_PROVIDERS", raising=False)
    monkeypatch.setenv("LOCAL_STATE_PATH", str(tmp_path))

    settings = load_settings()

    assert settings.image_discovery_providers == ("unsplash", "brave")


def test_load_settings_defaults_minimum_article_relevance_score(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv("MIN_ARTICLE_RELEVANCE_SCORE", raising=False)
    monkeypatch.setenv("LOCAL_STATE_PATH", str(tmp_path))

    settings = load_settings()

    assert settings.minimum_article_relevance_score == 4


def test_load_settings_defaults_weekly_publisher_cap(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv("MAX_ARTICLES_PER_PUBLISHER_PER_WEEK", raising=False)
    monkeypatch.delenv("MAX_ARTICLES_PER_SOURCE_PER_RUN", raising=False)
    monkeypatch.setenv("LOCAL_STATE_PATH", str(tmp_path))

    settings = load_settings()

    assert settings.max_articles_per_publisher_per_week == 2


def test_default_targets_total_twelve() -> None:
    settings = Settings()
    assert settings.weekly_region_targets == {
        "Global": 3,
        "UAE": 4,
        "KSA": 3,
        "Egypt": 2,
    }
    assert sum(settings.weekly_region_targets.values()) == 12
    assert settings.max_articles_per_run == 12


def test_legacy_source_cap_is_a_deprecated_fallback(monkeypatch, caplog) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv("MAX_ARTICLES_PER_PUBLISHER_PER_WEEK", raising=False)
    monkeypatch.setenv("MAX_ARTICLES_PER_SOURCE_PER_RUN", "3")
    settings = load_settings()
    assert settings.max_articles_per_publisher_per_week == 3
    assert "deprecated" in caplog.text


def test_configuration_validation_rejects_inconsistent_shortlist() -> None:
    settings = Settings(article_shortlist_initial_per_region=3)
    with pytest.raises(ValueError, match="largest regional target"):
        settings.validate()
