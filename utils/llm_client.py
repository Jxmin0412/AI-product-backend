"""
LLM Client - Supports multiple providers (HuggingFace, Groq, OpenAI-compatible)
HuggingFace is the default - uses OpenAI-compatible router endpoint.
"""
import logging
import json
import os
from typing import Optional, Dict, Any
from enum import Enum
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    HUGGINGFACE = "huggingface"
    GROQ = "groq"
    OPENAI = "openai"


class LLMClient:
    """
    Unified LLM client supporting multiple providers.
    Default: HuggingFace (OpenAI-compatible router endpoint)
    """

    # Default models per provider
    DEFAULT_MODELS = {
        LLMProvider.HUGGINGFACE: "meta-llama/Llama-3.1-8B-Instruct:novita",
        LLMProvider.GROQ: "llama-3.3-70b-versatile",
        LLMProvider.OPENAI: "gpt-3.5-turbo",
    }

    # Available HuggingFace models via router
    HUGGINGFACE_MODELS = {
        "meta-llama/Llama-3.1-8B-Instruct:novita": "Llama 3.1 8B - Fast and capable",
        "meta-llama/Llama-3.1-70B-Instruct:novita": "Llama 3.1 70B - Most capable",
    }

    # Available Groq models (all free)
    GROQ_MODELS = {
        "llama-3.3-70b-versatile": "Llama 3.3 70B - Latest, most capable",
        "llama-3.1-70b-versatile": "Llama 3.1 70B - Very capable",
        "llama-3.1-8b-instant": "Llama 3.1 8B - Fast",
        "mixtral-8x7b-32768": "Mixtral 8x7B - Good quality",
        "gemma2-9b-it": "Gemma 2 9B - Google's model",
    }

    # API endpoints
    HUGGINGFACE_API_URL = "https://router.huggingface.co/v1/chat/completions"
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(
        self,
        provider: LLMProvider = LLMProvider.GROQ,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize LLM client.

        Args:
            provider: LLM provider to use
            api_key: API key for the provider
            model: Model name (uses default if not specified)
        """
        self.provider = provider
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODELS.get(provider)

        if not self.api_key:
            logger.warning(f"No API key provided for {provider.value}. LLM calls will fail.")
        else:
            logger.info(f"LLM Client initialized: provider={provider.value}, model={self.model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """
        Generate text using the configured LLM provider.

        Args:
            prompt: User prompt/instruction
            system_prompt: Optional system prompt for context
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 1.0)

        Returns:
            Generated text string
        """
        if self.provider == LLMProvider.HUGGINGFACE:
            return await self._generate_huggingface(prompt, system_prompt, max_tokens, temperature)
        elif self.provider == LLMProvider.GROQ:
            return await self._generate_groq(prompt, system_prompt, max_tokens, temperature)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def _generate_groq(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> str:
        """Generate using Groq API via httpx (no SDK required)."""
        try:
            if not self.api_key:
                raise ValueError("Groq API key not set. Check GROQ_API_KEY in .env")

            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.GROQ_API_URL,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

                # Extract generated text
                generated = result["choices"][0]["message"]["content"]

                logger.debug(f"Groq response: {generated[:100]}...")
                return generated.strip()

        except httpx.HTTPStatusError as e:
            logger.error(f"Groq API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Groq generation error: {e}")
            raise

    async def _generate_huggingface(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> str:
        """Generate using HuggingFace OpenAI-compatible router API."""
        try:
            if not self.api_key:
                raise ValueError("HuggingFace API key not set. Check HUGGINGFACE_API_KEY in .env")

            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.HUGGINGFACE_API_URL,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

                # Extract generated text (OpenAI-compatible format)
                generated = result["choices"][0]["message"]["content"]

                logger.debug(f"HuggingFace response: {generated[:100]}...")
                return generated.strip()

        except httpx.HTTPStatusError as e:
            logger.error(f"HuggingFace API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"HuggingFace generation error: {e}")
            raise

    async def extract_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate and parse JSON response.

        Args:
            prompt: Prompt that should return JSON
            system_prompt: Optional system context

        Returns:
            Parsed JSON dict or None if parsing fails
        """
        # Add JSON instruction to system prompt
        json_system = (system_prompt or "") + "\nRespond ONLY with valid JSON, no other text."

        response = await self.generate(
            prompt=prompt,
            system_prompt=json_system,
            temperature=0.1  # Low temperature for consistent output
        )

        return self._parse_json(response)

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from text, handling common issues."""
        if not text:
            return None

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from response
        import re
        try:
            # Find JSON object in text
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

        # Try to find JSON array
        try:
            match = re.search(r'\[[^\[\]]*\]', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

        logger.warning(f"Failed to parse JSON from: {text[:200]}")
        return None

    async def health_check(self) -> bool:
        """Check if the LLM API is accessible."""
        try:
            response = await self.generate(
                prompt="Say 'ok'",
                max_tokens=10
            )
            return bool(response)
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return False


# ============================================
# Global Client Instance
# ============================================

_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """
    Get or create global LLM client instance.
    Reads configuration from settings (which loads from .env file).
    """
    global _llm_client

    if _llm_client is None:
        # Ensure .env is loaded
        import os
        from pathlib import Path

        # Try to load .env directly if settings didn't load it
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path)
                logger.info(f"Loaded .env from {env_path}")
            except ImportError:
                pass

        # Now import settings
        from config.settings import settings

        # Debug: log what we found
        hf_key = settings.HUGGINGFACE_API_KEY or os.getenv("HUGGINGFACE_API_KEY", "")
        groq_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")

        logger.info(f"HUGGINGFACE_API_KEY present: {bool(hf_key)} (length: {len(hf_key) if hf_key else 0})")
        logger.info(f"GROQ_API_KEY present: {bool(groq_key)}")

        # Check for HuggingFace first (preferred - uses OpenAI-compatible router)
        if hf_key:
            model = settings.HUGGINGFACE_MODEL or os.getenv("HUGGINGFACE_MODEL", "meta-llama/Llama-3.1-8B-Instruct:novita")
            logger.info(f"Initializing HuggingFace LLM client with model: {model}")
            _llm_client = LLMClient(
                provider=LLMProvider.HUGGINGFACE,
                api_key=hf_key,
                model=model
            )
        elif groq_key:
            # Fallback to Groq
            model = settings.GROQ_MODEL or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            logger.info(f"Initializing Groq LLM client with model: {model}")
            _llm_client = LLMClient(
                provider=LLMProvider.GROQ,
                api_key=groq_key,
                model=model
            )
        else:
            logger.error("No LLM API key found! Set HUGGINGFACE_API_KEY or GROQ_API_KEY in .env")
            # Create a client anyway (will fail on use but won't crash)
            _llm_client = LLMClient(
                provider=LLMProvider.HUGGINGFACE,
                api_key="",
                model="meta-llama/Llama-3.1-8B-Instruct:novita"
            )

    return _llm_client


def init_llm_client(
    provider: LLMProvider = LLMProvider.HUGGINGFACE,
    api_key: str = None,
    model: str = None
) -> LLMClient:
    """
    Initialize global LLM client with specific settings.
    Call this at app startup if you want custom configuration.
    """
    global _llm_client
    _llm_client = LLMClient(provider=provider, api_key=api_key, model=model)
    return _llm_client
