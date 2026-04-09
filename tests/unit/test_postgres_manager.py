"""Tests for PostgreSQL manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from context_bridge.database.postgres_manager import PostgreSQLManager
from context_bridge.config import Config


class TestPostgreSQLManager:
    """Test PostgreSQLManager functionality."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        config = MagicMock(spec=Config)
        config.postgres_host = "localhost"
        config.postgres_port = 5432
        config.postgres_user = "testuser"
        config.postgres_password = "testpass"
        config.postgres_db = "testdb"
        config.postgres_max_pool_size = 10
        return config

    @pytest.fixture
    def manager(self, mock_config):
        """Create a PostgreSQLManager instance."""
        return PostgreSQLManager(mock_config)

    def test_init(self, mock_config):
        """Test manager initialization."""
        manager = PostgreSQLManager(mock_config)
        assert manager.config == mock_config
        assert not manager._initialized
        assert manager._pool is None
        expected_dsn = "postgresql://testuser:testpass@localhost:5432/testdb"
        assert manager.dsn == expected_dsn

    @pytest.mark.asyncio
    async def test_initialize_success(self, manager):
        """Test successful initialization."""
        with patch("context_bridge.database.postgres_manager.ConnectionPool") as mock_pool_class:
            mock_pool = MagicMock()
            mock_pool_class.return_value = mock_pool

            await manager.initialize()

            assert manager._initialized
            assert manager._pool == mock_pool
            mock_pool_class.assert_called_once_with(dsn=manager.dsn, max_db_pool_size=10)

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, manager):
        """Test initialization when already initialized."""
        manager._initialized = True

        with patch("context_bridge.database.postgres_manager.logger") as mock_logger:
            await manager.initialize()

            mock_logger.warning.assert_called_once_with("PostgreSQL manager already initialized")

    @pytest.mark.asyncio
    async def test_initialize_with_retry_success(self, manager):
        """Test initialization with retry logic - success on second attempt."""
        with patch("context_bridge.database.postgres_manager.ConnectionPool") as mock_pool_class:
            mock_pool = MagicMock()
            # First call raises exception, second succeeds
            mock_pool_class.side_effect = [Exception("Connection failed"), mock_pool]

            with patch("asyncio.sleep") as mock_sleep:
                await manager.initialize()

                assert manager._initialized
                assert manager._pool == mock_pool
                assert mock_pool_class.call_count == 2
                mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_max_retries_exceeded(self, manager):
        """Test initialization when max retries exceeded."""
        with patch("context_bridge.database.postgres_manager.ConnectionPool") as mock_pool_class:
            mock_pool_class.side_effect = Exception("Connection failed")

            with patch("asyncio.sleep") as mock_sleep:
                with pytest.raises(Exception, match="Connection failed"):
                    await manager.initialize()

                assert not manager._initialized
                assert manager._pool is None
                assert mock_pool_class.call_count == 5  # max_retries
                assert mock_sleep.call_count == 4  # retries - 1

    @pytest.mark.asyncio
    async def test_health_check_success(self, manager):
        """Test successful health check."""
        manager._initialized = True
        manager._pool = MagicMock()

        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result.return_value = [{"health": 1}]
        mock_conn.execute.return_value = mock_result

        with patch.object(manager, "connection") as mock_connection:
            mock_connection.return_value.__aenter__.return_value = mock_conn

            result = await manager.health_check()

            assert result is True
            mock_conn.execute.assert_called_once_with("SELECT 1 as health")

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self, manager):
        """Test health check when not initialized."""
        result = await manager.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_failure(self, manager):
        """Test health check failure."""
        manager._initialized = True
        manager._pool = MagicMock()

        with patch.object(manager, "connection") as mock_connection:
            mock_connection.return_value.__aenter__.side_effect = Exception("Connection error")

            result = await manager.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_execute_transaction_success(self, manager):
        """Test successful transaction execution."""
        manager._initialized = True
        manager._pool = MagicMock()

        operations = [
            ("INSERT INTO test (col) VALUES ($1)", ["value1"]),
            ("UPDATE test SET col = $1", ["value2"]),
        ]

        mock_conn = AsyncMock()
        with patch.object(manager, "connection") as mock_connection:
            mock_connection.return_value.__aenter__.return_value = mock_conn

            await manager.execute_transaction(operations)

            # Verify transaction commands were called
            assert mock_conn.execute.call_count == 4  # BEGIN + 2 operations + COMMIT

    @pytest.mark.asyncio
    async def test_execute_transaction_rollback_on_error(self, manager):
        """Test transaction rollback on error."""
        manager._initialized = True
        manager._pool = MagicMock()

        operations = [
            ("INSERT INTO test (col) VALUES ($1)", ["value1"]),
            ("UPDATE test SET col = $1", ["value2"]),  # This will fail
        ]

        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = [None, None, Exception("Operation failed")]

        with patch.object(manager, "connection") as mock_connection:
            mock_connection.return_value.__aenter__.return_value = mock_conn

            with pytest.raises(Exception, match="Operation failed"):
                await manager.execute_transaction(operations)

            # Verify ROLLBACK was called
            rollback_calls = [
                call for call in mock_conn.execute.call_args_list if call[0][0] == "ROLLBACK"
            ]
            assert len(rollback_calls) == 1

    def test_log_pool_stats_initialized(self, manager):
        """Test logging pool stats when initialized."""
        manager._initialized = True
        manager._pool = MagicMock()

        with patch("context_bridge.database.postgres_manager.logger") as mock_logger:
            manager.log_pool_stats()

            mock_logger.info.assert_called_once_with(
                "PostgreSQL connection pool status: initialized, max_size=10"
            )

    def test_log_pool_stats_not_initialized(self, manager):
        """Test logging pool stats when not initialized."""
        with patch("context_bridge.database.postgres_manager.logger") as mock_logger:
            manager.log_pool_stats()

            mock_logger.warning.assert_called_once_with(
                "PostgreSQL manager not initialized - cannot log pool stats"
            )

    @pytest.mark.asyncio
    async def test_close_success(self, manager):
        """Test successful close."""
        mock_pool = MagicMock()
        manager._pool = mock_pool
        manager._initialized = True

        await manager.close()

        assert manager._pool is None
        assert not manager._initialized
        mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_with_error(self, manager):
        """Test close with error handling."""
        mock_pool = MagicMock()
        mock_pool.close.side_effect = Exception("Close failed")
        manager._pool = mock_pool
        manager._initialized = True

        with pytest.raises(Exception, match="Close failed"):
            await manager.close()

        # State should still be cleaned up
        assert manager._pool is None
        assert not manager._initialized

    @pytest.mark.asyncio
    async def test_context_manager(self, manager):
        """Test async context manager."""
        with (
            patch.object(manager, "initialize") as mock_init,
            patch.object(manager, "close") as mock_close,
        ):

            async with manager:
                mock_init.assert_called_once()

            mock_close.assert_called_once()
