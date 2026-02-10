"""
🚀 RUN THIS FIRST - Interactive Learning Script
================================================

This script lets you interactively test the concepts.
No database or FastAPI needed - just pure Python!

Run: python run_this_first.py
"""

print("""
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║   🎓 WELCOME TO THE AI PRODUCT CURATOR LEARNING DEMO          ║
║                                                                ║
║   This will teach you FastAPI + LangGraph concepts            ║
║   through interactive examples.                               ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝

Let's start with the BASICS...
""")

# ============================================
# PART 1: Understanding State (The Clipboard)
# ============================================

print("\n" + "=" * 60)
print("PART 1: Understanding State")
print("=" * 60)

print("""
Think of STATE as a clipboard that gets passed around.
Each person (agent) reads it, adds notes, and passes it on.
""")

from dataclasses import dataclass

@dataclass
class ShoppingState:
    """The clipboard with all the info"""
    customer_query: str
    product_category: str = None
    price_limit: float = None
    found_products: list = None
    recommendation: str = None

# Create initial state
state = ShoppingState(customer_query="I want a laptop under $1500")

print(f"📋 Initial State:")
print(f"   Customer Query: {state.customer_query}")
print(f"   Product Category: {state.product_category}")  # None yet
print(f"   Price Limit: {state.price_limit}")  # None yet

input("\n👉 Press ENTER to see Agent 1 process this...")

# ============================================
# PART 2: Agents Process State
# ============================================

print("\n" + "=" * 60)
print("PART 2: Agent 1 - Understanding the Query")
print("=" * 60)

def agent1_query_parser(state):
    """Agent 1: Extracts info from natural language"""
    print(f"\n🤖 Agent 1 is thinking...")
    print(f"   Input: '{state.customer_query}'")

    query = state.customer_query.lower()

    # Extract category
    if "laptop" in query:
        state.product_category = "Laptops"
        print(f"   ✅ Found category: Laptops")

    # Extract price
    if "under" in query:
        words = query.split()
        for i, word in enumerate(words):
            if word == "under" and i + 1 < len(words):
                price_str = words[i + 1].replace("$", "")
                state.price_limit = float(price_str)
                print(f"   ✅ Found price limit: ${state.price_limit}")
                break

    return state

# Run Agent 1
state = agent1_query_parser(state)

print(f"\n📋 State after Agent 1:")
print(f"   Product Category: {state.product_category}")
print(f"   Price Limit: ${state.price_limit}")

input("\n👉 Press ENTER to see Agent 2...")

# ============================================
# PART 3: Agent 2 - Finding Products
# ============================================

print("\n" + "=" * 60)
print("PART 3: Agent 2 - Finding Products")
print("=" * 60)

def agent2_product_finder(state):
    """Agent 2: Finds products based on criteria"""
    print(f"\n🤖 Agent 2 is searching...")
    print(f"   Looking for: {state.product_category}")
    print(f"   Price limit: ${state.price_limit}")

    # Simulated product database
    all_products = [
        {"name": "Dell XPS 13", "price": 1299, "rating": 4.6},
        {"name": "MacBook Air", "price": 999, "rating": 4.8},
        {"name": "HP Spectre", "price": 1699, "rating": 4.5},  # Too expensive
        {"name": "Lenovo ThinkPad", "price": 1199, "rating": 4.7},
    ]

    # Filter by price
    state.found_products = [
        p for p in all_products
        if p["price"] <= state.price_limit
    ]

    print(f"   ✅ Found {len(state.found_products)} products")
    for product in state.found_products:
        print(f"      - {product['name']}: ${product['price']} (⭐{product['rating']})")

    return state

# Run Agent 2
state = agent2_product_finder(state)

input("\n👉 Press ENTER to see Agent 3...")

# ============================================
# PART 4: Agent 3 - Making Recommendation
# ============================================

print("\n" + "=" * 60)
print("PART 4: Agent 3 - AI Recommendation")
print("=" * 60)

