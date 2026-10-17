# {run_id}cache and re-enactments.

**The actual model call is a cache blocking function that is not known 0entries.** The same. 100The original.700We're using a variation. 3,000Request for an experiment 1: 200The experiment. 2: 2,800I'm ready, but I'm not done with the cache.

## Why didn't you call?

The Codex CLI installed 0.155.0The help app-server generating schemes and the official config schemes could not verify the cache deactivation settings. `--ephemeral`You can't record that you're reading and writing off just by changing the cache key. `codex-luna/cache-preflight.json`There's a blocking property. 0The token and the cache-based verification are different.

The policy that we've added to this applies to the API, which is the Gemini Developer API path that doesn't even check the silent cache blocking control, but blocks before transmission. 0It's not considered.

## {reference_run}The actual record of

|Reasoning setting|Response count|Enter the cache use response number|Full input token|Cache input tokens among them|The total of returned cache writing tokens|Write item missing answer number|Returns the reasoning output token|
|---|---:|---:|---:|---:|---:|---:|---:|
{usage_table}

The table is the last reading of each request's response usage, and the cache input is included in the entire input. `cached_input_tokens`So, the item to write is `cache_write_input_tokens`So the write sum is just adding the returned items together, and the missing ones are just adding up. 0And it's only when you're working that you read all the responses as having been written. 0If the read is positive, then the answer is using a cache.

{correction_note}

The input cache is a function of reusing the input portion that has already been calculated. This alone does not mean that the previous answer or reasoning result has been returned as it is. The official document explains that the output is newly generated.](https://developers.openai.com/api/docs/guides/prompt-caching).

## Preserving the comparison conditions

The basic variable open input, non-public response, P0/P1; common prompt, the V4 hash of the schemes is the same as the previous run. {requests:,}The content of the entire request, the order of the request, the new cache policy record and the request ID that followed, were changed, and the existing response was not. `cache-audit.json`is the location.

## Alternatives to the path that we can follow

OpenAI's official API is GPT-5.6 And then we're going to model `prompt_cache_options.mode="explicit"`It explains that if you don't specify and enter the breakpoint, the input cache doesn't read and write all of it.](https://developers.openai.com/api/docs/guides/prompt-caching).

An alternative to calling the same Luna as the Payment Responses API `api-alternative-plan.json`The current experimental adapter is a microwave and there is no actual transmission. {requests:,}Turn, input the drug. {input_estimate}The number of characters4 estimate), output-reasoning sum per request 1,000In the token family, **Drugs. ${cost}**This is the $.0.20M. output $1.20It was calculated as the standard API of /M, and the Batch discount and the cache discount were not applied, depending on the actual token and not the cost.](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

The current setting is still a subscription CLI and hasn't switched automatically to a paid API. The API switching can't be claimed to be a separate comparison, depending on the overhead path and the basic instructions that Codex gives, but only the caching effect.

## Read sequence and reproducibility

1. This article `REPORT.md`: Block private and complete plan; missile row count.
2. `codex-luna/cache-preflight.json` → `state.json` → `events.jsonl`: actual pre-examination and call 0That one.
3. `cache-audit.json`: previous usage and input/request identification check.
4. `api-alternative-plan.json`: Payment API alternatives that haven't been implemented yet.

Renewability is a very important thing. `PYTHONPATH=src .venv/bin/python -m finarch.experiments.01-evaluation.04-validation.cache_audit --run reports/experiments-run/{run_id} --reference reports/experiments-run/{reference_run}`This command doesn't just read the stored files and call the model, and it doesn't create any HTML.
