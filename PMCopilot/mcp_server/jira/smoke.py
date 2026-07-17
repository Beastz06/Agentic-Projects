"""Smoke test for the business layer — run: uv run python -m mcp_server.jira.smoke"""
from mcp_server.jira import db
from mcp_server.jira.errors import IssueNotFoundError
from mcp_server.jira.schemas import (
    AddCommentInput,
    CreateIssueInput,
    GetIssueInput,
    ListIssuesInput,
    UpdateStatusInput,
)


def main() -> None:
    db.init_db()

    issue = db.create_issue(CreateIssueInput(
        title="Login button unresponsive on Safari",
        body="Users on Safari 17 report the login button does nothing on first click; second click works.",
    ))
    print("CREATED:", issue.model_dump())

    print("ALL:", [i.id for i in db.list_issues(ListIssuesInput())])
    print("OPEN:", [i.id for i in db.list_issues(ListIssuesInput(status="open"))])
    print("DONE (expect empty on fresh db):", [i.id for i in db.list_issues(ListIssuesInput(status="done"))])

    fetched = db.get_issue(GetIssueInput(issue_id=issue.id))
    print("FETCHED:", fetched.id, fetched.title)

    updated = db.update_status(UpdateStatusInput(issue_id=issue.id, status="in_progress"))
    print("UPDATED:", updated.status, "updated_at:", updated.updated_at, "created_at unchanged:", updated.created_at)

    comment = db.add_comment(AddCommentInput(
        issue_id=issue.id, author="Sam", body="Reproduced on Safari 17.1, investigating.",
    ))
    print("COMMENT:", comment.model_dump())

    for fn, arg in [
        (db.get_issue, GetIssueInput(issue_id=9999)),
        (db.update_status, UpdateStatusInput(issue_id=9999, status="done")),
        (db.add_comment, AddCommentInput(issue_id=9999, author="Sam", body="Should fail loudly.")),
    ]:
        try:
            fn(arg)
            print("BUG: expected IssueNotFoundError, none raised")
        except IssueNotFoundError as e:
            print(f"OK raised: {e} (issue_id={e.issue_id})")


if __name__ == "__main__":
    main()
