"""
SmartScraper - Firecrawl-inspired LLM-powered web scraping service.

Uses LLM for intelligent content extraction instead of brittle CSS selectors.
Supports multiple e-commerce platforms with automatic schema detection.

Note: Uses httpx for HTTP requests (Playwright has issues with Python 3.14 on Windows).
"""
import asyncio
import logging
import re
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from urllib.parse import quote_plus, urljoin, unquote

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False
    logger.warning("html2text not installed. Run: pip install html2text")

from utils.llm_client import get_llm_client, LLMClient


# ============================================
# SCHEMAS & DATA CLASSES
# ============================================

@dataclass
class ProductExtractionSchema:
    """JSON schema for product data extraction via LLM."""
    schema: Dict = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Product name/title"},
            "price": {"type": "number", "description": "Current price (number only)"},
            "original_price": {"type": "number", "description": "Original price if discounted"},
            "currency": {"type": "string", "description": "Currency code (INR, USD)"},
            "rating": {"type": "number", "description": "Rating out of 5"},
            "review_count": {"type": "integer", "description": "Number of reviews"},
            "availability": {"type": "string", "description": "Stock status"},
            "images": {"type": "array", "items": {"type": "string"}, "description": "Image URLs"},
            "description": {"type": "string", "description": "Product description"},
            "seller": {"type": "string", "description": "Seller/merchant name"},
            "shipping": {"type": "string", "description": "Shipping cost or Free"},
            "delivery_estimate": {"type": "string", "description": "Estimated delivery time"},
            "features": {"type": "array", "items": {"type": "string"}, "description": "Key features"},
            "brand": {"type": "string", "description": "Brand name"},
        },
        "required": ["name", "price"]
    })


@dataclass
class PlatformConfig:
    """Configuration for a supported e-commerce platform."""
    name: str
    base_url: str
    search_url_template: str
    trust_score: float  # 0-100
    currency: str = "INR"
    requires_js: bool = True


@dataclass
class ComparisonResult:
    """Result of product comparison across platforms."""
    product_name: str
    query: str
    comparisons: List[Dict[str, Any]]
    best_deal: Optional[Dict[str, Any]]
    price_range: Dict[str, float]
    images: List[str]
    recommendation: str


# ============================================
# PLATFORM CONFIGURATIONS
# ============================================

PLATFORM_CONFIGS: Dict[str, PlatformConfig] = {
    "amazon": PlatformConfig(
        name="Amazon",
        base_url="https://www.amazon.in",
        search_url_template="https://www.amazon.in/s?k={query}",
        trust_score=85.0,
        currency="INR"
    ),
    "flipkart": PlatformConfig(
        name="Flipkart",
        base_url="https://www.flipkart.com",
        search_url_template="https://www.flipkart.com/search?q={query}",
        trust_score=82.0,
        currency="INR"
    ),
    "myntra": PlatformConfig(
        name="Myntra",
        base_url="https://www.myntra.com",
        search_url_template="https://www.myntra.com/{query}",
        trust_score=78.0,
        currency="INR"
    ),
    "ajio": PlatformConfig(
        name="Ajio",
        base_url="https://www.ajio.com",
        search_url_template="https://www.ajio.com/search/?text={query}",
        trust_score=75.0,
        currency="INR"
    ),
    "croma": PlatformConfig(
        name="Croma",
        base_url="https://www.croma.com",
        search_url_template="https://www.croma.com/searchB?q={query}",
        trust_score=80.0,
        currency="INR"
    ),
    "reliance_digital": PlatformConfig(
        name="Reliance Digital",
        base_url="https://www.reliancedigital.in",
        search_url_template="https://www.reliancedigital.in/search?q={query}",
        trust_score=78.0,
        currency="INR"
    ),
}


# ============================================
# LLM EXTRACTION PROMPTS
# ============================================

