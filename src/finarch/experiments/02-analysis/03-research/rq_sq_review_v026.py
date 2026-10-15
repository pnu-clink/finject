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
    "RQ1": "근거 변경에 대한 반응",
    "RQ2": "풀이 조건과 원본 답변",
}
SCOPE = {
    "RQ1": "기존 통합 발견의 근거 변경 관찰을 연결했습니다. 후보 숫자의 일치만으로 근거 선택이나 의미 정답을 확정하지 않습니다.",
    "RQ2": "기존 통합 발견의 풀이 지시·추론 설정 비교를 연결했습니다. 설정 변화와 동반된 지시·출력 계약의 영향을 분리해야 합니다.",
    "SQ1": "원본 수치 일치의 기준선만 있습니다. 원본 성과별 변형 대응을 직접 나눠 비교하기 전에는 관계를 확정할 수 없습니다.",
    "SQ2": "이 통합본에는 제작 문항의 타당성·독립 검토자 일치도에 대한 직접 통합 발견이 없습니다. 제작 기록과 별도 검토를 대조해야 합니다.",
    "SQ3": "답·분류·설명·근거가 어긋난 관찰을 연결했습니다. 사례를 전수 의미 판정이나 발생 비율로 확대하지 않습니다.",
    "SQ4": "이 통합본에는 계산 그래프의 변수·연산·깊이를 응답과 연결한 직접 검토가 없습니다. 구조 지표를 정의하고 문항·응답에 연결해야 합니다.",
    "SQ5": "이 통합본에는 외부 규칙·수치 의존 기록과 모델 응답을 연결한 직접 검토가 없습니다. 제작자의 지식 사용을 모델의 사용으로 간주하지 않습니다.",
    "SQ6": "동일 입력·지시·스키마·모델 설정의 독립 반복을 확인하기 전까지 비교를 보류합니다. 저장 응답의 재분석은 독립 반복이 아닙니다.",
}
STATUS = {
    "RQ1": "기존 관찰 연결 · 결론 미확정",
    "RQ2": "기존 관찰 연결 · 결론 미확정",
    "SQ1": "기준선 연결 · 직접 관계 미검토",
    "SQ2": "직접 검토 없음",
    "SQ3": "사례 연결 · 전수 판정 아님",
    "SQ4": "직접 검토 없음",
    "SQ5": "직접 검토 없음",
    "SQ6": "독립 반복 확인 전 보류",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def questions_from_paper(text: str) -> dict[str, tuple[str, str]]:
    if "한글 논문 초안 v0.26" not in "\n".join(text.splitlines()[:5]):
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
                    "SQ1에는 부분 근거입니다. 2,017·176·35는 응답 수이며 독립 문항 수가 아닙니다. "
                    "원본 수치 일치·불일치·미평가별 동일 조건 변형 반응을 비교하기 전에는 "
                    "SQ1의 관계나 H3 지지를 확정하지 않습니다."
                )
            indexed_groups.append(item)
    return {
        "schema_version": 1,
        "kind": "editorial-index-of-saved-review",
        "run": run,
        "paper_version": "0.26",
        "paper": {"path": PAPER.as_posix(), "sha256": sha256(paper_path), "sections": ["3.3", "3.4"]},
        "saved_review": {"path": REVIEW.as_posix(), "sha256": sha256(review_path), "historical_rq_count": len(review["research_questions"])},
        "notice_ko": "이 화면은 이전 4-RQ 통합본의 9개 G를 논문 v0.26의 RQ/SQ에 재배치한 편집 색인입니다. 새로운 모델 호출·의미 판정·논문 결론이 아닙니다.",
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
        f"# 논문 v0.26 연구질문별 통합검토 색인\n\n"
        f"이 파일은 `{args.run}`의 저장된 통합 발견을 최신 논문 질문으로 찾아보는 **편집 색인**입니다. "
        "새 실험 결과나 논문 결론이 아닙니다.\n\n"
        "읽는 순서: ① 연구 해석 뷰어에서 RQ1·RQ2·SQ1–SQ6을 펼칩니다. "
        "② `rq-sq-review-v026.json`에서 논문 문구·상태·연결 G·원자료 해시를 확인합니다. "
        "③ 기존 `rq-review.md`와 `rq-review-audit.md`에서 이전 4-RQ 통합 판단과 전체 F 대응을 확인합니다. "
        "④ `findings.json` 및 인용된 Evaluation 원응답에서 개별 근거와 한계를 확인합니다.\n\n"
        "출처: `reports/run/20260924-paper-draft/PAPER-KO.md` v0.26 §3.3–3.4와 같은 회차의 "
        "`rq-review.json`. 색인의 해시는 두 출처 파일의 현재 내용을 가리킵니다. "
        "원본 발견·원응답·기존 통합본은 수정하지 않았습니다.\n",
        encoding="utf-8",
    )
    print(f"{target}: {len(result['questions'])} questions, {len(result['groups'])} saved groups")


if __name__ == "__main__":
    main()
