from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import os

import anthropic

from dotenv import load_dotenv

load_dotenv()


@dataclass
class ClaudeClientConfig:
    model: str = "claude-3-5-sonnet-20240620"
    temperature: float = 0.2
    max_tokens: int = 8192
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class ClaudeLLMClient:
    def __init__(self, cfg: Optional[ClaudeClientConfig] = None):
        self.cfg = cfg or ClaudeClientConfig()
        self.client = anthropic.Anthropic(
            api_key=self.cfg.api_key or os.getenv("ANTHROPIC_API_KEY"),
            base_url=self.cfg.base_url or os.getenv("ANTHROPIC_BASE_URL"),
        )

    def generate(self, prompt: str) -> str:

        message = self.client.messages.create(
            model=self.cfg.model,
            max_tokens=self.cfg.max_tokens,
            temperature=self.cfg.temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        return message.content[0].text


if __name__ == "__main__":
    client = ClaudeLLMClient()

    response = client.generate("你是claude3.5还是claude4？")
    print(response)
