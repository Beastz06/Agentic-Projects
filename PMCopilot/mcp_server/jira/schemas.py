from typing import Literal, Optional
from pydantic import BaseModel, Field

Status = Literal["open", "in_progress", "done"]


class Issue(BaseModel):
    id: int = Field(gt=0, description="Server-assigned issue id")
    title: str = Field(description="Issue title")
    body: str = Field(description="Statement of the user problem")
    status: Status = Field(description="Current status of the issue")
    created_at: str = Field(description="UTC ISO timestamp when the issue was created")
    updated_at: str = Field(description="UTC ISO timestamp when the issue was last updated")


class Comment(BaseModel):
    id: int = Field(gt=0, description="Server-assigned comment id")
    issue_id: int = Field(gt=0, description="Id of the issue this comment belongs to")
    author: str = Field(description="Name of the comment author")
    body: str = Field(description="Comment text")
    created_at: str = Field(description="UTC ISO timestamp when the comment was created")


class CreateIssueInput(BaseModel):
    title: str = Field(min_length=1, description="Issue title")
    body: str = Field(min_length=1, description="Statement of the user problem")


class ListIssuesInput(BaseModel):
    status: Optional[Status] = Field(
        default=None,
        description="Filter to issues with this status. Omit to return all issues.",
    )


class GetIssueInput(BaseModel):
    issue_id: int = Field(gt=0, description="Id of the issue to fetch")


class UpdateStatusInput(BaseModel):
    issue_id: int = Field(gt=0, description="Id of the issue to update")
    status: Status = Field(description="The new status to set on the issue")


class AddCommentInput(BaseModel):
    issue_id: int = Field(gt=0, description="Id of the issue to comment on")
    author: str = Field(min_length=1, description="Name of the comment author")
    body: str = Field(min_length=1, description="Comment text")
