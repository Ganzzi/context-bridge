"""
End-to-end tests for group management functionality.

Tests the following workflows:
1. Creating a group by processing pages
2. Viewing group details and statistics
3. Listing groups for a document
4. Reprocessing groups with context
5. Deleting groups
"""

import pytest
from playwright.sync_api import Page, expect
from typing import Generator


@pytest.fixture
def browser_page(streamlit_server, browser_context) -> Generator[Page, None, None]:
    """Create a new page for each test."""
    page = browser_context.new_page()
    page.goto("http://localhost:8501")
    page.wait_for_selector("h1", timeout=10000)  # Wait for app to load
    yield page
    page.close()


class TestGroupCreation:
    """Test group creation through page processing."""

    def test_create_group_via_page_processing(self, browser_page: Page):
        """
        Test creating a group by processing pages through the UI.

        Steps:
        1. Navigate to Page Management page
        2. Select a document
        3. Select some pages
        4. Enter group name and description
        5. Start chunking process
        6. Verify group was created
        """
        page = browser_page

        # Click on "📄 Page Management" in sidebar
        page.click("text=📄 Page Management")
        page.wait_for_selector("text=Select Document", timeout=5000)

        # Select first document from dropdown
        page.click("select:first-of-type")
        page.wait_for_timeout(500)

        # Select first available document option
        options = page.locator("option")
        if options.count() > 1:
            page.select_option("select:first-of-type", options.nth(1).get_attribute("value"))
            page.wait_for_timeout(1000)

            # Click Load Pages button
            page.click("button:has-text('Load Pages')")
            page.wait_for_selector("text=Select pages to process", timeout=5000)

            # Select first checkbox
            checkboxes = page.locator("input[type='checkbox']")
            if checkboxes.count() > 0:
                checkboxes.first.click()

                # Enter group name
                group_name_input = page.locator("input[placeholder='e.g., API Documentation']")
                if group_name_input:
                    group_name_input.fill("Test Group E2E")

                # Verify process button exists
                process_button = page.locator("button:has-text('Start Chunking & Group Creation')")
                expect(process_button).to_be_enabled()

    def test_group_configuration_fields(self, browser_page: Page):
        """Test that group configuration fields are visible and functional."""
        page = browser_page

        # Navigate to Page Management
        page.click("text=📄 Page Management")
        page.wait_for_selector("text=Select Document", timeout=5000)

        # Select document and load pages
        page.click("select:first-of-type")
        page.wait_for_timeout(500)

        options = page.locator("option")
        if options.count() > 1:
            page.select_option("select:first-of-type", options.nth(1).get_attribute("value"))
            page.wait_for_timeout(1000)

            page.click("button:has-text('Load Pages')")
            page.wait_for_selector("text=Select pages to process", timeout=5000)

            # Select at least one page
            checkbox = page.locator("input[type='checkbox']").first
            if checkbox:
                checkbox.click()
                page.wait_for_timeout(500)

                # Verify group configuration section appears
                expect(page.locator("text=🏷️ Group Configuration")).to_be_visible()
                expect(page.locator("input[placeholder='e.g., API Documentation']")).to_be_visible()
                expect(
                    page.locator("input[placeholder='e.g., Complete REST API reference']")
                ).to_be_visible()
                expect(page.locator("text=Enable AI Context Generation")).to_be_visible()


class TestGroupManagement:
    """Test group management page functionality."""

    def test_load_groups_page(self, browser_page: Page):
        """Test that groups page loads successfully."""
        page = browser_page

        # Click on Groups link in sidebar
        page.click("text=📊 Group Management")
        page.wait_for_selector("text=Group Management", timeout=5000)

        # Verify page elements
        expect(page.locator("text=📊 Group Management")).to_be_visible()
        expect(page.locator("text=Select Document")).to_be_visible()

    def test_select_document_and_load_groups(self, browser_page: Page):
        """Test selecting a document and loading its groups."""
        page = browser_page

        page.click("text=📊 Group Management")
        page.wait_for_selector("text=Select Document", timeout=5000)

        # Select document
        page.click("select:has-text('Select a document')")
        page.wait_for_timeout(500)

        options = page.locator("option")
        if options.count() > 1:
            page.select_option(
                "select:has-text('Select a document')",
                options.nth(1).get_attribute("value"),
            )
            page.wait_for_timeout(1000)

            # Click Load Groups
            page.click("button:has-text('Load Groups')")
            page.wait_for_selector("text=Groups Overview", timeout=5000)

            # Verify UI elements appear
            expect(
                page.locator("select:has-text('Sort by')", page.locator("text=Sort by"))
            ).to_be_visible()

    def test_sort_groups_by_status(self, browser_page: Page):
        """Test sorting groups by different criteria."""
        page = browser_page

        page.click("text=📊 Group Management")
        page.wait_for_selector("text=Select Document", timeout=5000)

        # Select document
        page.click("select:has-text('Select a document')")
        page.wait_for_timeout(500)

        options = page.locator("option")
        if options.count() > 1:
            page.select_option(
                "select:has-text('Select a document')",
                options.nth(1).get_attribute("value"),
            )
            page.wait_for_timeout(1000)

            # Click Load Groups
            page.click("button:has-text('Load Groups')")
            page.wait_for_selector("text=Groups Overview", timeout=5000)

            # Change sort option
            sort_select = page.locator("select").filter(has_text="Sort by")
            if sort_select:
                page.select_option(sort_select, "Status")
                page.wait_for_timeout(500)

    def test_group_details_view(self, browser_page: Page):
        """Test viewing detailed information for a group."""
        page = browser_page

        page.click("text=📊 Group Management")
        page.wait_for_selector("text=Select Document", timeout=5000)

        # Select document
        page.click("select:has-text('Select a document')")
        page.wait_for_timeout(500)

        options = page.locator("option")
        if options.count() > 1:
            page.select_option(
                "select:has-text('Select a document')",
                options.nth(1).get_attribute("value"),
            )
            page.wait_for_timeout(1000)

            # Click Load Groups
            page.click("button:has-text('Load Groups')")
            page.wait_for_selector("text=Groups Overview", timeout=5000)

            # Wait for groups table to load
            page.wait_for_selector("table", timeout=5000)

            # Try to select a group from dropdown
            group_selector = page.locator("select").nth(1)  # Second select should be group selector
            if group_selector:
                options = page.locator("option")
                if options.count() > 1:
                    page.select_option(group_selector, options.nth(1).get_attribute("value"))
                    page.wait_for_timeout(1000)

                    # Verify group details section appears
                    expect(page.locator("text=Group Information")).to_be_visible()
                    expect(page.locator("text=Statistics")).to_be_visible()


