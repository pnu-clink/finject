"""Structured single-case exception diagnosis."""
from typing import Literal
from finarch.dataset.schemas.common import StrictModel, Text

class ExceptionRequest(StrictModel):
    case: Text
    phase: Literal['preparation', 'generation']
    source_round: Text
    failed_step: Text
    error_type: Text
    reason: Text
    evidence: dict
    allowed_steps: list[Text]

class ExceptionResponse(StrictModel):
    retryable: bool
    target_step: Text
    diagnosis: Text
    guidance: Text
