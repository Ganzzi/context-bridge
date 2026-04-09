# Python Testing Guide

A comprehensive guide to testing Python applications, covering unit testing, integration testing, best practices, and essential tools.

---

## 🧩 1. Testing Overview

### **What is Testing?**

Testing is the process of verifying that your code works as expected. It's a critical practice in software development that:

- **Detects bugs early** in the development cycle
- **Ensures changes don't break existing features** (regression prevention)
- **Makes refactoring safer** by providing confidence in code changes
- **Serves as living documentation** of expected behavior
- **Improves code design** by encouraging modular, testable code

### **Two Common Levels of Testing**

| Type                 | Purpose                                   | Scope                 | Example                                  |
| -------------------- | ----------------------------------------- | --------------------- | ---------------------------------------- |
| **Unit Test**        | Test one function or class in isolation   | Smallest part of code | Test `add(a,b)` returns correct sum      |
| **Integration Test** | Test multiple components working together | Larger system         | Test `UserService` + `Database` together |

### **Testing Pyramid**

```
        /\
       /  \
      / UI \          ← Few, slow, expensive
     /------\
    /        \
   /Integration\     ← Moderate number
  /------------\
 /              \
/   Unit Tests   \   ← Many, fast, cheap
------------------
```

---

## 🧱 2. Unit Testing in Python

### **Definition**

Unit tests verify that individual "units" (functions, methods, or classes) behave correctly — **in isolation**. They should:

- Run quickly (milliseconds)
- Be independent of external systems
- Test a single behavior or functionality
- Be repeatable and deterministic

### **Frameworks**

