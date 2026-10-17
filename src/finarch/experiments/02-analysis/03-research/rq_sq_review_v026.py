"""Build a source-linked v0.26 question index for a saved A03 review.

This is an editorial index of existing observations, not a new analysis run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
PAPER = Path("reports/run/20260924-paper-draft/PAPER-KO.md")
REVIEW = Path("02_analysis/03_research/rq-review.json")
OUTPUT = Path("02_analysis/03_research/rq-sq-review-v026.json")
README = Path("02_analysis/03_research/rq-sq-review-v026-README.md")
ORDER = ("RQ1", "RQ2", "SQ1", "SQ2", "SQ3", "SQ4", "SQ5", "SQ6")
GROUPS = {
    "RQ1": ("G04", "G05", "G06", "G07"),
    "RQ2": ("G02", "G03"),
    "SQ1": ("G01",),
    "SQ2": (),
    "SQ3": ("G08", "G09"),
    "SQ4": (),
    "SQ5": (),
    "SQ6": (),
}
HEADINGS = {
    "RQ1": "Reaction to the change in the basis",
    "RQ2": "Weed conditions and original answers",
}
SCOPE = {
    "RQ1": "It's linked to the observation of the basis change of the existing integrated findings, which is that the matching of the candidate numbers doesn't confirm the basis selection or the meaning of the correct answer.",
    "RQ2": "The bottom of the existing integration findings connected the directional-reference setup comparison, separating the effects of the associated directional-output agreement from the changes in the setup.",
    "SQ1": "There's only a baseline of matching the original numbers, and you can't establish a relationship until you've actually split the original results and compared the variation matches.",
    "SQ2": "This consolidated copy has no direct consolidated findings of the validity and independent reviewers' consistency of the production clause, and it should be contrasted with the production record and the separate review.",
    "SQ3": "Answer: division: explanation: the whole is a contradiction, not a case-by-case semantic assessment or a rate of occurrence.",
    "SQ4": "This integrated version has no direct review linking the variables, the correlations, the depths of the calculation graph to the response. It has to define the structural index and link it to the case, the response.",
    "SQ5": "This consolidated copy does not have a direct review linking external rule-based records and model responses, and does not consider the use of creator knowledge to be the use of a model.",
    "SQ6": "We keep the comparison until we check the independent repetition of the same input, JIS, schema model settings.",
}
STATUS = {
    "RQ1": 'Existing observations linked \xb7 conclusions not established',
    "RQ2": 'Existing observations linked \xb7 conclusions not established',
    "SQ1": 'Baseline linked \xb7 direct relationship not reviewed',
    "SQ2": 'No direct review',
    "SQ3": 'Cases linked \xb7 not an exhaustive assessment',
    "SQ4": 'No direct review',
    "SQ5": 'No direct review',
    "SQ6": 'Pending independent repeated verification',
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def questions_from_paper(text: str) -> dict[str, tuple[str, str]]:
    if "\ud55c\uae00 \ub17c\ubb38 \ucd08\uc548 v0.26" not in "\n".join(text.splitlines()[:5]):
        raise ValueError("The source paper is not v0.26")
    questions = {}
    for code, question in re.findall(r"\*\*(RQ[12])\. ([^\n*]+)\*\*", text):
        questions[code] = (HEADINGS[code], question)
    for code, heading, question in re.findall(r"^\|(SQ[1-6])\|([^|]+)\|([^|]+)\|", text, re.MULTILINE):
        questions[code] = (heading, question)
    if set(questions) != set(ORDER):
        raise ValueError(f"Expected RQ1–RQ2 and SQ1–SQ6; found {sorted(questions)}")
    return questions


def build(run: str, root: Path = ROOT) -> dict:
    if not re.fullmatch(r"[a-zA-Z0-9-]+", run):
        raise ValueError("Invalid run ID")
    paper_path = root / PAPER
    review_path = root / "reports/experiments-run" / run / REVIEW
    paper = questions_from_paper(paper_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if review.get("run") != run:
        raise ValueError("The saved review belongs to another run")
    groups = {group["id"]: group for group in review["groups"]}
    mapped = [id for ids in GROUPS.values() for id in ids]
    if len(mapped) != len(set(mapped)) or set(mapped) != set(groups):
        raise ValueError("Each saved G group must be mapped exactly once")
    assigned = [(finding, group["id"]) for group in review["groups"] for finding in group["primary_finding_ids"]]
    expected = {(row["finding_id"], row["primary_group"]) for row in review["finding_review"]}
    if len(assigned) != len(expected) or set(assigned) != expected:
        raise ValueError("Every saved F finding must retain its primary G group")
    indexed_groups = []
    for code in ORDER:
        for id in GROUPS[code]:
            source = groups[id]
            item = {key: source[key] for key in (
                "id", "title_ko", "claim_ko", "evidence_ko", "alternatives_ko",
                "boundary_ko", "primary_finding_ids", "related_finding_ids", "interpretation_ids"
            )}
            item["question_id"] = code
            if id == "G01":
                item["boundary_ko"] = (
                    "SQ1 is partially based. 2,017·176·35It's not the number of answers, it's the number of independent cases. "
                    "Before we compare the matching, dismatching, and undermatching of the same condition to the original, we compare the variation reactions. "
                    "It doesn't confirm the relationship between SQ1 or H3."
                )
            indexed_groups.append(item)
    return {
        "schema_version": 1,
        "kind": "editorial-index-of-saved-review",
        "run": run,
        "paper_version": "0.26",
        "paper": {"path": PAPER.as_posix(), "sha256": sha256(paper_path), "sections": ["3.3", "3.4"]},
        "saved_review": {"path": REVIEW.as_posix(), "sha256": sha256(review_path), "historical_rq_count": len(review["research_questions"])},
        "notice_ko": "This screen is the old one. 4- The RQ integrated copy. 9items G is the paper v0.26It's the editing color that was re-assigned to RQ/SQ. It's not a new model call, semantic assessment, or discussion conclusion.",
        "questions": [
            {"id": code, "title_ko": paper[code][0], "question_ko": paper[code][1],
             "status_ko": STATUS[code], "scope_ko": SCOPE[code], "group_ids": list(GROUPS[code])}
            for code in ORDER
        ],
        "groups": indexed_groups,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", help="Saved experiment run ID")
    args = parser.parse_args()
    result = build(args.run)
    folder = ROOT / "reports/experiments-run" / args.run
    target = folder / OUTPUT
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / README).write_text(
        f"# Article v026 The color of the study is the color of the cross-sectional integrated examination.\n\n"
        f"This file is `{args.run}` to find the stored integrated findings as the latest paper questions **The editing color.**. "
        "It's not a new experiment or a paper conclusion.\n\n"
        "Reading order: 1 study interpretation viewer to run RQ1, RQ2, SQ1SQ6. "
        "② `rq-sq-review-v026.json`In the article sentence, condition, link, check the G-source chart. "
        "3 existing `rq-review.md`and `rq-review-audit.md`From previously 4-RQ integrated judgment and total F correspondence. "
        "④ `findings.json` And in the Evaluation raw response quoted, we check the individual basis and limitations.\n\n"
        "Sources: `reports/run/20260924-paper-draft/PAPER-KO.md` v0.26 §3.3–3.4And the same thing as a rotary "
        "`rq-review.json`The color bar is the current content of the two source files. "
        "The original discovery, raw response, and the existing integrated copy were not modified.\n",
        encoding="utf-8",
    )
    print(f"{target}: {len(result['questions'])} questions, {len(result['groups'])} saved groups")


if __name__ == "__main__":
    main()
