# The numerical form of the experimental analysis guide

1. [Analysis report](../ANALYSIS.md): comparison of the original numbers, variation-specific ubo declarations, form failure, resource use.
2. `Model name-failures.md`Failure: The actual question of the numerical inconsistency case.
3. `response-diagnostics.jsonl`Each request has a diagnostic tag and a token to use.
4. `Model name-resources.json`: CPU memory, concurrent processing number of observation range.
5. `Model name-precision-conflicts.jsonl`: The explicit minor digits of the question and the actual metadata transmitted are different requests.
6. `verification.json`If this is the case, check the results of the input hash, request, sub-token, source log, link, local return checks that were performed after execution.

Numeric_analysis.py only reads the saved response, does not call an additional evaluation model, and does not convert the ubo declaration to ubo accuracy. This README generates from the template.