PRODUCT_EXTRACTION_PROMPT = """You are a product data extraction specialist. Extract structured product information from the following webpage content.

IMPORTANT: Return ONLY a valid JSON object, no other text or explanation.

Extract these fields:
- name: Product name/title (string)
- price: Current price as a number only, no currency symbol (number)
- original_price: Original price if discounted, as number only (number or null)
- currency: Currency code like INR, USD (string)
- rating: Rating out of 5 (number or null)
- review_count: Number of reviews as integer (integer or null)
- availability: Stock status like "In Stock", "Out of Stock", "Limited Stock" (string)
- images: Array of image URLs found on the page (array of strings)
- description: Brief product description (string)
- seller: Seller or merchant name if available (string or null)
- shipping: Shipping cost or "Free Shipping" (string)
- delivery_estimate: Estimated delivery time like "2-3 days" (string or null)
- features: Key product features/specifications as array (array of strings)
- brand: Brand name if identifiable (string or null)

Platform: {platform}
Page URL: {url}

Webpage content:
{content}

JSON Response:"""


COMPARISON_RECOMMENDATION_PROMPT = """Based on the following product comparison data across multiple platforms, provide a brief recommendation (2-3 sentences) for the best purchase option.

Consider:
- Price (lower is better)
- Rating (higher is better)
- Availability
- Platform reliability
- Shipping/delivery time

Product: {product_name}

Comparison Data:
{comparison_data}

Provide a concise recommendation:"""


SEARCH_RESULTS_EXTRACTION_PROMPT = """Extract product listings from this e-commerce search results page.
Return a JSON array of products. Each product should have: name, price, url, image_url, rating (if available).

Platform: {platform}
Search Query: {query}

Page Content:
{content}

Return ONLY a JSON array:"""


# ============================================
# SMART SCRAPER SERVICE
# ============================================

