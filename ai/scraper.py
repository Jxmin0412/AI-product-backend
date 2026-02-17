"""
Universal LLM-powered scraper for product data collection.

ProductScraper handles all platforms through a single pipeline:
  fetch HTML -> convert to markdown -> LLM extracts structured JSON

Adding a new platform = one entry in PLATFORM_CONFIGS.
"""
import asyncio
import json
import logging
import random
import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from urllib.parse import quote_plus

import httpx

from ai.prompts import (
    PRODUCT_EXTRACTION_PROMPT,
    SEARCH_RESULTS_EXTRACTION_PROMPT,
    COMPARISON_RECOMMENDATION_PROMPT,
)

logger = logging.getLogger(__name__)

try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False


# ============================================
# PLATFORM CONFIGURATIONS & DATA CLASSES
# ============================================

@dataclass
class PlatformConfig:
    """Configuration for a supported e-commerce platform."""
    name: str
    base_url: str
    search_url_template: str
    trust_score: float
    currency: str = "INR"


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


PLATFORM_CONFIGS: Dict[str, PlatformConfig] = {
    "amazon": PlatformConfig(
        name="Amazon",
        base_url="https://www.amazon.in",
        search_url_template="https://www.amazon.in/s?k={query}",
        trust_score=85.0,
    ),
    "flipkart": PlatformConfig(
        name="Flipkart",
        base_url="https://www.flipkart.com",
        search_url_template="https://www.flipkart.com/search?q={query}",
        trust_score=82.0,
    ),
    "myntra": PlatformConfig(
        name="Myntra",
        base_url="https://www.myntra.com",
        search_url_template="https://www.myntra.com/{query}",
        trust_score=78.0,
    ),
    "croma": PlatformConfig(
        name="Croma",
        base_url="https://www.croma.com",
        search_url_template="https://www.croma.com/searchB?q={query}",
        trust_score=80.0,
    ),
}

