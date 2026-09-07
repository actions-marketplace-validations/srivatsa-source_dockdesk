import os
import time
from typing import Any, Optional

class BaseProvider:
    def complete(self, messages: list, temperature: float, max_tokens: int) -> str:
        raise NotImplementedError()
    def get_llm(self, model: str, temperature: float, num_predict: int, num_ctx: int) -> Any:
        raise NotImplementedError()

class OllamaProvider(BaseProvider):
    def __init__(self, pool=None):
        self.pool = pool

    def get_llm(self, model: str, temperature: float, num_predict: int, num_ctx: int) -> Any:
        from langchain_ollama import ChatOllama
        if self.pool:
            return self.pool.get_llm(model=model, temperature=temperature, num_predict=num_predict, num_ctx=num_ctx)
        return ChatOllama(model=model, temperature=temperature, num_predict=num_predict, num_ctx=num_ctx)

    def complete(self, messages: list, temperature: float, max_tokens: int) -> str:
        # Not used by Ollama because we use get_llm directly
        pass

class OpenAIProvider(BaseProvider):
    def __init__(self):
        import openai
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY not set in environment.")
        self.client = openai.OpenAI()

    def complete(self, model: str, messages: list, temperature: float, max_tokens: int) -> str:
        # messages is expected to be [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        max_attempts = 3
        attempts = 0
        last_err = None
        while attempts < max_attempts:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content
            except Exception as e:
                attempts += 1
                last_err = e
                if attempts < max_attempts:
                    time.sleep(2 ** attempts)
        raise last_err

class AnthropicProvider(BaseProvider):
    def __init__(self):
        import anthropic
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY not set in environment.")
        self.client = anthropic.Anthropic()

    def complete(self, model: str, messages: list, temperature: float, max_tokens: int) -> str:
        system_prompt = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                user_messages.append(msg)

        max_attempts = 3
        attempts = 0
        last_err = None
        while attempts < max_attempts:
            try:
                response = self.client.messages.create(
                    model=model,
                    system=system_prompt,
                    messages=user_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.content[0].text
            except Exception as e:
                attempts += 1
                last_err = e
                if attempts < max_attempts:
                    time.sleep(2 ** attempts)
        raise last_err

def get_provider(provider_name: str, pool: Optional[Any] = None) -> BaseProvider:
    provider_name = provider_name.lower()
    if provider_name == "openai":
        return OpenAIProvider()
    elif provider_name == "anthropic":
        return AnthropicProvider()
    elif provider_name == "ollama":
        return OllamaProvider(pool=pool)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