class SmartScraper:
    """
    Firecrawl-inspired scraper using LLM for intelligent extraction.

    Features:
    - LLM-powered content extraction (no brittle CSS selectors)
    - HTML to Markdown conversion for efficient LLM processing
    - Multi-platform concurrent scraping
    - Automatic comparison scoring
    - Schema-based extraction with fallbacks
    - Uses httpx for HTTP requests (compatible with Python 3.14)
    """

    # Common browser headers
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initialize SmartScraper.

        Args:
            llm_client: Optional LLM client instance. Uses global client if not provided.
        """
        self.llm_client = llm_client or get_llm_client()
        self.platforms = PLATFORM_CONFIGS
        self.extraction_schema = ProductExtractionSchema()

        # HTML to text converter settings
        if HTML2TEXT_AVAILABLE:
            self.html_converter = html2text.HTML2Text()
            self.html_converter.ignore_links = False
            self.html_converter.ignore_images = False
            self.html_converter.ignore_emphasis = True
            self.html_converter.body_width = 0  # Don't wrap lines

        logger.info(f"SmartScraper initialized with {len(self.platforms)} platforms")

    # ============================================
    # CORE SCRAPING METHODS
    # ============================================

    async def scrape_url(
        self,
        url: str,
        platform: Optional[str] = None,
        extraction_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Scrape a single URL with LLM extraction.

        Args:
            url: URL to scrape
            platform: Platform name (auto-detected if not provided)
            extraction_prompt: Custom extraction prompt (uses default if not provided)

        Returns:
            Extracted product data dictionary
        """
        # Auto-detect platform from URL
        if not platform:
            platform = self._detect_platform(url)

        logger.info(f"Scraping URL: {url} (platform: {platform})")

        try:
            # Fetch page content
            html_content = await self._fetch_page(url)
            if not html_content:
                return {}

            # Convert HTML to markdown for LLM
            markdown_content = self._html_to_markdown(html_content)

            # Truncate if too long (save tokens)
            max_chars = 15000
            if len(markdown_content) > max_chars:
                markdown_content = markdown_content[:max_chars] + "\n...[truncated]"

            # Extract with LLM
            extracted = await self._extract_with_llm(
                content=markdown_content,
                platform=platform,
                url=url,
                prompt=extraction_prompt
            )

            if extracted:
                extracted["platform"] = platform
                extracted["product_url"] = url
                extracted["platform_product_id"] = self._extract_product_id(url, platform)

            return extracted or {}

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {}

    async def scrape_product_search(
        self,
        query: str,
        platforms: Optional[List[str]] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        max_results_per_platform: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search and scrape products from multiple platforms concurrently.

        Args:
            query: Search query
            platforms: List of platforms to search (default: all)
            min_price: Minimum price filter
            max_price: Maximum price filter
            max_results_per_platform: Max products per platform

        Returns:
            List of product dictionaries from all platforms
        """
        if platforms is None:
            platforms = list(self.platforms.keys())

        # Validate platforms
        platforms = [p for p in platforms if p in self.platforms]

        if not platforms:
            logger.warning("No valid platforms specified")
            return []

        logger.info(f"Searching '{query}' on platforms: {platforms}")

        # Create search tasks for each platform
        tasks = [
            self._search_platform(
                query=query,
                platform=platform,
                min_price=min_price,
                max_price=max_price,
                max_results=max_results_per_platform
            )
            for platform in platforms
        ]

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect all products
        all_products = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error scraping {platforms[i]}: {result}")
            elif isinstance(result, list):
                all_products.extend(result)

        logger.info(f"Total products scraped: {len(all_products)}")

        # If no real products found, return demo data
        if not all_products:
            logger.warning("No products scraped from any platform - returning demo data")
            all_products = self._get_demo_products(query, platforms)

        return all_products

    async def compare_products(
        self,
        query: str,
        platforms: Optional[List[str]] = None
    ) -> ComparisonResult:
        """
        Search for a product and return comparison across platforms.

        Args:
            query: Product search query
            platforms: Platforms to compare (default: all)

        Returns:
            ComparisonResult with scored comparisons and best deal
        """
        # Scrape from all platforms
        products = await self.scrape_product_search(
            query=query,
            platforms=platforms,
            max_results_per_platform=5
        )

        if not products:
            return ComparisonResult(
                product_name=query,
                query=query,
                comparisons=[],
                best_deal=None,
                price_range={"min": 0, "max": 0},
                images=[],
                recommendation="No products found for this search."
            )

        # Calculate comparison scores
        scored_products = self._calculate_comparison_scores(products)

        # Collect all images
        all_images = []
        for p in scored_products:
            if p.get("images"):
                all_images.extend(p["images"][:3])  # Max 3 images per product
            elif p.get("image_url"):
                all_images.append(p["image_url"])

        # Get price range
        prices = [p["price"] for p in scored_products if p.get("price")]
        price_range = {
            "min": min(prices) if prices else 0,
            "max": max(prices) if prices else 0
        }

        # Best deal is rank 1
        best_deal = scored_products[0] if scored_products else None

        # Generate LLM recommendation
        recommendation = await self._generate_recommendation(
            product_name=query,
            comparisons=scored_products[:5]
        )

        return ComparisonResult(
            product_name=query,
            query=query,
            comparisons=scored_products,
            best_deal=best_deal,
            price_range=price_range,
            images=list(set(all_images))[:10],  # Dedupe, max 10
            recommendation=recommendation
        )

    # ============================================
    # PLATFORM-SPECIFIC SCRAPING
    # ============================================

    async def _search_platform(
        self,
        query: str,
        platform: str,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search a single platform and extract products."""
        config = self.platforms.get(platform)
        if not config:
            return []

        # Build search URL
        search_url = config.search_url_template.format(query=quote_plus(query))

        # Add price filters where supported
        if platform == "amazon":
            if min_price:
                search_url += f"&low-price={int(min_price)}"
            if max_price:
                search_url += f"&high-price={int(max_price)}"
        elif platform == "flipkart":
            if min_price:
                search_url += f"&p%5B%5D=facets.price_range.from%3D{int(min_price)}"
            if max_price:
                search_url += f"&p%5B%5D=facets.price_range.to%3D{int(max_price)}"

        logger.info(f"Searching {platform}: {search_url}")

        try:
            # Fetch search results page
            html_content = await self._fetch_page(search_url)
            if not html_content:
                logger.warning(f"No content fetched from {platform}")
                return []

            # Check if we got actual content or blocked page
            if len(html_content) < 1000:
                logger.warning(f"Content too short from {platform}, likely blocked")
                return []

            # Try platform-specific extraction first (more reliable)
            products = []
            if platform == "amazon":
                products = self._extract_amazon_products(html_content, config.base_url)
            elif platform == "flipkart":
                products = self._extract_flipkart_products(html_content, config.base_url)

            # If platform-specific extraction found products, use them
            if products:
                logger.info(f"Extracted {len(products)} products from {platform} using HTML parsing")
            else:
                # Fallback to LLM extraction
                logger.info(f"Falling back to LLM extraction for {platform}")
                markdown_content = self._html_to_markdown(html_content)
                max_chars = 20000
                if len(markdown_content) > max_chars:
                    markdown_content = markdown_content[:max_chars]

                products = await self._extract_search_results(
                    content=markdown_content,
                    platform=platform,
                    query=query,
                    base_url=config.base_url
                )

            # Add platform info and filter
            valid_products = []
            for product in products[:max_results]:
                if product.get("name") and product.get("price"):
                    product["platform"] = config.name
                    product["platform_key"] = platform
                    product["currency"] = config.currency
                    product["brand_trust_score"] = config.trust_score

                    # Apply price filters
                    try:
                        price = float(product["price"])
                        if min_price and price < min_price:
                            continue
                        if max_price and price > max_price:
                            continue
                    except (ValueError, TypeError):
                        continue

                    valid_products.append(product)

            return valid_products

        except Exception as e:
            logger.error(f"Error searching {platform}: {e}")
            return []

    def _extract_amazon_products(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """Extract products from Amazon search results using BeautifulSoup."""
        products = []
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Find all product containers
            # Amazon uses data-component-type="s-search-result" for search results
            product_cards = soup.find_all('div', {'data-component-type': 's-search-result'})

            if not product_cards:
                # Try alternative selectors
                product_cards = soup.find_all('div', {'data-asin': True, 'data-index': True})

            logger.info(f"Found {len(product_cards)} Amazon product cards")

            for card in product_cards[:20]:  # Limit to 20
                try:
                    asin = card.get('data-asin', '')
                    if not asin or len(asin) != 10:
                        continue

                    product = {
                        "platform_product_id": asin,
                        "url": f"{base_url}/dp/{asin}",
                    }

                    # Extract product name
                    name_elem = card.find('span', {'class': 'a-text-normal'})
                    if not name_elem:
                        name_elem = card.find('h2')
                    if name_elem:
                        product["name"] = name_elem.get_text(strip=True)
                    else:
                        product["name"] = f"Amazon Product {asin}"

                    # Extract price - look for whole and fraction parts
                    price_whole = card.find('span', {'class': 'a-price-whole'})
                    price_fraction = card.find('span', {'class': 'a-price-fraction'})

                    if price_whole:
                        price_text = price_whole.get_text(strip=True).replace(',', '').replace('.', '')
                        try:
                            product["price"] = float(price_text)
                            if price_fraction:
                                fraction = price_fraction.get_text(strip=True)
                                product["price"] += float(f"0.{fraction}")
                        except ValueError:
                            pass

                    # Try alternative price selectors
                    if "price" not in product:
                        price_elem = card.find('span', {'class': 'a-offscreen'})
                        if price_elem:
                            price_text = price_elem.get_text(strip=True)
                            # Extract number from text like "₹29,999"
                            price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                            if price_match:
                                try:
                                    product["price"] = float(price_match.group())
                                except ValueError:
                                    pass

                    # Extract original price (strike-through)
                    original_price_elem = card.find('span', {'class': 'a-price', 'data-a-strike': 'true'})
                    if original_price_elem:
                        orig_text = original_price_elem.get_text(strip=True)
                        orig_match = re.search(r'[\d,]+\.?\d*', orig_text.replace(',', ''))
                        if orig_match:
                            try:
                                product["original_price"] = float(orig_match.group())
                            except ValueError:
                                pass

                    # Extract image
                    img_elem = card.find('img', {'class': 's-image'})
                    if img_elem:
                        product["image_url"] = img_elem.get('src', '')

                    # Extract rating
                    rating_elem = card.find('span', {'class': 'a-icon-alt'})
                    if rating_elem:
                        rating_text = rating_elem.get_text(strip=True)
                        rating_match = re.search(r'([\d.]+)\s*out of\s*5', rating_text)
                        if rating_match:
                            try:
                                product["rating"] = float(rating_match.group(1))
                            except ValueError:
                                pass

                    # Extract review count
                    review_elem = card.find('span', {'class': 'a-size-base', 'dir': 'auto'})
                    if review_elem:
                        review_text = review_elem.get_text(strip=True).replace(',', '')
                        if review_text.isdigit():
                            product["review_count"] = int(review_text)

                    # Only add if we have at least name and price
                    if product.get("name") and product.get("price"):
                        product["availability"] = "In Stock"
                        products.append(product)

                except Exception as e:
                    logger.debug(f"Error parsing Amazon product card: {e}")
                    continue

        except Exception as e:
            logger.error(f"Amazon extraction error: {e}")

        return products

    def _extract_flipkart_products(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """Extract products from Flipkart search results using BeautifulSoup."""
        products = []
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Flipkart uses various class patterns for product cards
            # Try to find product links with /p/ in them
            product_links = soup.find_all('a', href=re.compile(r'/[^/]+/p/'))

            logger.info(f"Found {len(product_links)} Flipkart product links")

            seen_pids = set()

            for link in product_links[:30]:
                try:
                    href = link.get('href', '')

                    # Extract product ID from URL
                    pid_match = re.search(r'/p/([a-zA-Z0-9]+)', href)
                    if not pid_match:
                        continue

                    pid = pid_match.group(1)
                    if pid in seen_pids:
                        continue
                    seen_pids.add(pid)

                    # Build full URL
                    full_url = f"{base_url}{href}" if href.startswith('/') else href

                    product = {
                        "platform_product_id": pid,
                        "url": full_url,
                    }

                    # Get parent container for more info
                    parent = link.find_parent('div', {'class': True})
                    if not parent:
                        parent = link

                    # Go up a few levels to find the product card
                    for _ in range(5):
                        if parent.parent:
                            parent = parent.parent
                        else:
                            break

                    # Extract product name from the link or nearby elements
                    name_elem = link.find('div', {'class': True})
                    if name_elem:
                        product["name"] = name_elem.get_text(strip=True)[:200]

                    if not product.get("name") or len(product.get("name", "")) < 5:
                        # Try getting title from link title attribute
                        title = link.get('title', '')
                        if title:
                            product["name"] = title

                    # Search parent container for price
                    price_pattern = re.compile(r'₹\s*([\d,]+)')
                    parent_text = parent.get_text() if parent else ""
                    price_matches = price_pattern.findall(parent_text)

                    if price_matches:
                        # First price is usually the current price
                        try:
                            product["price"] = float(price_matches[0].replace(',', ''))
                            # Second price might be original
                            if len(price_matches) > 1:
                                orig = float(price_matches[1].replace(',', ''))
                                if orig > product["price"]:
                                    product["original_price"] = orig
                        except ValueError:
                            pass

                    # Extract image
                    img_elem = parent.find('img') if parent else None
                    if img_elem:
                        img_src = img_elem.get('src', '') or img_elem.get('data-src', '')
                        if img_src and 'http' in img_src:
                            product["image_url"] = img_src

                    # Extract rating
                    rating_elem = parent.find('div', string=re.compile(r'^\d\.?\d?$')) if parent else None
                    if rating_elem:
                        try:
                            product["rating"] = float(rating_elem.get_text(strip=True))
                        except ValueError:
                            pass

                    # Alternative rating extraction
                    if "rating" not in product and parent:
                        rating_match = re.search(r'(\d\.?\d?)\s*★', parent.get_text())
                        if rating_match:
                            try:
                                product["rating"] = float(rating_match.group(1))
                            except ValueError:
                                pass

                    # Only add if we have name and price
                    if product.get("name") and product.get("price"):
                        product["availability"] = "In Stock"
                        products.append(product)

                except Exception as e:
                    logger.debug(f"Error parsing Flipkart product: {e}")
                    continue

        except Exception as e:
            logger.error(f"Flipkart extraction error: {e}")

        return products

    # ============================================
    # LLM EXTRACTION METHODS
    # ============================================

    async def _extract_with_llm(
        self,
        content: str,
        platform: str,
        url: str,
        prompt: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to extract structured product data."""
        try:
            extraction_prompt = prompt or PRODUCT_EXTRACTION_PROMPT.format(
                platform=platform,
                url=url,
                content=content
            )

            result = await self.llm_client.extract_json(
                prompt=extraction_prompt,
                system_prompt="You are a precise data extraction assistant. Always return valid JSON."
            )

            return result

        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            return None

    async def _extract_search_results(
        self,
        content: str,
        platform: str,
        query: str,
        base_url: str
    ) -> List[Dict[str, Any]]:
        """Extract product listings from search results page."""
        try:
            prompt = SEARCH_RESULTS_EXTRACTION_PROMPT.format(
                platform=platform,
                query=query,
                content=content
            )

            result = await self.llm_client.extract_json(
                prompt=prompt,
                system_prompt="You are a product listing extractor. Return only a JSON array of products."
            )

            if isinstance(result, list):
                # Fix relative URLs
                for product in result:
                    if product.get("url") and not product["url"].startswith("http"):
                        product["url"] = urljoin(base_url, product["url"])
                    if product.get("image_url") and not product["image_url"].startswith("http"):
                        product["image_url"] = urljoin(base_url, product["image_url"])
                return result
            elif isinstance(result, dict) and "products" in result:
                return result["products"]

            return []

        except Exception as e:
            logger.error(f"Search results extraction error: {e}")
            return []

    async def _generate_recommendation(
        self,
        product_name: str,
        comparisons: List[Dict[str, Any]]
    ) -> str:
        """Generate LLM recommendation based on comparison data."""
        try:
            if not comparisons:
                return "No products available for comparison."

            comparison_data = json.dumps(
                [{
                    "platform": p.get("platform"),
                    "price": p.get("price"),
                    "rating": p.get("rating"),
                    "availability": p.get("availability"),
                    "value_score": p.get("value_score"),
                    "comparison_rank": p.get("comparison_rank")
                } for p in comparisons[:5]],
                indent=2
            )

            prompt = COMPARISON_RECOMMENDATION_PROMPT.format(
                product_name=product_name,
                comparison_data=comparison_data
            )

            recommendation = await self.llm_client.generate(
                prompt=prompt,
                max_tokens=150,
                temperature=0.7
            )

            return recommendation.strip()

        except Exception as e:
            logger.error(f"Recommendation generation error: {e}")
            # Fallback recommendation
            if comparisons:
                best = comparisons[0]
                return f"Best deal found on {best.get('platform', 'unknown')} at {best.get('currency', 'INR')} {best.get('price', 'N/A')}."
            return "Unable to generate recommendation."

    # ============================================
    # HELPER METHODS
    # ============================================

    async def _fetch_page(self, url: str, timeout: int = 30) -> Optional[str]:
        """Fetch page HTML using httpx."""
        try:
            async with httpx.AsyncClient(
                headers=self.HEADERS,
                timeout=timeout,
                follow_redirects=True
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text

        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error fetching {url}: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.warning(f"Request error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Page fetch error for {url}: {e}")
            return None

    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML to clean markdown for LLM processing."""
        if HTML2TEXT_AVAILABLE:
            try:
                # Remove script and style tags first
                html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
                html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
                html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)

                markdown = self.html_converter.handle(html)

                # Clean up excessive whitespace
                markdown = re.sub(r'\n{3,}', '\n\n', markdown)
                markdown = re.sub(r' {2,}', ' ', markdown)

                return markdown.strip()
            except Exception as e:
                logger.warning(f"HTML to markdown conversion error: {e}")

        # Fallback: basic HTML stripping
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _detect_platform(self, url: str) -> str:
        """Auto-detect platform from URL."""
        url_lower = url.lower()
        for platform, config in self.platforms.items():
            if config.base_url.replace("https://", "").replace("www.", "") in url_lower:
                return platform
        return "unknown"

    def _extract_product_id(self, url: str, platform: str) -> Optional[str]:
        """Extract platform-specific product ID from URL."""
        try:
            if platform == "amazon":
                # Amazon ASIN: /dp/B09ABC123/ or /gp/product/B09ABC123
                match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url)
                return match.group(1) if match else None

            elif platform == "flipkart":
                # Flipkart: /p/itm123abc
                match = re.search(r'/p/([a-zA-Z0-9]+)', url)
                return match.group(1) if match else None

            # Generic: use last path segment
            return url.rstrip('/').split('/')[-1]

        except:
            return None

    def _calculate_comparison_scores(
        self,
        products: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Calculate price_score, rating_score, value_score for comparison.

        Scoring:
        - price_score: 0-100, lower price = higher score
        - rating_score: 0-100, rating * 20
        - value_score: weighted combination
        - brand_trust_score: platform reliability
        """
        if not products:
            return []

        # Get price range
        prices = []
        for p in products:
            try:
                price = float(p.get("price", 0))
                if price > 0:
                    prices.append(price)
            except (ValueError, TypeError):
                pass

        if not prices:
            return products

        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price if max_price != min_price else 1

        for product in products:
            try:
                price = float(product.get("price", 0))
            except (ValueError, TypeError):
                price = 0

            try:
                rating = float(product.get("rating", 0) or 0)
            except (ValueError, TypeError):
                rating = 0

            # Price score: 100 for lowest price, scales down
            product["price_score"] = round(
                100 - ((price - min_price) / price_range * 100), 2
            ) if price else 0

            # Rating score: rating * 20 (5.0 = 100)
            product["rating_score"] = round(rating * 20, 2)

            # Platform trust score
            trust_score = product.get("brand_trust_score", 70)

            # Value score: weighted combination
            # 40% price, 35% rating, 25% platform trust
            product["value_score"] = round(
                (product["price_score"] * 0.40) +
                (product["rating_score"] * 0.35) +
                (trust_score * 0.25),
                2
            )

            # Calculate discount if original_price exists
            original = product.get("original_price")
            if original and price:
                try:
                    original = float(original)
                    if original > price:
                        product["discount_percent"] = round(
                            ((original - price) / original) * 100, 1
                        )
                except (ValueError, TypeError):
                    pass

        # Sort by value_score descending
        products.sort(key=lambda x: x.get("value_score", 0), reverse=True)

        # Assign ranks
        for i, product in enumerate(products):
            product["comparison_rank"] = i + 1
            product["is_best_deal"] = (i == 0)

        return products

    def _get_demo_products(self, query: str, platforms: List[str]) -> List[Dict[str, Any]]:
        """Return demo products when scraping fails."""
        import random

        logger.warning(f"Returning demo products for '{query}' - scraping was blocked")

        base_price = random.randint(20000, 80000)

        demo_products = []

        for i, platform in enumerate(platforms[:3]):
            config = self.platforms.get(platform)
            if not config:
                continue

            price_variation = random.randint(-5000, 5000)
            price = base_price + price_variation

            demo_products.append({
                "name": f"[DEMO] {query} - Option {i + 1}",
                "price": price,
                "original_price": price + random.randint(2000, 8000),
                "currency": config.currency,
                "rating": round(random.uniform(3.5, 4.8), 1),
                "review_count": random.randint(100, 5000),
                "availability": "Demo Data",
                "platform": f"{config.name} (Demo)",
                "platform_key": platform,
                "brand_trust_score": config.trust_score,
                "url": None,  # No URL for demo products
                "image_url": None,
                "description": None,  # No description for demo products
                "is_demo": True,
            })

        return demo_products

    async def extract_images(self, url: str) -> List[str]:
        """Extract all product images from a product page."""
        try:
            html_content = await self._fetch_page(url)
            if not html_content:
                return []

            # Find all image URLs
            img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
            images = re.findall(img_pattern, html_content, re.IGNORECASE)

            # Filter for product images (larger images, common patterns)
            product_images = []
            for img in images:
                # Skip tiny images, icons, logos
                if any(skip in img.lower() for skip in [
                    'icon', 'logo', 'sprite', 'pixel', '1x1', 'tracking',
                    'badge', 'star', 'rating', 'thumbnail'
                ]):
                    continue

                # Prefer larger product images
                if any(pattern in img.lower() for pattern in [
                    'product', 'item', 'large', 'main', 'primary', 'zoom'
                ]):
                    product_images.insert(0, img)
                else:
                    product_images.append(img)

            # Deduplicate and limit
            seen = set()
            unique_images = []
            for img in product_images:
                if img not in seen:
                    seen.add(img)
                    unique_images.append(img)

            return unique_images[:10]

        except Exception as e:
            logger.error(f"Image extraction error: {e}")
            return []


# ============================================
# GLOBAL INSTANCE
# ============================================

_smart_scraper: Optional[SmartScraper] = None


def get_smart_scraper() -> SmartScraper:
    """Get or create global SmartScraper instance."""
    global _smart_scraper
    if _smart_scraper is None:
        _smart_scraper = SmartScraper()
    return _smart_scraper
