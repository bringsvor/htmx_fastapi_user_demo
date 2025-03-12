#!/usr/bin/env python3

import pytest
import warnings
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from unittest.mock import patch, MagicMock
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import Base, User
from config import get_settings
from main import app, get_async_session

settings = get_settings()

# Create a test database URL - using SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Create test engine and session
test_engine = create_async_engine(
    TEST_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=test_engine, 
    class_=AsyncSession,
)


# Filter out specific warnings
def pytest_configure(config):
    warnings.filterwarnings(
        "ignore", 
        message="Support for class-based `config` is deprecated",
        module="pydantic"
    )
    
    warnings.filterwarnings(
        "ignore", 
        message="The `name` is not the first parameter anymore",
        module="starlette"
    )

# This fixture ensures the test database is properly set up and torn down
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Override the get_async_session dependency to use our test database
@pytest.fixture
async def override_get_async_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    async def _get_test_session():
        async with TestingSessionLocal() as session:
            yield session
    
    # Patch the dependency in main.py
    with patch("main.get_async_session", _get_test_session):
        # Also patch the dependency in imported modules
        with patch("users.get_async_session", _get_test_session):
            yield _get_test_session
    
    # Clean up after tests
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# Create a mock for SQLAlchemyUserDatabase
@pytest.fixture
def mock_user_db():
    mock_db = MagicMock()
    mock_db.get.return_value = None
    mock_db.get_by_email.return_value = None
    
    with patch("users.SQLAlchemyUserDatabase", return_value=mock_db):
        yield mock_db


# Create a test user fixture
@pytest.fixture
async def test_user(override_get_async_session):
    get_session = override_get_async_session
    async for session in get_session():
        # Create a test user
        test_user = User(
            email="test@example.com",
            hashed_password="$2b$12$Ihx.fPMPih0JzsDR9YeSE.4GiO5QXQvtmJA8MUwDV2YT7A4xGmLYS",  # hashed "password123"
            is_active=True,
            is_verified=True,
            name="Test User"
        )
        
        session.add(test_user)
        await session.commit()
        await session.refresh(test_user)
        
        yield test_user


# Helper function to run async functions in tests
@pytest.fixture
def run_async():
    def _run_async(coro):
        return asyncio.get_event_loop().run_until_complete(coro)
    
    return _run_async


# Fixture to mock the user manager
@pytest.fixture
def mock_user_manager():
    from users import UserManager
    
    mock_manager = MagicMock(spec=UserManager)
    
    # Make the methods async
    for method_name in [
        'request_verify', 'verify', 'forgot_password', 'reset_password',
        'authenticate', 'create', 'update', 'delete'
    ]:
        setattr(mock_manager, method_name, MagicMock())
        getattr(mock_manager, method_name).__awaited__ = True
    
    # Patch the get_user_manager function
    with patch("main.get_user_manager", return_value=mock_manager):
        yield mock_manager


# Fixture to disable logging during tests
@pytest.fixture(autouse=True)
def disable_logging():
    with patch("logging.Logger.info"), patch("logging.Logger.error"), patch("logging.Logger.warning"):
        yield