* ✅ Built-in: `unittest` (Python's standard library)
* 🌟 Popular alternative: `pytest` (more pythonic, better features)

---

### **Example: `unittest`**

The `unittest` framework is built into Python and follows the xUnit style.

**Code to test:**

```python
# calculator.py
def add(a, b):
    """Add two numbers together."""
    return a + b

def subtract(a, b):
    """Subtract b from a."""
    return a - b

def divide(a, b):
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
```

**Test file:**

```python
# test_calculator.py
import unittest
from calculator import add, subtract, divide

class TestCalculator(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(0, 0), 0)
    
    def test_subtract(self):
        self.assertEqual(subtract(5, 3), 2)
        self.assertEqual(subtract(0, 5), -5)
    
    def test_divide(self):
        self.assertEqual(divide(10, 2), 5)
        self.assertAlmostEqual(divide(7, 3), 2.333, places=3)
    
    def test_divide_by_zero(self):
        with self.assertRaises(ValueError):
            divide(10, 0)

if __name__ == '__main__':
    unittest.main()
```

**Run:**

```bash
python -m unittest test_calculator.py
```

**Common `unittest` assertions:**

```python
self.assertEqual(a, b)          # a == b
self.assertNotEqual(a, b)       # a != b
self.assertTrue(x)              # bool(x) is True
self.assertFalse(x)             # bool(x) is False
self.assertIs(a, b)             # a is b
self.assertIsNone(x)            # x is None
self.assertIn(a, b)             # a in b
self.assertIsInstance(a, b)     # isinstance(a, b)
self.assertRaises(exc, func)    # func raises exc
```

---

### **Using pytest**

Pytest offers simpler syntax, better error output, and powerful features with less boilerplate.

**Installation:**

```bash
pip install pytest
```

**Simple test:**

```python
# test_calculator_pytest.py
from calculator import add, subtract, divide
import pytest

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0

def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(0, 5) == -5

def test_divide():
    assert divide(10, 2) == 5
    assert abs(divide(7, 3) - 2.333) < 0.001

def test_divide_by_zero():
    with pytest.raises(ValueError):
        divide(10, 0)
```

**Run:**

```bash
# Run all tests
pytest

# Run specific file
pytest test_calculator_pytest.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=calculator
```

---

### **Pytest Fixtures**

Fixtures provide a way to set up test data and resources that can be reused across tests.

```python
import pytest

@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {
        'users': [
            {'id': 1, 'name': 'Alice'},
            {'id': 2, 'name': 'Bob'}
        ]
    }

@pytest.fixture
def database_connection():
    """Setup and teardown database connection."""
    conn = create_connection()  # Setup
    yield conn
    conn.close()  # Teardown

def test_user_count(sample_data):
    assert len(sample_data['users']) == 2

def test_user_names(sample_data):
    names = [u['name'] for u in sample_data['users']]
    assert 'Alice' in names
    assert 'Bob' in names
```

**Fixture scopes:**

```python
@pytest.fixture(scope="function")  # Default: runs for each test
@pytest.fixture(scope="class")     # Runs once per test class
@pytest.fixture(scope="module")    # Runs once per module
@pytest.fixture(scope="session")   # Runs once per test session
```

---

### **Mocking in Unit Tests**

Mocks simulate external systems (like databases, APIs, or file systems) to keep tests isolated and fast.

**Using `unittest.mock`:**

```python
from unittest.mock import patch, Mock, MagicMock
import requests

# Code to test
def get_user(user_id):
    """Fetch user from external API."""
    response = requests.get(f"https://api.example.com/users/{user_id}")
    return response.json()

def send_welcome_email(user_id):
    """Send email to user."""
    user = get_user(user_id)
    email_service.send(user['email'], 'Welcome!')
    return True

# Tests
@patch('requests.get')
def test_get_user(mock_get):
    # Mock the response
    mock_response = Mock()
    mock_response.json.return_value = {'id': 1, 'name': 'Alice', 'email': 'alice@example.com'}
    mock_get.return_value = mock_response
    
    result = get_user(1)
    
    assert result['name'] == 'Alice'
    mock_get.assert_called_once_with('https://api.example.com/users/1')

@patch('email_service.send')
@patch('mymodule.get_user')
def test_send_welcome_email(mock_get_user, mock_send):
    mock_get_user.return_value = {'email': 'alice@example.com'}
    
    result = send_welcome_email(1)
    
    assert result is True
    mock_send.assert_called_once_with('alice@example.com', 'Welcome!')
```

**Pytest-mock plugin:**

```bash
pip install pytest-mock
```

```python
def test_get_user(mocker):
    mock_get = mocker.patch('requests.get')
    mock_get.return_value.json.return_value = {'name': 'Alice'}
    
    result = get_user(1)
    assert result['name'] == 'Alice'
```

---

### **Parametrized Tests**

Test the same function with multiple inputs efficiently.

```python
import pytest

@pytest.mark.parametrize("a,b,expected", [
    (2, 3, 5),
    (0, 0, 0),
    (-1, 1, 0),
    (100, -50, 50),
])
def test_add_parametrized(a, b, expected):
    assert add(a, b) == expected

@pytest.mark.parametrize("a,b", [
    (10, 0),
    (5, 0),
    (-3, 0),
])
def test_divide_by_zero_parametrized(a, b):
    with pytest.raises(ValueError):
        divide(a, b)
```

---

## 🧠 3. Integration Testing in Python

### **Definition**

Integration tests verify that **multiple parts of your application work together** correctly, including:

- Service + Database interactions
- API endpoints + business logic
- External service integrations
- Configuration and dependency injection

### **Goal**

Integration tests check:

- ✅ Data flows correctly between components
- ✅ Configuration and dependencies are compatible
- ✅ Interfaces between modules work as expected
- ✅ External systems integrate properly

### **Differences from Unit Tests**

| Aspect        | Unit Tests                | Integration Tests           |
| ------------- | ------------------------- | --------------------------- |
| **Scope**     | Single function/class     | Multiple components         |
| **Speed**     | Very fast (ms)            | Slower (seconds)            |
| **Isolation** | Fully isolated with mocks | Real or test dependencies   |
| **Failures**  | Pinpoint exact issue      | May need debugging          |
| **Setup**     | Minimal                   | Requires environment setup  |

---

### **Example: Flask App Integration Test**

**Application code:**

```python
# app.py
from flask import Flask, jsonify, request
app = Flask(__name__)

# In-memory storage for demo
users = {}
next_id = 1

@app.route('/ping')
def ping():
    return jsonify({'status': 'ok'})

@app.route('/users', methods=['POST'])
def create_user():
    global next_id
    data = request.json
    user = {'id': next_id, 'name': data['name']}
    users[next_id] = user
    next_id += 1
    return jsonify(user), 201

@app.route('/users/<int:user_id>')
def get_user(user_id):
    user = users.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user)

if __name__ == '__main__':
    app.run()
```

**Integration tests:**

```python
# test_app_integration.py
import pytest
from app import app

@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture(autouse=True)
def reset_data():
    """Reset data before each test."""
    from app import users, next_id
    users.clear()
    app.next_id = 1

def test_ping(client):
    """Test health check endpoint."""
    res = client.get('/ping')
    assert res.status_code == 200
    assert res.json == {'status': 'ok'}

def test_create_and_get_user(client):
    """Test creating a user and retrieving it."""
    # Create user
    create_res = client.post('/users', json={'name': 'Alice'})
    assert create_res.status_code == 201
    assert create_res.json['name'] == 'Alice'
    user_id = create_res.json['id']
    
    # Get user
    get_res = client.get(f'/users/{user_id}')
    assert get_res.status_code == 200
    assert get_res.json['name'] == 'Alice'

def test_get_nonexistent_user(client):
    """Test getting a user that doesn't exist."""
    res = client.get('/users/999')
    assert res.status_code == 404
    assert 'error' in res.json
```

**Run:**

```bash
pytest test_app_integration.py -v
```

---

### **Integration Test Example with Database**

**Using SQLite for testing:**

```python
# db_integration_test.py
import sqlite3
import pytest

@pytest.fixture
def db_connection(tmp_path):
    """Create a temporary database for testing."""
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(db_file)
    yield conn
    conn.close()

def create_user_table(conn):
    """Create users table."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL
        )
    """)
    conn.commit()

def insert_user(conn, name, email):
    """Insert a new user."""
    cursor = conn.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        (name, email)
    )
    conn.commit()
    return cursor.lastrowid

def get_user_by_id(conn, user_id):
    """Get user by ID."""
    cursor = conn.execute(
        "SELECT id, name, email FROM users WHERE id = ?",
        (user_id,)
    )
    return cursor.fetchone()

# Integration tests
def test_create_user_table(db_connection):
    """Test table creation."""
    create_user_table(db_connection)
    
    cursor = db_connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    )
    assert cursor.fetchone() is not None

def test_insert_and_retrieve_user(db_connection):
    """Test full user workflow."""
    create_user_table(db_connection)
    
    # Insert user
    user_id = insert_user(db_connection, "Alice", "alice@example.com")
    assert user_id is not None
    
    # Retrieve user
    user = get_user_by_id(db_connection, user_id)
    assert user is not None
    assert user[1] == "Alice"
    assert user[2] == "alice@example.com"

def test_unique_email_constraint(db_connection):
    """Test that email must be unique."""
    create_user_table(db_connection)
    
    insert_user(db_connection, "Alice", "alice@example.com")
    
    with pytest.raises(sqlite3.IntegrityError):
        insert_user(db_connection, "Bob", "alice@example.com")
```

---

### **Testing with PostgreSQL**

**Using a test database:**

```python
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor

@pytest.fixture(scope="session")
def test_db():
    """Setup test database connection."""
    conn = psycopg2.connect(
        dbname="test_db",
        user="test_user",
        password="test_pass",
        host="localhost"
    )
    yield conn
    conn.close()

@pytest.fixture
def clean_db(test_db):
    """Clean database before each test."""
    cursor = test_db.cursor()
    cursor.execute("TRUNCATE TABLE users CASCADE")
    test_db.commit()
    yield test_db

def test_user_service_integration(clean_db):
    """Test UserService with real database."""
    from services import UserService
    
    service = UserService(clean_db)
    
    # Create user
    user = service.create_user("Alice", "alice@example.com")
    assert user['id'] is not None
    
    # Retrieve user
    retrieved = service.get_user(user['id'])
    assert retrieved['name'] == "Alice"
```

---

### **API Integration Testing**

**Testing external API integrations:**

```python
import pytest
import responses
import requests

@responses.activate
def test_external_api_integration():
    """Test integration with external API using responses library."""
    # Mock external API
    responses.add(
        responses.GET,
        'https://api.example.com/users/1',
        json={'id': 1, 'name': 'Alice'},
        status=200
    )
    
    # Your code that calls the API
    response = requests.get('https://api.example.com/users/1')
    
    assert response.status_code == 200
    assert response.json()['name'] == 'Alice'
```

---

## 🧪 4. Best Practices

### **General Testing Principles**

| Tip                          | Description                                                      |
| ---------------------------- | ---------------------------------------------------------------- |
| ✅ **Isolate unit tests**    | Don't depend on network, database, or file system               |
| 🧱 **Integration tests**     | Use real components where possible, test databases for data flow |
| 📦 **Organize tests**        | Use clear structure: `tests/unit/`, `tests/integration/`         |
| 🧩 **Use fixtures**          | Prepare test data/environment cleanly (pytest fixtures)          |
| 🔁 **Run automatically**     | Integrate with CI/CD (GitHub Actions, GitLab CI, etc.)           |
| 📝 **Test naming**           | Use descriptive names: `test_user_creation_with_valid_email`     |
| ⚡ **Keep tests fast**       | Unit tests should run in milliseconds                            |
| 🎯 **One assertion concept** | Each test should verify one behavior                             |
| 🔄 **Keep tests independent**| Tests should not depend on each other                            |

### **Test Structure: AAA Pattern**

```python
def test_user_registration():
    # Arrange - Setup test data and conditions
    user_data = {'name': 'Alice', 'email': 'alice@example.com'}
    
    # Act - Perform the action being tested
    result = register_user(user_data)
    
    # Assert - Verify the outcome
    assert result['success'] is True
    assert result['user']['name'] == 'Alice'
```

### **Project Structure**

```
my_project/
├── src/
│   ├── __init__.py
│   ├── calculator.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── user_service.py
│   └── models/
│       └── user.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_calculator.py
│   │   └── test_user_model.py
│   └── integration/
│       ├── __init__.py
│       ├── test_user_service.py
│       └── test_api.py
├── pytest.ini                   # Pytest configuration
└── requirements-dev.txt         # Testing dependencies
```

### **Configuration: `pytest.ini`**

```ini
[tool:pytest]
# Test discovery patterns
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*

# Directories to search
testpaths = tests

# Additional options
addopts = 
    -v
    --strict-markers
    --cov=src
    --cov-report=html
    --cov-report=term-missing

# Custom markers
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow running tests
```

**Run specific test types:**

```bash
pytest -m unit                    # Run only unit tests
pytest -m integration             # Run only integration tests
pytest -m "not slow"              # Skip slow tests
```

### **Code Coverage**

**Install:**

```bash
pip install pytest-cov
```

**Run with coverage:**

```bash
# Generate coverage report
pytest --cov=src --cov-report=html

# View coverage in terminal
pytest --cov=src --cov-report=term-missing

# Fail if coverage below threshold
pytest --cov=src --cov-fail-under=80
```

---

## 🧰 5. Testing Tools Summary

### **Core Testing Frameworks**

| Tool         | Purpose                                      | Installation           |
| ------------ | -------------------------------------------- | ---------------------- |
| `unittest`   | Built-in testing framework (xUnit style)     | Built-in (no install)  |
| `pytest`     | Modern testing with simpler syntax, plugins  | `pip install pytest`   |

### **Mocking and Fixtures**

| Tool              | Purpose                                     | Installation                |
| ----------------- | ------------------------------------------- | --------------------------- |
| `unittest.mock`   | Mocking for isolation                       | Built-in (no install)       |
| `pytest-mock`     | Pytest wrapper around unittest.mock         | `pip install pytest-mock`   |
| `responses`       | Mock HTTP requests                          | `pip install responses`     |
| `freezegun`       | Mock datetime                               | `pip install freezegun`     |

### **Coverage and Reporting**

| Tool           | Purpose                              | Installation                |
| -------------- | ------------------------------------ | --------------------------- |
| `pytest-cov`   | Test coverage reporting              | `pip install pytest-cov`    |
| `coverage`     | Code coverage measurement            | `pip install coverage`      |

### **Framework-Specific Testing**

| Tool             | Purpose                              | Installation                  |
| ---------------- | ------------------------------------ | ----------------------------- |
| `pytest-flask`   | Flask integration testing            | `pip install pytest-flask`    |
| `pytest-django`  | Django integration testing           | `pip install pytest-django`   |
| `pytest-asyncio` | Testing async code                   | `pip install pytest-asyncio`  |
| `httpx`          | Async HTTP client for testing        | `pip install httpx`           |

### **Database Testing**

| Tool                 | Purpose                          | Installation                    |
| -------------------- | -------------------------------- | ------------------------------- |
| `pytest-postgresql`  | PostgreSQL fixtures              | `pip install pytest-postgresql` |
| `pytest-mongodb`     | MongoDB fixtures                 | `pip install pytest-mongodb`    |
| `factory_boy`        | Test data generation             | `pip install factory_boy`       |
| `faker`              | Generate fake data               | `pip install faker`             |

### **Other Useful Tools**

| Tool              | Purpose                          | Installation                   |
| ----------------- | -------------------------------- | ------------------------------ |
| `pytest-xdist`    | Run tests in parallel            | `pip install pytest-xdist`     |
| `pytest-timeout`  | Timeout for hanging tests        | `pip install pytest-timeout`   |
| `tox`             | Test across Python versions      | `pip install tox`              |
| `hypothesis`      | Property-based testing           | `pip install hypothesis`       |

---

## 📚 6. Advanced Topics

### **Async Testing**

```python
import pytest
import asyncio

async def fetch_data():
    await asyncio.sleep(0.1)
    return {'data': 'value'}

@pytest.mark.asyncio
async def test_fetch_data():
    result = await fetch_data()
    assert result['data'] == 'value'
```

### **Property-Based Testing with Hypothesis**

```python
from hypothesis import given
import hypothesis.strategies as st

@given(st.integers(), st.integers())
def test_add_commutative(a, b):
    """Test that addition is commutative."""
    assert add(a, b) == add(b, a)
```

### **Test Factories**

```python
import factory
from models import User

class UserFactory(factory.Factory):
    class Meta:
        model = User
    
    name = factory.Faker('name')
    email = factory.Faker('email')
    age = factory.Faker('random_int', min=18, max=100)

def test_user_creation():
    user = UserFactory()
    assert user.name is not None
    assert '@' in user.email
```

---

## 🚀 7. CI/CD Integration

### **GitHub Actions Example**

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        python-version: ['3.9', '3.10', '3.11']
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        pytest --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## 📖 8. Additional Resources

- **Pytest Documentation**: https://docs.pytest.org/
- **Python Testing with pytest** (Book by Brian Okken)
- **Test-Driven Development with Python** (Book by Harry Percival)
- **Real Python Testing Guide**: https://realpython.com/pytest-python-testing/

---

## ✅ Quick Reference

```bash
# Run all tests
pytest

# Run specific file
pytest tests/test_calculator.py

# Run specific test
pytest tests/test_calculator.py::test_add

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src

# Run in parallel
pytest -n auto

# Run only failed tests from last run
pytest --lf

# Run only unit tests (with marker)
pytest -m unit

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l
```

---

**Happy Testing! 🎉**
