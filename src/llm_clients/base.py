from typing import Protocol


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str: ...

    def generate_response(self, prompt: str) -> dict: ...
