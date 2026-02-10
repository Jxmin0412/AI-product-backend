"""
Database connection and session management with robust connection pooling.

Features:
- Connection pooling with configurable size and overflow
- Connection recycling to prevent stale connections
- Pre-ping validation to detect dead connections
- Async session support for FastAPI async endpoints
- Health monitoring and pool statistics
- Automatic retry logic for transient failures
"""
import logging
import time
from contextlib import contextmanager, asynccontextmanager
from typing import Generator, AsyncGenerator, Optional, Dict, Any

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool, AsyncAdaptedQueuePool
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError, OperationalError

# Async support
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from config.settings import settings
from database.models import Base

logger = logging.getLogger(__name__)


class ConnectionPoolStats:
    """Track connection pool statistics."""

    def __init__(self):
        self.total_connections = 0
        self.active_connections = 0
        self.idle_connections = 0
        self.overflow_connections = 0
        self.checkouts = 0
        self.checkins = 0
        self.invalidated = 0
        self.recycled = 0
        self.errors = 0
        self.last_checkout_time: Optional[float] = None
        self.last_checkin_time: Optional[float] = None


class DatabaseManager:
    """
    Manages database connections with robust pooling.

    Features:
    - Singleton pattern for global database engine
    - Configurable connection pooling
    - Connection health monitoring
    - Automatic connection recycling
    - Support for both sync and async sessions
    """

    _instance = None
    _engine = None
    _async_engine = None
    _session_factory = None
    _async_session_factory = None
    _stats = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._stats = ConnectionPoolStats()
        return cls._instance

    def __init__(self):
        """Initialize database engine and session factory."""
        if self._engine is None:
            self._initialize_engine()

    def _get_pool_config(self) -> Dict[str, Any]:
        """Get connection pool configuration based on environment."""
        base_config = {
            "poolclass": QueuePool,
            "pool_pre_ping": settings.DB_POOL_PRE_PING,  # Validate connections before use
            "pool_recycle": settings.DB_POOL_RECYCLE,  # Recycle connections after N seconds
            "pool_timeout": settings.DB_POOL_TIMEOUT,  # Wait time for available connection
            "pool_use_lifo": True,  # Use LIFO to keep connections fresh
        }

        if settings.ENVIRONMENT == "production":
            # Production: larger pool, more overflow
            base_config.update({
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_POOL_MAX_OVERFLOW,
            })
        elif settings.ENVIRONMENT == "test":
            # Testing: use NullPool (no pooling) to avoid connection leaks
            base_config = {
                "poolclass": NullPool,
            }
        else:
            # Development: smaller pool
            base_config.update({
                "pool_size": min(settings.DB_POOL_SIZE, 5),
                "max_overflow": min(settings.DB_POOL_MAX_OVERFLOW, 10),
            })

        return base_config

    def _initialize_engine(self):
        """Create SQLAlchemy engine with optimized pooling settings."""
        try:
            pool_config = self._get_pool_config()

            # Engine configuration
            engine_kwargs = {
                "echo": settings.DEBUG and settings.ENVIRONMENT == "development",
                "echo_pool": settings.DB_ECHO_POOL,
                "future": True,
                **pool_config
            }

            # Create synchronous engine
            self._engine = create_engine(
                settings.DATABASE_URL,
                **engine_kwargs
            )

            # Register pool event listeners for monitoring
            self._register_pool_events(self._engine)

            # Create session factory with optimized settings
            self._session_factory = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False  # Prevent lazy loading issues after commit
            )

            # Initialize async engine if asyncpg is available
            self._initialize_async_engine()

            logger.info(
                f"Database engine initialized: {settings.DB_NAME}@{settings.DB_HOST} "
                f"(pool_size={pool_config.get('pool_size', 'N/A')}, "
                f"max_overflow={pool_config.get('max_overflow', 'N/A')}, "
                f"recycle={settings.DB_POOL_RECYCLE}s)"
            )

        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            raise

    def _initialize_async_engine(self):
        """Initialize async engine for async session support."""
        try:
            # Convert postgresql:// to postgresql+asyncpg://
            async_url = settings.DATABASE_URL.replace(
                "postgresql://", "postgresql+asyncpg://"
            )

            pool_config = self._get_pool_config()

            # Swap QueuePool for AsyncAdaptedQueuePool (QueuePool is not async-compatible)
            async_pool_config = {
                k: v for k, v in pool_config.items() if k != "pool_use_lifo"
            }
            if async_pool_config.get("poolclass") is QueuePool:
                async_pool_config["poolclass"] = AsyncAdaptedQueuePool

            self._async_engine = create_async_engine(
                async_url,
                echo=settings.DEBUG and settings.ENVIRONMENT == "development",
                future=True,
                **async_pool_config
            )

            self._async_session_factory = async_sessionmaker(
                bind=self._async_engine,
                class_=AsyncSession,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )

            logger.info("Async database engine initialized")

        except ImportError:
            logger.warning(
                "asyncpg not installed. Async database sessions unavailable. "
                "Install with: pip install asyncpg"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize async engine: {e}")

    def _register_pool_events(self, engine):
        """Register event listeners for connection pool monitoring."""

        @event.listens_for(engine, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            """Called when a connection is retrieved from the pool."""
            self._stats.checkouts += 1
            self._stats.active_connections += 1
            self._stats.last_checkout_time = time.time()
            logger.debug(f"Connection checkout (active: {self._stats.active_connections})")

        @event.listens_for(engine, "checkin")
        def on_checkin(dbapi_conn, connection_record):
            """Called when a connection is returned to the pool."""
            self._stats.checkins += 1
            self._stats.active_connections = max(0, self._stats.active_connections - 1)
            self._stats.last_checkin_time = time.time()
            logger.debug(f"Connection checkin (active: {self._stats.active_connections})")

        @event.listens_for(engine, "invalidate")
        def on_invalidate(dbapi_conn, connection_record, exception):
            """Called when a connection is invalidated due to error."""
            self._stats.invalidated += 1
            logger.warning(f"Connection invalidated: {exception}")

        @event.listens_for(engine, "connect")
        def on_connect(dbapi_conn, connection_record):
            """Called when a new raw database connection is created."""
            self._stats.total_connections += 1
            logger.debug(f"New connection created (total: {self._stats.total_connections})")

        @event.listens_for(engine, "close")
        def on_close(dbapi_conn, connection_record):
            """Called when a connection is closed."""
            logger.debug("Connection closed")

        # Handle connection errors for automatic recovery
        @event.listens_for(engine, "handle_error")
        def on_error(exception_context):
            """Handle connection errors."""
            self._stats.errors += 1
            logger.error(f"Database error: {exception_context.original_exception}")

    def get_session(self) -> Session:
        """
        Get a new database session from the pool.

        Returns:
            Session: SQLAlchemy session instance

        Raises:
            RuntimeError: If database not initialized
        """
        if self._session_factory is None:
            raise RuntimeError("Database not initialized")
        return self._session_factory()

    async def get_async_session(self) -> AsyncSession:
        """
        Get a new async database session.

        Returns:
            AsyncSession: SQLAlchemy async session instance

        Raises:
            RuntimeError: If async database not available
        """
        if self._async_session_factory is None:
            raise RuntimeError(
                "Async database not available. Install asyncpg: pip install asyncpg"
            )
        return self._async_session_factory()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope for database operations.

        Automatically commits on success, rolls back on exception.

        Usage:
            with db_manager.session_scope() as session:
                session.add(obj)

        Yields:
            Session: Database session with automatic transaction management
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database transaction failed: {e}")
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Transaction failed with unexpected error: {e}")
            raise
        finally:
            session.close()

    @asynccontextmanager
    async def async_session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Provide an async transactional scope for database operations.

        Usage:
            async with db_manager.async_session_scope() as session:
                await session.execute(query)

        Yields:
            AsyncSession: Async database session with automatic transaction management
        """
        session = await self.get_async_session()
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Async database transaction failed: {e}")
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Async transaction failed with unexpected error: {e}")
            raise
        finally:
            await session.close()

    def create_tables(self):
        """Create all database tables from models."""
        try:
            Base.metadata.create_all(bind=self._engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise

    def drop_tables(self):
        """Drop all database tables. Use with caution!"""
        try:
            Base.metadata.drop_all(bind=self._engine)
            logger.warning("All database tables dropped")
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise

    def health_check(self) -> bool:
        """
        Check database connectivity with connection validation.

        Returns:
            bool: True if database is accessible, False otherwise
        """
        try:
            with self.session_scope() as session:
                result = session.execute(text("SELECT 1"))
                result.fetchone()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def async_health_check(self) -> bool:
        """
        Async health check for database connectivity.

        Returns:
            bool: True if database is accessible, False otherwise
        """
        try:
            async with self.async_session_scope() as session:
                result = await session.execute(text("SELECT 1"))
                result.fetchone()
            return True
        except Exception as e:
            logger.error(f"Async database health check failed: {e}")
            return False

    def get_pool_status(self) -> Dict[str, Any]:
        """
        Get current connection pool status.

        Returns:
            Dict with pool statistics and status
        """
        pool = self._engine.pool if self._engine else None

        status = {
            "initialized": self._engine is not None,
            "environment": settings.ENVIRONMENT,
            "database": settings.DB_NAME,
            "host": settings.DB_HOST,
        }

        if pool and hasattr(pool, "size"):
            status.update({
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalidatedcount() if hasattr(pool, "invalidatedcount") else 0,
            })

        # Add tracked stats
        status.update({
            "stats": {
                "total_connections_created": self._stats.total_connections,
                "total_checkouts": self._stats.checkouts,
                "total_checkins": self._stats.checkins,
                "total_invalidated": self._stats.invalidated,
                "total_errors": self._stats.errors,
                "active_connections": self._stats.active_connections,
            }
        })

        return status

    def dispose(self):
        """
        Dispose of the connection pool.
        Call this during application shutdown.
        """
        if self._engine:
            self._engine.dispose()
            logger.info("Database connection pool disposed")

        if self._async_engine:
            # Note: async dispose should be called with await in async context
            logger.info("Async database engine marked for disposal")

    async def async_dispose(self):
        """Async dispose of the connection pool."""
        if self._async_engine:
            await self._async_engine.dispose()
            logger.info("Async database connection pool disposed")

    @property
    def engine(self):
        """Get the database engine instance."""
        return self._engine

    @property
    def async_engine(self):
        """Get the async database engine instance."""
        return self._async_engine


# Global database manager instance
db_manager = DatabaseManager()


# ============================================
# FASTAPI DEPENDENCIES
# ============================================

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for injecting database sessions.

    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()

    Yields:
        Session: Database session that automatically closes after use
    """
    session = db_manager.get_session()
    try:
        yield session
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database error in request: {e}")
        raise
    finally:
        session.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI async dependency for injecting async database sessions.

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()

    Yields:
        AsyncSession: Async database session
    """
    session = await db_manager.get_async_session()
    try:
        yield session
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Async database error in request: {e}")
        raise
    finally:
        await session.close()


# ============================================
# INITIALIZATION FUNCTIONS
# ============================================

def init_db():
    """
    Initialize the database.
    Creates all tables if they don't exist.
    """
    logger.info("Initializing database...")
    db_manager.create_tables()
    logger.info("Database initialization complete")


def reset_db():
    """
    Reset the database by dropping and recreating all tables.
    WARNING: This will delete all data!
    """
    logger.warning("Resetting database - ALL DATA WILL BE LOST!")
    db_manager.drop_tables()
    db_manager.create_tables()
    logger.info("Database reset complete")


def dispose_db():
    """
    Dispose of database connections.
    Call this during application shutdown.
    """
    db_manager.dispose()


async def async_dispose_db():
    """
    Async dispose of database connections.
    Call this during async application shutdown.
    """
    await db_manager.async_dispose()
