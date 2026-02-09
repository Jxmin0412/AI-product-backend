"""
🕷️ ScrapeGraphAI Demo - Understanding How It Works
==================================================

This demo shows how ScrapeGraphAI uses AI to extract data from websites
using natural language prompts instead of CSS selectors.

Install first:
    pip install scrapegraph-py

Run:
    python scrapegraph_demo.py
"""

import asyncio
from pydantic import BaseModel, Field
from typing import Optional, List

# Install: pip install scrapegraph-py
from scrapegraph_py import Client

# Your API Key
API_KEY = "sgai-938b5362-e88f-4025-8e8c-f6276db5865b"


# ============================================
# EXAMPLE 1: Basic Scraping (Simple)
# ============================================

def example_basic_scraping():
    """
    Basic example: Just give a URL and a prompt
    The AI figures out how to extract the data
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Basic Scraping")
    print("=" * 60)

    client = Client(api_key=API_KEY)

    # Simple prompt - AI understands what you want
    response = client.smartscraper(
        website_url="https://www.example.com",
        user_prompt="Extract the main heading and any paragraph text from this page"
    )

    print(f"\n✅ Response:")
    print(response)

    return response


# ============================================
# EXAMPLE 2: Structured Output with Schema
# ============================================

# Define what data structure you want
class ProductInfo(BaseModel):
    """Schema for product data extraction"""
    name: str = Field(description="Product name")
    price: Optional[float] = Field(description="Product price as a number")
    rating: Optional[float] = Field(description="Product rating (0-5)")
    description: Optional[str] = Field(description="Product description")


def example_with_schema():
    """
    Extract data into a specific structure using Pydantic schema
    This ensures you get consistent, typed data
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Structured Output with Schema")
    print("=" * 60)

    client = Client(api_key=API_KEY)

    # With schema, LLM returns data matching your structure
    response = client.smartscraper(
        website_url="https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        user_prompt="Extract the product information from this book page",
        output_schema=ProductInfo
    )

    print(f"\n✅ Structured Response:")
    print(f"   Name: {response.get('name', 'N/A')}")
    print(f"   Price: {response.get('price', 'N/A')}")
    print(f"   Rating: {response.get('rating', 'N/A')}")
    print(f"   Description: {response.get('description', 'N/A')[:100]}...")

    return response


# ============================================
# EXAMPLE 3: E-commerce Product List
# ============================================

class Product(BaseModel):
    """Schema for a single product"""
    name: str = Field(description="Product name")
    price: str = Field(description="Product price with currency")
    availability: Optional[str] = Field(description="Stock availability")


class ProductList(BaseModel):
    """Schema for multiple products"""
    products: List[Product] = Field(description="List of products on the page")


def example_product_list():
    """
    Extract multiple products from a listing page
    Great for e-commerce scraping
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 3: E-commerce Product List")
    print("=" * 60)

    client = Client(api_key=API_KEY)

    response = client.smartscraper(
        website_url="https://books.toscrape.com/",
        user_prompt="Extract all the book products shown on this page including their names and prices",
        output_schema=ProductList
    )

    print(f"\n✅ Found Products:")
    products = response.get('products', [])
    for i, product in enumerate(products[:5], 1):  # Show first 5
        print(f"   {i}. {product.get('name', 'Unknown')} - {product.get('price', 'N/A')}")

    print(f"\n   ... and {len(products) - 5} more products") if len(products) > 5 else None

    return response


# ============================================
# EXAMPLE 4: News/Article Extraction
# ============================================

class Article(BaseModel):
    """Schema for article/news extraction"""
    title: str = Field(description="Article title")
    author: Optional[str] = Field(description="Author name")
    date: Optional[str] = Field(description="Publication date")
    summary: Optional[str] = Field(description="Article summary or first paragraph")
    topics: Optional[List[str]] = Field(description="Main topics or tags")


def example_article_extraction():
    """
    Extract article information from a news page
    Works with blogs, news sites, documentation, etc.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Article Extraction")
    print("=" * 60)

    client = Client(api_key=API_KEY)

    response = client.smartscraper(
        website_url="https://en.wikipedia.org/wiki/Web_scraping",
        user_prompt="Extract the main article information: title, summary of what it's about, and key topics covered",
        output_schema=Article
    )

    print(f"\n✅ Article Info:")
    print(f"   Title: {response.get('title', 'N/A')}")
    print(f"   Author: {response.get('author', 'N/A')}")
    print(f"   Summary: {response.get('summary', 'N/A')[:200]}...")
    print(f"   Topics: {response.get('topics', [])}")

    return response


