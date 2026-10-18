"""One schema definition feeds both model instructions and Python validation."""

traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import pydantic
from pydantic import BaseModel
from finarch.dataset.schemas.feedback import FeedbackRequest, FeedbackResponse, LegacyFeedbackRequest
from finarch.dataset.schemas.preparation import RevisionRequest, RevisionResponse, EvidenceRequest, EvidenceResponse
from finarch.dataset.schemas.prepared import PreparedInputsSchema
from finarch.dataset.schemas.custom_input import CustomInputsSchema
from finarch.dataset.schemas.llm import ProgramResponse, ProgramResponseV5, RealizationResponse, LegacyAuditResponse, AuditResponse, AuditRequest, ProgramRequest, RealizationRequest

@dataclass(frozen=True)
class Contract:
    model: type[BaseModel]
    version: int = 1
    readiness: str = "defined"

from finarch.dataset.schemas.exception_handler import ExceptionRequest, ExceptionResponse

from finarch.dataset.schemas.verification import VerificationRequest, VerificationResponse
from finarch.dataset.schemas.generation_quality import RecoveryBindings
from finarch.dataset.schemas.ea_inverse_review import ROLE as INVERSE_ROLE, InverseRequest, InverseResponse
from finarch.dataset.schemas.failure_interpretation import ROLE, TRANSLATION_ROLE, InterpretationRequest, InterpretationResponse, TranslationRequest

CONTRACTS = {
    INVERSE_ROLE+".request": Contract(InverseRequest),
    INVERSE_ROLE+".response": Contract(InverseResponse),
    "02-generation.03-validation.ea-recovery-bindings": Contract(RecoveryBindings),
    ROLE+".request": Contract(InterpretationRequest),
    ROLE+".response": Contract(InterpretationResponse),
    TRANSLATION_ROLE+".request": Contract(TranslationRequest),
    TRANSLATION_ROLE+".response": Contract(InterpretationResponse),
    "01-preparation.05-verification.semantic.request": Contract(VerificationRequest),
    "01-preparation.05-verification.semantic.response": Contract(VerificationResponse),
    "shared.01-06.02-04.exception-handler.request": Contract(ExceptionRequest),
    "shared.01-06.02-04.exception-handler.response": Contract(ExceptionResponse),
    "01-preparation.02-review-and-correct.revision.request": Contract(RevisionRequest),
    "01-preparation.02-review-and-correct.revision.response": Contract(RevisionResponse),
    "01-preparation.03-calculation.review-answer-evidence.request": Contract(EvidenceRequest),
    "01-preparation.03-calculation.review-answer-evidence.response": Contract(EvidenceResponse),
    "02-generation.feedback.case-feedback.request": Contract(FeedbackRequest, version=2),
    "02-generation.feedback.case-feedback.response": Contract(FeedbackResponse),
    "01-preparation.01-source.prepared-input": Contract(PreparedInputsSchema, version=2),
    "01-preparation.01-source.custom-input": Contract(CustomInputsSchema),
    "01-preparation.03-calculation.pot.request": Contract(ProgramRequest, version=2),
    "01-preparation.03-calculation.pot.response": Contract(ProgramResponseV5, version=5),
    "02-generation.02-generate-text.realization.response": Contract(RealizationResponse),
    "02-generation.02-generate-text.realization.request": Contract(RealizationRequest),
    "shared.01-02.02-03.review-and-validation.request": Contract(AuditRequest, version=2),
    "shared.01-02.02-03.review-and-validation.response": Contract(AuditResponse, version=4),
    "shared.01-02.02-03.review-and-validation.response.v2": Contract(LegacyAuditResponse, version=2),
}

# Contract IDs and export filenames use the same stage-based naming.
SCHEMA_FILES = {"01-preparation.05-verification.semantic.request": "01-preparation.05-verification.semantic.request.schema.json", "01-preparation.05-verification.semantic.response": "01-preparation.05-verification.semantic.response.schema.json", "shared.01-06.02-04.exception-handler.request": "shared.01-06.02-04.exception-handler.request.schema.json", "shared.01-06.02-04.exception-handler.response": "shared.01-06.02-04.exception-handler.response.schema.json", '01-preparation.02-review-and-correct.revision.request': '01-preparation.02-review-and-correct.revision.request.schema.json',
 '01-preparation.02-review-and-correct.revision.response': '01-preparation.02-review-and-correct.revision.response.schema.json',
 '01-preparation.03-calculation.review-answer-evidence.request': '01-preparation.03-calculation.review-answer-evidence.request.schema.json',
 '01-preparation.03-calculation.review-answer-evidence.response': '01-preparation.03-calculation.review-answer-evidence.response.schema.json',
 '02-generation.feedback.case-feedback.request': '02-generation.feedback.case-feedback.request.schema.json',
 '02-generation.feedback.case-feedback.response': '02-generation.feedback.case-feedback.response.schema.json',
 '01-preparation.01-source.prepared-input': '01-preparation.01-source.prepared-input.schema.json',
 '01-preparation.03-calculation.pot.request': '01-preparation.03-calculation.pot.request.schema.json',
 '01-preparation.03-calculation.pot.response': '01-preparation.03-calculation.pot.response.schema.json',
 '02-generation.02-generate-text.realization.response': '02-generation.02-generate-text.realization.response.schema.json',
 '02-generation.02-generate-text.realization.request': '02-generation.02-generate-text.realization.request.schema.json',
 'shared.01-02.02-03.review-and-validation.request': 'shared.01-02.02-03.review-and-validation.request.schema.json',
 'shared.01-02.02-03.review-and-validation.response': 'shared.01-02.02-03.review-and-validation.response.schema.json',
 'shared.01-02.02-03.review-and-validation.response.v2': 'shared.01-02.02-03.review-and-validation.response.v2.schema.json'}

