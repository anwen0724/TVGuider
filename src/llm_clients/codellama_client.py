from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import os

from openai import OpenAI

from dotenv import load_dotenv

load_dotenv()


@dataclass
class CodeLlamaClientConfig:
    model: str = "meta-llama/CodeLlama-70b-Instruct-hf"
    temperature: float = 0.2
    max_tokens: int = 1200
    api_key: Optional[str] = None
    base_url: str = "https://api.together.xyz/v1"
    api_key_env: str = "CODELLAMA_API_KEY"


class CodeLlamaLLMClient:
    name: str = "codellama"

    def __init__(self, cfg: Optional[CodeLlamaClientConfig] = None):
        self.cfg = cfg or CodeLlamaClientConfig()
        self.client = OpenAI(
            api_key=self.cfg.api_key or os.getenv(self.cfg.api_key_env),
            base_url=self.cfg.base_url,
        )

    def generate(self, prompt: str) -> str:

        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
        )
        return resp.choices[0].message.content or ""


if __name__ == "__main__":
    client = CodeLlamaLLMClient()

    response = client.generate("写一个 Python 快速排序函数")
    print(response)
