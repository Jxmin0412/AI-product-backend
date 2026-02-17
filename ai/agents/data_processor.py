"""
Agent 3: Data Processor Agent
Cleans, normalizes, and deduplicates product data from multiple platforms.
"""
import re
import math
import logging
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher

from ai.agents.base import BaseAgent, AgentState

logger = logging.getLogger(__name__)


class DataProcessorAgent(BaseAgent):
    """
    Processes raw product data: cleaning, normalization, deduplication.
    Handles data from multiple platforms with different formats.
    """

    SIMILARITY_THRESHOLD = 0.85

    NOISE_WORDS = [
        "new", "latest", "best", "top", "sale", "deal", "offer",
        "free shipping", "fast delivery", "prime", "fulfilled",
        "warranty", "guarantee", "original", "genuine", "authentic"
    ]

    def __init__(self):
        super().__init__(name="DataProcessor")

    async def process(self, state: AgentState) -> AgentState:
        """
        Process and deduplicate raw product data.

        Pipeline:
        1. Clean and normalize each product
        2. Validate required fields
        3. Deduplicate similar products across platforms
        4. Sort by relevance/rating
        """
        self.log_start(state)

        try:
            raw_products = state.raw_product_data

            if not raw_products:
                logger.warning("No raw products to process")
                state.processed_products = []
                state.deduplicated_products = []
                self.log_end(state)
                return state

            logger.info(f"Processing {len(raw_products)} raw products")

            # Step 1: Clean and normalize
            cleaned_products = []
            for product in raw_products:
                cleaned = self._clean_product(product)
                if cleaned:
                    cleaned_products.append(cleaned)

            logger.info(f"Cleaned products: {len(cleaned_products)}")

            # Step 2: Store processed products
            state.processed_products = cleaned_products

            # Step 3: Deduplicate
            deduplicated = self._deduplicate_products(cleaned_products)
            logger.info(f"After deduplication: {len(deduplicated)}")

            # Step 4: Sort by score
            sorted_products = self._sort_by_relevance(deduplicated)
            state.deduplicated_products = sorted_products

            logger.info(f"Data processing completed: {len(sorted_products)} unique products")

        except Exception as e:
            self.log_error(e, state)
            state.processed_products = state.raw_product_data
            state.deduplicated_products = state.raw_product_data

        self.log_end(state)
        return state

    def _clean_product(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Clean and normalize a single product."""
        try:
            name = product.get("name")
            if not name or len(name.strip()) < 3:
                return None

            cleaned_name = self._clean_text(name)

            price = self._normalize_price(product.get("price"))
            if price is None or price <= 0:
                return None

            cleaned = {
                "name": cleaned_name,
                "price": price,
                "currency": product.get("currency", "USD"),
                "original_price": self._normalize_price(product.get("original_price")),
                "rating": self._normalize_rating(product.get("rating")),
                "review_count": self._normalize_int(product.get("review_count")),
                "availability": self._normalize_availability(product.get("availability")),
                "platform": product.get("platform", "Unknown"),
                "platform_product_id": product.get("platform_product_id"),
                "url": product.get("url"),
                "image_url": product.get("image_url"),
                "description": self._clean_text(product.get("description", "")),
                "category": product.get("category"),
                "brand": self._extract_brand(cleaned_name, product.get("brand")),
                "shipping_cost": self._normalize_price(product.get("shipping_cost")) or 0,
                "delivery_days": self._normalize_int(product.get("delivery_days")),
                "features": product.get("features", []),
            }

            if cleaned["original_price"] and cleaned["original_price"] > cleaned["price"]:
                discount = ((cleaned["original_price"] - cleaned["price"]) / cleaned["original_price"]) * 100
                cleaned["discount_percent"] = round(discount, 1)
            else:
                cleaned["discount_percent"] = 0

            return cleaned

        except Exception as e:
            logger.warning(f"Error cleaning product: {e}")
            return None

    def _clean_text(self, text: Optional[str]) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        cleaned = " ".join(text.split())
        cleaned = re.sub(r'[^\w\s\-\.\,\(\)]', '', cleaned)
        return cleaned.strip()

    def _normalize_price(self, price: Any) -> Optional[float]:
        """Normalize price to float."""
        if price is None:
            return None
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            cleaned = re.sub(r'[^\d.]', '', price.replace(',', ''))
            try:
                return float(cleaned) if cleaned else None
            except ValueError:
                return None
        return None

    def _normalize_rating(self, rating: Any) -> Optional[float]:
        """Normalize rating to float (0-5 scale)."""
        if rating is None:
            return None
        try:
            value = float(rating)
            if value > 5:
                value = value / 2
            return min(5.0, max(0.0, round(value, 1)))
        except (ValueError, TypeError):
            return None

    def _normalize_int(self, value: Any) -> Optional[int]:
        """Normalize value to integer."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            cleaned = re.sub(r'[^\d]', '', value)
            try:
                return int(cleaned) if cleaned else None
            except ValueError:
                return None
        return None

    def _normalize_availability(self, availability: Any) -> str:
        """Normalize availability status."""
        if not availability:
            return "Unknown"

        avail_lower = str(availability).lower()

        if any(word in avail_lower for word in ["in stock", "available", "yes"]):
            return "In Stock"
        elif any(word in avail_lower for word in ["out of stock", "unavailable", "no"]):
            return "Out of Stock"
        elif "limited" in avail_lower:
            return "Limited Stock"
        elif "pre" in avail_lower:
            return "Pre-order"

        return "Unknown"

    def _extract_brand(self, name: str, provided_brand: Optional[str]) -> Optional[str]:
        """Extract or validate brand from product name."""
        if provided_brand:
            return provided_brand

        known_brands = [
            "Apple", "Samsung", "Sony", "LG", "Dell", "HP", "Lenovo", "ASUS", "Acer",
            "Microsoft", "Google", "OnePlus", "Xiaomi", "Bose", "JBL", "Sennheiser",
            "Nike", "Adidas", "Bosch", "Philips", "Panasonic", "Canon", "Nikon"
        ]

        name_lower = name.lower()
        for brand in known_brands:
            if brand.lower() in name_lower:
                return brand

        return None

    def _deduplicate_products(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate products using fuzzy matching on names."""
        if not products:
            return []

        groups: List[List[Dict[str, Any]]] = []
        used_indices = set()

        for i, product in enumerate(products):
            if i in used_indices:
                continue

            group = [product]
            used_indices.add(i)

            for j, other in enumerate(products):
                if j in used_indices:
                    continue

                if self._are_similar(product, other):
                    group.append(other)
                    used_indices.add(j)

            groups.append(group)

        deduplicated = []
        for group in groups:
            best = self._select_best_product(group)
            if len(group) > 1:
                best["alternative_listings"] = [
                    {"platform": p["platform"], "price": p["price"], "url": p["url"]}
                    for p in group if p != best
                ]
            deduplicated.append(best)

        return deduplicated

    def _are_similar(self, p1: Dict, p2: Dict) -> bool:
        """Check if two products are similar (likely the same product)."""
        if p1.get("platform") == p2.get("platform"):
            return p1.get("name", "").lower() == p2.get("name", "").lower()

        name1 = self._normalize_name_for_comparison(p1.get("name", ""))
        name2 = self._normalize_name_for_comparison(p2.get("name", ""))

        similarity = SequenceMatcher(None, name1, name2).ratio()

        brand_match = True
        if p1.get("brand") and p2.get("brand"):
            brand_match = p1["brand"].lower() == p2["brand"].lower()

        return similarity >= self.SIMILARITY_THRESHOLD and brand_match

    def _normalize_name_for_comparison(self, name: str) -> str:
        """Normalize product name for comparison."""
        name_lower = name.lower()

        for word in self.NOISE_WORDS:
            name_lower = name_lower.replace(word, "")

        name_lower = re.sub(r'[^\w\s]', '', name_lower)
        return " ".join(name_lower.split())

    def _select_best_product(self, group: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select the best product from a group of similar products."""
        if len(group) == 1:
            return group[0]

        def score_product(p: Dict) -> Tuple[float, int, float]:
            rating = p.get("rating") or 0
            reviews = p.get("review_count") or 0
            price = p.get("price") or float('inf')
            return (rating, reviews, -price)

        return max(group, key=score_product)

    def _sort_by_relevance(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort products by relevance score."""
        def calculate_score(p: Dict) -> float:
            rating = p.get("rating") or 3.0
            reviews = p.get("review_count") or 1
            discount = p.get("discount_percent") or 0
            availability = p.get("availability", "Unknown")

            score = rating * 20
            score += math.log10(reviews + 1) * 5
            score += discount * 0.2

            if availability == "Out of Stock":
                score -= 30
            elif availability == "Limited Stock":
                score -= 10

            return score

        return sorted(products, key=calculate_score, reverse=True)
