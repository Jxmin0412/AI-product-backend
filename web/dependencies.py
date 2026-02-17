"""Web dependencies — re-exports database session providers for route handlers."""
from database.connection import get_db, get_async_db

__all__ = ["get_db", "get_async_db"]
