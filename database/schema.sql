-- AI Product Curator Database Schema
-- PostgreSQL Database Schema for E-commerce Intelligence Platform

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- CONSUMER-FACING TABLES
-- ============================================

-- Products Table: Core product information
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(500) NOT NULL,
    category VARCHAR(100) NOT NULL,
    description TEXT,
    image_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    embedding VECTOR(384),  -- For sentence-transformers embeddings
    INDEX idx_products_category (category),
    INDEX idx_products_created_at (created_at)
);

-- Product Listings: Platform-specific product listings
CREATE TABLE IF NOT EXISTS product_listings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    platform VARCHAR(100) NOT NULL,  -- Amazon, Flipkart, etc.
    platform_product_id VARCHAR(255),
    url TEXT NOT NULL,
    price DECIMAL(12, 2) NOT NULL,
    original_price DECIMAL(12, 2),  -- For discounts
    currency VARCHAR(10) DEFAULT 'INR',
    rating DECIMAL(3, 2),  -- 0.00 to 5.00
    review_count INTEGER DEFAULT 0,
    availability VARCHAR(50),  -- In Stock, Out of Stock, Limited
    shipping_cost DECIMAL(10, 2) DEFAULT 0.00,
    is_active BOOLEAN DEFAULT TRUE,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_listings_product_id (product_id),
    INDEX idx_listings_platform (platform),
    INDEX idx_listings_price (price),
    INDEX idx_listings_scraped_at (scraped_at),
    UNIQUE(platform, platform_product_id)
);

-- Price History: Track price changes over time
CREATE TABLE IF NOT EXISTS price_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    listing_id UUID REFERENCES product_listings(id) ON DELETE CASCADE,
    price DECIMAL(12, 2) NOT NULL,
    original_price DECIMAL(12, 2),
    availability VARCHAR(50),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_price_history_listing (listing_id),
    INDEX idx_price_history_date (recorded_at)
);

-- User Searches: Log search queries for analytics
CREATE TABLE IF NOT EXISTS user_searches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text TEXT NOT NULL,
    extracted_product_name VARCHAR(500),
    extracted_category VARCHAR(100),
    extracted_min_price DECIMAL(12, 2),
    extracted_max_price DECIMAL(12, 2),
    results_count INTEGER,
    session_id VARCHAR(255),
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_searches_date (searched_at),
    INDEX idx_searches_category (extracted_category)
);

-- Recommendations: AI-generated product recommendations
CREATE TABLE IF NOT EXISTS recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    search_id UUID REFERENCES user_searches(id),
    product_id UUID REFERENCES products(id),
    listing_id UUID REFERENCES product_listings(id),
    rank INTEGER NOT NULL,
    score DECIMAL(5, 4),  -- 0.0000 to 1.0000
    reason TEXT,  -- AI-generated explanation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_recommendations_search (search_id),
    INDEX idx_recommendations_rank (rank)
);

-- ============================================
-- BUSINESS INTELLIGENCE TABLES
-- ============================================

-- Market Metrics: Aggregated market-level statistics
CREATE TABLE IF NOT EXISTS market_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(100) NOT NULL,
    metric_type VARCHAR(100) NOT NULL,  -- avg_price, total_products, etc.
    metric_value DECIMAL(15, 2),
    extra_data JSONB,  -- Additional flexible data
    period_start TIMESTAMP,
    period_end TIMESTAMP,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_market_metrics_category (category),
    INDEX idx_market_metrics_type (metric_type),
    INDEX idx_market_metrics_period (period_start, period_end)
);

-- Competitive Analysis: Platform comparison data
CREATE TABLE IF NOT EXISTS competitive_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(100) NOT NULL,
    platform VARCHAR(100) NOT NULL,
    avg_price DECIMAL(12, 2),
    min_price DECIMAL(12, 2),
    max_price DECIMAL(12, 2),
    product_count INTEGER,
    avg_rating DECIMAL(3, 2),
    market_share DECIMAL(5, 2),  -- Percentage
    analysis_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_competitive_category (category),
    INDEX idx_competitive_platform (platform),
    INDEX idx_competitive_date (analysis_date),
    UNIQUE(category, platform, analysis_date)
);

-- Business Insights: AI-generated business intelligence
CREATE TABLE IF NOT EXISTS business_insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    insight_type VARCHAR(100) NOT NULL,  -- trend, opportunity, threat, etc.
    category VARCHAR(100),
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    confidence_score DECIMAL(5, 4),  -- 0.0000 to 1.0000
    impact_level VARCHAR(50),  -- High, Medium, Low
    data_sources JSONB,  -- References to source data
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_insights_type (insight_type),
    INDEX idx_insights_category (category),
    INDEX idx_insights_date (generated_at)
);

-- Search Trends: Track search volume over time
CREATE TABLE IF NOT EXISTS search_trends (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    keyword VARCHAR(500) NOT NULL,
    category VARCHAR(100),
    search_count INTEGER DEFAULT 0,
    trend_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_trends_keyword (keyword),
    INDEX idx_trends_date (trend_date),
    INDEX idx_trends_category (category),
    UNIQUE(keyword, trend_date)
);

-- Customer Journey Analytics: Track user behavior patterns
CREATE TABLE IF NOT EXISTS customer_journey (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL,
    stage VARCHAR(50) NOT NULL,  -- discovery, comparison, decision, purchase_intent
    product_id UUID REFERENCES products(id),
    listing_id UUID REFERENCES product_listings(id),
    action VARCHAR(100),  -- view, compare, add_to_cart, etc.
    extra_data JSONB,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_journey_session (session_id),
    INDEX idx_journey_stage (stage),
    INDEX idx_journey_date (occurred_at)
);

-- ============================================
-- UTILITY TABLES
-- ============================================

-- Scraping Jobs: Track scraping tasks and status
CREATE TABLE IF NOT EXISTS scraping_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_type VARCHAR(100) NOT NULL,  -- product_search, price_update, etc.
    platform VARCHAR(100),
    query_params JSONB,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, running, completed, failed
    results_count INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_jobs_status (status),
    INDEX idx_jobs_platform (platform),
    INDEX idx_jobs_created (created_at)
);

-- ============================================
-- FUNCTIONS AND TRIGGERS
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for automatic timestamp updates
CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_listings_updated_at
    BEFORE UPDATE ON product_listings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

-- Full-text search on product names
CREATE INDEX idx_products_name_fulltext ON products USING gin(to_tsvector('english', name));
CREATE INDEX idx_products_description_fulltext ON products USING gin(to_tsvector('english', description));

-- Composite indexes for common queries
CREATE INDEX idx_listings_product_platform ON product_listings(product_id, platform);
CREATE INDEX idx_listings_active_price ON product_listings(is_active, price) WHERE is_active = TRUE;

COMMENT ON TABLE products IS 'Core product information deduplicated across platforms';
COMMENT ON TABLE product_listings IS 'Platform-specific product listings with pricing and availability';
COMMENT ON TABLE price_history IS 'Historical price tracking for trend analysis';
COMMENT ON TABLE market_metrics IS 'Aggregated market statistics for business intelligence';
COMMENT ON TABLE business_insights IS 'AI-generated business intelligence and opportunities';
