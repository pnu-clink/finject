"""Private, explicitly supplied numeric bindings; never a model extraction request."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


class RecoveryBinding(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    variable: str = Field(min_length=1)
    field: Literal['context', 'question']
    span: list[Annotated[int, Field(ge=0)]] = Field(min_length=2, max_length=2)
    text: str = Field(min_length=1, max_length=128)

    @model_validator(mode='after')
    def ordered(self):
        if self.span[0] >= self.span[1]:
            raise ValueError('BINDING_SPAN_ORDER')
        return self


class RecoveryBindings(RootModel[list[RecoveryBinding]]):
    root: list[RecoveryBinding] = Field(max_length=16)
