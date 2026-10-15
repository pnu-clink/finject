"""EA recovery annotation, independent of the perturbation quality verdict."""
from pydantic import model_validator
from typing import Literal
from finarch.dataset.schemas.common import StrictModel, Text, Index

ROLE = "02-generation.03-validation.ea-recoverability-review"


class InverseRequest(StrictModel):
    question: Text
    context: Text


class InverseEvidence(StrictModel):
    field: Literal["question", "context"]
    start: Index
    end: Index
    quote: Text


class InverseReview(StrictModel):
    inverse_possible: bool
    missing_quantity: Text
    reason: Text
    evidence: list[InverseEvidence]
    formula: str | None

    @model_validator(mode="after")
    def require_witness_for_true(self):
        if not self.missing_quantity.strip() or not self.reason.strip():
            raise ValueError("NONEMPTY_RECOVERY_EXPLANATION_REQUIRED")
        if self.inverse_possible:
            if not self.evidence or not self.formula or not self.formula.strip():
                raise ValueError("RECOVERY_EVIDENCE_AND_FORMULA_REQUIRED")
        elif self.formula is not None:
            raise ValueError("FALSE_RECOVERY_FORMULA_MUST_BE_NULL")
        return self


class InverseResponse(StrictModel):
    inverse_review: InverseReview
