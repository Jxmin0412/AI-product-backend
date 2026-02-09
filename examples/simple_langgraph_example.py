"""
SIMPLE LANGGRAPH EXAMPLE
========================
This is the simplest possible LangGraph example to understand the concept.

Think of it like a food order:
- Agent 1: Takes order
- Agent 2: Cooks food
- Agent 3: Packages order
- Agent 4: Delivers to customer
"""
from dataclasses import dataclass, field
from typing import List

# ============================================
# STEP 1: Define State (Data Container)
# ============================================

@dataclass
class FoodOrderState:
    """
    This is like a clipboard that gets passed from person to person.
    Each person reads it, adds their info, and passes it along.
    """
    # Input (what customer wants)
    customer_order: str

    # Agent 1 outputs (order taker)
    parsed_order: dict = None

    # Agent 2 outputs (cook)
    cooked_food: List[str] = field(default_factory=list)

    # Agent 3 outputs (packager)
    packaged: bool = False
    bag_number: int = None

    # Agent 4 outputs (delivery)
    delivered: bool = False
    delivery_time: str = None


# ============================================
# STEP 2: Define Agents (Workers)
# ============================================

class OrderTaker:
    """Agent 1: Understands what customer wants"""

    def process(self, state: FoodOrderState) -> FoodOrderState:
        print(f"📝 ORDER TAKER: Received order: '{state.customer_order}'")

        # Parse the order
        order = state.customer_order.lower()

        if "burger" in order:
            state.parsed_order = {"item": "burger", "quantity": 1}
        elif "pizza" in order:
            state.parsed_order = {"item": "pizza", "quantity": 1}
        else:
            state.parsed_order = {"item": "sandwich", "quantity": 1}

        print(f"   ✅ Parsed: {state.parsed_order}")
        return state


class Cook:
    """Agent 2: Prepares the food"""

    def process(self, state: FoodOrderState) -> FoodOrderState:
        print(f"👨‍🍳 COOK: Preparing {state.parsed_order['item']}...")

        item = state.parsed_order["item"]

        # Simulate cooking
        if item == "burger":
            state.cooked_food = ["patty", "bun", "lettuce", "tomato"]
        elif item == "pizza":
            state.cooked_food = ["dough", "sauce", "cheese", "pepperoni"]
        else:
            state.cooked_food = ["bread", "meat", "cheese"]

        print(f"   ✅ Cooked: {', '.join(state.cooked_food)}")
        return state


class Packager:
    """Agent 3: Packages the food"""

    def process(self, state: FoodOrderState) -> FoodOrderState:
        print(f"📦 PACKAGER: Packaging food...")

        state.packaged = True
        state.bag_number = 12345

        print(f"   ✅ Packaged in bag #{state.bag_number}")
        return state


class DeliveryDriver:
    """Agent 4: Delivers the order"""

    def process(self, state: FoodOrderState) -> FoodOrderState:
        print(f"🚗 DRIVER: Delivering order...")

        state.delivered = True
        state.delivery_time = "15 minutes"

        print(f"   ✅ Delivered in {state.delivery_time}")
        return state


# ============================================
# STEP 3: Build Workflow (Connect Agents)
# ============================================

def run_food_order_workflow(customer_order: str):
    """
    Simple workflow WITHOUT LangGraph (for understanding).
    Just manually calling each agent in sequence.
    """
    print("\n" + "=" * 50)
    print(f"🍔 NEW ORDER: '{customer_order}'")
    print("=" * 50 + "\n")

    # Create initial state
    state = FoodOrderState(customer_order=customer_order)

    # Create agents
    order_taker = OrderTaker()
    cook = Cook()
    packager = Packager()
    driver = DeliveryDriver()

    # Run workflow manually (each agent processes state)
    state = order_taker.process(state)  # Agent 1
    state = cook.process(state)         # Agent 2
    state = packager.process(state)     # Agent 3
    state = driver.process(state)       # Agent 4

    # Final result
    print("\n" + "=" * 50)
    print("✅ ORDER COMPLETE!")
    print(f"   Item: {state.parsed_order['item']}")
    print(f"   Bag #: {state.bag_number}")
    print(f"   Delivered: {state.delivered}")
    print(f"   Time: {state.delivery_time}")
    print("=" * 50 + "\n")

    return state


# ============================================
# STEP 4: With LangGraph (Commented)
# ============================================

"""
# This is how you'd do it with LangGraph:

from langgraph.graph import StateGraph, END

def build_workflow():
    # Create graph
    workflow = StateGraph(FoodOrderState)

    # Add agents as nodes
    workflow.add_node("order_taker", OrderTaker().process)
    workflow.add_node("cook", Cook().process)
    workflow.add_node("packager", Packager().process)
    workflow.add_node("driver", DeliveryDriver().process)

    # Define flow (edges)
    workflow.set_entry_point("order_taker")  # Start here
    workflow.add_edge("order_taker", "cook")  # order_taker → cook
    workflow.add_edge("cook", "packager")     # cook → packager
    workflow.add_edge("packager", "driver")   # packager → driver
    workflow.add_edge("driver", END)          # driver → finish

    return workflow.compile()

# Run workflow
app = build_workflow()
result = app.invoke(FoodOrderState(customer_order="I want a burger"))
"""


# ============================================
# STEP 5: Run Examples
# ============================================

if __name__ == "__main__":
    # Example 1: Burger order
    result = run_food_order_workflow("I want a burger please")

    # Example 2: Pizza order
    result = run_food_order_workflow("Can I get a pizza?")

    # Example 3: Default order
    result = run_food_order_workflow("Give me something to eat")


"""
OUTPUT:
==================================================
🍔 NEW ORDER: 'I want a burger please'
==================================================

📝 ORDER TAKER: Received order: 'I want a burger please'
   ✅ Parsed: {'item': 'burger', 'quantity': 1}
👨‍🍳 COOK: Preparing burger...
   ✅ Cooked: patty, bun, lettuce, tomato
📦 PACKAGER: Packaging food...
   ✅ Packaged in bag #12345
🚗 DRIVER: Delivering order...
   ✅ Delivered in 15 minutes

==================================================
✅ ORDER COMPLETE!
   Item: burger
   Bag #: 12345
   Delivered: True
   Time: 15 minutes
==================================================


KEY CONCEPTS:

1. State = Clipboard with all info
   - Starts empty (just customer_order)
   - Each agent adds more info
   - Ends with complete order info

2. Agents = Workers
   - Each does ONE job
   - Reads state, adds to state, returns state
   - Can be tested independently

3. Workflow = Assembly line
   - Agents run in order
   - Output of Agent 1 → Input of Agent 2
   - Output of Agent 2 → Input of Agent 3
   - etc.

4. Why This Pattern?
   - Easy to add new agents (new worker)
   - Easy to change order (rearrange workers)
   - Easy to test (test one worker at a time)
   - Easy to debug (see state at each step)


HOW THIS RELATES TO YOUR PROJECT:

FoodOrderState          → AgentState
OrderTaker              → QueryHandlerAgent
Cook                    → DataCollectorAgent
Packager                → DataProcessorAgent
DeliveryDriver          → ConsumerRecommenderAgent

customer_order          → user_query
parsed_order            → extracted_category, extracted_price_range
cooked_food             → raw_products
packaged                → clean_products
delivered               → recommendations
"""
