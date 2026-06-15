# Stage 1: Deterministic Structural Gate

Stage 1 is the deterministic validation layer described in the paper. It checks
whether a generated perturbation has the visible form required by its intended
category before any semantic judging is performed.

This public folder contains the structural-check reference implementation only.
Intermediate construction inputs, raw generator outputs, Excel audit workbooks,
and Stage 1 result exports are intentionally not included in the release.

## Categories

- `EA-partial`: exactly one `[DATA MISSING]` marker replaces a numeric value.
- `EA-full`: one carrier sentence, clause, table row, cell, or entry is removed
  without leaving an explicit marker.
- `SA`: a numeric value is removed or neutralized without a visible marker.
- `IC-value`: two different numeric values appear for the same quantity label.
- `IC-source`: named sources attribute different values to the same quantity.
- `IC-premise`: an additional premise is inserted as a condition on the same
  calculation rather than as a replacement answer.

Stage 1 does not decide whether the removed evidence is truly answer-critical or
whether a conflict is semantically resolvable. Those judgments belong to Stage 2.

## Usage

```bash
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt

PYTHONPATH=src ./venv/bin/python src/stage1_structural_gate.py \
  --input candidates.jsonl \
  --output stage1_audit.jsonl
```

The input file should contain one JSON object per line with:

```json
{
  "category": "EA-partial",
  "original_context": "...",
  "perturbed_context": "...",
  "origin_python_solution": "...",
  "question": "..."
}
```

The output reports `stage1_pass`, failed required predicates, forbidden-pattern
deductions, and the diagnostic score. As in the supplementary material,
`stage1_pass` is decided by the required gates; deductions lower the diagnostic
score and should be inspected as audit signals. Public final-release rows
already include their construction provenance; this script is provided to make
the deterministic Stage 1 logic auditable, not to regenerate the paper's
intermediate exports or to relabel the human-repaired final release. The paper's
Stage 1 count is computed over the internal raw construction pool before Stage 2
and human repair.

## Directory Layout

```text
src/
  stage1_structural_gate.py   JSONL CLI wrapper for the Stage 1 gate
  perturb/                    structural predicates and text utilities
docs/
  FInject_stage1_conformance_spec.md
```
