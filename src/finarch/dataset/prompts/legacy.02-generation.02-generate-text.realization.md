# 문장 생성 지침 위치 변경

이 파일은 더 이상 LLM 호출에 사용하지 않습니다.

현재 지침은 [realize-prompts/README.md](realize-prompts/README.md)의 네 유형으로
분리했습니다. `realization_prompts.py`가 요청의 `axis`로 한 유형만 선택하고
공통 출력 계약을 붙입니다. 실제 호출 전문과 선택 파일·해시는 `01-input.json`에
저장됩니다. 예전 실행의 프롬프트는 해당 실행에 저장된 원본을 읽으세요.
