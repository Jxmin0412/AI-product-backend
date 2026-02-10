"""
Thin LLM client — works with any OpenAI-compatible endpoint.
Configure via .env:  LLM_API_KEY, LLM_API_URL, LLM_MODEL
"""
import json
import re
import logging
from typing import Optional, Dict, Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from utils.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)


class LLMClient:
    """OpenAI-compatible chat completions client (HuggingFace, Groq, etc.)."""

    def __init__(self, api_key: str, api_url: str, model: str):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self._rate_limiter = TokenBucketRateLimiter(
            rate=settings.LLM_RATE_LIMIT,
            burst=settings.LLM_BURST_LIMIT,
            per_seconds=60,
        )
        if not self.api_key:
            logger.warning("LLM_API_KEY is empty — LLM calls will fail")
        else:
            logger.info(f"LLM client ready: model={self.model}, url={self.api_url}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """Send a chat completion request and return the generated text."""
        await self._rate_limiter.acquire()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()

    async def extract_json(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate a response and parse it as JSON."""
        json_system = (system_prompt or "") + "\nRespond ONLY with valid JSON, no other text."
        text = await self.generate(prompt, system_prompt=json_system, temperature=0.1)
        return self._parse_json(text)

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Extract first JSON object or array from surrounding text
        for pattern in (r"\{.*\}", r"\[.*\]"):
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    continue
        logger.warning(f"Failed to parse JSON from LLM response: {text[:200]}")
        return None

    def __repr__(self) -> str:
        return f"<LLMClient model={self.model!r}>"


# --------------- singleton ---------------

_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the global LLM client (reads from settings)."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient(
            api_key=settings.LLM_API_KEY,
            api_url=settings.LLM_API_URL,
            model=settings.LLM_MODEL,
        )
    return _llm_client
