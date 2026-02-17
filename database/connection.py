"""
Database connection and session management with connection pooling.
"""
import logging
from contextlib import contextmanager, asynccontextmanager
from typing import Generator, AsyncGenerator, Dict, Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from config.settings import settings
from database.models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database engine, session factories, and connection pooling."""

    _instance = None
    _engine = None
    _async_engine = None
    _session_factory = None
    _async_session_factory = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._engine is None:
            self._initialize_engine()

    def _initialize_engine(self):
        pool_config = self._get_pool_config()

        self._engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG and settings.ENVIRONMENT == "development",
            future=True,
            **pool_config,
        )

        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

        self._init_async_engine(pool_config)

        logger.info(
            f"Database engine initialized: {settings.DB_NAME}@{settings.DB_HOST} "
            f"(pool_size={pool_config.get('pool_size', 'N/A')})"
        )

    def _get_pool_config(self) -> Dict[str, Any]:
        if settings.ENVIRONMENT == "test":
            return {"poolclass": NullPool}

        return {
            "poolclass": QueuePool,
            "pool_pre_ping": True,
            "pool_recycle": settings.DB_POOL_RECYCLE,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_use_lifo": True,
            "pool_size": min(settings.DB_POOL_SIZE, 5) if settings.ENVIRONMENT != "production" else settings.DB_POOL_SIZE,
            "max_overflow": min(settings.DB_POOL_MAX_OVERFLOW, 10) if settings.ENVIRONMENT != "production" else settings.DB_POOL_MAX_OVERFLOW,
        }

    def _init_async_engine(self, pool_config):
        try:
            async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
            async_pool = {k: v for k, v in pool_config.items() if k != "pool_use_lifo"}

            self._async_engine = create_async_engine(
                async_url,
                echo=settings.DEBUG and settings.ENVIRONMENT == "development",
                future=True,
                **async_pool,
            )
            self._async_session_factory = async_sessionmaker(
                bind=self._async_engine, class_=AsyncSession,
                autocommit=False, autoflush=False, expire_on_commit=False,
            )
            logger.info("Async database engine initialized")
        except ImportError:
            logger.warning("asyncpg not installed. Async database sessions unavailable. Install with: pip install asyncpg")
        except Exception as e:
            logger.warning(f"Failed to initialize async engine: {e}")

    def get_session(self) -> Session:
        if self._session_factory is None:
            raise RuntimeError("Database not initialized")
        return self._session_factory()

    async def get_async_session(self) -> AsyncSession:
        if self._async_session_factory is None:
            raise RuntimeError("Async database not available. Install asyncpg.")
        return self._async_session_factory()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Transactional scope: auto-commits on success, rolls back on error."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database transaction failed: {e}")
            raise
        finally:
            session.close()

    @asynccontextmanager
    async def async_session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        """Async transactional scope."""
        session = await self.get_async_session()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Async transaction failed: {e}")
            raise
        finally:
            await session.close()

    def create_tables(self):
        Base.metadata.create_all(bind=self._engine)
        logger.info("Database tables created")

    def health_check(self) -> bool:
        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1")).fetchone()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    def get_pool_status(self) -> Dict[str, Any]:
        pool = self._engine.pool if self._engine else None
        status = {"initialized": self._engine is not None, "environment": settings.ENVIRONMENT}
        if pool and hasattr(pool, "size"):
            status.update({
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            })
        return status

    def dispose(self):
        if self._engine:
            self._engine.dispose()
            logger.info("Database connection pool disposed")

    async def async_dispose(self):
        if self._async_engine:
            await self._async_engine.dispose()
            logger.info("Async database connection pool disposed")

    @property
    def engine(self):
        return self._engine


# Global instance
db_manager = DatabaseManager()


# ============================================
# FASTAPI DEPENDENCIES
# ============================================

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
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
    """FastAPI dependency for async database sessions."""
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
# INITIALIZATION
# ============================================

def init_db():
    """Initialize database — creates tables if they don't exist."""
    db_manager.create_tables()


def dispose_db():
    db_manager.dispose()


async def async_dispose_db():
    await db_manager.async_dispose()
