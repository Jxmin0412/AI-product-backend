"""
Validation script for ConsumerRecommender scoring system.
Tests that the scoring produces correct, differentiated rankings.
"""
import sys
import math

# ---- Inline the scoring logic (no imports needed) ----

WEIGHTS = {
    "rating": 25,
    "reviews": 10,
    "price_value": 15,
    "discount": 5,
    "availability": 20,
    "feature_match": 25,
}


def calculate_score(product, state):
    breakdown = {}

    rating = product.get("rating") or 0
    breakdown["rating"] = (rating / 5.0) * WEIGHTS["rating"]

    reviews = product.get("review_count") or 0
    if reviews > 0:
        review_score = min(math.log10(reviews + 1) / 4.0, 1.0)
        breakdown["reviews"] = review_score * WEIGHTS["reviews"]
    else:
        breakdown["reviews"] = 0

    price = product.get("price") or 0
    if price > 0:
        max_price = None
        if state.get("extracted_price_range") and state["extracted_price_range"][1]:
            max_price = state["extracted_price_range"][1]
        if max_price and price <= max_price:
            price_ratio = price / max_price
            breakdown["price_value"] = (1 - price_ratio * 0.5) * WEIGHTS["price_value"]
        elif max_price and price > max_price:
            over_ratio = min((price - max_price) / max_price, 1.0)
            breakdown["price_value"] = WEIGHTS["price_value"] * max(0.1, 0.5 - over_ratio * 0.4)
        else:
            breakdown["price_value"] = WEIGHTS["price_value"] * 0.6
    else:
        breakdown["price_value"] = 0

    discount = product.get("discount_percent") or 0
    breakdown["discount"] = min(discount / 50.0, 1.0) * WEIGHTS["discount"]

    availability = product.get("availability", "Unknown")
    if availability == "In Stock":
        breakdown["availability"] = WEIGHTS["availability"]
    elif availability == "Limited Stock":
        breakdown["availability"] = WEIGHTS["availability"] * 0.7
    elif availability == "Pre-order":
        breakdown["availability"] = WEIGHTS["availability"] * 0.3
    else:
        breakdown["availability"] = WEIGHTS["availability"] * 0.5

    relevance_score = calculate_relevance(product, state)
    breakdown["feature_match"] = relevance_score * WEIGHTS["feature_match"]

    total = sum(breakdown.values())
    return total, breakdown


def calculate_relevance(product, state):
    score = 0.0
    checks = 0

    if state.get("extracted_features"):
        user_features = [f.lower() for f in state["extracted_features"]]
        product_features = [f.lower() for f in product.get("features", [])]
        product_name = product.get("name", "").lower()
        product_desc = product.get("description", "").lower()

        matches = 0
        for feature in user_features:
            if any(feature in pf for pf in product_features):
                matches += 1
            elif feature in product_name:
                matches += 0.8
            elif feature in product_desc:
                matches += 0.5
        score += min(matches / len(user_features), 1.0)
        checks += 1

    if state.get("extracted_category") and state["extracted_category"] != "All":
        product_category = (product.get("category") or "").lower()
        target_category = state["extracted_category"].lower()
        product_name = product.get("name", "").lower()

        if target_category in product_category or product_category in target_category:
            score += 1.0
        elif target_category in product_name:
            score += 0.7
        else:
            score += 0.2
        checks += 1

    if state.get("extracted_product_name"):
        query_words = set(state["extracted_product_name"].lower().split())
        name_words = set(product.get("name", "").lower().split())
        if query_words and name_words:
            overlap = len(query_words & name_words) / len(query_words)
            score += min(overlap, 1.0)
            checks += 1

    if state.get("extracted_brand"):
        product_brand = (product.get("brand") or "").lower()
        product_name = product.get("name", "").lower()
        if state["extracted_brand"].lower() in product_brand or state["extracted_brand"].lower() in product_name:
            score += 1.0
        else:
            score += 0.3
        checks += 1

    if checks > 0:
        return score / checks

    rating = product.get("rating") or 0
    reviews = product.get("review_count") or 0
    return min(0.3 + (rating / 5.0) * 0.4 + min(reviews / 1000.0, 1.0) * 0.3, 1.0)


# ---- Test Data ----

