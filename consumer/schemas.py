"""Consumer feature Pydantic models — request/response schemas."""
from typing import List, Optional

from pydantic import BaseModel, Field


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


class ForYouResponse(BaseModel):
    """Personalized recommendations based on other users' searches."""
    source: str
    category: Optional[str] = None
    label: str
    recommendations: List[ProductResponse]


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
    """Full comparison response from ProductScraper."""
    productName: str
    query: str
    comparisons: List[PlatformComparison]
    bestDeal: Optional[PlatformComparison] = None
    priceRange: PriceRange
    images: List[str] = []
    recommendation: str
    totalPlatforms: int
