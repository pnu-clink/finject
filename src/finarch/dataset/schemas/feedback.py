"""Independent failure-to-guidance contract, never completed dataset prose."""
from typing import Literal
from pydantic import Field
from finarch.dataset.schemas.common import StrictModel, Text

class FeedbackFailure(StrictModel):
    case: Text
    label: Text
    reason: Text
    request: dict
    response: dict

class FeedbackRequest(StrictModel):
    axis: Literal['ANSWER','IC_VALUE','IC_SOURCE','IC_RELATION','EA']
    target_role: Literal['02-generation.02-generate-text.realization','shared.01-02.02-03.review-and-validation']
    common_and_type_instructions: Text
    feedback_scope: Literal['cumulative', 'single_case_variant'] = 'cumulative'
    previous_guidance: str
    failures: list[FeedbackFailure] = Field(min_length=1)

class FeedbackResponse(StrictModel):
    guidance: Text = Field(description='English repair guidance for the requested scope; concrete case-specific corrections for single_case_variant, cumulative guidance otherwise; no completed dataset sentences or answers')
    changes: list[Text] = Field(min_length=1, description='Explain the failure and corrective actions within the requested scope')

class LegacyFeedbackRequest(FeedbackRequest):
    target_role: Literal["dtt.realize", "dtt.audit"]
