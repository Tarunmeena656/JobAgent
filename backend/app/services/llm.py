import json
from dataclasses import dataclass
from functools import lru_cache

from .. import config


@dataclass
class LLMResult:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    model: str = ""


class LLMProvider:
    name = "none"
    enabled = False

    def complete(self, system: str, prompt: str, max_tokens: int = 800) -> LLMResult:
        raise NotImplementedError

    def complete_json(self, system: str, prompt: str, max_tokens: int = 1200) -> tuple[dict | None, LLMResult]:
        result = self.complete(system + "\nAnswer with a single JSON object and nothing else.", prompt, max_tokens)
        text = result.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[text.find("{") :]
        try:
            return json.loads(text), result
        except json.JSONDecodeError:
            return None, result


class MockProvider(LLMProvider):
    """No model: callers fall back to their template or rule based output."""

    name = "mock"
    enabled = False

    def complete(self, system: str, prompt: str, max_tokens: int = 800) -> LLMResult:
        return LLMResult(text="", model="mock")


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    enabled = True

    def __init__(self) -> None:
        from anthropic import Anthropic

        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.model = config.LLM_MODEL
        self.price_in = float(config.env("LLM_PRICE_IN_PER_MTOK", "0"))
        self.price_out = float(config.env("LLM_PRICE_OUT_PER_MTOK", "0"))

    def complete(self, system: str, prompt: str, max_tokens: int = 800) -> LLMResult:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
        tokens_in = message.usage.input_tokens
        tokens_out = message.usage.output_tokens
        cost = (tokens_in * self.price_in + tokens_out * self.price_out) / 1_000_000
        return LLMResult(text=text, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost, model=self.model)


@lru_cache(maxsize=1)
def get_llm() -> LLMProvider:
    if config.LLM_PROVIDER == "anthropic" and config.ANTHROPIC_API_KEY:
        return AnthropicProvider()
    return MockProvider()
