"""Reusable, synchronous metadata batching with bounded validation recovery."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
import json
import logging
import time

from openai import APIConnectionError, APIResponseValidationError, APIStatusError, APITimeoutError, OpenAI

from research_automation.config import Settings
from research_automation.models.classification import (
    DECISIONS, REGIONS, TOPICS, ArticleClassification, ClassificationInput,
    ClassificationOutcome, ClassificationReport, ClassificationRequest,
)

logger = logging.getLogger(__name__)

# Verified Chat Completions + strict JSON Schema models. Adding a
# model requires checking its endpoint, schema support and limits, not guessing
# from the installed SDK's parameter names. No model-capability API calls.
MODEL_LIMITS = {
    "gpt-4.1-mini": (1_047_576, 32_768),
    "gpt-4.1-nano": (1_047_576, 32_768),
    "gpt-6-luna": (1_050_000, 128_000),
}


class MalformedClassification(ValueError):
    """The entire response is invalid, even if some rows look usable."""


class OutputLimitReached(ValueError):
    """Retry the input as smaller batches, not as a partial JSON document."""


def classification_schema(ids: Sequence[str]) -> dict:
    fields = {
        "article_id": {"type": "string", "enum": list(ids)},
        "relevance_score": {"type": "integer", "minimum": 1, "maximum": 5},
        "assigned_region": {"type": "string", "enum": list(REGIONS)},
        "primary_mission_topic": {"type": "string", "enum": list(TOPICS)},
        "decision": {"type": "string", "enum": list(DECISIONS)},
        "justification": {"type": "string", "minLength": 1, "maxLength": 240},
    }
    return {
        "type": "object", "additionalProperties": False, "required": ["classifications"],
        "properties": {"classifications": {
            "type": "array", "minItems": len(ids), "maxItems": len(ids),
            "items": {
                "type": "object", "additionalProperties": False,
                "required": list(fields), "properties": fields,
            },
        }},
    }


def _validate_schema(value, schema: dict) -> None:
    """Validate precisely the JSON Schema subset above without another dependency.

    No coercion: booleans, numeric strings and floating-point scores are invalid.
    """

    kind = schema["type"]
    expected = {"object": dict, "array": list, "string": str, "integer": int}[kind]
    if type(value) is not expected:
        raise MalformedClassification("invalid field type")
    if "enum" in schema and value not in schema["enum"]:
        raise MalformedClassification("unknown enum value or article ID")
    if kind == "object":
        if set(value) != set(schema["required"]):
            raise MalformedClassification("missing or unexpected fields")
        for name, child in value.items():
            _validate_schema(child, schema["properties"][name])
    elif kind == "array":
        if not schema["minItems"] <= len(value) <= schema["maxItems"]:
            raise MalformedClassification("missing or extra results")
        for child in value:
            _validate_schema(child, schema["items"])
    elif kind == "integer":
        if not schema["minimum"] <= value <= schema["maximum"]:
            raise MalformedClassification("score outside 1-5")
    elif kind == "string" and (
        not value.strip() or not schema.get("minLength", 1) <= len(value) <= schema.get("maxLength", len(value))
    ):
        raise MalformedClassification("empty or oversized text")


def _unique_json_object(pairs: list[tuple]) -> dict:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise MalformedClassification("repeated JSON object keys")
    return result


class ArticleClassifier:
    def __init__(
        self, settings: Settings, *, client: OpenAI | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        if settings.classification_model not in MODEL_LIMITS:
            raise ValueError("Classification model capabilities have not been verified; see MODEL_LIMITS")
        for name in ("batch_size", "max_request_bytes", "max_output_tokens", "max_attempts", "timeout_seconds"):
            value = getattr(settings, "classification_" + name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"classification_{name} must be a positive integer")
        if settings.classification_max_attempts > 3:
            raise ValueError("classification_max_attempts must be at most 3")
        self.context_limit, self.output_limit = MODEL_LIMITS[settings.classification_model]
        if settings.classification_max_output_tokens > self.output_limit:
            raise ValueError("classification_max_output_tokens exceeds the verified model limit")
        self.prompt = (settings.prompt_directory / "article_classification.txt").read_text(encoding="utf-8")
        self.client = (client or OpenAI(api_key=settings.openai_api_key)).with_options(
            max_retries=0, timeout=settings.classification_timeout_seconds,
        )
        self.sleep = sleep

    def classify(self, articles: Sequence[ClassificationInput]) -> ClassificationReport:
        """Return one outcome per input, preserving failures without invented scores."""

        ids = [article.article_id for article in articles]
        if any(not isinstance(article_id, str) or not article_id.strip() or article_id != article_id.strip()
               or len(article_id) > 128 for article_id in ids):
            raise ValueError("Input article IDs must be nonempty, trimmed strings of at most 128 characters")
        if len(set(ids)) != len(ids):
            raise ValueError("Input article IDs must be unique")
        for article in articles:
            if not isinstance(article.title, str) or not article.title.strip():
                raise ValueError("Input articles require a nonempty title")
            if not isinstance(article.snippet, str) or not isinstance(article.publisher, str):
                raise ValueError("Input snippet and publisher must be strings")
            if article.published_date is not None and not isinstance(article.published_date, datetime):
                raise ValueError("Input publication date must be a datetime or explicitly unknown (None)")
            if not isinstance(article.source_region_hints, (tuple, list)) or any(
                not isinstance(hint, str) for hint in article.source_region_hints
            ):
                raise ValueError("Input source-region hints must be a sequence of strings")
        # Stable membership and request order; model output order never maps IDs.
        ordered = sorted(articles, key=lambda article: article.article_id)
        report = ClassificationReport(model=self.settings.classification_model)
        outcomes: dict[str, ClassificationOutcome] = {}
        fatal_error: str | None = None

        def fail(batch, reason):
            for article in batch:
                outcomes[article.article_id] = ClassificationOutcome(article.article_id, error=reason)

        def split_or_fail(batch, reason):
            if len(batch) == 1:
                fail(batch, reason)
                return
            report.split_count += 1
            middle = len(batch) // 2
            process(batch[:middle])
            process(batch[middle:])

        def process(batch):
            nonlocal fatal_error
            if fatal_error:
                fail(batch, fatal_error)
                return
            arguments = self._request_arguments(batch)
            if not self._fits(batch, arguments):
                split_or_fail(batch, "metadata_or_output_budget_exceeded")
                return
            reason = "classification_failed"
            for attempt in range(1, self.settings.classification_max_attempts + 1):
                record = ClassificationRequest(
                    tuple(article.article_id for article in batch), report.model, attempt,
                )
                report.requests.append(record)
                try:
                    response = self.client.chat.completions.create(**arguments)
                    returned_model = getattr(response, "model", None)
                    record.returned_model = returned_model if isinstance(returned_model, str) else None
                    usage = getattr(response, "usage", None)
                    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                        value = getattr(usage, key, None)
                        if type(value) is int and value >= 0:
                            setattr(record, key, value)
                    rows = self._parse_response(response, arguments["response_format"]["json_schema"]["schema"])
                except OutputLimitReached:
                    record.status = "output_limit"
                    split_or_fail(batch, record.status)
                    return
                except (MalformedClassification, APIResponseValidationError, json.JSONDecodeError):
                    reason = record.status = "malformed_response"
                except APIStatusError as exc:
                    # Do not retain raw API error text, request data or secrets.
                    reason = record.status = f"http_{exc.status_code}"
                    code = str(exc.code or "")
                    if exc.status_code == 413 or code in {"context_length_exceeded", "max_tokens_exceeded"}:
                        split_or_fail(batch, "request_size_limit")
                        return
                    if exc.status_code in {400, 401, 403, 404, 422} or code == "insufficient_quota":
                        fatal_error = reason
                        fail(batch, reason)
                        return
                    if exc.status_code != 429 and exc.status_code < 500:
                        fail(batch, reason)
                        return
                except (APIConnectionError, APITimeoutError):
                    reason = record.status = "connection_or_timeout"
                else:
                    record.status = "success"
                    outcomes.update({row.article_id: ClassificationOutcome(row.article_id, row) for row in rows})
                    return
                if attempt < self.settings.classification_max_attempts:
                    self.sleep(0.25 * 2 ** (attempt - 1))
            # More requests cannot fix rate limiting or a sustained outage.
            # Malformed responses/timeouts can be isolated with smaller inputs.
            if reason == "malformed_response" or reason == "connection_or_timeout":
                split_or_fail(batch, reason)
            else:
                fail(batch, reason)

        size = self.settings.classification_batch_size
        for offset in range(0, len(ordered), size):
            process(ordered[offset:offset + size])
        report.outcomes = [outcomes[article_id] for article_id in ids]
        logger.info(
            "Article classification: model=%s inputs=%d requests=%d failures=%d tokens=%s unknown_usage=%d",
            report.model, len(ids), report.request_count, len(report.failed_ids),
            report.token_usage, report.requests_without_usage,
        )
        return report

    def _request_arguments(self, batch: Sequence[ClassificationInput]) -> dict:
        return {
            "model": self.settings.classification_model,
            # Match the existing enrichment client; omit incompatible sampling
            # parameters. No tools/function calls are used by this classifier.
            **({"reasoning_effort": "medium"} if self.settings.classification_model == "gpt-6-luna" else {}),
            "max_completion_tokens": self.settings.classification_max_output_tokens,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "article_classifications", "strict": True,
                "schema": classification_schema([article.article_id for article in batch]),
            }},
            "messages": [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": json.dumps({"articles": [article.as_record() for article in batch]}, ensure_ascii=False)},
            ],
        }

    def _fits(self, batch: Sequence[ClassificationInput], arguments: dict) -> bool:
        # UTF-8 bytes are a conservative token upper bound, not a tokenizer.
        request_bytes = len(json.dumps(arguments, ensure_ascii=False).encode("utf-8"))
        # Reserve room for field names, enums, IDs and brief English rationales.
        output_estimate = 256 + sum(256 + len(article.article_id.encode("utf-8")) for article in batch)
        output_budget = self.settings.classification_max_output_tokens
        return (
            request_bytes <= self.settings.classification_max_request_bytes
            and request_bytes + output_budget + 1024 <= self.context_limit
            and output_estimate <= output_budget
        )

    @staticmethod
    def _parse_response(response, schema: dict) -> list[ArticleClassification]:
        choices = getattr(response, "choices", None)
        if not isinstance(choices, list) or len(choices) != 1:
            raise MalformedClassification("empty choices")
        choice = choices[0]
        finish_reason = getattr(choice, "finish_reason", None)
        if finish_reason == "length":
            raise OutputLimitReached()
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if finish_reason != "stop" or getattr(message, "refusal", None) or not isinstance(content, str) or not content:
            raise MalformedClassification("refused or incomplete response")
        try:
            payload = json.loads(content, object_pairs_hook=_unique_json_object)
        except json.JSONDecodeError as exc:
            raise MalformedClassification("invalid JSON") from exc
        _validate_schema(payload, schema)
        rows = payload["classifications"]
        returned_ids = [row["article_id"] for row in rows]
        if len(set(returned_ids)) != len(returned_ids):
            raise MalformedClassification("repeated article IDs")
        # Enum + exact array cardinality + uniqueness imply exact ID coverage.
        return [ArticleClassification(**row) for row in rows]
