"""LLM response structures; these schemas do not constrain Python operators.

Roles still marked draft in the registry cannot be called. Final-text audit is defined.
"""
from typing import Annotated, Literal
from pydantic import Field, model_validator, JsonValue
from finarch.dataset.schemas.common import StrictModel, Text, Span
from finarch.dataset.schemas.prepared import AnswerMetadata

class Observation(StrictModel):
    context: Text
    question: Text

class ProgramAnswerMetadata(StrictModel):
    scale: str | None

class ProgramRequest(Observation):
    reference_answer_type: Literal['integer', 'float']
    reference_precision: Annotated[int, Field(ge=0, le=100)]
    answer_metadata: ProgramAnswerMetadata
    provider_record: dict[str, JsonValue] = Field(default_factory=dict, description="Source identifiers and mechanically extracted numeric spans; no reference answer")

class Fact(StrictModel):
    id: Text
    span: Span
    text: Text
    value: Text
    unit: Text | None
    origin: Literal['CONTEXT', 'QUESTION'] = 'CONTEXT'

class ExternalEvidence(StrictModel):
    id: Text
    source_title: Text
    source_url: Text
    locator: Text
    selected_value: Text
    selection_conditions: list[Text]
    assumptions: list[Text]
    application_note: Text

class LegacyProgramResponse(StrictModel):
    # Native structured output requires every field; old stored responses may omit the new empty list.
    model_config = {"json_schema_extra": lambda schema: schema.update(required=list(schema['properties']))}
    code: Text = Field(description="Python solution source; arithmetic operators are not restricted by this schema")
    facts: Annotated[list[Fact], Field(min_length=1)]
    grounding: Text = Field(description="Explanation of how the cited facts support the solution")
    external_evidence: list[ExternalEvidence] = Field(default_factory=list, description="Reviewed catalog IDs used by evidence(id, selectors...) and explicit application assumptions; empty if none")

    @model_validator(mode="after")
    def unique_fact_ids(self):
        if len({fact.id for fact in self.facts}) != len(self.facts):
            raise ValueError("DUPLICATE_FACT_ID")
        return self


CalculationSource = Literal['IN_CONTEXT_DATA', 'EXTERNAL_RULE', 'EXTERNAL_DATA']

class CalculationSourceUsage(StrictModel):
    id: Text
    kind: CalculationSource
    description: Text
    fact_ids: list[Text] = Field(description="Numeric fact references. May be empty for a supplied textual instruction/condition with an exact Q/C quote; numeric operands still require facts.")
    evidence_ids: list[Text]
    acquisition: Literal['SUPPLIED', 'MODEL_KNOWLEDGE', 'RETRIEVED', 'UNAVAILABLE']
    source_title: Text | None
    source_url: Text | None
    locator: Text | None
    quote: Text | None
    applicability: Text
    code_lines: Annotated[list[Annotated[int, Field(ge=1)]], Field(min_length=1)]
    output_variables: Annotated[list[Text], Field(min_length=1)]

class ProgramResponse(LegacyProgramResponse):
    """POT v4: Internal/External Context usage, not a verified sufficiency verdict."""
    facts: list[Fact]
    calculation_input_sources: list[CalculationSource]
    source_usage: list[CalculationSourceUsage]

    @model_validator(mode='after')
    def provenance_links(self):
        import ast
        features = self.calculation_input_sources
        if len(features) != len(set(features)):
            raise ValueError('DUPLICATE_CALCULATION_SOURCE')
        if set(features) != {item.kind for item in self.source_usage}:
            raise ValueError('CALCULATION_SOURCE_USAGE_MISMATCH')
        ids = [item.id for item in self.source_usage]
        if len(ids) != len(set(ids)):
            raise ValueError('DUPLICATE_SOURCE_USAGE_ID')
        facts = {item.id for item in self.facts}
        evidence = {item.id for item in self.external_evidence}
        if len(evidence) != len(self.external_evidence):
            raise ValueError('DUPLICATE_EXTERNAL_EVIDENCE_ID')
        try:
            tree = ast.parse(self.code)
        except SyntaxError as error:
            raise ValueError('POT_SYNTAX_ERROR: ' + str(error)) from error
        assigned = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                assigned.setdefault(node.id, set()).add(node.lineno)
        used_facts = set()
        for item in self.source_usage:
            if not set(item.fact_ids) <= facts or not set(item.evidence_ids) <= evidence:
                raise ValueError('UNKNOWN_PROVENANCE_REFERENCE')
            used_facts.update(item.fact_ids)
            if any(line > len(self.code.splitlines()) for line in item.code_lines):
                raise ValueError('PROVENANCE_CODE_LINE_OUT_OF_RANGE')
            if any(not (assigned.get(name, set()) & set(item.code_lines)) for name in item.output_variables):
                raise ValueError('PROVENANCE_VARIABLE_LINE_MISMATCH')
            if item.kind == 'IN_CONTEXT_DATA':
                if item.acquisition != 'SUPPLIED' or (not item.fact_ids and not (item.quote and item.quote.strip())):
                    raise ValueError('SUPPLIED_FACT_REFERENCE_REQUIRED')
            elif item.acquisition == 'SUPPLIED':
                raise ValueError('EXTERNAL_SOURCE_MARKED_SUPPLIED')
            if item.acquisition == 'RETRIEVED' and not all((item.source_url, item.source_title, item.locator, item.quote)):
                raise ValueError('RETRIEVED_SOURCE_DETAILS_REQUIRED')
            if item.kind == 'EXTERNAL_DATA' and item.acquisition == 'MODEL_KNOWLEDGE':
                raise ValueError('EXTERNAL_DATA_REQUIRES_RETRIEVAL_OR_UNAVAILABLE')
        if facts != used_facts:
            raise ValueError('FACT_PROVENANCE_MISSING')
        return self


