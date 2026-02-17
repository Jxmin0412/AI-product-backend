"""Centralized prompt templates for agents."""

QUERY_EXTRACTION_PROMPT = """You are a product search query analyzer. Extract structured information from the user's search query.

Analyze this query and extract:
1. product_type: The main product being searched (e.g., "laptop", "headphones", "phone")
2. category: Product category (Electronics, Audio, Computers, Smartphones, Home, Fashion, etc.)
3. brand: Any specific brand mentioned (e.g., "Apple", "Samsung", "Sony") or null
4. min_price: Minimum price if mentioned, as number only (no currency symbol)
5. max_price: Maximum price if mentioned, as number only
6. features: List of specific features/requirements (e.g., ["gaming", "16GB RAM", "noise cancelling"])
7. intent: One of: "product_search", "price_comparison", "recommendation", "market_analysis"

User Query: "{query}"

Respond ONLY with valid JSON, no other text:
{{"product_type": "...", "category": "...", "brand": null or "...", "min_price": null or number, "max_price": null or number, "features": [...], "intent": "..."}}"""


RECOMMENDATION_REASON_PROMPT = """You are a helpful shopping assistant. Based on the user's search and the product details, write a brief, helpful recommendation reason (1-2 sentences).

User searched for: "{query}"
User preferences: {preferences}

Product: {product_name}
Price: ${price}
Rating: {rating}/5 ({reviews} reviews)
Key features: {features}

Write a concise reason why this product is a good match for the user. Focus on value, quality, or specific features that match their needs."""


PRODUCT_EXTRACTION_PROMPT = """You are a product data extraction specialist. Extract structured product information from the following webpage content.

IMPORTANT: Return ONLY a valid JSON object, no other text or explanation.

Extract these fields:
- name, price (number only — strip currency symbols and commas), original_price (number or null), currency, rating (out of 5 or null)
- review_count (integer or null), availability, images (array of URLs starting with http), description
- seller (string or null), shipping, delivery_estimate (string or null)
- features (array of strings), brand (string or null)

PRICE PARSING: Indian Rupee (₹) uses comma format: ₹1,49,990 = 149990, ₹29,999 = 29999. Strip ALL commas and symbols.

Platform: {platform}
Page URL: {url}

Webpage content:
{content}

JSON Response:"""

SEARCH_RESULTS_EXTRACTION_PROMPT = """You are a product data extraction specialist. Extract ALL product listings from the following search results page.

IMPORTANT: Return ONLY a valid JSON array. Each element must have these fields:
- name (string, required) — full product name
- price (number, required) — current selling price as a plain number, NO currency symbols
- original_price (number or null) — original/MRP price before discount, as a plain number
- currency (string) — "INR" for Indian sites, "USD" otherwise
- rating (number or null) — rating out of 5
- review_count (integer or null) — number of reviews
- image_url (string or null) — product image URL (must start with http)
- url (string or null) — link to product detail page (relative or absolute)
- availability (string) — "In Stock", "Out of Stock", or "Unknown"
- platform_product_id (string or null) — any product/item ID visible in the URL or data

PRICE PARSING RULES (critical):
- Indian Rupee prices use ₹ symbol and Indian comma format: ₹1,49,990 means 149990, ₹29,999 means 29999
- Strip ALL commas and currency symbols before returning the number
- "₹1,49,990" → 149990, "₹29,999" → 29999, "₹999" → 999, "$49.99" → 49.99
- If you see a price like "1,49,990" or "29,999" without a symbol, it is still a valid price in INR
- NEVER return price as 0. If you cannot determine the price, omit that product entirely.

Extract up to {max_results} products. Skip sponsored/ad listings if identifiable.
Only include products with BOTH a name AND a valid non-zero price.

Platform: {platform}
Search query: {query}

Page content:
{content}

JSON Array Response:"""


COMPARISON_RECOMMENDATION_PROMPT = """Based on the following product comparison data across multiple platforms, provide a brief recommendation (2-3 sentences).

Consider: Price, Rating, Availability, Platform reliability, Shipping/delivery time.

Product: {product_name}

Comparison Data:
{comparison_data}

Provide a concise recommendation:"""
