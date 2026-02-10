"""
Consumer-facing API routes for product search and recommendations.
Uses the LangGraph workflow for AI-powered product discovery.
"""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
import logging
import time

from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from agents.workflow import get_workflow_orchestrator

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

# In-memory cache for recommendations (avoids repeated LLM calls on page load)
_recommendations_cache: dict = {}  # key -> {"data": ..., "timestamp": ...}
RECOMMENDATIONS_CACHE_TTL = 600  # 10 minutes


# ============================================
# PYDANTIC MODELS (Request/Response Schemas)
# ============================================

class ProductResponse(BaseModel):
    """Product information response."""
    id: Optional[str] = None
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    price: float
    originalPrice: Optional[float] = None
    discountPercent: Optional[float] = None
    platform: str
    platformProductId: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    image: Optional[str] = None
    url: Optional[str] = None
    availability: str = "Unknown"
    shippingCost: Optional[float] = None
    deliveryDays: Optional[int] = None
    brand: Optional[str] = None
    features: List[str] = []
    matchType: Optional[str] = None
    rank: Optional[int] = None
    reason: Optional[str] = None
    alternativeListings: Optional[List[dict]] = None


class SearchRequest(BaseModel):
    """Product search request."""
    query: str = Field(..., min_length=1, max_length=500, description="Natural language search query")
    platforms: Optional[List[str]] = Field(None, description="Specific platforms to search")


class SearchMetadata(BaseModel):
    """Metadata about the search processing."""
    sessionId: str
    extractedProduct: Optional[str] = None
    extractedCategory: Optional[str] = None
    extractedBrand: Optional[str] = None
    extractedFeatures: List[str] = []
    priceRange: Optional[dict] = None
    intent: Optional[str] = None
    processingErrors: List[str] = []


class SearchResponse(BaseModel):
    """Product search response with recommendations."""
    query: str
    metadata: SearchMetadata
    recommendations: List[ProductResponse]
    allResults: List[ProductResponse]
    totalResults: int


class PlatformPrice(BaseModel):
    """Price info for a specific platform."""
    platform: str
    price: float
    url: Optional[str] = None


class PriceComparisonResponse(BaseModel):
    """Price comparison for a product across platforms."""
    productName: str
    prices: List[PlatformPrice]
    lowestPrice: float
    highestPrice: float
    priceDifference: float


# ============================================
# NEW COMPARISON SCHEMAS (SmartScraper)
# ============================================

class PlatformComparison(BaseModel):
    """Detailed comparison data for a single platform."""
    platform: str
    platformKey: Optional[str] = None
    productUrl: str
    platformProductId: Optional[str] = None
    price: float
    originalPrice: Optional[float] = None
    discountPercent: Optional[float] = None
    currency: str = "INR"
    rating: Optional[float] = None
    reviewCount: Optional[int] = None
    availability: Optional[str] = None
    seller: Optional[str] = None
    shippingInfo: Optional[str] = None
    deliveryEstimate: Optional[str] = None
    priceScore: float = 0
    ratingScore: float = 0
    valueScore: float = 0
    brandTrustScore: float = 0
    comparisonRank: int
    isBestDeal: bool = False


class PriceRange(BaseModel):
    """Price range for comparison."""
    min: float
    max: float


class SmartComparisonResponse(BaseModel):
    """Full comparison response from SmartScraper."""
    productName: str
    query: str
    comparisons: List[PlatformComparison]
    bestDeal: Optional[PlatformComparison] = None
    priceRange: PriceRange
    images: List[str] = []
    recommendation: str
    totalPlatforms: int


class ProductImageResponse(BaseModel):
    """Product image response."""
    id: Optional[str] = None
    imageUrl: str
    imageType: str = "primary"
    altText: Optional[str] = None
    sourcePlatform: Optional[str] = None
    displayOrder: int = 0


# ============================================
# HELPER FUNCTIONS
# ============================================

