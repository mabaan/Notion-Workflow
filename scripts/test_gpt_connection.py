"""Test OpenAI API connectivity with a short prompt."""

from __future__ import annotations

from openai import OpenAI

from research_automation.config import load_settings

PROMPT = "Hello, respond in 5 tokens."


def main() -> None:
    """Run the OpenAI connection test."""

    settings = load_settings()

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is missing.")

    client = OpenAI(api_key=settings.openai_api_key)

    response = client.responses.create(
        model=settings.llm_model,
        input=PROMPT,
    )

    print(f"Connected to OpenAI using model {settings.llm_model}.")
    print(response.output_text.strip())


if __name__ == "__main__":
    main()
