"""
SQLAlchemy ORM Models for the AI Product Curator database.
Corresponds to schema.sql PostgreSQL schema.
"""
from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, Text,
    DateTime, Date, ForeignKey, Index, ARRAY, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


# ============================================
# CONSUMER-FACING MODELS
# ============================================

class Product(Base):
    """Core product information deduplicated across platforms."""
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    image_url = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    listings = relationship("ProductListing", back_populates="product", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="product")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    comparisons = relationship("ProductComparison", back_populates="product", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}', category='{self.category}')>"


class ProductImage(Base):
    """Multiple images for a product from different sources/platforms."""
    __tablename__ = "product_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    image_url = Column(Text, nullable=False)
    image_type = Column(String(50), default="primary")  # primary, gallery, thumbnail, zoom
    alt_text = Column(String(500))
    source_platform = Column(String(100))  # amazon, flipkart, myntra, etc.
    display_order = Column(Integer, default=0)
    width = Column(Integer)
    height = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    product = relationship("Product", back_populates="images")

    __table_args__ = (
        Index('idx_product_images_product_type', 'product_id', 'image_type'),
    )

    def __repr__(self):
        return f"<ProductImage(id={self.id}, type='{self.image_type}', platform='{self.source_platform}')>"


class ProductComparison(Base):
    """Cross-platform product comparison with pricing and scoring."""
    __tablename__ = "product_comparisons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String(100), nullable=False, index=True)  # amazon, flipkart, myntra, ajio, croma, reliance_digital
    product_url = Column(Text, nullable=False)
    platform_product_id = Column(String(255))

    # Pricing
    price = Column(Numeric(12, 2), nullable=False)
    original_price = Column(Numeric(12, 2))
    currency = Column(String(10), default="INR")
    discount_percent = Column(Numeric(5, 2))

    # Ratings & Reviews
    rating = Column(Numeric(3, 2))
    review_count = Column(Integer, default=0)

    # Availability & Shipping
    availability = Column(String(50))
    seller_name = Column(String(255))
    shipping_info = Column(String(255))
    delivery_estimate = Column(String(100))

    # Comparison Scores (computed)
    price_score = Column(Numeric(5, 2))       # 0-100: Lower price = higher score
    rating_score = Column(Numeric(5, 2))      # 0-100: Higher rating = higher score
    value_score = Column(Numeric(5, 2))       # 0-100: Combined price/rating score
    brand_trust_score = Column(Numeric(5, 2)) # 0-100: Platform reliability score

    # Ranking
    is_best_deal = Column(Boolean, default=False)
    comparison_rank = Column(Integer)  # 1 = best option

    # Timestamps
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    product = relationship("Product", back_populates="comparisons")

    __table_args__ = (
        Index('idx_comparisons_product_platform', 'product_id', 'platform'),
        Index('idx_comparisons_best_deal', 'is_best_deal', 'comparison_rank'),
    )

    def __repr__(self):
        return f"<ProductComparison(platform='{self.platform}', price={self.price}, rank={self.comparison_rank})>"


