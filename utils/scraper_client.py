"""
Real web scraper for product data collection using Playwright.
Handles JavaScript-rendered e-commerce pages.
"""
import asyncio
import logging
import re
import random
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# Try to import Playwright
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Run: pip install playwright && playwright install chromium")


class BaseScraper(ABC):
    """Abstract base class for scrapers."""

    @abstractmethod
    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        pass


class AmazonScraper(BaseScraper):
    """Scraper for Amazon product search results."""

    BASE_URL = "https://www.amazon.com"
    SEARCH_URL = "https://www.amazon.com/s?k={query}"

    # Selectors for Amazon search results
    SELECTORS = {
        "product_container": "[data-component-type='s-search-result']",
        "product_name": "h2 a span",
        "product_link": "h2 a",
        "price_whole": ".a-price-whole",
        "price_fraction": ".a-price-fraction",
        "original_price": ".a-text-price .a-offscreen",
        "rating": ".a-icon-star-small span.a-icon-alt",
        "review_count": ".a-size-base.s-underline-text",
        "image": ".s-image",
        "prime": ".a-icon-prime",
    }

    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """Scrape Amazon search results."""

        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright not available")
            return []

        products = []
        search_url = self.SEARCH_URL.format(query=quote_plus(query))

        # Add price filters to URL if specified
        if min_price:
            search_url += f"&low-price={int(min_price)}"
        if max_price:
            search_url += f"&high-price={int(max_price)}"

        logger.info(f"Scraping Amazon: {search_url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()

            try:
                # Navigate with retry
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)  # Wait for dynamic content

                # Get all product containers
                containers = await page.query_selector_all(self.SELECTORS["product_container"])

                for container in containers[:max_results]:
                    try:
                        product = await self._parse_product(container, page)
                        if product and product.get("name"):
                            product["platform"] = "Amazon"
                            product["category"] = category or "All"
                            products.append(product)
                    except Exception as e:
                        logger.warning(f"Error parsing product: {e}")
                        continue

            except Exception as e:
                logger.error(f"Amazon scraping error: {e}")
            finally:
                await browser.close()

        logger.info(f"Scraped {len(products)} products from Amazon")
        return products

    async def _parse_product(self, container, page: Page) -> Optional[Dict[str, Any]]:
        """Parse a single product from its container element."""
        try:
            # Get ASIN (Amazon product ID)
            asin = await container.get_attribute("data-asin")
            if not asin:
                return None

            # Product name
            name_elem = await container.query_selector(self.SELECTORS["product_name"])
            name = await name_elem.inner_text() if name_elem else None

            # Product link
            link_elem = await container.query_selector(self.SELECTORS["product_link"])
            href = await link_elem.get_attribute("href") if link_elem else None
            url = f"{self.BASE_URL}{href}" if href and not href.startswith("http") else href

            # Price
            price = await self._extract_price(container)

            # Original price (if discounted)
            original_price = None
            orig_elem = await container.query_selector(self.SELECTORS["original_price"])
            if orig_elem:
                orig_text = await orig_elem.inner_text()
                original_price = self._parse_price_text(orig_text)

            # Rating
            rating = None
            rating_elem = await container.query_selector(self.SELECTORS["rating"])
            if rating_elem:
                rating_text = await rating_elem.inner_text()
                rating_match = re.search(r"(\d+\.?\d*)", rating_text)
                if rating_match:
                    rating = float(rating_match.group(1))

            # Review count
            review_count = None
            review_elem = await container.query_selector(self.SELECTORS["review_count"])
            if review_elem:
                review_text = await review_elem.inner_text()
                review_count = self._parse_number(review_text)

            # Image
            image_url = None
            img_elem = await container.query_selector(self.SELECTORS["image"])
            if img_elem:
                image_url = await img_elem.get_attribute("src")

            # Prime availability
            prime_elem = await container.query_selector(self.SELECTORS["prime"])
            has_prime = prime_elem is not None

            return {
                "platform_product_id": asin,
                "name": name,
                "url": url,
                "price": price,
                "currency": "USD",
                "original_price": original_price,
                "rating": rating,
                "review_count": review_count,
                "image_url": image_url,
                "availability": "In Stock" if price else "Unknown",
                "shipping_cost": 0 if has_prime else None,
                "delivery_days": 2 if has_prime else None,
            }

        except Exception as e:
            logger.warning(f"Error parsing product element: {e}")
            return None

    async def _extract_price(self, container) -> Optional[float]:
        """Extract price from product container."""
        try:
            whole_elem = await container.query_selector(self.SELECTORS["price_whole"])
            if whole_elem:
                whole_text = await whole_elem.inner_text()
                whole = whole_text.replace(",", "").replace(".", "").strip()

                frac_elem = await container.query_selector(self.SELECTORS["price_fraction"])
                frac = "00"
                if frac_elem:
                    frac = await frac_elem.inner_text()

                return float(f"{whole}.{frac}")
        except Exception:
            pass
        return None

    def _parse_price_text(self, text: str) -> Optional[float]:
        """Parse price from text like '$1,299.99'."""
        if not text:
            return None
        cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    def _parse_number(self, text: str) -> Optional[int]:
        """Parse number from text like '1,234 reviews'."""
        if not text:
            return None
        cleaned = re.sub(r"[^\d]", "", text.replace(",", ""))
        try:
            return int(cleaned) if cleaned else None
        except ValueError:
            return None


