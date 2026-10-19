"""Small shared editorial contract; model judgments describe the primary news."""

from __future__ import annotations


STORY_TYPES = (
    "development", "policy_regulation", "investment_financing",
    "infrastructure_project", "research_result", "investigation",
    "supply_disruption", "explainer_background", "commentary_opinion",
    "politics_diplomacy", "conflict_security", "humanitarian_relief",
    "routine_event", "other",
)

# JSON booleans for established novelty; a string only for genuine uncertainty.
NOVELTY_SCHEMA = {"anyOf": [
    {"type": "boolean"}, {"type": "string", "enum": ["unclear"]},
]}


def validate_editorial_fields(payload: dict) -> None:
    """Require both fields in new model responses, without truthy coercion."""

    if payload.get("story_type") not in STORY_TYPES:
        raise ValueError("Missing or invalid editorial story_type")
    value = payload.get("is_new_development")
    if not (type(value) is bool or (type(value) is str and value == "unclear")):
        raise ValueError("Missing or invalid editorial is_new_development")


def editorial_rejection_reason(story_type: str, is_new_development: bool | str) -> str:
    """Apply scope to the detailed judgment, never to title keywords.

    A material mission consequence must be the primary subject and use a mission
    type, e.g. supply_disruption, rather than conflict_security. An explainer or
    commentary requires an explicitly established substantive new development.
    Unclear novelty alone does not override the existing quality thresholds.
    """

    try:
        validate_editorial_fields({
            "story_type": story_type, "is_new_development": is_new_development,
        })
    except ValueError:
        return "editorial scope: invalid story type or novelty"
    if is_new_development is False:
        return "editorial scope: no substantive new development"
    if story_type in {"politics_diplomacy", "conflict_security", "humanitarian_relief", "routine_event"}:
        return f"editorial scope: primary story type {story_type}"
    if story_type in {"explainer_background", "commentary_opinion"} and is_new_development is not True:
        return f"editorial scope: {story_type} without an established new development"
    return ""
