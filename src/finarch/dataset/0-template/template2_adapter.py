# Append to 00-input/adapters.py, beside finance() and tatqa().
# Source-specific preprocessing belongs in 00-input/__DATASET__.py.
def __DATASET__(record: dict, question: dict, source: dict) -> dict:
    """Register preprocessed source input using the existing common helpers."""
    from finarch.shared.reference import Reference, load_raw

    token = question['answer']
    reference = Reference('-0', 'integer', 0) if token == '-0' else extract_reference(load_raw(token))
    return {
        'raw_id': question['uid'],
        **assemble(record, 'parts'),
        'question': question['question'],
        **reference.fields(),
        'answer_metadata': {'scale': None, 'negative': Decimal(reference.reference_answer).is_signed()},
        'provenance': {**source, 'dataset': __DATASET_LITERAL__},
    }
