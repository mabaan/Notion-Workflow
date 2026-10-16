import json
from pathlib import Path

import httpx
from openai import OpenAI
import pytest

import research_automation.clients.llm_client as llm_module


@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-4.1-mini"])
@pytest.mark.parametrize("json_output", [True, False])
def test_generation_preserves_output_contract_and_model_parameters(
    monkeypatch, model: str, json_output: bool
) -> None:
    requests = []
    content = '{"summary": "Supported fact"}' if json_output else "Newsletter draft"

    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        if model.startswith("gpt-6-luna"):
            assert "temperature" not in payload
            assert payload["reasoning_effort"] == "medium"
        else:
            assert payload["temperature"] == (0.2 if json_output else 0.4)
            assert "reasoning_effort" not in payload
        return httpx.Response(
            200,
            json={
                "id": "offline-completion",
                "object": "chat.completion",
                "created": 0,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": content},
                    }
                ],
            },
        )

    with OpenAI(
        api_key="offline-test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        max_retries=0,
    ) as api:
        monkeypatch.setattr(llm_module, "OpenAI", lambda **kwargs: api)
        client = llm_module.LlmClient(
            provider="openai",
            model=model,
            api_key="offline-test-key",
            prompt_directory=Path("unused"),
        )
        if json_output:
            assert client._generate_json("Reference facts") == {"summary": "Supported fact"}
        else:
            assert client._generate_text("Reference facts") == content

    assert len(requests) == 1
    request = requests[0]
    assert request["model"] == model
    assert request["messages"][-1] == {"role": "user", "content": "Reference facts"}
    if json_output:
        assert request["response_format"] == {"type": "json_object"}
    else:
        assert "response_format" not in request
