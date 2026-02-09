-- AI Product Curator - Full Schema for Supabase
-- Paste this into Supabase SQL Editor and click "Run"

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ============================================
-- AUTH TABLES
-- ============================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);
CREATE INDEX idx_users_email ON users(email);

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    revoked BOOLEAN DEFAULT FALSE
);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);

CREATE TABLE login_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    login_at TIMESTAMPTZ DEFAULT NOW(),
    logout_at TIMESTAMPTZ,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE
);
CREATE INDEX idx_login_sessions_user_id ON login_sessions(user_id);

-- ============================================
-- CONSUMER-FACING TABLES
-- ============================================

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(500) NOT NULL,
    category VARCHAR(100) NOT NULL,
    description TEXT,
    image_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_products_category ON products(category);

CREATE TABLE product_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    image_type VARCHAR(50) DEFAULT 'primary',
    alt_text VARCHAR(500),
    source_platform VARCHAR(100),
    display_order INTEGER DEFAULT 0,
    width INTEGER,
    height INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_product_images_product_id ON product_images(product_id);
CREATE INDEX idx_product_images_product_type ON product_images(product_id, image_type);

CREATE TABLE product_comparisons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    platform VARCHAR(100) NOT NULL,
    product_url TEXT NOT NULL,
    platform_product_id VARCHAR(255),
    price NUMERIC(12, 2) NOT NULL,
    original_price NUMERIC(12, 2),
    currency VARCHAR(10) DEFAULT 'INR',
    discount_percent NUMERIC(5, 2),
    rating NUMERIC(3, 2),
    review_count INTEGER DEFAULT 0,
    availability VARCHAR(50),
    seller_name VARCHAR(255),
    shipping_info VARCHAR(255),
    delivery_estimate VARCHAR(100),
    price_score NUMERIC(5, 2),
    rating_score NUMERIC(5, 2),
    value_score NUMERIC(5, 2),
    brand_trust_score NUMERIC(5, 2),
    is_best_deal BOOLEAN DEFAULT FALSE,
    comparison_rank INTEGER,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_product_comparisons_product_id ON product_comparisons(product_id);
CREATE INDEX idx_product_comparisons_platform ON product_comparisons(platform);
CREATE INDEX idx_comparisons_product_platform ON product_comparisons(product_id, platform);
CREATE INDEX idx_comparisons_best_deal ON product_comparisons(is_best_deal, comparison_rank);

CREATE TABLE product_listings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    platform VARCHAR(100) NOT NULL,
    platform_product_id VARCHAR(255),
    url TEXT NOT NULL,
    price NUMERIC(12, 2) NOT NULL,
    original_price NUMERIC(12, 2),
    currency VARCHAR(10) DEFAULT 'INR',
    rating NUMERIC(3, 2),
    review_count INTEGER DEFAULT 0,
    availability VARCHAR(50),
    shipping_cost NUMERIC(10, 2) DEFAULT 0.00,
    is_active BOOLEAN DEFAULT TRUE,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_product_listings_product_id ON product_listings(product_id);
CREATE INDEX idx_product_listings_platform ON product_listings(platform);
CREATE INDEX idx_product_listings_price ON product_listings(price);
CREATE INDEX idx_product_listings_scraped_at ON product_listings(scraped_at);
CREATE INDEX idx_listings_product_platform ON product_listings(product_id, platform);
CREATE INDEX idx_listings_active_price ON product_listings(is_active, price);

CREATE TABLE price_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    listing_id UUID NOT NULL REFERENCES product_listings(id) ON DELETE CASCADE,
    price NUMERIC(12, 2) NOT NULL,
    original_price NUMERIC(12, 2),
    availability VARCHAR(50),
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_price_history_listing_id ON price_history(listing_id);
CREATE INDEX idx_price_history_recorded_at ON price_history(recorded_at);

CREATE TABLE user_searches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text TEXT NOT NULL,
    extracted_product_name VARCHAR(500),
    extracted_category VARCHAR(100),
    extracted_min_price NUMERIC(12, 2),
    extracted_max_price NUMERIC(12, 2),
    results_count INTEGER,
    session_id VARCHAR(255),
    searched_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_user_searches_category ON user_searches(extracted_category);
CREATE INDEX idx_user_searches_searched_at ON user_searches(searched_at);

CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    search_id UUID REFERENCES user_searches(id),
    product_id UUID REFERENCES products(id),
    listing_id UUID REFERENCES product_listings(id),
    rank INTEGER NOT NULL,
    score NUMERIC(5, 4),
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_recommendations_search_id ON recommendations(search_id);
CREATE INDEX idx_recommendations_rank ON recommendations(rank);

-- ============================================
-- BUSINESS INTELLIGENCE TABLES
-- ============================================

CREATE TABLE market_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(100) NOT NULL,
    metric_type VARCHAR(100) NOT NULL,
    metric_value NUMERIC(15, 2),
    extra_data JSONB,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_market_metrics_category ON market_metrics(category);
CREATE INDEX idx_market_metrics_type ON market_metrics(metric_type);
CREATE INDEX idx_market_metrics_period ON market_metrics(period_start, period_end);

CREATE TABLE competitive_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(100) NOT NULL,
    platform VARCHAR(100) NOT NULL,
    avg_price NUMERIC(12, 2),
    min_price NUMERIC(12, 2),
    max_price NUMERIC(12, 2),
    product_count INTEGER,
    avg_rating NUMERIC(3, 2),
    market_share NUMERIC(5, 2),
    analysis_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_competitive_analysis_category ON competitive_analysis(category);
CREATE INDEX idx_competitive_analysis_platform ON competitive_analysis(platform);
CREATE INDEX idx_competitive_analysis_date ON competitive_analysis(analysis_date);

CREATE TABLE business_insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    insight_type VARCHAR(100) NOT NULL,
    category VARCHAR(100),
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    confidence_score NUMERIC(5, 4),
    impact_level VARCHAR(50),
    data_sources JSONB,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);
CREATE INDEX idx_business_insights_type ON business_insights(insight_type);
CREATE INDEX idx_business_insights_category ON business_insights(category);
CREATE INDEX idx_business_insights_generated_at ON business_insights(generated_at);

CREATE TABLE search_trends (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    keyword VARCHAR(500) NOT NULL,
    category VARCHAR(100),
    search_count INTEGER DEFAULT 0,
    trend_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_search_trends_keyword ON search_trends(keyword);
CREATE INDEX idx_search_trends_category ON search_trends(category);
CREATE INDEX idx_search_trends_date ON search_trends(trend_date);

CREATE TABLE customer_journey (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL,
    stage VARCHAR(50) NOT NULL,
    product_id UUID REFERENCES products(id),
    listing_id UUID REFERENCES product_listings(id),
    action VARCHAR(100),
    extra_data JSONB,
    occurred_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_customer_journey_session ON customer_journey(session_id);
CREATE INDEX idx_customer_journey_stage ON customer_journey(stage);
CREATE INDEX idx_customer_journey_occurred_at ON customer_journey(occurred_at);

-- ============================================
-- UTILITY TABLES
-- ============================================

CREATE TABLE scraping_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_type VARCHAR(100) NOT NULL,
    platform VARCHAR(100),
    query_params JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    results_count INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_scraping_jobs_platform ON scraping_jobs(platform);
CREATE INDEX idx_scraping_jobs_status ON scraping_jobs(status);
CREATE INDEX idx_scraping_jobs_created_at ON scraping_jobs(created_at);
