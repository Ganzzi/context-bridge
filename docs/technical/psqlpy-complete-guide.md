# PSQLPy Complete Usage Guide

## Overview

This is a comprehensive guide for using **PSQLPy** - a high-performance PostgreSQL driver for Python with async support. PSQLPy is NOT the same as psycopg2 or asyncpg. This guide covers everything from basic setup to advanced usage patterns including vector embeddings and BM25 full-text search.

**Key Features of PSQLPy:**
- Fully async/await support (asyncio)
- High-performance connection pooling
- Native support for PostgreSQL extensions (pgvector, vchord_bm25)
- Type-safe parameter binding with `$1, $2` placeholders
- Special types like `PgVector` for vector operations
- No ORM overhead - direct SQL execution

## Table of Contents

1. [Installation and Setup](#1-installation-and-setup)
2. [Configuration Management](#2-configuration-management)
3. [Connection Pool Architecture](#3-connection-pool-architecture)
4. [Database Initialization](#4-database-initialization)
5. [Connection Management](#5-connection-management)
6. [Query Execution Patterns](#6-query-execution-patterns)
7. [Result Handling](#7-result-handling)
8. [Exception Handling](#8-exception-handling)
9. [Vector Operations (pgvector)](#9-vector-operations-pgvector)
10. [BM25 Full-Text Search](#10-bm25-full-text-search)
11. [Hybrid Search](#11-hybrid-search)
12. [Best Practices](#12-best-practices)
13. [Common Pitfalls](#13-common-pitfalls)

---

## 1. Installation and Setup

### Installing PSQLPy

```bash
pip install psqlpy
```

Or with Poetry:

```bash
poetry add psqlpy
```

### Required PostgreSQL Extensions

PSQLPy works with standard PostgreSQL, but for advanced features, you'll need these extensions:

```sql
-- Vector similarity search
CREATE EXTENSION IF NOT EXISTS vector CASCADE;

-- Hierarchical vector search (optional)
CREATE EXTENSION IF NOT EXISTS vchord CASCADE;

-- Text tokenization for BM25
CREATE EXTENSION IF NOT EXISTS pg_tokenizer CASCADE;

-- BM25 full-text search
CREATE EXTENSION IF NOT EXISTS vchord_bm25 CASCADE;
```

**Important:** Extensions must be created BEFORE you run your application code.

---

## 2. Configuration Management

### Using Pydantic for Type-Safe Configuration

PSQLPy works best with a centralized configuration approach. Here's a production-ready config setup:

```python
# config/settings.py
import os
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class Config(BaseModel):
    """Database configuration."""
    
    # PostgreSQL settings
    postgres_host: str = Field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    postgres_port: int = Field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    postgres_user: str = Field(default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"))
    postgres_password: str = Field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", ""))
    postgres_db: str = Field(default_factory=lambda: os.getenv("POSTGRES_DB", "context_bridge"))
    
    # Connection pool settings
    max_pool_size: int = Field(default=10, description="Maximum connections in pool")
    
    # Vector settings
    vector_dimension: int = Field(default=768, description="Embedding dimension")

# Global config instance
_config: Optional[Config] = None

def get_config() -> Config:
    """Get the global configuration singleton."""
    global _config
    if _config is None:
        _config = Config()
    return _config
```

### Environment Variables (.env file)

```bash
# .env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=context_bridge
```

**Security Note:** Never commit `.env` files to version control. Add to `.gitignore`.

---

## 3. Connection Pool Architecture

### Understanding PSQLPy Connection Pools

PSQLPy uses connection pooling for optimal performance. A pool maintains a set of reusable database connections:

- **Advantage:** No overhead of creating new connections for each query
- **Thread-safe:** Pool manages concurrent access automatically
- **Resource efficient:** Limits total connections to database

### Building the PostgreSQL Manager Class

Create a manager class that wraps the connection pool and provides a clean API:

```python
# database/postgres_manager.py
import logging
from typing import Optional
from contextlib import asynccontextmanager

from psqlpy import ConnectionPool, Connection
from context_bridge.config import Config

logger = logging.getLogger(__name__)


class PostgreSQLManager:
    """
    PostgreSQL connection manager using PSQLPy.
    
    Manages connection pool lifecycle and provides connections
    for repository operations.
    """

    def __init__(self, config: Config):
        """
        Initialize the manager (does NOT create pool yet).
        
        Args:
            config: Configuration object with database settings
        """
        self.config = config
        self._pool: Optional[ConnectionPool] = None
        self._initialized = False

        # Build PostgreSQL DSN (Data Source Name)
        self.dsn = (
            f"postgresql://{config.postgres_user}:{config.postgres_password}"
            f"@{config.postgres_host}:{config.postgres_port}/{config.postgres_db}"
        )

        logger.info(
            f"PostgreSQL manager configured for "
            f"{config.postgres_host}:{config.postgres_port}/{config.postgres_db}"
        )

    async def initialize(self) -> None:
        """
        Initialize the connection pool.
        
        Call this once during application startup.
        """
        if self._initialized:
            logger.warning("PostgreSQL manager already initialized")
            return

        if self._pool is None:
            # Create the connection pool
            self._pool = ConnectionPool(
                dsn=self.dsn,
                max_db_pool_size=10,
            )
            self._initialized = True
            logger.info(f"PostgreSQL pool initialized (max_size=10)")

    async def close(self) -> None:
        """
        Close the connection pool and clean up resources.
        
        Call this during application shutdown.
        """
        if self._pool:
            self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info("PostgreSQL connection pool closed")

    @asynccontextmanager
    async def connection(self):
        """
        Get a connection from the pool using context manager (RECOMMENDED).
        
        The connection is automatically returned to the pool when exiting the context.
        
        Usage:
            async with manager.connection() as conn:
                result = await conn.execute("SELECT * FROM users WHERE id = $1", [user_id])
        
        Yields:
            Connection: A database connection from the pool
            
        Raises:
            RuntimeError: If pool is not initialized
        """
        if not self._initialized or not self._pool:
            raise RuntimeError(
                "PostgreSQL manager not initialized. Call initialize() first."
            )

        # Get connection from pool
        conn: Connection = await self._pool.connection()
        try:
            yield conn
        finally:
            # Connection is automatically returned to pool
            # No explicit cleanup needed with PSQLPy
            pass

    async def get_connection(self) -> Connection:
        """
        Get a connection from the pool (manual management).
        
        WARNING: With manual management, you're responsible for connection lifecycle.
        Prefer using connection() context manager instead.
        
        Returns:
            Connection from the pool
        """
        if not self._initialized or not self._pool:
            raise RuntimeError(
                "PostgreSQL manager not initialized. Call initialize() first."
            )

        return await self._pool.connection()

    async def execute(self, query: str, parameters: Optional[list] = None):
        """
        Execute a query using a connection from the pool.
        
        Convenience method for simple queries.
        
        Args:
            query: SQL query with $1, $2, ... placeholders
            parameters: Query parameters as list
        
        Returns:
            Query result
        
        Example:
            result = await manager.execute(
                "SELECT * FROM users WHERE email = $1",
                ["user@example.com"]
            )
        """
        async with self.connection() as conn:
            return await conn.execute(query, parameters or [])

    async def execute_many(self, query: str, parameters_list: list[list]):
        """
        Execute a query multiple times with different parameters.
        
        Useful for batch inserts.
        
        Args:
            query: SQL query
            parameters_list: List of parameter lists
        
        Returns:
            List of query results
        
        Example:
            results = await manager.execute_many(
                "INSERT INTO users (name, email) VALUES ($1, $2)",
                [
                    ["Alice", "alice@example.com"],
                    ["Bob", "bob@example.com"],
                    ["Charlie", "charlie@example.com"]
                ]
            )
        """
        async with self.connection() as conn:
            results = []
            for parameters in parameters_list:
                result = await conn.execute(query, parameters)
                results.append(result)
            return results

    async def verify_connection(self) -> bool:
        """
        Verify database connection is working.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            async with self.connection() as conn:
                await conn.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Connection verification failed: {e}")
            return False

    async def ensure_extensions(self) -> None:
        """
        Ensure required PostgreSQL extensions are installed.
        
        Required extensions:
        - vector: For vector similarity search
        - pg_tokenizer: For text tokenization
        - vchord_bm25: For BM25 full-text search
        """
        extensions = ["vector", "pg_tokenizer", "vchord_bm25"]

        for extension in extensions:
            try:
                query = f"CREATE EXTENSION IF NOT EXISTS {extension} CASCADE"
                await self.execute(query)
                logger.info(f"Ensured extension exists: {extension}")
            except Exception as e:
                logger.warning(
                    f"Could not create extension {extension}: {e}. "
                    f"You may need superuser privileges."
                )

    # Context manager support for manager itself
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
```

### Key Design Decisions

1. **Lazy Initialization:** Pool is created in `initialize()`, not `__init__`. This gives you control over when connections are established.

2. **Connection Context Manager:** The `@asynccontextmanager` decorator ensures connections are always returned to the pool, even if an exception occurs.

3. **Global Manager Pattern:** Typically, you create one manager instance per application and reuse it.

---

## 4. Database Initialization

### Creating Schema and Extensions

PSQLPy doesn't handle schema migrations - you need to initialize your database schema separately. Here's a complete initialization script:

```python
# database/init_databases.py
import asyncio
from pathlib import Path
from psqlpy import ConnectionPool
from context_bridge.config import get_config


async def init_postgresql():
    """Initialize PostgreSQL schema and extensions."""
    config = get_config()

    # Build DSN
    dsn = (
        f"postgresql://{config.postgres_user}:{config.postgres_password}"
        f"@{config.postgres_host}:{config.postgres_port}/{config.postgres_db}"
    )

    print(f"🔗 Connecting to PostgreSQL: {config.postgres_db}")
    
    # Create a temporary pool for initialization
    pool = ConnectionPool(dsn=dsn, max_db_pool_size=2)

    try:
        conn = await pool.connection()

        print("\n🔧 Ensuring extensions...")
        
        # Install required extensions
        extensions = [
            ("vector", "Vector similarity search"),
            ("vchord", "Hierarchical vector search"),
            ("pg_tokenizer", "Text tokenization"),
            ("vchord_bm25", "BM25 full-text search"),
        ]
        
        for ext_name, desc in extensions:
            try:
                await conn.execute(
                    f"CREATE EXTENSION IF NOT EXISTS {ext_name} CASCADE"
                )
                print(f"   ✅ {ext_name}: {desc}")
            except Exception as e:
                print(f"   ⚠️  {ext_name}: {e}")
                print(f"       Note: You may need superuser privileges")

        print("\n📄 Loading schema.sql...")
        
        # Read schema file
        schema_path = Path(__file__).parent.parent / "sql" / "schema.sql"
        
        if not schema_path.exists():
            print(f"   ❌ Schema file not found: {schema_path}")
            return

        schema_sql = schema_path.read_text(encoding="utf-8")

        # Split into individual statements
        # PSQLPy doesn't support multiple statements in one execute() call
        statements = split_sql_statements(schema_sql)

        # Execute each statement
        for i, statement in enumerate(statements, 1):
            statement = statement.strip()
            if not statement:
                continue

            try:
                await conn.execute(statement)
                
                # Log what was created
                if "CREATE TABLE" in statement:
                    table_name = (
                        statement.split("CREATE TABLE")[1]
                        .split("(")[0]
                        .strip()
                        .split()[0]
                    )
                    print(f"   ✅ Table: {table_name}")
                elif "CREATE INDEX" in statement:
                    idx_name = (
                        statement.split("CREATE INDEX")[1]
                        .split("ON")[0]
                        .strip()
                        .split()[0]
                    )
                    print(f"   ✅ Index: {idx_name}")
                elif "CREATE FUNCTION" in statement:
                    func_name = statement.split("FUNCTION")[1].split("(")[0].strip()
                    print(f"   ✅ Function: {func_name}")
                elif "CREATE TRIGGER" in statement:
                    trigger_name = (
                        statement.split("CREATE TRIGGER")[1]
                        .split("BEFORE")[0]
                        .strip()
                    )
                    print(f"   ✅ Trigger: {trigger_name}")
                    
            except Exception as e:
                print(f"   ❌ Error in statement {i}: {e}")
                print(f"      Statement: {statement[:100]}...")

        print("\n✅ PostgreSQL schema initialization complete!")

    finally:
        pool.close()


def split_sql_statements(sql: str) -> list[str]:
    """
    Split SQL file into individual statements.
    
    Handles:
    - Comments (-- and /* */)
    - Semicolon delimiters
    - Dollar-quoted strings ($$)
    """
    statements = []
    current = []
    in_dollar = False

    for line in sql.split("\n"):
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("--"):
            continue

        # Track dollar-quoted strings
        dollar_count = line.count("$$")
        for _ in range(dollar_count):
            in_dollar = not in_dollar

        current.append(line)

        # Split on semicolon only if not inside dollar quotes
        if ";" in line and not in_dollar:
            statements.append("\n".join(current))
            current = []

    if current:
        statements.append("\n".join(current))

    return statements


async def main():
    """Run database initialization."""
    print("=" * 70)
    print("🚀 Initializing AgentMem Database")
    print("=" * 70)
    
    try:
        await init_postgresql()
        print("\n" + "=" * 70)
        print("✅ Database initialization successful!")
        print("=" * 70)
    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
```

### Running Initialization

```bash
python -m context_bridge.database.init_databases
```

**Important:** Run this ONCE during initial setup or when schema changes.

---

## 5. Connection Management

### Pattern 1: Context Manager (Recommended)

Always use the context manager pattern to ensure connections are returned to the pool:

```python
async def get_user_by_id(manager: PostgreSQLManager, user_id: int):
    """Fetch a user using context manager."""
    async with manager.connection() as conn:
        result = await conn.execute(
            "SELECT id, name, email FROM users WHERE id = $1",
            [user_id]
        )
        rows = result.result()
        
        if not rows:
            return None
        
        return rows[0]  # Returns tuple: (id, name, email)
```

**Why Context Manager?**
- Automatically returns connection to pool
- Works even if an exception occurs
- Clean, readable code

### Pattern 2: Multiple Queries in One Connection

For related queries, reuse the same connection:

```python
async def get_user_with_posts(manager: PostgreSQLManager, user_id: int):
    """Fetch user and their posts using one connection."""
    async with manager.connection() as conn:
        # First query: get user
        user_result = await conn.execute(
            "SELECT id, name, email FROM users WHERE id = $1",
            [user_id]
        )
        user_rows = user_result.result()
        
        if not user_rows:
            return None
        
        user = user_rows[0]
        
        # Second query: get posts (same connection)
        posts_result = await conn.execute(
            "SELECT id, title, content FROM posts WHERE user_id = $1",
            [user_id]
        )
        posts = posts_result.result()
        
        return {
            "user": user,
            "posts": posts
        }
```

### Pattern 3: Transaction Support

PSQLPy supports transactions for atomic operations:

```python
async def transfer_funds(
    manager: PostgreSQLManager, 
    from_account: int, 
    to_account: int, 
    amount: float
):
    """Transfer money between accounts atomically."""
    async with manager.connection() as conn:
        try:
            # Start transaction
            await conn.execute("BEGIN")
            
            # Debit from source
            await conn.execute(
                "UPDATE accounts SET balance = balance - $1 WHERE id = $2",
                [amount, from_account]
            )
            
            # Credit to destination
            await conn.execute(
                "UPDATE accounts SET balance = balance + $1 WHERE id = $2",
                [amount, to_account]
            )
            
            # Commit transaction
            await conn.execute("COMMIT")
            
            return True
            
        except Exception as e:
            # Rollback on error
            await conn.execute("ROLLBACK")
            logger.error(f"Transfer failed: {e}")
            raise
```

---

## 6. Query Execution Patterns

### Basic Query Execution

PSQLPy uses PostgreSQL's native parameter binding with `$1, $2, $3...` placeholders:

```python
# CORRECT: Use $1, $2, $3 placeholders
async with manager.connection() as conn:
    result = await conn.execute(
        "SELECT * FROM users WHERE email = $1 AND age > $2",
        ["user@example.com", 18]
    )

# WRONG: Don't use %s or ? placeholders (those are for other libraries)
# result = await conn.execute("SELECT * FROM users WHERE email = %s", ["user@example.com"])
```

### INSERT with RETURNING

Get the ID of newly created records:

```python
async def create_user(manager: PostgreSQLManager, name: str, email: str) -> int:
    """Create a user and return the ID."""
    query = """
        INSERT INTO users (name, email, created_at)
        VALUES ($1, $2, CURRENT_TIMESTAMP)
        RETURNING id
    """
    
    async with manager.connection() as conn:
        result = await conn.execute(query, [name, email])
        rows = result.result()
        
        if rows:
            user_id = rows[0][0]  # First column of first row
            return user_id
        
        raise ValueError("INSERT did not return an ID")
```

### UPDATE Operations

```python
async def update_user_email(
    manager: PostgreSQLManager, 
    user_id: int, 
    new_email: str
) -> bool:
    """Update user email and return success status."""
    query = """
        UPDATE users 
        SET email = $1, updated_at = CURRENT_TIMESTAMP
        WHERE id = $2
    """
    
    async with manager.connection() as conn:
        result = await conn.execute(query, [new_email, user_id])
        # Check if any rows were affected
        return True  # Update successful
```

### DELETE Operations

### DELETE Operations

```python
async def delete_user(manager: PostgreSQLManager, user_id: int) -> bool:
    """
    Delete a user.
    """
    async with manager.connection() as conn:
        result = await conn.execute(query, [user_id])
        # Parse the result to check if any rows were affected
        if result and hasattr(result, "result"):
            result_str = str(result.result())
            if "DELETE 0" in result_str or result.result() == 0:
                raise ValueError(f"User with ID {user_id} not found")
        else:
            # Alternative approach - check if user exists first
            user = await get_user_by_id(manager, user_id)
            if not user:
                raise ValueError(f"User with ID {user_id} not found")
    return True
```

### Batch Operations

```python
async def create_multiple_users(
    manager: PostgreSQLManager, 
    users: list[dict]
) -> list[int]:
    """Create multiple users in a transaction."""
    query = """
        INSERT INTO users (name, email)
        VALUES ($1, $2)
        RETURNING id
    """
    
    user_ids = []
    
    async with manager.connection() as conn:
        await conn.execute("BEGIN")
        
        try:
            for user in users:
                result = await conn.execute(query, [user["name"], user["email"]])
                user_id = result.result()[0][0]
                user_ids.append(user_id)
            
            await conn.execute("COMMIT")
            return user_ids
            
        except Exception as e:
            await conn.execute("ROLLBACK")
            logger.error(f"Batch insert failed: {e}")
            raise
```

---

## 7. Result Handling

### Understanding PSQLPy Results

PSQLPy returns results as a special result object. Call `.result()` to get the rows:

```python
async with manager.connection() as conn:
    result = await conn.execute("SELECT id, name FROM users")
    
    # Get all rows
    rows = result.result()  # Returns list of tuples
    
    # Each row is a tuple
    for row in rows:
        user_id = row[0]
        name = row[1]
        print(f"User {user_id}: {name}")
```

### Different Result Types

```python
# 1. Single row result
result = await conn.execute("SELECT * FROM users WHERE id = $1", [1])
rows = result.result()

if rows:
    user = rows[0]  # First (and only) row
    print(f"Found user: {user}")
else:
    print("User not found")

# 2. Multiple rows
result = await conn.execute("SELECT * FROM users LIMIT 10")
rows = result.result()

for row in rows:
    print(row)

# 3. No rows (INSERT, UPDATE, DELETE without RETURNING)
result = await conn.execute("DELETE FROM users WHERE id = $1", [1])
# result.result() will be []

# 4. Single value
result = await conn.execute("SELECT COUNT(*) FROM users")
count = result.result()[0][0]  # First column of first row
print(f"Total users: {count}")
```

### Converting Rows to Models

Create a helper method to convert database rows to Pydantic models:

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class User(BaseModel):
    """User model."""
    id: int
    name: str
    email: str
    created_at: datetime


def row_to_user(row: tuple) -> User:
    """Convert database row to User model."""
    return User(
        id=row[0],
        name=row[1],
        email=row[2],
        created_at=row[3]
    )


async def get_all_users(manager: PostgreSQLManager) -> list[User]:
    """Get all users as model objects."""
    query = "SELECT id, name, email, created_at FROM users"
    
    async with manager.connection() as conn:
        result = await conn.execute(query)
        rows = result.result()
        
        users = [row_to_user(row) for row in rows]
        return users
```

### Handling JSON Columns

PostgreSQL JSONB columns are automatically parsed:

```python
# Table with JSONB column
# CREATE TABLE users (id SERIAL, name TEXT, metadata JSONB);

async with manager.connection() as conn:
    # Insert JSON data
    result = await conn.execute(
        "INSERT INTO users (name, metadata) VALUES ($1, $2) RETURNING id",
        ["Alice", {"role": "admin", "preferences": {"theme": "dark"}}]
    )
    
    # Query JSON data
    result = await conn.execute("SELECT name, metadata FROM users WHERE id = $1", [1])
    row = result.result()[0]
    
    name = row[0]
    metadata = row[1]  # Already parsed as Python dict
    
    print(f"User: {name}")
    print(f"Role: {metadata['role']}")
    print(f"Theme: {metadata['preferences']['theme']}")
```

---

## 8. Exception Handling

### Common PSQLPy Exceptions

```python
from psqlpy import ConnectionPool
import logging

logger = logging.getLogger(__name__)


async def safe_query_example(manager: PostgreSQLManager, user_id: int):
    """Example of proper exception handling."""
    try:
        async with manager.connection() as conn:
            result = await conn.execute(
                "SELECT * FROM users WHERE id = $1",
                [user_id]
            )
            return result.result()
            
    except RuntimeError as e:
        # Connection pool not initialized or other runtime errors
        logger.error(f"Runtime error: {e}")
        raise
        
    except Exception as e:
        # Database errors (constraint violations, syntax errors, etc.)
        logger.error(f"Database error: {e}")
        
        # Check for specific PostgreSQL error messages
        error_msg = str(e).lower()
        
        if "unique constraint" in error_msg:
            logger.error("Duplicate key violation")
        elif "foreign key" in error_msg:
            logger.error("Foreign key constraint violation")
        elif "does not exist" in error_msg:
            logger.error("Table or column does not exist")
        
        raise
```

### Retry Logic for Transient Errors

```python
import asyncio
from typing import Optional


async def execute_with_retry(
    manager: PostgreSQLManager,
    query: str,
    parameters: list,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> Optional[list]:
    """
    Execute query with retry logic for transient errors.
    
    Args:
        manager: PostgreSQL manager
        query: SQL query
        parameters: Query parameters
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries in seconds
    
    Returns:
        Query result rows or None
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            async with manager.connection() as conn:
                result = await conn.execute(query, parameters)
                return result.result()
                
        except Exception as e:
            last_error = e
            error_msg = str(e).lower()
            
            # Check if error is retryable
            is_transient = (
                "connection" in error_msg or
                "timeout" in error_msg or
                "too many connections" in error_msg
            )
            
            if not is_transient or attempt == max_retries - 1:
                # Don't retry if not transient or last attempt
                logger.error(f"Query failed (attempt {attempt + 1}/{max_retries}): {e}")
                raise
            
            # Log and retry
            logger.warning(
                f"Transient error (attempt {attempt + 1}/{max_retries}): {e}. "
                f"Retrying in {retry_delay}s..."
            )
            await asyncio.sleep(retry_delay)
    
    # Should never reach here, but just in case
    raise last_error
```

### Context Manager with Error Handling

```python
class SafePostgreSQLManager(PostgreSQLManager):
    """Extended manager with built-in error handling."""
    
    @asynccontextmanager
    async def safe_connection(self):
        """
        Get a connection with automatic error handling.
        
        Usage:
            async with manager.safe_connection() as conn:
                if conn:
                    result = await conn.execute(query, params)
        """
        conn = None
        try:
            if not self._initialized or not self._pool:
                logger.error("PostgreSQL manager not initialized")
                yield None
                return
            
            conn = await self._pool.connection()
            yield conn
            
        except Exception as e:
            logger.error(f"Database error: {e}", exc_info=True)
            yield None
            
        finally:
            # Connection automatically returned to pool
            pass
```

---

## 9. Vector Operations (pgvector)

### Table Schema with Vector Columns

Create tables with vector columns using the `vector(dimensions)` type:

```sql
-- Memory chunks with vector embeddings
CREATE TABLE IF NOT EXISTS memory_chunk (
    id SERIAL PRIMARY KEY,
    memory_id INTEGER NOT NULL,
    external_id TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768),  -- 768-dimensional embedding
    section_id TEXT,
    metadata JSONB DEFAULT '{}',
    access_count INTEGER DEFAULT 0,
    last_access TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create vector similarity index for fast searches
CREATE INDEX IF NOT EXISTS idx_memory_chunk_embedding
ON memory_chunk
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Storing Vector Embeddings

Use `PgVector` from `psqlpy.extra_types` to store embeddings:

```python
from psqlpy.extra_types import PgVector
from typing import List, Optional


async def create_chunk_with_embedding(
    manager: PostgreSQLManager,
    memory_id: int,
    external_id: str,
    content: str,
    embedding: List[float],
    section_id: Optional[str] = None,
    metadata: Optional[dict] = None
) -> int:
    """
    Create a memory chunk with vector embedding.
    
    Args:
        manager: PostgreSQL manager
        memory_id: Parent memory ID
        external_id: Agent identifier
        content: Chunk content
        embedding: Embedding vector as list of floats
        section_id: Optional section reference
        metadata: Optional metadata dict
    
    Returns:
        Created chunk ID
    """
    query = """
        INSERT INTO memory_chunk 
        (memory_id, external_id, content, embedding, section_id, metadata, access_count)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
    """
    
    # IMPORTANT: Convert Python list to PgVector
    pg_vector = PgVector(embedding)
    
    async with manager.connection() as conn:
        result = await conn.execute(
            query,
            [
                memory_id,
                external_id,
                content,
                pg_vector,  # Use PgVector, not the raw list
                section_id,
                metadata or {},
                0  # access_count
            ]
        )
        
        rows = result.result()
        if not rows:
            raise ValueError("INSERT did not return an ID")
        
        chunk_id = rows[0][0]
        logger.info(f"Created chunk {chunk_id} with embedding")
        return chunk_id
```

### Vector Similarity Search

PSQLPy supports PostgreSQL's vector operators:

- `<=>` : Cosine distance (1 - cosine similarity)
- `<->` : L2 distance (Euclidean)
- `<#>` : Inner product

```python
async def vector_similarity_search(
    manager: PostgreSQLManager,
    external_id: str,
    query_embedding: List[float],
    limit: int = 10,
    similarity_threshold: float = 0.7
) -> List[dict]:
    """
    Search for similar chunks using vector similarity.
    
    Args:
        manager: PostgreSQL manager
        external_id: Agent identifier
        query_embedding: Query vector
        limit: Maximum results
        similarity_threshold: Minimum similarity score (0-1)
    
    Returns:
        List of matching chunks with similarity scores
    """
    pg_vector = PgVector(query_embedding)
    
    query = """
        SELECT 
            id,
            content,
            section_id,
            metadata,
            1 - (embedding <=> $1) AS similarity_score
        FROM memory_chunk
        WHERE external_id = $2
          AND embedding IS NOT NULL
          AND 1 - (embedding <=> $1) >= $3
        ORDER BY embedding <=> $1
        LIMIT $4
    """
    
    async with manager.connection() as conn:
        result = await conn.execute(
            query,
            [pg_vector, external_id, similarity_threshold, limit]
        )
        rows = result.result()
        
        chunks = []
        for row in rows:
            chunks.append({
                "id": row[0],
                "content": row[1],
                "section_id": row[2],
                "metadata": row[3],
                "similarity_score": float(row[4])
            })
        
        logger.info(f"Found {len(chunks)} similar chunks for {external_id}")
        return chunks
```

### Understanding Vector Operators

```python
# Cosine similarity (most common for semantic search)
# Range: 0 (opposite) to 1 (identical)
# Use: 1 - (embedding <=> query) for similarity score
similarity = 1 - cosine_distance

# L2 distance (Euclidean distance)
# Smaller = more similar
# Use: embedding <-> query
distance = l2_distance

# Inner product
# Larger = more similar (if vectors are normalized)
# Use: embedding <#> query
inner_product = dot_product
```

### Real-World Example: Semantic Search

```python
from dataclasses import dataclass
from typing import List


@dataclass
class SearchResult:
    """Search result with content and score."""
    chunk_id: int
    content: str
    similarity_score: float
    metadata: dict


class MemorySearchRepository:
    """Repository for memory search operations."""
    
    def __init__(self, manager: PostgreSQLManager):
        self.postgres = manager
    
    async def semantic_search(
        self,
        external_id: str,
        query_embedding: List[float],
        limit: int = 10,
        min_similarity: float = 0.7
    ) -> List[SearchResult]:
        """
        Perform semantic search on memory chunks.
        
        Args:
            external_id: Agent identifier
            query_embedding: Query embedding vector
            limit: Maximum results
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of search results
        """
        pg_vector = PgVector(query_embedding)
        
        query = """
            SELECT 
                id,
                content,
                metadata,
                1 - (embedding <=> $1) AS similarity
            FROM memory_chunk
            WHERE external_id = $2
              AND embedding IS NOT NULL
              AND 1 - (embedding <=> $1) >= $3
            ORDER BY embedding <=> $1
            LIMIT $4
        """
        
        async with self.postgres.connection() as conn:
            result = await conn.execute(
                query,
                [pg_vector, external_id, min_similarity, limit]
            )
            rows = result.result()
            
            results = [
                SearchResult(
                    chunk_id=row[0],
                    content=row[1],
                    similarity_score=float(row[3]),
                    metadata=row[2]
                )
                for row in rows
            ]
            
            return results
```

---

## 10. BM25 Full-Text Search

### Table Schema with BM25

BM25 uses a special `bm25vector` type that is automatically generated via database triggers:

```sql
-- Memory chunk table with BM25 support
CREATE TABLE IF NOT EXISTS memory_chunk (
    id SERIAL PRIMARY KEY,
    memory_id INTEGER NOT NULL,
    external_id TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768),
    content_bm25 bm25vector,  -- Auto-populated by trigger
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create BERT tokenizer for BM25
SELECT create_tokenizer(
    'bert',
    $$ model = "bert_base_uncased" $$
);

-- Trigger to automatically populate bm25vector
CREATE OR REPLACE FUNCTION update_bm25_vector_memory_chunk()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND OLD.content IS DISTINCT FROM NEW.content) THEN
        -- Automatically tokenize content into bm25vector
        NEW.content_bm25 = tokenize(NEW.content, 'bert');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_bm25_memory_chunk
    BEFORE INSERT OR UPDATE ON memory_chunk
    FOR EACH ROW EXECUTE FUNCTION update_bm25_vector_memory_chunk();

-- Create BM25 index for fast text search
CREATE INDEX IF NOT EXISTS idx_memory_chunk_bm25
ON memory_chunk
USING bm25 (content_bm25 bm25_ops);
```

**Important Notes:**
- The `content_bm25` column is automatically populated by the trigger
- You don't manually insert values into `content_bm25`
- The tokenizer ('bert') must exist before creating the trigger
- The index name is used in BM25 queries

### BM25 Text Search

BM25 search uses `to_bm25query()` and `tokenize()` functions:

```python
async def bm25_text_search(
    manager: PostgreSQLManager,
    external_id: str,
    query_text: str,
    limit: int = 10,
    min_score: float = 0.0
) -> List[dict]:
    """
    Search for chunks using BM25 text ranking.
    
    Args:
        manager: PostgreSQL manager
        external_id: Agent identifier
        query_text: Search query text
        limit: Maximum results
        min_score: Minimum BM25 score threshold
    
    Returns:
        List of matching chunks with BM25 scores
    """
    query = """
        SELECT 
            id,
            content,
            metadata,
            content_bm25 <&> to_bm25query('idx_memory_chunk_bm25', tokenize($1, 'bert')) AS bm25_score
        FROM memory_chunk
        WHERE external_id = $2
          AND content_bm25 IS NOT NULL
          AND content_bm25 <&> to_bm25query('idx_memory_chunk_bm25', tokenize($1, 'bert')) >= $3
        ORDER BY bm25_score DESC
        LIMIT $4
    """
    
    async with manager.connection() as conn:
        result = await conn.execute(
            query,
            [query_text, external_id, min_score, limit]
        )
        rows = result.result()
        
        chunks = []
        for row in rows:
            chunks.append({
                "id": row[0],
                "content": row[1],
                "metadata": row[2],
                "bm25_score": float(row[3])
            })
        
        logger.info(f"BM25 search found {len(chunks)} chunks for query: {query_text}")
        return chunks
```

### BM25 Query Syntax

```python
# 1. Simple keyword search
query_text = "machine learning"

# 2. The BM25 query is created with:
#    - to_bm25query('index_name', tokenized_query)
#    - tokenize(text, 'tokenizer_name')

# 3. The <&> operator performs BM25 similarity search
#    Returns a score (higher = more relevant)

# Example query structure:
"""
SELECT 
    content,
    content_bm25 <&> to_bm25query('idx_name', tokenize($1, 'bert')) AS score
FROM table
WHERE content_bm25 <&> to_bm25query('idx_name', tokenize($1, 'bert')) >= min_score
ORDER BY score DESC
"""
```

### Understanding BM25 Components

1. **Tokenizer:** Breaks text into tokens
   - `'bert'`: BERT-based tokenization
   - Must be created with `create_tokenizer()`

2. **Index Name:** Must match the BM25 index
   - Used in `to_bm25query('idx_name', ...)`
   - Must be the exact index name from CREATE INDEX

3. **Operator `<&>`:** BM25 similarity operator
   - Returns relevance score
   - Higher score = more relevant

---

## 11. Hybrid Search

### Combining Vector and BM25 Search

Hybrid search provides the best of both worlds: semantic understanding (vectors) and keyword matching (BM25):

```python
async def hybrid_search(
    manager: PostgreSQLManager,
    external_id: str,
    query_text: str,
    query_embedding: List[float],
    limit: int = 10,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3,
    min_vector_score: Optional[float] = None,
    min_bm25_score: Optional[float] = None
) -> List[dict]:
    """
    Hybrid search combining vector similarity and BM25 text search.
    
    Args:
        manager: PostgreSQL manager
        external_id: Agent identifier
        query_text: Query text for BM25
        query_embedding: Query embedding for vector search
        limit: Maximum results
        vector_weight: Weight for vector similarity (0-1)
        bm25_weight: Weight for BM25 score (0-1)
        min_vector_score: Optional minimum vector similarity
        min_bm25_score: Optional minimum BM25 score
    
    Returns:
        List of chunks ranked by combined score
    """
    pg_vector = PgVector(query_embedding)
    
    query = """
        WITH vector_results AS (
            SELECT 
                id,
                1 - (embedding <=> $1) AS vector_score
            FROM memory_chunk
            WHERE external_id = $2 
              AND embedding IS NOT NULL
        ),
        bm25_results AS (
            SELECT 
                id,
                content_bm25 <&> to_bm25query('idx_memory_chunk_bm25', tokenize($3, 'bert')) AS bm25_score
            FROM memory_chunk
            WHERE external_id = $2 
              AND content_bm25 IS NOT NULL
        )
        SELECT 
            c.id,
            c.content,
            c.metadata,
            COALESCE(v.vector_score, 0) * $4 + COALESCE(b.bm25_score, 0) * $5 AS combined_score,
            COALESCE(v.vector_score, 0) AS vector_score,
            COALESCE(b.bm25_score, 0) AS bm25_score
        FROM memory_chunk c
        LEFT JOIN vector_results v ON c.id = v.id
        LEFT JOIN bm25_results b ON c.id = b.id
        WHERE c.external_id = $2
          AND (v.vector_score IS NOT NULL OR b.bm25_score IS NOT NULL)
          AND ($6::float IS NULL OR COALESCE(v.vector_score, 0) >= $6)
          AND ($7::float IS NULL OR COALESCE(b.bm25_score, 0) >= $7)
        ORDER BY combined_score DESC
        LIMIT $8
    """
    
    async with manager.connection() as conn:
        result = await conn.execute(
            query,
            [
                pg_vector,
                external_id,
                query_text,
                vector_weight,
                bm25_weight,
                min_vector_score,
                min_bm25_score,
                limit
            ]
        )
        rows = result.result()
        
        chunks = []
        for row in rows:
            chunks.append({
                "id": row[0],
                "content": row[1],
                "metadata": row[2],
                "combined_score": float(row[3]),
                "vector_score": float(row[4]),
                "bm25_score": float(row[5])
            })
        
        logger.info(
            f"Hybrid search found {len(chunks)} chunks "
            f"(vector_weight={vector_weight}, bm25_weight={bm25_weight})"
        )
        return chunks
```

### Adjusting Weights for Different Use Cases

```python
# Semantic-focused (emphasize meaning over keywords)
semantic_results = await hybrid_search(
    manager, external_id, query_text, query_embedding,
    vector_weight=0.8, bm25_weight=0.2
)

# Keyword-focused (emphasize exact matches)
keyword_results = await hybrid_search(
    manager, external_id, query_text, query_embedding,
    vector_weight=0.3, bm25_weight=0.7
)

# Balanced (equal weighting)
balanced_results = await hybrid_search(
    manager, external_id, query_text, query_embedding,
    vector_weight=0.5, bm25_weight=0.5
)
```

---

## 12. Best Practices

### 1. Always Use Connection Context Managers

```python
# ✅ GOOD: Context manager returns connection to pool
async with manager.connection() as conn:
    result = await conn.execute(query, params)

# ❌ BAD: Manual management risks leaking connections
conn = await manager.get_connection()
result = await conn.execute(query, params)
# Connection might not be returned if exception occurs!
```

### 2. Initialize Manager Once, Reuse Everywhere

```python
# ✅ GOOD: Create manager once at startup
class Application:
    def __init__(self):
        self.config = get_config()
        self.db_manager = PostgreSQLManager(self.config)
    
    async def startup(self):
        await self.db_manager.initialize()
    
    async def shutdown(self):
        await self.db_manager.close()

# ❌ BAD: Creating new manager for each request
async def handle_request():
    manager = PostgreSQLManager(get_config())  # Don't do this!
    await manager.initialize()
    # ...
```

### 3. Use Proper Parameter Binding

```python
# ✅ GOOD: Use $1, $2, ... placeholders
result = await conn.execute(
    "SELECT * FROM users WHERE email = $1 AND age > $2",
    [email, age]
)

# ❌ BAD: String formatting (SQL injection risk!)
result = await conn.execute(
    f"SELECT * FROM users WHERE email = '{email}'"  # NEVER DO THIS!
)
```

### 4. Handle Exceptions Appropriately

```python
# ✅ GOOD: Specific error handling
try:
    async with manager.connection() as conn:
        result = await conn.execute(query, params)
except RuntimeError as e:
    logger.error(f"Connection pool error: {e}")
    raise
except Exception as e:
    logger.error(f"Database error: {e}")
    # Handle or re-raise
    raise
```

### 5. Use Transactions for Related Operations

```python
# ✅ GOOD: Use transactions for atomic operations
async with manager.connection() as conn:
    await conn.execute("BEGIN")
    try:
        await conn.execute(query1, params1)
        await conn.execute(query2, params2)
        await conn.execute("COMMIT")
    except Exception:
        await conn.execute("ROLLBACK")
        raise
```

### 6. Convert Vectors with PgVector

```python
# ✅ GOOD: Use PgVector for embeddings
from psqlpy.extra_types import PgVector

pg_vector = PgVector(embedding)
await conn.execute(query, [pg_vector])

# ❌ BAD: Passing raw list
await conn.execute(query, [embedding])  # Won't work!
```

### 7. Normalize Vectors for Consistent Similarity

```python
import numpy as np

def normalize_vector(vector: List[float]) -> List[float]:
    """Normalize vector to unit length."""
    arr = np.array(vector)
    norm = np.linalg.norm(arr)
    if norm == 0:
        return vector
    return (arr / norm).tolist()

# Use normalized vectors
normalized = normalize_vector(raw_embedding)
pg_vector = PgVector(normalized)
```

### 8. Add Indexes for Performance

```sql
-- Vector index for similarity search
CREATE INDEX idx_embedding ON table_name 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- BM25 index for text search
CREATE INDEX idx_bm25 ON table_name 
USING bm25 (content_bm25 bm25_ops);

-- Regular indexes for filters
CREATE INDEX idx_external_id ON table_name (external_id);
CREATE INDEX idx_created_at ON table_name (created_at DESC);
```

### 9. Use Connection Pool Appropriately

```python
# ✅ GOOD: One pool per application
pool_size = 10  # For typical web application

# ❌ BAD: Too many connections
pool_size = 1000  # Will overwhelm database!

# ❌ BAD: Too few connections
pool_size = 1  # Will bottleneck on concurrent requests
```

### 10. Close Pool on Shutdown

```python
# FastAPI example
@app.on_event("startup")
async def startup():
    await db_manager.initialize()

@app.on_event("shutdown")
async def shutdown():
    await db_manager.close()  # Important!
```

---

## 13. Common Pitfalls

### Pitfall 1: Forgetting to Call initialize()

```python
# ❌ WRONG
manager = PostgreSQLManager(config)
# Forgot to call initialize()
async with manager.connection() as conn:  # RuntimeError!
    ...

# ✅ CORRECT
manager = PostgreSQLManager(config)
await manager.initialize()  # Must call this first
async with manager.connection() as conn:
    ...
```

### Pitfall 2: Not Using PgVector for Embeddings

```python
# ❌ WRONG
embedding = [0.1, 0.2, 0.3, ...]
await conn.execute(
    "INSERT INTO table (embedding) VALUES ($1)",
    [embedding]  # Will fail!
)

# ✅ CORRECT
from psqlpy.extra_types import PgVector

pg_vector = PgVector(embedding)
await conn.execute(
    "INSERT INTO table (embedding) VALUES ($1)",
    [pg_vector]  # Works!
)
```

### Pitfall 3: Wrong Placeholder Syntax

```python
# ❌ WRONG: psycopg2 style
await conn.execute("SELECT * FROM users WHERE id = %s", [user_id])

# ❌ WRONG: SQLite style
await conn.execute("SELECT * FROM users WHERE id = ?", [user_id])

# ✅ CORRECT: PostgreSQL style
await conn.execute("SELECT * FROM users WHERE id = $1", [user_id])
```

### Pitfall 4: Not Handling Empty Results

```python
# ❌ WRONG: Assumes rows exist
result = await conn.execute("SELECT * FROM users WHERE id = $1", [999])
user = result.result()[0]  # IndexError if no rows!

# ✅ CORRECT: Check for empty results
result = await conn.execute("SELECT * FROM users WHERE id = $1", [999])
rows = result.result()
if rows:
    user = rows[0]
else:
    user = None
```

### Pitfall 5: Forgetting to Split SQL Statements

```python
# ❌ WRONG: Multiple statements in one execute()
await conn.execute("""
    CREATE TABLE users (id SERIAL);
    CREATE INDEX idx_users ON users(id);
""")  # PSQLPy doesn't support this!

# ✅ CORRECT: Execute separately
await conn.execute("CREATE TABLE users (id SERIAL)")
await conn.execute("CREATE INDEX idx_users ON users(id)")
```

### Pitfall 6: Wrong BM25 Index Name

```python
# ❌ WRONG: Index name doesn't match
query = """
    SELECT content_bm25 <&> to_bm25query('wrong_index_name', tokenize($1, 'bert'))
    FROM table
"""

# ✅ CORRECT: Use exact index name from CREATE INDEX
query = """
    SELECT content_bm25 <&> to_bm25query('idx_memory_chunk_bm25', tokenize($1, 'bert'))
    FROM table
"""
```

### Pitfall 7: Manually Setting bm25vector Column

```python
# ❌ WRONG: Trying to insert bm25vector manually
await conn.execute(
    "INSERT INTO table (content, content_bm25) VALUES ($1, $2)",
    [content, some_bm25_value]  # content_bm25 is auto-populated!
)

# ✅ CORRECT: Only insert content, trigger handles bm25vector
await conn.execute(
    "INSERT INTO table (content) VALUES ($1)",
    [content]  # Trigger automatically populates content_bm25
)
```

### Pitfall 8: Not Using Transactions

```python
# ❌ WRONG: No transaction for related operations
await conn.execute("INSERT INTO orders ...")
await conn.execute("UPDATE inventory ...")  # If this fails, order is still inserted!

# ✅ CORRECT: Use transaction for atomicity
await conn.execute("BEGIN")
try:
    await conn.execute("INSERT INTO orders ...")
    await conn.execute("UPDATE inventory ...")
    await conn.execute("COMMIT")
except Exception:
    await conn.execute("ROLLBACK")
    raise
```

### Pitfall 9: Connection Leaks

```python
# ❌ WRONG: Connection not returned on exception
conn = await manager.get_connection()
result = await conn.execute(query, params)  # If this raises, connection is leaked!

# ✅ CORRECT: Context manager handles cleanup
async with manager.connection() as conn:
    result = await conn.execute(query, params)  # Connection always returned
```

### Pitfall 10: Ignoring Vector Dimension Mismatch

```python
# ❌ WRONG: Dimension mismatch
# Table expects vector(768)
embedding = [0.1, 0.2]  # Only 2 dimensions!
pg_vector = PgVector(embedding)
await conn.execute(...)  # Error: dimension mismatch!

# ✅ CORRECT: Ensure dimension matches table schema
assert len(embedding) == 768  # Verify dimension
pg_vector = PgVector(embedding)
await conn.execute(...)
```

---

## Summary

PSQLPy is a powerful async PostgreSQL driver with excellent support for advanced features like vector search and BM25. Key takeaways:

1. **Use connection pools** for efficient resource management
2. **Always use context managers** to prevent connection leaks
3. **Initialize once** at application startup
4. **Use `$1, $2, $3`** for parameter placeholders
5. **Use `PgVector`** for embedding columns
6. **BM25 vectors are auto-populated** by triggers
7. **Handle exceptions** appropriately
8. **Use transactions** for atomic operations
9. **Add indexes** for performance
10. **Close pool** on application shutdown

For more examples, refer to the context_bridge codebase:
- `context_bridge/database/postgres_manager.py` - Manager implementation
- `context_bridge/database/repositories/memory.py` - Repository pattern
- `context_bridge/database/init_databases.py` - Database initialization
- `context_bridge/config/settings.py` - Configuration management
