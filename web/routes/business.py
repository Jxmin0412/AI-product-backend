"""
Business Intelligence API routes — real analytics from user_searches + users tables.

Note: Route handlers use `def` (not `async def`) because they perform synchronous
DB queries. FastAPI runs sync handlers in a threadpool automatically.
"""
from datetime import datetime, timedelta
from typing import List
from collections import defaultdict
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, cast, Date

from database.connection import get_db
from database.models import UserSearch
from user_management.models import User
from user_management.rbac import require_admin
from business.schemas import (
    BusinessMetricResponse, DailySearchVolume, CompetitorData,
    TopSearchTerm, UserActivityItem, CategoryBreakdown,
    PriceInsight, BusinessDashboardResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_products_from_results(db: Session):
    """Extract individual product dicts from results_data JSONB across all searches."""
    rows = (
        db.query(UserSearch.results_data)
        .filter(UserSearch.results_data.isnot(None))
        .all()
    )
    products = []
    for (results_data,) in rows:
        if isinstance(results_data, list):
            products.extend(results_data)
        elif isinstance(results_data, dict):
            # Handle possible {"products": [...]} wrapper
            inner = results_data.get("products", results_data.get("results", []))
            if isinstance(inner, list):
                products.extend(inner)
    return products


@router.get("/dashboard-data", response_model=BusinessDashboardResponse)
def get_dashboard_data(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    Get comprehensive business dashboard data derived from real user search activity.
    Requires admin role.
    """
    try:
        logger.info("Fetching real business dashboard data")

        # ========== KEY METRICS ==========
        total_searches = db.query(func.count(UserSearch.id)).scalar() or 0

        active_users = (
            db.query(func.count(func.distinct(UserSearch.user_id)))
            .filter(UserSearch.user_id.isnot(None))
            .scalar() or 0
        )

        avg_results = float(
            db.query(func.avg(UserSearch.results_count))
            .filter(UserSearch.results_count.isnot(None))
            .scalar() or 0
        )

        top_category_row = (
            db.query(UserSearch.extracted_category, func.count(UserSearch.id).label("cnt"))
            .filter(UserSearch.extracted_category.isnot(None))
            .group_by(UserSearch.extracted_category)
            .order_by(desc("cnt"))
            .first()
        )
        top_category = top_category_row[0] if top_category_row else "N/A"

        # Compute simple week-over-week change for total searches
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        two_weeks_ago = datetime.utcnow() - timedelta(days=14)
        this_week = (
            db.query(func.count(UserSearch.id))
            .filter(UserSearch.searched_at >= one_week_ago)
            .scalar() or 0
        )
        last_week = (
            db.query(func.count(UserSearch.id))
            .filter(UserSearch.searched_at >= two_weeks_ago, UserSearch.searched_at < one_week_ago)
            .scalar() or 0
        )
        search_change = round(((this_week - last_week) / last_week * 100), 1) if last_week > 0 else 0.0

        metrics = [
            BusinessMetricResponse(
                label="Total Searches",
                value=f"{total_searches:,}",
                change=search_change,
                trend="up" if search_change > 0 else ("down" if search_change < 0 else "stable"),
            ),
            BusinessMetricResponse(
                label="Active Users",
                value=str(active_users),
                change=0.0,
                trend="stable",
            ),
            BusinessMetricResponse(
                label="Avg Results/Search",
                value=f"{avg_results:.1f}",
                change=0.0,
                trend="stable",
            ),
            BusinessMetricResponse(
                label="Top Category",
                value=top_category,
                change=0.0,
                trend="stable",
            ),
        ]

        # ========== DAILY SEARCH VOLUME (last 30 days) ==========
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        daily_rows = (
            db.query(
                cast(UserSearch.searched_at, Date).label("day"),
                func.count(UserSearch.id).label("cnt"),
            )
            .filter(UserSearch.searched_at >= thirty_days_ago)
            .group_by("day")
            .order_by("day")
            .all()
        )
        # Fill in missing days with 0 so the chart has no gaps
        day_map = {row.day: row.cnt for row in daily_rows}
        daily_search_volume = []
        for i in range(30):
            d = (datetime.utcnow() - timedelta(days=29 - i)).date()
            daily_search_volume.append(
                DailySearchVolume(
                    date=d.strftime("%b %d"),
                    searches=day_map.get(d, 0),
                )
            )

        # ========== CATEGORY BREAKDOWN ==========
        cat_rows = (
            db.query(
                UserSearch.extracted_category,
                func.count(UserSearch.id).label("cnt"),
            )
            .filter(UserSearch.extracted_category.isnot(None))
            .group_by(UserSearch.extracted_category)
            .order_by(desc("cnt"))
            .all()
        )
        total_categorised = sum(r.cnt for r in cat_rows) or 1
        category_breakdown = [
            CategoryBreakdown(
                category=row.extracted_category,
                count=row.cnt,
                percentage=round(row.cnt / total_categorised * 100, 1),
            )
            for row in cat_rows
        ]

        # ========== TOP SEARCH TERMS ==========
        term_rows = (
            db.query(
                func.coalesce(UserSearch.extracted_product_name, UserSearch.query_text).label("term"),
                UserSearch.extracted_category,
                func.count(UserSearch.id).label("cnt"),
            )
            .group_by("term", UserSearch.extracted_category)
            .order_by(desc("cnt"))
            .limit(10)
            .all()
        )
        top_search_terms = [
            TopSearchTerm(
                term=row.term,
                category=row.extracted_category,
                count=row.cnt,
            )
            for row in term_rows
        ]

        # ========== PLATFORM PERFORMANCE (from results_data JSONB) ==========
        products = _extract_products_from_results(db)
        platform_stats: dict = defaultdict(lambda: {"prices": [], "ratings": [], "count": 0})
        for p in products:
            plat = p.get("platform") or p.get("source") or "Unknown"
            price = p.get("price")
            rating = p.get("rating")
            platform_stats[plat]["count"] += 1
            if price is not None:
                try:
                    platform_stats[plat]["prices"].append(float(price))
                except (ValueError, TypeError):
                    pass
            if rating is not None:
                try:
                    platform_stats[plat]["ratings"].append(float(rating))
                except (ValueError, TypeError):
                    pass

        total_platform_products = sum(v["count"] for v in platform_stats.values()) or 1
        platform_performance = [
            CompetitorData(
                platform=plat,
                products=stats["count"],
                avgPrice=round(sum(stats["prices"]) / len(stats["prices"]), 2) if stats["prices"] else 0.0,
                marketShare=round(stats["count"] / total_platform_products * 100, 1),
                avgRating=round(sum(stats["ratings"]) / len(stats["ratings"]), 2) if stats["ratings"] else None,
            )
            for plat, stats in sorted(platform_stats.items(), key=lambda x: x[1]["count"], reverse=True)
        ]

        # ========== USER ACTIVITY ==========
        user_rows = (
            db.query(
                User.email,
                func.count(UserSearch.id).label("cnt"),
                func.max(UserSearch.searched_at).label("last_active"),
            )
            .join(User, UserSearch.user_id == User.id)
            .group_by(User.email)
            .order_by(desc("cnt"))
            .limit(20)
            .all()
        )
        user_activity = [
            UserActivityItem(
                email=row.email,
                searchCount=row.cnt,
                lastActive=row.last_active,
            )
            for row in user_rows
        ]

        # ========== PRICE INSIGHTS (from results_data JSONB) ==========
        cat_prices: dict = defaultdict(list)
        for p in products:
            cat = p.get("category") or "Uncategorized"
            price = p.get("price")
            if price is not None:
                try:
                    cat_prices[cat].append(float(price))
                except (ValueError, TypeError):
                    pass

        price_insights = [
            PriceInsight(
                category=cat,
                avgPrice=round(sum(prices) / len(prices), 2),
                minPrice=round(min(prices), 2),
                maxPrice=round(max(prices), 2),
                productCount=len(prices),
            )
            for cat, prices in sorted(cat_prices.items(), key=lambda x: len(x[1]), reverse=True)
            if prices
        ]

        return BusinessDashboardResponse(
            metrics=metrics,
            dailySearchVolume=daily_search_volume,
            categoryBreakdown=category_breakdown,
            topSearchTerms=top_search_terms,
            platformPerformance=platform_performance,
            userActivity=user_activity,
            priceInsights=price_insights,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard data error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard data: {str(e)}")
