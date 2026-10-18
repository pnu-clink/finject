"""Deterministic helpers for adapters; never solve questions or infer units."""
from dataclasses import dataclass
from pathlib import Path
import re
from finarch.dataset.schemas.custom_input import IntermediateSample
from finarch.shared.reference import extract_reference, load_raw


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


def make_record(*, q, c, a, origins):
    """Extract precision from the answer token, never from question wording.

    Numeric strings must contain only a JSON number. Dataset-specific currency,
    grouping or percent syntax needs an explicitly documented adapter rule.
    Ordinary Python floats are rejected because their original precision is lost.
    """
    if isinstance(a, str):
        if not re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', a):
            raise ValueError('ANSWER_MUST_BE_AN_UNAMBIGUOUS_NUMERIC_TOKEN')
        a = load_raw(a)
    reference = extract_reference(a)
    data = IntermediateSample(q=q, c=c, a=reference.reference_answer,
                              a_type=reference.reference_answer_type,
                              a_precision=reference.reference_precision)
    return ConvertedRecord(data, tuple(origins))


def exclude(reason, *, origins):
    """Record an explicit unsupported source record instead of silently skipping it."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('EXCLUSION_REASON_REQUIRED')
    return ExcludedRecord(reason, tuple(origins))
