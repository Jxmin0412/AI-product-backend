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
    "snapdeal": PlatformConfig(
        name="Snapdeal",
        base_url="https://www.snapdeal.com",
        search_url_template="https://www.snapdeal.com/search?keyword={query}&sort=rlvncy",
        trust_score=72.0,
    ),
    "vijaysales": PlatformConfig(
        name="Vijay Sales",
        base_url="https://www.vijaysales.com",
        search_url_template="https://www.vijaysales.com/search/{query}",
        trust_score=78.0,
    ),
    "shopclues": PlatformConfig(
        name="ShopClues",
        base_url="https://www.shopclues.com",
        search_url_template="https://www.shopclues.com/search?q={query}",
        trust_score=70.0,
    ),
}

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
]

_PLATFORM_REFERERS = {
    "amazon": "https://www.amazon.in/",
    "snapdeal": "https://www.snapdeal.com/",
    "vijaysales": "https://www.vijaysales.com/",
    "shopclues": "https://www.shopclues.com/",
}

def _get_browser_headers(platform: str = None) -> dict:
    """Get browser-like headers with rotated User-Agent and platform referer."""
    ua = random.choice(_USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin" if platform else "none",
        "sec-fetch-user": "?1",
    }
    if platform and platform in _PLATFORM_REFERERS:
        headers["Referer"] = _PLATFORM_REFERERS[platform]
    return headers


# ============================================
# SHARED HELPERS
# ============================================

