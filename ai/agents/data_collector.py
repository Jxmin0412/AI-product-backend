"""
Agent 2: Data Collector Agent
Scrapes product data from e-commerce platforms.
"""
import logging
from typing import List, Dict, Any, Optional

from ai.agents.base import BaseAgent, AgentState
from ai.scraper import get_product_scraper, ProductScraper

logger = logging.getLogger(__name__)


class DataCollectorAgent(BaseAgent):
    """
    Collects product data from multiple e-commerce platforms.
    Uses HTML-based scrapers for real data extraction.
    """

    DEFAULT_PLATFORMS = ["amazon", "flipkart"]
    MAX_PRODUCTS = 20

    def __init__(self, scraper_client: Optional[ProductScraper] = None):
        super().__init__(name="DataCollector")
        self.scraper = scraper_client or get_product_scraper()

    async def process(self, state: AgentState) -> AgentState:
        """Scrape product data from e-commerce platforms based on extracted query."""
        self.log_start(state)

        try:
            search_params = self._build_search_params(state)
            logger.info(f"Collecting products with params: {search_params}")

            platforms = self._determine_platforms(state)

            products = await self.scraper.search_products(
                query=search_params["query"],
                category=search_params.get("category"),
                min_price=search_params.get("min_price"),
                max_price=search_params.get("max_price"),
                platforms=platforms,
                max_results=self.MAX_PRODUCTS
            )

            state.raw_product_data = products

            logger.info(f"Data collection completed: {len(products)} products found")

            platform_counts = {}
            for p in products:
                plat = p.get("platform", "Unknown")
                platform_counts[plat] = platform_counts.get(plat, 0) + 1
            logger.info(f"Platform breakdown: {platform_counts}")

        except Exception as e:
            self.log_error(e, state)
            state.scraping_errors.append(str(e))
            state.raw_product_data = []

        self.log_end(state)
        return state

    def _build_search_params(self, state: AgentState) -> Dict[str, Any]:
        """Build search parameters from extracted query data."""
        query = state.extracted_product_name or state.user_query

        if state.extracted_brand:
            query = f"{state.extracted_brand} {query}"

        if state.extracted_features:
            top_features = state.extracted_features[:2]
            query = f"{query} {' '.join(top_features)}"

        min_price, max_price = None, None
        if state.extracted_price_range:
            min_price, max_price = state.extracted_price_range

        return {
            "query": query.strip(),
            "category": state.extracted_category,
            "min_price": min_price,
            "max_price": max_price,
        }

    def _determine_platforms(self, state: AgentState) -> List[str]:
        """Determine which platforms to search based on context."""
        return self.DEFAULT_PLATFORMS

    async def scrape_single_platform(
        self, query: str, platform: str, **kwargs
    ) -> List[Dict[str, Any]]:
        """Scrape a specific platform directly."""
        try:
            return await self.scraper.search_single_platform(
                query=query, platform=platform, **kwargs
            )
        except Exception as e:
            logger.error(f"Error scraping {platform}: {e}")
            return []

    async def refresh_product_data(
        self, product_url: str, platform: str
    ) -> Optional[Dict[str, Any]]:
        """Refresh data for a specific product by URL."""
        logger.warning("Product refresh not yet implemented")
        return None
