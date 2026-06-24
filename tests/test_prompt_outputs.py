from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "research_automation" / "prompts"


def test_prompt_templates_exist_and_are_non_empty() -> None:
    for prompt_name in [
        "article_enrichment.txt",
        "newsletter_draft.txt",
        "sns_draft.txt",
    ]:
        prompt = PROMPTS_DIR / prompt_name
        assert prompt.exists()
        assert prompt.read_text(encoding="utf-8").strip()

