#!/usr/bin/env python3
"""
Database interaction script for Context Bridge.

This script provides a simple way to interact with a real PostgreSQL database
and initialize the Context Bridge schema.

Usage:
    python db_interact.py init    # Initialize the database schema
    python db_interact.py verify  # Verify schema exists
    python db_interact.py reset   # Reset database (dev only)
    python db_interact.py test    # Run a simple connection test
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from context_bridge.config import get_config
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.database.init_databases import (
    init_postgresql,
    verify_schema,
    reset_database,
    run_migrations,
)


async def test_connection():
    """Test database connection."""
    print("🔗 Testing database connection...")

    config = get_config()
    manager = PostgreSQLManager(config)

    try:
        async with manager:
            # Test basic connection
            is_healthy = await manager.health_check()
            if is_healthy:
                print("✅ Database connection successful!")
                print(f"   Database: {config.postgres_db}")
                print(f"   Host: {config.postgres_host}:{config.postgres_port}")
                return True
            else:
                print("❌ Database connection failed!")
                return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    print("=" * 60)
    print("🔧 Context Bridge Database Tool")
    print("=" * 60)

    try:
        if command == "test":
            success = await test_connection()

        elif command == "init":
            print("🚀 Initializing database schema...")
            await init_postgresql()
            print("✅ Database initialization completed!")

        elif command == "verify":
            print("🔍 Verifying database schema...")
            success = await verify_schema()
            if success:
                print("✅ Schema verification passed!")
            else:
                print("❌ Schema verification failed!")
                sys.exit(1)

        elif command == "reset":
            print("🗑️  Resetting database...")
            print("⚠️  This will DELETE ALL DATA!")
            if len(sys.argv) > 2 and sys.argv[2] == "--force":
                await reset_database()
                print("✅ Database reset completed!")
            else:
                confirm = input("Type 'yes' to confirm: ")
                if confirm == "yes":
                    await reset_database()
                    print("✅ Database reset completed!")
                else:
                    print("Reset cancelled.")

        elif command == "migrate":
            print("🔄 Running migrations...")
            await run_migrations()
            print("✅ Migrations completed!")

        else:
            print(f"❌ Unknown command: {command}")
            print(__doc__)
            sys.exit(1)

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
