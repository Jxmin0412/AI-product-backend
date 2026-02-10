# 🔗 How Everything Connects: The Complete Picture

## The 30-Second Explanation

```
User types "laptop" in frontend
    ↓
Frontend sends HTTP POST to backend
    ↓
FastAPI receives request and validates it
    ↓
(Phase 2) LangGraph workflow runs (5 agents process the query)
    ↓
Results saved to PostgreSQL database
    ↓
FastAPI sends JSON response back
    ↓
Frontend displays products
```

---

## Visual Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                         │
│                     http://localhost:5173                        │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌─────────────┐              │
│  │  Landing   │  │   User     │  │  Business   │              │
│  │    Page    │  │ Dashboard  │  │  Dashboard  │              │
│  └────────────┘  └────────────┘  └─────────────┘              │
│                          │                                       │
└──────────────────────────┼───────────────────────────────────────┘
                          │
                          │ HTTP Request (JSON)
                          │ POST /api/consumer/search
                          │ {query: "laptop", category: "Laptops"}
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                             │
│                  http://localhost:8000                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      main.py                              │  │
│  │  - FastAPI app instance                                  │  │
│  │  - CORS configuration                                    │  │
│  │  - Route mounting                                        │  │
│  │  - Error handlers                                        │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│      ┌────────────────┴────────────────┐                        │
│      │                                  │                        │
│      ↓                                  ↓                        │
│  ┌────────────────┐           ┌────────────────┐               │
│  │   Consumer     │           │   Business     │               │
│  │    Routes      │           │    Routes      │               │
│  │ consumer_routes│           │business_routes │               │
│  │     .py        │           │     .py        │               │
│  └────────┬───────┘           └────────┬───────┘               │
│           │                            │                        │
│           │ Calls                      │ Calls                  │
│           ↓                            ↓                        │
│  ┌──────────────────────────────────────────────────┐          │
│  │          LANGGRAPH WORKFLOW (Phase 2)             │          │
│  │              workflow.py                          │          │
│  │                                                   │          │
│  │  ┌───────────┐    ┌──────────┐    ┌───────────┐ │          │
│  │  │  Agent 1  │───▶│ Agent 2  │───▶│  Agent 3  │ │          │
│  │  │   Query   │    │   Data   │    │   Data    │ │          │
│  │  │  Handler  │    │Collector │    │ Processor │ │          │
│  │  └───────────┘    └──────────┘    └─────┬─────┘ │          │
│  │                                          │       │          │
│  │                          ┌───────────────┴──┐    │          │
│  │                          │                  │    │          │
│  │                          ↓                  ↓    │          │
│  │                   ┌────────────┐    ┌────────────┐          │
│  │                   │  Agent 4   │    │  Agent 5   │          │
│  │                   │ Consumer   │    │ Business   │          │
│  │                   │Recommender │    │ Analytics  │          │
│  │                   └────────────┘    └────────────┘          │
│  └──────────────────────┬────────────────────────────┘          │
│                         │                                       │
│                         │ Results                               │
│                         ↓                                       │
└─────────────────────────┼───────────────────────────────────────┘
                          │
                          │ Database Queries
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                  POSTGRESQL DATABASE                             │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Products │  │ Product  │  │  Price   │  │  Market  │       │
│  │          │  │ Listings │  │ History  │  │ Metrics  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │   User   │  │Recommend-│  │Competitive│  │ Business │       │
│  │ Searches │  │ ations   │  │ Analysis │  │ Insights │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Request Flow with Code

### Step 1: Frontend Makes Request

```javascript
// frontend/src/pages/UserDashboard.tsx

const handleSearch = async () => {
  const response = await fetch('http://localhost:8000/api/consumer/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: "gaming laptop",
      category: "Laptops",
      maxPrice: 2000
    })
  });

  const data = await response.json();
  setSearchResults(data.results);
};
```

### Step 2: FastAPI Routes Request

```python
# backend/main.py

app = FastAPI()

# Mount consumer routes
app.include_router(
    consumer_routes.router,
    prefix="/api/consumer",  # All routes prefixed with /api/consumer
    tags=["Consumer"]
)

# So POST /api/consumer/search goes to:
# → consumer_routes.py → @router.post("/search")
```

### Step 3: Endpoint Receives Request

```python
# backend/api/consumer_routes.py

@router.post("/search", response_model=SearchResponse)
async def search_products(
    request: SearchRequest,  # ← Frontend data comes here
    db: Session = Depends(get_db)  # ← Database session auto-injected
):
    # request.query = "gaming laptop"
    # request.category = "Laptops"
    # request.maxPrice = 2000

    # Log search to database
    search_record = UserSearch(
        query_text=request.query,
        extracted_category=request.category,
        extracted_max_price=request.maxPrice
    )
    db.add(search_record)

    # ... (rest of processing)
```

### Step 4: Database Query