def workflow_product_to_response(product: dict, include_recommendation_fields: bool = False) -> ProductResponse:
    """Convert workflow product dict to API response format."""
    response = ProductResponse(
        id=product.get("platform_product_id") or product.get("id"),
        name=product.get("name", "Unknown Product"),
        category=product.get("category"),
        description=product.get("description"),
        price=product.get("price", 0),
        originalPrice=product.get("original_price"),
        discountPercent=product.get("discount_percent"),
        platform=product.get("platform", "Unknown"),
        platformProductId=product.get("platform_product_id"),
        rating=product.get("rating"),
        reviews=product.get("review_count"),
        image=product.get("image_url"),
        url=product.get("url"),
        availability=product.get("availability", "Unknown"),
        shippingCost=product.get("shipping_cost"),
        deliveryDays=product.get("delivery_days"),
        brand=product.get("brand"),
        features=product.get("features", []),
        alternativeListings=product.get("alternative_listings"),
    )

    if include_recommendation_fields:
        response.matchType = product.get("match_type")
        response.rank = product.get("rank")
        response.reason = product.get("reason")

    return response


# ============================================
# API ENDPOINTS
# ============================================

@router.post("/search", response_model=SearchResponse)
@limiter.limit("10/minute")
async def search_products(request: Request, search_body: SearchRequest):
    """
    Search for products using AI-powered natural language processing.

    This endpoint:
    1. Extracts product info, category, price range from natural language query
    2. Scrapes real-time data from e-commerce platforms (Amazon, Flipkart)
    3. Processes and deduplicates results
    4. Returns AI-ranked recommendations with explanations

    Example queries:
    - "gaming laptop under $1000"
    - "best wireless headphones with noise cancelling"
    - "Samsung phone between $500 and $800"
    """
    try:
        logger.info(f"Product search request: '{search_body.query}'")

        # Get workflow orchestrator
        orchestrator = get_workflow_orchestrator()

        # Run consumer search workflow
        result = await orchestrator.search_products(query=search_body.query)

        # Build metadata
        price_range = None
        if result.get("extracted_price_range"):
            min_p, max_p = result["extracted_price_range"]
            price_range = {"min": min_p, "max": max_p}

        metadata = SearchMetadata(
            sessionId=result.get("session_id", ""),
            extractedProduct=result.get("extracted_product_name"),
            extractedCategory=result.get("extracted_category"),
            extractedBrand=result.get("extracted_brand"),
            extractedFeatures=result.get("extracted_features", []),
            priceRange=price_range,
            intent=result.get("query_intent"),
            processingErrors=result.get("errors", []) + result.get("scraping_errors", []),
        )

        # Convert recommendations
        recommendations = [
            workflow_product_to_response(p, include_recommendation_fields=True)
            for p in result.get("recommendations", [])
        ]

        # Convert all ranked results
        all_results = [
            workflow_product_to_response(p)
            for p in result.get("ranked_products", [])
        ]

        return SearchResponse(
            query=search_body.query,
            metadata=metadata,
            recommendations=recommendations,
            allResults=all_results,
            totalResults=len(all_results),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed due to an internal error")


@router.get("/search")
@limiter.limit("10/minute")
async def search_products_get(
    request: Request,
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
):
    """
    GET version of search for simple queries.
    """
    search_body = SearchRequest(query=q)
    return await search_products(request, search_body)


@router.get("/recommendations")
@limiter.limit("10/minute")
async def get_trending_recommendations(
    request: Request,
    category: Optional[str] = Query(None, description="Category filter"),
    limit: int = Query(10, ge=1, le=20, description="Number of recommendations"),
):
    """
    Get trending/popular product recommendations.

    Uses a general query to fetch popular products in a category.
    Results are cached for 10 minutes to avoid exhausting LLM calls on page loads.
    """
    try:
        cache_key = f"{category or 'all'}:{limit}"
        now = time.time()

        # Return cached data if fresh
        if cache_key in _recommendations_cache:
            entry = _recommendations_cache[cache_key]
            age = now - entry["timestamp"]
            if age < RECOMMENDATIONS_CACHE_TTL:
                logger.info(f"Returning cached recommendations for '{cache_key}' (age: {int(age)}s)")
                return entry["data"]

        logger.info(f"Trending recommendations (cache miss): category={category}, limit={limit}")

        orchestrator = get_workflow_orchestrator()

        # Build query based on category
        if category and category != "All":
            query = f"best {category.lower()} products"
        else:
            query = "popular tech products"

        result = await orchestrator.search_products(query=query)

        recommendations = [
            workflow_product_to_response(p, include_recommendation_fields=True)
            for p in result.get("recommendations", [])[:limit]
        ]

        # Cache the result
        _recommendations_cache[cache_key] = {
            "data": recommendations,
            "timestamp": now,
        }

        return recommendations

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Recommendations error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get recommendations")


@router.get("/compare")
@limiter.limit("10/minute")
async def compare_product_prices(
    request: Request,
    query: str = Query(..., description="Product name to compare"),
):
    """
    Compare prices for a specific product across platforms.

    Searches for the product and returns price comparison.
    """
    try:
        logger.info(f"Price comparison for: {query}")

        orchestrator = get_workflow_orchestrator()

        result = await orchestrator.search_products(query=query)

        products = result.get("deduplicated_products", [])

        if not products:
            raise HTTPException(status_code=404, detail="No products found for comparison")

        # Find products with alternative listings
        for product in products:
            if product.get("alternative_listings"):
                # This product has cross-platform data
                all_prices = [
                    PlatformPrice(
                        platform=product["platform"],
                        price=product["price"],
                        url=product.get("url")
                    )
                ]
                for alt in product["alternative_listings"]:
                    all_prices.append(
                        PlatformPrice(
                            platform=alt["platform"],
                            price=alt["price"],
                            url=alt.get("url")
                        )
                    )

                prices_only = [p.price for p in all_prices]
                return PriceComparisonResponse(
                    productName=product["name"],
                    prices=all_prices,
                    lowestPrice=min(prices_only),
                    highestPrice=max(prices_only),
                    priceDifference=max(prices_only) - min(prices_only),
                )

        # No cross-platform data, return single platform
        product = products[0]
        return PriceComparisonResponse(
            productName=product["name"],
            prices=[
                PlatformPrice(
                    platform=product["platform"],
                    price=product["price"],
                    url=product.get("url")
                )
            ],
            lowestPrice=product["price"],
            highestPrice=product["price"],
            priceDifference=0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comparison error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Comparison failed due to an internal error")


@router.get("/categories")
async def get_categories():
    """Get available product categories."""
    return {
        "categories": [
            {"id": "all", "name": "All", "icon": "grid"},
            {"id": "computers", "name": "Computers", "icon": "laptop"},
            {"id": "smartphones", "name": "Smartphones", "icon": "smartphone"},
            {"id": "audio", "name": "Audio", "icon": "headphones"},
            {"id": "electronics", "name": "Electronics", "icon": "tv"},
            {"id": "home", "name": "Home", "icon": "home"},
            {"id": "fashion", "name": "Fashion", "icon": "shirt"},
        ]
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "consumer-api"}


# ============================================
# NEW SMART COMPARISON ENDPOINTS
# ============================================

@router.get("/search/compare", response_model=SmartComparisonResponse)
@limiter.limit("5/minute")
async def smart_compare_products(
    request: Request,
    query: str = Query(..., min_length=1, max_length=500, description="Product search query"),
    platforms: Optional[str] = Query(
        None,
        description="Comma-separated platforms: amazon,flipkart,myntra,ajio,croma,reliance_digital"
    ),
):
    """
    Search and compare a product across multiple e-commerce platforms.

    Uses LLM-powered extraction (Firecrawl-inspired) for intelligent scraping.
    Returns comparison scores, best deal recommendation, and all platform prices.

    Supported platforms:
    - amazon: Amazon India
    - flipkart: Flipkart
    - myntra: Myntra (fashion)
    - ajio: Ajio (fashion)
    - croma: Croma (electronics)
    - reliance_digital: Reliance Digital (electronics)

    Example: /search/compare?query=iPhone 15&platforms=amazon,flipkart,croma
    """
    try:
        logger.info(f"Smart comparison request: query='{query}', platforms={platforms}")

        # Import SmartScraper
        from services.smart_scraper import get_smart_scraper

        scraper = get_smart_scraper()

        # Parse platforms
        platform_list = None
        if platforms:
            platform_list = [p.strip().lower() for p in platforms.split(",")]

        # Run comparison
        result = await scraper.compare_products(
            query=query,
            platforms=platform_list
        )

        # Convert to response models
        comparisons = []
        for comp in result.comparisons:
            comparisons.append(PlatformComparison(
                platform=comp.get("platform", "Unknown"),
                platformKey=comp.get("platform_key"),
                productUrl=comp.get("product_url") or comp.get("url", ""),
                platformProductId=comp.get("platform_product_id"),
                price=comp.get("price", 0),
                originalPrice=comp.get("original_price"),
                discountPercent=comp.get("discount_percent"),
                currency=comp.get("currency", "INR"),
                rating=comp.get("rating"),
                reviewCount=comp.get("review_count"),
                availability=comp.get("availability"),
                seller=comp.get("seller"),
                shippingInfo=comp.get("shipping"),
                deliveryEstimate=comp.get("delivery_estimate"),
                priceScore=comp.get("price_score", 0),
                ratingScore=comp.get("rating_score", 0),
                valueScore=comp.get("value_score", 0),
                brandTrustScore=comp.get("brand_trust_score", 0),
                comparisonRank=comp.get("comparison_rank", 0),
                isBestDeal=comp.get("is_best_deal", False),
            ))

        # Best deal
        best_deal = None
        if result.best_deal:
            best_deal = PlatformComparison(
                platform=result.best_deal.get("platform", "Unknown"),
                platformKey=result.best_deal.get("platform_key"),
                productUrl=result.best_deal.get("product_url") or result.best_deal.get("url", ""),
                platformProductId=result.best_deal.get("platform_product_id"),
                price=result.best_deal.get("price", 0),
                originalPrice=result.best_deal.get("original_price"),
                discountPercent=result.best_deal.get("discount_percent"),
                currency=result.best_deal.get("currency", "INR"),
                rating=result.best_deal.get("rating"),
                reviewCount=result.best_deal.get("review_count"),
                availability=result.best_deal.get("availability"),
                seller=result.best_deal.get("seller"),
                shippingInfo=result.best_deal.get("shipping"),
                deliveryEstimate=result.best_deal.get("delivery_estimate"),
                priceScore=result.best_deal.get("price_score", 0),
                ratingScore=result.best_deal.get("rating_score", 0),
                valueScore=result.best_deal.get("value_score", 0),
                brandTrustScore=result.best_deal.get("brand_trust_score", 0),
                comparisonRank=1,
                isBestDeal=True,
            )

        return SmartComparisonResponse(
            productName=result.product_name,
            query=result.query,
            comparisons=comparisons,
            bestDeal=best_deal,
            priceRange=PriceRange(
                min=result.price_range.get("min", 0),
                max=result.price_range.get("max", 0)
            ),
            images=result.images,
            recommendation=result.recommendation,
            totalPlatforms=len(comparisons),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Smart comparison error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Comparison failed due to an internal error")


@router.get("/platforms")
async def get_supported_platforms():
    """Get list of supported e-commerce platforms for comparison."""
    from services.smart_scraper import PLATFORM_CONFIGS

    platforms = []
    for key, config in PLATFORM_CONFIGS.items():
        platforms.append({
            "id": key,
            "name": config.name,
            "baseUrl": config.base_url,
            "trustScore": config.trust_score,
            "currency": config.currency,
            "categories": _get_platform_categories(key),
        })

    return {"platforms": platforms}


def _get_platform_categories(platform: str) -> List[str]:
    """Get supported categories for a platform."""
    category_map = {
        "amazon": ["Electronics", "Computers", "Smartphones", "Home", "Fashion", "Books"],
        "flipkart": ["Electronics", "Computers", "Smartphones", "Home", "Fashion", "Appliances"],
        "myntra": ["Fashion", "Footwear", "Accessories", "Beauty"],
        "ajio": ["Fashion", "Footwear", "Accessories"],
        "croma": ["Electronics", "Smartphones", "Computers", "Appliances", "Audio"],
        "reliance_digital": ["Electronics", "Smartphones", "Computers", "Appliances", "Audio"],
    }
    return category_map.get(platform, ["General"])


@router.get("/scrape/url")
@limiter.limit("5/minute")
async def scrape_single_url(
    request: Request,
    url: str = Query(..., description="URL to scrape"),
    platform: Optional[str] = Query(None, description="Platform hint (auto-detected if not provided)"),
):
    """
    Scrape a single product URL with LLM-powered extraction.

    Extracts structured product data from any supported e-commerce product page.
    """
    try:
        logger.info(f"Single URL scrape: {url}")

        from services.smart_scraper import get_smart_scraper

        scraper = get_smart_scraper()
        result = await scraper.scrape_url(url=url, platform=platform)

        if not result:
            raise HTTPException(status_code=404, detail="Could not extract product data from URL")

        return {
            "success": True,
            "data": result,
            "platform": result.get("platform", "unknown"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"URL scrape error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Scraping failed due to an internal error")
