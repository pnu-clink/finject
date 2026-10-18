"""Runnable template using the supplied FinanceReasoning sample.

Copy this file to adapter_<dataset>.py and change only deterministic field
mapping, record iteration and context assembly for your actual source format.
The template ignores original solution code, difficulty and scale metadata.
"""
from finarch.dataset.shared.adapter import make_record


def adapt(sources):
    """Yield one converted item per question in the supplied file order."""
    for source in sources:
        records = source.json()
        if not isinstance(records, list):
            raise ValueError('EXPECTED_A_JSON_ARRAY_OF_RECORDS')
        for index, raw in enumerate(records):
            origin = source.origin(raw, locator=f'/{index}', index=index)
            yield make_record(
                q=raw['question'],
                c=raw['context'],
                a=raw['ground_truth'],
                origins=[origin],
            )
