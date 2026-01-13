"""
Agent 2: Data Collector Agent
Scrapes product data from e-commerce platforms using Playwright.
"""
import logging
from typing import List, Dict, Any, Optional

from agents.base_agent import BaseAgent, AgentState
from utils.scraper_client import get_scraper_client, ScraperClient

logger = logging.getLogger(__name__)


class DataCollectorAgent(BaseAgent):
    """
    Collects product data from multiple e-commerce platforms.
    Uses Playwright-based scrapers for real data extraction.
    """

    # Default platforms to scrape
    DEFAULT_PLATFORMS = ["amazon", "flipkart"]

    # Maximum products to collect per search
    MAX_PRODUCTS = 20

    def __init__(self, scraper_client: Optional[ScraperClient] = None):
        """
        Initialize Data Collector agent.

        Args:
            scraper_client: Optional custom scraper client (for testing)
        """
        super().__init__(name="DataCollector")
        self.scraper = scraper_client or get_scraper_client()

    async def process(self, state: AgentState) -> AgentState:
        """
        Scrape product data from e-commerce platforms based on extracted query.

        Args:
            state: Current workflow state with extracted query parameters

        Returns:
            AgentState: State with collected raw product data
        """
        self.log_start(state)

        try:
            # Build search parameters from Agent 1's extraction
            search_params = self._build_search_params(state)

            logger.info(f"Collecting products with params: {search_params}")

            # Determine which platforms to search
            platforms = self._determine_platforms(state)

            # Scrape products from all platforms
            products = await self.scraper.search_products(
                query=search_params["query"],
                category=search_params.get("category"),
                min_price=search_params.get("min_price"),
                max_price=search_params.get("max_price"),
                platforms=platforms,
                max_results=self.MAX_PRODUCTS
            )

            # Store raw data in state
            state.raw_product_data = products

            logger.info(f"Data collection completed: {len(products)} products found")

            # Log platform breakdown
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
        """
        Build search parameters from extracted query data.

        Args:
            state: Agent state with extracted parameters

        Returns:
            Dictionary of search parameters
        """
        # Use extracted product name, fall back to original query
        query = state.extracted_product_name or state.user_query

        # If we have brand info, include it in query
        if state.extracted_brand:
            query = f"{state.extracted_brand} {query}"

        # If we have specific features, add them to query
        if state.extracted_features:
            # Add top 2 features to query for better search results
            top_features = state.extracted_features[:2]
            query = f"{query} {' '.join(top_features)}"

        # Extract price range
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
        """
        Determine which platforms to search based on context.

        Args:
            state: Agent state

        Returns:
            List of platform names to search
        """
        # For now, search all default platforms
        # Future: Could be smarter based on category, location, etc.
        return self.DEFAULT_PLATFORMS

    async def scrape_single_platform(
        self,
        query: str,
        platform: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Scrape a specific platform directly.

        Args:
            query: Search query
            platform: Platform name (amazon, flipkart, etc.)
            **kwargs: Additional search parameters

        Returns:
            List of product dictionaries
        """
        try:
            return await self.scraper.search_single_platform(
                query=query,
                platform=platform,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Error scraping {platform}: {e}")
            return []

    async def refresh_product_data(
        self,
        product_url: str,
        platform: str
    ) -> Optional[Dict[str, Any]]:
        """
        Refresh data for a specific product by URL.
        Useful for price tracking and availability updates.

        Args:
            product_url: URL of the product page
            platform: Platform name

        Returns:
            Updated product data or None if failed
        """
        # TODO: Implement product detail scraping
        # This would scrape a specific product page for updated info
        logger.warning("Product refresh not yet implemented")
        return None
