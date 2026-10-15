# Reject 제외·모델 교체 로컬 확인

이번 변경은 새 Export·모델 호출 설정에 적용합니다. 기존 실제 run의 설정·응답·취합본은 이 점검에서 변경하지 않았습니다. 모델 호출은 0회이며 실제 의미 품질·지원 여부는 로컬 응답 대역으로 입증하지 않습니다.

읽는 순서: [설정과 변경 범위](01-change-summary.json) → [검사 결과](validation.json) → [Python 검사 로그](02-focused-tests.log) → [화면 코드 검사 로그](03-viewer-tests.log) → [검증용 결과 취합본](fixture-run/results/README.md). 검증용 취합본은 인공 로컬 사례이며 실제 제작 데이터셋이 아닙니다.

|변경|확인할 내용|
|---|---|
|Reject 제외|현재 사람 판정 기준. Preparation은 원본·7유형 전체, Generation은 해당 유형만 제외. Pending·자동 FAIL은 별도.|
|유형 연결|`id`로 연결. 파일별 순서·중복·누락 제외 근거·해시 확인. 7유형 완성 실험 조건은 별도.|
|모델 교체|Luna 5.6→6, Sol 5.6→6.1. 기존 effort·토큰 한도 유지. 실패 해석·가격 추정·CLI 선택지도 대조.|
|과거 기록|구형 파일 정렬·구형 가격·동결된 모델 기록 유지. 메타정보 보강은 과거 Reject 제외로 간주하지 않음.|

[모델 설정 문서](../../../config/MODELS-README.md) · [Release 동작과 흐름도](../../../docs/01-dataset/03-release/README.md) · [공통 뷰어](../../../viewer/dataset/index.html)

공통 뷰어에서 실행 `20261001-export-model-migration-check`를 선택하십시오. 새 HTML을 따로 생성하지 않고 현재 설정·Release 문서·검사 README를 읽습니다. 기존 테스트 자료의 실패 여부와 화면 확인 범위는 `validation.json`에 구분합니다.
