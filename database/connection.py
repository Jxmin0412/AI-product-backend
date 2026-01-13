"""
Database connection and session management.
Handles PostgreSQL connections and provides database session factories.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool
from contextlib import contextmanager
from typing import Generator
import logging

from config.settings import settings
from database.models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections and sessions.
    Implements singleton pattern for global database engine.
    """

    _instance = None
    _engine = None
    _session_factory = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize database engine and session factory."""
        if self._engine is None:
            self._initialize_engine()

    def _initialize_engine(self):
        """Create SQLAlchemy engine with optimized settings."""
        try:
            # Engine configuration
            engine_kwargs = {
                "echo": settings.ENVIRONMENT == "development",  # SQL logging in dev
                "future": True,  # SQLAlchemy 2.0 style
                "pool_pre_ping": True,  # Verify connections before using
            }

            # Connection pooling
            if settings.ENVIRONMENT == "production":
                engine_kwargs["poolclass"] = QueuePool
                engine_kwargs["pool_size"] = 20
                engine_kwargs["max_overflow"] = 10
                engine_kwargs["pool_timeout"] = 30
            else:
                # Use smaller pool for development
                engine_kwargs["poolclass"] = QueuePool
                engine_kwargs["pool_size"] = 5
                engine_kwargs["max_overflow"] = 5

            self._engine = create_engine(
                settings.DATABASE_URL,
                **engine_kwargs
            )

            # Create session factory
            self._session_factory = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )

            logger.info(f"Database engine initialized: {settings.DB_NAME}@{settings.DB_HOST}")

        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            raise

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

    def get_session(self) -> Session:
        """
        Get a new database session.

        Returns:
            Session: SQLAlchemy session instance
        """
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._session_factory()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope for database operations.

        Usage:
            with db_manager.session_scope() as session:
                session.add(obj)
                # Automatically commits on success, rolls back on exception

        Yields:
            Session: Database session with automatic transaction management
        """
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

    def health_check(self) -> bool:
        """
        Check database connectivity.

        Returns:
            bool: True if database is accessible, False otherwise
        """
        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    @property
    def engine(self):
        """Get the database engine instance."""
        return self._engine


# Global database manager instance
db_manager = DatabaseManager()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function for FastAPI to inject database sessions.

    Usage in FastAPI:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()

    Yields:
        Session: Database session that automatically closes after use
    """
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


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


# Note: Event listeners removed - they cannot be registered at module level
# before the engine is created. To add logging, register inside _initialize_engine().
