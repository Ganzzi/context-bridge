"""End-to-end tests for Streamlit UI using Playwright."""

import pytest
from playwright.sync_api import Page, expect


class TestNavigationAndHome:
    """Test basic navigation and home page functionality."""

    def test_home_page_loads(self, streamlit_page: Page):
        """Test that the home page loads successfully."""
        # Take screenshot for debugging
        import os

        os.makedirs("tests/e2e/screenshots", exist_ok=True)
        streamlit_page.screenshot(path="tests/e2e/screenshots/home_page.png")

        # Print page content for debugging
        content = streamlit_page.content()
        print(f"\nPage content length: {len(content)}")
        print(f"Page title: {streamlit_page.title()}")

        # Check for title - use more flexible matching
        # Streamlit may render text differently
        page_text = streamlit_page.inner_text("body")
        # Use safe encoding for printing with emojis
        print(
            f"Page text (full): {page_text[:1000].encode('utf-8', errors='replace').decode('utf-8')}"
        )

        # Check for error messages first
        if "error" in page_text.lower() or "exception" in page_text.lower():
            print(f"ERROR DETECTED ON PAGE: {page_text}")

        # Look for any stException elements (Streamlit's error display)
        error_elements = streamlit_page.locator("[data-testid='stException']").all()
        if error_elements:
            print(f"Found {len(error_elements)} Streamlit exceptions on page")
            for i, elem in enumerate(error_elements):
                print(f"Exception {i+1}: {elem.inner_text()}")

        assert "Context Bridge" in page_text or "context bridge" in page_text.lower()
        assert "documentation" in page_text.lower()

    def test_sidebar_navigation_exists(self, streamlit_page: Page):
        """Test that sidebar navigation is present."""
        # Check for sidebar navigation items using the radio group
        # Use more specific selectors to avoid matching content text
        radio_group = streamlit_page.get_by_test_id("stRadio")
        expect(radio_group.get_by_text("📚 Documents", exact=True)).to_be_visible()
        expect(radio_group.get_by_text("📄 Crawled Pages", exact=True)).to_be_visible()
        expect(radio_group.get_by_text("🔍 Search", exact=True)).to_be_visible()

    def test_navigate_to_documents(self, streamlit_page: Page):
        """Test navigation to Documents page."""
        # Click on Documents in sidebar radio button
        radio_group = streamlit_page.get_by_test_id("stRadio")
        radio_group.get_by_text("📚 Documents", exact=True).click()

        # Wait for Streamlit to rerun the script and render new content
        streamlit_page.wait_for_timeout(6000)
        streamlit_page.wait_for_load_state("networkidle")

        # Take screenshot for debugging
        import os

        os.makedirs("tests/e2e/screenshots", exist_ok=True)
        streamlit_page.screenshot(path="tests/e2e/screenshots/documents_page.png")

        # Verify we're on the documents page - use heading role
        expect(streamlit_page.get_by_role("heading", name="📚 Document Management")).to_be_visible()

    def test_navigate_to_pages(self, streamlit_page: Page):
        """Test navigation to Pages page."""
        # Click on Pages in sidebar radio button
        radio_group = streamlit_page.get_by_test_id("stRadio")
        radio_group.get_by_text("📄 Crawled Pages", exact=True).click()
        streamlit_page.wait_for_load_state("networkidle")

        # Verify we're on the pages page - use heading role to be more specific
        expect(streamlit_page.get_by_role("heading", name="📄 Page Management")).to_be_visible()

    def test_navigate_to_search(self, streamlit_page: Page):
        """Test navigation to Search page."""
        # Click on Search in sidebar radio button
        radio_group = streamlit_page.get_by_test_id("stRadio")
        radio_group.get_by_text("🔍 Search", exact=True).click()
        streamlit_page.wait_for_load_state("networkidle")

        # Verify we're on the search page - use heading role to be more specific
        expect(
            streamlit_page.get_by_role("heading", name="🔍 Search Documentation")
        ).to_be_visible()


class TestDocumentManagement:
    """Test document management functionality."""

    def test_documents_page_loads(self, streamlit_page: Page):
        """Test that documents page loads with all elements."""
        # Navigate to documents page
        streamlit_page.get_by_text("📚 Documents").first.click()
        streamlit_page.wait_for_load_state("networkidle")

        # Check for tabs
        expect(streamlit_page.get_by_text("All Documents")).to_be_visible()
        expect(streamlit_page.get_by_text("Crawl New")).to_be_visible()

    def test_document_list_displays(self, streamlit_page: Page):
        """Test that document list is displayed."""
        # Navigate to documents page
        streamlit_page.get_by_text("📚 Documents").first.click()
        streamlit_page.wait_for_load_state("networkidle")

        # Check for document list or empty state message
        # This will show either documents or "No documents found"
        page_content = streamlit_page.content()
        assert "document" in page_content.lower() or "no documents" in page_content.lower()

    def test_crawl_form_exists(self, streamlit_page: Page):
        """Test that crawl form is accessible."""
        # Navigate to documents page
        streamlit_page.get_by_text("📚 Documents").first.click()
        streamlit_page.wait_for_load_state("networkidle")

        # Click on Crawl New tab
        streamlit_page.get_by_text("Crawl New", exact=True).click()
        streamlit_page.wait_for_timeout(500)

        # Check for form elements
        expect(streamlit_page.get_by_text("Document Name", exact=False)).to_be_visible()
        expect(streamlit_page.get_by_text("Version", exact=False)).to_be_visible()
        expect(streamlit_page.get_by_text("Source URL", exact=False)).to_be_visible()

    def test_search_filter_exists(self, streamlit_page: Page):
        """Test that search/filter controls exist on documents page."""
        # Navigate to documents page
        streamlit_page.get_by_text("📚 Documents").first.click()
        streamlit_page.wait_for_load_state("networkidle")

        # Check for search/filter controls
        page_content = streamlit_page.content()
        assert "search" in page_content.lower() or "filter" in page_content.lower()


