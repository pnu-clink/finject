"""Read saved JSON context adapter checks in the single dataset viewer."""
import hashlib
import json
from pathlib import Path


def view(bundle):
    bundle = Path(bundle)
    report = json.loads((bundle / "json-context-adapter-check.json").read_text())
    if report.get("format") != "json-context-adapter-check-v1":
        raise ValueError("INVALID_JSON_CONTEXT_ADAPTER_REPORT")
    payload = {"format": "fin-arch-viewer-v1", "runs": [],
               "batch": {"name": bundle.name, "layout": report["format"], "rounds": [], "round": None,
                         "json_context_adapter": report, "summary": report["summary"],
                         "readme": (bundle / "README.md").read_text()}}
    payload["revision"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload
