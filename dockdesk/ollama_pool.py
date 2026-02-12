"""
OllamaPool — Distributed Ollama inference across multiple endpoints.

Supports round-robin load distribution across N Ollama instances.
Falls back to single localhost if no URLs configured.

Usage:
    pool = OllamaPool(["http://gpu1:11434", "http://gpu2:11434"])
    llm = pool.get_llm(model="qwen2.5-coder:3b", temperature=0.1, num_predict=512)
"""

import os
import itertools
import threading
from typing import List, Optional
from rich.console import Console
from langchain_ollama import ChatOllama

console = Console()

DEFAULT_OLLAMA_URL = "http://localhost:11434"


class OllamaPool:
    """Round-robin pool of Ollama endpoints for distributed inference."""

    def __init__(self, urls: Optional[List[str]] = None):
        """
        Args:
            urls: List of Ollama base URLs. If None, reads from OLLAMA_URLS env
                  or falls back to localhost:11434.
        """
        if urls is None:
            env_urls = os.environ.get("OLLAMA_URLS", "")
            if env_urls:
                urls = [u.strip() for u in env_urls.split(",") if u.strip()]
            else:
                # Single default
                urls = [os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_URL)]

        self._urls = urls or [DEFAULT_OLLAMA_URL]
        self._cycle = itertools.cycle(self._urls)
        self._lock = threading.Lock()
        self._healthy: List[str] = list(self._urls)  # assume all healthy initially

    @property
    def size(self) -> int:
        return len(self._healthy)

    @property
    def urls(self) -> List[str]:
        return list(self._urls)

    def _next_url(self) -> str:
        """Thread-safe round-robin URL selection."""
        with self._lock:
            return next(self._cycle)

    def health_check(self) -> List[str]:
        """
        Quick health check — ping each endpoint.
        Returns list of healthy URLs.
        """
        import requests
        healthy = []
        for url in self._urls:
            try:
                resp = requests.get(f"{url}/api/tags", timeout=3)
                if resp.status_code == 200:
                    healthy.append(url)
            except Exception:
                console.print(f"[yellow]⚠ Ollama endpoint unreachable: {url}[/yellow]")
        self._healthy = healthy if healthy else self._urls  # fallback to all if none responded
        return self._healthy

    def get_llm(
        self,
        model: str,
        temperature: float = 0.1,
        num_predict: int = 512,
        num_ctx: int = 2048,
        **kwargs,
    ) -> ChatOllama:
        """
        Get a ChatOllama instance pointed at the next available endpoint.
        Thread-safe — can be called from multiple workers simultaneously.
        """
        url = self._next_url()
        return ChatOllama(
            model=model,
            temperature=temperature,
            num_predict=num_predict,
            num_ctx=num_ctx,
            base_url=url,
            **kwargs,
        )

    def optimal_workers(self, base: int = 2) -> int:
        """
        Suggest optimal worker count based on pool size.
        Each Ollama instance can handle ~1-2 concurrent requests efficiently.
        """
        return max(base, self.size * 2)

    def __repr__(self) -> str:
        return f"OllamaPool({len(self._urls)} endpoints: {', '.join(self._urls)})"
