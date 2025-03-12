# FastAPI Test Suite Documentation

This document provides an overview of the test suite for the FastAPI application.

## Test Structure

The test suite includes the following files:

1. `conftest.py` - Contains pytest fixtures and shared utilities for testing
2. `test_main.py` - Main application route and core functionality tests
3. `test_auth.py` - Authentication system tests
4. `test_user_manager.py` - User management functionality tests

## Setup Requirements

To run the tests, you need to install the required dependencies:

```bash
pip install pytest pytest-asyncio httpx pytest-mock pytest-cov
```

## Running Tests

To run all tests:

```bash
pytest
```

To run specific test files:

```bash
pytest tests/test_main.py
pytest tests/test_auth.py
pytest tests/test_user_manager.py
```

To see more detailed output:

```bash
pytest -v
```

To see test coverage:

```bash
pytest --cov=app
```

## Known Issues and Test Status

Several tests are currently marked as `xfail` (expected failure) due to implementation details or dependencies that need to be adjusted:

1. OAuth routes tests - The Google and Vipps OAuth routes are not properly registered or return 404 errors.
2. Authentication flow tests - Several authentication flows have implementation issues.
3. User verification tests - The session commit is not being called in the email verification workflow.
4. Some redirection tests - Not all expected redirections are implemented correctly yet.
5. Form validation - Some endpoints return 422 Unprocessable Entity errors for form submissions.
6. AsyncSession implementation - The 'get_by_email' attribute is missing on AsyncSession objects.

## Test Structure Details

### Fixtures

The `conftest.py` file contains several key fixtures:

- `override_get_async_session`: Creates a test database and session
- `mock_user_manager`: Creates a mock for the UserManager
- `test_user`: Creates a test user in the database
- `client`: Creates a FastAPI TestClient

### Mock Strategy

The tests use a combination of:

1. Patching dependencies with unittest.mock
2. Creating mock objects for external dependencies
3. Using xfail markers for tests that depend on unimplemented features

### Database Testing

The tests use an in-memory SQLite database for testing database interactions instead of the production database:

```python
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
```

## Improving Test Coverage

To improve test coverage:

1. Implement missing routes and dependencies
2. Add more test cases for edge scenarios
3. Fix the xfailed tests as implementation progresses
4. Add integration tests that cover the full user flow

## Authentication Testing

Special attention is needed for authentication testing:

1. JWT token generation and validation
2. OAuth authentication flows
3. User registration and verification
4. Password reset functionality