from typing import Optional
from pydantic import BaseModel, Field


class Page(BaseModel):
    id: str = Field(description="Server-assigned page id (UUID hex)")
    database_id: str = Field(description="Id of the database this page belongs to")
    title: str = Field(description="Page title")
    properties: dict[str, str] = Field(description="Structured metadata properties on the page")
    content: str = Field(description="Page body text")
    created_at: str = Field(description="UTC ISO timestamp when the page was created")
    updated_at: str = Field(description="UTC ISO timestamp when the page was last updated")


class CreatePageInput(BaseModel):
    # Real Notion nests title inside properties and takes content as a block tree.
    # The mock hoists title to a required field (structural enforcement of the one
    # mandatory property) and flattens content to a string deliberately — the MCP
    # seam is the artifact here, not a Notion reimplementation.
    database_id: str = Field(min_length=1, description="Id of the database to create the page in")
    title: str = Field(min_length=1, description="Page title")
    properties: dict[str, str] = Field(
        default_factory=dict,
        description="Optional metadata properties, e.g. {'status': 'draft'}",
    )
    content: str = Field(min_length=1, description="Page body text")


class ListPagesInput(BaseModel):
    database_id: Optional[str] = Field(
        default=None,
        description="Filter to pages in this database. Omit to return all pages.",
    )


class UpdatePageInput(BaseModel):
    # Patch semantics: only supplied fields change. None means 'leave unchanged';
    # there is no way to clear a field. Properties merge at key level — supplied
    # keys upsert, absent keys survive (matches real Notion's property updates).
    page_id: str = Field(min_length=1, description="Id of the page to update")
    title: Optional[str] = Field(default=None, min_length=1, description="New title, if changing")
    properties: Optional[dict[str, str]] = Field(
        default=None,
        description="Properties to upsert by key. Keys not supplied are left unchanged.",
    )
    content: Optional[str] = Field(default=None, min_length=1, description="New body text, if changing")
