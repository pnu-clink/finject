# Dashboard — 프로젝트 상태와 저장 실험 자료

[문서 파이프라인](../../../docs/03-dashboard/README.md) · [전체 소스 구조](../../../docs/01-dataset/90-operations/05-source-layout.md)

1. [01-data/data.py](01-data/data.py): 등록된 저장 파일·원응답 연결·해시·조회 캐시.
2. [02-metrics/metrics.py](02-metrics/metrics.py): 기록된 처리 시간·시각·토큰·비용을 읽습니다. 없는 값은 null입니다.
3. [03-project/monitor.py](03-project/monitor.py): 로컬 세션과 저장된 run·문서를 읽어 프로젝트 현황을 만듭니다. [session-map.json](03-project/session-map.json)은 업무 분류만 담습니다.
4. [viewer/resources.py](viewer/resources.py): 허용된 화면 파일·API·원문 참조만 제공합니다.
5. [viewer/server.py](viewer/server.py): 8895 독립 서버. [start.command](../../../viewer/dashboard/start.command)로 브라우저를 함께 엽니다.

화면 파일은 [viewer/dashboard](../../../viewer/dashboard/README.md), 로컬 검사는 `checks`입니다. 기본 주소는 프로젝트 현황이며 실험 숫자 화면은 별도 경로로 유지합니다. 모델 호출이나 원점수 재평가를 수행하지 않습니다.
