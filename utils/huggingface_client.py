"""
Hugging Face API client for LLM inference.
Provides wrapper for Hugging Face Inference API with retry logic and error handling.
"""
import logging
from typing import Optional, Dict, Any, List
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

logger = logging.getLogger(__name__)


class HuggingFaceClient:
    """
    Client for interacting with Hugging Face Inference API.
    Supports text generation, embeddings, and classification tasks.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize Hugging Face client.

        Args:
            api_key: Hugging Face API key (defaults to settings)
            model: Model name/ID (defaults to settings)
        """
        self.api_key = api_key or settings.HUGGINGFACE_API_KEY
        self.model = model or settings.HUGGINGFACE_MODEL
        self.base_url = "https://api-inference.huggingface.co/models"

        if not self.api_key:
            logger.warning("Hugging Face API key not set. Inference will fail.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        logger.info(f"Hugging Face client initialized with model: {self.model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
        **kwargs
    ) -> str:
        """
        Generate text using Hugging Face Inference API.

        Args:
            prompt: Input prompt for text generation
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 1.0)
            top_p: Nucleus sampling parameter
            **kwargs: Additional model parameters

        Returns:
            str: Generated text

        Raises:
            Exception: If API call fails after retries
        """
        try:
            logger.debug(f"Generating text for prompt: {prompt[:100]}...")

            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                    "return_full_text": False,
                    **kwargs
                }
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/{self.model}",
                    headers=self.headers,
                    json=payload
                )

                response.raise_for_status()
                result = response.json()

                # Handle different response formats
                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get("generated_text", "")
                elif isinstance(result, dict):
                    generated_text = result.get("generated_text", "")
                else:
                    generated_text = str(result)

                logger.debug(f"Generated text: {generated_text[:100]}...")
                return generated_text.strip()

        except httpx.HTTPStatusError as e:
            logger.error(f"Hugging Face API HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Text generation error: {e}", exc_info=True)
            raise

    async def extract_structured_info(
        self,
        text: str,
        extraction_prompt: str
    ) -> str:
        """
        Extract structured information from text using LLM.

        Args:
            text: Input text to analyze
            extraction_prompt: Prompt describing what to extract

        Returns:
            str: Extracted information
        """
        prompt = f"""{extraction_prompt}

Input: {text}

Output:"""

        return await self.generate_text(
            prompt=prompt,
            max_tokens=200,
            temperature=0.3  # Lower temperature for more deterministic extraction
        )

    async def classify_text(
        self,
        text: str,
        labels: List[str]
    ) -> Dict[str, float]:
        """
        Classify text into predefined categories.

        Args:
            text: Text to classify
            labels: List of possible labels

        Returns:
            Dict[str, float]: Label to score mapping
        """
        try:
            # Use zero-shot classification endpoint
            url = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"

            payload = {
                "inputs": text,
                "parameters": {"candidate_labels": labels}
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload
                )

                response.raise_for_status()
                result = response.json()

                # Convert to dict
                scores = {}
                if "labels" in result and "scores" in result:
                    scores = dict(zip(result["labels"], result["scores"]))

                return scores

        except Exception as e:
            logger.error(f"Classification error: {e}", exc_info=True)
            return {label: 0.0 for label in labels}

    async def health_check(self) -> bool:
        """
        Check if Hugging Face API is accessible.

        Returns:
            bool: True if API is accessible, False otherwise
        """
        try:
            test_result = await self.generate_text(
                prompt="Hello, world!",
                max_tokens=10
            )
            return bool(test_result)
        except Exception as e:
            logger.error(f"Hugging Face health check failed: {e}")
            return False

    def __repr__(self):
        return f"<HuggingFaceClient(model='{self.model}')>"


# Global client instance
_hf_client: Optional[HuggingFaceClient] = None


def get_huggingface_client() -> HuggingFaceClient:
    """
    Get or create global Hugging Face client instance.

    Returns:
        HuggingFaceClient: Global client instance
    """
    global _hf_client

    if _hf_client is None:
        _hf_client = HuggingFaceClient()

    return _hf_client
