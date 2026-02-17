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


class TrendDataPoint(BaseModel):
    """Data point for trend charts."""
    month: str
    avgPrice: Optional[float] = None
    searches: Optional[int] = None


class CompetitorData(BaseModel):
    """Competitor benchmarking data."""
    platform: str
    products: int
    avgPrice: float
    marketShare: float
    avgRating: Optional[float] = None


class CustomerJourneyMetric(BaseModel):
    """Customer journey stage metric."""
    stage: str
    count: int
    percentage: float


class SentimentData(BaseModel):
    """Sentiment analysis data."""
    positive: int
    neutral: int
    negative: int


class BusinessDashboardResponse(BaseModel):
    """Complete business dashboard data."""
    metrics: List[BusinessMetricResponse]
    priceTrends: List[TrendDataPoint]
    searchTrends: List[TrendDataPoint]
    competitors: List[CompetitorData]
    customerJourney: List[CustomerJourneyMetric]
    sentiment: SentimentData


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
