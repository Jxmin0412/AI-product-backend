# 📝 FastAPI + LangGraph Cheat Sheet

## FastAPI Quick Reference

### Creating an App
```python
from fastapi import FastAPI

app = FastAPI(title="My API")
```

### Defining Endpoints

```python
# GET endpoint (retrieve data)
@app.get("/items")
def get_items():
    return {"items": [1, 2, 3]}

# POST endpoint (create data)
@app.post("/items")
def create_item(item: Item):
    return {"created": item}

# Path parameter
@app.get("/items/{item_id}")
def get_item(item_id: int):
    return {"item_id": item_id}

# Query parameter
@app.get("/search")
def search(q: str, limit: int = 10):
    # /search?q=laptop&limit=20
    return {"query": q, "limit": limit}
```

### Pydantic Models (Data Validation)

```python
from pydantic import BaseModel, Field

class Item(BaseModel):
    name: str
    price: float = Field(..., gt=0)  # Must be > 0
    description: str | None = None

# FastAPI auto-validates:
# ✅ name is required
# ✅ price must be positive
# ❌ Sends 422 error if invalid
```

### Dependency Injection

```python
from fastapi import Depends

def get_current_user():
    return {"user": "john"}

@app.get("/profile")
def get_profile(user = Depends(get_current_user)):
    return user  # FastAPI auto-calls get_current_user()
```

### Database Session (Your Project)

```python
from sqlalchemy.orm import Session
from backend.database.connection import get_db

@app.get("/products")
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).all()
```

### Async Endpoints

```python
# Synchronous (blocks)
@app.get("/slow")
def slow_endpoint():
    time.sleep(5)
    return {"done": True}

# Asynchronous (doesn't block)
@app.get("/fast")
async def fast_endpoint():
    await asyncio.sleep(5)
    return {"done": True}
```

### Error Handling

```python
from fastapi import HTTPException

@app.get("/items/{item_id}")
def get_item(item_id: int):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return items[item_id]
```

### Running the Server

```bash
# Development (auto-reload)
uvicorn main:app --reload

# Production
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Auto-Generated Docs

```
http://localhost:8000/docs       # Swagger UI
http://localhost:8000/redoc      # ReDoc
```

---

## LangGraph Quick Reference

### State Definition

```python
from dataclasses import dataclass

@dataclass
class MyState:
    user_query: str
    extracted_info: dict = None
    results: list = None
```

### Agent Class

```python
class MyAgent:
    def __init__(self, name: str):
        self.name = name

    async def process(self, state: MyState) -> MyState:
        # Read state
        query = state.user_query

        # Process
        info = extract_info(query)

        # Update state
        state.extracted_info = info

        # Return state
        return state
```

### Building a Workflow

```python
from langgraph.graph import StateGraph, END

# Create graph
workflow = StateGraph(MyState)

# Add agents as nodes
workflow.add_node("agent1", agent1.process)
workflow.add_node("agent2", agent2.process)

# Define flow
workflow.set_entry_point("agent1")
workflow.add_edge("agent1", "agent2")
workflow.add_edge("agent2", END)

# Compile
app = workflow.compile()
```

### Running a Workflow

```python
# Create initial state
state = MyState(user_query="laptop under $2000")

# Run workflow
final_state = await app.ainvoke(state)

# Access results
print(final_state.results)
```

### Conditional Routing

```python
def route_by_intent(state: MyState):
    if state.intent == "search":
        return "search_agent"
    else:
        return "recommend_agent"

workflow.add_conditional_edges(
    "classifier",
    route_by_intent,
    {
        "search_agent": "search_agent",
        "recommend_agent": "recommend_agent"
    }
)
```

---

## Database (SQLAlchemy) Quick Reference

### Model Definition

```python
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(500))
    price = Column(Integer)

    # Relationship
    listings = relationship("Listing")
```

### Queries

```python
# Get all
products = db.query(Product).all()

# Filter
laptops = db.query(Product).filter(Product.category == "Laptops").all()

# Filter with conditions
cheap_laptops = db.query(Product).filter(
    Product.category == "Laptops",
    Product.price < 1000
).all()

# Join
results = db.query(Product, Listing).join(Listing).all()

# Order by
sorted_products = db.query(Product).order_by(Product.price.desc()).all()

# Limit
top_5 = db.query(Product).limit(5).all()

