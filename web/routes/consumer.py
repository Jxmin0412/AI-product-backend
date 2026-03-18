"""
Consumer-facing API routes for product search and recommendations.
Uses the LangGraph workflow for AI-powered product discovery.
"""
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from ai.workflow import get_workflow_orchestrator
from ai.scraper import get_product_scraper, PLATFORM_CONFIGS
from auth.dependencies import get_current_user, get_current_user_optional
from database.connection import get_db
from database.models import UserSearch
from consumer.schemas import (
    ProductResponse, SearchRequest, SearchMetadata, SearchResponse,
    ForYouResponse,
    PlatformPrice, PriceComparisonResponse,
    PlatformComparison, PriceRange, SmartComparisonResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Bounded cache for recommendations (LRU eviction at MAX_CACHE_ENTRIES)
_recommendations_cache: dict = {}
RECOMMENDATIONS_CACHE_TTL = 600  # 10 minutes
MAX_CACHE_ENTRIES = 100


def _cache_get(key: str):
    """Get from cache if not expired."""
    entry = _recommendations_cache.get(key)
    if entry and (time.time() - entry["timestamp"]) < RECOMMENDATIONS_CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data):
    """Set cache entry with LRU eviction when full."""
    # Evict oldest entries if at capacity
    if len(_recommendations_cache) >= MAX_CACHE_ENTRIES:
        oldest_key = min(_recommendations_cache, key=lambda k: _recommendations_cache[k]["timestamp"])
        del _recommendations_cache[oldest_key]
    _recommendations_cache[key] = {"data": data, "timestamp": time.time()}


