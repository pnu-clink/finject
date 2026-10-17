# 1The raw response review of the tea

Running: **{{run}}** · The organizational view: {{updated}}

**The current step is to verify the data, and the new content of the Codex has not yet been assessed and improved.** The target LLM solves the problem with an API, and then analyzes the response directly in this Codex conversation, and then shows the analytical results to the user and then works out the next experiment together.

The input-response judgments and reviews of the same Luna API in the past are excluded from the basis of this analysis. 1·2·3The comparison of the rate of tea appropriation, improvement/ejaculation, and the paper's commentary are a commodity. The actual grass raw response, cost and availability score is not deleted or changed.

## 00 · The scope of this reading

|The data.|Confirmed content|
|---|---|
|Target|Same one. 100items and every single copy of the 7The transformation, the gun. 800inputs|
|The original grass.|Unguided Solving × Reasoning OFF/ON = 200Response|
|The transformed grass.|Unguided / Criteria-Guided Solving × Reasoning OFF/ON = 2,800Response|
|Run|GPT-6-Luna · OpenAI Native Batch · Returned reply 3,000entries|
|Reasoning setting|OFF = none / ON = medium|
|Limiting the output|max_output_tokens = 8,192Explanation to the maximum 2,000So, the evidence is up to 12Each corner 1,500Now, what?|
|Select range|Original work that has passed the manufacturing automation test;7The variation set 100The man's judgment record of the original is pending.|
|Work in progress|Check the input, actual request, output connections and record statistics only. Call the new API 0times|

## 01 · Input → instruction → actual request

|In order.|The data.|What do you check?|
|---|---|---|
|1|[public.jsonl](../../01-input/public.jsonl)|800The full-featured question/context/answer_format.decimal_places and the linked item_id. The actual user message only transmits three Q/C·precision fields|
|2|[private.jsonl](../../01-input/private.jsonl)|800H. Assessment time. Source correct answer. Participation information. Production type. Problem solving of the object model input and separation|
|3|[Common directions](../../00-definition/common.md)[The common grass is directed](../../00-definition/p0-standard.md)[The grass is directed according to the standard].](../../00-definition/p1-abstention-aware.md)|Not the latest version of the work folder. **1The car call.**|
|4|[Common response schema](../../00-definition/response.schema.json)|The output field and the data type that the two directions share|
|5|`luna-api/01-requests/manifest.jsonl`|3,000The phrases, templates, conditions of the items request and the actual input/prompt/schema link.|
|6|`luna-api/02-batches/batch-001/input.jsonl`|Check the model/instructions/input/reasoning/text.format/max_output_tokens that have been passed to the API|

The transmission files 3,000We compared the user input to the public, and we verified that it was precise, including the question/context/answer_format only, and that it wasn't complete by entering private information.

The manifest and batch transfer files are approximately 27MBIt's a full archive. **100The actual request-response link in the case**I'm going to read it in phrases. `request.input`, `request.prompt`, `request.response_schema`We can see it together.

## 02 • What was returned?

|The field.|What the model is doing|What we'll find in the next analysis.|
|---|---|---|
|answer|The final number or null|Is it the exact same as the order, order, and order?|
|answer_meta|And if negative and scale, and answer is equal to zero, then both are null.|So, what is the answer to that?|
|explanation|Reasons for calculation and judgement; Criteria-Guided Solving includes a Classification/Response declaration|Did you keep the input relationship; did the classification and the behavior match?|
|evidence|So the quotation sequence is taken from context.|So, what's the difference between a quote and whether it supports a real line?|

[List of results](../../luna-api/03-results/results.jsonl) `call_path`And then you connect the request-response to a file, `result_path`The record of the call files is stored in the check `records.raw_response_path`You can open the actual file with the link in the list of cases below.

## 03 • Number verified without a content judgment

The format validation is stored: **{{valid}} / 3,000 Pass**Formulation does not mean that the root, the logic, the distribution is right.

|The original condition|Numeric match|Numeric mismatch|No numeric answer|The plan.|
|---|---:|---:|---:|---:|
{{original_counts}}

The lower cell is **Number response / null response**And they're all real. `answer` It's an observation of a value, and null was not determined to be a proper eubenous or an invalid answer. 100items.

|Type of input|Unguided · OFF|Unguided · ON|Criteria-Guided · OFF|Criteria-Guided · ON|
|---|---:|---:|---:|---:|
{{answer_counts}}

## 04 · Open the data according to a single copy

The first case of the case number of the interval **{{sample_case}}**I use data-linking examples, not just to pick out a case that's not working or not working.

Question: {{sample_question}}

precision: {{sample_precision}}space · value of the reference: {{sample_reference}}. Reference is the evaluation information that you read from private.

### Two actual responses to the original.

{{sample_original}}

### The first variation of the same case is IC_VALUE_01_BEFORE

The difference between the original and the context of the variation is called the request.input.context or the viewfinder of the file below. **Case comparison**Check in. Check out what sentences you actually delivered before reading your response.

{{sample_variant}}

## 05 · The original 100Find the items and the request and output

**The OFF/ON column is just a number matching.** It doesn't mean logical, functional, or classification validity. In each call file, you can check the request path of the cases, the latest JSON, the raw response path of the user. 4The entire condition is selected from the same case in the viewer.

|Source text|Reference value of the rating|The original is OFF.|The original on.|The four conditions of the first transformation.|
|---|---:|---|---|---|
{{case_index}}

## 06 · The sequence of analysis and argumentation afterwards

|Stage|Responsibility|I'll show you the data.|Current state of play|
|---|---|---|---|
|Check the data|The codex stores input, directory, and raw response connections|This document and the actual call JSON|Ready to finish · Before user verification|
|Content analysis|The Codex directly contrasts Q/C with answer/explanation/evidence.|Article: Conditional observation, basis for calculation, reason for not judging|We're not even starting yet.|
|Conditions of comparison|The Codex is the original OFF/ON, 7Type x4Conditions, reverse case connections|The denominator is the basis of the comparison and the basis of origin|Following the analysis of the content|
|The improvement of the|Present the results of the analysis and decide the user and the change and the property|Changes to the proposal and the agreement|The competition.|
|The next experiment.|Apply only the agreed changes to the subject LLM call|New request: raw response|Not started|

Calculator aids and statistics can be done in local code, but they don't assign meaning judgments to other API models, and at this stage they don' t fix the prompt schema, correct answer, denominator, or write new paper conclusions.

Produced: `src/finarch/experiments/02-analysis/legacy/content-analysis/codex_review_materials.py` · Original connection, home network access · No API calls.
