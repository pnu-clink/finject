"""Model boundary: send schema, preserve raw response, validate before returning.

No provider transport is connected here. The caller supplies a transport that
accepts response_schema and explicitly declares how it passes it to its model.
"""

traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced
from pydantic import ValidationError
from finarch.dataset.schemas.failure_interpretation import ROLE, TRANSLATION_ROLE
from finarch.dataset.schemas.ea_inverse_review import ROLE as INVERSE_ROLE
from finarch.dataset.schemas.registry import require_llm_schema, SchemaContractError
from finarch.dataset.schemas.validation import validate, parse_json_object
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult


class ProviderFailure(RuntimeError):
    """An adapter's controlled, credential-free failure code."""


@traced("llm")
def complete(role, model_input, *, transport, save, schema_mode, before_validate=None):
    """transport returns raw JSON text. save writes immutable call-local artifacts.

    For draft roles this fails before transport. No schema or transport retries.
    Input projection for other roles must be added by their production adapters;
    this wrapper does not accept an entire private case as a model prompt.
    """
    # [SC08] docs/02-architecture.md#SC08 The default error is recorded in the corresponding except of complete.
    def stop_before_call(reason, status="FAIL", **details):
        save("03-result/schema-check.json", {"status": status, "reason": reason, "role": role,
                                  "phase": "before_call", "transport_invoked": False, **details})
        return StepResult(status, reason)

    # [SC02] docs/02-architecture.md#SC02 Check the response definition and setup status and existing internal input contracts and save the request.
    if schema_mode not in ("native", "prompt"):
        return stop_before_call("EXPLICIT_SCHEMA_MODE_REQUIRED")
    try:
        definition = require_llm_schema(role)
    except SchemaContractError as error:
        return stop_before_call(error.reason, schema_id=error.schema_id)
    schema_id = definition["schema_id"]
    save("01-input/response-schema.json", definition)
    if definition["readiness"] != "defined":
        return stop_before_call("Role schema semantics not finalized.", "NOT_IMPLEMENTED")
    # POT authors and standalone C/Q answers have defined model-input contracts.
    # Other roles must not silently serialize internal case/graph/provenance packets.
    if role not in (INVERSE_ROLE, ROLE, TRANSLATION_ROLE, "01-preparation.05-verification.semantic", "shared.01-06.02-04.exception-handler", "01-preparation.03-calculation.pot", "dtt.answer", "02-generation.02-generate-text.realization", "shared.01-02.02-03.review-and-validation", "02-generation.feedback.case-feedback", "01-preparation.02-review-and-correct.revision", "01-preparation.03-calculation.review-answer-evidence"):
        return stop_before_call("Role model-input projection not connected.", "NOT_IMPLEMENTED")
    try:
        request_definition = require_llm_schema(role, "request")
    except SchemaContractError as error:
        return stop_before_call(error.reason, schema_id=error.schema_id)
    save("01-input/request-schema.json", request_definition)
    if request_definition["readiness"] != "defined":
        return stop_before_call("Role request schema semantics not finalized.", "NOT_IMPLEMENTED")
    try:
        validate(role + ".request", model_input)
    except ValidationError as error:
        return stop_before_call("INPUT_SCHEMA_INVALID",
                                errors=error.errors(include_input=False, include_url=False, include_context=False))
    save("01-input/model-request.json", {"role": role, "input": model_input, "schema_mode": schema_mode,
                                "response_schema": definition})
    try:
        # [SC03] docs/02-architecture.md#SC03 The input and response schemes are sent to the input transport, and the requested schemes are not sent.
        raw = transport(role=role, payload=model_input, response_schema=definition["schema"],
                        schema_mode=schema_mode)
    except Exception as error:
        # Transport exception messages may contain credentials; retain only the type here.
        reason = str(error) if isinstance(error, ProviderFailure) else "PROVIDER_ERROR"
        save("03-result/schema-check.json", {"status": "FAIL", "reason": reason,
                                  "error_type": type(error).__name__})
        return StepResult("FAIL", reason)
    # [SC04] docs/02-architecture.md#SC04 The returned source is preserved before the passing-schema test.
    save("02-raw-response.json", {"text": raw})
    try:
        # [SC05] docs/02-architecture.md#SC05 It's a JSON object passing task and it rejects duplicate key, unlimited number, and grammar errors.
        value = parse_json_object(raw)
    except (ValueError, TypeError) as error:
        save("03-result/schema-check.json", {"status": "FAIL", "reason": "RESPONSE_JSON_INVALID",
                                  "error": str(error)})
        return StepResult("FAIL", "RESPONSE_JSON_INVALID")
    if before_validate is not None:
        # Diagnostic artifacts never turn an invalid response into a PASS.
        before_validate(value)
    try:
        validate(schema_id, value)
    except ValidationError as error:
        save("03-result/schema-check.json", {"status": "FAIL", "reason": "RESPONSE_SCHEMA_INVALID",
                                  "errors": error.errors(include_input=False, include_url=False, include_context=False)})
        return StepResult("FAIL", "RESPONSE_SCHEMA_INVALID")
    # [SC07] docs/02-architecture.md#SC07 The answer format returns the PASS record and data and does not determine the meaning of the correct answer.
    save("03-result/schema-check.json", {"status": "PASS", "schema_sha256": definition["sha256"]})
    return StepResult("PASS", "Response schema validated; no semantic judgment implied.", value)
