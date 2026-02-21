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
Price: {price}
Rating: {rating}/5 ({reviews} reviews)
Key features: {features}

Write a concise, specific reason why this product is a good match. Mention the product's standout qualities — its rating, price, specific features, or brand reputation. Do NOT be generic."""


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

SEARCH_RESULTS_EXTRACTION_PROMPT = """You are a product data extraction specialist. Extract ALL product listings from the search results below.

CRITICAL RULES:
1. Return ONLY a valid JSON array — no explanation, no markdown fences, just the array.
2. Extract EVERY visible product (up to {max_results}). Do NOT skip products.
3. Each product MUST have "name" (string) and "price" (number > 0). Omit products missing either.
4. If the content has sections like "=== PRODUCT N ===" with pre-extracted URLs and images, use those EXACT URLs — do NOT guess or fabricate URLs.

FIELDS per product:
- name (string, required) — full product name as shown
- price (number, required) — selling price as plain number, NO currency symbols
- original_price (number or null) — MRP/original price before discount
- currency (string) — "INR" for Indian sites
- rating (number or null) — rating out of 5
- review_count (integer or null) — number of reviews/ratings
- image_url (string or null) — product image URL from the content (must start with http). Use the "Product Image URL" if provided.
- url (string or null) — product detail page link. Use the "Product URL" if provided.
- availability (string) — "In Stock", "Out of Stock", or "Unknown"
- platform_product_id (string or null) — product/item ID from URL

PRICE PARSING (Indian Rupee):
- ₹1,49,990 → 149990, ₹29,999 → 29999, ₹999 → 999
- Strip ALL commas and currency symbols. NEVER return price as 0.

Platform: {platform}
Search query: {query}

Content:
{content}

JSON Array:"""


COMPARISON_RECOMMENDATION_PROMPT = """Based on the following product comparison data across multiple platforms, provide a brief recommendation (2-3 sentences).

Consider: Price, Rating, Availability, Platform reliability, Shipping/delivery time.

Product: {product_name}

Comparison Data:
{comparison_data}

Provide a concise recommendation:"""
