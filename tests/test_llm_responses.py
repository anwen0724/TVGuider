import importlib
import json

import httpx
import pytest
from anthropic import Anthropic
from openai import OpenAI


@pytest.mark.parametrize(
    "provider,prefix",
    [("deepseek", "DeepSeek"), ("qwen", "Qwen"), ("openai", "OpenAI"), ("codellama", "CodeLlama")],
)
def test_openai_compatible_clients_preserve_response_metadata(provider, prefix):
    module = importlib.import_module(f"llm_clients.{provider}_client")
    client = getattr(module, f"{prefix}LLMClient").__new__(getattr(module, f"{prefix}LLMClient"))
    client.cfg = getattr(module, f"{prefix}ClientConfig")(max_tokens=12345)
    requests = []

    def reply(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "response-test",
                "object": "chat.completion",
                "created": 1,
                "model": "served-model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "length",
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": "provider-test-content",
                        },
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 12345, "total_tokens": 12365},
                "provider_extension": "preserved",
            },
        )

    with OpenAI(
        api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(reply))
    ) as sdk:
        client.client = sdk
        response = client.generate_response("prompt")
        assert response["content"] == ""
        assert response["model"] == "served-model"
        assert response["finish_reason"] == "length"
        assert response["usage"]["completion_tokens"] == 12345
        assert (
            response["response"]["choices"][0]["message"]["reasoning_content"]
            == "provider-test-content"
        )
        assert response["response"]["provider_extension"] == "preserved"
        assert client.generate("prompt") == ""
    assert all(request["max_tokens"] == 12345 for request in requests)


def test_claude_client_preserves_all_content_blocks_and_usage():
    from llm_clients.claude_client import ClaudeClientConfig, ClaudeLLMClient

    client = ClaudeLLMClient.__new__(ClaudeLLMClient)
    client.cfg = ClaudeClientConfig()

    def reply(request):
        return httpx.Response(
            200,
            json={
                "id": "msg-test",
                "type": "message",
                "role": "assistant",
                "model": "served-model",
                "content": [
                    {"type": "text", "text": "first\n"},
                    {"type": "text", "text": "second"},
                ],
                "stop_reason": "max_tokens",
                "stop_sequence": None,
                "usage": {"input_tokens": 20, "output_tokens": 8192},
            },
        )

    with Anthropic(
        api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(reply))
    ) as sdk:
        client.client = sdk
        response = client.generate_response("prompt")
        assert response["content"] == "first\nsecond"
        assert response["finish_reason"] == "max_tokens"
        assert response["usage"]["output_tokens"] == 8192
        assert len(response["response"]["content"]) == 2
