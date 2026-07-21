class PageNotFoundError(Exception):
    """Raised when no page exists for the given page_id."""

    def __init__(self, message: str, page_id: str):
        super().__init__(message)
        self.page_id = page_id