PRODUCTS = [
    {
        "name": "Samsung Galaxy S24 Ultra 5G 256GB",
        "price": 89999,
        "rating": 4.6,
        "review_count": 12500,
        "discount_percent": 15,
        "availability": "In Stock",
        "category": "Smartphones",
        "brand": "Samsung",
        "features": ["5G", "256GB", "camera", "AMOLED"],
        "description": "Flagship Samsung smartphone with S Pen and 200MP camera",
        "platform": "Amazon",
    },
    {
        "name": "iPhone 15 Pro Max 256GB",
        "price": 149900,
        "rating": 4.7,
        "review_count": 8900,
        "discount_percent": 5,
        "availability": "In Stock",
        "category": "Smartphones",
        "brand": "Apple",
        "features": ["5G", "256GB", "A17 Pro", "titanium"],
        "description": "Apple flagship with A17 Pro chip and titanium design",
        "platform": "Flipkart",
    },
    {
        "name": "OnePlus 12 5G 256GB",
        "price": 59999,
        "rating": 4.4,
        "review_count": 5600,
        "discount_percent": 20,
        "availability": "In Stock",
        "category": "Smartphones",
        "brand": "OnePlus",
        "features": ["5G", "256GB", "Snapdragon 8 Gen 3", "fast charging"],
        "description": "OnePlus flagship with 100W charging and Hasselblad camera",
        "platform": "Amazon",
    },
    {
        "name": "Redmi Note 13 Pro 5G 128GB",
        "price": 22999,
        "rating": 4.2,
        "review_count": 25000,
        "discount_percent": 25,
        "availability": "In Stock",
        "category": "Smartphones",
        "brand": "Xiaomi",
        "features": ["5G", "128GB", "200MP camera"],
        "description": "Budget 5G smartphone with 200MP camera",
        "platform": "Flipkart",
    },
    {
        "name": "Samsung Galaxy A15 4G 128GB",
        "price": 13999,
        "rating": 4.0,
        "review_count": 3200,
        "discount_percent": 10,
        "availability": "In Stock",
        "category": "Smartphones",
        "brand": "Samsung",
        "features": ["4G", "128GB", "AMOLED"],
        "description": "Budget Samsung phone with AMOLED display",
        "platform": "Amazon",
    },
    {
        "name": "Dell XPS 15 Laptop Intel i7 16GB RAM",
        "price": 145000,
        "rating": 4.5,
        "review_count": 2100,
        "discount_percent": 12,
        "availability": "In Stock",
        "category": "Laptops",
        "brand": "Dell",
        "features": ["16GB RAM", "i7", "15 inch", "SSD"],
        "description": "Premium Dell laptop for professionals",
        "platform": "Amazon",
    },
]


def print_results(test_name, state, products):
    print("=" * 80)
    print(f"TEST: {test_name}")
    print(f"  Query: {state.get('user_query', 'N/A')}")
    print(f"  Product Name: {state.get('extracted_product_name')}")
    print(f"  Category: {state.get('extracted_category')}")
    print(f"  Brand: {state.get('extracted_brand')}")
    print(f"  Price Range: {state.get('extracted_price_range')}")
    print(f"  Features: {state.get('extracted_features')}")
    print("-" * 80)

    scored = []
    for p in products:
        total, breakdown = calculate_score(p, state)
        scored.append((p, total, breakdown))

    scored.sort(key=lambda x: x[1], reverse=True)

    for rank, (p, total, bd) in enumerate(scored, 1):
        print(f"\n  #{rank} [{total:.1f}/100] {p['name'][:50]}")
        print(f"     Price: Rs.{p['price']:,} | Rating: {p['rating']}/5 | Reviews: {p['review_count']:,} | Discount: {p['discount_percent']}%")
        print(f"     Breakdown: rating={bd['rating']:.1f} reviews={bd['reviews']:.1f} price={bd['price_value']:.1f} "
              f"discount={bd['discount']:.1f} avail={bd['availability']:.1f} relevance={bd['feature_match']:.1f}")

    print()
    return scored


