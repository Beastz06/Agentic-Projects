"""MCP tool surface for the mock Jira. Thin wrappers: registration + docstrings only; logic lives in db."""
from mcp_server.app import mcp
from mcp_server.jira import db
from mcp_server.jira.schemas import (
    AddCommentInput,
    Comment,
    CreateIssueInput,
    GetIssueInput,
    Issue,
    ListIssuesInput,
    UpdateStatusInput,
)


@mcp.tool()
def create_issue(data: CreateIssueInput) -> Issue:
    """Create a new issue with the given title and body. The new issue starts with status 'open'.
    Returns the created issue, including its server-assigned id and timestamps."""
    return db.create_issue(data)


@mcp.tool()
def list_issues(data: ListIssuesInput) -> list[Issue]:
    """List issues, optionally filtered by status. Omit the filter to return all issues."""
    return db.list_issues(data)


@mcp.tool()
def get_issue(data: GetIssueInput) -> Issue:
    """Fetch a single issue by id. Fails if no issue exists for the given id."""
    return db.get_issue(data)


@mcp.tool()
def update_status(data: UpdateStatusInput) -> Issue:
    """Set a new status on an issue. Returns the updated issue.
    Fails if no issue exists for the given id."""
    return db.update_status(data)


@mcp.tool()
def add_comment(data: AddCommentInput) -> Comment:
    """Add a comment to an issue. Returns the created comment, including its server-assigned id.
    Fails if no issue exists for the given id."""
    return db.add_comment(data)
