"""Evidence provenance shared by enrichment, Research Notes, and drafting."""

FEED_CONTENT_STATUS = "feed_content"
FEED_CONTENT_LIMITATION = (
    "Feed-provided article content; completeness not verified. "
    "It may be an excerpt. Use only the supplied text."
)


def is_feed_content(status: str) -> bool:
    """Recognize both the in-memory and Research Notes status spellings."""

    return status.strip().casefold().replace(" ", "_") == FEED_CONTENT_STATUS


def has_article_evidence(status: str) -> bool:
    """Recognize usable article text without asserting that a feed is complete."""

    return status.strip().casefold() == "extracted" or is_feed_content(status)
