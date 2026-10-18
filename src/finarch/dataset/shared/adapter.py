"""Deterministic helpers for adapters; never solve questions or infer units."""
from dataclasses import dataclass
from pathlib import Path
import re
from finarch.dataset.schemas.custom_input import IntermediateSample
from finarch.shared.reference import SourceFloat, extract_reference, load_raw


def input_run_directory(data_directory):
    """Pair data/prepared/<name> with reports/run/<name>/00-input.

    Standalone outputs outside a data tree use a sibling run/<name>/00-input.
    The same rule lets Preparation locate evidence without a pointer in data.
    """
    output = Path(data_directory).resolve()
    if output.name == 'data':
        raise ValueError('NAMED_DATA_OUTPUT_REQUIRED')
    for parent in output.parents:
        if parent.name == 'data':
            relative = output.relative_to(parent)
            if relative.parts[0] == 'prepared':
                relative = Path(*relative.parts[1:])
            if relative == Path('.'):
                raise ValueError('NAMED_DATA_OUTPUT_REQUIRED')
            return parent.parent / 'reports/run' / relative / '00-input'
    return output.parent / 'run' / output.name / '00-input'


@dataclass(frozen=True)
class Origin:
    source: str
    locator: str
    record: object
    index: int | None = None


@dataclass(frozen=True)
class RawSource:
    name: str
    path: Path
    content: bytes

    def json(self):
        """Retain JSON numeric tokens, including trailing decimal zeroes."""
        return load_raw(self.content)

    def text(self, encoding='utf-8'):
        return self.content.decode(encoding)

    def origin(self, record, *, locator, index=None):
        """Identify the original record; use a JSON pointer or an explicit row locator."""
        if not isinstance(locator, str) or not locator.strip():
            raise ValueError('SOURCE_LOCATOR_REQUIRED')
        if index is not None and (type(index) is not int or index < 0):
            raise ValueError('INVALID_SOURCE_INDEX')
        return Origin(self.name, locator, record, index)


@dataclass(frozen=True)
class ConvertedRecord:
    data: IntermediateSample
    origins: tuple[Origin, ...]


@dataclass(frozen=True)
class ExcludedRecord:
    reason: str
    origins: tuple[Origin, ...]


def make_record(*, question, context, reference_answer, origins):
    """Extract precision from the answer token, never from question wording.

    Numeric strings must contain only a JSON number. Dataset-specific currency,
    grouping or percent syntax needs an explicitly documented adapter rule.
    Ordinary Python floats are rejected because their original precision is lost.
    """
    if isinstance(reference_answer, str):
        if not re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?',
                            reference_answer):
            raise ValueError('ANSWER_MUST_BE_AN_UNAMBIGUOUS_NUMERIC_TOKEN')
        token = reference_answer
        reference_answer = load_raw(reference_answer)
    else:
        token = reference_answer.token if isinstance(reference_answer, SourceFloat) else str(reference_answer)
    reference = extract_reference(reference_answer)
    # Keep lexical distinctions such as 100 versus 1e2 without adding a type field.
    data = IntermediateSample(question=question, context=context,
                              reference_answer=token,
                              reference_precision=reference.reference_precision)
    return ConvertedRecord(data, tuple(origins))


def exclude(reason, *, origins):
    """Record an explicit unsupported source record instead of silently skipping it."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('EXCLUSION_REASON_REQUIRED')
    return ExcludedRecord(reason, tuple(origins))
