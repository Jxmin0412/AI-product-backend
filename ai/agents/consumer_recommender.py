"""
Agent 4: Consumer Recommender Agent
Ranks products and generates personalized recommendations with explanations.
"""
import logging
import math
from typing import List, Dict, Any, Optional, Tuple

from ai.agents.base import BaseAgent, AgentState
from ai.prompts import RECOMMENDATION_REASON_PROMPT

logger = logging.getLogger(__name__)


class ConsumerRecommenderAgent(BaseAgent):
    """
    Generates personalized product recommendations for consumers.
    Ranks products based on user preferences and generates explanations.
    """

    TOP_RECOMMENDATIONS = 10

    WEIGHTS = {
        "rating": 25,
        "reviews": 10,
        "price_value": 15,
        "discount": 5,
        "availability": 20,
        "feature_match": 25,
    }

    def __init__(self):
        super().__init__(name="ConsumerRecommender")

    async def process(self, state: AgentState) -> AgentState:
        """
        Rank products and generate recommendations with explanations.

        Pipeline:
        1. Score products based on multiple criteria
        2. Apply user preference filters
        3. Select top recommendations
        4. Generate explanations for top picks
        """
        self.log_start(state)

        try:
            products = state.deduplicated_products

            if not products:
                logger.warning("No products to recommend")
                state.ranked_products = []
                state.recommendations = []
                self.log_end(state)
                return state

            logger.info(f"Generating recommendations from {len(products)} products")

            # Step 1: Calculate scores for all products
            scored_products = []
            for product in products:
                score, breakdown = self._calculate_score(product, state)
                product_with_score = product.copy()
                product_with_score["recommendation_score"] = score
                product_with_score["score_breakdown"] = breakdown
                scored_products.append(product_with_score)

            # Step 2: Sort by score
            ranked = sorted(scored_products, key=lambda p: p["recommendation_score"], reverse=True)
            state.ranked_products = ranked

            # Step 3: Select top recommendations
            top_products = ranked[:self.TOP_RECOMMENDATIONS]

            # Step 4: Generate explanations
            recommendations = []
            for i, product in enumerate(top_products):
                recommendation = await self._create_recommendation(
                    product=product,
                    rank=i + 1,
                    state=state
                )
                recommendations.append(recommendation)

                product_id = product.get("platform_product_id") or product.get("name", "")
                state.recommendation_reasons[product_id] = recommendation.get("reason", "")

            state.recommendations = recommendations

            logger.info(f"Generated {len(recommendations)} recommendations")

            for i, rec in enumerate(recommendations[:3]):
                logger.info(f"  #{i+1}: {rec['name'][:40]}... (score: {rec['recommendation_score']:.1f})")

        except Exception as e:
            self.log_error(e, state)
            state.ranked_products = state.deduplicated_products
            state.recommendations = state.deduplicated_products[:self.TOP_RECOMMENDATIONS]

        self.log_end(state)
        return state

    def _calculate_score(
        self,
        product: Dict[str, Any],
        state: AgentState
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate recommendation score for a product."""
        breakdown = {}

        # 1. Rating score
        rating = product.get("rating") or 3.0
        breakdown["rating"] = (rating / 5) * self.WEIGHTS["rating"] * 4

        # 2. Review count score (logarithmic)
        reviews = product.get("review_count") or 0
        if reviews > 0:
            review_score = min(math.log10(reviews + 1) / 4, 1.0)
            breakdown["reviews"] = review_score * self.WEIGHTS["reviews"]
        else:
            breakdown["reviews"] = 0

        # 3. Price value score
        price = product.get("price") or 0
        if price > 0:
            max_price = state.extracted_price_range[1] if state.extracted_price_range else None
            if max_price and price <= max_price:
                price_ratio = price / max_price
                breakdown["price_value"] = (1 - price_ratio * 0.5) * self.WEIGHTS["price_value"]
            else:
                breakdown["price_value"] = self.WEIGHTS["price_value"] * 0.5
        else:
            breakdown["price_value"] = 0

        # 4. Discount bonus
        discount = product.get("discount_percent") or 0
        breakdown["discount"] = min(discount / 50, 1.0) * self.WEIGHTS["discount"]

        # 5. Availability score
        availability = product.get("availability", "Unknown")
        if availability == "In Stock":
            breakdown["availability"] = self.WEIGHTS["availability"]
        elif availability == "Limited Stock":
            breakdown["availability"] = self.WEIGHTS["availability"] * 0.7
        elif availability == "Pre-order":
            breakdown["availability"] = self.WEIGHTS["availability"] * 0.3
        else:
            breakdown["availability"] = self.WEIGHTS["availability"] * 0.5

        # 6. Feature match score
        feature_score = self._calculate_feature_match(product, state)
        breakdown["feature_match"] = feature_score * self.WEIGHTS["feature_match"]

        total = sum(breakdown.values())
        return total, breakdown

    def _calculate_feature_match(self, product: Dict[str, Any], state: AgentState) -> float:
        """Calculate how well product features match user's requirements."""
        if not state.extracted_features:
            return 0.5

        user_features = [f.lower() for f in state.extracted_features]
        product_features = [f.lower() for f in product.get("features", [])]
        product_name = product.get("name", "").lower()
        product_desc = product.get("description", "").lower()

        matches = 0
        for feature in user_features:
            if any(feature in pf for pf in product_features):
                matches += 1
            elif feature in product_name:
                matches += 0.8
            elif feature in product_desc:
                matches += 0.5

        if user_features:
            return min(matches / len(user_features), 1.0)
        return 0.5

    async def _create_recommendation(
        self,
        product: Dict[str, Any],
        rank: int,
        state: AgentState
    ) -> Dict[str, Any]:
        """Create a recommendation entry with explanation."""
        reason = await self._generate_reason(product, state)

        if not reason:
            reason = self._generate_fallback_reason(product, state)

        recommendation = {
            **product,
            "rank": rank,
            "reason": reason,
            "match_type": self._determine_match_type(product, state),
        }

        return recommendation

    async def _generate_reason(self, product: Dict[str, Any], state: AgentState) -> Optional[str]:
        """Generate recommendation reason using LLM."""
        try:
            preferences = []
            if state.extracted_price_range[1]:
                preferences.append(f"Budget: under ${state.extracted_price_range[1]}")
            if state.extracted_brand:
                preferences.append(f"Brand preference: {state.extracted_brand}")
            if state.extracted_features:
                preferences.append(f"Features wanted: {', '.join(state.extracted_features)}")

            prompt = RECOMMENDATION_REASON_PROMPT.format(
                query=state.user_query,
                preferences="; ".join(preferences) if preferences else "None specified",
                product_name=product.get("name", "Unknown"),
                price=product.get("price", 0),
                rating=product.get("rating", "N/A"),
                reviews=product.get("review_count", 0),
                features=", ".join(product.get("features", [])) or "Not specified"
            )

            reason = await self.generate_text(
                prompt=prompt,
                max_tokens=100,
                temperature=0.7
            )

            return reason.strip() if reason else None

        except Exception as e:
            logger.warning(f"LLM reason generation failed: {e}")
            return None

    def _generate_fallback_reason(self, product: Dict[str, Any], state: AgentState) -> str:
        """Generate rule-based recommendation reason as fallback."""
        reasons = []

        rating = product.get("rating")
        if rating and rating >= 4.5:
            reasons.append("Excellent customer ratings")
        elif rating and rating >= 4.0:
            reasons.append("Highly rated by customers")

        reviews = product.get("review_count") or 0
        if reviews >= 1000:
            reasons.append("trusted by thousands of buyers")
        elif reviews >= 100:
            reasons.append("well-reviewed")

        discount = product.get("discount_percent") or 0
        if discount >= 20:
            reasons.append(f"{int(discount)}% off")

        if product.get("availability") == "In Stock":
            reasons.append("ready to ship")

        if state.extracted_features:
            product_name = product.get("name", "").lower()
            matched = [f for f in state.extracted_features if f.lower() in product_name]
            if matched:
                reasons.append(f"matches your {matched[0]} requirement")

        if reasons:
            return reasons[0].capitalize() + (f" and {reasons[1]}" if len(reasons) > 1 else "") + "."

        return "Good value option based on price and quality."

    def _determine_match_type(self, product: Dict[str, Any], state: AgentState) -> str:
        """Determine the type of match for categorization."""
        score_breakdown = product.get("score_breakdown", {})

        if score_breakdown.get("feature_match", 0) > self.WEIGHTS["feature_match"] * 0.7:
            return "feature_match"
        elif score_breakdown.get("price_value", 0) > self.WEIGHTS["price_value"] * 0.8:
            return "best_value"
        elif score_breakdown.get("rating", 0) > self.WEIGHTS["rating"] * 3.5:
            return "top_rated"
        elif score_breakdown.get("discount", 0) > self.WEIGHTS["discount"] * 0.5:
            return "best_deal"
        else:
            return "recommended"
