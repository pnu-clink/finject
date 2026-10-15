# 03-validation

[문서의 단계·요구·실행 흐름](../../../../../docs/01-dataset/02-generation/03-validation/README.md) · [전체 소스 구조](../../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[ea_inverse_review.py](ea_inverse_review.py)|Q/C-only recovery annotation using the dedicated ea_inverse_review profile (gpt-6.1-sol/high API); pin the resolved profile, validate response/display, save immutable attempt and path/hash reference; never changes EA quality status.|
|[dtt_answer.py](dtt_answer.py)|R18: independent individual answers to saved, audited final observations.|
|[ea_recovery.py](ea_recovery.py)|Bounded, observation-only recovery witnesses for reviewed source grammars.|
|[feedback_evidence.py](feedback_evidence.py)|Collect immutable failure references for agent-led instruction refinement.|
|[source_validation.py](source_validation.py)|Validate attribution removal against the saved, assigned VALUE dependency.|
|[stage.py](stage.py)|Ordered stage subjobs; artifact paths retain their existing contract.|
|[validate_evidence_candidate.py](validate_evidence_candidate.py)|Validate a saved evidence-backed candidate without changing the human decision.|
|[verify_external_evidence_call.py](verify_external_evidence_call.py)|One fresh POT call, followed by local source/runtime/graph verification.|