def agent3_recommender(state):
    """Agent 3: Ranks products and recommends best"""
    print(f"\n🤖 Agent 3 is analyzing...")

    # Rank by rating (simple algorithm)
    sorted_products = sorted(
        state.found_products,
        key=lambda p: p["rating"],
        reverse=True
    )

    best = sorted_products[0]

    state.recommendation = f"{best['name']} - ${best['price']} (⭐{best['rating']})"

    print(f"   ✅ Top recommendation: {state.recommendation}")
    print(f"   Reason: Highest rating ({best['rating']}) within budget")

    return state

# Run Agent 3
state = agent3_recommender(state)

print(f"\n📋 Final State:")
print(f"   Customer Query: {state.customer_query}")
print(f"   Category: {state.product_category}")
print(f"   Price Limit: ${state.price_limit}")
print(f"   Found: {len(state.found_products)} products")
print(f"   Recommendation: {state.recommendation}")

# ============================================
# PART 5: Complete Workflow
# ============================================

print("\n" + "=" * 60)
print("PART 5: Complete Workflow")
print("=" * 60)

def run_complete_workflow(customer_query):
    """This is like LangGraph - connecting all agents"""
    print(f"\n🎯 Processing: '{customer_query}'")
    print("=" * 60)

    # 1. Create initial state
    state = ShoppingState(customer_query=customer_query)

    # 2. Run agents in sequence
    state = agent1_query_parser(state)
    state = agent2_product_finder(state)
    state = agent3_recommender(state)

    # 3. Return final result
    print("\n" + "=" * 60)
    print("✅ WORKFLOW COMPLETE!")
    print(f"💡 Recommendation: {state.recommendation}")
    print("=" * 60)

    return state

input("\n👉 Press ENTER to see the COMPLETE workflow...")

# Run example workflows
run_complete_workflow("I want a laptop under $1500")

print("\n" + "=" * 60)
print("Let's try another query...")
print("=" * 60)

run_complete_workflow("I want a laptop under $1000")

# ============================================
# PART 6: How This Relates to Your Project
# ============================================

print("\n" + "=" * 60)
print("🎓 HOW THIS RELATES TO YOUR PROJECT")
print("=" * 60)

print("""
What you just saw:

1. ShoppingState           → AgentState (in base_agent.py)
2. agent1_query_parser     → QueryHandlerAgent (in query_handler.py)
3. agent2_product_finder   → DataCollectorAgent (in data_collector.py)
4. agent3_recommender      → ConsumerRecommenderAgent (in consumer_recommender.py)
5. run_complete_workflow() → WorkflowOrchestrator (in workflow.py)

YOUR PROJECT ADDS:

✅ FastAPI: HTTP server to receive requests from frontend
✅ PostgreSQL: Real database instead of hardcoded products
✅ LangGraph: Proper workflow management with error handling
✅ Hugging Face: LLM for natural language understanding
✅ Web Scraping: Get real product data from Amazon, etc.

THE FLOW:

1. User types in frontend
2. Frontend calls FastAPI endpoint
3. FastAPI calls workflow.run()
4. Agents process sequentially
5. Results saved to database
6. FastAPI returns JSON
7. Frontend displays results

CURRENT STATUS:

Phase 1: ✅ FastAPI + Database working
         ⏳ Agents are basic (no LLM yet)

Phase 2: Add LLM, web scraping, embeddings
Phase 3: Advanced business analytics
Phase 4: Caching, background jobs, production ready
""")

print("\n" + "=" * 60)
print("🎉 CONGRATULATIONS!")
print("=" * 60)

print("""
You now understand:
✅ What STATE is (data container)
✅ What AGENTS do (process and update state)
✅ How WORKFLOWS connect agents
✅ How it relates to your project

NEXT STEPS:

1. Read: backend/examples/LEARNING_GUIDE.md
2. Read: backend/examples/HOW_IT_ALL_CONNECTS.md
3. Run: backend/examples/simple_langgraph_example.py
4. Try: Start your backend (python backend/main.py)
5. Explore: http://localhost:8000/docs

CHALLENGE: Can you add Agent 4 that checks reviews?
""")

print("\n✨ Happy Learning! ✨\n")