class KnowledgeTrigger(StrictModel):
    origin: Literal['QUESTION', 'CONTEXT']
    quote: Text
    span: Span

class FormulaBinding(StrictModel):
    symbol: Text
    code_variable: Text
    meaning: Text

class ExternalKnowledgeRequirement(StrictModel):
    id: Text
    tag: Literal['EXTERNAL_RULE', 'EXTERNAL_DATA']
    source_usage_id: Text
    triggers: Annotated[list[KnowledgeTrigger], Field(min_length=1)]
    why_external: Text
    definition: Text
    formula: Text | None
    bindings: list[FormulaBinding]
    data_requirements: list[Text]
    unit: Text | None

class ProgramResponseV5(ProgramResponse):
    external_knowledge_requirements: list[ExternalKnowledgeRequirement]

    @model_validator(mode='after')
    def requirement_links(self):
        import ast
        usages={u.id:u for u in self.source_usage}
        assigned={n.id for n in ast.walk(ast.parse(self.code)) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
        requirements=self.external_knowledge_requirements
        if len({r.id for r in requirements})!=len(requirements):
            raise ValueError('DUPLICATE_KNOWLEDGE_REQUIREMENT')
        for r in requirements:
            if r.source_usage_id not in usages or usages[r.source_usage_id].kind!=r.tag:
                raise ValueError('KNOWLEDGE_SOURCE_USAGE_MISMATCH')
            if r.tag=='EXTERNAL_RULE' and not r.formula:
                raise ValueError('EXTERNAL_RULE_FORMULA_REQUIRED')
            if r.tag=='EXTERNAL_DATA' and not r.data_requirements:
                raise ValueError('EXTERNAL_DATA_DEFINITION_REQUIRED')
            if any(t.span[0]>=t.span[1] for t in r.triggers):
                raise ValueError('INVALID_KNOWLEDGE_TRIGGER_SPAN')
            if any(b.code_variable not in assigned for b in r.bindings):
                raise ValueError('UNKNOWN_FORMULA_VARIABLE')
        if {r.source_usage_id for r in requirements}!={u.id for u in self.source_usage if u.kind in ('EXTERNAL_RULE','EXTERNAL_DATA')}:
            raise ValueError('EXTERNAL_KNOWLEDGE_REQUIREMENT_MISSING')
        return self


def check_knowledge_triggers(program, question, context):
    for requirement in program.get('external_knowledge_requirements', []):
        for trigger in requirement['triggers']:
            text=question if trigger['origin']=='QUESTION' else context
            start,end=trigger['span']
            if not 0 <= start < end <= len(text) or text[start:end]!=trigger['quote']:
                raise ValueError('KNOWLEDGE_TRIGGER_QUOTE_MISMATCH:'+requirement['id'])


def executable_program(response):
    """P01N: normalize a validated response list to the runtime's named lookup."""
    # Historical v3 artifacts remain readable without inventing provenance.
    model = ProgramResponse if 'calculation_input_sources' in response or 'source_usage' in response else LegacyProgramResponse
    if 'external_knowledge_requirements' in response:model=ProgramResponseV5
    checked=model.model_validate(response).model_dump()
    return {**checked,'facts':{fact['id']:{k:v for k,v in fact.items() if k!='id'}
                               for fact in checked['facts']}}

class Patch(StrictModel):
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(ge=0)]
    before: str
    text: str
    element_ids: Annotated[list[Text], Field(min_length=1)]

    @model_validator(mode="after")
    def ordered(self):
        if self.start > self.end:
            raise ValueError("REVERSED_PATCH_SPAN")
        return self

