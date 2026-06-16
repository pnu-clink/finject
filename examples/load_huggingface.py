#!/usr/bin/env python3
"""Load FInject from the Hugging Face dataset mirror."""

from __future__ import annotations

from datasets import load_dataset


DATASET_ID = "pnu-clink/finject"

final = load_dataset(DATASET_ID, split="test")
controls = load_dataset(DATASET_ID, "original_controls", split="test")

print(f"Loaded {len(final)} final unanswerable variants")
print(f"Loaded {len(controls)} original controls")
print(final[0]["sample_id"])
print(final[0]["category"])
print(final[0]["question"])
