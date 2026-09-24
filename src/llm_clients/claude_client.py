from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ClaudeClientConfig:
    model: str = "claude-3-5-sonnet-20240620"
    temperature: float = 0.2
    max_tokens: int = 8192
    api_key: str | None = None
    base_url: str | None = None


class ClaudeLLMClient:
    def __init__(self, cfg: ClaudeClientConfig | None = None):
        self.cfg = cfg or ClaudeClientConfig()
        self.client = anthropic.Anthropic(
            api_key=self.cfg.api_key or os.getenv("ANTHROPIC_API_KEY"),
            base_url=self.cfg.base_url or os.getenv("ANTHROPIC_BASE_URL"),
        )

    def generate(self, prompt: str) -> str:
        return self.generate_response(prompt)["content"]

    def generate_response(self, prompt: str) -> dict:
        message = self.client.messages.create(
            model=self.cfg.model,
            max_tokens=self.cfg.max_tokens,
            temperature=self.cfg.temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        data = message.model_dump(mode="json")
        return {
            "content": "".join(
                block["text"] for block in data["content"] if block["type"] == "text"
            ),
            "model": data.get("model"),
            "finish_reason": data.get("stop_reason"),
            "usage": data.get("usage"),
            "response": data,
        }


if __name__ == "__main__":
    client = ClaudeLLMClient()

    response = client.generate("你是claude3.5还是claude4？")
    print(response)
