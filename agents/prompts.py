"""
Centralized prompt templates for all agents.
Keeps prompts organized, versioned, and easy to modify.
"""

# ============================================
# AGENT 1: QUERY HANDLER PROMPTS
# ============================================

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


# ============================================
# AGENT 4: CONSUMER RECOMMENDER PROMPTS
# ============================================

RECOMMENDATION_REASON_PROMPT = """You are a helpful shopping assistant. Based on the user's search and the product details, write a brief, helpful recommendation reason (1-2 sentences).

User searched for: "{query}"
User preferences: {preferences}

Product: {product_name}
Price: ${price}
Rating: {rating}/5 ({reviews} reviews)
Key features: {features}

Write a concise reason why this product is a good match for the user. Focus on value, quality, or specific features that match their needs."""


PRODUCT_COMPARISON_PROMPT = """Compare these products and explain which is better for the user's needs.

User is looking for: {query}

Product A: {product_a_name}
- Price: ${product_a_price}
- Rating: {product_a_rating}/5
- Features: {product_a_features}

Product B: {product_b_name}
- Price: ${product_b_price}
- Rating: {product_b_rating}/5
- Features: {product_b_features}

Provide a brief comparison (2-3 sentences) explaining which product better matches the user's needs and why."""


# ============================================
# AGENT 5: BUSINESS ANALYTICS PROMPTS
# ============================================

MARKET_ANALYSIS_PROMPT = """Analyze the following market data and provide business insights.

Category: {category}
Total Products Analyzed: {total_products}
Price Range: ${min_price} - ${max_price}
Average Price: ${avg_price}
Average Rating: {avg_rating}/5

Top Brands: {top_brands}
Price Distribution: {price_distribution}

Provide 3-4 key business insights about this market segment, including:
1. Market positioning opportunities
2. Price sensitivity analysis
3. Quality vs price relationship
4. Recommendations for businesses"""


COMPETITIVE_ANALYSIS_PROMPT = """Analyze the competitive landscape for {product_type} based on this data:

Platform Breakdown:
{platform_data}

Key Metrics by Platform:
{metrics_by_platform}

Provide competitive insights including:
1. Which platform has the best prices
2. Which platform has better product quality (ratings)
3. Market share observations
4. Strategic recommendations"""


TREND_ANALYSIS_PROMPT = """Analyze search trends and identify opportunities.

Search Data:
{search_data}

Top Searched Products: {top_products}
Emerging Categories: {emerging_categories}
Price Preferences: {price_preferences}

Provide trend analysis including:
1. What products are gaining popularity
2. Consumer price sensitivity trends
3. Feature preferences
4. Predicted future trends"""


# ============================================
# UTILITY PROMPTS
# ============================================

PRODUCT_DESCRIPTION_ENHANCEMENT_PROMPT = """Enhance this product description to be more informative and engaging.

Original: {original_description}
Product: {product_name}
Category: {category}
Price: ${price}

Write a clear, concise enhanced description (2-3 sentences) that highlights key benefits."""


CATEGORY_CLASSIFICATION_PROMPT = """Classify this product into the most appropriate category.

Product Name: {product_name}
Description: {description}

Available Categories:
- Computers (laptops, desktops, tablets)
- Smartphones (mobile phones, accessories)
- Audio (headphones, speakers, earbuds)
- Electronics (TVs, cameras, smart home)
- Home (appliances, furniture)
- Fashion (clothing, shoes, accessories)

Respond with ONLY the category name, nothing else."""


# ============================================
# PROMPT FORMATTING HELPERS
# ============================================

def format_query_extraction_prompt(query: str) -> str:
    """Format the query extraction prompt with user query."""
    return QUERY_EXTRACTION_PROMPT.format(query=query)


def format_recommendation_prompt(
    query: str,
    preferences: str,
    product_name: str,
    price: float,
    rating: float,
    reviews: int,
    features: str
) -> str:
    """Format the recommendation reason prompt."""
    return RECOMMENDATION_REASON_PROMPT.format(
        query=query,
        preferences=preferences,
        product_name=product_name,
        price=price,
        rating=rating,
        reviews=reviews,
        features=features
    )


def format_market_analysis_prompt(
    category: str,
    total_products: int,
    min_price: float,
    max_price: float,
    avg_price: float,
    avg_rating: float,
    top_brands: str,
    price_distribution: str
) -> str:
    """Format the market analysis prompt."""
    return MARKET_ANALYSIS_PROMPT.format(
        category=category,
        total_products=total_products,
        min_price=min_price,
        max_price=max_price,
        avg_price=avg_price,
        avg_rating=avg_rating,
        top_brands=top_brands,
        price_distribution=price_distribution
    )


def format_competitive_analysis_prompt(
    product_type: str,
    platform_data: str,
    metrics_by_platform: str
) -> str:
    """Format the competitive analysis prompt."""
    return COMPETITIVE_ANALYSIS_PROMPT.format(
        product_type=product_type,
        platform_data=platform_data,
        metrics_by_platform=metrics_by_platform
    )
