"""Explicit adapters for two source schemas. Source programs are never executed."""

from decimal import Decimal

from finarch.shared.reference import extract_reference
assemble = __import__('finarch.dataset.00-input.content', fromlist=['assemble']).assemble


# IN.03: docs/01-dataset/00-input/01-selection.md
def finance(record: dict, source: dict, *, allow_embedded=False, distributed=False) -> dict:
    """Prepare Q/C/A, normalizing JSON table contexts before numeric registration.

    The source schema selects this adapter. Actual context shape selects JSON
    conversion because a single upstream source can contain both JSON and prose.
    """
    if not distributed and not record["source"].startswith("FinanceReasoning-") and not (allow_embedded and record["source"].startswith(("CodeFinQA-", "CodeTAT-QA-"))):
        raise ValueError("NOT_NATIVE_FINANCE_REASONING")
    return {
        "raw_id": "finance-" + record["question_id"],
        **assemble(record, "finance"), "question": record["question"],
        **extract_reference(record["ground_truth"]).fields(),
        "answer_metadata": {"scale": None,
                            "negative": Decimal(extract_reference(record["ground_truth"]).reference_answer).is_signed()},
        "provenance": {**source, "dataset": "FinanceReasoning-native" if record["source"].startswith("FinanceReasoning-") else "FinanceReasoning-embedded",
                       "source_id": record["source"], "level": record["level"]},
    }


# IN.03: docs/01-dataset/00-input/01-selection.md
def tatqa(record: dict, question: dict, source: dict) -> dict:
    """Prepare one arithmetic question from the native TAT-QA table schema."""
    if question["answer_type"] != "arithmetic":
        raise ValueError("NOT_ARITHMETIC")
    return {
        "raw_id": "tatqa-" + question["uid"],
        **assemble(record, "tatqa"), "question": question["question"],
        **extract_reference(question["answer"]).fields(),
        "answer_metadata": {"scale": None if question["scale"] == "" else question["scale"],
                            "negative": Decimal(extract_reference(question["answer"]).reference_answer).is_signed()},
        "provenance": {**source, "dataset": "TAT-QA", "document_id": record["table"]["uid"]},
    }
