from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Provenance(BaseModel):
    data_kind: str
    source_dataset_ids: list[str] = Field(default_factory=list)
    processing_version: str = "v1"
    notes: str | None = None


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class Message(BaseModel):
    detail: str
    extra: dict[str, Any] = Field(default_factory=dict)
