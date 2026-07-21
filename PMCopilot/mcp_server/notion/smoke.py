"""Smoke test for the business layer — run: uv run python -m mcp_server.notion.smoke"""
from mcp_server.notion import store
from mcp_server.notion.errors import PageNotFoundError
from mcp_server.notion.schemas import CreatePageInput, ListPagesInput, UpdatePageInput


def main() -> None:
    store.init_store()

    page = store.create_page(CreatePageInput(
        database_id="prd-db",
        title="Authentication session timeouts",
        properties={"status": "draft"},
        content="Users report being logged out mid-session with no warning.",
    ))
    print("CREATED:", page.model_dump())

    print("ALL:", [p.id for p in store.list_pages(ListPagesInput())])
    print("PRD-DB:", [p.id for p in store.list_pages(ListPagesInput(database_id="prd-db"))])
    print("OTHER-DB (expect empty):", [p.id for p in store.list_pages(ListPagesInput(database_id="nope"))])

    patched = store.update_page(UpdatePageInput(page_id=page.id, properties={"status": "approved", "owner": "Sam"}))
    print("PATCHED props:", patched.properties)
    print("TITLE unchanged:", patched.title, "| CONTENT unchanged:", patched.content == page.content)
    print("updated_at moved:", patched.updated_at != page.updated_at, "| created_at fixed:", patched.created_at == page.created_at)

    try:
        store.update_page(UpdatePageInput(page_id="deadbeef", title="ghost"))
        print("BUG: expected PageNotFoundError, none raised")
    except PageNotFoundError as e:
        print(f"OK raised: {e} (page_id={e.page_id})")


if __name__ == "__main__":
    main()
