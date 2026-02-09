# 🎓 Learning Resources for FastAPI + LangGraph

This folder contains comprehensive learning materials to help you understand the AI Product Curator backend.

---

## 📚 Learning Path (Start Here!)

### **Step 1: Interactive Tutorial** ⭐ START HERE
```bash
python run_this_first.py
```
**What you'll learn:**
- What is "state" and why it matters
- How agents process data sequentially
- How workflows connect agents
- How it relates to your project

**Time: 10 minutes**

---

### **Step 2: Simple LangGraph Example**
```bash
python simple_langgraph_example.py
```
**What you'll learn:**
- Real LangGraph code (food order workflow)
- How to create agents
- How to build workflows
- State management patterns

**Time: 15 minutes**

---

### **Step 3: Read the Complete Guide**
Open: `LEARNING_GUIDE.md`

**What you'll learn:**
- FastAPI fundamentals (endpoints, validation, dependencies)
- LangGraph fundamentals (state, agents, workflows)
- How they work together in this project
- Step-by-step request flow with code examples
- Hands-on examples you can try

**Time: 30-45 minutes**

---

### **Step 4: Architecture Deep Dive**
Open: `HOW_IT_ALL_CONNECTS.md`

**What you'll learn:**
- Visual architecture diagrams
- Complete request flow from frontend to database
- Where each file fits in the system
- Database relationships
- Common questions answered

**Time: 20 minutes**

---

### **Step 5: Quick Reference**
Open: `CHEAT_SHEET.md`

**What you'll learn:**
- Quick syntax reference for FastAPI
- Quick syntax reference for LangGraph
- Common patterns in this project
- Useful commands and debugging tips

**Time: Reference material (bookmark it!)**

---

### **Step 6: Basic FastAPI** (Optional)
```bash
uvicorn fastapi_basics:app --reload
```
Then visit: http://localhost:8000/docs

**What you'll learn:**
- How to create a simple API from scratch
- GET vs POST requests
- Path and query parameters
- Request validation with Pydantic

**Time: 15 minutes**

---

## 📖 Files in This Folder

| File | Type | Purpose | When to Use |
|------|------|---------|-------------|
| `run_this_first.py` | Script | Interactive tutorial with agents | First thing to run |
| `simple_langgraph_example.py` | Script | Food order workflow example | Learn LangGraph basics |
| `fastapi_basics.py` | Script | Pizza API example | Learn FastAPI basics |
| `LEARNING_GUIDE.md` | Doc | Complete tutorial | Deep understanding |
| `HOW_IT_ALL_CONNECTS.md` | Doc | Architecture guide | See the big picture |
| `CHEAT_SHEET.md` | Doc | Quick reference | Need syntax fast |

---

## 🎯 Learning by Doing

### After Reading, Try These:

#### 1. Add a New Endpoint
**Goal**: Add a "featured products" endpoint

```python
# In backend/api/consumer_routes.py

@router.get("/featured")
async def get_featured_products(db: Session = Depends(get_db)):
    # Get products with rating > 4.5
    products = db.query(Product, ProductListing).join(ProductListing)\
        .filter(ProductListing.rating > 4.5)\
        .limit(5)\
        .all()

    return [product_listing_to_response(p, l) for p, l in products]
```

**Test it:**
```bash
curl http://localhost:8000/api/consumer/featured
```

---

#### 2. Create a Custom Agent
**Goal**: Create an agent that filters out expensive products

```python
# In backend/agents/price_filter.py

from backend.agents.base_agent import BaseAgent, AgentState

class PriceFilterAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="PriceFilter")

    async def process(self, state: AgentState) -> AgentState:
        self.log_start(state)

        # Filter products over $2000
        filtered = [
            p for p in state.processed_products
            if p.get("price", 0) <= 2000
        ]

        state.processed_products = filtered

        self.log_end(state)
        return state
```

**Add to workflow:**
```python
# In backend/agents/workflow.py

from backend.agents.price_filter import PriceFilterAgent

# In __init__
self.price_filter = PriceFilterAgent()

# In _build_consumer_workflow
workflow.add_node("price_filter", self.price_filter.process)
workflow.add_edge("data_processor", "price_filter")
workflow.add_edge("price_filter", "consumer_recommender")
```

