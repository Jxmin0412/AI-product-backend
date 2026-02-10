"""
Real web scraper for product data collection using httpx.
Compatible with Python 3.14 on Windows (no Playwright subprocess issues).
"""
import asyncio
import logging
import re
import random
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup
import json

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for scrapers."""

    # Modern Chrome browser headers to avoid bot detection
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
    }

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
            logger.error(f"Page fetch error: {e}")
            return None

    def _extract_json_ld(self, html: str) -> List[Dict[str, Any]]:
        """Extract JSON-LD structured data from HTML."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            json_ld_scripts = soup.find_all('script', {'type': 'application/ld+json'})

            results = []
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        results.extend(data)
                    else:
                        results.append(data)
                except (json.JSONDecodeError, TypeError):
                    continue

            return results
        except Exception as e:
            logger.debug(f"JSON-LD extraction error: {e}")
            return []

    def _extract_embedded_json(self, html: str, pattern: str) -> List[Dict[str, Any]]:
        """Extract JSON data embedded in script tags matching a pattern."""
        try:
            results = []
            # Find all script tags
            soup = BeautifulSoup(html, 'html.parser')
            scripts = soup.find_all('script')

            for script in scripts:
                if script.string and pattern in script.string:
                    # Try to find JSON objects in the script
                    text = script.string
                    # Look for JSON array or object
                    json_matches = re.findall(r'\{[^{}]*"asin"[^{}]*\}', text)
                    for match in json_matches[:10]:
                        try:
                            data = json.loads(match)
                            results.append(data)
                        except json.JSONDecodeError:
                            continue

            return results
        except Exception as e:
            logger.debug(f"Embedded JSON extraction error: {e}")
            return []