# First or None
product = db.query(Product).filter(Product.id == 1).first()
```

### Insert

```python
new_product = Product(name="MacBook", price=1999)
db.add(new_product)
db.commit()
```

### Update

```python
product = db.query(Product).filter(Product.id == 1).first()
product.price = 1899
db.commit()
```

### Delete

```python
db.query(Product).filter(Product.id == 1).delete()
db.commit()
```

---

## Your Project Structure Quick Reference

```
backend/
├── main.py                    # FastAPI app entry point
├── requirements.txt           # Python dependencies
├── .env                       # Configuration (secrets)
│
├── config/
│   └── settings.py           # Load environment variables
│
├── database/
│   ├── models.py             # SQLAlchemy ORM models
│   ├── connection.py         # Database session manager
│   ├── schema.sql            # Raw SQL schema
│   └── seed.py               # Sample data
│
├── api/
│   ├── consumer_routes.py    # Consumer endpoints
│   └── business_routes.py    # Business endpoints
│
├── agents/
│   ├── base_agent.py         # Base class + AgentState
│   ├── query_handler.py      # Agent 1: Parse queries
│   ├── data_collector.py     # Agent 2: Scrape data
│   ├── data_processor.py     # Agent 3: Clean data
│   ├── consumer_recommender.py  # Agent 4: Recommendations
│   ├── business_analytics.py    # Agent 5: Business insights
│   └── workflow.py           # LangGraph orchestrator
│
└── utils/
    └── huggingface_client.py # LLM API client
```

---

## Common Patterns in Your Project

### API Endpoint Pattern

```python
@router.post("/search", response_model=SearchResponse)
async def search_products(
    request: SearchRequest,           # Request body (validated)
    db: Session = Depends(get_db)     # Database session (injected)
):
    # 1. Log to database
    search = UserSearch(query=request.query)
    db.add(search)

    # 2. Query database
    results = db.query(Product).filter(...).all()

    # 3. Convert to response format
    products = [convert(r) for r in results]

    # 4. Return
    return SearchResponse(results=products)
```

### Agent Pattern

```python
class MyAgent(BaseAgent):
    async def process(self, state: AgentState) -> AgentState:
        self.log_start(state)

        try:
            # Do work
            state.output = process_input(state.input)

        except Exception as e:
            self.log_error(e, state)

        self.log_end(state)
        return state
```

### Workflow Pattern (Phase 2)

```python
@router.post("/search")
async def search(request: SearchRequest):
    # Create state
    state = AgentState(user_query=request.query)

    # Run workflow
    orchestrator = get_workflow_orchestrator()
    result = await orchestrator.run(
        user_query=request.query,
        mode="consumer"
    )

    # Return results
    return result["recommendations"]
```

---

## Common Commands

### Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Create database
python database/seed.py

# Start server
python main.py

# Or with uvicorn
uvicorn main:app --reload
```

### Database

```bash
# PostgreSQL
psql -U postgres
CREATE DATABASE ecommerce_ai;
\q

# Reset database
python
>>> from database.connection import reset_db
>>> reset_db()
```

### Testing

```bash
# Manual test
curl http://localhost:8000/health

# Interactive docs
http://localhost:8000/docs
```

---

## Useful Debugging

### Print SQL Queries

```python
# In settings.py
engine = create_engine(DATABASE_URL, echo=True)
```

### FastAPI Debug Mode

```python
# In main.py
app = FastAPI(debug=True)
```

### Check Database Connection

```python
from backend.database.connection import db_manager
print(db_manager.health_check())
```

### Test Agent Independently

```python
from backend.agents.query_handler import QueryHandlerAgent

agent = QueryHandlerAgent()
state = AgentState(user_query="laptop under $2000")
result = await agent.process(state)
print(result.extracted_category)  # "Laptops"
```

---

## Key Concepts Summary

| Concept | What It Is | Example |
|---------|-----------|---------|
| **Endpoint** | URL that accepts requests | `/api/consumer/search` |
| **Pydantic Model** | Data validator | `class SearchRequest(BaseModel)` |
| **ORM Model** | Database table class | `class Product(Base)` |
| **Dependency** | Auto-injected resource | `db: Session = Depends(get_db)` |
| **State** | Data passed between agents | `AgentState` |
| **Agent** | Processing node | `QueryHandlerAgent` |
| **Workflow** | Connected agents | `Agent1 → Agent2 → Agent3` |
| **Orchestrator** | Workflow manager | `WorkflowOrchestrator` |

---

## URLs to Remember

```
Backend API:     http://localhost:8000
API Docs:        http://localhost:8000/docs
Health Check:    http://localhost:8000/health
Frontend:        http://localhost:5173
```

---

## Next Steps

1. ✅ Read `LEARNING_GUIDE.md` for detailed explanations
2. ✅ Run `run_this_first.py` for interactive tutorial
3. ✅ Check `HOW_IT_ALL_CONNECTS.md` for architecture
4. ✅ Start backend: `python main.py`
5. ✅ Explore APIs: http://localhost:8000/docs
6. ✅ Modify `consumer_routes.py` to add endpoint
7. ✅ Create custom agent in `agents/`

---

**Remember**: Code is just text. Read it, modify it, break it, fix it. That's how you learn! 🚀
