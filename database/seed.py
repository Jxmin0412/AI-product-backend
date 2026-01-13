"""
Database seed script to populate sample data for testing.
Creates products, listings, and business metrics.
"""
import sys
import os
from datetime import datetime, timedelta, date
from decimal import Decimal
import uuid

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import db_manager, init_db
from database.models import (
    Product, ProductListing, PriceHistory, UserSearch,
    MarketMetric, CompetitiveAnalysis, BusinessInsight,
    SearchTrend
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_products_and_listings():
    """Seed sample products and their platform listings."""
    logger.info("Seeding products and listings...")

    with db_manager.session_scope() as session:
        # Product 1: MacBook Pro
        macbook = Product(
            name="MacBook Pro 14-inch M3",
            category="Laptops",
            description="Powerful laptop with M3 chip, 16GB RAM, 512GB SSD. Perfect for developers and creators.",
            image_url="https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/mbp14-spacegray-select-202310"
        )
        session.add(macbook)
        session.flush()

        # Listings for MacBook
        listings = [
            ProductListing(
                product_id=macbook.id,
                platform="Apple Store",
                platform_product_id="MBP14-M3",
                url="https://www.apple.com/shop/buy-mac/macbook-pro",
                price=Decimal("1999.00"),
                original_price=Decimal("1999.00"),
                rating=Decimal("4.8"),
                review_count=1250,
                availability="In Stock",
                shipping_cost=Decimal("0.00")
            ),
            ProductListing(
                product_id=macbook.id,
                platform="Amazon",
                platform_product_id="B0CX23V2ZK",
                url="https://amazon.com/macbook-pro-14",
                price=Decimal("1949.00"),
                original_price=Decimal("1999.00"),
                rating=Decimal("4.7"),
                review_count=823,
                availability="In Stock",
                shipping_cost=Decimal("0.00")
            ),
            ProductListing(
                product_id=macbook.id,
                platform="Best Buy",
                platform_product_id="6534644",
                url="https://bestbuy.com/macbook-pro",
                price=Decimal("1999.00"),
                original_price=Decimal("1999.00"),
                rating=Decimal("4.9"),
                review_count=456,
                availability="Limited Stock",
                shipping_cost=Decimal("19.99")
            )
        ]
        session.add_all(listings)

        # Product 2: Sony WH-1000XM5
        sony_headphones = Product(
            name="Sony WH-1000XM5 Wireless Headphones",
            category="Audio",
            description="Industry-leading noise cancellation, premium sound quality, 30-hour battery life.",
            image_url="https://m.media-amazon.com/images/I/71o8Q5XJS5L._AC_SL1500_.jpg"
        )
        session.add(sony_headphones)
        session.flush()

        session.add_all([
            ProductListing(
                product_id=sony_headphones.id,
                platform="Amazon",
                url="https://amazon.com/sony-wh1000xm5",
                price=Decimal("399.99"),
                original_price=Decimal("449.99"),
                rating=Decimal("4.6"),
                review_count=3420,
                availability="In Stock"
            ),
            ProductListing(
                product_id=sony_headphones.id,
                platform="Best Buy",
                url="https://bestbuy.com/sony-headphones",
                price=Decimal("429.99"),
                rating=Decimal("4.7"),
                review_count=892,
                availability="In Stock",
                shipping_cost=Decimal("9.99")
            )
        ])

        # Product 3: iPhone 15 Pro
        iphone = Product(
            name="iPhone 15 Pro 256GB",
            category="Smartphones",
            description="Latest iPhone with titanium design, A17 Pro chip, and advanced camera system.",
            image_url="https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/iphone-15-pro-finish-select-202309"
        )
        session.add(iphone)
        session.flush()

        session.add_all([
            ProductListing(
                product_id=iphone.id,
                platform="Apple Store",
                url="https://apple.com/shop/buy-iphone",
                price=Decimal("1099.00"),
                rating=Decimal("4.8"),
                review_count=2156,
                availability="In Stock"
            ),
            ProductListing(
                product_id=iphone.id,
                platform="Amazon",
                url="https://amazon.com/iphone-15-pro",
                price=Decimal("1049.99"),
                original_price=Decimal("1099.00"),
                rating=Decimal("4.7"),
                review_count=1834,
                availability="In Stock"
            )
        ])

        # Product 4: Dell XPS 13
        dell_laptop = Product(
            name="Dell XPS 13 Intel Core i7",
            category="Laptops",
            description="Ultra-portable laptop with 13.4-inch display, 16GB RAM, 512GB SSD.",
            image_url="https://i.dell.com/is/image/DellContent/content/dam/ss2/product-images/dell-client-products/notebooks/xps-notebooks/xps-13-9340"
        )
        session.add(dell_laptop)
        session.flush()

        session.add_all([
            ProductListing(
                product_id=dell_laptop.id,
                platform="Dell",
                url="https://dell.com/xps-13",
                price=Decimal("1299.99"),
                rating=Decimal("4.5"),
                review_count=678,
                availability="In Stock"
            ),
            ProductListing(
                product_id=dell_laptop.id,
                platform="Amazon",
                url="https://amazon.com/dell-xps-13",
                price=Decimal("1249.99"),
                original_price=Decimal("1299.99"),
                rating=Decimal("4.6"),
                review_count=543,
                availability="In Stock"
            )
        ])

        # Product 5: AirPods Pro
        airpods = Product(
            name="Apple AirPods Pro (2nd generation)",
            category="Audio",
            description="Active noise cancellation, adaptive transparency, personalized spatial audio.",
            image_url="https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/MQD83"
        )
        session.add(airpods)
        session.flush()

        session.add_all([
            ProductListing(
                product_id=airpods.id,
                platform="Apple Store",
                url="https://apple.com/shop/airpods-pro",
                price=Decimal("249.00"),
                rating=Decimal("4.8"),
                review_count=5234,
                availability="In Stock"
            ),
            ProductListing(
                product_id=airpods.id,
                platform="Amazon",
                url="https://amazon.com/airpods-pro",
                price=Decimal("189.99"),
                original_price=Decimal("249.00"),
                rating=Decimal("4.7"),
                review_count=12453,
                availability="In Stock"
            ),
            ProductListing(
                product_id=airpods.id,
                platform="Best Buy",
                url="https://bestbuy.com/airpods-pro",
                price=Decimal("199.99"),
                original_price=Decimal("249.00"),
                rating=Decimal("4.8"),
                review_count=3421,
                availability="In Stock"
            )
        ])

        # Product 6: Samsung Galaxy S24
        samsung = Product(
            name="Samsung Galaxy S24 Ultra 512GB",
            category="Smartphones",
            description="Flagship Android phone with S Pen, 200MP camera, AI features.",
            image_url="https://images.samsung.com/is/image/samsung/p6pim/in/2401/gallery/in-galaxy-s24-s928-sm-s928bzkdins"
        )
        session.add(samsung)
        session.flush()

        session.add_all([
            ProductListing(
                product_id=samsung.id,
                platform="Samsung",
                url="https://samsung.com/galaxy-s24",
                price=Decimal("1299.99"),
                rating=Decimal("4.6"),
                review_count=1876,
                availability="In Stock"
            ),
            ProductListing(
                product_id=samsung.id,
                platform="Amazon",
                url="https://amazon.com/samsung-galaxy-s24",
                price=Decimal("1249.99"),
                original_price=Decimal("1299.99"),
                rating=Decimal("4.5"),
                review_count=934,
                availability="In Stock"
            )
        ])

    logger.info("Products and listings seeded successfully")


def seed_price_history():
    """Seed historical price data for trend analysis."""
    logger.info("Seeding price history...")

    with db_manager.session_scope() as session:
        # Get all listings
        listings = session.query(ProductListing).limit(10).all()

        for listing in listings:
            # Create price history for last 90 days
            base_price = float(listing.price)

            for days_ago in range(90, 0, -7):  # Weekly data points
                historical_date = datetime.now() - timedelta(days=days_ago)
                # Simulate price fluctuation
                price_variation = base_price * (0.95 + (days_ago % 20) * 0.005)

                price_record = PriceHistory(
                    listing_id=listing.id,
                    price=Decimal(str(round(price_variation, 2))),
                    original_price=listing.original_price,
                    availability=listing.availability,
                    recorded_at=historical_date
                )
                session.add(price_record)

    logger.info("Price history seeded successfully")


def seed_business_metrics():
    """Seed business intelligence data."""
    logger.info("Seeding business metrics...")

    with db_manager.session_scope() as session:
        categories = ["Laptops", "Audio", "Smartphones", "Electronics"]

        for category in categories:
            # Market metrics for last 6 months
            for month_offset in range(6):
                period_end = datetime.now() - timedelta(days=month_offset * 30)
                period_start = period_end - timedelta(days=30)

                metric = MarketMetric(
                    category=category,
                    metric_type="avg_price",
                    metric_value=Decimal("750.00") + Decimal(month_offset * 25),
                    metadata={"month": period_end.strftime("%B %Y")},
                    period_start=period_start,
                    period_end=period_end
                )
                session.add(metric)

        # Competitive analysis
        platforms = ["Amazon", "Best Buy", "Apple Store", "Dell"]
        for category in categories:
            for platform in platforms:
                analysis = CompetitiveAnalysis(
                    category=category,
                    platform=platform,
                    avg_price=Decimal("699.99"),
                    min_price=Decimal("199.99"),
                    max_price=Decimal("1999.99"),
                    product_count=25 + (hash(platform + category) % 50),
                    avg_rating=Decimal("4.5") + Decimal(hash(platform) % 5) / 10,
                    market_share=Decimal("20.0") + Decimal(hash(platform) % 15),
                    analysis_date=date.today()
                )
                session.add(analysis)

        # Business insights
        insights = [
            BusinessInsight(
                insight_type="opportunity",
                category="Laptops",
                title="Growing Demand for Premium Laptops",
                description="MacBook and high-end Windows laptops showing 15% increase in search volume over last quarter.",
                confidence_score=Decimal("0.87"),
                impact_level="High",
                data_sources={"source": "search_trends", "period": "Q4 2024"}
            ),
            BusinessInsight(
                insight_type="trend",
                category="Audio",
                title="Noise-Cancelling Headphones Market Expansion",
                description="Premium audio segment growing at 12% CAGR, driven by work-from-home and travel recovery.",
                confidence_score=Decimal("0.82"),
                impact_level="Medium",
                data_sources={"source": "market_analysis"}
            )
        ]
        session.add_all(insights)

        # Search trends
        keywords = ["laptop", "headphones", "smartphone", "macbook", "airpods"]
        for keyword in keywords:
            for days_ago in range(180, 0, -30):
                trend_date = date.today() - timedelta(days=days_ago)
                trend = SearchTrend(
                    keyword=keyword,
                    category=categories[hash(keyword) % len(categories)],
                    search_count=1000 + (hash(keyword + str(days_ago)) % 500),
                    trend_date=trend_date
                )
                session.add(trend)

    logger.info("Business metrics seeded successfully")


def main():
    """Main seeding function."""
    try:
        logger.info("Starting database seeding...")

        # Initialize database
        init_db()

        # Seed data
        seed_products_and_listings()
        seed_price_history()
        seed_business_metrics()

        logger.info("Database seeding completed successfully!")

    except Exception as e:
        logger.error(f"Database seeding failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
