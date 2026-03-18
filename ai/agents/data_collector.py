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

    DEFAULT_PLATFORMS = ["amazon", "snapdeal", "vijaysales", "shopclues"]
    MAX_PRODUCTS = 20
    MIN_PRODUCTS = 6

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

            # If too few results, retry with just the core product name (no features/brand)
            if len(products) < self.MIN_PRODUCTS and state.extracted_product_name:
                core_query = state.extracted_product_name
                if core_query != search_params["query"]:
                    logger.info(f"Only {len(products)} results, retrying with core query: '{core_query}'")
                    retry_products = await self.scraper.search_products(
                        query=core_query,
                        category=search_params.get("category"),
                        platforms=platforms,
                        max_results=self.MAX_PRODUCTS,
                    )
                    existing_names = {p.get("name", "").lower() for p in products}
                    for p in retry_products:
                        if p.get("name", "").lower() not in existing_names:
                            products.append(p)
                            existing_names.add(p.get("name", "").lower())

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

        # Only append top features if they add meaningful specificity
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