class FlipkartScraper(BaseScraper):
    """Scraper for Flipkart (India) product search results."""

    BASE_URL = "https://www.flipkart.com"
    SEARCH_URL = "https://www.flipkart.com/search?q={query}"

    SELECTORS = {
        "product_container": "._1AtVbE",
        "product_name": "._4rR01T, .s1Q9rs",
        "product_link": "._1fQZEK, .s1Q9rs",
        "price": "._30jeq3",
        "original_price": "._3I9_wc",
        "rating": "._3LWZlK",
        "review_count": "._2_R_DZ span",
        "image": "._396cs4, ._2r_T1I",
    }

    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """Scrape Flipkart search results."""

        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright not available")
            return []

        products = []
        search_url = self.SEARCH_URL.format(query=quote_plus(query))

        if min_price:
            search_url += f"&p%5B%5D=facets.price_range.from%3D{int(min_price)}"
        if max_price:
            search_url += f"&p%5B%5D=facets.price_range.to%3D{int(max_price)}"

        logger.info(f"Scraping Flipkart: {search_url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()

            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)

                # Close login popup if present
                try:
                    close_btn = await page.query_selector("button._2KpZ6l")
                    if close_btn:
                        await close_btn.click()
                except:
                    pass

                # Get products
                containers = await page.query_selector_all(self.SELECTORS["product_container"])

                for container in containers[:max_results * 2]:  # Get extra, filter later
                    try:
                        product = await self._parse_flipkart_product(container)
                        if product and product.get("name") and product.get("price"):
                            product["platform"] = "Flipkart"
                            product["category"] = category or "All"
                            products.append(product)
                            if len(products) >= max_results:
                                break
                    except Exception as e:
                        continue

            except Exception as e:
                logger.error(f"Flipkart scraping error: {e}")
            finally:
                await browser.close()

        logger.info(f"Scraped {len(products)} products from Flipkart")
        return products

    async def _parse_flipkart_product(self, container) -> Optional[Dict[str, Any]]:
        """Parse a Flipkart product."""
        try:
            # Name
            name_elem = await container.query_selector(self.SELECTORS["product_name"])
            name = await name_elem.inner_text() if name_elem else None
            if not name:
                return None

            # Link
            link_elem = await container.query_selector(self.SELECTORS["product_link"])
            href = await link_elem.get_attribute("href") if link_elem else None
            url = f"{self.BASE_URL}{href}" if href else None

            # Price
            price_elem = await container.query_selector(self.SELECTORS["price"])
            price = None
            if price_elem:
                price_text = await price_elem.inner_text()
                price = self._parse_inr_price(price_text)

            # Original price
            orig_elem = await container.query_selector(self.SELECTORS["original_price"])
            original_price = None
            if orig_elem:
                orig_text = await orig_elem.inner_text()
                original_price = self._parse_inr_price(orig_text)

            # Rating
            rating_elem = await container.query_selector(self.SELECTORS["rating"])
            rating = None
            if rating_elem:
                rating_text = await rating_elem.inner_text()
                try:
                    rating = float(rating_text)
                except:
                    pass

            # Image
            img_elem = await container.query_selector(self.SELECTORS["image"])
            image_url = await img_elem.get_attribute("src") if img_elem else None

            return {
                "platform_product_id": href.split("/")[-1] if href else None,
                "name": name,
                "url": url,
                "price": price,
                "currency": "INR",
                "original_price": original_price,
                "rating": rating,
                "review_count": None,
                "image_url": image_url,
                "availability": "In Stock" if price else "Unknown",
            }

        except Exception as e:
            return None

    def _parse_inr_price(self, text: str) -> Optional[float]:
        """Parse INR price from text like '₹1,299'."""
        if not text:
            return None
        cleaned = re.sub(r"[^\d]", "", text)
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None


class ScraperClient:
    """
    Main scraper client that orchestrates scraping from multiple platforms.
    """

    def __init__(self):
        """Initialize scraper client with available scrapers."""
        self.scrapers = {
            "amazon": AmazonScraper(),
            "flipkart": FlipkartScraper(),
        }
        logger.info(f"ScraperClient initialized with platforms: {list(self.scrapers.keys())}")

    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        platforms: List[str] = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for products across multiple platforms.

        Args:
            query: Search query
            category: Product category filter
            min_price: Minimum price filter
            max_price: Maximum price filter
            platforms: List of platforms to search (default: all)
            max_results: Maximum total results to return

        Returns:
            List of product dictionaries from all platforms
        """
        if platforms is None:
            platforms = list(self.scrapers.keys())

        all_products = []
        results_per_platform = max(max_results // len(platforms), 5)

        # Scrape each platform concurrently
        tasks = []
        for platform in platforms:
            if platform in self.scrapers:
                tasks.append(
                    self.scrapers[platform].search_products(
                        query=query,
                        category=category,
                        min_price=min_price,
                        max_price=max_price,
                        max_results=results_per_platform
                    )
                )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_products.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Scraping error: {result}")

        logger.info(f"Total products scraped: {len(all_products)}")
        return all_products[:max_results]

    async def search_single_platform(
        self,
        query: str,
        platform: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search a single platform."""
        if platform not in self.scrapers:
            logger.warning(f"Unknown platform: {platform}")
            return []

        return await self.scrapers[platform].search_products(query=query, **kwargs)


# Global client instance
_scraper_client: Optional[ScraperClient] = None


def get_scraper_client() -> ScraperClient:
    """Get or create global scraper client."""
    global _scraper_client
    if _scraper_client is None:
        _scraper_client = ScraperClient()
    return _scraper_client
