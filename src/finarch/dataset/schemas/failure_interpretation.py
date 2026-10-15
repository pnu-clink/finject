"""Read-only human-review advice, separate from production verdicts/feedback."""
from typing import Literal
from pydantic import Field
from finarch.dataset.schemas.common import StrictModel, Text

ROLE = 'shared.01-07.02-05.failure-interpretation'
TRANSLATION_ROLE = 'shared.01-07.02-05.display-translation'

class Artifact(StrictModel):
    id: Text
    path: Text
    sha256: Text
    content: str

class InterpretationRequest(StrictModel):
    run: Text
    phase: Literal['preparation', 'generation']
    case: Text
    variant: str | None
    round: str
    failed_step: Text
    current_rejection: str
    artifacts: list[Artifact] = Field(min_length=1)
    missing_stages: list[str]

class Observation(StrictModel):
    statement: Text
    evidence_ids: list[Text] = Field(min_length=1)
    kind: Literal['RECORDED', 'INFERRED']

class RepairPlan(StrictModel):
    action: Literal['REPAIR_AND_VERIFY', 'REVERIFY', 'HUMAN_REQUIRED']
    target_step: str | None
    evidence_ids: list[Text] = Field(min_length=1)
    instructions: list[Text] = Field(min_length=1)
    preserve: list[Text] = Field(min_length=1)
    acceptance_checks: list[Text] = Field(min_length=1)
    required_information: list[Text]

class InterpretationResponse(StrictModel):
    repair_plan: RepairPlan
    rejection_summary: Text
    observations: list[Observation] = Field(min_length=1)
    assessment: Literal['JUSTIFIED', 'TOO_STRICT', 'WRONG_CAUSE', 'INSUFFICIENT_EVIDENCE']
    rationale: Text
    recommended_action: Text
    target_step: str | None
    limitations: list[Text]

class TranslationRequest(StrictModel):
    source_language: Literal['en']
    display_language: Literal['ko']
    analysis: InterpretationResponse

