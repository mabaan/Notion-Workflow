from datetime import UTC, datetime, timedelta

from research_automation.config import Settings
from research_automation.models.article import Article, EnrichedArticle
from research_automation.models.candidate import CandidateResult
from research_automation.pipeline.candidate_ranking import (
    calculate_queue_score,
    evaluate_candidate_pool,
)
from research_automation.pipeline.selection import (
    WeeklyQueueState,
    probable_same_event,
    select_final_candidates,
)


NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)
TARGETS = {"Global": 3, "UAE": 4, "KSA": 3, "Egypt": 3}


def _article(
    key: str,
    region: str,
    *,
    publisher: str = "publisher-1",
    quality: float | None = 5,
    title: str | None = None,
) -> Article:
    geography = {
        "Global": "global",
        "UAE": "UAE",
        "KSA": "Saudi Arabia",
        "Egypt": "Egypt",
    }[region]
    return Article(
        title=title or f"{geography} energy transition project{key} advances",
        url=f"https://{publisher}.example/{key}",
        canonical_url=f"https://{publisher}.example/{key}",
        source_name=publisher,
        source_page_id=publisher if publisher.startswith("publisher") else "",
        published_date=NOW - timedelta(hours=1),
        snippet=f"{geography} renewable energy and grid policy update",
        region=[region],
        source_editorial_quality=quality,
        publisher_key=publisher,
    )


def _enriched(score: int) -> EnrichedArticle:
    return EnrichedArticle(
        summary="summary",
        why_it_matters="why",
        relevance_score=score,
        topic=["energy transition"],
        region=[],
    )


def _candidate(
    key: str,
    region: str,
    score: int = 5,
    *,
    publisher: str = "publisher-1",
    quality: float | None = 5,
    title: str | None = None,
) -> CandidateResult:
    article = _article(key, region, publisher=publisher, quality=quality, title=title)
    return CandidateResult(
        article=article,
        enrichment=_enriched(score),
        target_region=region,
        queue_score=calculate_queue_score(score, quality),
        source_quality=quality,
    )


def test_transitional_score_uses_exact_90_10_weighting() -> None:
    assert calculate_queue_score(5, 10) == 100
    assert calculate_queue_score(5, None) == 90
    assert calculate_queue_score(4, 10) == 82


def test_relevance_five_from_weaker_source_beats_relevance_four_from_ten() -> None:
    assert calculate_queue_score(5, 1) > calculate_queue_score(4, 10)


def test_equal_relevance_favors_higher_rated_publisher() -> None:
    settings = Settings()
    articles = [
        _article("low", "Global", publisher="publisher-low", quality=2),
        _article("high", "Global", publisher="publisher-high", quality=9),
    ]
    scores = {"low": 4, "high": 4}
    evaluation = evaluate_candidate_pool(
        list(reversed(articles)),
        deficits={"Global": 1, "UAE": 0, "KSA": 0, "Egypt": 0},
        settings=settings,
        enrich=lambda article: _enriched(scores[article.canonical_url.rsplit("/", 1)[-1]]),
        now=NOW,
    )
    eligible = sorted(
        (item for item in evaluation.results if item.eligible),
        key=lambda item: -item.queue_score,
    )
    assert eligible[0].article.publisher_key == "publisher-high"


def test_pool_ranking_is_independent_of_feed_order() -> None:
    settings = Settings()
    articles = [
        _article("a", "UAE", publisher="publisher-a", quality=2),
        _article("b", "UAE", publisher="publisher-b", quality=8),
    ]

    def rank(pool):
        evaluation = evaluate_candidate_pool(
            pool,
            deficits={"Global": 0, "UAE": 1, "KSA": 0, "Egypt": 0},
            settings=settings,
            enrich=lambda _: _enriched(5),
            now=NOW,
        )
        selected = select_final_candidates(
            [item for item in evaluation.results if item.eligible],
            weekly_state=WeeklyQueueState(),
            targets={"Global": 0, "UAE": 1, "KSA": 0, "Egypt": 0},
            run_limit=1,
            publisher_cap=2,
        )
        return selected.winners[0].article.publisher_key

    assert rank(articles) == rank(list(reversed(articles))) == "publisher-b"


def test_first_run_caps_at_twelve_and_second_fills_only_remaining_deficit() -> None:
    candidates = []
    index = 0
    for region, count in TARGETS.items():
        for _ in range(count):
            index += 1
            candidates.append(
                _candidate(
                    str(index),
                    region,
                    publisher=f"publisher-{(index + 1) // 2}",
                )
            )
    first = select_final_candidates(
        candidates,
        weekly_state=WeeklyQueueState(),
        targets=TARGETS,
        run_limit=12,
        publisher_cap=2,
    )
    assert len(first.winners) == 12
    assert sum(first.shortages.values()) == 1

    second = select_final_candidates(
        candidates,
        weekly_state=first.final_state,
        targets=TARGETS,
        run_limit=12,
        publisher_cap=2,
    )
    assert len(second.winners) == 1
    assert sum(second.shortages.values()) == 0


def test_publisher_weekly_cap_is_hard_and_has_no_override() -> None:
    state = WeeklyQueueState(publisher_counts={"publisher-1": 2})
    result = select_final_candidates(
        [_candidate("one", "Global", publisher="publisher-1")],
        weekly_state=state,
        targets={"Global": 1, "UAE": 0, "KSA": 0, "Egypt": 0},
        run_limit=12,
        publisher_cap=2,
    )
    assert result.winners == []
    assert result.shortages["Global"] == 1
    assert result.rejected_by_constraint["publisher weekly cap"] == 1