class ProductListing(Base):
    """Platform-specific product listings with pricing and availability."""
    __tablename__ = "product_listings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String(100), nullable=False, index=True)
    platform_product_id = Column(String(255))
    url = Column(Text, nullable=False)
    price = Column(Numeric(12, 2), nullable=False, index=True)
    original_price = Column(Numeric(12, 2))
    currency = Column(String(10), default="INR")
    rating = Column(Numeric(3, 2))
    review_count = Column(Integer, default=0)
    availability = Column(String(50))
    shipping_cost = Column(Numeric(10, 2), default=0.00)
    is_active = Column(Boolean, default=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    product = relationship("Product", back_populates="listings")
    price_history = relationship("PriceHistory", back_populates="listing", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="listing")

    __table_args__ = (
        Index('idx_listings_product_platform', 'product_id', 'platform'),
        Index('idx_listings_active_price', 'is_active', 'price'),
    )

    def __repr__(self):
        return f"<ProductListing(id={self.id}, platform='{self.platform}', price={self.price})>"


class PriceHistory(Base):
    """Historical price tracking for trend analysis."""
    __tablename__ = "price_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("product_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    price = Column(Numeric(12, 2), nullable=False)
    original_price = Column(Numeric(12, 2))
    availability = Column(String(50))
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    listing = relationship("ProductListing", back_populates="price_history")

    def __repr__(self):
        return f"<PriceHistory(id={self.id}, price={self.price}, recorded_at={self.recorded_at})>"


class UserSearch(Base):
    """Log search queries for analytics and trend analysis."""
    __tablename__ = "user_searches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    query_text = Column(Text, nullable=False)
    extracted_product_name = Column(String(500))
    extracted_category = Column(String(100), index=True)
    extracted_min_price = Column(Numeric(12, 2))
    extracted_max_price = Column(Numeric(12, 2))
    results_count = Column(Integer)
    results_data = Column(JSONB)  # Store actual product results for cross-user recommendations
    session_id = Column(String(255))
    searched_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", backref="searches")
    recommendations = relationship("Recommendation", back_populates="search")

    def __repr__(self):
        return f"<UserSearch(id={self.id}, query='{self.query_text[:50]}...')>"


class Recommendation(Base):
    """AI-generated product recommendations with explanations."""
    __tablename__ = "recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_id = Column(UUID(as_uuid=True), ForeignKey("user_searches.id"), index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"))
    listing_id = Column(UUID(as_uuid=True), ForeignKey("product_listings.id"))
    rank = Column(Integer, nullable=False, index=True)
    score = Column(Numeric(5, 4))
    reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    search = relationship("UserSearch", back_populates="recommendations")
    product = relationship("Product", back_populates="recommendations")
    listing = relationship("ProductListing", back_populates="recommendations")

    def __repr__(self):
        return f"<Recommendation(id={self.id}, rank={self.rank}, score={self.score})>"


# ============================================
# BUSINESS INTELLIGENCE MODELS
# ============================================

class MarketMetric(Base):
    """Aggregated market statistics for business intelligence."""
    __tablename__ = "market_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(100), nullable=False, index=True)
    metric_type = Column(String(100), nullable=False, index=True)
    metric_value = Column(Numeric(15, 2))
    extra_data = Column(JSONB)
    period_start = Column(DateTime(timezone=True))
    period_end = Column(DateTime(timezone=True))
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_market_metrics_period', 'period_start', 'period_end'),
    )

    def __repr__(self):
        return f"<MarketMetric(category='{self.category}', type='{self.metric_type}', value={self.metric_value})>"


class CompetitiveAnalysis(Base):
    """Platform comparison data for competitive intelligence."""
    __tablename__ = "competitive_analysis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(100), nullable=False, index=True)
    platform = Column(String(100), nullable=False, index=True)
    avg_price = Column(Numeric(12, 2))
    min_price = Column(Numeric(12, 2))
    max_price = Column(Numeric(12, 2))
    product_count = Column(Integer)
    avg_rating = Column(Numeric(3, 2))
    market_share = Column(Numeric(5, 2))
    analysis_date = Column(Date, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<CompetitiveAnalysis(category='{self.category}', platform='{self.platform}')>"


class BusinessInsight(Base):
    """AI-generated business intelligence and opportunities."""
    __tablename__ = "business_insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    insight_type = Column(String(100), nullable=False, index=True)
    category = Column(String(100), index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    confidence_score = Column(Numeric(5, 4))
    impact_level = Column(String(50))
    data_sources = Column(JSONB)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<BusinessInsight(type='{self.insight_type}', title='{self.title[:50]}...')>"


class SearchTrend(Base):
    """Track search volume and trends over time."""
    __tablename__ = "search_trends"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keyword = Column(String(500), nullable=False, index=True)
    category = Column(String(100), index=True)
    search_count = Column(Integer, default=0)
    trend_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<SearchTrend(keyword='{self.keyword}', date={self.trend_date}, count={self.search_count})>"


class CustomerJourney(Base):
    """Track user behavior patterns through the purchase funnel."""
    __tablename__ = "customer_journey"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), nullable=False, index=True)
    stage = Column(String(50), nullable=False, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"))
    listing_id = Column(UUID(as_uuid=True), ForeignKey("product_listings.id"))
    action = Column(String(100))
    extra_data = Column(JSONB)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<CustomerJourney(session='{self.session_id}', stage='{self.stage}', action='{self.action}')>"


# ============================================
# UTILITY MODELS
# ============================================

class ScrapingJob(Base):
    """Track scraping tasks and their execution status."""
    __tablename__ = "scraping_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(String(100), nullable=False)
    platform = Column(String(100), index=True)
    query_params = Column(JSONB)
    status = Column(String(50), default="pending", index=True)
    results_count = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<ScrapingJob(id={self.id}, type='{self.job_type}', status='{self.status}')>"
