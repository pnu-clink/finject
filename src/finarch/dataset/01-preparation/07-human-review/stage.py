"""Collect the actual preparation outcome without granting approval."""
def pp01_collect_results(ctx, report):
    ctx.save("07-human-review/01-collect-review-package/01-result.json", report)


def run(ctx, report):
    return pp01_collect_results(ctx, report)

collect = run


def pp02_LLM_interpret_failure(request, directory, config, profiles):
    """Explicit viewer action only; automatic review collection never calls this."""
    from finarch.dataset.shared.review.failure_interpretation import interpret
    return interpret(request, directory, config, profiles)
