# 서버 위젯 실행 기록

이 폴더는 [fin-arch 서버 위젯](../../apps/server-widget/README.md)의 실제 실행과 확인 기록을 보존합니다. 서버의 저장 자료·실험 원응답과는 별개입니다.

|읽는 순서|파일|의미|
|---|---|---|
|1|[smoke.log](smoke.log)|포트 순서 변경 전 네 서비스의 시작·재사용·재시작·중지, 다른 프로세스 보호, 꺼진 서버의 열기 확인|
|2|[port-order.log](port-order.log)|데이터셋 → 실험 → 대시보드 → 연구자료 순서, 새 포트에서 서버 시작·재사용·식별 확인|
|3|[build-and-install.json](build-and-install.json)|Release 앱 경로·서명·실행·문서 검사 결과|
|4|[현재 화면 렌더](preview.png) · [응답 없음 상태 렌더](experiment-unresponsive-preview.png)|SwiftUI 화면과 복구 가능 상태의 버튼 배치 확인. 두 번째 이미지는 검사 코드로 상태를 주입한 미리보기|
|5|[default-ports.log](default-ports.log)|각 `start.command`의 기본 포트와 서버 식별 응답 확인|
|6|[events.jsonl](events.jsonl)|위젯이 수행한 상태 확인·시작·중지·열기·실패의 시각·서비스·포트·결과|
|7|`experiments.log`, `dataset.log`, `dashboard.log`, `research.log`|각 서버의 표준 출력과 오류. 해당 파일이 없으면 그 서버를 위젯에서 아직 실행하지 않은 상태|
|8|[node-path-repair.json](node-path-repair.json) · [화면](experiments-node-path-repair.png)|메뉴 막대 환경에서 Node 탐색 오류를 재현·수정하고 실제 8894 화면을 확인한 기록|
|9|[첫 복구 기록](unresponsive-recovery.log) → [재시도 기록](unresponsive-recovery-attempt-2.log) · [강제 종료 검사](forced-stop.log)|실험 서버 응답 중단과 일반 종료 실패를 보존하고, 안전한 재시작·다른 프로세스 보호·강제 종료 경로를 확인한 기록|
|10|[unresponsive-recovery.json](unresponsive-recovery.json)|복구 전후 PID·포트·다른 서버 보존·설치 앱 검증 범위|

실제 현재 상태는 로그의 마지막 줄보다 위젯의 색상 점과 서버 응답을 우선해서 확인합니다. [서버 위젯 사용 안내](../../apps/server-widget/README.md)에서 버튼과 색상의 의미를 확인할 수 있습니다. 이 README는 `src/finarch/documentation/templates/server-widget-log.md`에서 생성합니다.
