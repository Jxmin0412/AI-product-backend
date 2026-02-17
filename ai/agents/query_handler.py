"""
Agent 1: Query Handler Agent
Extracts structured information from natural language queries using LLM.
Falls back to rule-based extraction if LLM fails.
"""
import json
import re
import logging
from typing import Optional, Dict, Any, List, Tuple

from ai.agents.base import BaseAgent, AgentState
from ai.prompts import QUERY_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


class QueryHandlerAgent(BaseAgent):
    """
    Processes user queries and extracts structured search parameters.
    Uses LLM for intelligent extraction with rule-based fallback.
    """

    # Category mappings for rule-based fallback
    CATEGORY_KEYWORDS = {
        "Computers": ["laptop", "notebook", "macbook", "thinkpad", "chromebook", "desktop", "pc", "computer"],
        "Smartphones": ["phone", "smartphone", "mobile", "iphone", "android", "pixel", "galaxy"],
        "Audio": ["headphone", "earphone", "speaker", "airpods", "buds", "earbuds", "soundbar", "audio"],
        "Electronics": ["tv", "television", "monitor", "camera", "tablet", "ipad", "kindle", "watch", "smartwatch"],
        "Home": ["appliance", "vacuum", "refrigerator", "microwave", "washer", "dryer", "furniture"],
        "Fashion": ["shirt", "pants", "dress", "shoes", "jacket", "clothing", "wear"],
    }

    # Brand detection patterns
    KNOWN_BRANDS = [
        "apple", "samsung", "sony", "lg", "dell", "hp", "lenovo", "asus", "acer",
        "microsoft", "google", "oneplus", "xiaomi", "bose", "jbl", "sennheiser",
        "nike", "adidas", "bosch", "philips", "panasonic", "canon", "nikon"
    ]

    def __init__(self):
        super().__init__(name="QueryHandler")

    async def process(self, state: AgentState) -> AgentState:
        """
        Extract product name, category, price range, features from user query.
        Uses LLM first, falls back to rule-based extraction on failure.
        """
        self.log_start(state)

        try:
            query = state.user_query

            # Try LLM extraction first
            extracted = await self._extract_with_llm(query)

            if extracted:
                state.extracted_product_name = extracted.get("product_type", query)
                state.extracted_category = extracted.get("category", "All")
                state.extracted_brand = extracted.get("brand")
                state.extracted_features = extracted.get("features", [])
                state.query_intent = extracted.get("intent", "product_search")

                min_price = extracted.get("min_price")
                max_price = extracted.get("max_price")
                state.extracted_price_range = (min_price, max_price)

                logger.info(f"LLM extraction successful for: {query[:50]}")
            else:
                logger.info(f"Falling back to rule-based extraction for: {query[:50]}")
                await self._extract_rule_based(state)

            self._log_extraction_results(state)

        except Exception as e:
            self.log_error(e, state)
            await self._extract_rule_based(state)

        self.log_end(state)
        return state

    async def _extract_with_llm(self, query: str) -> Optional[Dict[str, Any]]:
        """Extract structured info using LLM. Returns None if extraction fails."""
        try:
            prompt = QUERY_EXTRACTION_PROMPT.format(query=query)

            response = await self.generate_text(
                prompt=prompt,
                max_tokens=200,
                temperature=0.1
            )

            if not response:
                return None

            return self._parse_json_response(response)

        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return None

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LLM response, handling common formatting issues."""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        try:
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

        logger.warning(f"Failed to parse JSON from: {response[:100]}")
        return None

    async def _extract_rule_based(self, state: AgentState) -> None:
        """Fallback rule-based extraction using keywords and regex."""
        query = state.user_query.lower()

        state.extracted_category = self._extract_category(query)
        state.extracted_price_range = self._extract_price_range(query)
        state.extracted_brand = self._extract_brand(query)
        state.extracted_features = self._extract_features(query)
        state.query_intent = self._determine_intent(query, state.mode)
        state.extracted_product_name = self._clean_product_name(state.user_query)

    def _extract_category(self, query: str) -> str:
        """Extract product category from query using keyword matching."""
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(keyword in query for keyword in keywords):
                return category
        return "All"

    def _extract_price_range(self, query: str) -> Tuple[Optional[float], Optional[float]]:
        """Extract price range from query using regex patterns."""
        patterns = [
            (r"(?:under|below|less than|up to|max|maximum)\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)", None, 1),
            (r"(?:over|above|more than|min|minimum|at least)\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)", 1, None),
            (r"\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:-|to|and)\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)", 1, 2),
            (r"(?:around|about|approximately|~)\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)", "around", "around"),
        ]

        for pattern, min_group, max_group in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                if min_group == "around" and max_group == "around":
                    price = float(match.group(1).replace(",", ""))
                    return (price * 0.8, price * 1.2)
                elif min_group is None:
                    return (None, float(match.group(max_group).replace(",", "")))
                elif max_group is None:
                    return (float(match.group(min_group).replace(",", "")), None)
                else:
                    return (
                        float(match.group(min_group).replace(",", "")),
                        float(match.group(max_group).replace(",", ""))
                    )

        return (None, None)

    def _extract_brand(self, query: str) -> Optional[str]:
        """Extract brand name from query."""
        for brand in self.KNOWN_BRANDS:
            if brand in query:
                return brand.capitalize()
        return None

    def _extract_features(self, query: str) -> List[str]:
        """Extract product features/requirements from query."""
        features = []

        ram_match = re.search(r"(\d+)\s*gb\s*ram", query)
        if ram_match:
            features.append(f"{ram_match.group(1)}GB RAM")

        storage_match = re.search(r"(\d+)\s*(gb|tb)\s*(?:storage|ssd|hdd)", query)
        if storage_match:
            features.append(f"{storage_match.group(1)}{storage_match.group(2).upper()} Storage")

        screen_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:inch|\")", query)
        if screen_match:
            features.append(f"{screen_match.group(1)} inch")

        feature_keywords = [
            "gaming", "professional", "budget", "premium", "wireless", "bluetooth",
            "noise cancelling", "waterproof", "portable", "lightweight", "fast charging",
            "4k", "hdr", "oled", "amoled", "retina", "touchscreen"
        ]
        for keyword in feature_keywords:
            if keyword in query:
                features.append(keyword.title())

        return features

    def _determine_intent(self, query: str, mode: str) -> str:
        """Determine user intent from query."""
        if mode == "business":
            if any(word in query for word in ["trend", "trending", "popular"]):
                return "market_analysis"
            elif any(word in query for word in ["competitor", "competition", "versus"]):
                return "competitive_analysis"
            return "business_intelligence"

        if any(word in query for word in ["compare", "comparison", "vs", "versus", "or"]):
            return "price_comparison"
        elif any(word in query for word in ["best", "recommend", "suggest", "top", "good"]):
            return "recommendation"
        return "product_search"

    def _clean_product_name(self, query: str) -> str:
        """Clean query to extract product name."""
        cleaned = re.sub(
            r"(?:under|below|above|over|between|around|less than|more than)\s*\$?\s*\d+(?:,\d{3})*(?:\.\d{2})?(?:\s*(?:and|to|-)\s*\$?\s*\d+(?:,\d{3})*(?:\.\d{2})?)?",
            "",
            query,
            flags=re.IGNORECASE
        )
        cleaned = re.sub(r"\b(?:find|search|show|get|looking for|i want|i need|a|an|the)\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = " ".join(cleaned.split())
        return cleaned.strip() or query

    def _log_extraction_results(self, state: AgentState) -> None:
        """Log extraction results for debugging."""
        logger.info(
            f"Extracted - Product: {state.extracted_product_name}, "
            f"Category: {state.extracted_category}, "
            f"Brand: {state.extracted_brand}, "
            f"Price: {state.extracted_price_range}, "
            f"Features: {state.extracted_features}, "
            f"Intent: {state.query_intent}"
        )
