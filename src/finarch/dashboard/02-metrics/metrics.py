"""Extract recorded metrics without estimating missing values or timestamps."""
import math
import re
from datetime import datetime, timezone

ISO_DATETIME = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}"
    r"(?::[0-9]{2}(?:[.,][0-9]+)?)?"
    r"(?P<zone>Z|[+-](?:[01][0-9]|2[0-3])(?::?[0-5][0-9])?)?\Z"
)
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

def _number(value, *, integer=False):
    if type(value) not in ((int,) if integer else (int, float)):
        return None
    if value < 0 or (type(value) is float and not math.isfinite(value)):
        return None
    return value


def _metrics(result: dict | None) -> dict:
    result = result if isinstance(result, dict) else {}
    usage = result.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    output_details = usage.get("output_tokens_details")
    output_details = output_details if isinstance(output_details, dict) else {}
    if "reasoning_tokens" in output_details:
        reasoning = output_details["reasoning_tokens"]
    elif "reasoning_tokens" in usage:
        reasoning = usage["reasoning_tokens"]
    else:
        reasoning = usage.get("reasoning_output_tokens")
    return {
        "elapsed_seconds": _number(result.get("elapsed_seconds")),
        "input_tokens": _number(usage.get("input_tokens"), integer=True),
        "output_tokens": _number(usage.get("output_tokens"), integer=True),
        "reasoning_tokens": _number(reasoning, integer=True),
        "cost_estimate_usd": _number(result.get("token_cost_estimate_usd")),
    }


def _timing(result: dict | None) -> tuple[dict, list[str]]:
    """Use recorded ISO timestamps only; never infer dates from elapsed or mtime."""
    result = result if isinstance(result, dict) else {}
    timing = {"started_at": None, "ended_at": None,
              "started_epoch_ms": None, "ended_epoch_ms": None}
    dates, warnings = {}, []
    for field, epoch_field in (("started_at", "started_epoch_ms"), ("ended_at", "ended_epoch_ms")):
        value = result.get(field)
        if value is None:
            continue
        match = ISO_DATETIME.fullmatch(value) if isinstance(value, str) else None
        if match is None:
            warnings.append("TIMING_" + field.upper() + "_INVALID")
            continue
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if match.group("zone") is None or date.utcoffset() is None:
                warnings.append("TIMING_" + field.upper() + "_TIMEZONE_MISSING")
                continue
            date = date.astimezone(timezone.utc)
            delta = date - EPOCH
        except (ValueError, OverflowError):
            warnings.append("TIMING_" + field.upper() + "_INVALID")
            continue
        timing[field] = value
        timing[epoch_field] = (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000
        dates[field] = date
    if len(dates) == 2 and dates["ended_at"] < dates["started_at"]:
        warnings.append("TIMING_END_BEFORE_START")
    return timing, warnings