```python
    # Build query using SQLAlchemy ORM
    query = db.query(Product, ProductListing).join(ProductListing)

    # Apply filters
    query = query.filter(Product.category == "Laptops")
    query = query.filter(ProductListing.price <= 2000)
    query = query.filter(Product.name.ilike("%gaming%"))

    # Execute query
    results = query.limit(20).all()

    # Results = [(Product, ProductListing), (Product, ProductListing), ...]
```

**SQL Generated:**
```sql
SELECT products.*, product_listings.*
FROM products
INNER JOIN product_listings ON products.id = product_listings.product_id
WHERE products.category = 'Laptops'
  AND product_listings.price <= 2000
  AND products.name ILIKE '%gaming%'
  AND product_listings.is_active = true
LIMIT 20;
```

### Step 5: Convert to API Response

```python
    # Convert database models to API response format
    product_responses = []
    for product, listing in results:
        product_responses.append({
            "id": str(listing.id),
            "name": product.name,
            "category": product.category,
            "price": float(listing.price),
            "platform": listing.platform,
            "rating": float(listing.rating),
            "reviews": listing.review_count,
            "image": product.image_url,
            "inStock": listing.availability == "In Stock"
        })
```

### Step 6: Return Response

```python
    return SearchResponse(
        searchId=str(search_record.id),
        query=request.query,
        results=product_responses,
        totalResults=len(product_responses),
        recommendations=product_responses[:2]
    )
```

**JSON Response:**
```json
{
  "searchId": "abc-123-def-456",
  "query": "gaming laptop",
  "results": [
    {
      "id": "product-1",
      "name": "ASUS ROG Gaming Laptop",
      "category": "Laptops",
      "price": 1499.99,
      "platform": "Amazon",
      "rating": 4.7,
      "reviews": 1234,
      "image": "https://...",
      "inStock": true
    }
  ],
  "totalResults": 1,
  "recommendations": [...]
}
```

### Step 7: Frontend Displays Results

```javascript
// Frontend receives data and displays it
setSearchResults(data.results);

// React renders:
{searchResults.map(product => (
  <ProductCard
    key={product.id}
    name={product.name}
    price={product.price}
    rating={product.rating}
  />
))}
```

---

## LangGraph Workflow Flow (Phase 2)

### Current (Phase 1): Direct Database Query

```
User Query → FastAPI → Database → Response
```

### Future (Phase 2): With LangGraph Agents

```
User Query
    ↓
FastAPI creates initial state:
    AgentState(user_query="gaming laptop under 2000")
    ↓
LangGraph Workflow starts
    ↓
┌──────────────────────────────────────────┐
│         Agent 1: Query Handler           │
│  Input:  user_query = "gaming laptop     │
│          under 2000"                     │
│  Process: Parse query                    │
│  Output: extracted_category = "Laptops"  │
│          extracted_price = (None, 2000)  │
└──────────────┬───────────────────────────┘
               ↓
┌──────────────────────────────────────────┐
│         Agent 2: Data Collector          │
│  Input:  category = "Laptops"            │
│          price_range = (None, 2000)      │
│  Process: Scrape Amazon, Flipkart        │
│  Output: raw_products = [                │
│            {name: "ASUS", price: 1499},  │
│            {name: "MSI", price: 1799}    │
│          ]                               │
└──────────────┬───────────────────────────┘
               ↓
┌──────────────────────────────────────────┐
│         Agent 3: Data Processor          │
│  Input:  raw_products = [...]            │
│  Process: Deduplicate, normalize         │
│  Output: clean_products = [...]          │
└──────────────┬───────────────────────────┘
               ↓
┌──────────────────────────────────────────┐
│      Agent 4: Consumer Recommender       │
│  Input:  clean_products = [...]          │
│  Process: Rank by value, rating          │
│          Generate AI explanations        │
│  Output: recommendations = [             │
│            {name: "ASUS", score: 0.95,   │
│             reason: "Best value..."}     │
│          ]                               │
└──────────────┬───────────────────────────┘
               ↓
LangGraph Workflow ends
    ↓
FastAPI receives final state
    ↓
Return recommendations to frontend
```

---

## Code Flow: Where Things Are

### 1. Server Starts

```
python backend/main.py
    ↓
Loads: backend/config/settings.py (environment variables)
    ↓
Initializes: backend/database/connection.py (database connection)
    ↓
Creates tables: backend/database/models.py (table definitions)
    ↓
Mounts routes: backend/api/consumer_routes.py
                backend/api/business_routes.py
    ↓
Server running at http://localhost:8000
```

### 2. Request Comes In

```
POST http://localhost:8000/api/consumer/search
    ↓
backend/main.py (receives request)
    ↓
Routes to: backend/api/consumer_routes.py
    ↓
Function: search_products()
    ↓
Injects: db session from backend/database/connection.py
    ↓
Queries: backend/database/models.py (Product, ProductListing)
    ↓
Returns: JSON response
```

