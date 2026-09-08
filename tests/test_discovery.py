from research_automation.config import Settings
from research_automation.models.source import Source
from research_automation.pipeline.discovery import DiscoveryService
from research_automation.clients.discovery_common import ProviderError


def _publisher(name, host, quality, regions=("Global",)):
    return Source(
        name=name,
        source_type="Publisher",
        source_url=f"https://{host}",
        feed_url=f"https://{host}/rss",
        collection_method="RSS",
        editorial_quality=quality,
        region=list(regions),
        topic_focus=["energy transition"],
        notion_page_id=f"{name}-id",
    )


def _provider(name, quality, priority):
    return Source(
        name=name,
        source_type="Discovery Provider",
        collection_method="API",
        editorial_quality=quality,
        acquisition_priority=priority,
        notion_page_id=f"{name}-id",
    )


def test_provider_order_uses_provider_quality_before_priority() -> None:
    service = DiscoveryService(
        Settings(),
        [
            _provider("NewsAPI Fallback", 4, "Core"),
            _provider("Brave Search Fallback", 5, "Trial"),
        ],
    )
    assert service.provider_order == ("brave", "newsapi")


def test_discovered_reuters_article_inherits_reuters_quality_not_provider_quality() -> None:
    reuters = _publisher("Reuters", "reuters.com", 9, ("MENA", "UAE"))
    brave = _provider("Brave Search Fallback", 5, "Core")
    service = DiscoveryService(Settings(), [brave, reuters])
    articles = service._map_results(
        "Global",
        [
            {
                "url": "https://www.reuters.com/world/energy-story",
                "title": "Global renewable energy investment accelerates",
                "description": "Global grid and renewable energy policy",
                "page_age": "2026-09-01T08:00:00Z",
            }
        ],
        brave,
        kind="brave",
    )
    assert articles[0].source_name == "Reuters"
    assert articles[0].source_editorial_quality == 9
    assert articles[0].publisher_key == "Reuters-id"
    assert articles[0].discovery_provider == "Brave Search Fallback"
    assert articles[0].region == ["Global", "MENA", "UAE"]


def test_unknown_discovered_publisher_gets_no_provider_rating() -> None:
    brave = _provider("Brave Search Fallback", 5, "Core")
    service = DiscoveryService(Settings(), [brave])
    articles = service._map_results(
        "Global",
        [
            {
                "url": "https://unknown.example/story",
                "title": "Global renewable energy investment accelerates",
                "description": "Global grid and renewable energy policy",
                "page_age": "2026-09-01T08:00:00Z",
            }
        ],
        brave,
        kind="brave",
    )
    assert articles[0].source_editorial_quality is None
    assert articles[0].source_page_id == ""
    assert articles[0].publisher_key == "unknown.example"


def test_preferred_discovery_domains_are_quality_sorted_not_row_sorted() -> None:
    service = DiscoveryService(
        Settings(),
        [
            _publisher("Lower", "lower.example", 4, ("Global",)),
            _publisher("Higher", "higher.example", 9, ("Global",)),
        ],
    )
    assert service._preferred_source_domains("Global") == [
        "higher.example",
        "lower.example",
    ]


def test_provider_failure_is_reported_and_next_provider_continues() -> None:
    class FailingBrave:
        def search_news(self, **kwargs):
            raise ProviderError("Brave unavailable")

    class WorkingNewsApi:
        def search_everything(self, **kwargs):
            return [
                {
                    "url": "https://unknown.example/global-grid-story",
                    "title": "Global renewable grid policy investment expands",
                    "description": "Global renewable energy transition and grid policy",
                    "publishedAt": "2026-09-01T08:00:00Z",
                    "source": {"name": "Unknown"},
                }
            ]

    service = DiscoveryService(
        Settings(brave_search_api_key="brave", news_api_key="news"),
        [
            _provider("Brave Search Fallback", 5, "Core"),
            _provider("NewsAPI Fallback", 4, "Secondary"),
        ],
    )
    service.brave = FailingBrave()
    service.newsapi = WorkingNewsApi()
    articles = service.discover_articles(
        {"Global": 1, "UAE": 0, "KSA": 0, "Egypt": 0},
        max_per_region=2,
        excluded_hashes=set(),
    )
    assert len(articles) == 1
    assert [(attempt.source_name, attempt.outcome) for attempt in service.attempts] == [
        ("Brave Search Fallback", "HTTP Error"),
        ("NewsAPI Fallback", "Success"),
    ]


def test_duplicate_provider_result_does_not_consume_candidate_limit() -> None:
    duplicate_url = "https://unknown.example/shared-story"

    class Brave:
        def search_news(self, **kwargs):
            return [
                {
                    "url": duplicate_url,
                    "title": "Global renewable grid policy advances",
                    "description": "Global renewable grid transition policy",
                    "page_age": "2026-09-01T08:00:00Z",
                }
            ]

    class NewsApi:
        def search_everything(self, **kwargs):
            return [
                {
                    "url": duplicate_url,
                    "title": "Global renewable grid policy advances",
                    "description": "Global renewable grid transition policy",
                    "publishedAt": "2026-09-01T08:00:00Z",
                },
                {
                    "url": "https://another.example/distinct-story",
                    "title": "Global solar supply chain policy changes",
                    "description": "Global solar energy supply chain policy",
                    "publishedAt": "2026-09-01T07:00:00Z",
                },
            ]

    service = DiscoveryService(
        Settings(brave_search_api_key="brave", news_api_key="news"),
        [
            _provider("Brave Search Fallback", 5, "Core"),
            _provider("NewsAPI Fallback", 4, "Secondary"),
        ],
    )
    service.brave = Brave()
    service.newsapi = NewsApi()
    articles = service.discover_articles(
        {"Global": 1, "UAE": 0, "KSA": 0, "Egypt": 0},
        max_per_region=2,
        excluded_hashes=set(),
    )
    assert [article.canonical_url for article in articles] == [
        "https://another.example/distinct-story",
        duplicate_url,
    ]
