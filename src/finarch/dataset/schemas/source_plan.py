"""Private stage-13 source conditions and text-realization input, not LLM output."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class SourceDescriptor(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    side: Literal['A','B']
    source_id: str=Field(min_length=1)
    role: str=Field(min_length=1)
    information_access: str=Field(min_length=1)
    verification: str=Field(min_length=1)
    attribution: Literal['direct']
    intended_reliability: Literal['H']

class SourcePlan(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    axis: Literal['IC_SOURCE']
    base_plan_ref: str=Field(min_length=1)
    base_plan_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    source_condition: Literal['A_ONLY','B_ONLY']
    base_variant: Literal['IC_VALUE_01_BEFORE','IC_VALUE_01_AFTER']='IC_VALUE_01_BEFORE'
    claim_order: list[Literal['A','B']]=Field(min_length=2,max_length=2)
    sources: list[SourceDescriptor]=Field(min_length=1,max_length=1)
    realization_rules: list[str]=Field(min_length=1)
    provenance: Literal['locally_authored_source_conditions_not_original_facts']
    semantic_status: Literal['NOT_EVALUATED']
    final_text_status: Literal['NOT_RUN']
    model_calls: Literal[0]

    @model_validator(mode='after')
    def assignment(self):
        if sorted(self.claim_order)!=['A','B']:raise ValueError('BOTH_CLAIM_IDENTITIES_REQUIRED')
        if self.sources[0].side!=self.source_condition[0]:raise ValueError('SOURCE_ASSIGNMENT_MISMATCH')
        return self