---

#### 3. Modify Search Logic
**Goal**: Make search case-insensitive and search descriptions too

```python
# In backend/api/consumer_routes.py

# Change this:
query = query.filter(Product.name.ilike(search_term))

# To this:
query = query.filter(
    (Product.name.ilike(search_term)) |
    (Product.description.ilike(search_term))
)
```

---

## 🤔 Common Questions

### Q: What should I learn first?

**A:** Run `run_this_first.py` first! It's interactive and teaches core concepts without complexity.

### Q: I don't understand LangGraph. Help?

**A:**
1. Think of it like an assembly line
2. Each agent = one worker
3. State = clipboard passed between workers
4. Workflow = connecting the workers in order
5. Read `simple_langgraph_example.py` - it's a food order system

### Q: I don't understand FastAPI. Help?

**A:**
1. FastAPI = web server
2. Endpoint = function that responds to URLs
3. `@app.get("/path")` = responds to GET requests
4. `@app.post("/path")` = responds to POST requests
5. Run `uvicorn fastapi_basics:app --reload` and visit `/docs`

### Q: How do I debug?

**A:**
```python
# Add print statements
print(f"State: {state}")

# Add logging
logger.info(f"Processing: {query}")

# Check database
from backend.database.connection import db_manager
print(db_manager.health_check())

# Test agent independently
agent = QueryHandlerAgent()
state = AgentState(user_query="test")
result = await agent.process(state)
print(result)
```

### Q: Where should I make changes?

| Want to... | Edit this file... |
|-----------|-------------------|
| Add API endpoint | `api/consumer_routes.py` or `api/business_routes.py` |
| Add database table | `database/models.py` + run `reset_db()` |
| Change agent logic | `agents/[agent_name].py` |
| Change workflow order | `agents/workflow.py` |
| Add LLM feature | `utils/huggingface_client.py` |
| Change config | `.env` file |

### Q: Can I break something?

**A:** Yes! And you should! That's how you learn.

**Safe to modify:**
- `examples/` folder (this folder)
- Create new files in `agents/`
- Add endpoints in `api/`

**Be careful:**
- `database/models.py` (requires database reset)
- `main.py` (might break server)
- `.env` (don't commit secrets)

**If you break it:**
```bash
# Reset database
python
>>> from database.connection import reset_db
>>> reset_db()
>>> exit()

# Reinstall
pip install -r requirements.txt

# Reseed
python database/seed.py
```

---

## 🚀 Next Steps After Learning

### Phase 2 Features You Can Implement:

1. **Web Scraping** (Agent 2)
   - Use BeautifulSoup or Playwright
   - Scrape Amazon product pages
   - Store results in database

2. **LLM Query Understanding** (Agent 1)
   - Use Hugging Face to parse queries
   - Extract complex intent
   - Handle typos and variations

3. **Product Matching with Embeddings** (Agent 3)
   - Use sentence-transformers
   - Match products across platforms
   - Deduplicate by similarity

4. **AI Explanations** (Agent 4)
   - Generate "why recommended" text
   - Personalize based on query
   - Use Hugging Face LLM

5. **Business Insights** (Agent 5)
   - Trend analysis
   - Market forecasting
   - Competitive positioning

---

## 📞 Need Help?

1. **Re-read the guides** - Seriously, read them again!
2. **Check the cheat sheet** - Quick syntax reference
3. **Read official docs**:
   - FastAPI: https://fastapi.tiangolo.com/
   - LangGraph: https://langchain-ai.github.io/langgraph/
   - SQLAlchemy: https://docs.sqlalchemy.org/
4. **Run the examples** - See working code
5. **Ask specific questions** - "How do I..." not "I don't understand"

---

## ✨ Remember

1. **Start simple** - Don't try to understand everything at once
2. **Run the code** - Reading alone won't help
3. **Modify and break** - Best way to learn
4. **Read error messages** - They tell you what's wrong
5. **Be patient** - This is complex! Take your time

---

**Happy Learning! 🎓**

You're building something cool. Take it one step at a time, and you'll get there! 🚀
