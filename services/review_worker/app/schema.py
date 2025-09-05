import operator

from pydantic import BaseModel, Field
from typing_extensions import Annotated, TypedDict


class Comment(BaseModel):
    issue_header: str = Field(..., description="The header of the issue")
    issue_content: str = Field(..., description="The content of the issue")
    start_line: int = Field(..., description="The start line number of the issue")
    start_sign: str = Field(
        ..., description="The sign of the start line (+, -, or empty)"
    )
    end_line: int = Field(..., description="The end line number of the issue")
    end_sign: str = Field(..., description="The sign of the end line (+, -, or empty)")


class Reviews(BaseModel):
    filename: str = Field(
        ..., description="The name of the file where the comment applies"
    )
    previous_filename: str = Field(
        ..., description="The name of the file before the change"
    )
    comments: list[Comment] = Field(..., description="List of comments for the review")


class Summary(BaseModel):
    summary: str = Field(..., description="The summary of the reviews")


class OverallState(TypedDict):
    pr_title: str
    pr_description: str
    context_data: list[dict]
    reviews: Annotated[list, operator.add]
    summary: str


class ReviewAgentState(TypedDict):
    pr_title: str
    pr_description: str
    file: dict