def main():
    passed = 0
    failed = 0

    # -------------------------------------------------------------------
    # TEST 1: Budget smartphone search ("best smartphones under 100000")
    # Expected: Samsung S24 or OnePlus 12 should rank high (within budget,
    #   good rating, smartphone category). iPhone should be penalized (over
    #   budget). Dell laptop should rank last (wrong category).
    # -------------------------------------------------------------------
    state1 = {
        "user_query": "best smartphones under 100000",
        "extracted_product_name": "smartphones",
        "extracted_category": "Smartphones",
        "extracted_brand": None,
        "extracted_price_range": (None, 100000),
        "extracted_features": ["5G", "camera"],
    }
    scored1 = print_results("Budget Smartphone Search (under Rs.100,000)", state1, PRODUCTS)

    # Check: Dell laptop should NOT be #1
    top_name = scored1[0][0]["name"]
    last_name = scored1[-1][0]["name"]
    if "Dell" not in top_name and "Laptops" not in scored1[0][0].get("category", ""):
        print("  [PASS] Top pick is a smartphone, not a laptop")
        passed += 1
    else:
        print("  [FAIL] Laptop ranked #1 for smartphone search!")
        failed += 1

    if "Dell" in last_name or "Laptop" in last_name:
        print("  [PASS] Dell laptop ranked last (wrong category)")
        passed += 1
    else:
        print("  [FAIL] Dell laptop is NOT last. Last is: " + last_name)
        failed += 1

    # Check: iPhone should be penalized (over budget at Rs.149,900 vs Rs.100,000)
    iphone_rank = next(i for i, (p, _, _) in enumerate(scored1, 1) if "iPhone" in p["name"])
    s24_rank = next(i for i, (p, _, _) in enumerate(scored1, 1) if "S24" in p["name"])
    if s24_rank < iphone_rank:
        print(f"  [PASS] Samsung S24 (#{s24_rank}) ranks above iPhone (#{iphone_rank}) -- iPhone over budget")
        passed += 1
    else:
        print(f"  [FAIL] iPhone (#{iphone_rank}) beat S24 (#{s24_rank}) despite being over budget")
        failed += 1

    # Check: Scores are differentiated (not all the same)
    scores1 = [s for _, s, _ in scored1]
    spread = max(scores1) - min(scores1)
    if spread > 10:
        print(f"  [PASS] Good score spread: {spread:.1f} points between best and worst")
        passed += 1
    else:
        print(f"  [FAIL] Scores too close together (spread={spread:.1f}). Not differentiating well.")
        failed += 1

    # -------------------------------------------------------------------
    # TEST 2: Samsung-specific search ("Samsung phone")
    # Expected: Samsung phones should rank at top. Non-Samsung phones
    #   should be penalized. Dell laptop should rank last.
    # -------------------------------------------------------------------
    state2 = {
        "user_query": "Samsung phone",
        "extracted_product_name": "phone",
        "extracted_category": "Smartphones",
        "extracted_brand": "Samsung",
        "extracted_price_range": None,
        "extracted_features": [],
    }
    scored2 = print_results("Brand-Specific Search (Samsung phone)", state2, PRODUCTS)

    samsung_ranks = [i for i, (p, _, _) in enumerate(scored2, 1) if p["brand"] == "Samsung"]
    non_samsung_ranks = [i for i, (p, _, _) in enumerate(scored2, 1)
                         if p["brand"] != "Samsung" and p["category"] == "Smartphones"]

    if samsung_ranks and non_samsung_ranks and max(samsung_ranks) < min(non_samsung_ranks):
        print(f"  [PASS] All Samsung phones (ranks {samsung_ranks}) rank above non-Samsung phones (ranks {non_samsung_ranks})")
        passed += 1
    elif samsung_ranks and min(samsung_ranks) <= 2:
        print(f"  [PASS] At least one Samsung phone in top 2 (ranks: {samsung_ranks})")
        passed += 1
    else:
        print(f"  [FAIL] Samsung phones not prioritized. Ranks: {samsung_ranks}")
        failed += 1

    # -------------------------------------------------------------------
    # TEST 3: Generic search ("popular tech products")
    # Expected: No strong category/brand/feature bias. Quality signals
    #   (rating, reviews, availability) should dominate. All products
    #   should get moderate relevance scores.
    # -------------------------------------------------------------------
    state3 = {
        "user_query": "popular tech products",
        "extracted_product_name": None,
        "extracted_category": None,
        "extracted_brand": None,
        "extracted_price_range": None,
        "extracted_features": [],
    }
    scored3 = print_results("Generic Search (popular tech products)", state3, PRODUCTS)

    # Check that scores are closer together (no unfair advantages)
    scores3 = [s for _, s, _ in scored3]
    spread3 = max(scores3) - min(scores3)
    if spread3 < spread:
        print(f"  [PASS] Generic search has tighter spread ({spread3:.1f}) than targeted search ({spread:.1f})")
        passed += 1
    else:
        print(f"  [FAIL] Generic search spread ({spread3:.1f}) >= targeted search ({spread:.1f})")
        failed += 1

    # Check that highly-rated products rank well
    top3_ratings = [scored3[i][0]["rating"] for i in range(3)]
    avg_top3_rating = sum(top3_ratings) / len(top3_ratings)
    if avg_top3_rating >= 4.3:
        print(f"  [PASS] Top 3 avg rating = {avg_top3_rating:.1f} (quality signals working)")
        passed += 1
    else:
        print(f"  [FAIL] Top 3 avg rating = {avg_top3_rating:.1f} (expected >= 4.3)")
        failed += 1

    # -------------------------------------------------------------------
    # TEST 4: Out of stock impact
    # Expected: An out-of-stock product should rank lower than its
    #   in-stock equivalent.
    # -------------------------------------------------------------------
    print("=" * 80)
    print("TEST: Availability Impact")
    in_stock_product = PRODUCTS[0].copy()  # Samsung S24, In Stock
    out_of_stock_product = PRODUCTS[0].copy()
    out_of_stock_product["availability"] = "Out of Stock"

    in_score, in_bd = calculate_score(in_stock_product, state1)
    out_score, out_bd = calculate_score(out_of_stock_product, state1)
    diff = in_score - out_score

    print(f"  In Stock score:  {in_score:.1f} (availability={in_bd['availability']:.1f})")
    print(f"  Out of Stock:    {out_score:.1f} (availability={out_bd['availability']:.1f})")
    print(f"  Difference:      {diff:.1f} points")

    if diff >= 8:
        print(f"  [PASS] In Stock gives {diff:.1f} point advantage")
        passed += 1
    else:
        print(f"  [FAIL] Availability impact too small ({diff:.1f} points)")
        failed += 1

    # -------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} checks")
    if failed == 0:
        print("ALL CHECKS PASSED - Recommendation scoring is working correctly!")
    else:
        print(f"WARNING: {failed} check(s) failed - review scoring logic.")
    print("=" * 80)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
