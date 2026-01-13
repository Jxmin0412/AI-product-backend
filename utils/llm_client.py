"""
LLM Client - Supports multiple providers (Groq, HuggingFace, OpenAI-compatible)
Groq is the default - fast and free.
"""
import logging
import json
from typing import Optional, Dict, Any, List
from enum import Enum
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    GROQ = "groq"
    HUGGINGFACE = "huggingface"
    OPENAI = "openai"  # Or any OpenAI-compatible API


class LLMClient:
    """
    Unified LLM client supporting multiple providers.
    Default: Groq (fast, free tier available)
    """

    # Groq API settings
    GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    # Default models per provider
    DEFAULT_MODELS = {
        LLMProvider.GROQ: "mixtral-8x7b-32768",  # Fast, good quality
        LLMProvider.HUGGINGFACE: "mistralai/Mistral-7B-Instruct-v0.3",
        LLMProvider.OPENAI: "gpt-3.5-turbo",
    }

    # Available Groq models (all free)
    GROQ_MODELS = {
        "mixtral-8x7b-32768": "Mixtral 8x7B - Best quality",
        "llama-3.1-70b-versatile": "Llama 3.1 70B - Very capable",
        "llama-3.1-8b-instant": "Llama 3.1 8B - Fast",
        "gemma2-9b-it": "Gemma 2 9B - Google's model",
    }

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
        max_tokens: int = 256,
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
        if self.provider == LLMProvider.GROQ:
            return await self._generate_groq(prompt, system_prompt, max_tokens, temperature)
        elif self.provider == LLMProvider.HUGGINGFACE:
            return await self._generate_huggingface(prompt, max_tokens, temperature)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def _generate_groq(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> str:
        """Generate using Groq API (OpenAI-compatible)."""
        try:
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

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.GROQ_BASE_URL,
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
        max_tokens: int,
        temperature: float
    ) -> str:
        """Generate using HuggingFace Inference API."""
        try:
            # Format prompt for Mistral
            formatted_prompt = f"<s>[INST] {prompt} [/INST]"

            payload = {
                "inputs": formatted_prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                    "return_full_text": False,
                }
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            url = f"https://api-inference.huggingface.co/models/{self.model}"

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()

                if isinstance(result, list) and len(result) > 0:
                    return result[0].get("generated_text", "").strip()

                return ""

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
    Reads configuration from environment variables.
    """
    global _llm_client

    if _llm_client is None:
        import os

        # Check for Groq first (preferred)
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            _llm_client = LLMClient(
                provider=LLMProvider.GROQ,
                api_key=groq_key,
                model=os.getenv("GROQ_MODEL", "mixtral-8x7b-32768")
            )
        else:
            # Fallback to HuggingFace
            hf_key = os.getenv("HUGGINGFACE_API_KEY")
            _llm_client = LLMClient(
                provider=LLMProvider.HUGGINGFACE,
                api_key=hf_key,
                model=os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
            )

    return _llm_client


def init_llm_client(
    provider: LLMProvider = LLMProvider.GROQ,
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