# ============================================
# HELPERS
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
async def search_products(
    request: SearchRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """
    Search for products using AI-powered natural language processing.

    Pipeline: extract query -> scrape platforms -> process/deduplicate -> rank with LLM
    """
    try:
        logger.info(f"Product search request: '{request.query}'")

        orchestrator = get_workflow_orchestrator()
        result = await orchestrator.search_products(query=request.query)

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

        recommendations = [
            workflow_product_to_response(p, include_recommendation_fields=True)
            for p in result.get("recommendations", [])
        ]

        all_results = [
            workflow_product_to_response(p)
            for p in result.get("ranked_products", [])
        ]

        # Save search record with user_id and actual results
        try:
            # Store all ranked products as JSON for cross-user recommendations
            all_ranked = result.get("ranked_products") or result.get("recommendations") or []
            results_json = [
                {
                    "name": p.get("name"),
                    "price": p.get("price"),
                    "original_price": p.get("original_price"),
                    "discount_percent": p.get("discount_percent"),
                    "platform": p.get("platform"),
                    "platform_product_id": p.get("platform_product_id"),
                    "rating": p.get("rating"),
                    "review_count": p.get("review_count"),
                    "image_url": p.get("image_url"),
                    "url": p.get("url"),
                    "availability": p.get("availability"),
                    "brand": p.get("brand"),
                    "category": p.get("category"),
                    "features": p.get("features", []),
                    "description": p.get("description"),
                    "recommendation_score": p.get("recommendation_score"),
                    "reason": p.get("reason"),
                    "match_type": p.get("match_type"),
                }
                for p in all_ranked[:20]
            ] or None

            search_record = UserSearch(
                user_id=current_user.id if current_user else None,
                query_text=request.query,
                extracted_product_name=result.get("extracted_product_name"),
                extracted_category=result.get("extracted_category"),
                results_count=len(all_results),
                results_data=results_json,
                session_id=result.get("session_id"),
            )
            db.add(search_record)
            db.commit()
        except Exception as save_err:
            logger.warning(f"Failed to save search record: {save_err}")
            db.rollback()

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
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """GET version of search for simple queries."""
    request = SearchRequest(query=q)
    return await search_products(request, db=db, current_user=current_user)


@router.get("/recommendations")
async def get_trending_recommendations(
    category: Optional[str] = Query(None, description="Category filter"),
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations"),
):
    """
    Get trending/popular product recommendations.
    Results are cached for 10 minutes with bounded LRU cache.
    """
    try:
        cache_key = f"{category or 'all'}:{limit}"

        cached = _cache_get(cache_key)
        if cached is not None:
            logger.info(f"Returning cached recommendations for '{cache_key}'")
            return cached

        logger.info(f"Trending recommendations (cache miss): category={category}, limit={limit}")

        orchestrator = get_workflow_orchestrator()

        # Build specific queries per category for better relevance
        category_queries = {
            "Laptops": "top rated laptops 2025",
            "Audio": "best wireless headphones earbuds speakers",
            "Smartphones": "best smartphones mobiles 2025",
            "Electronics": "top electronics gadgets TV smartwatch",
            "Home": "best home appliances kitchen essentials",
            "Fashion": "trending fashion clothing accessories",
        }
        if category and category != "All":
            query = category_queries.get(category, f"best {category.lower()} products")
        else:
            query = "top rated trending products electronics gadgets"

        result = await orchestrator.search_products(query=query)

        recommendations = [
            workflow_product_to_response(p, include_recommendation_fields=True)
            for p in result.get("recommendations", [])[:limit]
        ]

        _cache_set(cache_key, recommendations)

        return recommendations

    except Exception as e:
        logger.error(f"Recommendations error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.get("/recommendations/for-you", response_model=ForYouResponse)
async def get_for_you_recommendations(
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations"),
    include_own: bool = Query(False, description="Include current user's own search results"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get personalized recommendations based on what users have been searching.
    Pulls actual saved search results from the DB — no re-scraping needed.
    Requires authentication.

    - include_own=false (default): only other users' results ("For You")
    - include_own=true: all users' results including own ("All" tab)
    """
    try:
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        # 1. Query saved searches with results
        search_query = (
            db.query(UserSearch)
            .filter(
                UserSearch.user_id.isnot(None),
                UserSearch.results_data.isnot(None),
                UserSearch.searched_at >= thirty_days_ago,
            )
        )

        if not include_own:
            search_query = search_query.filter(UserSearch.user_id != current_user.id)

        saved_searches = (
            search_query
            .order_by(UserSearch.searched_at.desc())
            .limit(50)
            .all()
        )

        # Related categories to supplement results
        RELATED_CATEGORIES = {
            "Audio": ["Electronics", "Smartphones"],
            "Smartphones": ["Electronics", "Audio"],
            "Electronics": ["Smartphones", "Audio", "Laptops"],
            "Laptops": ["Electronics", "Smartphones"],
            "Home": ["Electronics", "Fashion"],
            "Fashion": ["Home", "Electronics"],
        }

        # 2. Collect products from saved searches, deduplicate by name
        seen_names = set()
        collected_products = []
        searched_categories = set()

        if saved_searches:
            for search in saved_searches:
                if search.extracted_category:
                    searched_categories.add(search.extracted_category)
                if not search.results_data:
                    continue
                for product in search.results_data:
                    name_key = (product.get("name") or "").lower().strip()
                    if name_key and name_key not in seen_names:
                        seen_names.add(name_key)
                        collected_products.append(product)

        # 3. If not enough saved products, supplement with related categories
        if len(collected_products) < limit:
            related_cats = set()
            for cat in searched_categories:
                for rc in RELATED_CATEGORIES.get(cat, []):
                    related_cats.add(rc)
            # Also add general categories if still sparse
            if not related_cats:
                related_cats = {"Electronics", "Smartphones", "Audio"}

            for rel_cat in related_cats:
                if len(collected_products) >= limit:
                    break
                try:
                    extra = await get_trending_recommendations(category=rel_cat, limit=10)
                    for p in extra:
                        # extra items are ProductResponse objects, convert to dict
                        p_dict = p.model_dump() if hasattr(p, "model_dump") else p.__dict__ if hasattr(p, "__dict__") else p
                        name_key = (p_dict.get("name") or "").lower().strip()
                        if name_key and name_key not in seen_names:
                            seen_names.add(name_key)
                            # Map ProductResponse field names back to workflow dict keys
                            collected_products.append({
                                "name": p_dict.get("name"),
                                "price": p_dict.get("price"),
                                "original_price": p_dict.get("originalPrice") or p_dict.get("original_price"),
                                "discount_percent": p_dict.get("discountPercent") or p_dict.get("discount_percent"),
                                "platform": p_dict.get("platform"),
                                "platform_product_id": p_dict.get("platformProductId") or p_dict.get("platform_product_id"),
                                "rating": p_dict.get("rating"),
                                "review_count": p_dict.get("reviews") or p_dict.get("review_count"),
                                "image_url": p_dict.get("image") or p_dict.get("image_url"),
                                "url": p_dict.get("url"),
                                "availability": p_dict.get("availability"),
                                "brand": p_dict.get("brand"),
                                "category": p_dict.get("category"),
                                "features": p_dict.get("features", []),
                                "description": p_dict.get("description"),
                                "recommendation_score": p_dict.get("recommendation_score") or 50,
                                "reason": p_dict.get("reason"),
                                "match_type": p_dict.get("matchType") or p_dict.get("match_type"),
                            })
                except Exception as e:
                    logger.warning(f"Failed to fetch related products for {rel_cat}: {e}")

        if collected_products:
            # 4. Sort by recommendation_score, take top N
            collected_products.sort(
                key=lambda p: p.get("recommendation_score") or 0,
                reverse=True,
            )
            top_products = collected_products[:limit]

            recommendations = [
                workflow_product_to_response(p, include_recommendation_fields=True)
                for p in top_products
            ]

            top_category = max(searched_categories, key=lambda c: 1) if searched_categories else None
            has_other_users = saved_searches and any(s.user_id != current_user.id for s in saved_searches)

            if has_other_users:
                label = f"Based on what others are searching in {top_category}" if top_category else "Based on what others are searching"
                source = "other_users"
            else:
                label = "Recommended for you"
                source = "trending"

            logger.info(f"For-you: serving {len(recommendations)} products (saved + related, include_own={include_own})")
            return ForYouResponse(
                source=source,
                category=top_category,
                label=label,
                recommendations=recommendations,
            )

        # 5. Fallback: return general trending (runs live pipeline)
        logger.info("For-you: no saved results, returning general trending")
        recommendations = await get_trending_recommendations(category=None, limit=limit)
        return ForYouResponse(
            source="trending",
            category=None,
            label="Trending products",
            recommendations=recommendations,
        )

    except Exception as e:
        logger.error(f"For-you recommendations error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.get("/compare")
async def compare_product_prices(
    query: str = Query(..., description="Product name to compare"),
):
    """Compare prices for a specific product across platforms."""
    try:
        logger.info(f"Price comparison for: {query}")

        orchestrator = get_workflow_orchestrator()
        result = await orchestrator.search_products(query=query)

        products = result.get("deduplicated_products", [])

        if not products:
            raise HTTPException(status_code=404, detail="No products found for comparison")

        for product in products:
            if product.get("alternative_listings"):
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


# ============================================
# SMART COMPARISON HELPERS & ENDPOINTS
# ============================================

def _dict_to_comparison(d: dict, is_best: bool = False) -> PlatformComparison:
    """Convert a comparison dict to PlatformComparison response."""
    return PlatformComparison(
        platform=d.get("platform", "Unknown"),
        platformKey=d.get("platform_key"),
        productUrl=d.get("product_url") or d.get("url", ""),
        platformProductId=d.get("platform_product_id"),
        price=d.get("price", 0),
        originalPrice=d.get("original_price"),
        discountPercent=d.get("discount_percent"),
        currency=d.get("currency", "INR"),
        rating=d.get("rating"),
        reviewCount=d.get("review_count"),
        availability=d.get("availability"),
        seller=d.get("seller"),
        shippingInfo=d.get("shipping"),
        deliveryEstimate=d.get("delivery_estimate"),
        priceScore=d.get("price_score", 0),
        ratingScore=d.get("rating_score", 0),
        valueScore=d.get("value_score", 0),
        brandTrustScore=d.get("brand_trust_score", 0),
        comparisonRank=1 if is_best else d.get("comparison_rank", 0),
        isBestDeal=True if is_best else d.get("is_best_deal", False),
    )

@router.get("/search/compare", response_model=SmartComparisonResponse)
async def smart_compare_products(
    query: str = Query(..., min_length=1, max_length=500, description="Product search query"),
    platforms: Optional[str] = Query(None, description="Comma-separated platforms: amazon,snapdeal,vijaysales,shopclues"),
):
    """
    Search and compare a product across multiple e-commerce platforms.
    Uses LLM-powered extraction for intelligent scraping.
    """
    try:
        logger.info(f"Smart comparison request: query='{query}', platforms={platforms}")

        scraper = get_product_scraper()

        platform_list = None
        if platforms:
            platform_list = [p.strip().lower() for p in platforms.split(",")]

        result = await scraper.compare_products(query=query, platforms=platform_list)

        comparisons = [_dict_to_comparison(c) for c in result.comparisons]
        best_deal = _dict_to_comparison(result.best_deal, is_best=True) if result.best_deal else None

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

    except Exception as e:
        logger.error(f"Smart comparison error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@router.get("/platforms")
async def get_supported_platforms():
    """Get list of supported e-commerce platforms for comparison."""
    category_map = {
        "amazon": ["Electronics", "Computers", "Smartphones", "Home", "Fashion", "Books"],
        "snapdeal": ["Electronics", "Home", "Fashion", "Accessories", "Health"],
        "vijaysales": ["Electronics", "Smartphones", "Laptops", "Appliances", "Audio"],
        "shopclues": ["Electronics", "Home", "Fashion", "Accessories", "Lifestyle"],
    }

    platforms = []
    for key, config in PLATFORM_CONFIGS.items():
        platforms.append({
            "id": key,
            "name": config.name,
            "baseUrl": config.base_url,
            "trustScore": config.trust_score,
            "currency": config.currency,
            "categories": category_map.get(key, ["General"]),
        })

    return {"platforms": platforms}


@router.get("/scrape/url")
async def scrape_single_url(
    url: str = Query(..., description="URL to scrape"),
    platform: Optional[str] = Query(None, description="Platform hint (auto-detected if not provided)"),
):
    """Scrape a single product URL with LLM-powered extraction."""
    try:
        logger.info(f"Single URL scrape: {url}")

        scraper = get_product_scraper()
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
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")