_BROWSER_HEADERS = {
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


# ============================================
# SHARED HELPERS
# ============================================

async def fetch_page(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch page HTML with browser-like headers."""
    try:
        async with httpx.AsyncClient(
            headers=_BROWSER_HEADERS, timeout=timeout, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP {e.response.status_code} fetching {url}")
    except httpx.RequestError as e:
        logger.warning(f"Request error fetching {url}: {e}")
    except Exception as e:
        logger.error(f"Page fetch error: {e}")
    return None


# ============================================
# PRODUCT SCRAPER (Universal LLM-powered)
# ============================================

class ProductScraper:
    """
    Universal LLM-powered product scraper.

    Pipeline: build search URL -> fetch HTML -> convert to markdown -> LLM extracts JSON
    Supports all platforms in PLATFORM_CONFIGS without platform-specific parsing.
    """

    def __init__(self, llm_client=None):
        from ai.llm_client import get_llm_client
        self.llm_client = llm_client or get_llm_client()
        self.platforms = PLATFORM_CONFIGS

        if HTML2TEXT_AVAILABLE:
            self.html_converter = html2text.HTML2Text()
            self.html_converter.ignore_links = False
            self.html_converter.ignore_images = False
            self.html_converter.ignore_emphasis = True
            self.html_converter.body_width = 0

    # ------------------------------------------
    # Multi-platform search (used by DataCollectorAgent)
    # ------------------------------------------

    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        platforms: Optional[List[str]] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search across multiple platforms concurrently using LLM extraction."""
        target_platforms = platforms or list(self.platforms.keys())
        valid_platforms = [p for p in target_platforms if p in self.platforms]

        if not valid_platforms:
            logger.warning(f"No valid platforms in {target_platforms}")
            return _get_demo_products(query, category)

        results_per_platform = max(max_results // len(valid_platforms), 5)

        tasks = [
            self._search_single_platform(
                query=query, platform=p,
                category=category, max_results=results_per_platform,
            )
            for p in valid_platforms
        ]

        all_products = []
        for i, result in enumerate(await asyncio.gather(*tasks, return_exceptions=True)):
            if isinstance(result, list):
                all_products.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Scraping error for {valid_platforms[i]}: {result}")

        # Post-filter by price range
        if min_price is not None or max_price is not None:
            all_products = [
                p for p in all_products
                if (min_price is None or (p.get("price") or 0) >= min_price)
                and (max_price is None or (p.get("price") or 0) <= max_price)
            ]

        if not all_products:
            logger.warning("No products scraped — returning demo data")
            all_products = _get_demo_products(query, category)

        return all_products[:max_results]

    async def search_single_platform(self, query: str, platform: str, **kwargs) -> List[Dict[str, Any]]:
        """Search a single platform. Public wrapper."""
        return await self._search_single_platform(query=query, platform=platform, **kwargs)

    # ------------------------------------------
    # Single URL extraction (used by consumer routes)
    # ------------------------------------------

    async def scrape_url(
        self, url: str, platform: Optional[str] = None, extraction_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Scrape a single product URL with LLM extraction."""
        if not platform:
            platform = self._detect_platform(url)

        html_content = await fetch_page(url)
        if not html_content:
            return {}

        markdown = self._html_to_markdown(html_content)
        if len(markdown) > 15000:
            markdown = markdown[:15000] + "\n...[truncated]"

        try:
            prompt = extraction_prompt or PRODUCT_EXTRACTION_PROMPT.format(
                platform=platform, url=url, content=markdown
            )
            extracted = await self.llm_client.extract_json(
                prompt=prompt,
                system_prompt="You are a precise data extraction assistant. Always return valid JSON.",
            )
        except Exception as e:
            logger.error(f"LLM extraction error for {url}: {e}")
            return {}

        if extracted:
            extracted["platform"] = platform
            extracted["product_url"] = url
            extracted["platform_product_id"] = self._extract_product_id(url, platform)

        return extracted or {}

    # ------------------------------------------
    # Cross-platform comparison (used by consumer routes)
    # ------------------------------------------

    async def compare_products(
        self, query: str, platforms: Optional[List[str]] = None,
    ) -> ComparisonResult:
        """Search and return scored comparison across platforms."""
        supported = [p for p in (platforms or self.platforms.keys()) if p in self.platforms]
        total_max = max(len(supported), 1) * 5

        products = await self.search_products(
            query=query, platforms=supported or None, max_results=total_max
        )

        if not products:
            return ComparisonResult(
                product_name=query, query=query, comparisons=[], best_deal=None,
                price_range={"min": 0, "max": 0}, images=[], recommendation="No products found.",
            )

        scored = self._score_products(products)

        images = [p["image_url"] for p in scored if p.get("image_url")]
        prices = [p["price"] for p in scored if p.get("price")]
        recommendation = await self._generate_recommendation(query, scored[:5])

        return ComparisonResult(
            product_name=query,
            query=query,
            comparisons=scored,
            best_deal=scored[0] if scored else None,
            price_range={"min": min(prices, default=0), "max": max(prices, default=0)},
            images=list(dict.fromkeys(images))[:10],
            recommendation=recommendation,
        )

    # ------------------------------------------
    # Internal: core LLM extraction pipeline
    # ------------------------------------------

    async def _search_single_platform(
        self, query: str, platform: str,
        category: Optional[str] = None, max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Fetch search results from one platform and extract products via LLM."""
        config = self.platforms.get(platform)
        if not config:
            return []

        search_url = config.search_url_template.format(query=quote_plus(query))

        html = await fetch_page(search_url)
        if not html or len(html) < 1000:
            logger.warning(f"{config.name}: empty or blocked response")
            return []

        if "captcha" in html.lower()[:3000] or "robot" in html.lower()[:3000]:
            logger.warning(f"{config.name}: CAPTCHA/bot detection triggered")
            return []

        # Pre-filter HTML to product sections, then convert to markdown
        focused_html = self._extract_product_html(html)
        source_html = focused_html or html

        # Extract image URLs and product links from HTML (html2text drops both)
        image_urls = self._extract_image_urls(source_html)
        product_links = self._extract_product_links(source_html, platform, config.base_url)

        markdown = self._html_to_markdown(source_html)
        # Keep under ~12K chars (~3K tokens) to stay within Groq free-tier TPM limits
        if len(markdown) > 12000:
            markdown = markdown[:12000] + "\n...[truncated]"

        # Append extracted data so the LLM can match them to products by position
        if image_urls or product_links:
            markdown += "\n\nEXTRACTED DATA (match to products above by order):"
            if product_links:
                markdown += "\nProduct URLs:\n" + "\n".join(f"{i+1}. {url}" for i, url in enumerate(product_links[:max_results]))
            if image_urls:
                markdown += "\nProduct Images:\n" + "\n".join(f"{i+1}. {url}" for i, url in enumerate(image_urls[:max_results]))

        try:
            prompt = SEARCH_RESULTS_EXTRACTION_PROMPT.format(
                platform=config.name, query=query,
                content=markdown, max_results=max_results,
            )
            raw_result = await self.llm_client.extract_json(
                prompt=prompt,
                system_prompt="You are a precise product data extraction assistant. Return ONLY a valid JSON array.",
            )
        except Exception as e:
            logger.error(f"LLM extraction error for {config.name}: {e}")
            return []

        return self._normalize_products(raw_result, platform, config, category)

    def _normalize_products(
        self, raw_result: Any, platform: str,
        config: PlatformConfig, category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Validate and normalize LLM-extracted product data."""
        if not raw_result:
            return []

        # LLM may return a list or wrap it in {"products": [...]}
        products_list = raw_result
        if isinstance(raw_result, dict):
            products_list = raw_result.get("products", [])
            if not products_list:
                products_list = [raw_result]
        if not isinstance(products_list, list):
            return []

        normalized = []
        for item in products_list:
            if not isinstance(item, dict):
                continue

            name = item.get("name", "").strip()
            price = item.get("price")
            if not name or price is None:
                continue
            # Handle price as string with currency symbols/commas (e.g. "₹1,49,990")
            if isinstance(price, str):
                price = re.sub(r'[₹$€,\s]', '', price)
            try:
                price = float(price)
            except (ValueError, TypeError):
                continue
            if price <= 0:
                continue

            product = {
                "name": name[:200],
                "price": price,
                "platform": config.name,
                "category": category or "All",
                "currency": item.get("currency", config.currency),
                "availability": item.get("availability", "In Stock"),
            }

            if item.get("original_price"):
                try:
                    orig = float(item["original_price"])
                    if orig > price:
                        product["original_price"] = orig
                except (ValueError, TypeError):
                    pass

            if item.get("rating"):
                try:
                    product["rating"] = float(item["rating"])
                except (ValueError, TypeError):
                    pass

            if item.get("review_count"):
                try:
                    product["review_count"] = int(item["review_count"])
                except (ValueError, TypeError):
                    pass

            if item.get("image_url"):
                img = str(item["image_url"])
                # Filter out LLM-hallucinated placeholder URLs
                if (img.startswith("http")
                    and "..." not in img
                    and "example.com" not in img
                    and "placeholder" not in img.lower()
                    and len(img) > 20):
                    product["image_url"] = img

            url = item.get("url", "")
            if url:
                if url.startswith("/"):
                    url = config.base_url + url
                product["url"] = url

            pid = item.get("platform_product_id")
            if pid:
                product["platform_product_id"] = str(pid)
            elif product.get("url"):
                product["platform_product_id"] = self._extract_product_id(
                    product["url"], platform
                )

            normalized.append(product)

        return normalized

    # ------------------------------------------
    # Internal: scoring & recommendation
    # ------------------------------------------

    def _score_products(self, products):
        """Calculate price_score, rating_score, value_score for comparison ranking."""
        prices = [float(p["price"]) for p in products if p.get("price")]
        if not prices:
            return products

        min_p, max_p = min(prices), max(prices)
        price_range = max_p - min_p or 1

        for product in products:
            price = float(product.get("price", 0) or 0)
            rating = float(product.get("rating", 0) or 0)
            trust = product.get("brand_trust_score", 70)

            product["price_score"] = round(100 - ((price - min_p) / price_range * 100), 2) if price else 0
            product["rating_score"] = round(rating * 20, 2)
            product["value_score"] = round(
                product["price_score"] * 0.40 + product["rating_score"] * 0.35 + trust * 0.25, 2
            )

            orig = product.get("original_price")
            if orig and price:
                try:
                    orig = float(orig)
                    if orig > price:
                        product["discount_percent"] = round(((orig - price) / orig) * 100, 1)
                except (ValueError, TypeError):
                    pass

        products.sort(key=lambda x: x.get("value_score", 0), reverse=True)
        for i, product in enumerate(products):
            product["comparison_rank"] = i + 1
            product["is_best_deal"] = (i == 0)

        return products

    async def _generate_recommendation(self, product_name, comparisons):
        """Generate LLM recommendation based on comparison data."""
        if not comparisons:
            return "No products available for comparison."
        try:
            data = json.dumps([{
                "platform": p.get("platform"), "price": p.get("price"),
                "rating": p.get("rating"), "availability": p.get("availability"),
                "value_score": p.get("value_score"),
            } for p in comparisons[:5]], indent=2)

            result = await self.llm_client.generate(
                prompt=COMPARISON_RECOMMENDATION_PROMPT.format(
                    product_name=product_name, comparison_data=data
                ),
                max_tokens=150, temperature=0.7
            )
            return result.strip()
        except Exception as e:
            logger.error(f"Recommendation generation error: {e}")
            if comparisons:
                best = comparisons[0]
                return f"Best deal found on {best.get('platform', 'unknown')} at {best.get('currency', 'INR')} {best.get('price', 'N/A')}."
            return "Unable to generate recommendation."

    # ------------------------------------------
    # Internal: HTML/URL utilities
    # ------------------------------------------

    def _extract_product_html(self, html: str) -> Optional[str]:
        """Extract product card sections from search results HTML.
        Keeps images and product data, strips navigation/headers/footers."""
        try:
            # Promote data-src to src so images survive markdown conversion
            html = re.sub(r'data-src="(https?://[^"]+)"', r'src="\1"', html)

            # Amazon: find each search result div and extract full card via bracket matching
            card_starts = [m.start() for m in re.finditer(
                r'<div[^>]*data-component-type="s-search-result"', html
            )]
            if card_starts:
                cards = []
                for start in card_starts[:20]:
                    end = self._find_closing_tag(html, start)
                    if end:
                        cards.append(html[start:end])
                if cards:
                    return "\n".join(cards)

            # Flipkart: extract product link containers
            card_starts = [m.start() for m in re.finditer(
                r'<a[^>]*href="[^"]*/p/[^"]*"', html
            )]
            if card_starts:
                cards = []
                for start in card_starts[:20]:
                    end = self._find_closing_tag(html, start, tag='a')
                    if end:
                        cards.append(html[start:end])
                if cards:
                    return "\n".join(cards)

            # Generic: strip header/footer/nav/scripts, keep body content
            for tag in ['header', 'nav', 'footer', 'script', 'style', 'noscript']:
                html = re.sub(rf'<{tag}[^>]*>.*?</{tag}>', '', html, flags=re.DOTALL | re.IGNORECASE)
            return html
        except Exception as e:
            logger.debug(f"Product HTML extraction failed: {e}")
            return None

    def _find_closing_tag(self, html: str, start: int, tag: str = 'div') -> Optional[int]:
        """Find the matching closing tag by counting open/close tags from start position."""
        depth = 0
        i = start
        open_pattern = re.compile(rf'<{tag}[\s>]', re.IGNORECASE)
        close_pattern = re.compile(rf'</{tag}\s*>', re.IGNORECASE)
        while i < len(html):
            open_match = open_pattern.search(html, i)
            close_match = close_pattern.search(html, i)
            if not close_match:
                break
            if open_match and open_match.start() < close_match.start():
                depth += 1
                i = open_match.end()
            else:
                depth -= 1
                if depth == 0:
                    return close_match.end()
                i = close_match.end()
        return None

    def _extract_image_urls(self, html: str) -> List[str]:
        """Extract product image URLs from HTML before markdown conversion.
        html2text drops images, so we extract them separately."""
        urls = []
        seen = set()
        # Match src or data-src attributes with image URLs
        for match in re.finditer(r'(?:src|data-src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)"', html, re.IGNORECASE):
            url = match.group(1)
            # Skip tiny icons, sprites, logos, and tracking pixels
            if any(skip in url.lower() for skip in ['icon', 'sprite', 'logo', 'pixel', '1x1', 'badge', 'star', 'rating']):
                continue
            # Skip very small images (likely UI elements)
            if re.search(r'[/_.](\d{1,2})x(\d{1,2})[/._]', url):
                continue
            if url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    def _extract_product_links(self, html: str, platform: str, base_url: str) -> List[str]:
        """Extract individual product page URLs from search results HTML."""
        links = []
        seen = set()
        if platform == "amazon":
            # Amazon product URLs contain /dp/ASIN or /gp/product/ASIN
            for match in re.finditer(r'href="(/[^"]*?/dp/[A-Z0-9]{10})[^"]*"', html):
                path = match.group(1)
                # Clean to just the /product-name/dp/ASIN part
                clean = re.match(r'(/[^?]*?/dp/[A-Z0-9]{10})', path)
                if clean and clean.group(1) not in seen:
                    seen.add(clean.group(1))
                    links.append(base_url + clean.group(1))
        elif platform == "flipkart":
            # Flipkart product URLs contain /p/
            for match in re.finditer(r'href="(/[^"]*?/p/[^"?]+)', html):
                path = match.group(1)
                if path not in seen:
                    seen.add(path)
                    links.append(base_url + path)
        else:
            # Generic: extract links that look like product pages
            for match in re.finditer(r'href="(/[^"]{20,})"', html):
                path = match.group(1)
                if path not in seen and not any(s in path for s in ['/s?', '/search', '/cart', '/account', '/login']):
                    seen.add(path)
                    links.append(base_url + path)
        return links

    def _html_to_markdown(self, html):
        """Convert HTML to markdown for LLM processing."""
        if HTML2TEXT_AVAILABLE:
            try:
                for tag in ['script', 'style', 'nav', 'footer']:
                    html = re.sub(rf'<{tag}[^>]*>.*?</{tag}>', '', html, flags=re.DOTALL | re.IGNORECASE)
                markdown = self.html_converter.handle(html)
                return re.sub(r'\n{3,}', '\n\n', re.sub(r' {2,}', ' ', markdown)).strip()
            except Exception:
                pass
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()

    def _detect_platform(self, url):
        url_lower = url.lower()
        for platform, config in self.platforms.items():
            if config.base_url.replace("https://", "").replace("www.", "") in url_lower:
                return platform
        return "unknown"

    def _extract_product_id(self, url, platform):
        try:
            if platform == "amazon":
                match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url)
                return match.group(1) if match else None
            elif platform == "flipkart":
                match = re.search(r'/p/([a-zA-Z0-9]+)', url)
                return match.group(1) if match else None
            return url.rstrip('/').split('/')[-1]
        except Exception:
            return None


# ============================================
# DEMO FALLBACK
# ============================================

def _get_demo_products(query, category=None):
    """Return demo products when scraping fails."""
    base_price = random.randint(15000, 75000)
    return [
        {
            "platform_product_id": f"DEMO{i:03d}",
            "name": f"[DEMO] {query.title()} - {label}",
            "url": None,
            "price": base_price + offset,
            "currency": "INR",
            "original_price": base_price + offset + random.randint(2000, 8000) if i < 2 else None,
            "rating": round(random.uniform(3.8, 4.8), 1),
            "review_count": random.randint(100, 5000),
            "image_url": None,
            "availability": "Demo Data",
            "platform": "Demo Mode",
            "category": category or "Electronics",
            "is_demo": True,
        }
        for i, (label, offset) in enumerate([
            ("Premium Model", 0),
            ("Standard Edition", -random.randint(3000, 8000)),
            ("Budget Option", -random.randint(8000, 15000)),
        ])
    ]


# ============================================
# GLOBAL INSTANCE
# ============================================

_product_scraper: Optional[ProductScraper] = None


def get_product_scraper() -> ProductScraper:
    """Get or create global ProductScraper instance."""
    global _product_scraper
    if _product_scraper is None:
        _product_scraper = ProductScraper()
    return _product_scraper


# Backward-compatible aliases
get_scraper_client = get_product_scraper
get_smart_scraper = get_product_scraper
