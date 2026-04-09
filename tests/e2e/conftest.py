"""Pytest configuration for end-to-end browser tests."""

import asyncio
import subprocess
import time
from typing import AsyncIterator, Iterator

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="session")
def streamlit_server():
    """Start Streamlit server for testing."""
    import os

    # Change to project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    # Start the Streamlit server
    process = subprocess.Popen(
        [
            "uv",
            "run",
            "streamlit",
            "run",
            "streamlit_app/app.py",
            "--server.headless",
            "true",
            "--server.port",
            "8501",
            "--server.address",
            "localhost",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=project_root,
    )

    # Wait for server to start (check for "You can now view" message)
    max_wait = 30  # seconds
    start_time = time.time()
    server_ready = False

    while time.time() - start_time < max_wait:
        if process.poll() is not None:
            # Process terminated
            stdout, stderr = process.communicate()
            pytest.fail(f"Streamlit server failed to start.\nStdout: {stdout}\nStderr: {stderr}")

        # Check if server is ready by attempting to connect
        try:
            import requests

            response = requests.get("http://localhost:8501/_stcore/health", timeout=1)
            if response.status_code == 200:
                server_ready = True
                break
        except Exception:
            pass

        time.sleep(0.5)

    if not server_ready:
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        pytest.fail(
            f"Streamlit server did not start within timeout.\nStdout: {stdout}\nStderr: {stderr}"
        )

    # Give it a bit more time to fully initialize
    time.sleep(2)

    yield "http://localhost:8501"

    # Cleanup
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.fixture
def streamlit_page(page: Page, streamlit_server: str):
    """Navigate to Streamlit app and return page object."""

    # Set up console message listener for debugging
    def handle_console(msg):
        print(f"Browser console [{msg.type}]: {msg.text}")

    page.on("console", handle_console)

    # Set up page error listener
    def handle_page_error(error):
        print(f"Browser page error: {error}")

    page.on("pageerror", handle_page_error)

    page.goto(streamlit_server)

    # Wait for Streamlit to finish loading
    # Streamlit apps typically have a "stApp" class when ready
    try:
        page.wait_for_selector("[data-testid='stApp']", timeout=10000)
    except Exception:
        # Fallback to network idle
        page.wait_for_load_state("networkidle", timeout=10000)

    # Additional wait for dynamic content
    page.wait_for_timeout(5000)

    # Wait for actual content to appear (not just the app shell)
    try:
        page.wait_for_selector("h1", timeout=5000)
    except Exception:
        pass  # Continue even if h1 doesn't appear

    return page


@pytest.fixture
def expect_helper():
    """Return Playwright expect helper for assertions."""
    return expect