### 3. LangGraph Workflow (Phase 2)

```
FastAPI endpoint calls:
    backend/agents/workflow.py → get_workflow_orchestrator()
        ↓
    Creates agents:
        backend/agents/query_handler.py
        backend/agents/data_collector.py
        backend/agents/data_processor.py
        backend/agents/consumer_recommender.py
        ↓
    Runs workflow:
        Agent 1 → Agent 2 → Agent 3 → Agent 4
        ↓
    Returns final state with recommendations
```

---

## Database Tables and Their Relationships

```
┌─────────────┐
│  products   │  ← Core product info (name, category, description)
│  - id       │
│  - name     │
│  - category │
└──────┬──────┘
       │
       │ 1:Many
       ↓
┌─────────────────┐
│product_listings │  ← Platform-specific prices (Amazon, Best Buy)
│  - id           │
│  - product_id ──┼──→ Foreign Key to products.id
│  - platform     │
│  - price        │
│  - rating       │
└──────┬──────────┘
       │
       │ 1:Many
       ↓
┌──────────────┐
│price_history │  ← Historical prices for trends
│  - id        │
│  - listing_id┼──→ Foreign Key to product_listings.id
│  - price     │
│  - recorded  │
└──────────────┘

┌──────────────┐
│user_searches │  ← Search query logs
│  - id        │
│  - query_text│
│  - results   │
└──────┬───────┘
       │
       │ 1:Many
       ↓
┌─────────────────┐
│recommendations  │  ← AI-generated recommendations
│  - id           │
│  - search_id  ──┼──→ Foreign Key to user_searches.id
│  - product_id ──┼──→ Foreign Key to products.id
│  - rank         │
│  - reason       │
└─────────────────┘
```

**Example Data:**

```sql
-- products table
id: 1, name: "MacBook Pro", category: "Laptops"

-- product_listings table (multiple platforms)
id: 101, product_id: 1, platform: "Amazon", price: 1999.00
id: 102, product_id: 1, platform: "Best Buy", price: 2049.99
id: 103, product_id: 1, platform: "Apple Store", price: 1999.00

-- price_history table (tracks changes)
id: 1001, listing_id: 101, price: 1999.00, recorded: 2024-01-15
id: 1002, listing_id: 101, price: 1899.00, recorded: 2024-01-10
id: 1003, listing_id: 101, price: 2099.00, recorded: 2024-01-05
```

---

## The Missing Piece: How to Run It

### Terminal 1: Start Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python database/seed.py  # Load sample data
python main.py  # Start server
```

### Terminal 2: Start Frontend
```bash
cd frontend
npm install
npm run dev
```

### Browser
1. Visit http://localhost:5173 (frontend)
2. Search for "laptop"
3. Frontend calls http://localhost:8000/api/consumer/search
4. Backend processes request
5. Results displayed

---

## Common Questions

### Q: Where does the LLM (AI) get used?

**Phase 1**: Not used yet (skeleton only)

**Phase 2 will use it for**:
- Agent 1: Understanding natural language queries
- Agent 4: Generating recommendation explanations
- Agent 5: Generating business insights

**Example**:
```python
# In Agent 4: Consumer Recommender
from backend.utils.huggingface_client import get_huggingface_client

client = get_huggingface_client()

# Generate explanation
explanation = await client.generate_text(
    f"Explain why this laptop is recommended for programming: {product.name}"
)
# Output: "This laptop is recommended because it has a powerful processor,
#          16GB RAM suitable for running IDEs and Docker containers..."
```

### Q: Why separate agents instead of one big function?

**Benefits**:
1. **Testable**: Test each agent independently
2. **Reusable**: Use Agent 1 in both consumer and business workflows
3. **Maintainable**: Fix Agent 2 without touching Agent 3
4. **Scalable**: Add Agent 6 without changing existing agents
5. **Clear**: Each agent has one job

### Q: What if an agent fails?

```python
try:
    state = await agent2.process(state)
except Exception as e:
    logger.error(f"Agent 2 failed: {e}")
    state.errors.append(f"Data collection failed: {e}")
    # Continue with empty data or return error
```

### Q: How do I add a new endpoint?

```python
# 1. Add to consumer_routes.py
@router.get("/products/trending")
async def get_trending_products(db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.view_count.desc()).limit(10).all()
    return products

# 2. That's it! Visit: http://localhost:8000/api/consumer/products/trending
```

---

## Summary

1. **FastAPI** = Web server that receives HTTP requests
2. **LangGraph** = Multi-agent workflow system (Phase 2)
3. **PostgreSQL** = Database storing all data
4. **Pydantic** = Data validation
5. **SQLAlchemy** = Database ORM

**Flow**: Frontend → FastAPI → LangGraph → Database → Response → Frontend

**Current State**: Phase 1 complete (FastAPI + Database working)

**Next Steps**: Phase 2 (Add LangGraph agents, web scraping, LLM features)
