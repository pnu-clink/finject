# Analysis is a prompt to understand

[Source guide](../../../../src/finarch/experiments/02-analysis/README.md) · [Operating records](../README.md) · [Common viewer](http://127.0.0.1:8893/?run=20260927-experiment-source-layout&doc=reports%2Frun%2F20260927-experiment-source-layout%2Fprompt-clarity%2FREADME.md)

The model now receives the prompt data response scheme for the request, and so as not to assume that you've read other conversations or project documents, you've changed the internal step number to the actual task and field description, which is the same description that Codex and API use.

## What have you changed?

|Conventional expression or omission|Currently|
|---|---|
|`E04 numeric comparison`|`numeric_comparison.matches`: Results of comparing the number of standard answers and original answers to existing rules. Distinguishing between the validity of the explanation or meaning of the correct answer judgment|
|`original_result`The connection is omitted|Distinguish between MATCH/MISMATCH/UNEVALUATED of the original and NOT_ORIGINAL of the variation. When tying the variation, the same model is linked to the original row of the instruction-reference setting|
|`D02` The number of the follow-up discussion.|Subsequent comparison to distinguish the impact of the source tag and the position of the claim.|
|Conditions and Problem Type Code|Unguided/Criteria-Guided, Reasoning OFF/ON, the original and the actual meaning of the seven variations; parent relationship description|
|Formatting pass and number nomination|VALID is the format pass, A/B is the matching of the reference and alternate numbers, FRONT/BACK is the position of the argument|
|Study interpretation of the set and the partition input|Explain the meaning and denominator of the whole; conditionally; originally; corresponding pair set. Explain that the repeating set in multiple input sets should not be recombined|

## File roles and reading order

|In order.|File|Confirmation of the|
|---|---|---|
|1|[The entire prompt to be delivered to the analysis of the data](comparison-current.md)|A common description and comparison analysis instruction combined with the actual current string|
|2|[The entire prompt to be delivered to the research interpretation](research-current.md)|A common description and a compilation/analysis instruction combined with the actual current string|
|3|[Common explanation](common-current.md)|The conditions that the two requests share: variable definition and scope of analysis|
|4|[Previous comparison prompt](comparison-before.md) · [Previous research prompt](research-before.md) · [Previous common explanation](common-before.md)|Correction of the pre-primary|
|5|[Local verification](validation.json) · [Check log](local-checks.log)|Prompt verification, current local checks, running backup status|
|6|[Operating log](../events.jsonl)|Fix, check, check the screen|

The current source is [pipeline.py](../../../../src/finarch/experiments/02-analysis/pipeline.py)Come on, you know what?](../../../../src/finarch/experiments/02-analysis/llm_backend.py)The new analysis request uses this string and schema when you restart the execution. The already-consolidated request is subject to change checks and does not overwrite the previous source.

This is a local code-text verification, not a verification of the understanding of the actual analytical model or the quality of the response, but a maintenance of Haiku and Analysis running without the model calling and assigning.

This README is generated from `src/finarch/documentation/templates/experiment-analysis-prompt-clarity.md`.
