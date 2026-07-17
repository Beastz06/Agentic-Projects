"""Business layer: SQLite-backed CRUD for the mock Jira. Raises IssueNotFoundError on missing ids;
the MCP transport converts uncaught exceptions into readable error-results for the calling model."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from mcp_server.jira.errors import IssueNotFoundError
from mcp_server.jira.schemas import (
    AddCommentInput,
    Comment,
    CreateIssueInput,
    GetIssueInput,
    Issue,
    ListIssuesInput,
    UpdateStatusInput,
)

DB_PATH = Path(__file__).parent / "jira_mock.sqlite"


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS issues (id INTEGER PRIMARY KEY, title TEXT NOT NULL, "
            "body TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, "
            "updated_at TEXT NOT NULL);"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY, issue_id INTEGER NOT NULL, "
            "author TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL, "
            "FOREIGN KEY (issue_id) REFERENCES issues(id));"
        )
        conn.commit()
    finally:
        conn.close()


def create_issue(data: CreateIssueInput) -> Issue:
    """Insert a new issue, let SQLite assign the id, return the full Issue."""
    now = datetime.now(timezone.utc).isoformat()
    status = "open"  # create-default lives here, not in the model

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            "INSERT INTO issues (title, body, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (data.title, data.body, status, now, now),
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()

    return Issue(id=new_id, title=data.title, body=data.body, status=status, created_at=now, updated_at=now)


def list_issues(data: ListIssuesInput) -> list[Issue]:
    """Return issues matching the status filter; all issues if no filter given."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    issues: list[Issue] = []
    try:
        if data.status is None:
            rows = conn.execute("SELECT * FROM issues").fetchall()
        else:
            rows = conn.execute("SELECT * FROM issues WHERE status = ?", (data.status,)).fetchall()
        issues = [Issue(**dict(row)) for row in rows]
    finally:
        conn.close()
    return issues


def get_issue(data: GetIssueInput) -> Issue:
    """Fetch a single issue by id. Raises IssueNotFoundError if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM issues WHERE id = ?", (data.issue_id,)).fetchone()
    finally:
        conn.close()

    if row is None:
        raise IssueNotFoundError(f"No issue found with id {data.issue_id}", issue_id=data.issue_id)
    return Issue(**dict(row))


def update_status(data: UpdateStatusInput) -> Issue:
    """Set a new status on an issue and return it. Raises IssueNotFoundError if it doesn't exist."""
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "UPDATE issues SET status = ?, updated_at = ? WHERE id = ?",
            (data.status, now, data.issue_id),
        )
        if cursor.rowcount == 0:
            raise IssueNotFoundError(f"No issue found with id {data.issue_id}", issue_id=data.issue_id)
        row = conn.execute("SELECT * FROM issues WHERE id = ?", (data.issue_id,)).fetchone()
        conn.commit()
    finally:
        conn.close()
    return Issue(**dict(row))


def add_comment(data: AddCommentInput) -> Comment:
    """Add a comment to an existing issue. Raises IssueNotFoundError if the issue doesn't exist."""
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        exists = conn.execute("SELECT 1 FROM issues WHERE id = ?", (data.issue_id,)).fetchone()
        if exists is None:
            raise IssueNotFoundError(f"No issue found with id {data.issue_id}", issue_id=data.issue_id)
        cursor = conn.execute(
            "INSERT INTO comments (issue_id, author, body, created_at) VALUES (?, ?, ?, ?)",
            (data.issue_id, data.author, data.body, now),
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()

    return Comment(id=new_id, issue_id=data.issue_id, author=data.author, body=data.body, created_at=now)
