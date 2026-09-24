from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import os

from openai import OpenAI

from dotenv import load_dotenv

load_dotenv()


@dataclass
class OpenAIClientConfig:
    model: str = "gpt-4o"
    temperature: float = 0.2
    max_tokens: int = 8192
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class OpenAILLMClient:
    def __init__(self, cfg: Optional[OpenAIClientConfig] = None):
        self.cfg = cfg or OpenAIClientConfig()
        self.client = OpenAI(
            api_key=self.cfg.api_key or os.getenv("OPENAI_API_KEY"),
            base_url=self.cfg.base_url or os.getenv("OPENAI_BASE_URL"),
        )

    def generate(self, prompt: str) -> str:

        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
        )
        return resp.choices[0].message.content


if __name__ == "__main__":
    client = OpenAILLMClient()

    response = client.generate("告诉我你是那个公司的那款模型,你的模型具体型号是什么？")
    print(response)
