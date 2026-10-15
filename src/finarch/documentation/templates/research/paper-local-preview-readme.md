# FInject · 로컬 LaTeX 미리보기

이 README는 문서 템플릿에서 생성합니다. 현재 프로젝트는 검토용 로컬 사본이며 Overleaf에 반영하지 않았습니다.

## 읽는 순서

1. [main.pdf](main.pdf): 로컬에서 컴파일한 영문 조판 미리보기.
2. [main.tex](main.tex): 진입 파일과 Abstract.
3. [sections/01-introduction.tex](sections/01-introduction.tex): Introduction과 Figure 1.
4. [revision-20261002-body.tex](revision-20261002-body.tex): Related Works부터 부록까지의 본문.
5. [현재 수치·절차](../instructdion/MANUSCRIPT-STATE.json): human annotation 전 수량과 승인 순서.
6. [동기화 기록](../../reports/run/20261003-paper-local-sync/README.md): 백업·검사·로그.

## 작업 순서

먼저 기존 FInject Revision Draft에서 한글·영문 변경사항을 검토합니다. 사용자가 반영을 결정한 뒤에만 Overleaf로 전송합니다. 로컬 PDF를 만드는 것은 배포가 아닙니다.

현재 검토 자료는 `reports/run/20261003-paper-revision-draft/paper-review.json`, annotation 전 수량 설명은 `paper/local-preview-content/counts-en.md`와 `counts-ko.md`입니다. 과거 배포 run의 원본은 보존합니다. 이 프로젝트에서는 기존 날짜별 원고 생성기를 다시 실행하지 않습니다.

프로젝트 루트에서 한·영 검토본과 로컬 PDF를 맞춥니다:

```sh
python3 src/finarch/documentation/sync_paper_revision.py --build
```

LaTeX 본문만 수정한 뒤 PDF만 다시 만들 때에는 이 폴더에서 실행합니다:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

현재 PC의 latexmk와 pdflatex를 사용합니다. 여러 소스·그림·ACL 스타일 파일이 있는 프로젝트이므로 로컬 LaTeX 도구로 컴파일합니다. PDF는 Codex에서 열어 볼 수 있습니다. 직접 LaTeX를 편집했다면 Revision Draft의 대응 문장도 함께 갱신해야 하며, 한쪽만 바꾸고 동기화 완료라고 보고하지 않습니다.

원고에는 기존 미작성 항목과 Appendix # 표기가 남아 있습니다. 이 PDF는 제출 완료본이 아닙니다.
