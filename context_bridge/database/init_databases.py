"""
Initialize database schemas for PostgreSQL.

This script provides database management operations:
- init: Initialize the complete database schema
- verify: Check if all required tables/indexes exist
- reset: Drop all tables (dev only)
- migrate: Run schema migrations

Usage:
    python -m context_bridge.database.init_databases init
    python -m context_bridge.database.init_databases verify
    python -m context_bridge.database.init_databases reset --force
    python -m context_bridge.database.init_databases migrate
"""

import argparse
import asyncio
import sys
from pathlib import Path
from context_bridge.config import get_config
from context_bridge.database.postgres_manager import PostgreSQLManager


# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def verify_schema():
    """Verify all tables, indexes, and extensions exist."""
    config = get_config()
    manager = PostgreSQLManager(config)
    await manager.initialize()

    print(f"🔍 Verifying schema in: {config.postgres_db}")

    try:
        async with manager.connection() as conn:
            # Check extensions
            required_extensions = ["vector", "vchord", "pg_tokenizer", "vchord_bm25"]
        print("\n🔧 Checking extensions...")
        for ext in required_extensions:
            try:
                result = await conn.execute("SELECT 1 FROM pg_extension WHERE extname = $1", [ext])
                if result.result():
                    print(f"   ✅ {ext}")
                else:
                    print(f"   ❌ {ext} - missing")
                    return False
            except Exception as e:
                print(f"   ❌ {ext} - error: {e}")
                return False

        # Check tables
        required_tables = ["documents", "pages", "page_groups", "page_group_members", "chunks"]
        print("\n📋 Checking tables...")
        for table in required_tables:
            try:
                result = await conn.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_name = $1", [table]
                )
                if result.result():
                    print(f"   ✅ {table}")
                else:
                    print(f"   ❌ {table} - missing")
                    return False
            except Exception as e:
                print(f"   ❌ {table} - error: {e}")
                return False

        # Check indexes (basic check)
        print("\n🔍 Checking key indexes...")
        key_indexes = ["idx_chunks_vector", "idx_chunks_bm25"]
        for idx in key_indexes:
            try:
                result = await conn.execute("SELECT 1 FROM pg_indexes WHERE indexname = $1", [idx])
                if result.result():
                    print(f"   ✅ {idx}")
                else:
                    print(f"   ⚠️  {idx} - missing (may be created later)")
            except Exception as e:
                print(f"   ❌ {idx} - error: {e}")

        print("\n✅ Schema verification completed successfully!")
        return True

    finally:
        await manager.close()


async def reset_database():
    """Drop and recreate all tables (dev only)."""
    config = get_config()
    manager = PostgreSQLManager(config)
    await manager.initialize()

    print(f"🗑️  Resetting database: {config.postgres_db}")
    print("⚠️  This will DROP ALL TABLES and DATA!")

    # Safety check - only allow in development
    if config.postgres_db not in ["context_bridge_dev", "context_bridge"]:
        print(f"❌ Reset only allowed in development databases. Current: {config.postgres_db}")
        return False

    try:
        async with manager.connection() as conn:
            # Drop tables in reverse dependency order
            tables_to_drop = [
                "chunks",
                "page_group_members",
                "page_groups",
                "pages",
                "documents",
            ]
        print("\n🗑️  Dropping tables...")

        for table in tables_to_drop:
            try:
                await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                print(f"   ✅ Dropped {table}")
            except Exception as e:
                print(f"   ❌ Failed to drop {table}: {e}")

        # Drop functions and triggers
        print("\n🗑️  Dropping functions and triggers...")
        objects_to_drop = [
            "DROP TRIGGER IF EXISTS chunks_bm25_trigger ON chunks",
            "DROP TRIGGER IF EXISTS update_doc_on_page_insert ON pages",
            "DROP TRIGGER IF EXISTS update_doc_on_chunk_insert ON chunks",
            "DROP FUNCTION IF EXISTS generate_bm25_vector()",
            "DROP FUNCTION IF EXISTS update_document_timestamp()",
        ]

        for drop_stmt in objects_to_drop:
            try:
                await conn.execute(drop_stmt)
                print(f"   ✅ {drop_stmt.split()[-1]}")
            except Exception as e:
                print(f"   ⚠️  {drop_stmt}: {e}")

        print("\n✅ Database reset completed!")

    finally:
        await manager.close()

    return True


