# 🎓 Complete Learning Guide: FastAPI + LangGraph in This Project

## Table of Contents
1. [FastAPI Fundamentals](#part-1-fastapi-fundamentals)
2. [LangGraph Fundamentals](#part-2-langgraph-fundamentals)
3. [How They Work Together](#part-3-how-they-work-together-in-this-project)
4. [Project Architecture Deep Dive](#part-4-project-architecture-deep-dive)
5. [Hands-On Examples](#part-5-hands-on-examples)

---

# Part 1: FastAPI Fundamentals

## What is FastAPI?

**FastAPI** is a modern Python web framework for building APIs (Application Programming Interfaces).

**Think of it like a restaurant:**
- **Frontend (React)** = Customer ordering food
- **FastAPI** = Kitchen preparing the food
- **Database (PostgreSQL)** = Refrigerator storing ingredients

### Core Concept #1: Endpoints (Routes)

An **endpoint** is like a specific dish on the menu.

```python
from fastapi import FastAPI

app = FastAPI()

# GET endpoint - retrieve data
@app.get("/hello")
def say_hello():
    return {"message": "Hello, World!"}

# When you visit: http://localhost:8000/hello
# You get: {"message": "Hello, World!"}
```

**In Your Project** (`api/consumer_routes.py`):
```python
@router.post("/search", response_model=SearchResponse)
async def search_products(request: SearchRequest, db: Session = Depends(get_db)):
    # This is the endpoint that handles product searches
    # POST means sending data TO the server
    # The request contains: {"query": "laptop", "category": "Laptops"}

    # 1. Log the search to database
    search_record = UserSearch(query_text=request.query)
    db.add(search_record)

    # 2. Query the database for products
    query = db.query(Product, ProductListing).join(ProductListing)

    # 3. Apply filters
    if request.category:
        query = query.filter(Product.category == request.category)

    # 4. Execute and return results
    results = query.limit(20).all()

    return SearchResponse(results=results)
```

### Core Concept #2: Pydantic Models (Data Validation)

**Pydantic** models define what data should look like. FastAPI uses them to:
- **Validate** incoming data
- **Document** the API automatically
- **Convert** data types

```python
from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = None
    minPrice: Optional[float] = Field(None, ge=0)  # >= 0
    maxPrice: Optional[float] = Field(None, ge=0)

# FastAPI automatically validates:
# ✅ query is required and between 1-500 chars
# ✅ minPrice/maxPrice are >= 0 if provided
# ❌ Sends error if validation fails
```

**What happens when you send bad data:**
```json
POST /api/consumer/search
{
  "query": "",  // ❌ Too short (min_length=1)
  "minPrice": -10  // ❌ Negative (ge=0)
}

// FastAPI automatically responds:
{
  "error": "Validation error",
  "details": [
    {"field": "query", "message": "ensure this value has at least 1 characters"},
    {"field": "minPrice", "message": "ensure this value is greater than or equal to 0"}
  ]
}
```

### Core Concept #3: Dependency Injection

**Dependency Injection** = Automatically providing resources to functions.

```python
from fastapi import Depends
from sqlalchemy.orm import Session

def get_db():
    """Creates a database session"""
    db = SessionLocal()
    try:
        yield db  # Give it to the endpoint
    finally:
        db.close()  # Clean up after

@app.get("/products")
def list_products(db: Session = Depends(get_db)):
    # FastAPI automatically:
    # 1. Calls get_db()
    # 2. Passes the result to this function
    # 3. Closes the database when done

    return db.query(Product).all()
```

**Why this is powerful:**
- No manual session management
- Automatic cleanup
- Easy testing (can mock `get_db`)

### Core Concept #4: Async vs Sync

```python
# Synchronous (blocks while waiting)
@app.get("/slow")
def slow_endpoint():
    time.sleep(5)  # Blocks entire server!
    return {"done": True}

# Asynchronous (doesn't block)
@app.get("/fast")
async def fast_endpoint():
    await asyncio.sleep(5)  # Other requests can run!
    return {"done": True}
```

**In Your Project:**
- Most endpoints are `async` for better performance
- Database queries are sync (SQLAlchemy doesn't require async here)

### FastAPI Request Flow

```
1. Client sends HTTP request
   ↓
2. FastAPI receives request
   ↓
3. Pydantic validates request data
   ↓
4. Dependencies injected (database session)
   ↓
5. Endpoint function runs
   ↓
6. Response validated with Pydantic
   ↓
7. JSON response sent to client
   ↓
8. Dependencies cleaned up (database closed)
```

---

# Part 2: LangGraph Fundamentals

## What is LangGraph?

**LangGraph** is a framework for building **multi-agent workflows** where multiple AI agents work together.

**Think of it like an assembly line:**
- Each agent is a worker station
- Data flows from one station to the next
- Each station transforms the data
- Final product comes out at the end

### Core Concept #1: State

**State** = All the data that flows through the workflow.

```python
from dataclasses import dataclass

@dataclass
class AgentState:
    # Input
    user_query: str  # "laptop under $2000"

    # Agent 1 outputs
    extracted_category: str = None  # "Laptops"
    extracted_price_range: tuple = None  # (None, 2000)

    # Agent 2 outputs
    raw_products: list = None  # Scraped data

    # Agent 3 outputs
    clean_products: list = None  # Deduplicated data

    # Agent 4 outputs
    recommendations: list = None  # Top 5 products
```

**Why dataclass?**
- Easy to create: `state = AgentState(user_query="laptop")`
- Type hints help catch bugs
- Clean structure for passing data

### Core Concept #2: Agents

An **agent** is a single processing step.

```python
from backend.agents.base_agent import BaseAgent, AgentState

class QueryHandlerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="QueryHandler")

    async def process(self, state: AgentState) -> AgentState:
        # INPUT: state.user_query = "laptop under $2000"

        # PROCESSING
        query = state.user_query.lower()

        if "laptop" in query:
            state.extracted_category = "Laptops"

        # Extract price: "under $2000" → (None, 2000)
        if "under" in query:
            price = extract_number(query)
            state.extracted_price_range = (None, price)

        # OUTPUT: state with filled fields
        return state
```

**Agent Pattern:**
1. **Receive state** (with data from previous agents)
2. **Process data** (do one specific job)
3. **Update state** (add your results)
4. **Return state** (pass to next agent)

### Core Concept #3: Workflow Graph

**Workflow** = Connecting agents in sequence.

```python
from langgraph.graph import StateGraph, END

# Create workflow
workflow = StateGraph(AgentState)

# Add agents as "nodes"
workflow.add_node("agent1", agent1.process)
workflow.add_node("agent2", agent2.process)
workflow.add_node("agent3", agent3.process)

# Define flow with "edges"
workflow.set_entry_point("agent1")  # Start here
workflow.add_edge("agent1", "agent2")  # agent1 → agent2
workflow.add_edge("agent2", "agent3")  # agent2 → agent3
workflow.add_edge("agent3", END)  # agent3 → finish

# Compile
app = workflow.compile()

# Run
result = await app.ainvoke(initial_state)
```

**Visual Representation:**
```
User Query
    ↓
[Agent 1: Query Handler]
    ↓
[Agent 2: Data Collector]
    ↓
[Agent 3: Data Processor]
    ↓
[Agent 4: Recommender]
    ↓
Final Results
```

### Core Concept #4: Conditional Edges (Advanced)

You can have branching logic:

```python
def route_by_mode(state: AgentState):
    if state.mode == "consumer":
        return "consumer_recommender"
    else:
        return "business_analytics"

workflow.add_conditional_edges(
    "data_processor",  # From this node
    route_by_mode,  # Use this function to decide
    {
        "consumer_recommender": "consumer_recommender",
        "business_analytics": "business_analytics"
    }
)
```

**Your Project Uses Two Separate Workflows Instead:**
```python
# Consumer workflow
Query Handler → Data Collector → Data Processor → Consumer Recommender

# Business workflow
Query Handler → Data Collector → Data Processor → Business Analytics
```

---

# Part 3: How They Work Together in This Project

## The Big Picture

```
┌─────────────┐
│   FRONTEND  │  React app (user interface)
│  (React)    │
└──────┬──────┘
       │ HTTP Request (JSON)
       ↓
┌─────────────────────────────────────────────┐
│           FASTAPI SERVER                     │
│  (main.py + api/consumer_routes.py)         │
│                                              │
│  @router.post("/search")                    │
│  async def search_products(request):        │
│      # 1. Validate request                  │
│      # 2. Call LangGraph workflow (Phase 2) │
│      # 3. Query database                    │
│      # 4. Return results                    │
└──────┬──────────────────┬───────────────────┘
       │                   │
       ↓                   ↓
┌─────────────┐    ┌──────────────────┐
│  DATABASE   │    │  LANGGRAPH       │
│ (PostgreSQL)│    │  WORKFLOW        │
│             │    │                  │
│ - Products  │    │  Agent 1         │
│ - Listings  │    │     ↓            │
│ - Prices    │    │  Agent 2         │
└─────────────┘    │     ↓            │
                   │  Agent 3         │
                   │     ↓            │
                   │  Agent 4/5       │
                   └──────────────────┘
```

## Example Flow: User Searches for "laptop under $2000"

### Phase 1 (Current - Direct Database)

```python
# 1. Frontend sends request
fetch('http://localhost:8000/api/consumer/search', {
  method: 'POST',
  body: JSON.stringify({
    query: "laptop under $2000",
    category: "Laptops"
  })
})

# 2. FastAPI receives it
@router.post("/search")
async def search_products(request: SearchRequest, db: Session = Depends(get_db)):
    # 3. Create search log
    search_record = UserSearch(query_text=request.query)
    db.add(search_record)

    # 4. Query database directly
    results = db.query(Product, ProductListing)\
                .filter(Product.category == "Laptops")\
                .filter(ProductListing.price <= 2000)\
                .all()

    # 5. Convert to API response format
    products = [product_listing_to_response(p, l) for p, l in results]

    # 6. Return JSON
    return {
        "query": "laptop under $2000",
        "results": products,
        "totalResults": len(products)
    }
```

### Phase 2 (Planned - With LangGraph Agents)

```python
@router.post("/search")
async def search_products(request: SearchRequest, db: Session = Depends(get_db)):
    # 1. Create initial state
    state = AgentState(
        user_query=request.query,
        mode="consumer"
    )

    # 2. Run LangGraph workflow
    orchestrator = get_workflow_orchestrator()
    result = await orchestrator.run(
        user_query=request.query,
        mode="consumer"
    )

    # Workflow executes:
    # - Agent 1: Extracts "Laptops" category, (None, 2000) price range
    # - Agent 2: Scrapes Amazon, Flipkart for laptops under $2000
    # - Agent 3: Deduplicates and cleans data
    # - Agent 4: Ranks by value, generates AI recommendations

    # 3. Return results
    return {
        "query": request.query,
        "results": result["recommendations"],
        "totalResults": len(result["recommendations"])
    }
```

---

# Part 4: Project Architecture Deep Dive

## File-by-File Walkthrough

### 1. `main.py` - The Entry Point

```python
from fastapi import FastAPI
from backend.api import consumer_routes, business_routes

# Create app
app = FastAPI(title="AI Product Curator")

# Add CORS (allow frontend to call backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Your React app
    allow_methods=["*"],  # GET, POST, etc.
    allow_headers=["*"]  # Authorization, Content-Type, etc.
)

# Mount routes
app.include_router(
    consumer_routes.router,
    prefix="/api/consumer",  # All routes start with /api/consumer
    tags=["Consumer"]
)

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy"}

# Run with: python main.py
# Visit: http://localhost:8000/docs
```

### 2. `api/consumer_routes.py` - API Endpoints

```python
from fastapi import APIRouter

# Create router (like a mini-app)
router = APIRouter()

# Define Pydantic models
class SearchRequest(BaseModel):
    query: str
    category: Optional[str]

class SearchResponse(BaseModel):
    results: List[Product]
    totalResults: int

# Define endpoint
@router.post("/search", response_model=SearchResponse)
async def search_products(
    request: SearchRequest,  # Request body
    db: Session = Depends(get_db)  # Database session (auto-injected)
):
    """
    Full URL: POST http://localhost:8000/api/consumer/search

    Request body:
    {
      "query": "laptop",
      "category": "Laptops"
    }

    Response:
    {
      "results": [...],
      "totalResults": 5
    }
    """

    # Query database
    results = db.query(Product).filter(
        Product.category == request.category
    ).all()

    return SearchResponse(
        results=results,
        totalResults=len(results)
    )
```

### 3. `database/models.py` - ORM Models

```python
from sqlalchemy import Column, String, Integer, Numeric
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    # Each column = database field
    id = Column(UUID, primary_key=True)
    name = Column(String(500))
    category = Column(String(100))
    price = Column(Numeric(12, 2))

    # Relationship to other tables
    listings = relationship("ProductListing")

# Usage:
product = Product(
    name="MacBook Pro",
    category="Laptops",
    price=1999.00
)

db.add(product)  # INSERT INTO products ...
db.commit()  # Save to database
```

### 4. `agents/base_agent.py` - Base Agent Class

```python
class AgentState:
    """Data container passed between agents"""
    user_query: str
    extracted_category: str = None
    products: list = None
    recommendations: list = None

class BaseAgent:
    """All agents inherit from this"""

    async def process(self, state: AgentState) -> AgentState:
        """Override this in each agent"""
        raise NotImplementedError

    def log_start(self, state):
        print(f"{self.name} started")

    def log_end(self, state):
        print(f"{self.name} finished")
```

### 5. `agents/query_handler.py` - Agent 1

```python
class QueryHandlerAgent(BaseAgent):
    async def process(self, state: AgentState) -> AgentState:
        self.log_start(state)

        # INPUT: state.user_query = "laptop under $2000"

        # PROCESS: Extract category
        query = state.user_query.lower()
        if "laptop" in query:
            state.extracted_category = "Laptops"

        # PROCESS: Extract price
        match = re.search(r"under \$?(\d+)", query)
        if match:
            state.extracted_price_range = (None, int(match.group(1)))

        # OUTPUT: state with extracted info
        self.log_end(state)
        return state

# Agent 1 transforms:
# IN:  user_query = "laptop under $2000"
# OUT: user_query = "laptop under $2000"
#      extracted_category = "Laptops"
#      extracted_price_range = (None, 2000)
```

### 6. `agents/workflow.py` - Orchestrator

```python
class WorkflowOrchestrator:
    def __init__(self):
        # Create all agents
        self.agent1 = QueryHandlerAgent()
        self.agent2 = DataCollectorAgent()
        self.agent3 = DataProcessorAgent()
        self.agent4 = ConsumerRecommenderAgent()

        # Build workflow
        self.workflow = self._build_consumer_workflow()

    def _build_consumer_workflow(self):
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("query_handler", self.agent1.process)
        workflow.add_node("data_collector", self.agent2.process)
        workflow.add_node("data_processor", self.agent3.process)
        workflow.add_node("recommender", self.agent4.process)

        # Define flow
        workflow.set_entry_point("query_handler")
        workflow.add_edge("query_handler", "data_collector")
        workflow.add_edge("data_collector", "data_processor")
        workflow.add_edge("data_processor", "recommender")
        workflow.add_edge("recommender", END)

        return workflow.compile()

    async def run(self, user_query: str):
        # Create initial state
        state = AgentState(user_query=user_query)

        # Run workflow
        final_state = await self.workflow.ainvoke(state)

        # Return results
        return final_state.recommendations

# Usage:
orchestrator = WorkflowOrchestrator()
results = await orchestrator.run("laptop under $2000")
```

---

# Part 5: Hands-On Examples

## Example 1: How a Search Request Works

### Step-by-Step Execution

```python
# USER ACTION: Clicks search button
# Frontend sends:
POST http://localhost:8000/api/consumer/search
{
  "query": "gaming laptop",
  "category": "Laptops",
  "maxPrice": 1500
}

# ==========================================
# BACKEND EXECUTION STARTS
# ==========================================

# 1. FastAPI routes to consumer_routes.py
@router.post("/search")
async def search_products(request: SearchRequest, db: Session = Depends(get_db)):

    # 2. Pydantic validates request
    # ✅ query is string: "gaming laptop"
    # ✅ category is string: "Laptops"
    # ✅ maxPrice is number: 1500

    # 3. Create search log
    search_record = UserSearch(
        query_text="gaming laptop",
        extracted_category="Laptops",
        extracted_max_price=1500
    )
    db.add(search_record)  # INSERT INTO user_searches ...
    db.flush()  # Get ID but don't commit yet

    # 4. Build database query
    query = db.query(Product, ProductListing).join(ProductListing)

    # 5. Apply filters
    query = query.filter(Product.category == "Laptops")
    query = query.filter(ProductListing.price <= 1500)
    query = query.filter(Product.name.ilike("%gaming%"))

    # SQL Generated:
    # SELECT products.*, product_listings.*
    # FROM products
    # JOIN product_listings ON products.id = product_listings.product_id
    # WHERE products.category = 'Laptops'
    #   AND product_listings.price <= 1500
    #   AND products.name ILIKE '%gaming%'
    # LIMIT 20

    # 6. Execute query
    results = query.limit(20).all()
    # results = [(Product(...), ProductListing(...)), ...]

    # 7. Convert to API format
    products = []
    for product, listing in results:
        products.append({
            "id": str(listing.id),
            "name": product.name,
            "price": float(listing.price),
            "platform": listing.platform,
            "rating": float(listing.rating)
        })

    # 8. Update search record
    search_record.results_count = len(products)
    db.commit()  # COMMIT transaction

    # 9. Return response
    return {
        "searchId": str(search_record.id),
        "query": "gaming laptop",
        "results": products,
        "totalResults": len(products),
        "recommendations": products[:2]  # Top 2
    }

# ==========================================
# BACKEND EXECUTION ENDS
# ==========================================

# FRONTEND RECEIVES:
{
  "searchId": "abc-123",
  "query": "gaming laptop",
  "results": [
    {
      "id": "product-1",
      "name": "ASUS ROG Gaming Laptop",
      "price": 1299.99,
      "platform": "Amazon",
      "rating": 4.7
    },
    {
      "id": "product-2",
      "name": "MSI Gaming Laptop",
      "price": 1449.99,
      "platform": "Best Buy",
      "rating": 4.6
    }
  ],
  "totalResults": 2,
  "recommendations": [...]
}
```

## Example 2: How LangGraph Workflow Will Work (Phase 2)

```python
# USER QUERY: "best laptop for programming under 2000"

# ==========================================
# WORKFLOW EXECUTION
# ==========================================

# Initial State
state = AgentState(
    user_query="best laptop for programming under 2000",
    mode="consumer"
)

# -------- Agent 1: Query Handler --------
state = await agent1.process(state)
# OUTPUT:
# state.extracted_category = "Laptops"
# state.extracted_price_range = (None, 2000)
# state.query_intent = "recommendation"

# -------- Agent 2: Data Collector --------
state = await agent2.process(state)
# Scrapes:
# - Amazon for laptops under $2000
# - Flipkart for laptops under $2000
# - Best Buy for laptops under $2000
# OUTPUT:
# state.raw_products = [
#     {"name": "MacBook Pro", "price": 1999, "platform": "Amazon"},
#     {"name": "Dell XPS 13", "price": 1299, "platform": "Best Buy"},
#     {"name": "MacBook Pro", "price": 1999, "platform": "Apple"},  # Duplicate!
#     ...
# ]

# -------- Agent 3: Data Processor --------
state = await agent3.process(state)
# - Removes duplicate MacBook (same product, different platform)
# - Normalizes prices
# - Cleans data
# OUTPUT:
# state.clean_products = [
#     {"name": "MacBook Pro", "price": 1999, "platforms": ["Amazon", "Apple"]},
#     {"name": "Dell XPS 13", "price": 1299, "platforms": ["Best Buy"]},
#     ...
# ]

# -------- Agent 4: Recommender --------
state = await agent4.process(state)
# - Ranks by: rating, price, reviews, programming suitability
# - Generates AI explanations using LLM
# OUTPUT:
# state.recommendations = [
#     {
#         "name": "MacBook Pro",
#         "price": 1999,
#         "rating": 4.8,
#         "reason": "Best for programming: Unix-based, excellent battery, high-quality display"
#     },
#     {
#         "name": "Dell XPS 13",
#         "price": 1299,
#         "rating": 4.6,
#         "reason": "Great value: Linux compatible, good keyboard, portable"
#     }
# ]

# FINAL RESULT RETURNED TO API
```

---

## Key Takeaways

### FastAPI

1. **Endpoints** = Functions decorated with `@app.get()` / `@app.post()`
2. **Pydantic** = Automatic data validation
3. **Depends()** = Dependency injection (database sessions, etc.)
4. **async/await** = Better performance for I/O operations
5. **Auto docs** = Visit `/docs` for interactive API documentation

### LangGraph

1. **State** = Data container passed through workflow
2. **Agents** = Processing nodes (each does one job)
3. **Workflow** = Connects agents in sequence
4. **Graph** = Visual representation of data flow
5. **Orchestrator** = Manages workflow execution

### How They Connect

1. **FastAPI** receives HTTP requests from frontend
2. **FastAPI** calls **LangGraph workflow**
3. **LangGraph** runs agents sequentially
4. **Agents** process data (scrape, clean, rank)
5. **FastAPI** returns results to frontend

---

## Next Steps to Learn More

1. **Run the Basic Example**:
   ```bash
   cd backend/examples
   uvicorn fastapi_basics:app --reload
   ```
   Visit http://localhost:8000/docs

2. **Read the Code**:
   - Start with `main.py` (entry point)
   - Then `api/consumer_routes.py` (one endpoint)
   - Then `agents/query_handler.py` (one agent)
   - Then `agents/workflow.py` (how they connect)

3. **Modify and Experiment**:
   - Add a new endpoint in `consumer_routes.py`
   - Add a new agent that does sentiment analysis
   - Change the workflow order

4. **Official Docs**:
   - FastAPI: https://fastapi.tiangolo.com/
   - LangGraph: https://langchain-ai.github.io/langgraph/

---

**Questions to Think About**:
1. What happens if Agent 2 (scraper) fails? How would you handle that?
2. How would you add authentication (login) to the API?
3. How would you cache results so you don't scrape every time?
4. What if you wanted Agent 4 to use a different LLM model?

These are all Phase 2-4 enhancements! 🚀
