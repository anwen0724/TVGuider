from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


@dataclass
class OpenAIClientConfig:
    model: str = "gpt-4o"
    temperature: float = 0.2
    max_tokens: int = 16384
    api_key: str | None = None
    base_url: str | None = None


class OpenAILLMClient:
    def __init__(self, cfg: OpenAIClientConfig | None = None):
        self.cfg = cfg or OpenAIClientConfig()
        self.client = OpenAI(
            api_key=self.cfg.api_key or os.getenv("OPENAI_API_KEY"),
            base_url=self.cfg.base_url or os.getenv("OPENAI_BASE_URL"),
        )

    def generate(self, prompt: str) -> str:
        return self.generate_response(prompt)["content"] or ""

    def generate_response(self, prompt: str) -> dict:
        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
        )
        data = resp.model_dump(mode="json")
        choice = next(iter(data.get("choices") or []), {})
        return {
            "content": (choice.get("message") or {}).get("content"),
            "model": data.get("model"),
            "finish_reason": choice.get("finish_reason"),
            "usage": data.get("usage"),
            "response": data,
        }


if __name__ == "__main__":
    client = OpenAILLMClient()

    response = client.generate("Explain setup and hold timing violations in synchronous circuits.")
    print(response)
