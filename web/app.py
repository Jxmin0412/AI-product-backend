"""
FastAPI application factory — creates and configures the app.
Handles CORS, exception handlers, lifespan events, and router registration.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from config.settings import settings
from database.connection import init_db, db_manager, dispose_db, async_dispose_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager — handles startup and shutdown."""
    # Startup
    logger.info("Starting AI Product Curator API...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

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

# CORS — allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


# ============================================
# EXCEPTION HANDLERS
# ============================================

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


# ============================================
# ROOT & HEALTH ENDPOINTS
# ============================================

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
            "auth": "/api/auth/*",
            "health": "/health",
            "docs": "/docs"
        }
    }


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


# ============================================
# REGISTER ROUTERS
# ============================================

from web.routes import auth as auth_routes
from web.routes import consumer as consumer_routes
from web.routes import business as business_routes

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
    auth_routes.router,
    prefix="/api/auth",
    tags=["Authentication"]
)
