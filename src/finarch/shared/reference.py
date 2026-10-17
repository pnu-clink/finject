"""Reference type comes from the raw JSON token, never from an LLM guess.

Integer references use truncation toward zero. Float references use ROUND_HALF_UP
at the recorded number of decimal places. Intermediate calculations stay exact.
This module has been written for fin-arch; behavior tests await the PM interview.
"""

traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced

import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Literal


class SourceFloat(float):
    """Preserve 10.0 versus 10.00 while allowing source-record JSON serialization."""

    def __new__(cls, token: str):
        obj = super().__new__(cls, token)
        obj.token = token
        return obj


# [DP13-1] docs/02-architecture.md#DP13-1 So we save the JSON source token and move on to the exact digit extraction.
@traced("python")
def load_raw(text: str | bytes):
    def reject_constant(value):
        raise ValueError(f"NON_FINITE_SOURCE_NUMBER: {value}")
    return json.loads(text, parse_float=SourceFloat, parse_constant=reject_constant)


@dataclass(frozen=True)
class Reference:
    reference_answer: str
    reference_answer_type: Literal["integer", "float"]
    reference_precision: int

    def __post_init__(self):
        if self.reference_answer_type not in ("integer", "float"):
            raise ValueError("INVALID_REFERENCE_TYPE")
        if type(self.reference_precision) is not int or not 0 <= self.reference_precision <= 100:
            raise ValueError("INVALID_REFERENCE_PRECISION")
        value = Decimal(self.reference_answer)
        if not value.is_finite():
            raise ValueError("NON_FINITE_REFERENCE")
        if self.reference_answer_type == "integer" and (
            self.reference_precision != 0 or value != value.to_integral_value()
        ):
            raise ValueError("INVALID_INTEGER_REFERENCE")
        if max(0, -value.as_tuple().exponent) != self.reference_precision:
            raise ValueError("REFERENCE_PRECISION_MISMATCH")

    def fields(self):
        return asdict(self)


# [DP13] docs/02-architecture.md#DP13 So we extract the value, integer/float type, accuracy from the exact number of the source.
@traced("python")
def extract_reference(value) -> Reference:
    if type(value) is int:
        return Reference(str(value), "integer", 0)
    if not isinstance(value, SourceFloat):
        raise ValueError("REFERENCE_MUST_BE_RAW_JSON_NUMBER")
    number = Decimal(value.token)
    if not number.is_finite():
        raise ValueError("NON_FINITE_REFERENCE")
    precision = max(0, -number.as_tuple().exponent)
    return Reference(format(number, "f"), "float", precision)


# [N01] docs/02-architecture.md#N01 So, you can show the exact value as a cut or a ROUND_HALF_UP, depending on the source type and accuracy.
@traced("python")
def normalize(value: Fraction | str | int, reference: Reference) -> str:
    if isinstance(value, (float, bool)):
        raise ValueError("USE_EXACT_VALUE_NOT_BINARY_FLOAT")
    exact = Fraction(value)
    if reference.reference_answer_type == "integer":
        return str(int(exact))
    scale = 10 ** reference.reference_precision
    whole, remainder = divmod(abs(exact.numerator) * scale, exact.denominator)
    whole += int(2 * remainder >= exact.denominator)
    sign = "-" if exact < 0 and whole else ""
    if reference.reference_precision == 0:
        return sign + str(whole)
    integer, decimal = divmod(whole, scale)
    return f"{sign}{integer}.{decimal:0{reference.reference_precision}d}"


@traced("python")
def compare(value: Fraction | str | int, reference: Reference) -> dict:
    exact = Fraction(value) if not isinstance(value, (float, bool)) else value
    computed = normalize(value, reference)
    gold = normalize(reference.reference_answer, reference)
    return {"exact_value": str(exact), "computed": computed, "gold": gold,
            "matches": computed == gold, "normalized_matches": computed == gold,
            "exact_matches": exact == Fraction(reference.reference_answer), **reference.fields(),
            "policy": "truncate_toward_zero" if reference.reference_answer_type == "integer" else "ROUND_HALF_UP"}
