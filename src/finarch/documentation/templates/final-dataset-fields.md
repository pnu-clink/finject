# FInject dataset fields

Read [dataset.jsonl](dataset.jsonl) for the combined data and [dataset.schema.json](dataset.schema.json) for its record contract. Each line contains one family: the original and its seven variants. There are __FAMILIES__ families, __VARIANTS__ variants, and __ITEMS__ total items.

This export retains the questions, contexts, answers, precision, item IDs, content hashes, annotations, and edit provenance from [dataset-original.jsonl](dataset-original.jsonl). It embeds the saved annotations from [EA_INVERSE_REVIEW.jsonl](EA_INVERSE_REVIEW.jsonl) in each EA variant. The original data and schema are preserved as `dataset-original.jsonl` and `dataset-original.schema.json`. The previous manifest is preserved byte-for-byte as [manifest-original.json](manifest-original.json), with its historical filenames. The current [manifest.json](manifest.json) records the active files and the preserved originals. No reviews or generation steps were rerun.

## Embedded EA review

Every `EA_01` and `EA_02` item has `variants[].metadata.inverse_review`. Other item types do not have this field. The review belongs to the containing item's question and context; these texts and their IDs are not duplicated inside it.

| Field | Meaning |
| --- | --- |
| `status` | `COMPLETED`, `CALL_FAILED`, or `NOT_RECORDED` in this export. |
| `inverse_possible` | The saved review's Boolean judgment; null when the review failed or was not recorded. |
| `missing_quantity` | The saved description of the missing quantity; null without a completed review. |
| `reason` | The saved explanation of the judgment; null without a completed review. |
| `formula` | The saved recovery formula, which can be null. |
| `evidence` | Original evidence quotes and character offsets in the containing item's `question` or `context`; null without a completed review. |
| `evidence_display_check` | The complete saved display check, including its status, original/resolved coordinates, and resolved evidence. Null when no record exists. |
| `model` | Saved `provider`, `model`, and `effort`; null when no record exists. |
| `timestamp` | Saved review time; null when no record exists. |
| `affects_quality_status` | Always false: this annotation does not change the item's existing quality status. |
| `failure_reason` | The saved API failure reason for failed reviews; null otherwise. This is separate from the judgment's `reason`. |

| Saved result | EA items |
| --- | ---: |
| Completed, inverse possible | __INVERSE_TRUE__ |
| Completed, inverse not possible | __INVERSE_FALSE__ |
| Call failed | __CALL_FAILED__ |
| Not recorded | __NOT_RECORDED__ |
| Total | __EA_ITEMS__ |

Null does not mean false. These annotations are LLM judgments from the remaining question and context, not independently certified answerability labels. The existing `annotation.status` and automatic-validation status are preserved separately. Evidence-display checks verify coordinates for display, not whether a formula proves recoverability. The saved display checks include __DISPLAY_PASS__ `PASS`, __DISPLAY_WARNING__ `WARNING`, __DISPLAY_NOT_RUN__ `NOT_RUN`, and __DISPLAY_MISSING__ absent records; all are preserved.

For completed reviews, `missing_quantity`, `reason`, `formula`, and `evidence` come directly from the source entry's `review_record.inverse_review`. `status`, `inverse_possible`, and `evidence_display_check` come from the source EA entry. Model information and the timestamp come from `review_record`; `failure_reason` comes from its top-level `reason`. `NOT_RECORDED` represents the source's `availability: MISSING`. Records were joined by `item_id` after checking the family, type, question, context, and content hash.

The compact review omits internal request paths, source-file paths, retry bookkeeping, and the full model configuration. These remain available in the unchanged source files. The `evidence` and `evidence_display_check` objects preserve their original contents, including coordinate warnings.

## Fields omitted from the compact copy

| Location | Omitted fields | Retained information |
| --- | --- | --- |
| `source_input` | `context_mapping`, `source_content` | Original input fields and source provenance. |
| `original.metadata` | `reference_metadata_repair` | Reference answer, answer type, precision, answer metadata, and external-knowledge metadata. |
| Each item's `metadata` | `publication_source` | Remaining metadata, including provenance and edit provenance where present. |
| Each item's `automatic_validation` | `round`, `reason` | `status`. |
| Each item's `production_review` | `record`, `source` | `decision`, including existing null or pending values. |
| `production_selection` | `policy`, `exclusion_reasons` | `eligible`. |

The former nested EA review wrapper is replaced by the embedded structure above. The parent item's `source` field and all unlisted fields remain unchanged.

## Read a saved review

Run from the repository root to display the first completed review from the actual file:

```python
import json
from pathlib import Path

path = Path("data/final/finject-20261007/dataset.jsonl")
with path.open(encoding="utf-8") as stream:
    for line in stream:
        family = json.loads(line)
        completed = [
            item for item in family["variants"]
            if item["metadata"].get("inverse_review", {}).get("status") == "COMPLETED"
        ]
        if completed:
            item = completed[0]
            print(item["item_id"])
            print(json.dumps(item["metadata"]["inverse_review"], indent=2, ensure_ascii=False))
            break
```

The existing Evaluation loader reads this `dataset.jsonl` and verifies its hash against the updated `manifest.json`. See the [dataset guide](README.md) for the Evaluation and viewer entry points. No loader or configuration changes are required for this filename change. The embedded review can also be inspected directly with the example above.

## File identity

| File | SHA-256 |
| --- | --- |
| `dataset.jsonl` | `__COMPACT_SHA256__` |
| `dataset-original.jsonl` | `__DATASET_SHA256__` |
| `EA_INVERSE_REVIEW.jsonl` | `__EA_SHA256__` |

The compact JSONL is __COMPACT_BYTES__ bytes. Its companion schema extends the existing dataset record contract with the embedded review structure. This README is rendered from `src/finarch/documentation/templates/final-dataset-fields.md`.
