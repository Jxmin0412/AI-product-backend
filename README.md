# AI Product Curator - Backend

Backend system for the AI Product Curator - a dual-purpose e-commerce intelligence platform powered by LangGraph multi-agent system and Hugging Face models.

## Features

- **5-Agent LangGraph System**: Query Handler, Data Collector, Data Processor, Consumer Recommender, Business Analytics
- **Dual Mode Operation**: Consumer product search + Business intelligence
- **FastAPI Server**: High-performance async API with OpenAPI docs
- **PostgreSQL Database**: Robust data persistence with time-series support
- **Hugging Face Integration**: Open-source LLM inference via API
- **Scalable Architecture**: Modular design for Phase 2-4 enhancements

---

## Tech Stack

- **Framework**: Python 3.11+, FastAPI 0.109+
- **Agents**: LangChain, LangGraph
- **LLM**: Hugging Face Inference API (Mistral-7B-Instruct)
- **Database**: PostgreSQL 15+
- **ORM**: SQLAlchemy 2.0+
- **Data Processing**: Pandas, NumPy
- **Web Scraping**: BeautifulSoup4, Playwright (Phase 2)

---

## Prerequisites

Before starting, ensure you have:

1. **Python 3.11 or higher** - [Download](https://www.python.org/downloads/)
2. **PostgreSQL 15+** - [Download](https://www.postgresql.org/download/)
3. **Hugging Face Account** - [Sign up](https://huggingface.co/join) and get API key

---

## Installation

### Step 1: Clone and Navigate

```bash
cd "C:\Users\bharg\OneDrive\Desktop\projects\AI product curator\backend"
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Setup PostgreSQL Database

**Option A: Using psql command line**

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE ecommerce_ai;

# Create user (optional)
CREATE USER ai_curator WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ecommerce_ai TO ai_curator;

# Exit
\q
```

**Option B: Using pgAdmin**

1. Open pgAdmin
2. Right-click on "Databases" → Create → Database
3. Name: `ecommerce_ai`
4. Click "Save"

### Step 5: Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` file with your configuration:

```env
# Database Configuration
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/ecommerce_ai
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ecommerce_ai
DB_USER=postgres
DB_PASSWORD=your_password

# Hugging Face API
HUGGINGFACE_API_KEY=hf_your_api_key_here
HUGGINGFACE_MODEL=mistralai/Mistral-7B-Instruct-v0.2

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Application Settings
ENVIRONMENT=development
LOG_LEVEL=INFO
```

**Getting Hugging Face API Key:**

1. Go to https://huggingface.co/settings/tokens
2. Click "New token"
3. Name it "AI Product Curator"
4. Select "Read" permission
5. Copy the token to your `.env` file

### Step 6: Initialize Database

Run the seed script to create tables and populate sample data:

```bash
cd backend
python database/seed.py
```

You should see:
```
INFO - Starting database seeding...
INFO - Database initialized successfully
INFO - Seeding products and listings...
INFO - Products and listings seeded successfully
INFO - Database seeding completed successfully!
```

---

## Running the Server

### Development Mode

```bash
# From backend directory
python main.py
```

Or using uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server will start at:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Verify Installation

Check these endpoints:

1. **Root**: http://localhost:8000/
   ```json
   {
     "message": "AI Product Curator API",
     "version": "1.0.0",
     "status": "running"
   }
   ```

2. **Health Check**: http://localhost:8000/health
   ```json
   {
     "status": "healthy",
     "database": "connected",
     "environment": "development"
   }
   ```

3. **API Documentation**: http://localhost:8000/docs
   - Interactive Swagger UI for testing endpoints

---

## API Endpoints

### Consumer Endpoints (`/api/consumer`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/search` | Search products across platforms |
| GET | `/compare/{product_id}` | Compare prices for a product |
| GET | `/recommendations` | Get AI recommendations |
| GET | `/products/{product_id}` | Get product details |

### Business Endpoints (`/api/business`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard-data` | Complete business dashboard |
| GET | `/insights` | AI-generated business insights |
| GET | `/market-overview` | Market statistics |
| GET | `/price-trends/{category}` | Price trend analysis |

---

## Testing the API

### Using the Interactive Docs

1. Open http://localhost:8000/docs
2. Try the **POST /api/consumer/search** endpoint:
   - Click "Try it out"
   - Enter request body:
     ```json
     {
       "query": "laptop under 2000",
       "category": "Laptops"
     }
     ```
   - Click "Execute"

### Using curl

```bash
# Search products
curl -X POST http://localhost:8000/api/consumer/search \
  -H "Content-Type: application/json" \
  -d '{"query": "laptop", "category": "Laptops"}'

# Get dashboard data
curl http://localhost:8000/api/business/dashboard-data
```

### Using Python

```python
import requests

# Search products
response = requests.post(
    "http://localhost:8000/api/consumer/search",
    json={"query": "headphones", "category": "Audio"}
)
print(response.json())
```

---

## Project Structure

```
backend/
├── agents/                  # LangGraph agent system
│   ├── base_agent.py       # Base agent class
│   ├── query_handler.py    # Agent 1: Query processing
│   ├── data_collector.py   # Agent 2: Web scraping
│   ├── data_processor.py   # Agent 3: Data cleaning
│   ├── consumer_recommender.py  # Agent 4: Recommendations
│   ├── business_analytics.py    # Agent 5: Business intelligence
│   └── workflow.py         # LangGraph workflow orchestration
├── api/                    # FastAPI routes
│   ├── consumer_routes.py  # Consumer-facing endpoints
│   └── business_routes.py  # Business intelligence endpoints
├── database/               # Database layer
│   ├── models.py          # SQLAlchemy models
│   ├── connection.py      # Database connection manager
│   ├── schema.sql         # PostgreSQL schema
│   └── seed.py            # Sample data seeder
├── config/                # Configuration
│   └── settings.py        # Environment settings
├── utils/                 # Utilities
│   └── huggingface_client.py  # HF API client
├── main.py               # FastAPI application
├── requirements.txt      # Python dependencies
├── .env.example         # Example environment variables
└── README.md           # This file
```

---

## Development Workflow

### Making Changes

1. **Edit code** in your IDE
2. **Server auto-reloads** (if using `--reload` flag)
3. **Test changes** via http://localhost:8000/docs

### Database Changes

After modifying models:

```bash
# Reset database (WARNING: Deletes all data)
python
>>> from database.connection import reset_db
>>> reset_db()
>>> exit()

# Re-seed data
python database/seed.py
```

### Adding New Endpoints

1. Add route function to `api/consumer_routes.py` or `api/business_routes.py`
2. Define Pydantic models for request/response
3. Test in Swagger UI

---

## Troubleshooting

### Database Connection Error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution:**
- Ensure PostgreSQL is running
- Check DATABASE_URL in `.env`
- Verify database exists: `psql -U postgres -l`

### Hugging Face API Error

```
httpx.HTTPStatusError: 401 Unauthorized
```

**Solution:**
- Verify HUGGINGFACE_API_KEY in `.env`
- Check token at https://huggingface.co/settings/tokens
- Ensure token has "Read" permission

### Port Already in Use

```
ERROR: [Errno 98] Address already in use
```

**Solution:**
```bash
# Find process using port 8000
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

### Import Errors

```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution:**
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

---

## Next Steps (Phase 2)

Phase 1 is complete! Next phases:

**Phase 2: Core Agent System** (Weeks 2-3)
- Implement web scrapers for Amazon, Flipkart
- Add LLM-powered query understanding
- Implement embeddings-based product matching
- End-to-end product search working

**Phase 3: Business Analytics** (Week 4)
- Real-time price tracking
- Competitive analysis
- Market trend forecasting
- AI-generated business insights

**Phase 4: Production Ready** (Week 5)
- Redis caching
- Celery background jobs
- Comprehensive testing
- Docker deployment

---

## Support

For issues or questions:
- **Email**: B.R.MridulaTara / A.Koushik (MGIT)
- **Docs**: See `enhanced-ecommerce-agent-workflow.md`

---

## License

Educational project - MGIT College

---

**Built with ❤️ using FastAPI, LangGraph, and Hugging Face**
