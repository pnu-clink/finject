# 화면 언어·HTML Export 확인

읽는 순서: [확인 자료 안내](../../outputs/viewer-i18n-20261002/README.md) → [verification.json](verification.json) → [자동 검사 로그](checks.log) → [문서 검사](documentation-check.log).

Dataset·Experiments에 같은 화면 언어 사전을 적용하고, 평가자·실험·Annotation HTML에 자산을 포함했습니다. 모델 호출·제작 판정 저장은 하지 않았습니다. 라이브 화면에서 선택값·미저장 이유·체크박스·판정을 유지하는지 확인하며 테스트 초안은 저장하지 않고 제거합니다.

`source-before.json`과 `source-after.json`은 확인한 Dataset 문항의 실제 제작 JSON 해시입니다. `checks.log`는 사전·저장 차단·저장된 한/영 설명·오프라인 조회·CSP·Dataset Export 검사의 출력입니다. `dataset-server.log`, `experiments-server.log`는 화면 서버의 실행 로그입니다. 상세 책임과 흐름은 [공통 코드 안내](../../viewer/shared/README.md)에 있습니다.

브라우저 도구는 `file://`를 허용하지 않아 내보낸 파일을 직접 열어 보는 검사는 미확인입니다. 오프라인 자료 조회는 자동 검사에서 확인하며 라이브 UI 확인과 구분합니다. 원문 설명에 번역이 없으면 새 번역을 생성하지 않고 그대로 표시합니다.
