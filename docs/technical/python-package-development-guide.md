# Python Package Development & Maintenance Guide

> **Version:** 1.0  
> **Last Updated:** October 9, 2025  
> **Target Audience:** Software Engineering Team

This comprehensive guide covers the complete lifecycle of Python package development, from initial setup to deployment and maintenance.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Version Control with Git & GitHub](#2-version-control-with-git--github)
3. [Package Configuration with pyproject.toml](#3-package-configuration-with-pyprojecttoml)
4. [Documentation](#4-documentation)
5. [GitHub Actions CI/CD](#5-github-actions-cicd)
6. [Containerization with Docker](#6-containerization-with-docker)
7. [Best Practices & Workflows](#7-best-practices--workflows)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Project Structure

### Standard Python Package Layout

```
my-package/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── publish.yml
├── docs/
│   ├── index.md
│   ├── getting-started.md
│   ├── api-reference.md
│   └── contributing.md
├── src/
│   └── my_package/
│       ├── __init__.py
│       ├── core.py
│       └── utils.py
├── tests/
│   ├── __init__.py
│   ├── test_core.py
│   └── test_utils.py
├── .gitignore
├── .dockerignore
├── Dockerfile
├── LICENSE
├── README.md
├── pyproject.toml
├── mkdocs.yml
└── CHANGELOG.md
```

### Key Directories

- **`src/`**: Source code using the "src layout" (recommended for better isolation)
- **`tests/`**: Test files using pytest
- **`docs/`**: Documentation source files for MkDocs
- **`.github/workflows/`**: GitHub Actions workflow definitions
- **`scripts/`**: Utility scripts for development

---

## 2. Version Control with Git & GitHub

### 2.1 Git Workflow

#### Branching Strategy

We follow **Git Flow** with simplified conventions:

```
main (production-ready)
  ├── develop (integration branch)
  │   ├── feature/add-new-api
  │   ├── feature/improve-performance
  │   ├── bugfix/fix-memory-leak
  │   └── hotfix/critical-security-patch
```

#### Branch Naming Conventions

- **Feature branches:** `feature/<short-description>`
- **Bug fixes:** `bugfix/<issue-number>-<description>`
- **Hotfixes:** `hotfix/<issue-number>-<description>`
- **Release branches:** `release/v<version>`

### 2.2 Commit Message Guidelines

Follow **Conventional Commits**:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements
- `ci`: CI/CD changes

**Examples:**

```bash
feat(api): add user authentication endpoint

Implement JWT-based authentication with refresh tokens.
Includes middleware for protected routes.

Closes #123
```

```bash
fix(parser): handle edge case with empty strings

Previously crashed when receiving empty input.
Now returns appropriate error message.
```

### 2.3 Common Git Commands

```bash
# Clone repository
git clone https://github.com/organization/my-package.git
cd my-package

# Create and switch to a new branch
git checkout -b feature/my-new-feature

# Stage and commit changes
git add .
git commit -m "feat(module): add new functionality"

# Push to remote
git push origin feature/my-new-feature

# Update your branch with latest main
git checkout main
git pull origin main
git checkout feature/my-new-feature
git merge main

# Or use rebase (cleaner history)
git rebase main
```

### 2.4 GitHub Workflow

#### Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make Changes and Commit**
   ```bash
   git add .
   git commit -m "feat: implement new feature"
   ```

3. **Push to GitHub**
   ```bash
   git push origin feature/my-feature
   ```

4. **Create Pull Request**
   - Go to GitHub repository
   - Click "New Pull Request"
   - Select your branch
   - Fill in PR template
   - Request reviewers

5. **Code Review**
   - Address reviewer comments
   - Push additional commits if needed
   - Ensure CI checks pass

6. **Merge**
   - Squash and merge (recommended for clean history)
   - Delete branch after merge

#### GitHub Repository Settings

**Branch Protection Rules** (for `main` branch):
- ✅ Require pull request reviews (minimum 1)
- ✅ Require status checks to pass
- ✅ Require branches to be up to date
- ✅ Include administrators
- ✅ Restrict force pushes

### 2.5 .gitignore Template

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environments
venv/
env/
ENV/
.venv

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Documentation
docs/_build/
site/

# Docker
*.log
docker-compose.override.yml

# OS
.DS_Store
Thumbs.db

# Environment
.env
.env.local
```

### 2.6 Tagging and Releases

```bash
# Create annotated tag for release
git tag -a v1.0.0 -m "Release version 1.0.0"

# Push tag to remote
git push origin v1.0.0

# List all tags
git tag -l

# Delete tag (if needed)
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0
```

---

## 3. Package Configuration with pyproject.toml

### 3.1 Modern Python Packaging

`pyproject.toml` is the modern standard (PEP 517, 518, 621) replacing `setup.py` and `setup.cfg`.

### 3.2 Complete pyproject.toml Template

```toml
[build-system]
requires = ["hatchling>=1.21.0"]
build-backend = "hatchling.build"

[project]
name = "my-package"
version = "0.1.0"
description = "A comprehensive Python package"
readme = "README.md"
license = { text = "MIT" }
authors = [
    { name = "Your Team", email = "team@example.com" }
]
maintainers = [
    { name = "Lead Developer", email = "lead@example.com" }
]
keywords = ["python", "package", "example"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Python Modules",
]
requires-python = ">=3.10"
dependencies = [
    "requests>=2.31.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.5.0",
    "pre-commit>=3.3.0",
]
docs = [
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.4.0",
    "mkdocstrings[python]>=0.24.0",
]
test = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "coverage[toml]>=7.3.0",
]

[project.urls]
Homepage = "https://github.com/organization/my-package"
Documentation = "https://my-package.readthedocs.io"
Repository = "https://github.com/organization/my-package"
"Bug Tracker" = "https://github.com/organization/my-package/issues"
Changelog = "https://github.com/organization/my-package/blob/main/CHANGELOG.md"

[project.scripts]
my-cli = "my_package.cli:main"

# Tool configurations

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "--cov=my_package",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-report=xml",
]

[tool.coverage.run]
source = ["my_package"]
omit = ["*/tests/*", "*/test_*.py"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]

[tool.black]
line-length = 100
target-version = ["py310", "py311", "py312"]
include = '\.pyi?$'

[tool.ruff]
line-length = 100
target-version = "py310"
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "C",   # flake8-comprehensions
    "B",   # flake8-bugbear
    "UP",  # pyupgrade
]
ignore = [
    "E501",  # line too long (handled by black)
    "B008",  # do not perform function calls in argument defaults
    "C901",  # too complex
]

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]  # imported but unused

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
strict_equality = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

### 3.3 Version Management

#### Semantic Versioning (SemVer)

Format: `MAJOR.MINOR.PATCH` (e.g., `1.2.3`)

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

**Examples:**
- `1.0.0` → `1.0.1`: Bug fix
- `1.0.1` → `1.1.0`: New feature added
- `1.1.0` → `2.0.0`: Breaking API change

#### Dynamic Versioning

Use `hatch-vcs` or `setuptools-scm` for automatic versioning from git tags:

```toml
[build-system]
requires = ["hatchling>=1.21.0", "hatch-vcs>=0.3.0"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "vcs"

[tool.hatch.build.hooks.vcs]
version-file = "src/my_package/_version.py"
```

### 3.4 Package Installation

```bash
# Install in editable mode for development
pip install -e .

# Install with optional dependencies
pip install -e ".[dev]"
pip install -e ".[dev,docs,test]"

# Install from git repository
pip install git+https://github.com/organization/my-package.git

# Install specific version
pip install my-package==1.2.3
```

---

## 4. Documentation

### 4.1 README.md

A great README is the first impression. Include:

```markdown
# My Package

[![CI](https://github.com/org/my-package/workflows/CI/badge.svg)](https://github.com/org/my-package/actions)
[![codecov](https://codecov.io/gh/org/my-package/branch/main/graph/badge.svg)](https://codecov.io/gh/org/my-package)
[![PyPI](https://img.shields.io/pypi/v/my-package.svg)](https://pypi.org/project/my-package/)
[![Python Version](https://img.shields.io/pypi/pyversions/my-package.svg)](https://pypi.org/project/my-package/)
[![License](https://img.shields.io/github/license/org/my-package.svg)](https://github.com/org/my-package/blob/main/LICENSE)

One-line description of what your package does.

## Features

- 🚀 Feature 1
- 🔧 Feature 2
- 📦 Feature 3

## Installation

```bash
pip install my-package
```

## Quick Start

```python
from my_package import MyClass

# Example usage
obj = MyClass()
result = obj.do_something()
print(result)
```

## Documentation

Full documentation is available at [https://my-package.readthedocs.io](https://my-package.readthedocs.io)

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/org/my-package.git
cd my-package

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
black src tests

# Lint
ruff check src tests

# Type check
mypy src
```

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file.

## Authors

- Your Team (team@example.com)

## Acknowledgments

- Thanks to contributors
- Inspired by XYZ project
```

### 4.2 LICENSE

#### MIT License Template

```text
MIT License

Copyright (c) 2025 Your Organization

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Common licenses:**
- **MIT**: Permissive, allows commercial use
- **Apache 2.0**: Permissive with patent grant
- **GPL-3.0**: Copyleft, derivative works must be open source
- **BSD-3-Clause**: Permissive, similar to MIT

### 4.3 MkDocs Documentation

#### Installation

```bash
pip install mkdocs mkdocs-material mkdocstrings[python]
```

#### mkdocs.yml Configuration

```yaml
site_name: My Package Documentation
site_description: Comprehensive documentation for My Package
site_author: Your Team
site_url: https://my-package.readthedocs.io

repo_name: organization/my-package
repo_url: https://github.com/organization/my-package
edit_uri: edit/main/docs/

theme:
  name: material
  palette:
    # Light mode
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    # Dark mode
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - navigation.top
    - search.suggest
    - search.highlight
    - content.code.copy
    - content.code.annotate

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            docstring_style: google
            show_source: true
            show_root_heading: true
            show_category_heading: true
            show_if_no_docstring: false

markdown_extensions:
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.superfences
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - pymdownx.tabbed:
      alternate_style: true
  - admonition
  - pymdownx.details
  - pymdownx.emoji:
      emoji_index: !!python/name:material.extensions.emoji.twemoji
      emoji_generator: !!python/name:material.extensions.emoji.to_svg
  - toc:
      permalink: true

nav:
  - Home: index.md
  - Getting Started:
      - Installation: getting-started/installation.md
      - Quick Start: getting-started/quickstart.md
      - Configuration: getting-started/configuration.md
  - User Guide:
      - Basic Usage: user-guide/basic-usage.md
      - Advanced Features: user-guide/advanced.md
      - Examples: user-guide/examples.md
  - API Reference:
      - Core Module: api/core.md
      - Utils Module: api/utils.md
  - Development:
      - Contributing: development/contributing.md
      - Architecture: development/architecture.md
      - Testing: development/testing.md
  - Changelog: changelog.md
```

#### Documentation Structure

```
docs/
├── index.md                    # Homepage
├── getting-started/
│   ├── installation.md
│   ├── quickstart.md
│   └── configuration.md
├── user-guide/
│   ├── basic-usage.md
│   ├── advanced.md
│   └── examples.md
├── api/
│   ├── core.md
│   └── utils.md
├── development/
│   ├── contributing.md
│   ├── architecture.md
│   └── testing.md
└── changelog.md
```

#### API Documentation with mkdocstrings

Create `docs/api/core.md`:

```markdown
# Core Module

::: my_package.core
    options:
      show_root_heading: true
      show_source: true
```

This automatically generates documentation from docstrings.

#### MkDocs Commands

```bash
# Serve documentation locally
mkdocs serve

# Build static documentation
mkdocs build

# Deploy to GitHub Pages
mkdocs gh-deploy
```

### 4.4 Docstring Standards

Use **Google Style** docstrings:

```python
def calculate_sum(a: int, b: int, verbose: bool = False) -> int:
    """Calculate the sum of two numbers.

    This function takes two integers and returns their sum.
    Optionally prints the operation if verbose is True.

    Args:
        a: The first number to add.
        b: The second number to add.
        verbose: If True, print the calculation. Defaults to False.

    Returns:
        The sum of a and b.

    Raises:
        TypeError: If inputs are not integers.
        ValueError: If inputs are negative.

    Example:
        >>> calculate_sum(2, 3)
        5
        >>> calculate_sum(2, 3, verbose=True)
        Calculating: 2 + 3
        5

    Note:
        This is a simple example function for demonstration.

    Warning:
        Large numbers may cause overflow.
    """
    if verbose:
        print(f"Calculating: {a} + {b}")
    return a + b
```

### 4.5 CHANGELOG.md

Follow [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New feature X for handling Y

### Changed
- Improved performance of function Z

### Deprecated
- Old API endpoint will be removed in v2.0.0

### Removed
- Removed deprecated function from v0.x

### Fixed
- Fixed bug where X caused Y

### Security
- Fixed vulnerability in dependency XYZ

## [1.0.0] - 2025-10-01

### Added
- Initial stable release
- Core functionality
- Full test coverage
- Complete documentation

## [0.2.0] - 2025-09-15

### Added
- Feature A
- Feature B

### Fixed
- Bug in module C

## [0.1.0] - 2025-09-01

### Added
- Initial release
- Basic functionality

[Unreleased]: https://github.com/org/my-package/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/org/my-package/compare/v0.2.0...v1.0.0
[0.2.0]: https://github.com/org/my-package/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/org/my-package/releases/tag/v0.1.0
```

---

## 5. GitHub Actions CI/CD

### 5.1 Continuous Integration Workflow

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ["3.10", "3.11", "3.12"]

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
        cache: 'pip'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev,test]"

    - name: Lint with ruff
      run: ruff check src tests

    - name: Format check with black
      run: black --check src tests

    - name: Type check with mypy
      run: mypy src

    - name: Run tests with pytest
      run: pytest --cov --cov-report=xml --cov-report=term

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v4
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-${{ matrix.os }}-py${{ matrix.python-version }}
        fail_ci_if_error: false

  docs:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"

    - name: Install dependencies
      run: |
        pip install -e ".[docs]"

    - name: Build documentation
      run: mkdocs build --strict
```

### 5.2 Publish to PyPI Workflow

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"

    - name: Install build tools
      run: |
        python -m pip install --upgrade pip
        pip install build twine

    - name: Build package
      run: python -m build

    - name: Check package
      run: twine check dist/*

    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: twine upload dist/*
```

**Setup:**
1. Go to [PyPI](https://pypi.org/) and create an API token
2. Add token to GitHub Secrets as `PYPI_API_TOKEN`
3. Create a release on GitHub to trigger publishing

### 5.3 Deploy Documentation Workflow

Create `.github/workflows/docs.yml`:

```yaml
name: Deploy Documentation

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      with:
        fetch-depth: 0  # Fetch all history for git info

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"

    - name: Install dependencies
      run: |
        pip install -e ".[docs]"

    - name: Deploy to GitHub Pages
      run: mkdocs gh-deploy --force
```

---

## 6. Containerization with Docker

### 6.1 Dockerfile

Create a multi-stage Dockerfile for efficiency:

```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./
COPY src/ ./src/

# Install package
RUN pip install --user --no-cache-dir -e .

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy only necessary files from builder
COPY --from=builder /root/.local /root/.local
COPY --from=builder /app /app

# Make sure scripts are in PATH
ENV PATH=/root/.local/bin:$PATH

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose port if needed
EXPOSE 8000

# Run application
CMD ["python", "-m", "my_package"]
```

### 6.2 .dockerignore

```dockerignore
# Git
.git
.gitignore
.github

# Python
__pycache__
*.py[cod]
*$py.class
*.so
.Python
*.egg-info
dist/
build/

# Virtual environments
venv/
env/
.venv

# Testing
.pytest_cache
.coverage
htmlcov/
.tox/

# Documentation
docs/
site/
*.md

# IDE
.vscode
.idea
*.swp

# Docker
Dockerfile
.dockerignore
docker-compose*.yml

# CI/CD
.github/

# Misc
*.log
.DS_Store
```

### 6.3 docker-compose.yml

```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: my-package-app
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=INFO
    env_file:
      - .env
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    networks:
      - app-network

  # Optional: Add dependent services
  postgres:
    image: postgres:15-alpine
    container_name: my-package-db
    environment:
      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: mypassword
      POSTGRES_DB: mydb
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - app-network

networks:
  app-network:
    driver: bridge

volumes:
  postgres-data:
```

### 6.4 Docker Commands

```bash
# Build image
docker build -t my-package:latest .

# Run container
docker run -d -p 8000:8000 --name my-app my-package:latest

# View logs
docker logs my-app

# Execute command in container
docker exec -it my-app bash

# Stop and remove container
docker stop my-app
docker rm my-app

# Using docker-compose
docker-compose up -d
docker-compose logs -f
docker-compose down

# Build without cache
docker-compose build --no-cache

# Scale services
docker-compose up -d --scale app=3
```

### 6.5 Docker Best Practices

1. **Use specific base images**: `python:3.11-slim` instead of `python:latest`
2. **Multi-stage builds**: Reduce final image size
3. **Layer caching**: Order commands from least to most frequently changing
4. **Security**: Run as non-root user
5. **Health checks**: Add health check endpoints
6. **Environment variables**: Never hardcode secrets
7. **Volume mounts**: Persist data outside containers
8. **Networking**: Use Docker networks for service communication

---

## 7. Best Practices & Workflows

### 7.1 Development Workflow

#### Daily Development

```bash
# 1. Update from main
git checkout main
git pull origin main

# 2. Create feature branch
git checkout -b feature/my-feature

# 3. Make changes and test frequently
pytest

# 4. Check code quality before committing
black src tests
ruff check src tests
mypy src

# 5. Commit with meaningful messages
git add .
git commit -m "feat(module): add new feature"

# 6. Push and create PR
git push origin feature/my-feature
```

#### Pre-commit Hooks

Install pre-commit for automatic checks:

```bash
pip install pre-commit
```

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-json
      - id: check-toml
      - id: detect-private-key

  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
```

Install hooks:

```bash
pre-commit install
```

### 7.2 Testing Strategy

#### Test Structure

```python
# tests/test_core.py
import pytest
from my_package.core import MyClass


class TestMyClass:
    """Test suite for MyClass."""

    @pytest.fixture
    def instance(self):
        """Create MyClass instance for testing."""
        return MyClass(config="test")

    def test_initialization(self, instance):
        """Test that instance initializes correctly."""
        assert instance is not None
        assert instance.config == "test"

    def test_do_something(self, instance):
        """Test do_something method."""
        result = instance.do_something(input_data="test")
        assert result == "expected_output"

    def test_error_handling(self, instance):
        """Test that errors are handled properly."""
        with pytest.raises(ValueError):
            instance.do_something(input_data=None)

    @pytest.mark.parametrize("input,expected", [
        ("a", "A"),
        ("b", "B"),
        ("c", "C"),
    ])
    def test_multiple_inputs(self, instance, input, expected):
        """Test with multiple input values."""
        assert instance.process(input) == expected
```

#### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=my_package --cov-report=html

# Run specific test file
pytest tests/test_core.py

# Run specific test
pytest tests/test_core.py::TestMyClass::test_initialization

# Run with markers
pytest -m "not slow"

# Verbose output
pytest -v

# Stop at first failure
pytest -x
```

### 7.3 Code Quality Tools

#### Configuration Summary

| Tool | Purpose | Config Location |
|------|---------|----------------|
| **black** | Code formatting | `pyproject.toml` |
| **ruff** | Linting (replaces flake8, isort) | `pyproject.toml` |
| **mypy** | Static type checking | `pyproject.toml` |
| **pytest** | Testing framework | `pyproject.toml` |
| **coverage** | Code coverage | `pyproject.toml` |

#### Running All Checks

```bash
# Format code
black src tests

# Lint
ruff check src tests --fix

# Type check
mypy src

# Run tests with coverage
pytest --cov --cov-report=term --cov-report=html
```

### 7.4 Release Process

#### Step-by-Step Release

1. **Update CHANGELOG.md**
   ```markdown
   ## [1.2.0] - 2025-10-09
   ### Added
   - New feature X
   ### Fixed
   - Bug in module Y
   ```

2. **Update version in pyproject.toml**
   ```toml
   [project]
   version = "1.2.0"
   ```

3. **Commit changes**
   ```bash
   git add CHANGELOG.md pyproject.toml
   git commit -m "chore: bump version to 1.2.0"
   git push origin main
   ```

4. **Create git tag**
   ```bash
   git tag -a v1.2.0 -m "Release version 1.2.0"
   git push origin v1.2.0
   ```

5. **Create GitHub Release**
   - Go to GitHub repository
   - Click "Releases" → "Draft a new release"
   - Select tag `v1.2.0`
   - Copy changelog content
   - Publish release

6. **Verify Deployment**
   - Check GitHub Actions ran successfully
   - Verify package on PyPI
   - Test installation: `pip install my-package==1.2.0`

### 7.5 Team Collaboration

#### Code Review Checklist

**For Author:**
- ✅ Code follows style guide
- ✅ All tests pass
- ✅ New tests added for new features
- ✅ Documentation updated
- ✅ CHANGELOG.md updated
- ✅ No debugging code left
- ✅ PR description clear and complete

**For Reviewer:**
- ✅ Code is readable and maintainable
- ✅ Logic is sound
- ✅ Edge cases handled
- ✅ Tests are comprehensive
- ✅ No security vulnerabilities
- ✅ Performance considerations addressed
- ✅ Documentation is clear

#### Communication

- **GitHub Issues**: Bug reports, feature requests
- **Pull Requests**: Code changes with discussion
- **GitHub Discussions**: General questions and ideas
- **Wiki**: Additional documentation
- **Project Board**: Task tracking and sprint planning

---

## 8. Troubleshooting

### 8.1 Common Issues

#### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'my_package'`

**Solution:**
```bash
# Ensure installed in editable mode
pip install -e .

# Verify installation
pip list | grep my-package

# Check PYTHONPATH
python -c "import sys; print(sys.path)"
```

#### Git Merge Conflicts

**Problem:** Conflicts when merging branches

**Solution:**
```bash
# Update your branch with main
git checkout feature/my-feature
git fetch origin
git merge origin/main

# Resolve conflicts in your editor
# After resolving:
git add .
git commit -m "merge: resolve conflicts with main"
git push
```

#### Docker Build Failures

**Problem:** Docker build fails with dependency errors

**Solution:**
```bash
# Clear Docker cache
docker builder prune -a

# Build with no cache
docker build --no-cache -t my-package:latest .

# Check logs
docker logs <container-id>
```

#### Test Failures in CI

**Problem:** Tests pass locally but fail in CI

**Solution:**
- Check Python version consistency
- Verify environment variables
- Check OS-specific issues (paths, line endings)
- Review CI logs carefully
- Run tests in Docker locally to simulate CI

### 8.2 Performance Tips

1. **Use virtual environments**: Isolate dependencies
2. **Cache dependencies**: In CI and Docker
3. **Parallel testing**: Use `pytest-xdist`
4. **Incremental builds**: With Docker layer caching
5. **Selective CI**: Only run relevant workflows

### 8.3 Security Considerations

- **Never commit secrets**: Use `.env` files (gitignored)
- **Use environment variables**: For sensitive configuration
- **Dependency scanning**: Use Dependabot or similar
- **Code scanning**: Enable GitHub security features
- **Regular updates**: Keep dependencies up to date
- **Access control**: Use branch protection rules

---

## Appendix

### A. Useful Commands Reference

```bash
# Git
git clone <url>                    # Clone repository
git checkout -b <branch>           # Create new branch
git add .                          # Stage all changes
git commit -m "message"            # Commit changes
git push origin <branch>           # Push to remote
git pull origin main               # Pull from main
git tag -a v1.0.0 -m "message"    # Create tag

# Python Package
pip install -e .                   # Install editable
pip install -e ".[dev]"            # Install with extras
python -m build                    # Build package
twine upload dist/*                # Upload to PyPI

# Testing
pytest                             # Run tests
pytest --cov                       # With coverage
pytest -v                          # Verbose
pytest -x                          # Stop at first failure
pytest -k "test_name"              # Run specific test

# Code Quality
black src tests                    # Format code
ruff check src tests               # Lint
mypy src                           # Type check

# Documentation
mkdocs serve                       # Serve locally
mkdocs build                       # Build docs
mkdocs gh-deploy                   # Deploy to GitHub Pages

# Docker
docker build -t name:tag .         # Build image
docker run -d -p 8000:8000 name    # Run container
docker logs <container>            # View logs
docker exec -it <container> bash   # Enter container
docker-compose up -d               # Start services
docker-compose down                # Stop services
```

### B. Helpful Resources

- [Python Packaging Guide](https://packaging.python.org/)
- [PEP 517 – Build System](https://peps.python.org/pep-0517/)
- [PEP 621 – Project Metadata](https://peps.python.org/pep-0621/)
- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Documentation](https://docs.docker.com/)
- [pytest Documentation](https://docs.pytest.org/)

### C. Template Repository Checklist

When starting a new package, ensure you have:

- [ ] `pyproject.toml` configured
- [ ] `README.md` with badges and examples
- [ ] `LICENSE` file
- [ ] `.gitignore` for Python
- [ ] `.github/workflows/ci.yml`
- [ ] `tests/` directory with initial tests
- [ ] `docs/` directory with MkDocs
- [ ] `mkdocs.yml` configured
- [ ] `.pre-commit-config.yaml`
- [ ] `CHANGELOG.md`
- [ ] `CONTRIBUTING.md`
- [ ] `Dockerfile` and `.dockerignore`
- [ ] `docker-compose.yml` (if needed)
- [ ] Branch protection rules on GitHub
- [ ] GitHub secrets configured (PyPI token)

---

**Document Version:** 1.0  
**Last Updated:** October 9, 2025  
**Maintained By:** Software Engineering Team

For questions or suggestions, please open an issue or contact the team.
