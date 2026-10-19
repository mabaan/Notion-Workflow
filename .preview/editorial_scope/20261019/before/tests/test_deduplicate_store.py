from research_automation.pipeline.deduplicate import SeenArticleStore


def test_dedupe_store_loads_and_saves(tmp_path) -> None:
    store_path = tmp_path / "seen_articles.json"
    store = SeenArticleStore(store_path)

    assert not store.contains("abc")

    store.record(
        url_hash="abc",
        title="Story",
        canonical_url="https://example.com/story",
        source="Reuters",
        notion_page_id="page-1",
        created_at="2026-07-01T00:00:00+00:00",
    )

    reloaded = SeenArticleStore(store_path)
    assert reloaded.contains("abc")


def test_dedupe_store_prunes_missing_pages(tmp_path) -> None:
    store_path = tmp_path / "seen_articles.json"
    store = SeenArticleStore(store_path)
    store.record(
        url_hash="keep",
        title="Keep",
        canonical_url="https://example.com/keep",
        source="Reuters",
        notion_page_id="page-keep",
        created_at="2026-07-01T00:00:00+00:00",
    )
    store.record(
        url_hash="drop",
        title="Drop",
        canonical_url="https://example.com/drop",
        source="Reuters",
        notion_page_id="page-drop",
        created_at="2026-07-01T00:00:00+00:00",
    )

    removed = store.prune_missing_pages({"page-keep"})

    assert removed == 1
    assert store.contains("keep")
    assert not store.contains("drop")
