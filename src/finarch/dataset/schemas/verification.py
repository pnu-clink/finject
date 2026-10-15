"""Semantic verification supplements deterministic execution checks."""
from typing import Literal
from pydantic import Field, model_validator
from finarch.dataset.schemas.common import StrictModel, Text

CRITERIA = {'grounding_binding', 'operation_semantics', 'units_roles', 'context_sufficiency', 'solvability_uniqueness'}

class VerificationRequest(StrictModel):
    case: Text
    sample: dict
    program: dict
    execution: dict
    graph: dict
    deterministic_checks: dict

class Finding(StrictModel):
    criterion: Literal['grounding_binding','operation_semantics','units_roles','context_sufficiency','solvability_uniqueness']
    judgment: Literal['PASS','FAIL','UNKNOWN']
    reason: Text
    evidence: list[Text] = Field(min_length=1)

class VerificationResponse(StrictModel):
    findings: list[Finding]
    cohort: Literal['INTERNAL', 'EXTERNAL', 'PENDING']
    cohort_reason: Text
    required_external_sources: list[Literal['EXTERNAL_RULE', 'EXTERNAL_DATA']]
    @model_validator(mode='after')
    def complete(self):
        if len(self.findings)!=len(CRITERIA) or {x.criterion for x in self.findings}!=CRITERIA:
            raise ValueError('VERIFICATION_CRITERIA_INCOMPLETE')
        if self.cohort == 'INTERNAL' and self.required_external_sources:
            raise ValueError('INTERNAL_HAS_EXTERNAL_REQUIREMENT')
        if self.cohort == 'EXTERNAL' and not self.required_external_sources:
            raise ValueError('EXTERNAL_REQUIREMENT_MISSING')
        return self
