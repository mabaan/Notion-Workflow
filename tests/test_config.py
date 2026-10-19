from pathlib import Path

import research_automation.config as config_module
import pytest

from research_automation.config import Settings, load_settings


def test_load_settings_accepts_unsplash_access_key_variant(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.setenv("Unsplash_Access_Key", "access-key")
    monkeypatch.setenv("LOCAL_STATE_PATH", str(tmp_path))

    settings = load_settings()

    assert settings.unsplash_access_key == "access-key"


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


def test_luna_defaults_keep_legacy_selection_opt_out() -> None:
    settings = Settings()
    assert settings.llm_model == "gpt-6-luna"
    assert settings.article_selection_mode == "deterministic"
    assert settings.article_enrichment_budget == 32
    assert settings.enrichment_initial_budget == 32
    assert settings.article_enrichment_max_budget == 48
    assert settings.article_enrichment_backfill_batch == 8
    assert settings.classification_model == "gpt-6-luna"
    assert settings.classification_timeout_seconds == 120
    assert settings.classification_batch_size == 100
    assert settings.classification_max_attempts == 2


@pytest.mark.parametrize("overrides,match", [
    ({"article_selection_mode": "unknown"}, "ARTICLE_SELECTION_MODE"),
    ({"article_enrichment_budget": 0}, "ARTICLE_ENRICHMENT_BUDGET"),
    ({"article_selection_mode": "luna", "classification_model": "gpt-4.1-mini"}, "requires CLASSIFICATION_MODEL"),
    ({"article_selection_mode": "luna", "llm_model": "another-model"}, "requires CLASSIFICATION_MODEL"),
    ({"article_selection_mode": "luna", "minimum_article_relevance_score": 3}, "RELEVANCE_SCORE >= 4"),
])
def test_selection_configuration_rejects_unsafe_luna_settings(overrides, match):
    with pytest.raises(ValueError, match=match):
        Settings(**overrides).validate()


def test_selection_configuration_loads_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.setenv("ARTICLE_SELECTION_MODE", "LUNA")
    monkeypatch.setenv("ARTICLE_ENRICHMENT_BUDGET", "40")
    monkeypatch.setenv("CLASSIFICATION_MODEL", "gpt-6-luna")
    monkeypatch.setenv("LLM_MODEL", "gpt-6-luna")
    settings = load_settings()
    assert settings.article_selection_mode == "luna"
    assert settings.article_enrichment_budget == 40


def test_luna_shared_pool_has_no_legacy_regional_enrichment_ceiling():
    Settings(article_selection_mode="luna", article_queue_weekly_target_uae=10).validate()
    with pytest.raises(ValueError, match="discovery collection limit"):
        Settings(article_selection_mode="luna", article_shortlist_max_per_region=0).validate()


def test_luna_classifier_allows_explicit_sol_enrichment():
    settings = Settings(article_selection_mode="luna", classification_model="gpt-6-luna", llm_model="gpt-6-sol")
    settings.validate()
    assert settings.classification_model == "gpt-6-luna"
    assert settings.llm_model == "gpt-6-sol"
    assert settings.classification_batch_size == 100
    assert (settings.enrichment_initial_budget, settings.article_enrichment_max_budget,
            settings.article_enrichment_backfill_batch) == (32, 48, 8)
    assert settings.minimum_article_relevance_score == 4


@pytest.mark.parametrize("raw,expected", [(None, False), ("false", False), ("true", True), ("TRUE", True)])
def test_direct_site_flag_is_explicitly_default_off(monkeypatch, raw, expected):
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv("DIRECT_SITE_DISCOVERY_ENABLED", raising=False)
    if raw is not None:
        monkeypatch.setenv("DIRECT_SITE_DISCOVERY_ENABLED", raw)
    assert load_settings().direct_site_discovery_enabled is expected
    assert Settings().direct_site_discovery_enabled is False


def test_direct_site_flag_rejects_invalid_boolean(monkeypatch):
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.setenv("DIRECT_SITE_DISCOVERY_ENABLED", "maybe")
    with pytest.raises(ValueError, match="DIRECT_SITE_DISCOVERY_ENABLED must be true or false"):
        load_settings()


@pytest.mark.parametrize("overrides", [
    {"article_enrichment_initial_budget": 0},
    {"article_enrichment_initial_budget": 40, "article_enrichment_max_budget": 32},
    {"article_enrichment_max_budget": 49},
    {"article_enrichment_backfill_batch": 0},
])
def test_adaptive_enrichment_configuration_rejects_unsafe_budgets(overrides):
    with pytest.raises(ValueError, match="BUDGET|BACKFILL_BATCH"):
        Settings(article_selection_mode="luna", **overrides).validate()


def test_new_initial_budget_precedes_legacy_alias(monkeypatch):
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.setenv("ARTICLE_SELECTION_MODE", "luna")
    monkeypatch.setenv("CLASSIFICATION_MODEL", "gpt-6-luna")
    monkeypatch.setenv("LLM_MODEL", "gpt-6-luna")
    monkeypatch.setenv("ARTICLE_ENRICHMENT_BUDGET", "16")
    monkeypatch.setenv("ARTICLE_ENRICHMENT_INITIAL_BUDGET", "32")
    monkeypatch.setenv("ARTICLE_ENRICHMENT_MAX_BUDGET", "40")
    monkeypatch.setenv("ARTICLE_ENRICHMENT_BACKFILL_BATCH", "4")
    settings = load_settings()
    assert settings.enrichment_initial_budget == 32
    assert settings.article_enrichment_max_budget == 40
    assert settings.article_enrichment_backfill_batch == 4


def test_independent_classifier_configuration_loads_from_environment(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    values = {
        "CLASSIFICATION_MODEL": "gpt-4.1-nano",
        "CLASSIFICATION_BATCH_SIZE": "25", "CLASSIFICATION_MAX_REQUEST_BYTES": "50000",
        "CLASSIFICATION_MAX_OUTPUT_TOKENS": "8000", "CLASSIFICATION_MAX_ATTEMPTS": "3",
        "CLASSIFICATION_TIMEOUT_SECONDS": "30",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    settings = load_settings()
    assert settings.classification_model == "gpt-4.1-nano"
    assert settings.classification_batch_size == 25
    assert settings.classification_max_request_bytes == 50_000
    assert settings.classification_max_output_tokens == 8_000
    assert settings.classification_max_attempts == 3
    assert settings.classification_timeout_seconds == 30
