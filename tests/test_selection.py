from datetime import UTC, datetime

from research_automation.config import Settings
from research_automation.models.article import Article, EnrichedArticle
from research_automation.models.candidate import CandidateResult
from research_automation.pipeline.candidate_ranking import calculate_queue_score
from research_automation.pipeline.selection import (
    load_weekly_queue_state,
    select_final_candidates,
)


class FakeNotion:
    def __init__(self, pages):
        self.pages = pages

    def query_database(self, database_id, filter_payload=None):
        return self.pages


def _page(title, region, url, relation_id=None):
    return {
        "properties": {
            "TItle": {"title": [{"plain_text": title}]},
            "Region": {"multi_select": [{"name": region}]},
            "Canonical URL": {"url": url},
            "URL": {"url": url},
            "Source": {
                "relation": [{"id": relation_id}] if relation_id else []
            },
        }
    }


def test_weekly_state_counts_registered_and_unknown_publishers() -> None:
    state = load_weekly_queue_state(
        FakeNotion(
            [
                _page(
                    "UAE solar project advances",
                    "UAE",
                    "https://registered.example/a",
                    "publisher-1",
                ),
                _page(
                    "Egypt water project advances",
                    "Egypt",
                    "https://unknown.example/b",
                ),
            ]
        ),
        Settings(notion_article_queue_database_id="article-db"),
        "dataset-1",
    )
    assert state.region_counts["UAE"] == 1
    assert state.region_counts["Egypt"] == 1
    assert state.publisher_counts == {"publisher-1": 1, "unknown.example": 1}
    assert state.existing_urls == {
        "https://registered.example/a",
        "https://unknown.example/b",
    }


def test_existing_weekly_event_blocks_another_outlets_version() -> None:
    article = Article(
        title="UAE awards major solar project to clean energy consortium - Outlet B",
        url="https://outlet-b.example/story",
        canonical_url="https://outlet-b.example/story",
        source_name="Outlet B",
        source_page_id="publisher-b",
        published_date=datetime(2026, 9, 1, tzinfo=UTC),
        publisher_key="publisher-b",
    )
    enriched = EnrichedArticle("summary", "why", 5)
    candidate = CandidateResult(
        article=article,
        enrichment=enriched,
        target_region="UAE",
        queue_score=calculate_queue_score(5, 8),
        source_quality=8,
    )
    from research_automation.pipeline.selection import WeeklyQueueState

    state = WeeklyQueueState(
        existing_titles=["UAE awards major solar project to clean energy consortium"]
    )
    result = select_final_candidates(
        [candidate],
        weekly_state=state,
        targets={"Global": 0, "UAE": 1, "KSA": 0, "Egypt": 0},
        run_limit=1,
        publisher_cap=2,
    )
    assert result.winners == []
    assert result.rejected_by_constraint["existing event"] == 1
