# 원천 데이터 보관

준비·가공 이전의 배포 데이터셋 파일을 원래 바이트 그대로 보관한다. easy와 TAT-QA는 기존 로컬 원천에서 복사해 고정 SHA-256과 대조했다. medium과 hard는 easy와 같은 고정 버전의 공식 저장소에서 내려받아 GitHub 파일 목록의 크기·Git blob 해시와 대조했다. 새 설명용 문제를 생성하거나 레코드를 수정하지 않았다. 데이터셋 자체의 제작 방식과 실제 공시 원문 여부는 출처별로 구분해야 하며, 여기서 ‘원천’은 우리 준비 작업 이전의 배포 파일을 뜻한다.

|원천 파일|내용|원천 레코드 수|
|---|---|---|
|[FinanceReasoning easy](finance-easy.json)|질문·본문·정답·제공자 풀이 등을 담은 원천 목록|1,000|
|[FinanceReasoning medium](finance-medium.json)|medium 난이도의 배포 원천 목록|1,000|
|[FinanceReasoning hard](finance-hard.json)|hard 난이도의 배포 원천 목록|238|
|[TAT-QA dev](tatqa-dev.json)|표·문단·여러 질문을 담은 문서 목록|278문서; 질문 수와 다름|

[출처·버전·무결성 기록](manifest.json)에 원래 배포 URL, 고정 commit, 해시, 파일 크기, 원천 레코드 수, 가져온 위치를 기록한다. medium·hard의 다운로드 검증에 사용한 [공식 파일 목록](finance-upstream-files.json)도 보관한다.

## 관리 순서

1. 원천 파일의 출처·버전·해시를 확인한다.
2. [준비용 출처 목록](../../config/source-catalog.json)이 이 프로젝트의 원천 파일을 가리키게 한다.
3. 준비 단계는 원천을 읽어 별도의 prepared 디렉터리에 질문·본문·표·정답과 비교 기록을 만든다.
4. 원천을 직접 정제·수정하지 않는다. 다른 원천 버전은 별도 버전 폴더와 manifest로 보관한다.
5. 기존 data/prepared는 사용자 요청으로 삭제했다. 이후 명시적으로 요청된 [10건·30건·100건](../prepared/README.md)만 새로 준비했다. 필요 없는 준비본을 자동으로 재생성하거나 누적하지 않는다. reports의 과거 실행 기록은 이번 삭제 대상에 포함되지 않았다.

여기의 정답·제공자 풀이를 포함한 원천 파일은 제작용 자료다. 대상 모델에는 동결된 public 입력만 전달한다.