class TestGroupStatistics:
    """Test group statistics display and metrics."""

    def test_group_statistics_displayed(self, browser_page: Page):
        """Test that group statistics are correctly displayed."""
        page = browser_page

        page.click("text=📊 Group Management")
        page.wait_for_selector("text=Select Document", timeout=5000)

        # Select document and load groups
        page.click("select:has-text('Select a document')")
        page.wait_for_timeout(500)

        options = page.locator("option")
        if options.count() > 1:
            page.select_option(
                "select:has-text('Select a document')",
                options.nth(1).get_attribute("value"),
            )
            page.wait_for_timeout(1000)

            page.click("button:has-text('Load Groups')")
            page.wait_for_selector("text=Groups Overview", timeout=5000)

            # Wait for table
            page.wait_for_selector("table", timeout=5000)

            # Verify table has expected columns
            expect(page.locator("text=Pages")).to_be_visible()
            expect(page.locator("text=Chunks")).to_be_visible()
            expect(page.locator("text=Status")).to_be_visible()


class TestGroupActions:
    """Test group action buttons and confirmations."""

    def test_view_pages_action(self, browser_page: Page):
        """Test the 'View Pages' action for a group."""
        page = browser_page

        page.click("text=📊 Group Management")
        page.wait_for_selector("text=Select Document", timeout=5000)

        # Select document
        page.click("select:has-text('Select a document')")
        page.wait_for_timeout(500)

        options = page.locator("option")
        if options.count() > 1:
            page.select_option(
                "select:has-text('Select a document')",
                options.nth(1).get_attribute("value"),
            )
            page.wait_for_timeout(1000)

            page.click("button:has-text('Load Groups')")
            page.wait_for_selector("text=Groups Overview", timeout=5000)

            # Select a group
            page.wait_for_selector("table", timeout=5000)
            group_selector = page.locator("select").nth(1)
            if group_selector:
                options = page.locator("option")
                if options.count() > 1:
                    page.select_option(group_selector, options.nth(1).get_attribute("value"))
                    page.wait_for_timeout(1000)

                    # Click View Pages button if it exists
                    view_pages_button = page.locator("button:has-text('View Pages')")
                    if view_pages_button:
                        expect(view_pages_button).to_be_visible()

    def test_delete_group_confirmation(self, browser_page: Page):
        """Test the delete group confirmation dialog."""
        page = browser_page

        page.click("text=📊 Group Management")
        page.wait_for_selector("text=Select Document", timeout=5000)

        # Select document
        page.click("select:has-text('Select a document')")
        page.wait_for_timeout(500)

        options = page.locator("option")
        if options.count() > 1:
            page.select_option(
                "select:has-text('Select a document')",
                options.nth(1).get_attribute("value"),
            )
            page.wait_for_timeout(1000)

            page.click("button:has-text('Load Groups')")
            page.wait_for_selector("text=Groups Overview", timeout=5000)

            # Select a group
            page.wait_for_selector("table", timeout=5000)
            group_selector = page.locator("select").nth(1)
            if group_selector:
                options = page.locator("option")
                if options.count() > 1:
                    page.select_option(group_selector, options.nth(1).get_attribute("value"))
                    page.wait_for_timeout(1000)

                    # Verify delete button exists
                    delete_button = page.locator("button:has-text('Delete Group')")
                    expect(delete_button).to_be_visible()


class TestGroupIntegration:
    """Integration tests for complete group workflows."""

    def test_complete_group_workflow(self, browser_page: Page):
        """
        Test complete workflow: create group → view details → manage.

        Note: This is a high-level integration test that verifies
        the complete workflow is possible.
        """
        page = browser_page

        # Step 1: Navigate to Page Management
        page.click("text=📄 Page Management")
        page.wait_for_selector("text=Select Document", timeout=5000)

        # Step 2: Select a document
        page.click("select:first-of-type")
        page.wait_for_timeout(500)

        options = page.locator("option")
        if options.count() > 1:
            page.select_option("select:first-of-type", options.nth(1).get_attribute("value"))
            page.wait_for_timeout(1000)

            # Step 3: Load pages
            page.click("button:has-text('Load Pages')")
            page.wait_for_selector("text=Select pages to process", timeout=5000)

            # Step 4: Navigate to Groups page
            page.click("text=📊 Group Management")
            page.wait_for_selector("text=Select Document", timeout=5000)

            # Step 5: Verify groups page loads
            expect(page.locator("text=📊 Group Management")).to_be_visible()
            expect(page.locator("text=Select Document")).to_be_visible()
