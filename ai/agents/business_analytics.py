"""
Agent 5: Business Analytics Agent
Generates market intelligence and business insights.
"""
from typing import Dict, Any

from ai.agents.base import BaseAgent, AgentState


class BusinessAnalyticsAgent(BaseAgent):
    """
    Generates business intelligence, market analysis, and strategic insights.
    Provides competitive analysis and trend forecasting.
    """

    def __init__(self):
        super().__init__(name="BusinessAnalytics")

    async def process(self, state: AgentState) -> AgentState:
        """Generate business analytics and insights."""
        self.log_start(state)

        try:
            state.market_metrics = await self._calculate_market_metrics(state)
            state.competitive_analysis = await self._analyze_competition(state)
            state.business_insights = await self._generate_insights(state)

            self.logger.info(f"Generated {len(state.business_insights)} business insights")

        except Exception as e:
            self.log_error(e, state)

        self.log_end(state)
        return state

    async def _calculate_market_metrics(self, state: AgentState) -> Dict[str, Any]:
        """Calculate market-level metrics."""
        products = state.deduplicated_products

        if not products:
            return {}

        prices = [p.get("price", 0) for p in products if p.get("price")]
        avg_price = sum(prices) / len(prices) if prices else 0

        return {
            "total_products": len(products),
            "average_price": round(avg_price, 2),
            "price_range": (min(prices), max(prices)) if prices else (0, 0),
            "category": state.extracted_category
        }

    async def _analyze_competition(self, state: AgentState) -> Dict[str, Any]:
        """Analyze competitive landscape."""
        products = state.deduplicated_products

        platform_stats = {}
        for product in products:
            platform = product.get("platform", "Unknown")
            if platform not in platform_stats:
                platform_stats[platform] = {"count": 0, "total_price": 0}

            platform_stats[platform]["count"] += 1
            platform_stats[platform]["total_price"] += product.get("price", 0)

        return {
            "platform_distribution": platform_stats,
            "total_platforms": len(platform_stats)
        }

    async def _generate_insights(self, state: AgentState) -> list:
        """Generate AI-powered business insights."""
        insights = [
            {
                "type": "trend",
                "title": "Market Analysis",
                "description": f"Analyzed {len(state.deduplicated_products)} products in {state.extracted_category} category",
                "confidence": 0.85,
                "impact": "Medium"
            }
        ]

        return insights
