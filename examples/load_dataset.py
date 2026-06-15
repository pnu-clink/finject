#!/usr/bin/env python3
"""Minimal example for loading the FInject JSONL release."""

from __future__ import annotations

import json
from pathlib import Path


path = Path(__file__).resolve().parents[1] / "data/final_release/finject_final_426.jsonl"

with path.open(encoding="utf-8") as f:
    rows = [json.loads(line) for line in f if line.strip()]

print(f"Loaded {len(rows)} FInject rows")
print(rows[0]["sample_id"])
print(rows[0]["category"])
print(rows[0]["question"])
