"""Read frozen requests and raw responses; report stability without semantic scoring.

Run with the project virtual environment. No provider adapter is imported and no
source artifact is changed. Numeric comparisons already recorded by a run remain
the scoring authority; additional numeric observations never replace that score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from jsonschema import Draft202012Validator

METHOD = "stability-review-v3-contract-specific-precision"
from finarch.paths import PROJECT as ROOT
FIXED_DECIMAL_CONTRACT = "FinancialAnswerMagnitudeV4"
NUMERIC_ROUNDING_CONTRACT = "FinancialAnswerV6"
VARIANTS = ("ORIGINAL", "IC_VALUE_01_BEFORE", "IC_VALUE_01_AFTER",
            "IC_SOURCE_A_ONLY", "IC_SOURCE_B_ONLY", "IC_RELATION_01", "EA_01", "EA_02")
NAMES = dict(zip(VARIANTS, ("Original", "IC-value-before", "IC-value-after",
             "IC-source-before", "IC-source-after", "IC-relation", "EA-01", "EA-02")))
NUMBER = r"[+\-−]?\s*\$?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
EQUATION_RHS = re.compile(r"=\s*(" + NUMBER + r")")
NEGATIVE_MENTION = re.compile(r"(?:\bnegative\s+\$?\s*|[−-]\s*\$?\s*)(\d[\d,]*(?:\.\d+)?)", re.I)
NO_COMMITMENT = re.compile(
    r"\b(?:cannot|can't|unable to)\s+(?:be\s+)?(?:determin\w*|calculat\w*|comput\w*|answer\w*|provid\w*|establish\w*)"
    r"|\b(?:no|not a|not one)\s+(?:unique|single|definitive|unambiguous)\s+(?:answer|result|value)"
    r"|\b(?:insufficient|not enough)\s+(?:information|data|evidence)"
    r"|\b(?:I\s+)?(?:must\s+|therefore\s+)?abstain\b", re.I)


def load(path):
    return json.loads(Path(path).read_text())


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def path_label(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(Path(path).resolve())


def decimal(value):
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except InvalidOperation:
        return None


def normalized(number):
    return format(number.normalize(), "f") if number is not None else None


def signed_answer(response):
    if not isinstance(response, dict):
        return None
    number = decimal(response.get("answer"))
    if number is None:
        return None
    if "status" in response:
        sign = response.get("answer_meta", {}).get("negative")
        if type(sign) is not bool:
            return None
        return -abs(number) if sign else abs(number)
    return number


def raw_text(raw):
    if isinstance(raw, list):
        return "".join(event.get("item", {}).get("text", "") for event in raw
                       if event.get("type") == "item.completed"
                       and event.get("item", {}).get("type") == "agent_message")
    if isinstance(raw, dict):
        return "".join(part.get("text", "") for item in raw.get("output", [])
                       if item.get("type") == "message" for part in item.get("content", [])
                       if part.get("type") == "output_text")
    return ""


def parse_strict(text):
    duplicates = []

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                duplicates.append(key)
            result[key] = value
        return result

    def reject(value):
        raise ValueError("NON_FINITE_JSON_NUMBER:" + value)

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("NON_FINITE_JSON_NUMBER:" + value)
        return number

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=reject, parse_float=finite_float)
        return value, duplicates, None
    except (ValueError, TypeError) as error:
        return None, duplicates, str(error)


def precision_conflict(request):
    words = dict(zip(("zero", "one", "two", "three", "four", "five", "six",
                      "seven", "eight", "nine", "ten"), range(11)))
    question = request["input"]["question"].lower()
    hints = {0} if "nearest integer" in question else set()
    for token in re.findall(r"\b(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten) decimal places?\b", question):
        hints.add(int(token) if token.isdigit() else words[token])
    supplied = request["input"].get("answer_format", {}).get("decimal_places")
    return {"question": sorted(hints), "metadata": supplied} if hints and hints != {supplied} else None


def saved_precision_tags(errors, schema_title):
    """Classify saved precision errors without rechecking or changing answers."""
    tags = set()
    for error in errors:
        if not isinstance(error, dict) or error.get("path") != ["answer"]:
            continue
        message = error.get("message", "")
        if (schema_title == FIXED_DECIMAL_CONTRACT and error.get("rule") == "answer_format"
                and isinstance(message, str) and re.fullmatch(
                    r"Use an unsigned decimal string with exactly \d+ decimal places; no symbols or separators\.", message)):
            tags.add("SAVED_DECIMAL_PLACES_FAILURE")
        if (schema_title == NUMERIC_ROUNDING_CONTRACT
                and error.get("rule") == "representation_consistency"
                and message == "The numeric value must be rounded to the supplied decimal_places; trailing zeros are optional."):
            tags.add("SAVED_NUMERIC_ROUNDING_FAILURE")
    return sorted(tags)


def observations(response, request):
    """Return literal and lexical observations, never an answerability verdict."""
    tags, details = [], {}
    if not isinstance(response, dict):
        return ["NO_RESPONSE_OBJECT"], details
    answer, meta = response.get("answer"), response.get("answer_meta", {})
    value = signed_answer(response)
    answer_observed = "answer" in response
    null = answer_observed and answer is None
    tags.append(("NULL_ANSWER" if null else "NON_NULL_ANSWER") if answer_observed else "MISSING_ANSWER_FIELD")
    if value is not None:
        tags.append("NUMERIC_FIELD_PRESENT")
    if response.get("status") == "abstained":
        tags.append("RAW_DECLARED_ABSTENTION")
        if answer_observed and not null:
            tags.append("DECLARED_ABSTENTION_WITH_NON_NULL_ANSWER")
            if value == 0:
                tags.append("DECLARED_ABSTENTION_WITH_ZERO")
        if meta.get("negative") is not None:
            tags.append("DECLARED_ABSTENTION_WITH_NON_NULL_SIGN")
    if "status" not in response:
        if null and meta.get("negative") is not None:
            tags.append("NULL_ANSWER_WITH_NON_NULL_SIGN")
        if value is not None and type(meta.get("negative")) is bool and meta["negative"] != (value < 0):
            tags.append("SIGNED_NUMBER_METADATA_DISAGREE")
    evidence = response.get("evidence")
    if isinstance(evidence, list):
        if not evidence:
            tags.append("EMPTY_EVIDENCE")
        payload = request["input"]
        exact = [isinstance(quote, str) and (quote in payload["context"] or quote in payload["question"])
                 for quote in evidence]
        details["evidence_exact_matches"] = exact
        if not all(exact):
            tags.append("EVIDENCE_NOT_EXACT_SUBSTRING")
        if any(quote == "" for quote in evidence):
            tags.append("EMPTY_EVIDENCE_QUOTE")
    explanation = response.get("explanation", "")
    if isinstance(explanation, str):
        if not explanation.strip():
            tags.append("EMPTY_EXPLANATION")
        cues = [match.group(0) for match in NO_COMMITMENT.finditer(explanation)]
        details["no_commitment_cue_spans"] = cues
        if cues:
            tags.append("EXPLANATION_NO_COMMITMENT_CUE")
            if value is not None:
                tags.append("NUMERIC_FIELD_WITH_NO_COMMITMENT_CUE")
        rhs = [decimal(re.sub(r"[\s,$]", "", match.group(1)).replace("−", "-"))
               for match in EQUATION_RHS.finditer(explanation)]
        rhs = [number for number in rhs if number is not None]
        details["equation_rhs_numbers"] = [normalized(number) for number in rhs]
        if value is not None and rhs and all(number != value for number in rhs):
            tags.append("ANSWER_ABSENT_FROM_EQUATION_RHS_CANDIDATE")
        negative_mentions = [decimal(match.group(1).replace(",", ""))
                             for match in NEGATIVE_MENTION.finditer(explanation)]
        if value is not None and value > 0 and any(number == value for number in negative_mentions):
            tags.append("POSITIVE_ANSWER_WITH_SAME_NEGATIVE_NUMBER_CANDIDATE")
    return sorted(set(tags)), details


def numeric_selection(value, private):
    """Compare reported coefficients to stored anchors, not to semantic answers."""
    if value is None:
        return "NO_NUMERIC_FIELD"
    reference = decimal(private.get("reference", {}).get("reference_answer"))
    alternative = decimal(private.get("alternative_answer"))
    same_ref, same_alt = value == reference, alternative is not None and value == alternative
    if same_ref and same_alt:
        return "BOTH_ANCHORS_EQUAL"
    if same_ref:
        return "REFERENCE_COEFFICIENT"
    if same_alt:
        return "ALTERNATIVE_COEFFICIENT"
    return "OTHER_COEFFICIENT"


def read_run(root, model=None):
    root = Path(root).resolve()
    candidates = sorted(root.glob("*/03-results/results.jsonl"))
    if model is None:
        if len(candidates) != 1:
            raise ValueError("MODEL_REQUIRED_FOR_MULTIPLE_OR_MISSING_RESULTS")
        model = candidates[0].parents[1].name
    request_path = root / model / "01-requests/manifest.jsonl"
    result_path = root / model / "03-results/results.jsonl"
    requests, results = read_rows(request_path), read_rows(result_path)
    private = {row["item_id"]: row for row in read_rows(root / "01-input/private.jsonl")}
    public = {row["item_id"]: row for row in read_rows(root / "01-input/public.jsonl")}
    counts = Counter(row["trial_id"] for row in results)
    if any(count != 1 for count in counts.values()):
        raise ValueError("DUPLICATE_RESULT_TRIAL_ID")
    if len({r["trial_id"] for r in requests}) != len(requests):
        raise ValueError("DUPLICATE_REQUEST_TRIAL_ID")
    result_map = {row["trial_id"]: row for row in results}
    if set(result_map) - {r["trial_id"] for r in requests}:
        raise ValueError("RESULT_WITHOUT_PLANNED_REQUEST")
    hashes = {path_label(path): sha(path) for path in
              (request_path, result_path, root / "01-input/private.jsonl", root / "01-input/public.jsonl")}
    validators, output = {}, []
    for request in requests:
        trial = request["trial_id"]
        row = result_map.get(trial, {})
        item = private[request["item_id"]]
        result_file = root / row["result_path"] if row.get("result_path") else None
        result = load(result_file) if result_file and result_file.exists() else {}
        raw_file = result_file.with_name("raw-response.json") if result_file else None
        raw, envelope_error = None, None
        if raw_file and raw_file.exists():
            try:
                raw = load(raw_file)
            except (ValueError, UnicodeError) as error:
                envelope_error = str(error)
        if result_file and result_file.exists():
            hashes[path_label(result_file)] = sha(result_file)
        if raw_file and raw_file.exists():
            hashes[path_label(raw_file)] = sha(raw_file)
        parsed, duplicates, parse_error = parse_strict(raw_text(raw))
        response = parsed if isinstance(parsed, dict) else result.get("response")
        schema = request.get("response_schema")
        if not isinstance(schema, dict) or not schema:
            raise ValueError("MISSING_FROZEN_RESPONSE_SCHEMA:" + trial)
        schema_hash = digest(schema)
        if schema_hash not in validators:
            Draft202012Validator.check_schema(schema)
            validators[schema_hash] = Draft202012Validator(schema)
        schema_errors = [{"path": list(error.absolute_path), "rule": error.validator,
                          "message": error.message} for error in validators[schema_hash].iter_errors(parsed)]
        tags, details = observations(response, request)
        conflict = precision_conflict(request)
        if conflict:
            tags.append("QUESTION_METADATA_PRECISION_CONFLICT")
        tags.extend(saved_precision_tags(result.get("schema_errors", row.get("schema_errors", [])),
                                         schema.get("title")))
        if parse_error:
            tags.append("RAW_JSON_PARSE_FAILURE")
        if envelope_error:
            tags.append("RAW_PROVIDER_ENVELOPE_PARSE_FAILURE")
        if duplicates:
            tags.append("DUPLICATE_JSON_KEYS")
        if schema_errors:
            tags.append("RAW_JSON_SCHEMA_FAILURE")
        raw_matches = parsed == result.get("response") if parse_error is None else None
        if raw_matches is False:
            tags.append("RAW_SAVED_RESPONSE_DIFFER")
        value = signed_answer(response)
        status = row.get("status", "NOT_COLLECTED")
        comparison = row.get("checks", {}).get("numeric_comparison")
        if request["variant"] == "ORIGINAL":
            if status != "VALID":
                outcome = "FORMAT_OR_COLLECTION_FAILURE"
            elif comparison:
                outcome = "NUMERIC_MATCH" if comparison["matches"] else "NUMERIC_MISMATCH"
            elif isinstance(response, dict) and "answer" in response and response["answer"] is None:
                outcome = "VALID_NULL_ANSWER"
            else:
                outcome = "NOT_NUMERICALLY_EVALUATED"
        else:
            outcome = "SEMANTIC_NOT_SCORED"
        qc = {name: request["input"][name] for name in ("question", "context")}
        usage = result.get("usage") or {}
        cache_details = usage.get("input_tokens_details") or {}
        payload_matches = all(public[request["item_id"]][name] == qc[name] for name in qc)
        if not payload_matches:
            tags.append("PUBLIC_REQUEST_QC_DIFFER")
        output.append({"run_id": root.name, "model": model,
                       **{name: request[name] for name in ("trial_id", "item_id", "case", "variant", "prompt_condition", "reasoning")},
                       "saved_status": status, "original_outcome": outcome,
                       "transport": row.get("transport", result.get("transport")),
                       "cache_read_tokens": cache_details.get("cached_tokens", usage.get("cached_input_tokens")),
                       "cache_write_tokens": cache_details.get("cache_write_tokens", usage.get("cache_write_input_tokens")),
                       "schema_title": schema.get("title"), "raw_json_parse_ok": parse_error is None,
                       "raw_provider_envelope_error": envelope_error,
                       "raw_json_parse_error": parse_error, "duplicate_json_keys": duplicates,
                       "raw_schema_valid": not schema_errors and parse_error is None,
                       "raw_schema_errors": schema_errors, "raw_matches_saved_response": raw_matches,
                       "response": response, "response_fingerprint": digest(response) if response is not None else None,
                       "response_object_observed": isinstance(response, dict),
                       "answer_field_observed": isinstance(response, dict) and "answer" in response,
                       "signed_numeric_field": normalized(value),
                       "answer_is_null": response["answer"] is None if isinstance(response, dict) and "answer" in response else None,
                       "numeric_selection_observation": ("RESPONSE_NOT_OBSERVED" if not isinstance(response, dict)
                                                         else "ANSWER_FIELD_MISSING" if "answer" not in response
                                                         else numeric_selection(value, item)),
                       "saved_numeric_comparison": comparison, "saved_schema_errors": result.get("schema_errors", row.get("schema_errors", [])),
                       "saved_all_quotes_present": row.get("checks", {}).get("all_quotes_present"),
                       "precision_conflict": conflict,
                       "baseline_qc_matches_generation_reference": item.get("baseline_qc_matches_generation_reference"),
                       "qc_sha256": digest(qc), "input_sha256": digest(request["input"]),
                       "prompt_sha256": digest(request["prompt"]), "schema_sha256": schema_hash,
                       "raw_path": path_label(raw_file) if raw_file else None,
                       "result_path": path_label(result_file) if result_file else None,
                       "call_path": path_label(root / row["call_path"]) if row.get("call_path") else None,
                       "tags": sorted(set(tags)), "details": details})
    return {"root": root, "model": model, "rows": output, "private": private,
            "public": public, "hashes": hashes, "planned": len(requests)}


def counts_for(rows):
    tags = Counter(tag for row in rows for tag in row["tags"])
    return {"planned": len(rows), "saved_status": dict(Counter(row["saved_status"] for row in rows)),
            "schema_titles": dict(Counter(row.get("schema_title") or "UNKNOWN" for row in rows)),
            "response_objects_observed": sum(isinstance(row.get("response"), dict) for row in rows),
            "response_objects_not_observed": sum(not isinstance(row.get("response"), dict) for row in rows),
            "transport_counts": dict(Counter(row.get("transport") or "UNKNOWN" for row in rows)),
            "cache_read_tokens_observed_sum": sum(row["cache_read_tokens"] for row in rows if type(row.get("cache_read_tokens")) is int),
            "cache_read_observation_missing": sum(type(row.get("cache_read_tokens")) is not int for row in rows),
            "cache_write_tokens_observed_sum": sum(row["cache_write_tokens"] for row in rows if type(row.get("cache_write_tokens")) is int),
            "cache_write_observation_missing": sum(type(row.get("cache_write_tokens")) is not int for row in rows),
            "original_outcomes": dict(Counter(row["original_outcome"] for row in rows)),
            "raw_json_parse_ok": sum(row["raw_json_parse_ok"] for row in rows),
            "raw_schema_valid": sum(row["raw_schema_valid"] for row in rows),
            "raw_saved_response_equal": sum(row["raw_matches_saved_response"] is True for row in rows),
            "saved_quote_check_available": sum(type(row["saved_all_quotes_present"]) is bool for row in rows),
            "saved_quote_check_failed": sum(row["saved_all_quotes_present"] is False for row in rows),
            "tags": dict(sorted(tags.items())),
            "numeric_selection_all_responses": dict(Counter(row["numeric_selection_observation"] for row in rows)),
            "numeric_selection_valid_responses": dict(Counter(row["numeric_selection_observation"] for row in rows if row["saved_status"] == "VALID"))}


def grouped(rows, dimensions):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[dimension] for dimension in dimensions)].append(row)
    ordered = sorted(groups.items(), key=lambda item: tuple(VARIANTS.index(value) if dimension == 'variant' and value in VARIANTS else value for dimension, value in zip(dimensions, item[0])))
    return [{**dict(zip(dimensions, key)), **counts_for(group)} for key, group in ordered]


def pair_record(left, right, kind):
    a, b = left.get("response"), right.get("response")
    left_observed, right_observed = isinstance(a, dict), isinstance(b, dict)
    observed = left_observed and right_observed
    left_answer_observed = left_observed and "answer" in a
    right_answer_observed = right_observed and "answer" in b
    answer_comparable = left_answer_observed and right_answer_observed
    explanation_comparable = observed and isinstance(a.get("explanation"), str) and isinstance(b.get("explanation"), str)
    scale_comparable = (observed and isinstance(a.get("answer_meta"), dict)
                        and isinstance(b.get("answer_meta"), dict)
                        and "scale" in a["answer_meta"] and "scale" in b["answer_meta"])
    an, bn = left["signed_numeric_field"], right["signed_numeric_field"]
    left_numeric = an is not None if left_answer_observed else None
    right_numeric = bn is not None if right_answer_observed else None
    both_numeric = left_numeric is True and right_numeric is True
    return {"kind": kind, "left_trial_id": left["trial_id"], "right_trial_id": right["trial_id"],
            "case": left["case"], "variant": left["variant"], "prompt_condition": left["prompt_condition"],
            "reasoning": left["reasoning"], "same_qc": left["qc_sha256"] == right["qc_sha256"],
            "same_input": left["input_sha256"] == right["input_sha256"],
            "left_response_observed": left_observed, "right_response_observed": right_observed,
            "observed_response_pair": observed,
            "response_comparison_status": ("COMPARABLE" if observed else "BOTH_RESPONSES_MISSING"
                                           if not left_observed and not right_observed
                                           else "LEFT_RESPONSE_MISSING" if not left_observed
                                           else "RIGHT_RESPONSE_MISSING"),
            "answer_fields_comparable": answer_comparable,
            "explanations_comparable": explanation_comparable,
            "scales_comparable": scale_comparable,
            "left_valid": left["saved_status"] == "VALID", "right_valid": right["saved_status"] == "VALID",
            "left_numeric": left_numeric, "right_numeric": right_numeric,
            "left_answer_is_null": a["answer"] is None if left_answer_observed else None,
            "right_answer_is_null": b["answer"] is None if right_answer_observed else None,
            "numeric_field_presence_agrees": (an is None) == (bn is None) if answer_comparable else None,
            "both_numeric": both_numeric,
            "numeric_values_agree": an == bn if both_numeric else None,
            "both_valid_numeric": both_numeric and left["saved_status"] == right["saved_status"] == "VALID",
            "same_scale": a["answer_meta"]["scale"] == b["answer_meta"]["scale"] if scale_comparable else None,
            "same_explanation": a["explanation"] == b["explanation"] if explanation_comparable else None,
            "same_full_response": a == b if observed else None,
            "left_original_outcome": left["original_outcome"], "right_original_outcome": right["original_outcome"]}


def summarize_pairs(pairs):
    observed = [pair for pair in pairs if pair["observed_response_pair"]]
    answer_comparable = [pair for pair in pairs if pair["answer_fields_comparable"]]
    explanation_comparable = [pair for pair in pairs if pair["explanations_comparable"]]
    numeric = [pair for pair in pairs if pair["both_numeric"]]
    valid_numeric = [pair for pair in pairs if pair["both_valid_numeric"]]
    return {"pairs": len(pairs), "same_qc": sum(pair["same_qc"] for pair in pairs),
            "same_input": sum(pair["same_input"] for pair in pairs),
            "observed_response_pair_denominator": len(observed),
            "response_pair_not_evaluated": len(pairs) - len(observed),
            "response_comparison_statuses": dict(Counter(pair["response_comparison_status"] for pair in pairs)),
            "answer_field_comparable_denominator": len(answer_comparable),
            "numeric_presence_not_evaluated": len(pairs) - len(answer_comparable),
            "explanation_comparable_denominator": len(explanation_comparable),
            "explanation_not_evaluated": len(pairs) - len(explanation_comparable),
            "numeric_presence_agreement": sum(pair["numeric_field_presence_agrees"] is True for pair in answer_comparable),
            "both_numeric_denominator": len(numeric), "numeric_agreement": sum(pair["numeric_values_agree"] for pair in numeric),
            "both_valid_numeric_denominator": len(valid_numeric),
            "valid_numeric_agreement": sum(pair["numeric_values_agree"] for pair in valid_numeric),
            "same_explanation": sum(pair["same_explanation"] is True for pair in explanation_comparable),
            "same_full_response": sum(pair["same_full_response"] is True for pair in observed),
            "invalid_to_valid": sum(not pair["left_valid"] and pair["right_valid"] for pair in observed),
            "valid_to_invalid": sum(pair["left_valid"] and not pair["right_valid"] for pair in observed),
            # Preserve the old extracted-number metrics for completed baselines.
            # Their historical "empty" name also includes an unextractable value.
            "numeric_to_empty": sum(pair["left_numeric"] is True and pair["right_numeric"] is False for pair in answer_comparable),
            "empty_to_numeric": sum(pair["left_numeric"] is False and pair["right_numeric"] is True for pair in answer_comparable),
            "legacy_empty_metric_definition": "OBSERVED_ANSWER_WITHOUT_NORMALIZABLE_SIGNED_NUMBER_NOT_NECESSARILY_NULL",
            "numeric_to_null": sum(pair["left_numeric"] is True and pair["right_answer_is_null"] is True for pair in answer_comparable),
            "null_to_numeric": sum(pair["left_answer_is_null"] is True and pair["right_numeric"] is True for pair in answer_comparable)}


def check_pair_regressions():
    """Exercise observed, null, missing, and malformed-field pair boundaries."""
    base = {"trial_id": "fixture", "case": "case", "variant": "ORIGINAL",
            "prompt_condition": "P0", "reasoning": "off", "qc_sha256": "qc",
            "input_sha256": "input", "original_outcome": "NOT_NUMERICALLY_EVALUATED"}
    missing = {**base, "response": None, "saved_status": "NOT_COLLECTED", "signed_numeric_field": None}
    null_response = {"answer": None, "answer_meta": {"negative": None, "scale": None},
                     "explanation": "No numeric result.", "evidence": []}
    null = {**base, "response": null_response, "saved_status": "VALID", "signed_numeric_field": None}
    numeric = {**base, "response": {**null_response, "answer": 7}, "saved_status": "VALID", "signed_numeric_field": "7"}
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append({"name": name, "status": "PASS"})

    for name, left, right in (("both_missing", missing, missing), ("left_missing", missing, null),
                              ("right_missing", null, missing), ("missing_to_numeric", missing, numeric),
                              ("numeric_to_missing", numeric, missing)):
        pair = pair_record(left, right, "FIXTURE")
        summary = summarize_pairs([pair])
        check(name + "_agreements_not_evaluated", all(pair[field] is None for field in
              ("same_full_response", "same_explanation", "same_scale", "numeric_field_presence_agrees", "numeric_values_agree")))
        check(name + "_denominator_and_transitions", summary["observed_response_pair_denominator"] == 0
              and summary["response_pair_not_evaluated"] == 1
              and all(summary[field] == 0 for field in ("same_full_response", "same_explanation",
                  "numeric_presence_agreement", "numeric_to_empty", "empty_to_numeric", "numeric_to_null", "null_to_numeric", "invalid_to_valid", "valid_to_invalid")))
    pair = pair_record(null, null, "FIXTURE")
    check("valid_nulls_are_observed", pair["same_full_response"] is True
          and pair["same_explanation"] is True and pair["numeric_field_presence_agrees"] is True
          and summarize_pairs([pair])["observed_response_pair_denominator"] == 1)
    check("valid_null_to_numeric_transition", summarize_pairs([pair_record(null, numeric, "FIXTURE")])["null_to_numeric"] == 1)
    check("numeric_to_valid_null_transition", summarize_pairs([pair_record(numeric, null, "FIXTURE")])["numeric_to_null"] == 1)
    nonnull_unextractable = {**null, "response": {**null_response, "answer": "7"}, "saved_status": "INVALID_RESPONSE"}
    summary = summarize_pairs([pair_record(nonnull_unextractable, numeric, "FIXTURE")])
    check("unextractable_value_is_not_null", summary["empty_to_numeric"] == 1 and summary["null_to_numeric"] == 0)
    malformed = {**null, "response": {}, "saved_status": "INVALID_RESPONSE"}
    pair = pair_record(malformed, malformed, "FIXTURE")
    check("absent_fields_are_not_valid_null_fields", pair["left_answer_is_null"] is None
          and pair["numeric_field_presence_agrees"] is None and pair["same_explanation"] is None)
    return {"checks": checks, "new_model_calls": 0}


def pairing(run):
    rows, private, public = run["rows"], run["private"], run["public"]
    by_key = {(row["item_id"], row["prompt_condition"], row["reasoning"]): row for row in rows}
    pairs, links = [], []
    for row in rows:
        if row["reasoning"] == "off":
            other = by_key.get((row["item_id"], row["prompt_condition"], "on"))
            if other:
                pairs.append(pair_record(row, other, "REASONING_OFF_TO_ON"))
        if row["prompt_condition"] == "P0":
            other = by_key.get((row["item_id"], "P1", row["reasoning"]))
            if other:
                pairs.append(pair_record(row, other, "PROMPT_P0_TO_P1"))
    for item in private.values():
        if item.get("matched_value_parent_ids"):
            for parent_id in item["matched_value_parent_ids"]:
                restored = public[item["item_id"]]["context"]
                exact = True
                shifted, delta = [], 0
                for patch in sorted(item["patches"], key=lambda value: value["start"]):
                    shifted.append((patch["start"] + delta, patch))
                    delta += len(patch["text"]) - (patch["end"] - patch["start"])
                for start, patch in reversed(shifted):
                    exact = exact and restored[start:start + len(patch["text"])] == patch["text"]
                    restored = restored[:start] + patch["before"] + restored[start + len(patch["text"]):]
                verified = exact and restored == public[parent_id]["context"] and public[item["item_id"]]["question"] == public[parent_id]["question"]
                links.append({"source_item_id": item["item_id"], "parent_item_id": parent_id,
                              "case": item["case"], "source_variant": item["variant"],
                              "exact_source_insertion_reversed": verified})
                if not verified:
                    continue
                for prompt in ("P0", "P1"):
                    for reasoning in ("off", "on"):
                        left, right = by_key.get((parent_id, prompt, reasoning)), by_key.get((item["item_id"], prompt, reasoning))
                        if left and right:
                            pair = pair_record(left, right, "MATCHED_VALUE_TO_SOURCE")
                            pair["source_variant"] = item["variant"]
                            pairs.append(pair)
        if item.get("original_item_id"):
            for prompt in ("P0", "P1"):
                for reasoning in ("off", "on"):
                    left = by_key.get((item["original_item_id"], "P0", reasoning))
                    right = by_key.get((item["item_id"], prompt, reasoning))
                    if left and right:
                        pair = pair_record(left, right, "ORIGINAL_TO_VARIANT")
                        pair.update(variant=item["variant"], prompt_condition=prompt,
                                    baseline_qc_matches_generation_reference=item.get("baseline_qc_matches_generation_reference"),
                                    shared_prompt_condition=prompt == "P0")
                        pairs.append(pair)
    groups = defaultdict(list)
    for pair in pairs:
        groups[pair["kind"]].append(pair)
    summaries = {kind: summarize_pairs(group) for kind, group in groups.items()}
    return pairs, links, summaries


def make_summary(run, pairs, links, pair_summary):
    rows, private = run["rows"], run["private"]
    return {"method": METHOD, "run_id": run["root"].name, "model": run["model"],
            "source_run": path_label(run["root"]), "new_model_calls": 0,
            "semantic_scoring": "NOT_PERFORMED", "rows": len(rows),
            "unique_cases": len({row["case"] for row in rows}),
            "unique_inputs": len({row["item_id"] for row in rows}),
            "overall": counts_for(rows),
            "by_variant_prompt_reasoning": grouped(rows, ("variant", "prompt_condition", "reasoning")),
            "by_prompt_reasoning": grouped([row for row in rows if row["variant"] != "ORIGINAL"], ("prompt_condition", "reasoning")),
            "by_original_reasoning": grouped([row for row in rows if row["variant"] == "ORIGINAL"], ("reasoning",)),
            "pair_summary": pair_summary,
            "reasoning_pairs_by_scope": {scope: summarize_pairs([pair for pair in pairs if pair["kind"] == "REASONING_OFF_TO_ON" and (pair["variant"] == "ORIGINAL") == original]) for scope, original in (("original", True), ("variants", False))},
            "source_links": {"declared": len(links), "exact_reversal_verified": sum(link["exact_source_insertion_reversed"] for link in links)},
            "source_pairs_by_condition": [
                {"source_variant": variant, "prompt_condition": prompt, "reasoning": reasoning,
                 **summarize_pairs([pair for pair in pairs if pair['kind'] == 'MATCHED_VALUE_TO_SOURCE'
                                    and pair['source_variant'] == variant and pair['prompt_condition'] == prompt
                                    and pair['reasoning'] == reasoning])}
                for variant in ('IC_SOURCE_A_ONLY', 'IC_SOURCE_B_ONLY') for prompt in ('P0', 'P1') for reasoning in ('off', 'on')],
            "original_link_qc_status_by_input": dict(Counter(str(item.get("baseline_qc_matches_generation_reference")) for item in private.values() if item["variant"] != "ORIGINAL")),
            "original_to_variant_same_qc_reference_pairs": summarize_pairs([pair for pair in pairs if pair["kind"] == "ORIGINAL_TO_VARIANT" and pair["baseline_qc_matches_generation_reference"] is True and pair["shared_prompt_condition"]]),
            "precision_conflict_cases": sorted({row["case"] for row in rows if row["precision_conflict"]}),
            "heuristic_policy": {"no_commitment_cue": NO_COMMITMENT.pattern,
                                 "equation_rhs": EQUATION_RHS.pattern,
                                 "limits": ["Lexical cues can quote or discuss alternatives and miss paraphrases.",
                                            "Equation RHS may be intermediate or require rounding; mismatch is a candidate only.",
                                            "Exact excerpt presence does not establish evidential sufficiency or entailment.",
                                            "Coefficient anchors are not semantic correctness labels.",
                                            "No repeated same-condition trials; temporal repeatability is not measured.",
                                            "P0/P1 and off/on pairs measure sensitivity to changed conditions, not same-condition reproducibility."]}}


def cross_run(left_run, right_run):
    def key(row):
        return row["case"], row["variant"], row["prompt_condition"], row["reasoning"]
    left, right = ({key(row): row for row in run["rows"]} for run in (left_run, right_run))
    common = sorted(set(left) & set(right))
    pairs = [pair_record(left[value], right[value], "CROSS_RUN") for value in common]
    same_qc = [value for value in common if left[value]['qc_sha256'] == right[value]['qc_sha256']]
    observed_same_qc = [value for value in same_qc if isinstance(left[value].get('response'), dict)
                       and isinstance(right[value].get('response'), dict)]
    tag_names = sorted({tag for value in observed_same_qc for row in (left[value], right[value]) for tag in row['tags']})
    return {"left_run": left_run["root"].name, "right_run": right_run["root"].name,
            "left_only": len(set(left) - set(right)), "right_only": len(set(right) - set(left)),
            "matched": summarize_pairs(pairs),
            "same_qc_matched": summarize_pairs([pair for pair in pairs if pair["same_qc"]]),
            "original_by_reasoning": {reasoning: summarize_pairs([pair for pair in pairs if pair["variant"] == "ORIGINAL" and pair["reasoning"] == reasoning]) for reasoning in ("off", "on")},
            "same_qc_observations": {"denominator": len(same_qc),
                                     "left": counts_for([left[value] for value in same_qc]),
                                     "right": counts_for([right[value] for value in same_qc])},
            "tag_transition_observed_pair_denominator": len(observed_same_qc),
            "tag_transition_not_evaluated": len(same_qc) - len(observed_same_qc),
            "tag_transitions_same_qc": {tag: {
                "present_both": sum(tag in left[value]['tags'] and tag in right[value]['tags'] for value in observed_same_qc),
                "left_only": sum(tag in left[value]['tags'] and tag not in right[value]['tags'] for value in observed_same_qc),
                "right_only": sum(tag not in left[value]['tags'] and tag in right[value]['tags'] for value in observed_same_qc)} for tag in tag_names},
            "prompt_unchanged": sum(left[value]['prompt_sha256'] == right[value]['prompt_sha256'] for value in common),
            "schema_unchanged": sum(left[value]['schema_sha256'] == right[value]['schema_sha256'] for value in common),
            "limitations": ["Prompt and schema equality counts are observed; effects of remaining transport, cache, and sampling differences are not isolated.",
                            "Equal case IDs alone do not prove equal Q/C; exact Q/C hashes are reported.",
                            "Saved validity and precision errors use each frozen contract; fixed decimal strings and numeric rounding are different rules.",
                            "Contract-specific tags can become inapplicable after a field is removed; tag disappearance is not proof of behavioral improvement.",
                            "Full response equality is not comparable across different response structures; numeric equality is coefficient equality, not semantic equivalence.",
                            "The left run is a comparator; old scoring is not recalculated."]}, pairs


def table(headers, rows):
    return "\n".join(["|" + "|".join(headers) + "|", "|" + "|".join("---" for _ in headers) + "|"] + ["|" + "|".join(str(cell) for cell in row) + "|" for row in rows])


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows))


def report_text(summary, comparison=None):
    overall = summary["overall"]
    def precision_count(group, title, tag):
        return group['tags'].get(tag, 0) if group.get('schema_titles', {}).get(title, 0) else '해당 없음'
    lines = ["# Luna 응답 형식·표현 및 조건 민감도 분석 — 반복 안정성 미평가", "", f"실행 `{summary['run_id']}` · 원문 {summary['unique_cases']}개 · 계획 요청 {summary['rows']:,}건 · 새 모델 호출 0건.", "",
             "JSON 파싱·필드 규칙·답과 설명의 표현을 확인하고, off/on 또는 P0/P1처럼 조건을 바꿨을 때의 응답 차이를 분석합니다. 조건 변화에 대한 민감도와 같은 조건에서 반복했을 때의 안정성은 서로 다른 측정입니다. 이 자료로 반복 안정성은 평가하지 않습니다. 원문 숫자 일치와 변형의 의미 정답 여부도 분리합니다.", "",
             "## 원응답과 저장 결과 대조", "", f"원응답 JSON 파싱 {overall['raw_json_parse_ok']}/{overall['planned']}, 동결 JSON Schema 통과 {overall['raw_schema_valid']}/{overall['planned']}, 저장 response와 동일 {overall['raw_saved_response_equal']}/{overall['planned']}입니다. 추가 실행 당시 검사 상태는 {overall['saved_status']}입니다. 스키마 타입 통과와 필드 조합·표기 검사 통과는 다릅니다.", "",
             "## 원문 결과: 조건마다 계획 분모 유지", "",
             table(["추론", "계획", "숫자 일치", "숫자 불일치", "형식·수집 실패", "유효 빈 답", "기타 미평가"], [[g['reasoning'], g['planned'], *[g['original_outcomes'].get(name, 0) for name in ('NUMERIC_MATCH', 'NUMERIC_MISMATCH', 'FORMAT_OR_COLLECTION_FAILURE', 'VALID_NULL_ANSWER', 'NOT_NUMERICALLY_EVALUATED')]] for g in summary['by_original_reasoning']]), "",
             "숫자 일치와 불일치는 기존 채점값입니다. 계산 경로·해석·인용 의미 전체가 맞았다는 뜻이 아닙니다. 유효 빈 답은 V4의 유효 유보와 V5/V6의 null 답을 필드 차원에서 관찰하는 표현이며, V5/V6에서 유보 의도를 단정하지 않습니다. 버전마다 형식 검사 규칙이 달라지므로 유효 응답 비율만으로 개선을 확정하지 않습니다.", "",
             "## 변형: 프롬프트·추론별 형식과 답변 표현", "",
             table(["프롬프트", "추론", "계획", "형식 유효", "원응답 유보 선언", "숫자 필드", "빈 답", "유보+숫자", "고정 자릿수 표기 실패", "수치 반올림 실패", "인용 문자열 불일치"], [[g['prompt_condition'], g['reasoning'], g['planned'], g['saved_status'].get('VALID', 0), g['tags'].get('RAW_DECLARED_ABSTENTION', 0), g['tags'].get('NUMERIC_FIELD_PRESENT', 0), g['tags'].get('NULL_ANSWER', 0), g['tags'].get('DECLARED_ABSTENTION_WITH_NON_NULL_ANSWER', 0), precision_count(g, FIXED_DECIMAL_CONTRACT, 'SAVED_DECIMAL_PLACES_FAILURE'), precision_count(g, NUMERIC_ROUNDING_CONTRACT, 'SAVED_NUMERIC_ROUNDING_FAILURE'), g['tags'].get('EVIDENCE_NOT_EXACT_SUBSTRING', 0)] for g in summary['by_prompt_reasoning']]), "",
             "고정 자릿수 표기 실패는 FinancialAnswerMagnitudeV4의 문자열 표기 검사, 수치 반올림 실패는 FinancialAnswerV6의 숫자 값 검사 메시지에서 각각 읽은 관찰입니다. 서로 다른 규칙이므로 두 건수를 동일 기준의 실패 감소로 비교하지 않습니다. 해당 계약을 사용하지 않은 열은 0이 아닌 ‘해당 없음’으로 표시합니다. 원래 saved_schema_errors와 검사 결과는 변경하지 않습니다.", "",
             "유보+숫자는 형식 실패인 경우에도 원응답의 행동을 보존하기 위한 별도 관찰값입니다. V5/V6에는 status가 없으므로 ‘원응답 유보 선언’의 0은 유보가 없다는 뜻이 아닙니다.", "",
             f"인용 문자열의 새 관찰은 형식 실패를 포함한 전체 {overall['planned']}응답을 분모로 합니다. 기존 인용 검사값은 {overall['saved_quote_check_available']}응답에만 있고, 그중 실패 {overall['saved_quote_check_failed']}건입니다. 따라서 기존 보고서의 실패 건수와 전체 원응답 재검사 건수는 분모를 맞춰 읽어야 합니다. 정확한 문자열이 있어도 그 인용이 답을 뒷받침한다는 의미 판정은 아닙니다.", "",
             "## 유형별 전체 분모", "",
             table(["유형", "P", "추론", "계획", "형식 유효", "숫자", "빈 답", "유보+숫자", "정확한 인용 아님"], [[NAMES.get(g['variant'], g['variant']), g['prompt_condition'], g['reasoning'], g['planned'], g['saved_status'].get('VALID', 0), g['tags'].get('NUMERIC_FIELD_PRESENT', 0), g['tags'].get('NULL_ANSWER', 0), g['tags'].get('DECLARED_ABSTENTION_WITH_NON_NULL_ANSWER', 0), g['tags'].get('EVIDENCE_NOT_EXACT_SUBSTRING', 0)] for g in summary['by_variant_prompt_reasoning']]), "",
             "## 조건 변화에 대한 민감도", "",
             table(["짝", "계획쌍", "응답 관측쌍", "응답 미평가쌍", "숫자 존재 동일", "양쪽 숫자", "숫자값 동일", "양쪽 유효 숫자", "그중 숫자값 동일", "설명 동일", "JSON 동일"], [[kind, g['pairs'], g['observed_response_pair_denominator'], g['response_pair_not_evaluated'], g['numeric_presence_agreement'], g['both_numeric_denominator'], g['numeric_agreement'], g['both_valid_numeric_denominator'], g['valid_numeric_agreement'], g['same_explanation'], g['same_full_response']] for kind, g in summary['pair_summary'].items()]), "",
             "양쪽 응답 객체가 실제로 관측된 쌍만 응답 비교 분모에 넣습니다. 한쪽 또는 양쪽 미수집은 동일·불일치가 아닌 미평가(null)입니다. 유효 응답의 answer=null은 실제 관측된 빈 답으로서 미수집과 구별합니다. 숫자 존재는 양쪽 answer 필드가 있는 쌍, 설명 동일성은 양쪽 설명 문자열이 있는 쌍에서만 비교하며 각 세부 분모를 JSON에 기록합니다.", "",
             "off/on과 P0/P1은 조건을 바꾼 비교입니다. 같은 조건을 반복한 실험이 아니므로 반복 재현성·시간 안정성 또는 분산을 추정할 수 없습니다. explanation 문자열 일치는 내부 추론 경로의 일치도 아닙니다.", "",
             "## 원문·변형과 출처 짝의 비교 범위", "",
             f"원문과 제작 기준 Q/C가 같다고 저장된 변형은 {summary['original_link_qc_status_by_input']}. 이 조건이 true이고 P0끼리인 원문→변형 비교는 {summary['original_to_variant_same_qc_reference_pairs']['pairs']}쌍입니다. P1 변형은 원문 P0와 프롬프트도 달라지는 별도 조건으로 남깁니다.", "",
             f"VALUE→SOURCE 연결 {summary['source_links']['declared']}개 중 {summary['source_links']['exact_reversal_verified']}개에서 출처 삽입문을 정확히 되돌리면 부모 VALUE의 질문·본문과 일치했습니다. 이 연결에 대한 조건별 비교는 `pairs.jsonl`에서 확인합니다. SOURCE-before와 SOURCE-after를 서로 비교하면 위치와 부모 VALUE도 달라지므로 출처 효과 하나로 해석하지 않습니다.", "",
             "## 숫자 선택과 답·설명 불일치 후보", "",
             table(["관찰", "응답 수"], sorted(overall['tags'].items())), "",
             "`NUMERIC_FIELD_WITH_NO_COMMITMENT_CUE`는 숫자 필드와 ‘계산할 수 없다’는 계열 표현의 동시 등장입니다. 조건부 예시·인용·부정문을 완전히 구별하지 못하므로 의미 모순의 확정 건수로 쓰지 않습니다. `ANSWER_ABSENT_FROM_EQUATION_RHS_CANDIDATE`도 중간 계산 또는 반올림 때문에 발생할 수 있습니다. 양의 답과 같은 크기의 음수가 설명에 등장하는 후보 역시 문맥 검토가 필요합니다.", "",
             "reference/alternative 숫자 선택은 저장된 숫자 계수에 대한 일치 관찰입니다. 원문 참조와 같다고 변형의 정답으로, alternative와 같다고 잘못된 숫자 선택으로 채점하지 않습니다. 상세 분포는 `summary.json`의 `numeric_selection_*`, 실제 후보는 `rows.jsonl`에 있습니다.", "",
             table(["P", "추론", "계획", "원문 참조 계수", "변형 대안 계수", "기타 계수", "숫자 없음", "응답 미관측", "답 필드 없음"], [[g['prompt_condition'], g['reasoning'], g['planned'], *[g['numeric_selection_all_responses'].get(name, 0) for name in ('REFERENCE_COEFFICIENT', 'ALTERNATIVE_COEFFICIENT', 'OTHER_COEFFICIENT', 'NO_NUMERIC_FIELD', 'RESPONSE_NOT_OBSERVED', 'ANSWER_FIELD_MISSING')]] for g in summary['by_prompt_reasoning']]), "",
             f"질문과 전달 자릿수 메타정보 충돌은 {len(summary['precision_conflict_cases'])}원문에서 발견되었습니다: {', '.join(summary['precision_conflict_cases'])}. 기존 입력·정답·숫자 규칙은 이 분석에서 바꾸지 않았습니다.", ""]
    if comparison:
        observed = comparison['same_qc_observations']
        lines += ["## 이전 실행과의 보조 비교", "", f"`{comparison['left_run']}` → `{comparison['right_run']}`: 조건 키가 맞는 {comparison['matched']['pairs']}쌍 중 Q/C 동일 {comparison['matched']['same_qc']}쌍, 전체 모델 입력 동일 {comparison['matched']['same_input']}쌍입니다. 프롬프트는 {comparison['prompt_unchanged']}쌍, 응답 스키마는 {comparison['schema_unchanged']}쌍에서 동일했습니다.", "",
                  table(["범위", "계획쌍", "응답 관측쌍", "미평가쌍", "실패→유효", "유효→실패", "숫자→null", "null→숫자"], [[scope, group['pairs'], group['observed_response_pair_denominator'], group['response_pair_not_evaluated'], group['invalid_to_valid'], group['valid_to_invalid'], group['numeric_to_null'], group['null_to_numeric']] for scope, group in [('전체', comparison['matched']), *[(f'원문 P0/{reasoning}', group) for reasoning, group in comparison['original_by_reasoning'].items()]]]), "",
                  "이 표의 빈 답 전이는 명시적인 answer=null만 포함합니다. JSON의 기존 `numeric_to_empty`·`empty_to_numeric`는 과거 수치 보존을 위해 정규화된 부호 숫자가 없는 관측 응답을 뜻하는 기존 정의를 유지하고, 엄격한 null 전이는 `numeric_to_null`·`null_to_numeric`로 추가했습니다. 부호 필드가 없어 숫자를 읽지 못한 응답은 null 전이에 넣지 않습니다. 미수집은 어느 전이에도 넣지 않습니다.", "",
                  "실패→유효는 각 실행 당시 계약의 검사 상태 전이입니다. status 삭제 후 유보·숫자 모순 태그가 없어지거나 부호 숫자 계약에만 있는 태그가 새로 생기는 것은 공통 행동 지표의 개선·악화와 구별합니다. 구조가 다른 JSON의 전체 동일성은 개선 지표로 사용하지 않으며, 숫자값 동일성도 저장된 계수의 일치로서 scale·단위와 의미를 보장하지 않습니다.", "",
                  table(["실행", "관측 경로", "저장 결과 캐시 읽기 토큰 합", "읽기 정보 없는 요청", "캐시 쓰기 토큰 합", "쓰기 정보 없는 요청"], [[run_id, group['transport_counts'], group['cache_read_tokens_observed_sum'], group['cache_read_observation_missing'], group['cache_write_tokens_observed_sum'], group['cache_write_observation_missing']] for run_id, group in [(comparison['left_run'], observed['left']), (comparison['right_run'], observed['right'])]]), "",
                  "위 프롬프트·스키마 동일성은 요청별 해시 확인값이며, 호출 경로와 캐시 토큰은 저장된 최종 결과의 관측값입니다. CLI/API 경로와 캐시 조건 등 남은 차이의 효과를 분리한 실험이 아니므로 어느 하나의 인과 효과로 확정하지 않습니다. 재시도가 있었다면 이 표의 토큰은 선택된 최종 결과만 포함하며 전체 청구 사용량으로 사용하지 않습니다.", ""]
    lines += ["## 개선 판단과 논문에 사용할 수 있는 주장", "", "- **채택:** 답·부호·설명 관계와 계약별 실패를 함께 확인합니다. 본문 수치는 이 실행에서 관찰한 결과이며 새 계약이나 지시문의 효과를 자동으로 확정하지 않습니다.", "- **수정 채택:** 형식 실패를 줄였다는 주장은 JSON·동결 스키마와 공통 관찰 지표를 함께 보고할 때 가능합니다. 느슨해진 검사만으로 형식 안정성이 좋아졌다고 쓰지 않습니다.", "- **보류:** 유보 능력·근거의 의미 정확도·출처 신뢰 판단이 향상되었다는 주장. 현재 자동 관찰에는 그 의미 정답이 없습니다.", "- **기각:** 서로 다른 off/on 또는 P0/P1 응답을 같은 조건 반복으로 간주하여 재현성 향상을 주장하거나, 형식 실패를 계산 오답으로 합산하는 방식.", "", f"{summary['unique_cases']}개 원문은 기존 선정 표본이며 무작위 표본이 아닙니다. 질문·본문을 같게 유지한 재실험은 이 표본 안의 비교를 돕지만 다른 금융 문제나 모델로의 일반화를 보장하지 않습니다.", ""]
    return "\n".join(lines)


def representative_cases(rows):
    wanted = [("test-0025", "ORIGINAL", "P0", "off", "SIGN_AND_EXPLANATION_AGREEMENT"),
              ("test-0260", "IC_VALUE_01_AFTER", "P0", "off", "NO_COMMITMENT_AND_NUMERIC_FIELD"),
              ("test-0238", "ORIGINAL", "P0", "off", "PRECISION_INSTRUCTION_CONFLICT"),
              ("test-0052", "EA_01", "P0", "off", "DECIMAL_REPRESENTATION"),
              ("test-0203", "ORIGINAL", "P0", "on", "ALTERNATIVE_CALCULATION_PATH")]
    by_key = {(r['case'], r['variant'], r['prompt_condition'], r['reasoning']): r for r in rows}
    result = []
    for case, variant, prompt, reasoning, label in wanted:
        row = by_key.get((case, variant, prompt, reasoning))
        if row:
            result.append({"label": label, "row": row})
    candidate = next((r for r in rows if "EVIDENCE_NOT_EXACT_SUBSTRING" in r['tags']), None)
    if candidate:
        result.append({"label": "EXACT_EXCERPT_MISMATCH_NOT_SEMANTIC_VERDICT", "row": candidate})
    return result


def build(args):
    started = datetime.now(timezone.utc).isoformat()
    run = read_run(args.run, args.model)
    output = Path(args.output).resolve()
    if output == run['root'] or run['root'] in output.parents:
        raise ValueError("NEW_REVIEW_OUTPUT_OUTSIDE_SOURCE_RUN_REQUIRED")
    pairs, links, pair_summary = pairing(run)
    summary = make_summary(run, pairs, links, pair_summary)
    comparison, comparison_rows, compare_summary = None, [], None
    all_hashes = dict(run['hashes'])
    if args.compare_run:
        comparator = read_run(args.compare_run, args.compare_model)
        if output == comparator['root'] or comparator['root'] in output.parents:
            raise ValueError("OUTPUT_MUST_NOT_OVERWRITE_COMPARATOR_RUN")
        compare_pairs, compare_links, compare_pair_summary = pairing(comparator)
        compare_summary = make_summary(comparator, compare_pairs, compare_links, compare_pair_summary)
        comparison, comparison_rows = cross_run(comparator, run)
        all_hashes.update(comparator['hashes'])
    source_unchanged = all(sha(ROOT / path) == value for path, value in all_hashes.items())
    if not source_unchanged:
        raise ValueError("SOURCE_CHANGED_DURING_REVIEW")
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / 'summary.json', summary)
    write_rows(output / 'rows.jsonl', run['rows'])
    write_rows(output / 'pairs.jsonl', pairs)
    write_rows(output / 'source-links.jsonl', links)
    if comparison:
        write_json(output / 'comparison.json', comparison)
        write_json(output / 'comparator-summary.json', compare_summary)
        write_rows(output / 'comparison-pairs.jsonl', comparison_rows)
    cases = representative_cases(run['rows'])
    write_json(output / 'representative-cases.json', cases)
    case_lines = ["# 실제 응답 사례", "", "아래는 분석기가 원응답에서 읽은 값입니다. 기존 채점과 원문을 변경하지 않습니다. 사례 제목은 확인할 쟁점이며 새 의미 채점이 아닙니다.", ""]
    labels = {'SIGN_AND_EXPLANATION_AGREEMENT': '부호 필드와 설명의 일치 여부',
              'NO_COMMITMENT_AND_NUMERIC_FIELD': '답을 확정하지 않는 표현과 숫자 필드',
              'PRECISION_INSTRUCTION_CONFLICT': '질문과 전달 자릿수의 충돌',
              'DECIMAL_REPRESENTATION': '숫자 답의 소수 표기',
              'ALTERNATIVE_CALCULATION_PATH': '참조 답과 다른 계산 경로',
              'EXACT_EXCERPT_MISMATCH_NOT_SEMANTIC_VERDICT': '인용 문자열 불일치: 의미 거짓으로 단정하지 않음'}
    for item in cases:
        row = item['row']
        source_links = ' · '.join(f"[{label}]({ROOT / row[field]})" for field, label in
                                 (('raw_path', '실제 원응답'), ('result_path', '실제 result')) if row.get(field))
        case_lines += [f"## {row['case']} · {NAMES.get(row['variant'], row['variant'])} · {row['prompt_condition']}/{row['reasoning']}", "", labels[item['label']], "", f"기존 상태 `{row['saved_status']}` / `{row['original_outcome']}`", "", source_links or '미수집: 원응답·결과 경로가 없습니다.', "", "```json", json.dumps(row['response'], ensure_ascii=False, indent=2), "```", "", f"관찰 태그: {', '.join(row['tags'])}", ""]
    (output / 'cases.md').write_text('\n'.join(case_lines))
    (output / 'analysis.md').write_text(report_text(summary, comparison))
    verification = {"method": METHOD, "at": started, "source_files": len(all_hashes),
                    "all_source_hashes_unchanged": source_unchanged, "source_sha256": all_hashes,
                    "new_model_calls": 0, "semantic_scoring": "NOT_PERFORMED",
                    "viewer_verified": False, "user_review_completed": False,
                    "analyzer_sha256": sha(Path(__file__)),
                    "readme_template_sha256": sha(Path(__file__).with_name('stability-review-template.md'))}
    write_json(output / 'verification.json', verification)
    template = Path(__file__).with_name('stability-review-template.md').read_text()
    command = f"PYTHONPATH=src .venv/bin/python src/finarch/experiments/02-analysis/legacy/content-analysis/stability_review.py --run {path_label(run['root'])} --model {run['model']} --output {path_label(output)}"
    if args.compare_run:
        command += f" --compare-run {path_label(args.compare_run)} --compare-model {comparator['model']}"
    (output / 'README.md').write_text(template.replace('{{run_id}}', summary['run_id']).replace('{{rows}}', str(summary['rows'])).replace('{{command}}', command).replace('{{source_files}}', str(len(all_hashes))))
    with (output / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps({"at": started, "event": "OFFLINE_STABILITY_REVIEW_COMPLETED", "method": METHOD,
                                 "run_id": summary['run_id'], "planned_requests": len(run['rows']),
                                 "preserved_source_files": len(all_hashes), "new_model_calls": 0}) + '\n')
    return {"output": path_label(output), "rows": len(run['rows']), "source_hashes_unchanged": source_unchanged,
            "new_model_calls": 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--model')
    parser.add_argument('--output', required=True)
    parser.add_argument('--compare-run')
    parser.add_argument('--compare-model')
    print(json.dumps(build(parser.parse_args()), ensure_ascii=False))