class AmazonScraper(BaseScraper):
    """Scraper for Amazon product search results."""

    BASE_URL = "https://www.amazon.in"
    SEARCH_URL = "https://www.amazon.in/s?k={query}"

    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """Scrape Amazon search results."""
        search_url = self.SEARCH_URL.format(query=quote_plus(query))

        if min_price:
            search_url += f"&low-price={int(min_price)}"
        if max_price:
            search_url += f"&high-price={int(max_price)}"

        logger.info(f"Scraping Amazon: {search_url}")

        html_content = await self._fetch_page(search_url)
        if not html_content:
            logger.warning("Failed to fetch Amazon page - likely blocked")
            return []

        # Check if we got a CAPTCHA or blocked page
        if "captcha" in html_content.lower() or len(html_content) < 1000:
            logger.warning("Amazon returned CAPTCHA or blocked page")
            return []

        products = self._extract_products_from_html(html_content, category, max_results)

        logger.info(f"Scraped {len(products)} products from Amazon")
        return products

    def _extract_products_from_html(
        self,
        html: str,
        category: Optional[str],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Extract products from HTML using BeautifulSoup."""
        products = []

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Find all product containers
            product_cards = soup.find_all('div', {'data-component-type': 's-search-result'})

            if not product_cards:
                product_cards = soup.find_all('div', {'data-asin': True, 'data-index': True})

            logger.info(f"Found {len(product_cards)} Amazon product cards")

            for card in product_cards[:max_results]:
                try:
                    asin = card.get('data-asin', '')
                    if not asin or len(asin) != 10:
                        continue

                    # Build the product URL
                    product_url = f"{self.BASE_URL}/dp/{asin}"

                    product = {
                        "platform_product_id": asin,
                        "url": product_url,
                        "platform": "Amazon",
                        "category": category or "All",
                        "currency": "INR",
                    }

                    # Extract product name - try multiple selectors
                    name_elem = card.find('span', {'class': 'a-text-normal'})
                    if not name_elem:
                        name_elem = card.find('h2')
                    if not name_elem:
                        # Try finding any link with a title
                        link_with_title = card.find('a', {'title': True})
                        if link_with_title:
                            product["name"] = link_with_title.get('title', '')
                    if name_elem:
                        product["name"] = name_elem.get_text(strip=True)

                    if not product.get("name"):
                        continue  # Skip products without names

                    # Extract price - try multiple patterns
                    price_whole = card.find('span', {'class': 'a-price-whole'})
                    if price_whole:
                        price_text = price_whole.get_text(strip=True).replace(',', '').replace('.', '')
                        try:
                            product["price"] = float(price_text)
                        except ValueError:
                            pass

                    # Try alternative price selector (offscreen price)
                    if "price" not in product:
                        price_elem = card.find('span', {'class': 'a-offscreen'})
                        if price_elem:
                            price_text = price_elem.get_text(strip=True)
                            price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                            if price_match:
                                try:
                                    product["price"] = float(price_match.group())
                                except ValueError:
                                    pass

                    # Try to find price anywhere in the card
                    if "price" not in product:
                        card_text = card.get_text()
                        price_patterns = [
                            r'₹\s*([\d,]+)',
                            r'Rs\.?\s*([\d,]+)',
                            r'INR\s*([\d,]+)',
                        ]
                        for pattern in price_patterns:
                            price_match = re.search(pattern, card_text)
                            if price_match:
                                try:
                                    product["price"] = float(price_match.group(1).replace(',', ''))
                                    break
                                except ValueError:
                                    pass

                    # Skip if no price found
                    if "price" not in product:
                        logger.debug(f"No price found for ASIN {asin}")
                        continue

                    # Extract original price
                    orig_price_elem = card.find('span', {'class': 'a-price', 'data-a-strike': 'true'})
                    if orig_price_elem:
                        orig_text = orig_price_elem.get_text(strip=True)
                        orig_match = re.search(r'[\d,]+\.?\d*', orig_text.replace(',', ''))
                        if orig_match:
                            try:
                                product["original_price"] = float(orig_match.group())
                            except ValueError:
                                pass

                    # Extract image - try multiple sources
                    img_elem = card.find('img', {'class': 's-image'})
                    if img_elem:
                        img_src = img_elem.get('src', '') or img_elem.get('data-src', '')
                        if img_src and img_src.startswith('http'):
                            product["image_url"] = img_src

                    # Also try to find any product image
                    if not product.get("image_url"):
                        all_imgs = card.find_all('img')
                        for img in all_imgs:
                            src = img.get('src', '') or img.get('data-src', '')
                            if src and 'images' in src and src.startswith('http'):
                                product["image_url"] = src
                                break

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

                    product["availability"] = "In Stock"
                    products.append(product)

                    logger.debug(f"Extracted Amazon product: {product.get('name', '')[:50]} - ₹{product.get('price')}")

                except Exception as e:
                    logger.debug(f"Error parsing Amazon product card: {e}")
                    continue

        except Exception as e:
            logger.error(f"Amazon extraction error: {e}")

        # Log summary
        if products:
            logger.info(f"Successfully extracted {len(products)} products from Amazon with prices")
        else:
            logger.warning("Amazon: Found product cards but couldn't extract complete data (JS rendering required)")

        return products


class FlipkartScraper(BaseScraper):
    """Scraper for Flipkart (India) product search results."""

    BASE_URL = "https://www.flipkart.com"
    SEARCH_URL = "https://www.flipkart.com/search?q={query}"

    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """Scrape Flipkart search results."""
        search_url = self.SEARCH_URL.format(query=quote_plus(query))

        if min_price:
            search_url += f"&p%5B%5D=facets.price_range.from%3D{int(min_price)}"
        if max_price:
            search_url += f"&p%5B%5D=facets.price_range.to%3D{int(max_price)}"

        logger.info(f"Scraping Flipkart: {search_url}")

        html_content = await self._fetch_page(search_url)
        if not html_content:
            logger.warning("Failed to fetch Flipkart page - likely blocked")
            return []

        if len(html_content) < 1000:
            logger.warning("Flipkart returned minimal content - likely blocked")
            return []

        products = self._extract_products_from_html(html_content, category, max_results)

        logger.info(f"Scraped {len(products)} products from Flipkart")
        return products

    def _extract_from_initial_state(
        self,
        html: str,
        category: Optional[str],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Extract products from Flipkart's embedded window.__INITIAL_STATE__ JSON."""
        products = []

        try:
            match = re.search(
                r'window\.__INITIAL_STATE__\s*=\s*({.*?});\s*</script>',
                html, re.DOTALL
            )
            if not match:
                logger.debug("No __INITIAL_STATE__ found in Flipkart HTML")
                return []

            data = json.loads(match.group(1))
            page_data = data.get("pageDataV4", {}).get("page", {}).get("data", {})

            seen_pids = set()

            for slot_key in page_data:
                slot = page_data[slot_key]
                if not isinstance(slot, list):
                    continue

                for item in slot:
                    if not isinstance(item, dict):
                        continue
                    widget = item.get("widget", {})
                    if widget.get("type") != "PRODUCT_SUMMARY":
                        continue

                    for prod in widget.get("data", {}).get("products", []):
                        if len(products) >= max_results:
                            break

                        try:
                            val = prod.get("productInfo", {}).get("value", {})
                            action = prod.get("productInfo", {}).get("action", {})

                            pid = val.get("id", "")
                            if not pid or pid in seen_pids:
                                continue
                            seen_pids.add(pid)

                            # Name
                            name = val.get("titles", {}).get("title", "")
                            if not name:
                                continue

                            # Price
                            pricing = val.get("pricing", {})
                            prices = pricing.get("prices", [])
                            current_price = None
                            original_price = None
                            for p in prices:
                                if p.get("strikeOff"):
                                    original_price = p.get("value")
                                else:
                                    current_price = p.get("value")

                            if current_price is None:
                                continue

                            # URL
                            url = action.get("url", "") or val.get("baseUrl", "")
                            full_url = f"{self.BASE_URL}{url}" if url.startswith("/") else url

                            # Image
                            image_url = None
                            images = val.get("media", {}).get("images", [])
                            if images:
                                img_template = images[0].get("url", "")
                                image_url = (
                                    img_template
                                    .replace("{@width}", "416")
                                    .replace("{@height}", "416")
                                    .replace("{@quality}", "70")
                                )
                                if image_url.startswith("http://"):
                                    image_url = "https://" + image_url[7:]

                            # Rating
                            rating_data = val.get("rating", {})
                            rating = rating_data.get("average") if isinstance(rating_data, dict) else None
                            review_count = rating_data.get("reviewCount") if isinstance(rating_data, dict) else None

                            # Category
                            analytics = val.get("analyticsData", {})
                            prod_category = category or analytics.get("category", "All")

                            product = {
                                "platform_product_id": pid,
                                "name": name[:200],
                                "url": full_url,
                                "platform": "Flipkart",
                                "category": prod_category,
                                "currency": "INR",
                                "price": float(current_price),
                                "availability": "In Stock",
                            }

                            if original_price and original_price > current_price:
                                product["original_price"] = float(original_price)
                            if image_url:
                                product["image_url"] = image_url
                            if rating and rating > 0:
                                product["rating"] = float(rating)
                            if review_count:
                                product["review_count"] = int(review_count)

                            products.append(product)
                            logger.debug(f"Extracted Flipkart product: {name[:50]} - ₹{current_price}")

                        except Exception as e:
                            logger.debug(f"Error parsing Flipkart product from JSON: {e}")
                            continue

                    if len(products) >= max_results:
                        break
                if len(products) >= max_results:
                    break

        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"Failed to parse __INITIAL_STATE__ JSON: {e}")
        except Exception as e:
            logger.debug(f"__INITIAL_STATE__ extraction error: {e}")

        return products

    def _extract_products_from_html(
        self,
        html: str,
        category: Optional[str],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Extract products from HTML — tries embedded JSON first, falls back to HTML parsing."""

        # Try extracting from embedded JSON (most reliable)
        products = self._extract_from_initial_state(html, category, max_results)
        if products:
            logger.info(f"Successfully extracted {len(products)} products from Flipkart via __INITIAL_STATE__ JSON")
            return products

        # Fallback: HTML parsing (works for some page layouts)
        logger.info("Flipkart __INITIAL_STATE__ extraction returned 0 products, falling back to HTML parsing")
        products = []

        try:
            soup = BeautifulSoup(html, 'html.parser')
            product_links = soup.find_all('a', href=re.compile(r'/[^/]+/p/'))

            logger.info(f"Found {len(product_links)} Flipkart product links")

            seen_pids = set()

            for link in product_links[:max_results * 2]:
                try:
                    href = link.get('href', '')

                    pid_match = re.search(r'/p/([a-zA-Z0-9]+)', href)
                    if not pid_match:
                        continue

                    pid = pid_match.group(1)
                    if pid in seen_pids:
                        continue
                    seen_pids.add(pid)

                    full_url = f"{self.BASE_URL}{href}" if href.startswith('/') else href

                    product = {
                        "platform_product_id": pid,
                        "url": full_url,
                        "platform": "Flipkart",
                        "category": category or "All",
                        "currency": "INR",
                    }

                    # Navigate up to find the product card container
                    parent = link
                    for _ in range(6):
                        if parent.parent:
                            parent = parent.parent
                        else:
                            break

                    # Extract product name
                    name_elem = link.find('div', {'class': True})
                    if name_elem:
                        name_text = name_elem.get_text(strip=True)
                        if len(name_text) > 5:
                            product["name"] = name_text[:200]

                    if not product.get("name"):
                        title = link.get('title', '')
                        if title:
                            product["name"] = title

                    if not product.get("name"):
                        for elem in link.find_all(['div', 'span']):
                            text = elem.get_text(strip=True)
                            if 10 < len(text) < 200:
                                product["name"] = text
                                break

                    if not product.get("name"):
                        continue

                    # Extract price from parent container
                    parent_text = parent.get_text() if parent else ""
                    price_pattern = re.compile(r'₹\s*([\d,]+)')
                    price_matches = price_pattern.findall(parent_text)

                    if price_matches:
                        try:
                            product["price"] = float(price_matches[0].replace(',', ''))
                            if len(price_matches) > 1:
                                orig = float(price_matches[1].replace(',', ''))
                                if orig > product["price"]:
                                    product["original_price"] = orig
                        except ValueError:
                            pass

                    if "price" not in product:
                        continue

                    # Extract image
                    img_elem = parent.find('img') if parent else link.find('img')
                    if img_elem:
                        img_src = img_elem.get('src', '') or img_elem.get('data-src', '')
                        if img_src and 'http' in img_src:
                            product["image_url"] = img_src

                    # Extract rating
                    if parent:
                        rating_match = re.search(r'(\d\.?\d?)\s*★', parent.get_text())
                        if rating_match:
                            try:
                                product["rating"] = float(rating_match.group(1))
                            except ValueError:
                                pass

                    product["availability"] = "In Stock"
                    products.append(product)

                    if len(products) >= max_results:
                        break

                except Exception as e:
                    logger.debug(f"Error parsing Flipkart product: {e}")
                    continue

        except Exception as e:
            logger.error(f"Flipkart extraction error: {e}")

        if products:
            logger.info(f"Successfully extracted {len(products)} products from Flipkart with prices")
        else:
            logger.warning("Flipkart: Could not extract products from HTML or JSON")

        return products


class ScraperClient:
    """
    Main scraper client that orchestrates scraping from multiple platforms.
    Uses httpx for HTTP requests (compatible with Python 3.14).
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

        for i, result in enumerate(results):
            if isinstance(result, list):
                all_products.extend(result)
            elif isinstance(result, Exception):
                platform_name = platforms[i] if i < len(platforms) else "unknown"
                logger.error(f"Scraping error for {platform_name}: {type(result).__name__}: {result}")

        logger.info(f"Total products scraped: {len(all_products)}")

        # If no products found, return demo data with a note
        if not all_products:
            logger.warning("No products scraped - e-commerce sites may have changed their HTML structure")
            logger.info("Returning demo data for demonstration purposes")
            all_products = self._get_demo_products(query, category)

        return all_products[:max_results]

    def _get_demo_products(self, query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return demo products when scraping fails."""
        logger.warning(f"Returning demo products for '{query}' - all scrapers were blocked")

        base_price = random.randint(15000, 75000)

        demo_data = [
            {
                "platform_product_id": "DEMO001",
                "name": f"[DEMO] {query.title()} - Premium Model",
                "url": None,
                "price": base_price,
                "currency": "INR",
                "original_price": base_price + random.randint(5000, 15000),
                "rating": round(random.uniform(4.2, 4.8), 1),
                "review_count": random.randint(500, 5000),
                "image_url": None,
                "availability": "Demo Data",
                "platform": "Demo Mode",
                "category": category or "Electronics",
                "description": None,
                "is_demo": True,
            },
            {
                "platform_product_id": "DEMO002",
                "name": f"[DEMO] {query.title()} - Standard Edition",
                "url": None,
                "price": base_price - random.randint(3000, 8000),
                "currency": "INR",
                "original_price": base_price,
                "rating": round(random.uniform(4.0, 4.5), 1),
                "review_count": random.randint(200, 2000),
                "image_url": None,
                "availability": "Demo Data",
                "platform": "Demo Mode",
                "category": category or "Electronics",
                "description": None,
                "is_demo": True,
            },
            {
                "platform_product_id": "DEMO003",
                "name": f"[DEMO] {query.title()} - Budget Option",
                "url": None,
                "price": base_price - random.randint(8000, 15000),
                "currency": "INR",
                "original_price": None,
                "rating": round(random.uniform(3.8, 4.3), 1),
                "review_count": random.randint(100, 1000),
                "image_url": None,
                "availability": "Demo Data",
                "platform": "Demo Mode",
                "category": category or "Electronics",
                "description": None,
                "is_demo": True,
            },
        ]
        return demo_data

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
