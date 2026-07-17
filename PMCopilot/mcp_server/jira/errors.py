class IssueNotFoundError(Exception):
    """Raised when no issue exists for the given issue_id."""

    def __init__(self, message: str, issue_id: int):
        super().__init__(message)
        self.issue_id = issue_id
