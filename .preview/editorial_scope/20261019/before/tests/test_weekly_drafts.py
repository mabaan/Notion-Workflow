from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.run_weekly_drafts_local as weekly_drafts

from research_automation.config import Settings
from research_automation.models.article import EnrichedArticle
from research_automation.models.draft import DraftArticle
from research_automation.pipeline.article_retrieval import ArticleRetrievalResult


def test_weekly_generation_writes_both_drafts_despite_quality_warnings(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    newsletter_article = DraftArticle(
        title="Egypt battery proposal",
        source_name="Publisher",
        canonical_url="https://news.google.com/rss/articles/battery",
        summary="A 500 MWh battery assembly facility is proposed.",
    )
    social_article = DraftArticle(
        title="Sharjah water infrastructure",
        source_name="Publisher",
        canonical_url="",
        summary="Sharjah announced planned water infrastructure.",
    )
    settings = Settings(local_state_path=tmp_path)
    pages = SimpleNamespace(
        dataset_meeting_id="dataset-1",
        newsletter_id="newsletter-1",
        social_media_id="social-1",
        week=SimpleNamespace(start=date(2026, 10, 12), end=date(2026, 10, 18)),
    )
    replacements = []
    status_updates = []

    class FakeLlm:
        def __init__(self, **kwargs):
            pass

        def generate_newsletter_draft(self, week_start, week_end, articles):
            return "\n".join(
                [
                    "## Egypt battery proposal",
                    "The proposal has 750 MWh of annual capacity.",
                    "SOMA's Perspective:",
                    "The capacity claim requires review.",
                    "Sources:",
                ]
            )

        def generate_social_media_draft(self, week_start, week_end, articles):
            return "\n".join(
                [
                    "Topic 1: Sharjah water infrastructure",
                    "Hook: A planned project was announced.",
                    "Define the Issue: Evidence is limited.",
                    "Describe the Situation: Review the source.",
                    "So Why Does This Matter? Planning details remain uncertain.",
                    "Call-to-Action: Verify before publication.",
                    "Sources:",
                ]
            )

    class FakeImageResolver:
        def __init__(self, _settings):
            pass

        def resolve_articles(self, articles):
            return articles

    def load_articles(notion, loaded_settings, dataset_id, statuses):
        if statuses == ["Use in Newsletter"]:
            return [newsletter_article]
        return [social_article]

    monkeypatch.setattr(weekly_drafts, "load_settings", lambda: settings)
    monkeypatch.setattr(weekly_drafts, "configure_logging", lambda _: None)
    monkeypatch.setattr(weekly_drafts, "NotionClient", lambda token: object())
    monkeypatch.setattr(weekly_drafts, "ensure_current_weekly_pages", lambda *_: pages)
    monkeypatch.setattr(weekly_drafts, "load_weekly_draft_articles", load_articles)
    monkeypatch.setattr(weekly_drafts, "LlmClient", FakeLlm)
    monkeypatch.setattr(weekly_drafts, "ArticleImageResolver", FakeImageResolver)
    monkeypatch.setattr(
        weekly_drafts,
        "replace_generated_section",
        lambda notion, page_id, marker, content: replacements.append(
            (page_id, marker, content)
        ),
    )
    monkeypatch.setattr(
        weekly_drafts,
        "mark_newsletter_ready_for_review",
        lambda notion, page_id: status_updates.append(("newsletter", page_id)),
    )
    monkeypatch.setattr(
        weekly_drafts,
        "mark_social_media_ready",
        lambda notion, page_id: status_updates.append(("sns", page_id)),
    )

    weekly_drafts.main([])

    output = capsys.readouterr().out
    assert len(replacements) == 2
    assert status_updates == [
        ("newsletter", "newsletter-1"),
        ("sns", "social-1"),
    ]
    assert "Newsletter quality warnings" in output
    assert "SNS quality warnings" in output
    assert "possible mismatch" in output
    assert "no usable story image" in output
    assert "Newsletter draft updated" in output
    assert "Social media draft updated" in output


class ReadOnlyNotion:
    def create_page(self, *args, **kwargs):
        raise AssertionError("preview must not create Notion pages")

    def update_page(self, *args, **kwargs):
        raise AssertionError("preview must not update Notion pages")

    def append_block_children(self, *args, **kwargs):
        raise AssertionError("preview must not append Notion blocks")

    def delete_block(self, *args, **kwargs):
        raise AssertionError("preview must not delete Notion blocks")


def _preview_article(index: int, relevance: int, *, with_notes: bool = True):
    return DraftArticle(
        title=f"Approved article {index}",
        source_name=f"Publisher {index}",
        canonical_url=f"https://publisher-{index}.example/story",
        summary=f"The proposed project has {index * 100} MW of capacity.",
        relevance_score=relevance,
        factual_points=(
            [f"The proposed project has {index * 100} MW of capacity."]
            if with_notes
            else []
        ),
        evidence_retrieval_status="Extracted" if with_notes else "",
        resolved_publisher_url=(
            f"https://publisher-{index}.example/story" if with_notes else ""
        ),
    )


def _valid_newsletter(articles: list[DraftArticle]) -> str:
    sections = []
    for article in articles:
        sections.append(
            "\n".join(
                [
                    f"## {article.title}",
                    "#NetZeroTransition",
                    article.summary,
                    "The proposal remains under review.",
                    "Its implementation details remain material.",
                    "SOMA's Perspective:",
                    "The project status is the central execution question.",
                    "Sources:",
                    article.resolved_publisher_url or article.canonical_url,
                ]
            )
        )
    return "\n".join(sections)


def _valid_social(articles: list[DraftArticle]) -> str:
    sections = []
    for index, article in enumerate(articles, start=1):
        sections.append(
            "\n".join(
                [
                    f"Topic {index}: {article.title}",
                    f"Hook: {article.summary}",
                    "Define the Issue: The project remains proposed.",
                    "Describe the Situation: Implementation details remain open.",
                    "So Why Does This Matter? Execution affects the project timeline.",
                    "Call-to-Action: Review the proposal.",
                    "Sources:",
                    article.resolved_publisher_url or article.canonical_url,
                ]
            )
        )
    return "\n".join(sections)


def test_preview_generates_local_outputs_without_writes_or_image_cache_changes(
    monkeypatch,
    tmp_path,
) -> None:
    articles = [
        _preview_article(1, 1),
        _preview_article(2, 5),
        _preview_article(3, 4),
        _preview_article(4, 3),
    ]
    selected = [articles[1], articles[2], articles[3]]
    status_queries = []
    prompt_contexts = {}
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    image_cache = state_dir / "article_assets.json"
    image_cache.write_text('{"sentinel": true}', encoding="utf-8")
    settings = Settings(local_state_path=state_dir)
    week = SimpleNamespace(start=date(2026, 10, 12), end=date(2026, 10, 18))

    class FakeLlm:
        def __init__(self, **kwargs):
            pass

        def generate_newsletter_draft(self, week_start, week_end, context):
            prompt_contexts["newsletter"] = context
            return _valid_newsletter(selected)

        def generate_social_media_draft(self, week_start, week_end, context):
            prompt_contexts["sns"] = context
            return _valid_social(selected)

    def load_articles(notion, loaded_settings, dataset_id, statuses):
        status_queries.append(statuses)
        return list(articles)

    monkeypatch.setattr(weekly_drafts, "current_workweek", lambda: week)
    monkeypatch.setattr(
        weekly_drafts,
        "find_dataset_meeting_for_week",
        lambda *_: {"id": "dataset-1"},
    )
    monkeypatch.setattr(weekly_drafts, "load_weekly_draft_articles", load_articles)
    monkeypatch.setattr(weekly_drafts, "LlmClient", FakeLlm)
    monkeypatch.setattr(
        weekly_drafts,
        "ArticleImageResolver",
        lambda *_: (_ for _ in ()).throw(AssertionError("no preview image resolver")),
    )

    paths = weekly_drafts._run_preview(
        ReadOnlyNotion(),
        settings,
        tmp_path / "preview",
        output=lambda _: None,
    )

    assert {path.name for path in paths} == {
        "newsletter_preview.md",
        "sns_preview.md",
        "preview_summary.md",
    }
    assert all(path.exists() for path in paths)
    assert status_queries == [
        ["Use in Newsletter"],
        ["Use in Newsletter", "SNS Only"],
    ]
    assert "Approved article 1" not in prompt_contexts["newsletter"]
    assert "Approved article 2" in prompt_contexts["newsletter"]
    assert "The proposed project has 200 MW" in prompt_contexts["newsletter"]
    assert "The proposed project has 200 MW" in prompt_contexts["sns"]
    assert image_cache.read_text(encoding="utf-8") == '{"sentinel": true}'
    summary = next(path for path in paths if path.name == "preview_summary.md").read_text(
        encoding="utf-8"
    )
    assert "Research Notes: Yes" in summary
    assert "Original publisher URL: Yes" in summary
    assert "Image selection and image-cache behavior were not evaluated" in summary


def test_preview_reports_legacy_fallback_honestly(monkeypatch, tmp_path) -> None:
    legacy = _preview_article(1, 5, with_notes=False)
    settings = Settings(local_state_path=tmp_path / "state")
    week = SimpleNamespace(start=date(2026, 10, 12), end=date(2026, 10, 18))

    class FakeLlm:
        def __init__(self, **kwargs):
            pass

        def generate_newsletter_draft(self, *args):
            return _valid_newsletter([legacy])

        def generate_social_media_draft(self, *args):
            return _valid_social([legacy])

    monkeypatch.setattr(weekly_drafts, "current_workweek", lambda: week)
    monkeypatch.setattr(
        weekly_drafts,
        "find_dataset_meeting_for_week",
        lambda *_: {"id": "dataset-1"},
    )
    monkeypatch.setattr(
        weekly_drafts,
        "load_weekly_draft_articles",
        lambda *args, **kwargs: [legacy],
    )
    monkeypatch.setattr(weekly_drafts, "LlmClient", FakeLlm)

    paths = weekly_drafts._run_preview(
        ReadOnlyNotion(),
        settings,
        tmp_path / "preview",
        output=lambda _: None,
    )

    summary = next(path for path in paths if path.name == "preview_summary.md").read_text(
        encoding="utf-8"
    )
    assert "Research Notes: No" in summary
    assert "Evidence status: Not available (legacy entry)" in summary
    assert "legacy summary fallback" in summary
    assert "not evidence-grounded generation" in summary


def test_preview_main_bypasses_write_capable_weekly_page_setup(
    monkeypatch,
    tmp_path,
) -> None:
    settings = Settings()
    calls = []
    monkeypatch.setattr(weekly_drafts, "load_settings", lambda: settings)
    monkeypatch.setattr(weekly_drafts, "configure_logging", lambda _: None)
    monkeypatch.setattr(weekly_drafts, "NotionClient", lambda token: ReadOnlyNotion())
    monkeypatch.setattr(
        weekly_drafts,
        "ensure_current_weekly_pages",
        lambda *_: (_ for _ in ()).throw(AssertionError("must not ensure pages")),
    )
    monkeypatch.setattr(
        weekly_drafts,
        "_run_preview",
        lambda notion, loaded_settings, output_dir, **kwargs: calls.append(
            (Path(output_dir), kwargs)
        ),
    )

    weekly_drafts.main(["--preview", "--output-dir", str(tmp_path)])

    assert calls == [
        (
            tmp_path,
            {"refresh_evidence": False, "publisher_url_overrides": {}},
        )
    ]


def test_refresh_evidence_requires_preview() -> None:
    with pytest.raises(SystemExit):
        weekly_drafts.parse_args(["--refresh-evidence"])


def test_evidence_refresh_reaches_both_drafts_without_writes_or_cache_changes(
    monkeypatch,
    tmp_path,
) -> None:
    legacy = _preview_article(1, 5, with_notes=False)
    legacy.title = "Egypt battery assembly"
    legacy.canonical_url = "https://news.google.com/rss/articles/battery"
    settings = Settings(local_state_path=tmp_path / "state")
    settings.local_state_path.mkdir()
    image_cache = settings.local_state_path / "article_assets.json"
    image_cache.write_text('{"sentinel": true}', encoding="utf-8")
    week = SimpleNamespace(start=date(2026, 10, 12), end=date(2026, 10, 18))
    prompt_contexts = {}
    calls = {"retrieve": 0, "enrich": 0}

    class FakeRetriever:
        def retrieve(self, article):
            calls["retrieve"] += 1
            assert article.canonical_url == "https://publisher.example/egypt-battery"
            return ArticleRetrievalResult(
                canonical_url="https://publisher.example/egypt-battery",
                url_resolution_status="publisher_url",
                evidence_retrieval_status="extracted",
                article_text="The proposed facility would assemble 500 MWh annually.",
            )

    class FakeLlm:
        def __init__(self, **kwargs):
            pass

        def enrich_article(self, article):
            calls["enrich"] += 1
            assert "500 MWh" in article.article_text
            return EnrichedArticle(
                summary="Egypt proposed a battery assembly plant with 500 MWh capacity.",
                why_it_matters="The proposal could add local battery manufacturing.",
                relevance_score=5,
                topic=["Batteries"],
                region=["Egypt"],
                newsletter_angle="Assess the proposed manufacturing capacity.",
                sns_hook="Egypt has proposed 500 MWh of annual assembly capacity.",
                factual_points=[
                    "The proposed battery facility would assemble 500 MWh annually."
                ],
            )

        def generate_newsletter_draft(self, week_start, week_end, context):
            prompt_contexts["newsletter"] = context
            refreshed = DraftArticle(
                title=legacy.title,
                source_name=legacy.source_name,
                canonical_url=legacy.canonical_url,
                summary="Egypt proposed a battery assembly plant with 500 MWh capacity.",
                factual_points=[
                    "The proposed battery facility would assemble 500 MWh annually."
                ],
                evidence_retrieval_status="extracted",
                resolved_publisher_url="https://publisher.example/egypt-battery",
            )
            return _valid_newsletter([refreshed])

        def generate_social_media_draft(self, week_start, week_end, context):
            prompt_contexts["sns"] = context
            refreshed = DraftArticle(
                title=legacy.title,
                source_name=legacy.source_name,
                canonical_url=legacy.canonical_url,
                summary="Egypt proposed a battery assembly plant with 500 MWh capacity.",
                factual_points=[
                    "The proposed battery facility would assemble 500 MWh annually."
                ],
                evidence_retrieval_status="extracted",
                resolved_publisher_url="https://publisher.example/egypt-battery",
            )
            return _valid_social([refreshed])

    monkeypatch.setattr(weekly_drafts, "current_workweek", lambda: week)
    monkeypatch.setattr(
        weekly_drafts,
        "find_dataset_meeting_for_week",
        lambda *_: {"id": "dataset-1"},
    )
    monkeypatch.setattr(
        weekly_drafts,
        "load_weekly_draft_articles",
        lambda *args, **kwargs: [
            DraftArticle(**{**legacy.__dict__, "factual_points": []})
        ],
    )
    monkeypatch.setattr(weekly_drafts, "LlmClient", FakeLlm)
    monkeypatch.setattr(weekly_drafts, "ArticleRetriever", FakeRetriever)
    monkeypatch.setattr(
        weekly_drafts,
        "ArticleImageResolver",
        lambda *_: (_ for _ in ()).throw(AssertionError("no preview image resolver")),
    )

    paths = weekly_drafts._run_preview(
        ReadOnlyNotion(),
        settings,
        tmp_path / "preview",
        refresh_evidence=True,
        publisher_url_overrides={
            "egypt battery": "https://publisher.example/egypt-battery"
        },
        output=lambda _: None,
    )

    assert {path.name for path in paths} == {
        "newsletter_evidence_preview.md",
        "sns_evidence_preview.md",
        "evidence_report.md",
    }
    assert calls == {"retrieve": 1, "enrich": 1}
    assert "500 MWh" in prompt_contexts["newsletter"]
    assert "500 MWh" in prompt_contexts["sns"]
    assert "Research retrieval status: extracted" in prompt_contexts["newsletter"]
    assert "https://publisher.example/egypt-battery" in prompt_contexts["sns"]
    assert image_cache.read_text(encoding="utf-8") == '{"sentinel": true}'
    report = next(path for path in paths if path.name == "evidence_report.md").read_text(
        encoding="utf-8"
    )
    assert "Full-article enrichment succeeded for 1/1" in report
    assert "Factual points extracted: 1" in report


def test_evidence_refresh_reports_retrieval_failure_as_legacy_fallback(
    monkeypatch,
    tmp_path,
) -> None:
    legacy = _preview_article(1, 5, with_notes=False)
    legacy.title = "Iraq solar expansion"
    legacy.canonical_url = "https://news.google.com/rss/articles/solar"
    settings = Settings(local_state_path=tmp_path / "state")
    week = SimpleNamespace(start=date(2026, 10, 12), end=date(2026, 10, 18))
    contexts = []

    class BlockedRetriever:
        def retrieve(self, article):
            return ArticleRetrievalResult(
                canonical_url=article.canonical_url,
                url_resolution_status="unresolved",
                evidence_retrieval_status="blocked",
            )

    class FakeLlm:
        def __init__(self, **kwargs):
            pass

        def enrich_article(self, article):
            assert not article.article_text
            return EnrichedArticle(
                summary=article.snippet,
                why_it_matters="",
                relevance_score=5,
                factual_points=["Limited point retained from the legacy summary."],
            )

        def generate_newsletter_draft(self, *args):
            contexts.append(args[-1])
            return _valid_newsletter([legacy])

        def generate_social_media_draft(self, *args):
            contexts.append(args[-1])
            return _valid_social([legacy])

    monkeypatch.setattr(weekly_drafts, "current_workweek", lambda: week)
    monkeypatch.setattr(
        weekly_drafts,
        "find_dataset_meeting_for_week",
        lambda *_: {"id": "dataset-1"},
    )
    monkeypatch.setattr(
        weekly_drafts,
        "load_weekly_draft_articles",
        lambda *args, **kwargs: [legacy],
    )
    monkeypatch.setattr(weekly_drafts, "LlmClient", FakeLlm)
    monkeypatch.setattr(weekly_drafts, "ArticleRetriever", BlockedRetriever)

    paths = weekly_drafts._run_preview(
        ReadOnlyNotion(),
        settings,
        tmp_path / "preview",
        refresh_evidence=True,
        output=lambda _: None,
    )

    assert all("Limited points from available feed context" in value for value in contexts)
    assert all("Factual evidence (primary" not in value for value in contexts)
    report = next(path for path in paths if path.name == "evidence_report.md").read_text(
        encoding="utf-8"
    )
    assert "Evidence retrieval status: blocked" in report
    assert "Full-article evidence used: No" in report
    assert "Publisher blocked retrieval; enrichment used legacy summary context only" in report
