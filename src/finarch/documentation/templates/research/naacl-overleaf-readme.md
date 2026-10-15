# NAACL/ARR 영문 Overleaf 원고 · v0.1

최신 공동 검토용 한국어 원고 v0.10을 영어 논문으로 구성했습니다. 본문은 익명 심사용 ACL 공식 양식의 8쪽 범위이며, 전체 PDF는 참고문헌·상세 부록을 포함한 20쪽입니다. 결과와 결론은 공란입니다. 지정된 [Overleaf 프로젝트](https://www.overleaf.com/project/6abcb58e055822eb16ed6e06)에 업로드하고 컴파일을 확인했습니다. 학회 제출은 하지 않았습니다.

## 읽는 순서와 파일 역할

1. [PDF](main.pdf): 표·그림·인용이 배치된 전체 원고입니다.
2. [Overleaf 업로드 ZIP](fin-arch-naacl-overleaf.zip): 새 프로젝트 → Upload Project에 올리고, main.tex와 pdfLaTeX를 선택합니다. 필요한 양식·본문·표·BibTeX·그림 파일을 포함합니다.
3. [main.tex](main.tex)와 sections/: 수정할 LaTeX 원본입니다. Results·Conclusion은 빈 절이며, Limitations는 Conclusion 뒤에 있습니다.
4. [영문 검토본](PAPER-EN.md): TeX에서 생성한 Markdown 읽기용 원고입니다. 공통 연구 뷰어도 이 내용의 보고서 사본을 읽습니다.
5. tables/: 금융 제작·평가 표는 본문, 비금융 표·검토 지원 상세 표는 부록입니다. ○/빈칸 456개 셀을 그대로 유지했습니다.
6. figures/: 별도 영어 벡터 PDF 그림과 수정 가능한 TikZ 원본입니다. PNG는 공통 뷰어용입니다. 주석 시스템 그림은 구현 화면의 기능을 설명하는 도식이며 실제 영문 UI로 표기하지 않습니다.
7. [references.bib](references.bib): 24편의 저자–연도 인용과 원문 링크입니다.
8. [영문 사용 안내](README-OVERLEAF.md), [원고 대응·근거](evidence/SOURCE-MAP.md), [확인 결과](verification.json), [작업 로그](events.jsonl): 수정 방법과 자료의 범위를 확인합니다.

[한글 HTML](PAPER-KO.html)은 영문 Overleaf 원고의 바탕이 된 기존 한글 원고 v0.10을 번역·개작 없이 표시한 읽기용 파일입니다. 본문·부록·표 20개와 그림 2개를 보존하며, 그림을 파일 안에 담아 인터넷 없이 열 수 있습니다. 영문 원고의 축약·재배열을 역번역한 문서가 아니므로 한글 원문의 절 구성과 번호를 유지합니다. [한글 HTML 확인 기록](evidence/qa/korean-html-audit.json)에서 본문 일치·그림·목차를 확인할 수 있습니다.

## 화면에서 확인

[공통 연구 뷰어](http://127.0.0.1:8896/viewer/research/)에서 **2026-10-02 · NAACL/ARR 영문 Overleaf 원고**를 선택합니다. reports/run의 실제 원고와 별도 영어 그림을 읽으며, 결과 폴더별 HTML은 만들지 않았습니다. `main.tex`를 기본 LaTeX 편집기에 열도록 요청했으며, 실제 확인한 컴파일·화면 범위는 verification.json에 기록합니다. 파일 저장과 사용자 검토 완료는 별개입니다.

## Overleaf 업로드 확인

[2026-ARR-FInject](https://www.overleaf.com/project/6abcb58e055822eb16ed6e06)에 원고·표·그림·양식·참고문헌 31개 파일과 업로드 ZIP을 반영했습니다. 메인 문서는 `main.tex`, 컴파일러는 pdfLaTeX, TeX Live는 2026입니다. Overleaf는 오류 0건·경고 0건과 Underfull 조판 안내 23건을 표시했습니다. 내려받은 PDF는 20쪽이며, 페이지별 본문 텍스트가 로컬 검증본과 모두 일치합니다.

업로드 전 [기존 프로젝트 전체](evidence/overleaf-before-upload.zip)를 보관했습니다. [업로드 후 원본](evidence/overleaf-after-upload.zip)을 내려받아 새 원본 31개와 로컬 파일의 해시 일치 및 교체 대상 외 기존 파일 14개의 보존을 확인했습니다. [업로드 기록](evidence/overleaf-upload.json), [원본 대조 결과](evidence/qa/overleaf-source-audit.json), [Overleaf PDF](evidence/qa/overleaf-compiled.pdf), [최종 화면](evidence/qa/overleaf-upload-complete.png)을 함께 제공합니다. Overleaf 업로드와 사용자 원고 검토·학회 제출은 별개입니다.

## 검증과 주장 범위

- 2026-10-02 용어·표 설명 수정: 자체 비교 항목 CQA를 Conflict QA로 통일했습니다. Tab-CQA는 선행연구의 고유 이름으로 유지합니다. 본문·부록의 네 비교표 설명은 `\textbf{Calc}. numerical QA, \textbf{Fact}. factuality, …`처럼 용어를 굵게 쓰고 쉼표로 구분합니다. 기존 Overleaf 수정 내용을 보존했으며, [수정 확인 기록](evidence/qa/conflict-qa-caption-audit.json)과 [화면](evidence/qa/conflict-qa-caption-overleaf.png)을 제공합니다. 한글 원고·HTML의 해당 용어도 맞췄고 분석 결과·결론과 표의 포함 표시는 바꾸지 않았습니다.
- pdfLaTeX/latexmk로 전체 프로젝트 및 업로드 ZIP을 새 폴더에 푼 상태에서 컴파일합니다. PDF의 페이지·폰트·줄 번호 겹침·표·그림 배치와 미해결 인용을 확인합니다.
- 공식 양식 파일은 변경하지 않았습니다. 현재 양식의 줄 번호 겹침에 대해서만 review-line-numbers.tex에서 문서별 위치 보정을 합니다. 본문 글꼴·여백·열 간격·행간은 유지합니다.
- H1은 사람 주석자의 판정 재현성, HS1은 모델의 원본 정답 여부와 변형 대응의 관계입니다. 품질 수용 기준과 최종 일치율·κ는 미정·미보고 상태를 유지합니다.
- 구현 경로, 과거 저장 자료, 예정된 의미 검증·분석을 구분합니다. 새 실험·LLM 호출·주석·성능 집계·데이터셋 및 실험 구현 변경은 하지 않았습니다.

이 README는 src/finarch/documentation/templates/research/naacl-overleaf-readme.md에서 생성했습니다.
