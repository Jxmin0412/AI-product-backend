"""
Consumer-facing API routes for product search and recommendations.
Uses the LangGraph workflow for AI-powered product discovery.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging

from pydantic import BaseModel, Field

from agents.workflow import get_workflow_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


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
async def search_products(request: SearchRequest):
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
        logger.info(f"Product search request: '{request.query}'")

        # Get workflow orchestrator
        orchestrator = get_workflow_orchestrator()

        # Run consumer search workflow
        result = await orchestrator.search_products(query=request.query)

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
            query=request.query,
            metadata=metadata,
            recommendations=recommendations,
            allResults=all_results,
            totalResults=len(all_results),
        )

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/search")
async def search_products_get(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
):
    """
    GET version of search for simple queries.
    """
    request = SearchRequest(query=q)
    return await search_products(request)


@router.get("/recommendations")
async def get_trending_recommendations(
    category: Optional[str] = Query(None, description="Category filter"),
    limit: int = Query(10, ge=1, le=20, description="Number of recommendations"),
):
    """
    Get trending/popular product recommendations.

    Uses a general query to fetch popular products in a category.
    """
    try:
        logger.info(f"Trending recommendations: category={category}, limit={limit}")

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

        return recommendations

    except Exception as e:
        logger.error(f"Recommendations error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.get("/compare")
async def compare_product_prices(
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
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


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
