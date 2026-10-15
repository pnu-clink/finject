# 로컬 화면과 서버 실행

각 폴더의 `start.command`를 실행하면 서버 준비 후 브라우저가 열립니다. 실행 위치와 관계없이 프로젝트 루트를 기준으로 동작합니다.

|영역|실행 파일|기본 화면|서버 코드|
|---|---|---|---|
|데이터셋|[dataset/start.command](dataset/start.command)|[8893](http://127.0.0.1:8893/)|[dataset/viewer](../src/finarch/dataset/viewer/README.md)|
|실험|[experiments/start.command](experiments/start.command)|[8894](http://127.0.0.1:8894/)|[experiments/viewer](../src/finarch/experiments/viewer/README.md)|
|대시보드|[dashboard/start.command](dashboard/start.command)|[8895](http://127.0.0.1:8895/dashboard/03-project/)|[dashboard/viewer](../src/finarch/dashboard/viewer/README.md)|
|연구 자료|[research/start.command](research/start.command)|[8896](http://127.0.0.1:8896/viewer/research/)|[research_viewer.py](../src/finarch/shared/research_viewer.py)|

예: `./viewer/dashboard/start.command --port 8905 --no-open`. Python `.venv`를 공통으로 사용하며 실험 뷰어는 Node.js도 필요합니다. `--no-open`은 브라우저 자동 열기를 끄고, `Ctrl+C`는 해당 서버를 종료합니다. 이미 실행 중인 동일 영역·프로젝트 서버는 재사용합니다.

메뉴 막대 [fin-arch 서버 위젯](../apps/server-widget/README.md)을 누르면 네 서비스의 실제 상태를 색상 점으로 확인하고 시작·중지·재시작·화면 열기를 실행할 수 있습니다. **열기**는 꺼진 서비스를 먼저 시작해 준비를 확인한 뒤 브라우저를 엽니다. 기본 포트는 데이터셋 8893 → 실험 8894 → 대시보드 8895 → 연구 자료 8896입니다.

브라우저용 HTML·CSS·JavaScript는 각 폴더에, 서버·조회·내보내기 코드는 `src/finarch/<영역>/viewer`에 있습니다. [폴더 정의와 파이프라인 대응](../docs/01-dataset/90-operations/05-source-layout.md)을 먼저 읽습니다.

Dataset·Experiments는 상단 **한국어 / English**로 화면을 전환합니다. [공통 표시 코드](shared/README.md)는 필터·입력값을 유지하고 저장된 한글/영어 설명을 선택합니다. 질문·본문·원응답·주석은 원문 그대로입니다. 두 영역의 새 HTML Export에도 같은 코드가 내장되며 언어 전환에 인터넷·모델 호출이 필요하지 않습니다. 예전 HTML은 다시 내보내야 합니다. [확인 자료와 검사 범위](../outputs/viewer-i18n-20261002/README.md).
