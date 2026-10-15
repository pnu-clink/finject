# fin-arch 서버 위젯

메뉴 막대의 서버 아이콘을 누르면 로컬 조회 서버 네 개의 실제 상태·포트와 제어 버튼을 한 화면에서 볼 수 있습니다. 서버가 꺼져 있어도 위젯은 실행됩니다. **열기**는 해당 서버가 꺼져 있으면 시작하고, 확인된 실험 서버가 응답하지 않으면 복구한 뒤 브라우저를 엽니다.

## 먼저 읽을 파일

|순서|파일|역할|
|---|---|---|
|1|[project.yml](project.yml) · [Xcode 프로젝트](FinArchServerWidget.xcodeproj)|앱 빌드 설정·프로젝트 경로|
|2|[ServerSpec.swift](Sources/ServerSpec.swift)|네 서비스의 이름·포트·실행 파일·화면 주소|
|3|[ServerController.swift](Sources/ServerController.swift)|실제 응답 확인, 안전한 시작·중지·재시작, 로그|
|4|[ServerWidgetApp.swift](Sources/ServerWidgetApp.swift)|색상 점·버튼이 있는 메뉴 막대 화면|
|5|[실행 기록](../../log/server-widget/README.md)|작업 결과와 각 서버의 출력 로그|

## 포트와 상태

|서비스|포트|기본 화면|
|---|---:|---|
|데이터셋·문서|8893|[열기](http://127.0.0.1:8893/)|
|실험 결과|8894|[열기](http://127.0.0.1:8894/)|
|대시보드|8895|[열기](http://127.0.0.1:8895/dashboard/03-project/)|
|연구 자료|8896|[열기](http://127.0.0.1:8896/viewer/research/)|

포트 번호와 위젯 목록은 데이터셋 → 실험 → 대시보드 → 연구 자료 흐름에 맞춰 이어집니다.

초록은 서버가 응답하고 영역·프로젝트 식별이 일치한다는 뜻입니다. 빨강은 포트가 비었다는 뜻입니다. 주황색 **응답 없음**은 8894 포트의 실험 서버가 응답하지 않지만 실행 경로가 현재 프로젝트와 정확히 일치한다는 뜻입니다. 이때 **중지·재시작·열기**로 복구할 수 있습니다. 주황색 **다른 서비스 또는 확인 실패**는 서버를 안전하게 식별할 수 없다는 뜻이며 버튼을 비활성화하고 그 프로세스를 건드리지 않습니다. 상태 확인 중과 시작·중지 중에는 회색을 사용합니다.

각 줄의 **시작**은 포트가 비었을 때 서버를 실행하고 준비를 확인합니다. **중지**는 서버 식별과 프로세스 명령을 확인한 뒤 종료합니다. **재시작**은 중지 확인 후 다시 시작합니다. 실험 서버가 응답하지 않아 일반 종료가 듣지 않으면 같은 PID와 실행 경로를 다시 확인한 뒤 그 프로세스에만 강제 종료 신호를 보냅니다. **열기**는 실행 중인 서버를 재사용하거나 꺼진 서버를 시작하고, 응답 없는 실험 서버는 복구한 뒤 화면을 엽니다. 상태는 위젯을 열 때와 3초마다 다시 확인합니다. 프로젝트 위치가 바뀌면 **프로젝트 폴더…**에서 새 폴더를 선택합니다.

## 빌드와 실행

Xcode에서 [FinArchServerWidget.xcodeproj](FinArchServerWidget.xcodeproj)를 열고 **FinArchServerWidget** 스킴을 실행합니다. 터미널에서는 프로젝트 루트에서 다음 명령으로 빌드할 수 있습니다.

```sh
xcodebuild -project apps/server-widget/FinArchServerWidget.xcodeproj -scheme FinArchServerWidget -configuration Release -derivedDataPath apps/server-widget/build build CODE_SIGNING_ALLOWED=NO
open apps/server-widget/build/Build/Products/Release/FinArchServerWidget.app
```

이 컴퓨터에 설치한 실행 앱은 `~/Applications/FinArchServerWidget.app`입니다. Xcode 프로젝트 파일을 다시 생성할 때만 `apps/server-widget`에서 `xcodegen generate --spec project.yml`을 실행합니다. 조회 서버는 모델을 호출하거나 저장 결과를 변경하지 않습니다. 기존 `start.command`도 직접 사용할 수 있습니다.

실험 결과 서버는 Node.js 20 이상을 사용합니다. 위젯에서 실행할 때 터미널의 PATH를 물려받지 않으므로, 실험 뷰어 시작 코드는 일반 PATH에서 먼저 찾고 Homebrew 기본 설치 경로(`/opt/homebrew/bin`, `/usr/local/bin`)도 확인합니다. 실제 설치가 없다면 `experiments.log`의 안내를 확인하세요.

## 기록과 과거 주소

위젯의 시작·중지·실패 기록은 `log/server-widget/events.jsonl`, 서버 출력은 같은 폴더의 서비스별 `.log`에 남습니다. [실행 기록 안내](../../log/server-widget/README.md)에 읽는 순서가 있습니다. 과거 보고서와 원응답은 수정하지 않았습니다. 과거 파일 안에 이미 기록된 8876·8897 링크는 당시 주소이며 새 포트로 자동 연결되지 않습니다. 포트 순서 변경 전의 보고서에 기록된 8893·8894 링크도 현재는 서로 다른 영역을 가리킬 수 있으므로, 현행 문서나 위젯의 **열기**를 사용합니다.

[전체 서버 흐름과 책임 표](../../docs/01-dataset/90-operations/05-source-layout.md)에 위젯의 실제 분기·실패 경로가 있습니다. 이 README는 `src/finarch/documentation/templates/server-widget.md`에서 생성합니다.
