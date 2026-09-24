from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import os

from openai import OpenAI

from dotenv import load_dotenv

load_dotenv()


@dataclass
class QwenClientConfig:
    model: str = "qwen3-max"
    temperature: float = 0.2
    max_tokens: int = 8192
    api_key: Optional[str] = None
    base_url: str = None
    api_key_env: str = None


class QwenLLMClient:
    name: str = "qwen"

    def __init__(self, cfg: Optional[QwenClientConfig] = None):
        self.cfg = cfg or QwenClientConfig()
        self.client = OpenAI(
            api_key=self.cfg.api_key or os.getenv("QWEN_API_KEY"),
            base_url=self.cfg.base_url or os.getenv("QWEN_BASE_URL"),
        )
        print("QWEN_API_KEY =", os.getenv("QWEN_API_KEY"))
        print("QWEN_BASE_URL =", os.getenv("QWEN_BASE_URL"))

    def generate(self, prompt: str) -> str:

        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
        )
        return resp.choices[0].message.content or ""


if __name__ == "__main__":
    client = QwenLLMClient()

    response = client.generate("告诉我你是那个公司的那款模型,你的模型具体型号是什么？")
    print(response)
