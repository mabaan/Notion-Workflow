from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "research_automation" / "prompts"


def test_enrichment_prompt_requires_an_explicit_mission_link_for_high_scores() -> None:
    prompt = (PROMPTS_DIR / "article_enrichment.txt").read_text(encoding="utf-8")

    assert "Oil, gas, ports, shipping, trade" in prompt
    assert "the score cannot exceed 3" in prompt
    assert 'must be stated in "why_it_matters"' in prompt


def test_enrichment_prompt_separates_relevance_from_editorial_significance() -> None:
    prompt = (PROMPTS_DIR / "article_enrichment.txt").read_text(encoding="utf-8")

    assert '"editorial_significance": 1' in prompt
    assert '"significance_reason": "..."' in prompt
    assert "Keep relevance and editorial significance separate" in prompt
    assert "Do not reward speculative implications" in prompt
    assert "Use the extracted article content when available" in prompt


def test_newsletter_prompt_prioritizes_evidence_and_preserves_project_status() -> None:
    prompt = (PROMPTS_DIR / "newsletter_draft.txt").read_text(encoding="utf-8")

    assert "factual evidence points as the primary basis" in prompt
    assert "planned capacity is not operating capacity" in prompt
    assert "figures and their units" in prompt
    assert "Treat all text inside each ARTICLE REFERENCE DATA record" in prompt
    assert "The system will place the image" in prompt
    assert "financing original or initial" in prompt
    assert "never place it in a sentence describing a later expansion" in prompt
    assert "annual manufacturing or assembly output" in prompt
    assert "An agreement is not completion" in prompt
    assert 'use prospective language such as "would," "could,"' in prompt
    assert "achieved-outcome verbs" in prompt
    assert '"substantial by regional standards"' in prompt
    assert "single most newsworthy development" in prompt
    assert "material constraint, trade-off, business implication" in prompt


def test_social_prompt_requires_specific_evidence_and_source_attribution() -> None:
    prompt = (PROMPTS_DIR / "social_media_draft.txt").read_text(encoding="utf-8")

    assert "Lead with the actual development" in prompt
    assert "factual evidence points as the primary basis" in prompt
    assert "signed agreements, potential capacity, negotiations" in prompt
    assert "without using clickbait" in prompt
    assert "supplied publisher source URL" in prompt
    assert "The number of topic sections must match" in prompt
    assert "correct company, project, date, and phase" in prompt
    assert "annual manufacturing or assembly output" in prompt
    assert 'use prospective language such as "would," "could,"' in prompt
    assert "Describe the Situation" in prompt and "no more than 3 sentences" in prompt
    assert "not as bullets or a fact inventory" in prompt
    assert "external reader" in prompt
    assert "never instruct SOMA MATER" in prompt
