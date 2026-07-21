"""MCP tool surface for the mock Notion. Thin wrappers: registration + docstrings only; logic lives in store."""
from mcp_server.app import mcp
from mcp_server.notion import store
from mcp_server.notion.schemas import CreatePageInput, ListPagesInput, Page, UpdatePageInput


@mcp.tool()
def create_page(data: CreatePageInput) -> Page:
    """Create a new page in a database with a title, optional metadata properties, and body text.
    Returns the created page, including its server-assigned id and timestamps."""
    return store.create_page(data)


@mcp.tool()
def list_pages(data: ListPagesInput) -> list[Page]:
    """List pages, optionally filtered by database id. Omit the filter to return all pages."""
    return store.list_pages(data)


@mcp.tool()
def update_page(data: UpdatePageInput) -> Page:
    """Patch a page: only the fields you supply are changed; properties merge by key.
    Returns the updated page. Fails if no page exists for the given id."""
    return store.update_page(data)