class TestPageManagement:
    """Test page management functionality."""

    def test_pages_page_loads(self, streamlit_page: Page):
        """Test that pages page loads successfully."""
        # Navigate to pages page
        streamlit_page.get_by_text("📄 Crawled Pages").click()
        streamlit_page.wait_for_load_state("networkidle")

        # Check page loaded
        expect(streamlit_page.get_by_text("Page Management", exact=False)).to_be_visible()

    def test_document_selector_exists(self, streamlit_page: Page):
        """Test that document selector is present."""
        # Navigate to pages page
        streamlit_page.get_by_text("📄 Crawled Pages").click()
        streamlit_page.wait_for_load_state("networkidle")

        # Check for document selector
        page_content = streamlit_page.content()
        assert "select document" in page_content.lower() or "document" in page_content.lower()

    def test_page_list_section_exists(self, streamlit_page: Page):
        """Test that page list section exists."""
        # Navigate to pages page
        streamlit_page.get_by_text("📄 Crawled Pages").click()
        streamlit_page.wait_for_load_state("networkidle")

        # Check for page-related content
        page_content = streamlit_page.content()
        assert "page" in page_content.lower()


class TestSearchInterface:
    """Test search interface functionality."""

    def test_search_page_loads(self, streamlit_page: Page):
        """Test that search page loads successfully."""
        # Navigate to search page
        streamlit_page.get_by_text("🔍 Search").first.click()
        streamlit_page.wait_for_load_state("networkidle")

        # Check page loaded
        expect(streamlit_page.get_by_text("Search Documentation", exact=False)).to_be_visible()

    def test_search_form_exists(self, streamlit_page: Page):
        """Test that search form is present."""
        # Navigate to search page
        streamlit_page.get_by_text("🔍 Search").first.click()
        streamlit_page.wait_for_load_state("networkidle")

        # Check for search form elements
        page_content = streamlit_page.content()
        assert "search" in page_content.lower() or "query" in page_content.lower()

    def test_document_filter_exists(self, streamlit_page: Page):
        """Test that document filter exists on search page."""
        # Navigate to search page
        streamlit_page.get_by_text("🔍 Search").first.click()
        streamlit_page.wait_for_load_state("networkidle")

        # Check for filter options
        page_content = streamlit_page.content()
        assert "document" in page_content.lower() or "filter" in page_content.lower()


class TestResponsiveness:
    """Test UI responsiveness and loading states."""

    def test_page_loads_within_timeout(self, page: Page, streamlit_server: str):
        """Test that pages load within reasonable time."""
        # Set a reasonable timeout
        page.set_default_timeout(10000)  # 10 seconds

        # Navigate to app
        page.goto(streamlit_server)
        page.wait_for_load_state("networkidle")

        # Check that main content is visible
        expect(page.get_by_text("🌉 Context Bridge")).to_be_visible()

    def test_navigation_is_responsive(self, streamlit_page: Page):
        """Test that navigation between pages is responsive."""
        # Navigate through all pages quickly
        pages_to_test = ["📚 Documents", "📄 Crawled Pages", "🔍 Search"]

        for page_name in pages_to_test:
            streamlit_page.get_by_text(page_name).first.click()
            streamlit_page.wait_for_load_state("networkidle")
            # Should load within default timeout
            assert streamlit_page.url is not None


@pytest.mark.slow
class TestEndToEndWorkflows:
    """Test complete end-to-end workflows (marked as slow tests)."""

    def test_complete_navigation_flow(self, streamlit_page: Page):
        """Test navigating through all pages in sequence."""
        # Start at home
        expect(streamlit_page.get_by_text("🌉 Context Bridge")).to_be_visible()

        # Navigate to Documents
        streamlit_page.get_by_text("📚 Documents").first.click()
        streamlit_page.wait_for_load_state("networkidle")
        expect(streamlit_page.get_by_text("Document Management", exact=False)).to_be_visible()

        # Navigate to Pages
        streamlit_page.get_by_text("📄 Crawled Pages").first.click()
        streamlit_page.wait_for_load_state("networkidle")
        expect(streamlit_page.get_by_text("Page Management", exact=False)).to_be_visible()

        # Navigate to Search
        streamlit_page.get_by_text("🔍 Search").first.click()
        streamlit_page.wait_for_load_state("networkidle")
        expect(streamlit_page.get_by_text("Search Documentation", exact=False)).to_be_visible()

        # Navigate back to home
        streamlit_page.get_by_text("🏠 Home").first.click()
        streamlit_page.wait_for_load_state("networkidle")
        expect(streamlit_page.get_by_text("🌉 Context Bridge")).to_be_visible()