SCHEMA_FILES["02-generation.03-validation.ea-recovery-bindings"] = "02-generation.03-validation.ea-recovery-bindings.schema.json"
SCHEMA_FILES["01-preparation.01-source.custom-input"] = "01-preparation.01-source.custom-input.schema.json"
SCHEMA_FILES.update({INVERSE_ROLE+"."+direction: INVERSE_ROLE+"."+direction+".schema.json" for direction in ("request", "response")})

SCHEMA_FILES.update({role+"."+direction:role+"."+direction+".schema.json" for role in (ROLE,TRANSLATION_ROLE) for direction in ("request","response")})

LEGACY_SCHEMA_IDS = {'preparation.revise.request': '01-preparation.02-review-and-correct.revision.request', 'preparation.revise.response': '01-preparation.02-review-and-correct.revision.response', 'preparation.evidence.request': '01-preparation.03-calculation.review-answer-evidence.request', 'preparation.evidence.response': '01-preparation.03-calculation.review-answer-evidence.response', 'dtt.feedback.request': '02-generation.feedback.case-feedback.request', 'dtt.feedback.response': '02-generation.feedback.case-feedback.response', 'prepared.input': '01-preparation.01-source.prepared-input', 'pot.author.request': '01-preparation.03-calculation.pot.request', 'pot.author.response': '01-preparation.03-calculation.pot.response', 'dtt.realize.response': '02-generation.02-generate-text.realization.response', 'dtt.realize.request': '02-generation.02-generate-text.realization.request', 'dtt.audit.request': 'shared.01-02.02-03.review-and-validation.request', 'dtt.audit.response': 'shared.01-02.02-03.review-and-validation.response', 'dtt.audit.response.v2': 'shared.01-02.02-03.review-and-validation.response.v2'}

def resolve_schema_id(schema_id):
    return LEGACY_SCHEMA_IDS.get(schema_id, schema_id)

def schema_filename(schema_id):
    return SCHEMA_FILES[resolve_schema_id(schema_id)]

# Keep the role inventory independent: deleting a schema must not silently turn
# an LLM step into an unchecked Python step.
LLM_ROLES = frozenset({INVERSE_ROLE, ROLE, TRANSLATION_ROLE,"01-preparation.05-verification.semantic","shared.01-06.02-04.exception-handler",
    "01-preparation.02-review-and-correct.revision", "01-preparation.03-calculation.review-answer-evidence",
    "01-preparation.03-calculation.pot", "dag.review_inverse", "dag.source",
    "02-generation.02-generate-text.realization", "shared.01-02.02-03.review-and-validation", "dtt.answer", "02-generation.feedback.case-feedback",
})


class SchemaContractError(ValueError):
    def __init__(self, reason, schema_id=None):
        super().__init__(reason)
        self.reason, self.schema_id = reason, schema_id

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

@traced("python")
def describe(schema_id):
    contract = CONTRACTS[resolve_schema_id(schema_id)]
    if schema_id == "dtt.feedback.request":
        contract = Contract(LegacyFeedbackRequest)
    schema = contract.model.model_json_schema()
    if schema_id == "dtt.feedback.request":
        schema["title"] = "FeedbackRequest"
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"urn:finarch:{schema_id}:v{contract.version}"
    return {"schema_id": schema_id, "version": contract.version,
            "readiness": contract.readiness, "pydantic_version": pydantic.__version__,
            "sha256": hashlib.sha256(canonical(schema)).hexdigest(), "schema": schema}


# [SC01] docs/02-architecture.md#SC01 The default response definition is rejected before calling based on the list of fixed LLM roles.
@traced("python")
def require_llm_schema(role, direction="response"):
    """Resolve a concrete object schema before any LLM handler/transport runs."""
    from finarch.shared.providers.roles import resolve_role
    role = resolve_role(role)
    if role not in LLM_ROLES:
        raise SchemaContractError("UNKNOWN_LLM_ROLE")
    if direction not in ("request", "response"):
        raise SchemaContractError("UNKNOWN_SCHEMA_DIRECTION")
    schema_id = resolve_schema_id(role + "." + direction)
    if schema_id not in CONTRACTS:
        raise SchemaContractError("MISSING_LLM_SCHEMA", schema_id)
    try:
        definition = describe(schema_id)
        schema = definition["schema"]
        if (not isinstance(schema, dict) or schema.get("type") != "object"
                or not isinstance(schema.get("properties"), dict)
                or not schema["properties"]):
            raise ValueError("CONCRETE_OBJECT_SCHEMA_REQUIRED")
    except Exception as error:
        raise SchemaContractError("INVALID_LLM_SCHEMA", schema_id) from error
    return definition

def export(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    index = []
    for schema_id in CONTRACTS:
        definition = describe(schema_id)
        filename = schema_filename(schema_id)
        (directory / filename).write_text(json.dumps(definition["schema"], ensure_ascii=False, indent=2) + "\n")
        index.append({k: v for k, v in definition.items() if k != "schema"} | {"file": filename})
    (directory / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    return index

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export derived, read-only JSON Schema files")
    parser.add_argument("--output", type=Path, required=True)
    export(parser.parse_args().output)
