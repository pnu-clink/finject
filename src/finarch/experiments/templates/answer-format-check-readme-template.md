# V4 response format local scanner

State of play: **{status}** • Offline testing {tests}items passes call new model {calls}That one.

## Reading order

1. `verification.json`Check results: Prompt/Skyma hash V2 and V3 compatibility.
2. `tests.log`: The actual check log.
3. `request-example.json`: Synthetic Q/C and minor digits; Prompt schemes.
4. `provider-request-example.json`: Gemini request example, which is configured to match the actual delivery method.
5. `expected-response-example.json`Formal validation: expected response. Not LLM output.

The actual program and rules:](../../../../docs/02-experiments/README.md).
The compliance rate for the new model is a mismatch.003I passed the V2 request test of the fixed manifest.
