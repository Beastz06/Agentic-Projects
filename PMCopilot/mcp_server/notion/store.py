"""Business layer: JSON-file-backed page store for the mock Notion. Raises PageNotFoundError
on missing ids; the MCP transport converts uncaught exceptions into readable error-results."""
import json
import uuid
from datetime import datetime, timezone
from mcp_server.app import DATA_ROOT
from mcp_server.notion.errors import PageNotFoundError
from mcp_server.notion.schemas import CreatePageInput, ListPagesInput, Page, UpdatePageInput

DATA_DIR = DATA_ROOT / "notion"
DATA_DIR.mkdir(parents=True, exist_ok=True)
STORE_PATH = DATA_DIR / "notion_mock.json"


def init_store() -> None:
    if not STORE_PATH.exists():
        STORE_PATH.write_text(json.dumps({"pages": {}}, indent=2), encoding="utf-8")


def _load() -> dict:
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def create_page(data: CreatePageInput) -> Page:
    """Insert a new page with a server-assigned UUID id and return it."""
    now = datetime.now(timezone.utc).isoformat()
    page = Page(
        id=uuid.uuid4().hex,
        database_id=data.database_id,
        title=data.title,
        properties=data.properties,
        content=data.content,
        created_at=now,
        updated_at=now,
    )
    store = _load()
    store["pages"][page.id] = page.model_dump()
    _save(store)
    return page


def list_pages(data: ListPagesInput) -> list[Page]:
    """Return pages matching the database filter; all pages if no filter given."""
    store = _load()
    pages = [Page(**p) for p in store["pages"].values()]
    if data.database_id is not None:
        pages = [p for p in pages if p.database_id == data.database_id]
    return pages


def update_page(data: UpdatePageInput) -> Page:
    """Patch a page: only supplied fields change; properties upsert at key level.
    Raises PageNotFoundError if the page doesn't exist."""
    store = _load()
    raw = store["pages"].get(data.page_id)
    if raw is None:
        raise PageNotFoundError(f"No page found with id {data.page_id}", page_id=data.page_id)

    if data.title is not None:
        raw["title"] = data.title
    if data.properties is not None:
        raw["properties"].update(data.properties)
    if data.content is not None:
        raw["content"] = data.content
    raw["updated_at"] = datetime.now(timezone.utc).isoformat()

    store["pages"][data.page_id] = raw
    _save(store)
    return Page(**raw)
