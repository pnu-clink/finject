"""Persist pending human review without approving a variant."""
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write

def gg01_collect_results(bundle, item):
    record = {"status":"AWAITING_HUMAN","automatic_status":item["status"],"reason":item.get("reason",""),"observation":item.get("observation"),"source":item["path"]}
    if item.get('inverse_review_ref'):
        record['inverse_review_ref'] = item['inverse_review_ref']
    write(bundle/item["path"]/"05-human-review/01-result.json", record)


def run(bundle, item):
    return gg01_collect_results(bundle, item)

collect = run


def gg02_LLM_interpret_failure(request, directory, config, profiles):
    """Explicit viewer action only; automatic review collection never calls this."""
    from finarch.dataset.shared.review.failure_interpretation import interpret
    return interpret(request, directory, config, profiles)
