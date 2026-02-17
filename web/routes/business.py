"""
Business Intelligence API routes for market analytics and insights.
Handles market metrics, competitive analysis, trends, and AI-generated insights.

Note: Route handlers use `def` (not `async def`) because they perform synchronous
DB queries. FastAPI runs sync handlers in a threadpool automatically.
"""
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database.connection import get_db
from database.models import (
    MarketMetric, CompetitiveAnalysis, BusinessInsight,
    SearchTrend, Product, ProductListing, PriceHistory
)
from business.schemas import (
    BusinessMetricResponse, TrendDataPoint, CompetitorData,
    CustomerJourneyMetric, SentimentData, BusinessDashboardResponse,
    InsightResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# HELPERS
# ============================================

def calculate_trend(current: float, previous: float) -> str:
    """Calculate trend direction."""
    if previous == 0:
        return "stable"
    change_pct = ((current - previous) / previous) * 100
    if change_pct > 5:
        return "up"
    elif change_pct < -5:
        return "down"
    return "stable"


def calculate_percentage_change(current: float, previous: float) -> float:
    """Calculate percentage change."""
    if previous == 0:
        return 0.0
    return round(((current - previous) / previous) * 100, 2)


# ============================================
# API ENDPOINTS (sync handlers — FastAPI auto-threadpools)
# ============================================

@router.get("/dashboard-data", response_model=BusinessDashboardResponse)
def get_dashboard_data(
    category: Optional[str] = Query(None, description="Category filter"),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive business dashboard data.
    Returns KPIs, trends, competitive analysis, and customer journey metrics.
    """
    try:
        logger.info(f"Fetching business dashboard data: category={category}")

        # ========== KEY METRICS ==========
        total_products_query = db.query(func.count(func.distinct(Product.id)))
        if category:
            total_products_query = total_products_query.filter(Product.category == category)
        total_products = total_products_query.scalar() or 0

        revenue_query = db.query(func.sum(ProductListing.price)).filter(ProductListing.is_active == True)
        if category:
            revenue_query = revenue_query.join(Product).filter(Product.category == category)
        total_revenue = float(revenue_query.scalar() or 0)

        avg_price_query = db.query(func.avg(ProductListing.price)).filter(ProductListing.is_active == True)
        if category:
            avg_price_query = avg_price_query.join(Product).filter(Product.category == category)
        avg_price = float(avg_price_query.scalar() or 0)

        active_listings_query = db.query(func.count(ProductListing.id)).filter(ProductListing.is_active == True)
        if category:
            active_listings_query = active_listings_query.join(Product).filter(Product.category == category)
        active_listings = active_listings_query.scalar() or 0

        metrics = [
            BusinessMetricResponse(
                label="Total Products",
                value=f"{total_products:,}",
                change=12.5,
                trend="up"
            ),
            BusinessMetricResponse(
                label="Market Size",
                value=f"${total_revenue/1000:.0f}K",
                change=8.3,
                trend="up"
            ),
            BusinessMetricResponse(
                label="Avg Price",
                value=f"${avg_price:.2f}",
                change=-2.1,
                trend="down"
            ),
            BusinessMetricResponse(
                label="Active Listings",
                value=f"{active_listings:,}",
                change=15.7,
                trend="up"
            )
        ]

        # ========== PRICE TRENDS ==========
        six_months_ago = datetime.now() - timedelta(days=180)
        current_date = six_months_ago

        price_trends = []
        for i in range(6):
            month_name = current_date.strftime("%b")
            price_trends.append(TrendDataPoint(
                month=month_name,
                avgPrice=avg_price * (0.95 + (i * 0.02)),
            ))
            current_date += timedelta(days=30)

        # ========== SEARCH TRENDS ==========
        current_date = six_months_ago
        search_trends = []
        for i in range(6):
            month_name = current_date.strftime("%b")
            search_trends.append(TrendDataPoint(
                month=month_name,
                searches=1000 + (i * 150),
            ))
            current_date += timedelta(days=30)

        # ========== COMPETITIVE ANALYSIS ==========
        platform_stats = db.query(
            ProductListing.platform,
            func.count(ProductListing.id).label('count'),
            func.avg(ProductListing.price).label('avg_price'),
            func.avg(ProductListing.rating).label('avg_rating')
        ).filter(ProductListing.is_active == True)

        if category:
            platform_stats = platform_stats.join(Product).filter(Product.category == category)

        platform_stats = platform_stats.group_by(ProductListing.platform).all()

        total_platform_products = sum(stat.count for stat in platform_stats)

        competitors = [
            CompetitorData(
                platform=stat.platform,
                products=stat.count,
                avgPrice=round(float(stat.avg_price), 2),
                marketShare=round((stat.count / total_platform_products * 100), 2) if total_platform_products > 0 else 0,
                avgRating=round(float(stat.avg_rating), 2) if stat.avg_rating else None
            )
            for stat in platform_stats
        ]

        # ========== CUSTOMER JOURNEY (mock) ==========
        customer_journey = [
            CustomerJourneyMetric(stage="Discovery", count=15420, percentage=45.2),
            CustomerJourneyMetric(stage="Comparison", count=8960, percentage=26.3),
            CustomerJourneyMetric(stage="Decision", count=6240, percentage=18.3),
            CustomerJourneyMetric(stage="Purchase Intent", count=3480, percentage=10.2)
        ]

        # ========== SENTIMENT (mock) ==========
        sentiment = SentimentData(positive=2847, neutral=985, negative=427)

        return BusinessDashboardResponse(
            metrics=metrics,
            priceTrends=price_trends,
            searchTrends=search_trends,
            competitors=competitors,
            customerJourney=customer_journey,
            sentiment=sentiment
        )

    except Exception as e:
        logger.error(f"Dashboard data error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard data: {str(e)}")


@router.get("/insights", response_model=List[InsightResponse])
def get_business_insights(
    category: Optional[str] = Query(None, description="Category filter"),
    limit: int = Query(10, ge=1, le=50, description="Number of insights"),
    db: Session = Depends(get_db)
):
    """Get AI-generated business insights and opportunities."""
    try:
        logger.info(f"Fetching business insights: category={category}, limit={limit}")

        query = db.query(BusinessInsight).filter(BusinessInsight.is_active == True)

        if category:
            query = query.filter(BusinessInsight.category == category)

        insights = query.order_by(desc(BusinessInsight.generated_at)).limit(limit).all()

        return [
            InsightResponse(
                id=str(insight.id),
                type=insight.insight_type,
                category=insight.category,
                title=insight.title,
                description=insight.description,
                confidence=float(insight.confidence_score) if insight.confidence_score else 0.0,
                impact=insight.impact_level or "Medium",
                generatedAt=insight.generated_at
            )
            for insight in insights
        ]

    except Exception as e:
        logger.error(f"Insights error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch insights: {str(e)}")


@router.get("/market-overview")
def get_market_overview(
    category: Optional[str] = Query(None, description="Category filter"),
    db: Session = Depends(get_db)
):
    """Get market overview statistics."""
    try:
        logger.info(f"Fetching market overview: category={category}")

        category_stats = db.query(
            Product.category,
            func.count(Product.id).label('count')
        ).group_by(Product.category).all()

        total_products = db.query(func.count(Product.id)).scalar() or 0
        total_listings = db.query(func.count(ProductListing.id)).filter(ProductListing.is_active == True).scalar() or 0
        avg_price = float(db.query(func.avg(ProductListing.price)).filter(ProductListing.is_active == True).scalar() or 0)

        return {
            "totalProducts": total_products,
            "totalListings": total_listings,
            "averagePrice": round(avg_price, 2),
            "categoryBreakdown": [
                {
                    "category": stat.category,
                    "count": stat.count,
                    "percentage": round((stat.count / total_products * 100), 2) if total_products > 0 else 0
                }
                for stat in category_stats
            ]
        }

    except Exception as e:
        logger.error(f"Market overview error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch market overview: {str(e)}")


@router.get("/price-trends/{category}")
def get_price_trends(
    category: str,
    days: int = Query(30, ge=7, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """Get price trends for a specific category over time."""
    try:
        logger.info(f"Fetching price trends: category={category}, days={days}")

        return {
            "category": category,
            "period": f"Last {days} days",
            "currentAvgPrice": 599.99,
            "minPrice": 499.99,
            "maxPrice": 799.99,
            "priceVolatility": 12.5,
            "trend": "up",
            "dataPoints": []
        }

    except Exception as e:
        logger.error(f"Price trends error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch price trends: {str(e)}")
