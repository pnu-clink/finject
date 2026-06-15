# Answerability Evaluation Prompt

This is the text-only evidence-sufficiency prompt used to evaluate answerable original controls and FInject unanswerable variants. Models receive only the question and context, with no retrieval, tools, calculators, files, code execution, or web search.

```text
You are solving a financial numerical reasoning problem.

Use only the provided question and context. Do not use outside knowledge,
unstated assumptions, memorized benchmark answers, or plausible default values.
Do not call external tools, calculators, code execution, web search, or files.

Follow this procedure internally before producing the final JSON:
1. Identify the formula or reasoning procedure needed to answer the question.
2. Identify every quantity, premise, condition, time period, and source choice
   required by that procedure.
3. Check whether each required item is explicitly available in the context.
4. Check whether any required item has unresolved conflicting values, source
   statements, or premises. If two plausible alternatives are present and the
   context gives no explicit priority rule, the answer is not uniquely supported.
5. If any required item is missing, not recoverable from the context, or
   contradicted without a priority rule, do not guess.
6. If the context is sufficient and non-contradictory, compute the answer
   carefully using step-by-step arithmetic internally.

Return only valid JSON in one of the following two forms:
{"decision":"INSUFFICIENT_INFORMATION","answer":null}
or:
{"decision":"ANSWER","answer":<numeric answer>}

The numeric answer should follow the rounding and unit instructions in the
question. Do not include explanations, code fences, or extra keys.

Question:
{question}

Context:
{context}
```
