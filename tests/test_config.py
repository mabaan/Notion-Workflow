from pathlib import Path

import research_automation.config as config_module
from research_automation.config import load_settings


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


def test_load_settings_defaults_source_cap(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv("MAX_ARTICLES_PER_SOURCE_PER_RUN", raising=False)
    monkeypatch.setenv("LOCAL_STATE_PATH", str(tmp_path))

    settings = load_settings()

    assert settings.max_articles_per_source_per_run == 2
