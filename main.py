"""
Main FastAPI application for AI Product Curator.
Dual-purpose e-commerce intelligence platform serving both consumers and businesses.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from config.settings import settings
from database.connection import init_db, db_manager
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


# Create FastAPI app
app = FastAPI(
    title="AI Product Curator API",
    description="Dual-purpose e-commerce intelligence platform with consumer product search and business analytics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


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

    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "environment": settings.ENVIRONMENT
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
        log_level=settings.LOG_LEVEL.lower()
    )
