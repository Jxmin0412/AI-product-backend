"""
Main FastAPI application for AI Product Curator.
Dual-purpose e-commerce intelligence platform serving both consumers and businesses.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config.settings import settings
from database.connection import init_db, db_manager, dispose_db, async_dispose_db
from api import consumer_routes, business_routes
from api.auth import router as auth_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting AI Product Curator API...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    # Try to initialize database (optional - app works without it for scraping)
    try:
        init_db()
        logger.info("Database initialized successfully")

        if db_manager.health_check():
            logger.info("Database health check passed")
        else:
            logger.warning("Database health check failed - continuing without DB")

    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
        logger.info("Continuing without database - real-time scraping will still work")

    yield

    # Shutdown
    logger.info("Shutting down AI Product Curator API...")

    # Dispose database connections properly
    try:
        await async_dispose_db()
        dispose_db()
        logger.info("Database connections disposed successfully")
    except Exception as e:
        logger.warning(f"Error disposing database connections: {e}")


# Create FastAPI app
app = FastAPI(
    title="AI Product Curator API",
    description="Dual-purpose e-commerce intelligence platform with consumer product search and business analytics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API rate limiting (per IP)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Exception Handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with consistent JSON response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "message": "Validation error",
            "details": exc.errors(),
            "status_code": 422
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal server error",
            "status_code": 500
        }
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "AI Product Curator API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "consumer": "/api/consumer/*",
            "business": "/api/business/*",
            "health": "/health",
            "docs": "/docs"
        }
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    db_healthy = db_manager.health_check()
    pool_status = db_manager.get_pool_status()

    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "environment": settings.ENVIRONMENT,
        "pool": pool_status
    }


# Database pool status endpoint
@app.get("/health/db")
async def database_health():
    """Detailed database and connection pool health."""
    db_healthy = db_manager.health_check()
    pool_status = db_manager.get_pool_status()

    return {
        "healthy": db_healthy,
        "database": {
            "name": settings.DB_NAME,
            "host": settings.DB_HOST,
            "port": settings.DB_PORT,
        },
        "pool": pool_status,
        "config": {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_POOL_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_recycle": settings.DB_POOL_RECYCLE,
            "pre_ping": settings.DB_POOL_PRE_PING,
        }
    }


# Include routers
app.include_router(
    consumer_routes.router,
    prefix="/api/consumer",
    tags=["Consumer"]
)

app.include_router(
    business_routes.router,
    prefix="/api/business",
    tags=["Business Intelligence"]
)

app.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["Authentication"]
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
        reload_excludes=[".venv"],
        log_level=settings.LOG_LEVEL.lower()
    )
