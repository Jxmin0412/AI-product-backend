"""
LLM Client — Supports multiple providers (Groq, HuggingFace, OpenAI-compatible).
Groq is the default primary provider. Falls back to the secondary on connection errors.
"""
import logging
import json
import re
from typing import Optional, Any
from enum import Enum
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    HUGGINGFACE = "huggingface"
    GROQ = "groq"


API_URLS = {
    LLMProvider.HUGGINGFACE: "https://router.huggingface.co/v1/chat/completions",
    LLMProvider.GROQ: "https://api.groq.com/openai/v1/chat/completions",
}

DEFAULT_MODELS = {
    LLMProvider.HUGGINGFACE: "meta-llama/Llama-3.1-8B-Instruct:novita",
    LLMProvider.GROQ: "llama-3.3-70b-versatile",
}


class LLMClient:
    """
    Unified LLM client with automatic provider fallback.

    If the primary provider fails with a connection error, retries with the
    fallback provider (if configured). API errors (4xx/5xx) are NOT retried
    on the fallback since they indicate prompt/auth issues, not connectivity.
    """

    def __init__(self, providers: list[dict]):
        """
        providers: ordered list of {"provider": LLMProvider, "api_key": str, "model": str}
        First entry is primary, rest are fallbacks.
        """
        self.providers = providers
        self.provider = providers[0]["provider"]  # for backward compat
        self.model = providers[0]["model"]

        for p in providers:
            if p["api_key"]:
                logger.info(f"LLM provider configured: {p['provider'].value} ({p['model']})")
            else:
                logger.warning(f"No API key for {p['provider'].value} — will skip as fallback")

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
    async def _call_provider(self, provider_config: dict, messages: list, max_tokens: int, temperature: float) -> str:
        """Call a single provider with retry on transient errors."""
        provider = provider_config["provider"]
        api_key = provider_config["api_key"]
        model = provider_config["model"]
        api_url = API_URLS[provider]

        if not api_key:
            raise ValueError(f"{provider.value} API key not set.")

        payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            generated = result["choices"][0]["message"]["content"]
            logger.debug(f"{provider.value} response: {generated[:100]}...")
            return generated.strip()

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024, temperature: float = 0.7, **kwargs) -> str:
        """Generate text. Tries primary provider, falls back on connection errors."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_error = None
        for i, provider_config in enumerate(self.providers):
            if not provider_config["api_key"]:
                continue
            try:
                return await self._call_provider(provider_config, messages, max_tokens, temperature)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                logger.error(f"{provider_config['provider'].value} API error: {status} - {e.response.text[:200]}")
                # Rate limit (429) or server error (5xx) — try fallback provider
                if status in (429, 500, 502, 503, 529):
                    last_error = e
                    if i < len(self.providers) - 1:
                        logger.info(f"Falling back to {self.providers[i + 1]['provider'].value} (HTTP {status})")
                    continue
                # Auth/client errors (401, 400, etc.) — raise immediately
                raise
            except Exception as e:
                # Connection errors — log and try next provider
                last_error = e
                logger.warning(f"{provider_config['provider'].value} failed: {e}")
                if i < len(self.providers) - 1:
                    next_provider = self.providers[i + 1]["provider"].value
                    logger.info(f"Falling back to {next_provider}")

        raise last_error or RuntimeError("No LLM providers available")

    async def extract_json(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[Any]:
        """Generate and parse JSON response. Returns dict, list, or None."""
        json_system = (system_prompt or "") + "\nRespond ONLY with valid JSON, no other text."
        response = await self.generate(prompt=prompt, system_prompt=json_system, temperature=0.1)
        return self._parse_json(response)

    def _parse_json(self, text: str) -> Optional[Any]:
        """Parse JSON from text, handling common LLM output issues."""
        if not text:
            return None

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code fence
        fence_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text)
        if fence_match:
            try:
                return json.loads(fence_match.group(1))
            except json.JSONDecodeError:
                pass

        # Find first { or [ and match to closing bracket (supports nesting)
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            start_idx = text.find(start_char)
            if start_idx == -1:
                continue
            depth = 0
            for i in range(start_idx, len(text)):
                if text[i] == start_char:
                    depth += 1
                elif text[i] == end_char:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start_idx:i + 1])
                        except json.JSONDecodeError:
                            break

        logger.warning(f"Failed to parse JSON from: {text[:200]}")
        return None

    async def health_check(self) -> bool:
        try:
            response = await self.generate(prompt="Say 'ok'", max_tokens=10)
            return bool(response)
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return False


# Global Client Instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create global LLM client with provider fallback chain."""
    global _llm_client

    if _llm_client is None:
        from config.settings import settings

        providers = []

        if settings.GROQ_API_KEY:
            providers.append({
                "provider": LLMProvider.GROQ,
                "api_key": settings.GROQ_API_KEY,
                "model": settings.GROQ_MODEL,
            })

        if settings.HUGGINGFACE_API_KEY:
            providers.append({
                "provider": LLMProvider.HUGGINGFACE,
                "api_key": settings.HUGGINGFACE_API_KEY,
                "model": settings.HUGGINGFACE_MODEL,
            })

        if not providers:
            logger.error("No LLM API key found! Set GROQ_API_KEY or HUGGINGFACE_API_KEY in .env")
            providers.append({
                "provider": LLMProvider.GROQ,
                "api_key": "",
                "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            })

        _llm_client = LLMClient(providers=providers)

    return _llm_client
