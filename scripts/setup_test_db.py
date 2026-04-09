#!/usr/bin/env python3
"""
Test Database Setup Script for Context Bridge Integration Tests.

This script sets up and manages test databases for integration testing.
It can create, initialize, reset, and verify test databases.

Usage:
    python scripts/setup_test_db.py init    # Initialize test database
    python scripts/setup_test_db.py verify  # Verify test database setup
    python scripts/setup_test_db.py reset   # Reset test database
    python scripts/setup_test_db.py clean   # Clean up test data
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from context_bridge.config import Config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.database.init_databases import (
    init_postgresql,
    verify_schema,
    reset_database,
)


def get_test_config() -> Config:
    """Get configuration for test database."""
    # Load from .env.test if it exists, otherwise use defaults
    test_env_file = project_root / ".env.test"
    if test_env_file.exists():
        # Load test environment variables
        from dotenv import load_dotenv

        load_dotenv(test_env_file)

    return Config(
        postgres_host=os.getenv("TEST_POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("TEST_POSTGRES_PORT", "5432")),
        postgres_user=os.getenv("TEST_POSTGRES_USER", "postgres"),
        postgres_password=os.getenv("TEST_POSTGRES_PASSWORD", "postgres"),
        postgres_db=os.getenv("TEST_POSTGRES_DB", "context_bridge_test"),
        postgres_max_pool_size=int(os.getenv("DB_POOL_MAX", "5")),
    )


async def init_test_database():
    """Initialize the test database with schema."""
    print("🚀 Initializing test database...")

    config = get_test_config()
    print(f"   Database: {config.postgres_db}")
    print(f"   Host: {config.postgres_host}:{config.postgres_port}")

    manager = PostgreSQLManager(config)
    try:
        await manager.initialize()
        print("✅ Database connection established")

        # Initialize schema
        await init_postgresql(manager)
        print("✅ Database schema initialized")

        # Verify schema
        is_valid = await verify_schema(manager)
        if is_valid:
            print("✅ Schema verification passed")
        else:
            print("❌ Schema verification failed")
            return False

    except Exception as e:
        print(f"❌ Error initializing test database: {e}")
        return False
    finally:
        await manager.close()

    print("✅ Test database initialization completed")
    return True


async def verify_test_database():
    """Verify that the test database is properly set up."""
    print("🔍 Verifying test database setup...")

    config = get_test_config()
    manager = PostgreSQLManager(config)

    try:
        await manager.initialize()
        print("✅ Database connection established")

        # Verify schema
        is_valid = await verify_schema(manager)
        if is_valid:
            print("✅ Schema verification passed")
            return True
        else:
            print("❌ Schema verification failed")
            return False

    except Exception as e:
        print(f"❌ Error verifying test database: {e}")
        return False
    finally:
        await manager.close()


async def reset_test_database():
    """Reset the test database (drop and recreate all tables)."""
    print("🗑️  Resetting test database...")
    print("⚠️  This will DELETE ALL DATA!")

    # Get confirmation unless --force is used
    if len(sys.argv) < 3 or sys.argv[2] != "--force":
        confirm = input("Type 'yes' to confirm: ")
        if confirm != "yes":
            print("Reset cancelled.")
            return False

    config = get_test_config()
    manager = PostgreSQLManager(config)

    try:
        await manager.initialize()
        print("✅ Database connection established")

        await reset_database(manager)
        print("✅ Database reset completed")

        # Re-initialize schema
        await init_postgresql(manager)
        print("✅ Database schema re-initialized")

    except Exception as e:
        print(f"❌ Error resetting test database: {e}")
        return False
    finally:
        await manager.close()

    return True


async def clean_test_data():
    """Clean up test data while preserving schema."""
    print("🧹 Cleaning up test data...")

    config = get_test_config()
    manager = PostgreSQLManager(config)

    try:
        await manager.initialize()
        print("✅ Database connection established")

        async with manager.connection() as conn:
            # Delete test data (be careful not to delete schema)
            await conn.execute(
                "DELETE FROM chunks WHERE document_id IN (SELECT id FROM documents WHERE name LIKE 'test-%')"
            )
            await conn.execute(
                "DELETE FROM pages WHERE document_id IN (SELECT id FROM documents WHERE name LIKE 'test-%')"
            )
            await conn.execute("DELETE FROM documents WHERE name LIKE 'test-%'")

        print("✅ Test data cleaned up")

    except Exception as e:
        print(f"❌ Error cleaning test data: {e}")
        return False
    finally:
        await manager.close()

    return True


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    print("=" * 60)
    print("🧪 Context Bridge Test Database Tool")
    print("=" * 60)

    try:
        if command == "init":
            success = await init_test_database()

        elif command == "verify":
            success = await verify_test_database()

        elif command == "reset":
            success = await reset_test_database()

        elif command == "clean":
            success = await clean_test_data()

        else:
            print(f"❌ Unknown command: {command}")
            print(__doc__)
            sys.exit(1)

        if "success" in locals() and success:
            print("✅ Operation completed successfully")
        else:
            print("❌ Operation failed")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
