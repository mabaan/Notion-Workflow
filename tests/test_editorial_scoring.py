from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from research_automation.clients.llm_client import LlmClient
from research_automation.config import Settings
from research_automation.models.article import Article, EnrichedArticle
from research_automation.models.candidate import CandidateResult
from research_automation.pipeline.candidate_ranking import (
    calculate_queue_score,
    evaluate_candidate_pool,
)
from research_automation.pipeline.selection import (
    WeeklyQueueState,
    select_final_candidates,
)


NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)
PROMPTS_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "research_automation" / "prompts"
)


def _article(
    key: str,
    title: str,
    snippet: str,
    region: str,
    *,
    quality: float = 8,
) -> Article:
    return Article(
        title=title,
        url=f"https://publisher-{key}.example/{key}",
        canonical_url=f"https://publisher-{key}.example/{key}",
        source_name=f"Publisher {key}",
        source_page_id=f"publisher-{key}",
        published_date=NOW,
        snippet=snippet,
        region=[region],
        source_editorial_quality=quality,
        publisher_key=f"publisher-{key}",
    )


def _enriched(
    relevance: int,
    significance: int,
    reason: str = "The development has supported measurable consequences.",
) -> EnrichedArticle:
    return EnrichedArticle(
        summary="Summary",
        why_it_matters="Why it matters",
        relevance_score=relevance,
        editorial_significance=significance,
        significance_reason=reason,
    )


def _candidate(
    article: Article,
    *,
    relevance: int,
    significance: int,
) -> CandidateResult:
    enrichment = _enriched(relevance, significance)
    return CandidateResult(
        article=article,
        enrichment=enrichment,
        target_region=article.region[0],
        queue_score=calculate_queue_score(
            relevance,
            article.source_editorial_quality,
            editorial_significance=significance,
        ),
        source_quality=article.source_editorial_quality,
    )


def test_mission_relevance_remains_the_eligibility_gate() -> None:
    water = _article(
        "water",
        "Sharjah expands strategic water infrastructure",
        "New treatment and storage capacity will strengthen water security in Sharjah.",
        "UAE",
    )
    opec = _article(
        "opec",
        "OPEC agrees major conventional oil output increase",
        "The group announced a large increase in crude oil production.",
        "Global",
        quality=10,
    )
    enrichments = {
        water.title: _enriched(4, 3),
        opec.title: _enriched(
            2,
            5,
            "The output decision could materially affect global oil markets.",
        ),
    }

    evaluation = evaluate_candidate_pool(
        [opec, water],
        deficits={"Global": 1, "UAE": 1, "KSA": 0, "Egypt": 0},
        settings=Settings(),
        enrich=lambda article: enrichments[article.title],
        now=NOW,
    )

    eligible = [result for result in evaluation.results if result.eligible]
    assert [result.article.title for result in eligible] == [water.title]
    assert evaluation.rejection_counts["relevance below 4"] == 1


def test_equal_relevance_is_ranked_by_editorial_significance() -> None:
    battery = _candidate(
        _article(
            "battery",
            "Egypt announces 500 MWh battery assembly facility",
            "The proposed factory would add 500 MWh of annual assembly capacity.",
            "Egypt",
        ),
        relevance=5,
        significance=4,
    )
    pilot = _candidate(
        _article(
            "pilot",
            "Egypt launches small battery training pilot",
            "A limited pilot will train a small technical cohort.",
            "Egypt",
        ),
        relevance=5,
        significance=2,
    )

    result = select_final_candidates(
        [pilot, battery],
        weekly_state=WeeklyQueueState(),
        targets={"Global": 0, "UAE": 0, "KSA": 0, "Egypt": 1},
        run_limit=1,
        publisher_cap=2,
    )

    assert result.winners == [battery]
    assert battery.queue_score > pilot.queue_score


