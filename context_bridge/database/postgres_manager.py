"""
PostgreSQL connection management using PSQLPy.

Provides connection pool management for the context_bridge package.
"""

import asyncio
import logging
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

from psqlpy import ConnectionPool, Connection

from context_bridge.config import Config


logger = logging.getLogger(__name__)


class PostgreSQLManager:
    """
    PostgreSQL connection manager for context_bridge.

    Manages connection pool lifecycle and provides connections
    for repository operations.
    """

    def __init__(self, config: Config):
        """
        Initialize PostgreSQL manager.

        Args:
            config: Configuration object with database settings
        """
        self.config = config
        self._pool: Optional[ConnectionPool] = None
        self._initialized = False

        # Build DSN from config
        self.dsn = (
            f"postgresql://{config.postgres_user}:{config.postgres_password}"
            f"@{config.postgres_host}:{config.postgres_port}/{config.postgres_db}"
        )

        logger.info(
            f"PostgreSQL manager configured for {config.postgres_host}:{config.postgres_port}/{config.postgres_db}"
        )

    async def initialize(self) -> None:
        """Initialize the connection pool with retry logic."""
        if self._initialized:
            logger.warning("PostgreSQL manager already initialized")
            return

        max_retries = 5
        base_delay = 1.0  # seconds

        for attempt in range(max_retries):
            try:
                if self._pool is None:
                    self._pool = ConnectionPool(
                        dsn=self.dsn,
                        max_db_pool_size=self.config.postgres_max_pool_size,
                    )
                    self._initialized = True
                    logger.info(
                        f"PostgreSQL connection pool initialized (max_size={self.config.postgres_max_pool_size})"
                    )
                    return
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Failed to initialize PostgreSQL connection pool after {max_retries} attempts: {e}"
                    )
                    raise

                delay = base_delay * (2**attempt)  # Exponential backoff
                logger.warning(
                    f"Failed to initialize PostgreSQL connection pool (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)

    async def health_check(self) -> bool:
        """Verify database connectivity and return health status."""
        if not self._initialized or not self._pool:
            logger.warning("PostgreSQL manager not initialized")
            return False

        try:
            async with self.connection() as conn:
                result = await conn.execute("SELECT 1 as health")
                rows = result.result()
                # PSQLPy returns results as list of dicts with column names as keys
                if rows and len(rows) > 0 and rows[0].get("health") == 1:
                    logger.debug("PostgreSQL health check passed")
                    return True
                else:
                    logger.error(f"PostgreSQL health check failed: unexpected result {rows}")
                    return False
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return False

    def log_pool_stats(self) -> None:
        """Log current connection pool statistics."""
        if not self._initialized or not self._pool:
            logger.warning("PostgreSQL manager not initialized - cannot log pool stats")
            return

        # Note: PSQLPy doesn't expose detailed pool statistics directly
        # We can log basic info about the pool state
        pool_status = "initialized" if self._initialized else "not initialized"
        logger.info(
            f"PostgreSQL connection pool status: {pool_status}, max_size={self.config.postgres_max_pool_size}"
        )

    async def close(self) -> None:
        """Close the connection pool and clean up resources gracefully."""
        if not self._pool:
            logger.debug("PostgreSQL connection pool already closed")
            return

        try:
            # Log final stats before closing
            self.log_pool_stats()

            # Close the pool with timeout handling
            # Note: PSQLPy's close() is synchronous, but we'll wrap it for future async support
            self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info("PostgreSQL connection pool closed gracefully")

        except Exception as e:
            logger.error(f"Error during PostgreSQL connection pool shutdown: {e}")
            # Ensure state is cleaned up even on error
            self._pool = None
            self._initialized = False
            raise

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[Connection, None]:
        """
        Get a connection from the pool (context manager).

        Usage:
            async with manager.connection() as conn:
                result = await conn.execute("SELECT * FROM table")

        Yields:
            Connection from the pool
        """
        if not self._initialized or not self._pool:
            raise RuntimeError("PostgreSQL manager not initialized. Call initialize() first.")

        conn: Connection = await self._pool.connection()
        try:
            yield conn
        finally:
            # Connection is automatically returned to pool when context exits
            pass

    async def execute(self, query: str, parameters: Optional[list] = None):
        """
        Execute a query using a connection from the pool.

        Args:
            query: SQL query to execute
            parameters: Query parameters (optional)

        Returns:
            Query result
        """
        async with self.connection() as conn:
            return await conn.execute(query, parameters or [])

    async def execute_transaction(self, operations: list) -> None:
        """
        Execute multiple operations in a transaction with rollback support.

        Args:
            operations: List of tuples (query, parameters) to execute

        Raises:
            Exception: If any operation fails, transaction is rolled back
        """
        if not self._initialized or not self._pool:
            raise RuntimeError("PostgreSQL manager not initialized. Call initialize() first.")

        async with self.connection() as conn:
            try:
                # Start transaction
                await conn.execute("BEGIN")

                for query, parameters in operations:
                    await conn.execute(query, parameters or [])

                # Commit transaction
                await conn.execute("COMMIT")
                logger.debug(
                    f"Transaction completed successfully with {len(operations)} operations"
                )

            except Exception as e:
                # Rollback on error
                try:
                    await conn.execute("ROLLBACK")
                    logger.warning("Transaction rolled back due to error")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback transaction: {rollback_error}")

                logger.error(f"Transaction failed: {e}")
                raise

    # Context manager support
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
