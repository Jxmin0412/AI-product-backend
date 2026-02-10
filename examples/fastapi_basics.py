"""
FastAPI Basics - Understanding the fundamentals
Run this: uvicorn fastapi_basics:app --reload
Then visit: http://localhost:8000/docs
"""
from fastapi import FastAPI
from pydantic import BaseModel

# Step 1: Create the FastAPI app (like creating a restaurant)
app = FastAPI(title="My First API")

# Step 2: Define what data looks like (Pydantic models = menu items)
class Pizza(BaseModel):
    name: str
    size: str  # small, medium, large
    toppings: list[str]
    price: float

# Step 3: Create endpoints (routes = menu options)

# GET endpoint - Read data
@app.get("/")
def home():
    """Simple endpoint that returns a greeting"""
    return {"message": "Welcome to Pizza API!"}

# GET with path parameter
@app.get("/pizza/{pizza_id}")
def get_pizza(pizza_id: int):
    """Get a specific pizza by ID"""
    return {
        "id": pizza_id,
        "name": "Margherita",
        "size": "large",
        "price": 12.99
    }

# POST endpoint - Create data
@app.post("/order")
def order_pizza(pizza: Pizza):
    """Order a new pizza - FastAPI automatically validates the data!"""
    total = pizza.price

    return {
        "message": f"Order received for {pizza.name}!",
        "total": total,
        "pizza": pizza
    }

# GET with query parameters
@app.get("/menu")
def get_menu(size: str = "medium", max_price: float = 20.0):
    """
    Get menu items filtered by size and price
    Example: /menu?size=large&max_price=15.0
    """
    return {
        "filters": {"size": size, "max_price": max_price},
        "results": ["Margherita", "Pepperoni"]
    }

"""
KEY CONCEPTS:

1. @app.get() / @app.post() = Decorators that define HTTP methods
2. Path parameters: /pizza/{pizza_id} - dynamic URLs
3. Query parameters: ?size=large&max_price=15.0 - filters
4. Request body: Pizza model - structured input data
5. Pydantic validation: Automatic data validation & error messages
6. Type hints: FastAPI uses them for validation and docs

Visit /docs to see auto-generated API documentation!
"""