async def run_migrations():
    """Run database migrations for schema changes."""
    config = get_config()
    manager = PostgreSQLManager(config)
    await manager.initialize()

    print(f"🔄 Running migrations on: {config.postgres_db}")

    try:
        async with manager.connection() as conn:
            # Check if we need to add any missing columns or indexes
            print("\n🔍 Checking for missing schema elements...")

        # Example migration: Add metadata column to documents if missing
        try:
            result = await conn.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents' AND column_name = 'metadata'
            """
            )
            if not result.result():
                print("   📝 Adding metadata column to documents table...")
                await conn.execute(
                    """
                    ALTER TABLE documents ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb
                """
                )
                print("   ✅ Added metadata column")
        except Exception as e:
            print(f"   ⚠️  Migration check failed: {e}")

        # Add any other migrations here as needed
        print("\n✅ Migrations completed!")

    finally:
        await manager.close()


async def init_postgresql():
    """Initialize PostgreSQL schema."""
    config = get_config()
    manager = PostgreSQLManager(config)
    await manager.initialize()

    print(f"🔗 Connecting to PostgreSQL: {config.postgres_db}")

    try:
        async with manager.connection() as conn:
            print("\n🏗️  Initializing PostgreSQL schema...")

            # Ensure extensions exist
        print("\n🔧 Ensuring extensions...")
        extensions = [
            ("vector", "Vector similarity search"),
            ("vchord", "Hierarchical vector search"),
            ("pg_tokenizer", "Text tokenization"),
            ("vchord_bm25", "BM25 full-text search"),
        ]
        for ext_name, desc in extensions:
            try:
                await conn.execute(f"CREATE EXTENSION IF NOT EXISTS {ext_name} CASCADE")
                print(f"   ✅ {ext_name}: {desc}")
            except Exception as e:
                print(f"   ⚠️  {ext_name}: {e}")

        # Read and execute extensions.sql
        print("\n📄 Reading extensions.sql...")
        schema_path = Path(__file__).parent / "schema" / "extensions.sql"

        if not schema_path.exists():
            print(f"   ❌ Schema file not found: {schema_path}")
            return

        schema_sql = schema_path.read_text(encoding="utf-8")

        # Split into statements and execute
        # Remove comments and split by semicolons, but not inside dollar-quoted strings
        statements = []
        current = []
        in_dollar = False

        for line in schema_sql.split("\n"):
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

        # Execute each statement
        for i, statement in enumerate(statements, 1):
            statement = statement.strip()
            if not statement:
                continue

            try:
                await conn.execute(statement)
                # Extract table/object name for logging
                if "CREATE TABLE" in statement:
                    if "IF NOT EXISTS" in statement:
                        table_name = (
                            statement.split("CREATE TABLE IF NOT EXISTS")[1].split("(")[0].strip()
                        )
                    else:
                        table_name = statement.split("CREATE TABLE")[1].split("(")[0].strip()
                    print(f"   ✅ Table: {table_name}")
                elif "CREATE INDEX" in statement:
                    if "IF NOT EXISTS" in statement:
                        index_name = (
                            statement.split("CREATE INDEX IF NOT EXISTS")[1].split("ON")[0].strip()
                        )
                    else:
                        index_name = statement.split("CREATE INDEX")[1].split("ON")[0].strip()
                    print(f"   ✅ Index: {index_name}")
                elif "CREATE TRIGGER" in statement:
                    trigger_name = statement.split("CREATE TRIGGER")[1].split("BEFORE")[0].strip()
                    print(f"   ✅ Trigger: {trigger_name}")
                elif "CREATE OR REPLACE FUNCTION" in statement or "CREATE FUNCTION" in statement:
                    func_name = statement.split("FUNCTION")[1].split("(")[0].strip()
                    print(f"   ✅ Function: {func_name}")
                elif "SELECT create_tokenizer" in statement:
                    print(f"   ✅ Tokenizer: bert")
                elif "CREATE OR REPLACE VIEW" in statement or "CREATE VIEW" in statement:
                    view_name = statement.split("VIEW")[1].split("AS")[0].strip()
                    print(f"   ✅ View: {view_name}")
                elif "DROP TRIGGER" in statement:
                    trigger_name = statement.split("DROP TRIGGER")[1].split("ON")[0].strip()
                    print(f"   ✅ Drop Trigger: {trigger_name}")
            except Exception as e:
                print(f"   ❌ Error in statement {i}: {e}")
                print(f"      Statement: {statement[:100]}...")

        print("\n✅ PostgreSQL schema initialization complete!")

        # Run migrations
        await run_migrations()

    except Exception as e:
        print(f"\n❌ Schema initialization failed: {e}")
        raise

    finally:
        await manager.close()


async def main():
    """Initialize databases with command line options."""
    parser = argparse.ArgumentParser(description="Context Bridge Database Management")
    parser.add_argument(
        "action", choices=["init", "verify", "reset", "migrate"], help="Action to perform"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force reset without confirmation (dev only)"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("🚀 Context Bridge Database Management")
    print("=" * 70)
    print(f"Action: {args.action}")

    try:
        if args.action == "init":
            await init_postgresql()
            print("\n" + "=" * 70)
            print("✅ Database initialization completed successfully!")
            print("=" * 70)

        elif args.action == "verify":
            success = await verify_schema()
            if success:
                print("\n✅ Schema verification passed!")
            else:
                print("\n❌ Schema verification failed!")
                sys.exit(1)

        elif args.action == "reset":
            if not args.force:
                confirm = input("\n⚠️  This will DELETE ALL DATA! Type 'yes' to confirm: ")
                if confirm != "yes":
                    print("Reset cancelled.")
                    return
            success = await reset_database()
            if success:
                print("\n✅ Database reset completed!")
            else:
                print("\n❌ Database reset failed!")
                sys.exit(1)

        elif args.action == "migrate":
            await run_migrations()
            print("\n✅ Migrations completed!")

    except Exception as e:
        print(f"\n❌ Operation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
