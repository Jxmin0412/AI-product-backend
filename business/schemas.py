"""Business intelligence Pydantic models — request/response schemas."""
from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel


class BusinessMetricResponse(BaseModel):
    """Key business metric response."""
    label: str
    value: str
    change: float
    trend: str  # 'up', 'down', 'stable'


class DailySearchVolume(BaseModel):
    """Search count per day for line/area charts."""
    date: str
    searches: int


class CompetitorData(BaseModel):
    """Platform benchmarking data."""
    platform: str
    products: int
    avgPrice: float
    marketShare: float
    avgRating: Optional[float] = None


class TopSearchTerm(BaseModel):
    """Top search term with frequency."""
    term: str
    category: Optional[str] = None
    count: int


class UserActivityItem(BaseModel):
    """User activity summary."""
    email: str
    searchCount: int
    lastActive: datetime


class CategoryBreakdown(BaseModel):
    """Search category distribution."""
    category: str
    count: int
    percentage: float


class PriceInsight(BaseModel):
    """Price statistics per category from search results."""
    category: str
    avgPrice: float
    minPrice: float
    maxPrice: float
    productCount: int


class BusinessDashboardResponse(BaseModel):
    """Complete business dashboard data."""
    metrics: List[BusinessMetricResponse]
    dailySearchVolume: List[DailySearchVolume]
    categoryBreakdown: List[CategoryBreakdown]
    topSearchTerms: List[TopSearchTerm]
    platformPerformance: List[CompetitorData]
    userActivity: List[UserActivityItem]
    priceInsights: List[PriceInsight]


class InsightResponse(BaseModel):
    """Business insight response."""
    id: str
    type: str
    category: Optional[str] = None
    title: str
    description: str
    confidence: float
    impact: str
    generatedAt: datetime