# ============================================
# EXAMPLE 5: Interactive Mode - User Input
# ============================================

def example_interactive():
    """
    Interactive mode - let user input URL and prompt
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Interactive Mode")
    print("=" * 60)

    client = Client(api_key=API_KEY)

    # Get user input
    url = input("\n🌐 Enter website URL: ").strip()
    if not url:
        url = "https://books.toscrape.com/"
        print(f"   Using default: {url}")

    prompt = input("💬 What do you want to extract? ").strip()
    if not prompt:
        prompt = "Extract all product names and prices"
        print(f"   Using default: {prompt}")

    print(f"\n⏳ Scraping {url}...")
    print(f"   Prompt: {prompt}")

    try:
        response = client.smartscraper(
            website_url=url,
            user_prompt=prompt
        )

        print(f"\n✅ Result:")
        print(response)

    except Exception as e:
        print(f"\n❌ Error: {e}")

    return response


# ============================================
# EXAMPLE 6: Compare with Traditional Scraping
# ============================================

def example_comparison():
    """
    Show the difference between traditional and AI scraping
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Traditional vs AI Scraping Comparison")
    print("=" * 60)

    print("""
    📌 TRADITIONAL SCRAPING (BeautifulSoup):
    ----------------------------------------
    ```python
    from bs4 import BeautifulSoup
    import requests

    response = requests.get("https://books.toscrape.com/")
    soup = BeautifulSoup(response.text, 'html.parser')

    products = []
    for article in soup.select('article.product_pod'):
        name = article.select_one('h3 a')['title']
        price = article.select_one('.price_color').text
        products.append({'name': name, 'price': price})
    ```

    ❌ Problems:
    - Breaks when HTML structure changes
    - Need to inspect page source manually
    - Different selectors for each website
    - Can't handle dynamic content easily


    📌 AI SCRAPING (ScrapeGraphAI):
    -------------------------------
    ```python
    from scrapegraph_py import Client

    client = Client(api_key="your-key")
    response = client.smartscraper(
        website_url="https://books.toscrape.com/",
        user_prompt="Extract all product names and prices"
    )
    ```

    ✅ Benefits:
    - Adapts to HTML changes automatically
    - Natural language prompts
    - Works across different websites
    - Handles dynamic content
    - No manual inspection needed
    """)

    # Actually run the AI version
    print("\n🤖 Running AI Scraper...")

    client = Client(api_key=API_KEY)
    response = client.smartscraper(
        website_url="https://books.toscrape.com/",
        user_prompt="Extract the first 3 book names and their prices"
    )

    print(f"\n✅ AI Scraper Result:")
    print(response)


# ============================================
# MAIN - Run Examples
# ============================================

def main():
    """
    Main function - choose which example to run
    """
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║   🕷️  ScrapeGraphAI Demo                                   ║
    ║                                                            ║
    ║   See how AI-powered web scraping works!                  ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝

    Choose an example to run:

    1. Basic Scraping (simple URL + prompt)
    2. Structured Output (with Pydantic schema)
    3. E-commerce Product List
    4. Article/News Extraction
    5. Interactive Mode (your own URL + prompt)
    6. Traditional vs AI Comparison

    0. Run ALL examples
    """)

    choice = input("Enter your choice (0-6): ").strip()

    if choice == "1":
        example_basic_scraping()
    elif choice == "2":
        example_with_schema()
    elif choice == "3":
        example_product_list()
    elif choice == "4":
        example_article_extraction()
    elif choice == "5":
        example_interactive()
    elif choice == "6":
        example_comparison()
    elif choice == "0":
        example_basic_scraping()
        example_with_schema()
        example_product_list()
        example_article_extraction()
        example_comparison()
    else:
        print("Invalid choice. Running interactive mode...")
        example_interactive()

    print("\n" + "=" * 60)
    print("🎉 Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