class RealizationResponse(StrictModel):
    patches: Annotated[list[Patch], Field(min_length=1)]

class RealizationSlot(Patch):
    kind: Literal["VALUE", "SOURCE_A", "SOURCE_B", "RELATION", "EA"]
    instruction: Text
    exact_text: str | None
    required_prefix: str
    allowed_numbers: list[str]

class RealizationRequest(Observation):
    """Internal input projection; only the response schema is sent to the LLM."""
    axis: Literal["IC_VALUE", "IC_SOURCE", "IC_RELATION", "EA"]
    python_code: Text
    graph_structure: Annotated[list[dict[str, JsonValue]], Field(min_length=1)]
    edit_slots: Annotated[list[RealizationSlot], Field(min_length=1)]
    instructions: Annotated[list[Text], Field(min_length=1)]
    tagged_context: str | None

class AnswerResponse(StrictModel):
    text: Text = Field(description="Answer in natural language; no forced answer label or count")

class LegacyInverseReview(StrictModel):
    variable_id: Text
    state: Literal["RECOVERABLE", "NOT_RECOVERABLE", "UNKNOWN"]
    evidence: list[Text]
    proposed_path: str
    reason: Text

class LegacyInverseResponse(StrictModel):
    reviews: Annotated[list[LegacyInverseReview], Field(min_length=1)]

from finarch.dataset.schemas.ea_inverse_review import InverseReview, InverseResponse

class SourceAnnotation(StrictModel):
    side: Literal["A", "B"]
    text: Text
    reason: Text

class SourceResponse(StrictModel):
    source_annotations: Annotated[list[SourceAnnotation], Field(min_length=1, max_length=1)]

AuditCriterion = Literal["preservation", "planned_change", "scope", "source_assignment",
                         "unplanned_content", "readability", "explicit_resolution", "ea_consistency"]
LEGACY_AUDIT_CRITERIA = ("preservation", "planned_change", "scope", "source_assignment",
                  "unplanned_content", "readability", "explicit_resolution", "ea_consistency")

class AuditEvidence(StrictModel):
    field: Literal["original_context", "context", "question"]
    quote: Text

class AuditRequest(Observation):
    reference_answer: str | None = None
    reference_answer_type: Literal['integer', 'float'] | None = None
    reference_precision: int | None = Field(default=None, ge=0, le=100)

    """Private production audit, distinct from the C/Q-only independent answer."""
    original_context: Text
    axis: Literal["ANSWER", "IC_VALUE", "IC_SOURCE", "IC_RELATION", "EA"]
    intent: dict[str, JsonValue]
    edits: list[Patch]
    recovery_review: Literal["DEFERRED_BY_USER", "SEPARATE_LLM_ANNOTATION"]

class AuditFinding(StrictModel):
    criterion: AuditCriterion
    judgment: Literal["PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"]
    reason: Text
    evidence: list[AuditEvidence]

class LegacyAuditResponse(StrictModel):
    findings: Annotated[list[AuditFinding], Field(min_length=8, max_length=8)]
    observed_state: Literal["CONFLICT", "MISSING_TARGET_EVIDENCE", "ANSWERABLE", "RESOLVED", "MIXED", "UNKNOWN"]
    state_reason: Text
    state_evidence: Annotated[list[AuditEvidence], Field(min_length=1)]

    @model_validator(mode="after")
    def all_criteria_once(self):
        if {f.criterion for f in self.findings} != set(LEGACY_AUDIT_CRITERIA):
            raise ValueError("AUDIT_CRITERIA_MISSING_OR_DUPLICATED")
        return self


AUDIT_CRITERIA = ("planned_change", "unintended_change", "readability")

class CompactAuditFinding(StrictModel):
    criterion: Literal["planned_change", "unintended_change", "readability"]
    judgment: Literal["PASS", "FAIL", "UNKNOWN"]
    reason: str = Field(description="Empty for PASS; a concrete English explanation for FAIL or UNKNOWN.")

    @model_validator(mode="after")
    def failure_needs_reason(self):
        if self.judgment != "PASS" and not self.reason.strip():
            raise ValueError("AUDIT_REASON_REQUIRED")
        return self

class AuditResponse(StrictModel):
    findings: Annotated[list[CompactAuditFinding], Field(min_length=3, max_length=3)]

    @model_validator(mode="after")
    def all_criteria_once(self):
        if {f.criterion for f in self.findings} != set(AUDIT_CRITERIA):
            raise ValueError("AUDIT_CRITERIA_MISSING_OR_DUPLICATED")
        return self