def test_complete_quotas_receive_no_generic_backfill() -> None:
    state = WeeklyQueueState(region_counts=dict(TARGETS))
    result = select_final_candidates(
        [_candidate("extra", "Global", publisher="publisher-9")],
        weekly_state=state,
        targets=TARGETS,
        run_limit=12,
        publisher_cap=2,
    )
    assert result.winners == []


def test_same_event_candidates_yield_one_representative() -> None:
    candidates = [
        _candidate(
            "one",
            "UAE",
            publisher="publisher-a",
            quality=9,
            title="UAE awards major solar project to clean energy consortium",
        ),
        _candidate(
            "two",
            "UAE",
            publisher="publisher-b",
            quality=5,
            title="UAE awards major solar project to clean energy consortium - Outlet",
        ),
    ]
    result = select_final_candidates(
        candidates,
        weekly_state=WeeklyQueueState(),
        targets={"Global": 0, "UAE": 2, "KSA": 0, "Egypt": 0},
        run_limit=12,
        publisher_cap=2,
    )
    assert len(result.winners) == 1
    assert result.winners[0].article.publisher_key == "publisher-a"
    assert probable_same_event(candidates[0].article.title, candidates[1].article.title)


def test_region_with_scarcer_qualified_pool_is_selected_first() -> None:
    candidates = [
        _candidate("uae", "UAE", publisher="publisher-u"),
        _candidate("alpha", "Global", publisher="publisher-g1"),
        _candidate("beta", "Global", publisher="publisher-g2"),
    ]
    result = select_final_candidates(
        candidates,
        weekly_state=WeeklyQueueState(),
        targets={"Global": 1, "UAE": 1, "KSA": 0, "Egypt": 0},
        run_limit=1,
        publisher_cap=2,
    )
    assert result.winners[0].target_region == "UAE"


def test_unknown_publisher_requires_five_while_registered_publisher_uses_default_gate() -> None:
    settings = Settings()
    unknown = _article("unknown", "Global", publisher="unknown", quality=None)
    registered = _article("registered", "Global", publisher="publisher-known", quality=None)
    evaluation = evaluate_candidate_pool(
        [unknown, registered],
        deficits={"Global": 2, "UAE": 0, "KSA": 0, "Egypt": 0},
        settings=settings,
        enrich=lambda _: _enriched(4),
        now=NOW,
    )
    assert [item.article.publisher_key for item in evaluation.results if item.eligible] == [
        "publisher-known"
    ]
    assert evaluation.rejection_counts["relevance below 5"] == 1


def test_unknown_and_stale_publication_dates_are_explicitly_rejected() -> None:
    settings = Settings(article_freshness_days=7)
    unknown = _article("unknown-date", "Global", publisher="publisher-u")
    unknown.published_date = None
    stale = _article("stale", "Global", publisher="publisher-s")
    stale.published_date = NOW - timedelta(days=8)
    evaluation = evaluate_candidate_pool(
        [unknown, stale],
        deficits={"Global": 2, "UAE": 0, "KSA": 0, "Egypt": 0},
        settings=settings,
        enrich=lambda _: _enriched(5),
        now=NOW,
    )
    assert evaluation.rejection_counts == {
        "outside freshness window": 1,
        "unknown publication date": 1,
    }


def test_llm_scoring_is_bounded_at_eight_per_region() -> None:
    settings = Settings(
        article_shortlist_initial_per_region=6,
        article_shortlist_max_per_region=8,
    )
    articles = [
        _article(f"candidate{index}", "Global", publisher=f"publisher-{index}")
        for index in range(10)
    ]
    calls = []

    def enrich(article):
        calls.append(article.title)
        return _enriched(1)

    evaluation = evaluate_candidate_pool(
        articles,
        deficits={"Global": 3, "UAE": 0, "KSA": 0, "Egypt": 0},
        settings=settings,
        enrich=enrich,
        now=NOW,
    )
    assert len(calls) == 8
    assert evaluation.rejection_counts["shortlist ceiling"] == 2


def test_failed_enrichment_attempts_still_consume_the_eight_candidate_budget() -> None:
    settings = Settings(
        article_shortlist_initial_per_region=6,
        article_shortlist_max_per_region=8,
    )
    calls = []

    def fail(article):
        calls.append(article.title)
        raise RuntimeError("provider timeout")

    first = evaluate_candidate_pool(
        [
            _article(f"first{index}", "Global", publisher=f"publisher-a{index}")
            for index in range(6)
        ],
        deficits={"Global": 3, "UAE": 0, "KSA": 0, "Egypt": 0},
        settings=settings,
        enrich=fail,
        now=NOW,
    )
    second = evaluate_candidate_pool(
        [
            _article(f"second{index}", "Global", publisher=f"publisher-b{index}")
            for index in range(6)
        ],
        deficits={"Global": 3, "UAE": 0, "KSA": 0, "Egypt": 0},
        settings=settings,
        enrich=fail,
        now=NOW,
        already_shortlisted=first.shortlisted_counts,
    )
    assert len(calls) == 8
    assert second.shortlisted_counts["Global"] == 2
