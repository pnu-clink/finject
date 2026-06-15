"""perturb.constants — domain constants for Stage 1 structural validation.

This module can be imported without side effects; the only external dependency is
the standard `re` module.
"""
from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Category (transformation type) ordering
# ---------------------------------------------------------------------------
TYPE_ORDER = ["EA-partial", "EA-full", "SA", "IC-value", "IC-source", "IC-premise"]


# ---------------------------------------------------------------------------
# Perturbation request prompt summary.
#
# The full public construction prompt is released in
# ../../../../prompts/perturbation_generation.md. These strings are kept here so
# the Stage 1 checker can expose the category contract alongside its predicates.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a financial-data perturbation expert.

You will be provided with a QUESTION, a CONTEXT, the CORRECT ANSWER, and a reference
SOLUTION. The answer is currently DEDUCIBLE from the context. Your task is to modify
ONLY the context, per the given Transformation Type, so that a competent solver can
no longer derive a unique correct answer. This evaluates evidence sufficiency and
abstention under missing or conflicting financial evidence.

Method (all types):
1. Use the reference solution to identify the data ESSENTIAL to the answer.
2. Review the context SENTENCE BY SENTENCE. Keep the MAJORITY of it unchanged and
   touch only what the Transformation Type requires.
3. The result must read as fluent, grammatically complete, and natural English,
   matching the prose style of the original context (period-separated sentences,
   no semicolons, em-dashes, or other markers absent from the original).
4. Do NOT change the question. Transform the context only. If there is no context,
   transform the question itself.
5. For conflict types, ADD a contradicting value or premise rather than removing data.
6. Output ONLY the specified JSON object — no commentary, no code fences — and fill
   "derivable_check" with a justification of why the answer is now underivable or
   underdetermined.
"""


CATEGORY_INSTRUCTIONS = {
    "EA-partial": """Transformation Type: EA-partial (Explicit Absence, Partial)

Replace exactly one answer-critical value with the explicit marker \"[DATA MISSING]\".
- Replace only a value that is necessary for deriving the unique answer.
- Do NOT replace a value that can be back-derived from the remaining data.
  Example: if Total = A + B, replacing A is invalid (Total - B recovers it).
- Choose an independent input value that cannot be recovered.
- The marker must be visible — the reader should clearly see something is missing.""",

    "EA-full": """Transformation Type: EA-full (Explicit Absence, Full)

Delete the sentence, clause, table row, cell, or entry that carries the answer-critical value.
- The deleted block must contain data necessary for deriving the unique answer.
- After deletion, the answer must NOT be back-derivable from what remains.
- Do NOT leave a \"[DATA MISSING]\" marker; the block is simply gone.
- Preserve unrelated question/action clauses and the surrounding context structure.""",

    "SA": """Transformation Type: SA (Silent Absence)

Remove only the numeric value of an answer-critical quantity WITHOUT leaving any explicit trace.
- After removal, the surrounding context must read as fully natural and complete.
- NEVER leave markers like \"N/A\" or \"[DATA MISSING]\".
- Keep a natural reference to the quantity itself when possible.
- A reader should NOT feel that anything is missing.
- This is the hardest transformation — naturalness is the key criterion.""",

    # --- Three new IC types introduced in v4 (appendix_v1.1_EN.md §C) — for display/reference ---
    "IC-value": """Transformation Type: IC-value (Intra-context Value Conflict)

Pick ONE answer-critical numeric value. Decide a SECOND value for the SAME quantity that is
DIFFERENT but FINANCIALLY PLAUSIBLE — same order of magnitude / within the valid domain
range (e.g., tax rate 25% to 28%). A digit-order (x10) or absurd value is FORBIDDEN.
- Keep the original statement; add a second natural statement of the same quantity in a
  SEPARATE, NON-ADJACENT sentence (NOT two contradictory numbers back-to-back).
- Present BARE: NO attribution phrases, NO purposive qualifiers, NO different units.
- Provide NO cue (no corrected/updated/approximately; no third reconciling value).""",
    "IC-source": """Transformation Type: IC-source (Inter-source Value Conflict)

Keep the original value. ADD a conflicting value for the SAME answer-critical quantity,
attributed to two financial sources of EQUAL authority, recency, and topical relevance.
- NEVER mark one source as authoritative / official / audited / latest / revised /
  corrected — UNLESS the same marker applies equally to both. Provide NO recency clue.
- Provide no cue that lets a solver prefer one source.""",
    "IC-premise": """Transformation Type: IC-premise (Mutually-Exclusive Premise)

Insert/alter the context to assert TWO statements that CANNOT both be true, where BOTH are
answer-critical. Each must create a LOGICAL / categorical incompatibility (NOT a numeric
mismatch — that is IC-value), be factual, independently reasonable, and use distinct
wording with explicit entity names.
- Do NOT attribute either premise to an authority. Both premises stated as plain facts.
- A zero-vs-positive numeric conflict (no debt + debt=$100M) is an IC-value candidate.""",
}


USER_TEMPLATE = """## Transformation Type
{CATEGORY_INSTRUCTION}

