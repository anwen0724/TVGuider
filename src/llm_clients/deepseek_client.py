from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from .responses import openai_response

load_dotenv()


@dataclass
class DeepSeekClientConfig:
    model: str = "deepseek-flash"
    temperature: float = 0.2
    max_tokens: int = 32768
    api_key: str | None = None
    base_url: str | None = None


class DeepSeekLLMClient:
    def __init__(self, cfg: DeepSeekClientConfig | None = None):
        self.cfg = cfg or DeepSeekClientConfig()
        self.client = OpenAI(
            api_key=self.cfg.api_key or os.getenv("DEEPSEEK_API_KEY"),
            base_url=self.cfg.base_url or os.getenv("DEEPSEEK_BASE_URL"),
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
        return openai_response(resp)


if __name__ == "__main__":
    client = DeepSeekLLMClient()

    response = client.generate("告诉我你是那个公司的那款模型,你的模型具体型号是什么？")
    print(response)