async def fetch_page(url: str, timeout: int = 30, platform: str = None) -> Optional[str]:
    """Fetch page HTML with browser-like headers and platform-specific referer."""
    headers = _get_browser_headers(platform)
    try:
        async with httpx.AsyncClient(
            headers=headers, timeout=timeout, follow_redirects=True
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

    MIN_RESULTS = 6

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

        all_products = await self._scrape_platforms(
            query=query, platforms=valid_platforms,
            category=category, results_per_platform=results_per_platform,
        )

        # Retry with simplified query if too few results
        if len(all_products) < self.MIN_RESULTS:
            simple_query = self._simplify_query(query)
            if simple_query != query:
                logger.info(f"Too few results ({len(all_products)}), retrying with simplified query: '{simple_query}'")
                retry_products = await self._scrape_platforms(
                    query=simple_query, platforms=valid_platforms,
                    category=category, results_per_platform=results_per_platform,
                )
                # Merge without duplicating (by name)
                existing_names = {p.get("name", "").lower() for p in all_products}
                for p in retry_products:
                    if p.get("name", "").lower() not in existing_names:
                        all_products.append(p)
                        existing_names.add(p.get("name", "").lower())

        # Post-filter by price range
        if min_price is not None or max_price is not None:
            filtered = [
                p for p in all_products
                if (min_price is None or (p.get("price") or 0) >= min_price)
                and (max_price is None or (p.get("price") or 0) <= max_price)
            ]
            # Only apply filter if it doesn't eliminate everything
            if filtered:
                all_products = filtered

        if not all_products:
            logger.warning("No products scraped — returning demo data")
            all_products = _get_demo_products(query, category)

        return all_products[:max_results]

    async def _scrape_platforms(
        self, query: str, platforms: List[str],
        category: Optional[str], results_per_platform: int,
    ) -> List[Dict[str, Any]]:
        """Scrape multiple platforms concurrently and combine results."""
        tasks = [
            self._search_single_platform(
                query=query, platform=p,
                category=category, max_results=results_per_platform,
            )
            for p in platforms
        ]

        all_products = []
        for i, result in enumerate(await asyncio.gather(*tasks, return_exceptions=True)):
            if isinstance(result, list):
                all_products.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Scraping error for {platforms[i]}: {result}")

        return all_products

    def _simplify_query(self, query: str) -> str:
        """Simplify a search query for broader results (strip modifiers, keep core terms)."""
        simplified = re.sub(
            r'\b(?:best|top|good|great|cheap|affordable|premium|professional|under|below|above|over|around|latest|new|2024|2025|2026)\b',
            '', query, flags=re.IGNORECASE
        )
        simplified = re.sub(r'\$?\d[\d,]*(?:\.\d+)?', '', simplified)
        simplified = ' '.join(simplified.split()).strip()
        return simplified if len(simplified) >= 3 else query

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

        html = await fetch_page(search_url, platform=platform)
        if not html or len(html) < 1000:
            logger.warning(f"{config.name}: empty or blocked response")
            return []

        if "captcha" in html.lower()[:3000] or "robot" in html.lower()[:3000]:
            logger.warning(f"{config.name}: CAPTCHA/bot detection triggered")
            return []

        # Strategy 1: Per-card extraction (associates images/URLs correctly)
        cards = self._extract_product_cards(html, platform, config.base_url)

        if cards:
            logger.info(f"{config.name}: extracted {len(cards)} product cards")
            sections = []
            for i, card in enumerate(cards[:max_results]):
                section = f"=== PRODUCT {i+1} ==="
                if card.get("product_url"):
                    section += f"\nProduct URL: {card['product_url']}"
                if card.get("image_url"):
                    section += f"\nProduct Image URL: {card['image_url']}"
                card_md = self._html_to_markdown(card["html"])
                # Limit each card to keep total size manageable
                if len(card_md) > 1500:
                    card_md = card_md[:1500]
                section += f"\n{card_md}"
                sections.append(section)
            markdown = "\n\n".join(sections)
        else:
            # Strategy 2: Whole-page fallback with global image/link extraction
            logger.info(f"{config.name}: no card patterns found, using whole-page extraction")
            focused_html = self._extract_product_html(html)
            source_html = focused_html or html

            image_urls = self._extract_image_urls(source_html)
            product_links = self._extract_product_links(source_html, platform, config.base_url)

            markdown = self._html_to_markdown(source_html)

            if image_urls or product_links:
                markdown += "\n\nEXTRACTED DATA (match to products above by order):"
                if product_links:
                    markdown += "\nProduct URLs:\n" + "\n".join(f"{i+1}. {url}" for i, url in enumerate(product_links[:max_results]))
                if image_urls:
                    markdown += "\nProduct Images:\n" + "\n".join(f"{i+1}. {url}" for i, url in enumerate(image_urls[:max_results]))

        # Truncation — increased budget for better extraction
        if len(markdown) > 24000:
            markdown = markdown[:24000] + "\n...[truncated]"

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
        elif platform == "snapdeal":
            for match in re.finditer(r'href="(/product/[^"]+)"', html):
                path = match.group(1).split('?')[0]
                if path not in seen:
                    seen.add(path)
                    links.append(base_url + path)
        else:
            for match in re.finditer(r'href="(/[^"]{20,})"', html):
                path = match.group(1)
                if path not in seen and not any(s in path for s in ['/s?', '/search', '/cart', '/account', '/login']):
                    seen.add(path)
                    links.append(base_url + path)
        return links

    def _extract_product_cards(self, html: str, platform: str, base_url: str) -> List[Dict[str, Any]]:
        """Extract individual product cards, each with its own image URL and product link.
        Returns list of {"html": str, "image_url": str|None, "product_url": str|None}."""
        # Promote lazy-loaded images before extraction
        html = re.sub(r'data-src="(https?://[^"]+)"', r'src="\1"', html)

        cards = []
        card_starts = []

        if platform == "amazon":
            card_starts = [m.start() for m in re.finditer(
                r'<div[^>]*data-component-type="s-search-result"', html
            )]
            tag = 'div'
        elif platform == "snapdeal":
            card_starts = [m.start() for m in re.finditer(
                r'<div[^>]*class="[^"]*product-tuple-listing[^"]*"', html, re.IGNORECASE
            )]
            tag = 'div'
        else:
            for pattern in [r'<div[^>]*class="[^"]*product[^"]*"', r'<article[^>]*']:
                card_starts = [m.start() for m in re.finditer(pattern, html, re.IGNORECASE)]
                if card_starts:
                    tag = pattern.split('<')[1].split('[')[0].split(' ')[0]
                    break

        for start in card_starts[:20]:
            end = self._find_closing_tag(html, start, tag=tag if platform != "amazon" else 'div')
            if not end:
                continue
            card_html = html[start:end]

            # Skip sponsored/ad cards
            if 'AdHolder' in card_html or 'sp-sponsored' in card_html or 'data-component-type="sp-' in card_html:
                continue

            image_url = self._extract_card_image(card_html)
            product_url = self._extract_card_link(card_html, platform, base_url)
            cards.append({"html": card_html, "image_url": image_url, "product_url": product_url})

        return cards

    def _extract_card_image(self, card_html: str) -> Optional[str]:
        """Extract the first relevant product image from a single card's HTML."""
        for match in re.finditer(
            r'src="(https?://[^"]+\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)"',
            card_html, re.IGNORECASE
        ):
            url = match.group(1)
            if any(skip in url.lower() for skip in [
                'icon', 'sprite', 'logo', 'pixel', '1x1', 'badge',
                'star', 'rating', 'overlay', 'placeholder', 'loading'
            ]):
                continue
            if re.search(r'[/_.](\d{1,2})x(\d{1,2})[/._]', url):
                continue
            return url
        return None

    def _extract_card_link(self, card_html: str, platform: str, base_url: str) -> Optional[str]:
        """Extract the product page URL from a single card's HTML."""
        if platform == "amazon":
            match = re.search(r'href="(/[^"]*?/dp/[A-Z0-9]{10})[^"]*"', card_html)
            if match:
                clean = re.match(r'(/[^?]*?/dp/[A-Z0-9]{10})', match.group(1))
                return base_url + clean.group(1) if clean else None
        elif platform == "snapdeal":
            match = re.search(r'href="(/product/[^"]+)"', card_html)
            if match:
                return base_url + match.group(1).split('?')[0]
        else:
            match = re.search(r'href="(/[^"]{20,})"', card_html)
            if match:
                path = match.group(1)
                if not any(s in path for s in ['/s?', '/search', '/cart', '/account', '/login']):
                    return base_url + path
        return None

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
            elif platform == "snapdeal":
                match = re.search(r'/(\d{8,})$', url.rstrip('/'))
                return match.group(1) if match else url.rstrip('/').split('/')[-1]
            return url.rstrip('/').split('/')[-1]
        except Exception:
            return None


# ============================================
# DEMO FALLBACK
# ============================================

def _get_demo_products(query, category=None):
    """Return demo products when scraping fails. Provides enough products for a useful display."""
    base_price = random.randint(15000, 75000)
    product_variants = [
        ("Premium Model", 0, 4.6, 3200, "In Stock", "Amazon"),
        ("Pro Edition", -2000, 4.4, 1850, "In Stock", "Flipkart"),
        ("Standard Edition", -5000, 4.3, 2400, "In Stock", "Amazon"),
        ("Lite Version", -8000, 4.1, 980, "In Stock", "Flipkart"),
        ("Value Pack", -10000, 4.0, 1500, "In Stock", "Amazon"),
        ("Budget Option", -12000, 3.9, 620, "Limited Stock", "Flipkart"),
    ]
    products = []
    for i, (label, offset, rating, reviews, avail, platform) in enumerate(product_variants):
        price = max(base_price + offset, 999)
        product = {
            "platform_product_id": f"DEMO{i:03d}",
            "name": f"[Demo] {query.title()} - {label}",
            "url": None,
            "price": price,
            "currency": "INR",
            "rating": rating,
            "review_count": reviews,
            "image_url": None,
            "availability": avail,
            "platform": platform,
            "category": category or "Electronics",
            "is_demo": True,
        }
        if i < 3:
            product["original_price"] = price + random.randint(2000, 8000)
        products.append(product)
    return products


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
