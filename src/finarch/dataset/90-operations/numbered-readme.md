# Running sequence and actual output

{case_name} · The link below is the actual file saved in this run.

The folder number is in the order of processing. LLM calls read in the order they are entered received → request prepared → call → raw response received → response checked → results applied. `request`The actual transmission request, `raw-response`The model is raw response, `handler-response`The Python processing envelope, `result`It's a test-to-use result, which distinguishes between raw response and processing results.

4And then there are four changes. 5The bar is a meaning test after the phrase is created. The backward arrangement of the front and back pairs uses the same phrase as the one created in this execution, and it's not a separate LLM call. Human judgment and inference and experimentation only results when it's actually performed.

The resulting folder and the log folder have the same case, step, sub-processing path. `default.log`The detailed timeline is the log of the `sequence`I'll check it out.

{sections}
