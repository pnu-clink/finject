"""Current experiment prompt and schema files, named by pipeline stage."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROMPTS = {
    'solver_common': '01-evaluation.02-request.common.md',
    'solver_unguided': '01-evaluation.02-request.unguided.md',
    'solver_guided': '01-evaluation.02-request.guided.md',
    'analysis_common': 'shared.02-analysis.02-03.common.md',
    'comparison_common': 'shared.02-analysis.02-comparison.common.md',
    'comparison': '02-analysis.02-comparison.response-patterns.md',
    'research': '02-analysis.03-research.findings.md',
    'quadrant_findings': '02-analysis.04-quadrant.findings.md',
}
SCHEMAS = {
    'solver_response': '01-evaluation.02-request.solver.response.schema.json',
    'interpretations': '02-analysis.02-comparison.interpretations.schema.json',
    'comparison_response': '02-analysis.02-comparison.response.schema.json',
    'research_response': '02-analysis.03-research.findings.response.schema.json',
    'quadrant_response': '02-analysis.04-quadrant.findings.response.schema.json',
}


def prompt_path(name):
    return ROOT / 'prompts' / PROMPTS[name]


def schema_path(name):
    return ROOT / 'schemas/json' / SCHEMAS[name]


def prompt_text(name):
    value = prompt_path(name).read_text()
    if not value.strip():
        raise ValueError('EMPTY_EXPERIMENT_PROMPT:' + name)
    return value


def schema(name):
    value = json.loads(schema_path(name).read_text())
    if not isinstance(value, dict) or not (value.get('properties') or value.get('items')):
        raise ValueError('EMPTY_EXPERIMENT_SCHEMA:' + name)
    return value