---

## Original Problem

**Question:**
{question}

**Context:**
{context}

**Python Solution (reference for identifying essential data):**
```python
{python_solution}
```

**Ground Truth:** {ground_truth}

---

## Instructions

1. Analyze the python_solution to identify the data ESSENTIAL to deriving the answer.
2. Check whether removing/altering that data still allows back-derivation from the rest.
3. Pick non-recoverable essential data and transform it per the Transformation Type above.
4. Transform the CONTEXT only. Do NOT change the question.

## Output Format (output ONLY this JSON object, nothing else)

{{
  "is_transformable": true | false,
  "reason_if_not": "<reason if not transformable, else null>",
  "critical_data": ["<list of data essential to the solution>"],
  "removed_or_modified": "<what was removed or modified>",
  "derivable_check": "<your back-derivation analysis>",
  "transformed_context": "<the full transformed context>",
  "description": "<one-line summary of the transformation>"
}}"""


# ---------------------------------------------------------------------------
# Colors and verdicts
# ---------------------------------------------------------------------------
COLORS = {
    "header_bg":        "1F4E78",
    "header_fg":        "FFFFFF",
    "claude_change_bg": "F5E6D8",
    "claude_change_fg": "8B4513",
    "claude_col_bg":    "FDF6EF",
    "orig_change_bg":   "D9E2F3",
    "orig_change_fg":   "1F4E78",
    "orig_col_bg":      "F2F6FC",
    "pass_bg":          "BDD7EE",   # blue family (PASS)
    "pass_fg":          "1F4E78",
    "fail_bg":          "F4CCCC",   # red family (FAIL)
    "fail_fg":          "990000",
    "notxf_bg":         "C0504D",   # deeper red — is_transformable=false cases
    "notxf_fg":         "FFFFFF",
    "qxf_bg":           "E4D7F2",   # light purple — Q transform (context_original empty; the question itself is the transform target)
    "qxf_fg":           "5B2C8C",
    "border":           "B7B7B7",
    "verdict": {
        "Identical (exact match)":                              "C6EFCE",
        "Equivalent (minor difference)":                       "D6E5C8",
        "Equivalent (some key-number difference)":               "E5EFC8",
        "Equivalent (reworded, key numbers match)":  "D9EAD3",
        "Partial match (numeric/data difference)":             "FFEB9C",
        "Similar but differing (recheck needed)":              "FFE0B2",
        "Different (major structural/content difference)":                 "FFC7CE",
    },
}

VERDICT_THRESHOLDS = [
    ("Identical (exact match)",                              "The two texts are completely identical after normalization."),
    ("Equivalent (minor difference)",                       "Similarity ≥ 0.97 and all numeric tokens match."),
    ("Equivalent (some key-number difference)",               "Similarity ≥ 0.97 but some numeric tokens differ (a different position/element within the same structure was changed)."),
    ("Equivalent (reworded, key numbers match)",  "Similarity 0.60–0.97, numeric token sets identical (meaning presumed preserved)."),
    ("Partial match (numeric/data difference)",             "Similarity 0.60–0.97 and numeric tokens differ."),
    ("Similar but differing (recheck needed)",              "Similarity 0.40–0.60; human review recommended."),
    ("Different (major structural/content difference)",                 "Similarity < 0.40; large structural/content divergence."),
]

# Rank verdicts from identical (0) to most different (N-1) — used for the comparison heatmap.
VERDICT_RANK = {v: i for i, v in enumerate(COLORS["verdict"])}
N_VERDICT = len(VERDICT_RANK)


# ---------------------------------------------------------------------------
# Per-category purpose_fit evaluation rules (documentation — description text for Score/Pass sheets)
# ---------------------------------------------------------------------------
PURPOSE_RULES = {
    "EA-partial": [
        "The text must contain exactly one '[DATA MISSING]' marker.",
        "No new numeric values may be added relative to the original (the numeric token set must be a subset of the original's).",
        "The question must not be changed (this check compares context only).",
    ],
    "EA-full": [
        "Text length must decrease meaningfully relative to the original (≤ 90% recommended).",
        "No '[DATA MISSING]' or 'N/A' markers may be present.",
        "A carrier sentence, clause, table row, cell, or entry must be removed.",
    ],
    "SA": [
        "No markers such as '[DATA MISSING]', 'N/A', 'missing', or 'unknown' may be present.",
        "At least one of the original's key numeric values must be absent.",
        "The paragraph must show no signs of unnatural truncation (heuristic: must not contain '...', '???', or '__').",
    ],
}


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Text regexes
# ---------------------------------------------------------------------------
RE_WS = re.compile(r"\s+")
# Numeric tokens — absorbs the full thousands-comma group and decimal point.
#   "$3,500,000.50"  →  "3,500,000.50"   (one token)
#   "350,000"        →  "350,000"
#   "9.5"            →  "9.5"
#   "100"            →  "100"
RE_NUM = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
RE_NUM_PCT = re.compile(r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)%?")
RE_TOKEN = re.compile(r"[\w%\[\]\-./]+", re.UNICODE)


# ---------------------------------------------------------------------------
# Marker, language, and authority keywords (used by purpose_fit checks)
# ---------------------------------------------------------------------------
DATA_MISSING_RE = re.compile(r"\[DATA\s*MISSING\]", re.IGNORECASE)
MARKER_RE = re.compile(r"\[DATA\s*MISSING\]|\bN/?A\b", re.IGNORECASE)
# Hangul syllables / jamo — detects 'English only' constraint violations (IC-source, etc.).
HANGUL_RE = re.compile(r"[\uac00-\ud7a3\u3131-\u314e\u314f-\u3163]")
AUTHORITY_WORDS = re.compile(
    r"\b("
    r"audit(?:or|ing|ed|s)?|"
    r"report(?:s|ed|ing)?|"
    r"fil(?:e|ed|ing|ings)|"
    r"memo(?:s|randum|randa)?|"
    r"estimat(?:e|ed|es|ion|ions)|"
    r"revis(?:e|ed|ion|ions)|"
    r"amend(?:ed|ment|ments)?|"
    r"internal|external|"
    r"valuation(?:s)?|"
    r"discrepanc(?:y|ies)|"
    r"advis(?:or|ory|er|ers)|"
    r"consultant(?:s)?|"
    r"appraisal(?:s)?|appraiser(?:s)?|appraised|"
    r"review(?:er|ed|s|ing)?|"
    r"statement(?:s)?|"
    r"regulat(?:or|ors|ory|ion|ions|ed)|"
    r"IRS|SEC|FINRA|"
    r"broker(?:age|s)?|"
    r"disclos(?:e|ed|ure|ures)|"
    r"reconcil(?:e|ed|iation|ing)|"
    r"authorit(?:y|ies|ative)|"
    r"compliance|"
    r"prospectus|"
    r"certif(?:ied|ication|y)|"
    r"attestation"
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Stage-1 v4 ruleset constants (docs/perturbation_eval_tables.md, 2026-05-29)
# All forbidden terms/patterns are consolidated here — detection functions
# (system_common, ic_*) only import from this module.
# ---------------------------------------------------------------------------

# Exclusion pattern to prevent source-label numbers (10-K / 8-K / 10-Q) from
# being captured by RE_NUM and contaminating IC value-checks.
SOURCE_LABEL_RE = re.compile(r"\b\d{1,2}-?[KQ]\b")

# IC-source asymmetric authority/recency markers (violation if attached to only one source).
# 'authoritative' always appears in the reconcile sentence, so the bare token is excluded.
ASYMMETRIC_AUTHORITY_MARKERS = re.compile(
    r"\b(?:"
    r"audited|independently verified|system of record|"
    r"a prior version|an earlier version|superseded|"
    r"the (?:updated|latest|most recent|revised|corrected) "
    r"(?:figure|value|number|filing|report|estimate)"
    r")\b",
    re.IGNORECASE,
)
# IC-source recency/version/correction cue (conditional deduction; negation window invalidates).
RECENCY_CUE_RE = re.compile(
    r"\b(?:"
    r"a prior version|an earlier version|the latest|the most recent|"
    r"superseded|as of the current period"
    r")\b",
    re.IGNORECASE,
)

# IC-value: BARE violation — source-attribution phrases (applies only to the added sentence = diff-scope).
IC_VALUE_FORBIDDEN_ATTRIBUTION = (
    "management notes", "management states", "the team states",
    "according to", "per the company", "as reported by", "per the team",
    "the auditor reported", "the cfo confirmed", "based on the report",
    "filing indicates",
)
# IC-value: correction cues (imply one side is correct). False-positive terms
# (approximately/roughly/originally/previously) are excluded; only clear correction signals.
IC_VALUE_FORBIDDEN_CUE = (
    "corrected", "updated", "revised", "restated", "amended",
)
# IC-value: purposive qualifiers (excluded from scoring — kept only for warning output).
IC_VALUE_FORBIDDEN_PURPOSIVE = (
    "effective rate for", "applicable when", "used in financing calculations",
    "the rate used in", "when modeling after-tax", "for the purpose of",
    "to be applied to", "use this rate when",
)

# IC-premise: authority attribution is forbidden.
IC_PREMISE_FORBIDDEN_ATTRIBUTION = (
    "management has confirmed", "the auditor reported", "according to the cfo",
    "per the company filing", "the board has determined", "as confirmed by",
    "officially stated", "the filing indicates", "according to management",
    "the cfo stated", "the auditor confirmed", "as disclosed by",
    "the company reported", "verified by", "the controller noted",
)
# IC-premise: asymmetry hedging (implying one statement is erroneous or outdated).
# approximately/roughly excluded (rounding-prose false positives).
IC_PREMISE_FORBIDDEN_HEDGING = (
    "likely incorrect", "may be outdated", "a prior version", "tentatively",
    "is believed to be", "preliminary", "presumably", "allegedly",
    "reportedly", "supposedly", "questionable",
)
