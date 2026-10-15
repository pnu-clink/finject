"""Shared strict types; no silent conversion or invented success defaults."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field

Text = Annotated[str, Field(min_length=1)]
Index = Annotated[int, Field(ge=0)]
Span = Annotated[list[Index], Field(min_length=2, max_length=2)]

class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