def test_publisher_quality_has_less_influence_than_editorial_significance() -> None:
    solar_expansion = _candidate(
        _article(
            "solar",
            "Iraq proposes doubling solar project to 2,000 MW",
            "Negotiations would increase capacity from 1,000 MW to 2,000 MW.",
            "Global",
            quality=1,
        ),
        relevance=4,
        significance=5,
    )
    shipping_update = _candidate(
        _article(
            "shipping",
            "Oil shipping operator issues routine market update",
            "The company made a limited operational adjustment to crude shipments.",
            "Global",
            quality=10,
        ),
        relevance=4,
        significance=2,
    )

    result = select_final_candidates(
        [shipping_update, solar_expansion],
        weekly_state=WeeklyQueueState(),
        targets={"Global": 1, "UAE": 0, "KSA": 0, "Egypt": 0},
        run_limit=1,
        publisher_cap=2,
    )

    assert result.winners == [solar_expansion]
    assert solar_expansion.queue_score == 77
    assert shipping_update.queue_score == 74


def test_selection_reason_includes_all_scoring_components() -> None:
    fertilizer = _article(
        "fertilizer",
        "Hormuz disruption threatens regional fertilizer supply",
        "Supply disruption could reduce fertilizer availability and affect food security.",
        "Global",
        quality=9,
    )
    reason = "The disruption could materially constrain fertilizer supply."
    evaluation = evaluate_candidate_pool(
        [fertilizer],
        deficits={"Global": 1, "UAE": 0, "KSA": 0, "Egypt": 0},
        settings=Settings(),
        enrich=lambda _: _enriched(5, 4, reason),
        now=NOW,
    )

    selected = next(result for result in evaluation.results if result.eligible)
    assert "relevance 5/5" in selected.selection_reason
    assert "editorial significance 4/5" in selected.selection_reason
    assert "publisher quality 9/10" in selected.selection_reason
    assert f"queue score {selected.queue_score:.2f}" in selected.selection_reason
    assert reason in selected.selection_reason


def test_older_enrichment_objects_and_score_calls_remain_compatible() -> None:
    article = _article(
        "legacy",
        "Sharjah water reuse project advances",
        "The water reuse project supports water security in Sharjah.",
        "UAE",
    )
    legacy = SimpleNamespace(relevance_score=4)

    evaluation = evaluate_candidate_pool(
        [article],
        deficits={"Global": 0, "UAE": 1, "KSA": 0, "Egypt": 0},
        settings=Settings(),
        enrich=lambda _: legacy,
        now=NOW,
    )

    selected = next(result for result in evaluation.results if result.eligible)
    assert EnrichedArticle("summary", "why", 4).editorial_significance == 3
    assert calculate_queue_score(4, 8) == 76
    assert selected.queue_score == 76
    assert "editorial significance 3/5" in selected.selection_reason


def test_llm_returns_significance_from_the_existing_enrichment_call(monkeypatch) -> None:
    article = _article(
        "iraq-solar",
        "Iraq negotiates expansion of solar project",
        "The proposal would increase project capacity.",
        "Global",
    )
    article.evidence_retrieval_status = "extracted"
    article.article_text = (
        "Iraq is negotiating an increase in the project from 1,000 MW to 2,000 MW; "
        "the expansion has not yet been approved."
    )
    client = LlmClient(
        provider="openai",
        model="test-model",
        api_key="test-key",
        prompt_directory=PROMPTS_DIR,
    )
    calls = []

    def generate(prompt: str):
        calls.append(prompt)
        return {
            "summary": "Iraq is negotiating a larger solar project.",
            "story_type": "infrastructure_project", "is_new_development": True,
            "why_it_matters": "It directly concerns renewable capacity.",
            "relevance_score": 5,
            "editorial_significance": 4,
            "significance_reason": (
                "The proposal would double planned capacity to 2,000 MW."
            ),
        }

    monkeypatch.setattr(client, "_generate_json", generate)

    enriched = client.enrich_article(article)

    assert len(calls) == 1
    assert "1,000 MW to 2,000 MW" in calls[0]
    assert enriched.editorial_significance == 4
    assert enriched.significance_reason == (
        "The proposal would double planned capacity to 2,000 MW."
    )
