"""Render the saved improvement evidence in the existing documentation viewer."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from finarch.paths import PROJECT as ROOT
OUT = ROOT / 'reports/run/20260923-experiment-improvement'
TEMPLATES = Path(__file__).parent


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def validate_document_index(documents):
    """Check the just-built viewer index without changing experiment evidence."""
    errors, checked_links = [], 0
    for row in documents:
        path = ROOT / row['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            errors.append('INDEX_FILE_OR_HASH:' + row['path'])
            continue
        if path.suffix != '.md':
            continue
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith(('#', 'mailto:')):
                continue
            checked_links += 1
            if not (path.parent / unquote(parsed.path)).exists():
                errors.append('BROKEN_LINK:' + row['path'] + ':' + target)
    result = {'status': 'PASS' if not errors else 'FAIL',
              'checked_at': datetime.now(timezone.utc).isoformat(),
              'current_documents': len(documents), 'checked_local_links': checked_links,
              'errors': errors, 'model_calls': 0,
              'scope': 'Current improvement-run document index, hashes and local links only; no semantic evaluation.'}
    write(OUT/'current-documentation-validation.json', result)
    if errors:
        raise ValueError('CURRENT_DOCUMENTATION_VALIDATION_FAILED')


def template(name, target, values=None):
    body = (TEMPLATES / name).read_text()
    for key, value in (values or {}).items():
        body = body.replace('{{' + key + '}}', str(value))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(body)


def run_analysis_files(run_id):
    """Include only analysis artifacts that exist for the currently selected run."""
    folder = OUT/'03-research'/run_id
    candidates = [
        ('findings.md', '개선 재실험 핵심 결과'),
        ('bounded-output.md', '출력 길이 제한 120회 후속 확인'),
        ('bounded-output.json', '길이 제한 60쌍·원응답·보존 검증'),
        ('README.md', '재실험 분석 안내'),
        ('analysis.md', '재실험 결과 분석'),
        ('cases.md', '재실험 실제 사례'),
        ('comparison.json', '기존·새 응답 비교 자료'),
        ('intent-case-comparison.json', '진단 사례 20쌍과 원응답 근거'),
        ('summary.json', '재실험 분석 집계'),
        ('comparator-summary.json', '비교 기준 집계'),
        ('contrasts/analysis.md', '조건별 대응쌍 분석'),
        ('pilot/README.md', '진단 300조건 분석 안내'),
        ('pilot/analysis.md', '진단 300조건 관찰'),
        ('pilot/decision.json', '진단 후 확장 판단'),
    ]
    files = [(folder/name, title) for name, title in candidates if (folder/name).is_file()]
    status = read(OUT/'status.json', {})
    first_run = status.get('first_refined_run')
    if first_run and first_run != run_id and Path(first_run).name == first_run:
        first = OUT/'03-research'/first_run
        for name, title in [('findings.md', '반복 기준이 되는 첫 수집 결과'),
                            ('analysis.md', '첫 수집 전체 분석'),
                            ('intent-case-comparison.json', '첫 수집 진단 20조건의 변화')]:
            if (first/name).is_file():
                files.append((first/name, title))
    repeat_path = status.get('repeat_analysis_output')
    if repeat_path:
        repeat = (ROOT/repeat_path).resolve()
        if (OUT/'03-research').resolve() not in repeat.parents:
            raise ValueError('REPEAT_ANALYSIS_MUST_BE_INSIDE_RESEARCH_REPORTS')
        for name, title in [('README.md', '동일 조건 반복 분석 안내'),
                            ('analysis.md', '동일 조건 반복 결과'),
                            ('summary.json', '반복 일치·변화 집계')]:
            if (repeat/name).is_file():
                files.append((repeat/name, title))
    for bounded_run in status.get('bounded_followup_runs', []):
        if Path(bounded_run).name != bounded_run:
            raise ValueError('BOUNDED_RUN_MUST_BE_A_RUN_NAME')
        bounded = OUT/'03-research'/bounded_run
        for name in ('README.md', 'analysis.md'):
            if (bounded/name).is_file():
                files.append((bounded/name, f'{bounded_run} 소규모 확인 · {name}'))
    ledger = OUT/'03-research/continuation-cost-ledger.json'
    if ledger.is_file():
        files.append((ledger, '이번 작업의 실제 호출·비용 추정 장부'))
    return files


def run_analysis_section(status, files):
    if not files:
        return ''
    phase = status.get('phase', 'IN_PROGRESS')
    progress = ('수집 완료 상태입니다. 아래는 실제 저장된 분석 파일이며, 분석 완료 여부와 판단 근거는 각 파일을 따릅니다.'
                if phase == 'COLLECTION_COMPLETED' else
                '아래는 현재 저장된 분석 파일입니다. 수집 중간에 생성된 파일일 수 있으므로 존재만으로 수집·분석 완료를 뜻하지 않습니다.')
    links = ' · '.join(f'[{title}]({path.relative_to(OUT).as_posix()})' for path, title in files)
    repetition = ('동일 조건 두 번의 관찰 결과는 연결된 반복 분석에서 확인합니다. 두 번의 일치로 장기간 신뢰도나 의미 정답을 확정하지 않습니다.'
                  if status.get('repeat_analysis_status') == 'COMPLETED' else
                  '동일 조건 반복 안정성은 아직 미평가입니다.')
    return (f"\n\n## 현재 run의 분석 산출물 — {status['improved_run_id']}\n\n"
            f"저장 상태 **{phase}**. {progress}\n\n{links}\n\n"
            '기존 형식과 변경 형식은 응답 구조·검사 규칙이 다릅니다. 형식 유효 응답의 증가를 순수한 문제 풀이 능력 향상으로 해석하지 않습니다. '
            '숫자 없음(null)은 적절한 유보 여부와 구분합니다. ' + repetition)


def build():
    status = read(OUT/'status.json',{})
    run_id = status['improved_run_id']
    run = ROOT/'reports/experiments-run'/run_id
    summary = read(run/'summary.json',{})
    active_experiment = status.get('active_scope') == 'IMPROVED_LUNA_REEXPERIMENT'
    summary_calls = sum(m.get('attempts',0) for m in summary.get('models',[]))
    calls = status.get('experiment_request_attempts', summary_calls) if active_experiment else summary_calls
    # Provider responses and format-valid responses are different observations.
    successful = status.get('successful_responses', '미확인')
    current_review = status.get('current_review') if active_experiment else 'EXISTING_RESPONSE_INTENT_REVIEW'
    title = 'Luna 개선안 재실험 현황과 기존 분석' if active_experiment else '기존 Luna 응답의 문제·개선 검토'
    run_status = (f"{'현재 재실험' if active_experiment else '앞선 재실행 이력'}: **{run_id}** · "
                  f"이 run의 API 요청 시도 **{calls}회** · 제공자가 반환한 새 응답 **{successful}건** · "
                  f"저장된 실행 상태 **{status.get('phase','IN_PROGRESS')}**. "
                  '응답 확보는 형식 통과나 의미 정답을 뜻하지 않습니다.')
    current_intro = (
        '**현재 작업은 사용자가 재개를 지시한 개선안 재실험입니다.** ' + run_status + '\n\n'
        f"[현재 실행의 고정 요청·상태·호출 기록](../../experiments-run/{run_id}/README.md)을 먼저 보십시오. "
        '이하 기존 원응답 진단은 재실험 전에 완료한 분석으로 보존합니다. 개선 효과·의미 정확도·반복 안정성은 별도 평가 대상이며, 보고서 생성 자체는 모델을 호출하지 않습니다.'
        if active_experiment else
        '**현재 작업은 기존 실험 원응답을 원래 실험 취지에 비추어 검토하고, 확인한 문제와 개선안을 먼저 정리하는 일입니다.** 변경안을 저장해 둔 사실과 모델의 실제 응답이 좋아졌다는 판단을 구별합니다. 현재 검토·보고서 생성의 새 모델 호출은 0회입니다.')
    analysis_files = run_analysis_files(run_id)
    current_intro += run_analysis_section(status, analysis_files)
    repeat_complete = status.get('repeat_analysis_status') == 'COMPLETED'
    if repeat_complete:
        repeat_summary = read(ROOT/status['repeat_analysis_output']/'summary.json', {})
        observed = repeat_summary.get('overall', {})
        current_intro += (
            '\n\n## 이번 계속 작업의 완료 수치\n\n'
            f"실제 호출 **{status.get('continuation_actual_calls', 0):,}회**: "
            '앞선 진단 300 + 개선 전체 3,000 + 동일 조건 반복 3,000 + 길이 제한 확인 120입니다. '
            '각 run의 실패·미실행은 보존했으며, 소규모 확인을 전체 100원문 재검증으로 세지 않습니다.\n\n'
            f"반복에서 답이 양쪽에 관찰된 **{observed.get('answer_observed_pairs', 0):,}쌍** 중 "
            f"숫자·단위 또는 null이 같은 쌍은 **{observed.get('same_answer_and_scale', 0):,}개**입니다. "
            f"숫자↔null 전환은 **{observed.get('numeric_to_null', 0)+observed.get('null_to_numeric', 0):,}개**입니다. "
            '형식·인용 보완과 근거 선택 판단의 안정성을 구분해 현재 핵심 결과에 정리했습니다. '
            '후속 길이 제한 확인은 120회 모두 형식 통과·잘림 0이지만 의미 안정성의 완료 증거는 아닙니다.\n\n'
            f"이번 계속 작업의 사용량 기준 비용 추정은 **${status.get('continuation_paid_api_usage_cost_estimate_usd', 0):.7f}**이며 청구서 값은 아닙니다.")
    intent = read(OUT/'03-research/intent-review-evidence.json',{})
    review_cases = intent.get('selected_case_count','미확인')
    review_responses = intent.get('selected_response_count','미확인')
    review_files = len(intent['source_sha256']) if isinstance(intent.get('source_sha256'),dict) else '미확인'
    status.update(improved_run_id=run_id, model_calls=calls, experiment_request_attempts=calls,
                  report_new_model_calls=0,
                  updated_at=datetime.now(timezone.utc).isoformat())
    if not active_experiment:
        status['current_review'] = current_review
    write(OUT/'status.json',status)
    template('improvement-report-template.md',OUT/'README.md',{
        'status':status.get('phase','IN_PROGRESS'),'run_id':run_id,'calls':calls,
        'successful':successful,'review_cases':review_cases,'review_responses':review_responses,
        'review_files':review_files,'title':title,'current_intro':current_intro,
        'run_status':run_status,'run_link_label':'현재 재실험 자료' if active_experiment else '앞선 재실행 자료'})
    template('a100-review-template.md',OUT/'02-a100/README.md')
    template('research-review-template.md',OUT/'03-research/README.md')
    remote=read(OUT/'02-a100/source/summary.json',{})
    a=['# A100 자료에서 확인한 범위','',f"원격 집계 시각: `{remote.get('updated_at')}` · 저장 상태 `{remote.get('status')}`. 읽기 전용 수집본이며 원격 프로세스의 현재 생존 상태를 확인한 결과는 아닙니다.",'',
       '|모델|계획|기록|기존 형식 통과|잘림|상태|','|---|---:|---:|---:|---:|---|']
    for m in remote.get('models',[]):
        a.append(f"|{m['key']}|{m['planned']:,}|{m['recorded']:,}|{m.get('schema_valid','미평가')}|{m.get('truncated','미평가')}|{m['status']}|")
    a += ['', '## 이번 개선에 적용할 내용', '',
      '- **채택:** 전체 계획, 실제 시도, 정상 종료, 형식 통과, 잘림, 미실행을 별도로 유지합니다. 금융 모델에서 출력이 없다는 사실을 오답률 100%로 바꾸지 않습니다.',
      '- **수정 채택:** 추론 출력이 길어지면 속도·대기·잘림도 함께 봅니다. Qwen3-8B 기록에서 잘림 211건, preemption 표본 합 1,417과 KV peak 1.0이 함께 보이지만 이 집계만으로 어느 것이 원인인지 확정하지 않습니다. 자원 설정 비교는 응답 계약 개선과 분리합니다.',
      '- **보류:** 금융 모델과 직접 기반 모델의 능력 비교. 이번 수집본에서 금융 모델의 본실험 응답은 모두 없고 NOT_EXECUTABLE입니다. 원격 오류 NO_COMPATIBLE_TOPOLOGY는 환경의 실행 호환성 문제이지 해당 모델의 금융 문제 능력 판정이 아닙니다.',
      '- **기각:** 원격 1,080개 원문 집단과 Luna 100개 원문 집단의 집계율을 그대로 모델 우열로 비교하는 것. cohort 교집합·Q/C·계약·추론설정·샘플링·revision·양자화 조건을 먼저 맞춰야 합니다.',
      '', 'Luna none/medium과 각 Qwen의 native 토글은 동일한 추론량 척도가 아닙니다. 처리량을 맞추기 위해 답의 출력 상한이나 채점 기준을 바꾸지 않습니다. 원격의 raw를 가져오지 않았으므로 P0/P1의 의미 대응 개선 근거는 이번 Luna 원응답에서만 검토합니다.', '']
    (OUT/'02-a100/analysis.md').write_text('\n'.join(a))
    base=read(OUT/'01-baseline/summary.json',{}); overall=base.get('overall',{}); tags=overall.get('tags',{})
    plan=read(run/'plan.json',{}); model=(plan.get('models') or [{}])[0]
    quota=read(OUT/'quota-preflight.json',{})
    authorization=read(OUT/'execution-authorization.json',{})
    user_managed_usage=authorization.get('scope',{}).get('account_usage_monitoring')=='USER_MANAGED'
    quota_note=('실행 승인에서 사용자가 계정 사용량을 직접 관리하도록 정했습니다. API 예산 $35와 호출 시도·비용·캐시 기록 조건은 execution-authorization.json에 남아 있습니다. 보고서 생성 자체는 계정 사용량을 조회하거나 모델을 호출하지 않습니다.' if user_managed_usage else f"이전에 저장한 한도 검사 이력은 `{quota.get('status','NOT_CHECKED')}` / `{quota.get('reason','')}`입니다. 보고서 생성 자체는 새 한도 조회나 모델 호출을 하지 않습니다.")
    lines=['# '+title+' 보고서','',
      current_intro,'',
      '[문제·개선 계획](../../../docs/02-experiments/02_analysis/02_comparison/README.md) → [검토한 원응답과 근거 해시](03-research/intent-review-evidence.json) → 아래 관찰과 제안 순서로 읽습니다.', '',
      f"{'재실험 전에 완료한' if active_experiment else '이번'} 의도 대응 검토는 원문 **{review_cases}개**, 선택 응답 **{review_responses}개**, 근거 파일 **{review_files}개**의 해시를 연결했습니다. 목적에 맞춰 고른 진단 사례이며 전체 오류율의 무작위 표본이나 새로운 의미 정답이 아닙니다. 기존 점수와 원응답은 변경하지 않습니다.", '',
      f"기존 응답 형식(파일 식별명 `FinancialAnswerMagnitudeV4`)은 exp-006에서 사용한 규약입니다. 변경해 둔 응답 형식(파일 식별명 `FinancialAnswerV6`; 제공자가 반환한 새 응답 {successful}건)은 지시문·JSON 구조·Python 검사를 변경해 저장한 안입니다. 이 식별명의 숫자는 모델 버전이나 여섯 번째 실험을 뜻하지 않습니다. 이하에서는 기존 형식·변경해 둔 형식으로 부릅니다.", '',
      '## 사용자의 의도와 문서 구조','',
      '실험의 의도는 P0에서 제공된 질문·본문을 기본적으로 풀게 하고, P1에서 근거의 충분성·충돌·질문의 출처 조건을 고려하도록 안내하는 것입니다. 하지만 기존 공통 지시문에도 유보 작성법과 조건부 답변 안내가 들어 있어, 기존 P0를 행동 안내가 전혀 없는 조건으로 해석하면 안 됩니다. 변경해 둔 형식은 판단 지시를 P1에 모으려는 안입니다.','',
      '두 조건에 동일한 공통 JSON 구조를 제공하는 것은 표현 조건을 맞추려는 조치이며, 구조가 모델 행동에 주는 영향이 0이라는 보장은 아닙니다. 목표는 답의 정확도와 형식 준수, 답·설명 표현의 일관성, 조건 변화에 대한 민감도를 구분하는 것입니다. ' + ('동일 조건 두 번의 실제 관찰은 위 반복 분석을 따르며 일반 신뢰도·의미 정답과 구별합니다.' if repeat_complete else '같은 조건의 반복 안정성은 별도 미평가입니다.'),'',
      '[실험 문서](../../../docs/02-experiments/README.md)는 전체→00_input→01_evaluation→02_analysis 순서로 정리했습니다. 각 단계에 기대 결과, 필요한 조치, 실제 파일, 분기·실패·미평가·산출물과 Mermaid를 연결했습니다. 기존 docs 보관본과 기존 형식의 원응답은 보존했습니다.','',
      '## 완료한 기존 자료 검토 — 실제 Luna 결과에서 확인한 문제','',
      f"원응답 {overall.get('planned')}건 모두 JSON으로 읽히고 당시 스키마의 타입을 통과했지만, 추가 규칙에서는 {overall.get('saved_status',{}).get('VALID',0):,}건이 통과하고 {overall.get('saved_status',{}).get('INVALID_RESPONSE',0):,}건이 실패했습니다. 유보 선언과 숫자/부호 동시 출력 {tags.get('DECLARED_ABSTENTION_WITH_NON_NULL_ANSWER')}건, 자릿수 실패 {tags.get('SAVED_DECIMAL_PLACES_FAILURE')}건입니다. 따라서 단순 JSON 파싱률만 높이는 것으로 사용자 의도에 맞는 표현을 보장할 수 없습니다.",'',
      f"근거 인용 문자열 불일치는 전체 응답을 다시 읽으면 {tags.get('EVIDENCE_NOT_EXACT_SUBSTRING')}/3,000입니다. 정확한 문자열 일치 자체도 의미상 지지 근거라는 보장은 아닙니다. 질문·자릿수 충돌은 16개 원문·32개 요청이며 기존 입력은 수정하지 않았습니다.",'',
      '|조건|원문 계획|숫자 일치|숫자 불일치|형식 실패|유효한 null|','|---|---:|---:|---:|---:|---:|']
    for m in base.get('by_original_reasoning',[]):
        x=m['original_outcomes'];lines.append(f"|{m['reasoning']}|{m['planned']}|{x.get('NUMERIC_MATCH',0)}|{x.get('NUMERIC_MISMATCH',0)}|{x.get('FORMAT_OR_COLLECTION_FAILURE',0)}|{x.get('VALID_NULL_ANSWER',0)}|")
    lines += ['', '[분모·유형·사례·원본 해시의 상세](01-baseline/README.md)를 함께 보십시오. 같은 조건을 반복한 자료가 아니므로 off/on 일치를 반복 안정성으로 부르지 않습니다.', '',
      '## 재실험 전 변경안의 구현 범위 — 최신 관찰은 위 결과 참조','',
      '아래는 파일과 로컬 검사에 구현된 내용입니다. 이전에 저장해 둔 변경안의 구현 상태를 설명하며, 이번 사례 검토에서 새로 제안한 사항까지 구현 완료로 표시하지 않습니다.', '',
      '|변경|파일에 구현한 내용|남은 문제와 해석 제한|','|---|---|---|',
      '|공통 JSON|부호 있는 숫자 또는 null, 설명·인용, 메타정보. status 삭제|유보 선언과 숫자의 모순 211건은 status 삭제 후 같은 방식으로 관측할 수 없음. 오류가 해결됐다고 단정하지 않음|',
      '|P0/P1|공통 schema의 설명·일부 행동 단어 제한, P1에 충분성·충돌·명시출처 판단 안내|단어 검사는 의미상 중립성을 증명하지 않음. 항상 유보하는 정책을 좋은 대응으로 보지 않음|',
      '|표현 검사|숫자와 부호 일치, null이면 메타정보 둘 다 null, 출력 정밀도|원응답을 고치거나 값에 맞춰 정답을 바꾸지 않음|',
      '|자유문장 설명·인용|설명과 답의 일관성·정확 인용을 지시하고 빈 문자열을 제한|조건부 수치의 역할·설명의 의미·근거 충분성은 검사하지 않음. 인용 문자열 존재는 별도 관찰값|',
      '|출력 정밀도|Q/C·메타값 보존, 충돌 시 메타정보 우선 명시|기존 지시와 우선순위가 달라 해당 16개 원문을 구분해야 함. 입력 충돌 해결 완료가 아님|',
      '|실행 관리|구현 사본·요청 해시 보존, 회차당 최대 100회 호출, 중복·전달 불명·사용량 누락 시 차단|유료 예산은 토큰 기반 추정이며 청구액 상한 보장이 아님|',
      '', '## 검토할 개선 제안 — 아직 적용·효과 확인하지 않은 범위', '',
      '[문제·개선 계획](../../../docs/02-experiments/02_analysis/02_comparison/README.md)에 제안과 판단 근거를 모았습니다. 공통 표현 규약과 P1 판단 안내의 경계를 확인하고, 실제 사례에서 최종 숫자·조건부 값·출처 조건·근거를 연결하는 데 필요한 최소 정보를 먼저 확인합니다.', '',
      '조건부 결과 필드, 근거 ID·위치, 중복 부호 메타정보 축소 등은 후속 설계 후보입니다. 새 필드는 P0의 행동까지 바꿀 수 있으므로 도입만으로 중립성이나 개선을 확정하지 않습니다. 도입한다면 P0/P1의 공통 입력·스키마·검사를 고정하고 그 변경 효과를 별도로 비교해야 합니다. 새 의미 루브릭이나 평가 모델을 만들었다는 뜻이 아닙니다.', '',
      '## 기존 관찰에서 논문으로 연결할 비교대조','',
      '1. **응답 표현과 판단의 분리:** 유보라고 말하면서 숫자를 채운 경우를 원응답 수준에서 보존하고, 개선 계약 후에도 공통 관찰 기준으로 다시 검사합니다.',
      '2. **안내 × 추론 × 변형의 차이:** P1 안내에 따른 null 전환이 off/on 및 VALUE/SOURCE/RELATION/EA에서 어떻게 다른지 원문별로 연결합니다. null 증가를 적절한 유보 향상으로 단정하지 않습니다.',
      '3. **출처 부착 전후:** SOURCE를 실제 부모 VALUE에 연결해 비교합니다. 앞/뒤 위치와 다른 부모가 섞인 비교를 단일 출처 효과로 부르지 않습니다.',
      ('4. **동일 조건 반복:** 같은 실제 전송 바이트의 3,000조건을 두 번 수집했고 숫자 유무·값·단위·형식·근거의 변동을 위 반복 분석에 기록했습니다. 원문 P1 정상 대조는 실행하지 않았으므로 적절한 유보율이나 과도한 유보의 정도는 미평가입니다.' if repeat_complete else '4. **동일 조건 안정성:** 아직 미측정입니다. 고정한 요청의 독립 반복과 원문 P1 대조는 후속 확인 후보입니다.'),
      '5. **외부 모델:** A100 자료는 현재 실행 가능 여부·시간 자료입니다. 금융 모델 본실험 응답이 없어 금융튜닝 효과 비교는 보류합니다.', '',
      '[계산한 대응표와 연구 판단](03-research/analysis.md) · [의도 대응 실제 사례](03-research/qualitative-cases.md) · [A100 관찰](02-a100/analysis.md). 이 100개 원문은 개선 과정에서 사용한 집단입니다. 논문의 최종 확인 실험은 개발 중 보지 않은 집단과 고정한 기준으로 분리해야 합니다.', '',
      '## 완료한 로컬 확인과 남은 판단','',
      '기존·변경 응답 형식, API, 제한 실행의 로컬 모의 회귀 검사 기록은 04-validation에 있습니다. 이는 실제 모델이 지시를 따랐다는 검증과 다릅니다. 기존 Luna 분석은 입력·원응답·결과 12,008개 파일의 해시 보존을 확인했습니다. 이번 의도 대응 검토의 선택 사례와 근거 파일은 intent-review-evidence.json에 따로 연결했습니다. 문서 링크·README 생성·실제 브라우저 확인은 별도 기록을 따르며 사용자 검토 완료로 표시하지 않습니다.', '',
      ('현재 재실험은 위 기존 진단 이후의 실행입니다. ' if active_experiment else '현재 우선순위는 기존 응답에서 확인한 문제와 최소 개선안을 검토하는 것입니다. ') + ('전체 두 수집과 길이 제한 소규모 확인을 마쳤습니다. 관찰된 개선과 반복 변동은 위 핵심 결과를 따르며, 의미 정확도·장기간 신뢰도·개발 집단 밖 일반화는 미평가입니다.' if repeat_complete else '변경 형식의 모델 효과, 의미 정확도, 같은 조건의 반복 안정성은 남은 판단입니다.'), '',
      '## 현재 재실험의 저장 기록' if active_experiment else '## 앞선 재실행 시도 이력 — 현재 원응답 검토와 분리', '',
      run_status + ' 이 횟수는 보고서 생성에서 새로 호출한 수가 아닙니다.', '',
      f"당시 계획은 모델 `gpt-5.6-luna`, 동일 원문 100개·변형 700개, 총 {model.get('requests',3000):,}요청이었습니다. none/medium, 캐시 금지, 동시 50개, 출력 상한 8,192토큰으로 준비했습니다. 입력 추정 {model.get('input_token_estimate',0):,}토큰, 출력 1,000토큰/요청 가정 비용 ${model.get('api_equivalent_estimate_usd_at_1000_output_tokens',0):.4f}, 출력 상한 전체 사용 가정 약 $30.35, 실행 예산 설정 $35는 저장된 준비 시점의 계획입니다. 가격 출처로 기록한 [OpenAI Luna 공식 문서](https://developers.openai.com/api/docs/models/gpt-5.6-luna)를 연결하며 이 보고서가 최신 가격을 다시 조회했다는 뜻은 아닙니다.", '',
      quota_note, '',
      '야간 읽기 전용 정기 점검은 아침 보고 후 일시정지한 이력이 있습니다. 이 보고서 생성 자체는 자동화를 재개하거나 다음 모델 호출을 실행하지 않습니다. ' + (f"재개한 실험은 별도 고정 run `{run_id}`에서 진행하며 기존 사례 검토와 실행 결과를 구별합니다." if active_experiment else '이후 재실행을 진행한다면 고정한 요청·구현·기준을 별도 run으로 보존하고, 현재 사례 검토와 실행 결과를 구별해야 합니다.'), '']
    blocker = read(OUT/'api-blocker.json', {})
    if blocker.get('run_id') and (active_experiment or (blocker.get('run_id') == run_id and status.get('phase') == 'API_CREDIT_BALANCE_EXHAUSTED')):
        lines += ['', '### 앞선 요청에서 확인한 외부 차단', '',
            f"아래는 [보존한 api-blocker.json](api-blocker.json)에 기록된 `{blocker['run_id']}`의 과거 이력입니다. 현재 실행의 상태는 보고서 맨 위 기록을 따릅니다.", '',
            '첫 요청을 OpenAI API에 전송했으나 HTTP 429와 `credit_balance_exhausted`로 거절됐습니다. 제공자 메시지는 API 크레딧 잔액이 없으며 충전이 필요하다는 내용입니다. API 요청 시도 1회, 정상 모델 응답 0건이며 나머지 요청은 전송하지 않았습니다.', '',
            '이 상태는 계정 사용량 자동 점검에 따른 중단이 아닙니다. 사용량은 사용자 직접 관리로 적용했습니다. 초기 분류기가 이를 RATE_LIMITED로 표시한 기록은 보존하고, 정확한 원인은 api-blocker.json에 QUOTA_EXHAUSTED로 별도 기록했습니다. 같은 키의 단순 재시도로 해결되는 요청 속도 제한이 아닙니다.', '',
            '이는 앞선 재실행 요청의 차단 이력이며 새 run의 현재 상태를 나타내지 않습니다. 원응답과 기존 점수는 수정하지 않았으며 실제 청구 금액은 미확인으로 남깁니다.', '']
    lines[2:2] = ['[종합 현황 대시보드](http://127.0.0.1:8895/dashboard/01-overview/) · [문항 분석 대시보드](http://127.0.0.1:8895/dashboard/02-explorer/): 저장된 실제 수치·산점도·표·응답을 연결합니다.', '']
    content_analysis = OUT/'03-research/20260924-content-analysis'
    if (content_analysis/'analysis.md').is_file():
        lines[2:2] = ['[원본 R0/R1·변형 조건 분석](03-research/20260924-content-analysis/analysis.md): 형식 다음의 숫자 일치와 내용 미평가를 분리합니다.', '']
    (OUT/'REPORT.md').write_text('\n'.join(lines))
    docpaths=[OUT/'README.md',OUT/'REPORT.md']
    docs_root = ROOT/'docs/02-experiments'
    overview = [docs_root/'README.md']
    docpaths += overview + sorted((p for p in docs_root.rglob('*.md') if p not in overview),
                                  key=lambda path: str(path).replace('/README.md', '/'))
    docpaths += [OUT/'01-baseline/README.md',OUT/'01-baseline/analysis.md',OUT/'01-baseline/cases.md',
                 OUT/'02-a100/README.md',OUT/'02-a100/analysis.md',
                 OUT/'03-research/README.md',OUT/'03-research/analysis.md',OUT/'03-research/qualitative-cases.md',
                 OUT/'04-validation/README.md']
    analysis_titles = dict(analysis_files)
    docpaths += [path for path, _ in analysis_files if path.suffix == '.md']
    docpaths += [content_analysis/name for name in ('README.md', 'analysis.md', 'summary.json', 'source-hashes.json', 'validation.json')
                 if (content_analysis/name).is_file()]
    documents=[]
    for path in docpaths:
        if not path.exists(): continue
        text=path.read_text(); relative=str(path.relative_to(ROOT))
        documents.append({'path':relative,'title':text.splitlines()[0].lstrip('# ') if text.splitlines() else analysis_titles.get(path, path.name),
            'group':('재실험 분석 · '+run_id if path in analysis_titles else
                     '02-experiments' if relative.startswith('docs/') else path.parent.name),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    navigation=[['문제·개선','docs/02-experiments/02_analysis/02_comparison/README.md'],
                ['작업 보고서',str((OUT/'REPORT.md').relative_to(ROOT))],['실험 전체','docs/02-experiments/README.md'],
                ['Luna기준선',str((OUT/'01-baseline/analysis.md').relative_to(ROOT))],
                ['논문비교',str((OUT/'03-research/analysis.md').relative_to(ROOT))],
                ['A100',str((OUT/'02-a100/analysis.md').relative_to(ROOT))]]
    navigation[0:0] = [[title, str(path.relative_to(ROOT))]
                       for path, title in analysis_files if path.suffix == '.md']
    if (content_analysis/'analysis.md').is_file():
        navigation.insert(0, ['R0/R1·변형 분석', str((content_analysis/'analysis.md').relative_to(ROOT))])
    evidence_path=OUT/'03-research/intent-review-evidence.json'
    evidence_files=([{'path':str(evidence_path.relative_to(ROOT)),
                     'title':'기존 원응답 의도 대응 검토 근거',
                     'sha256':hashlib.sha256(evidence_path.read_bytes()).hexdigest()}]
                    if evidence_path.exists() else [])
    evidence_files.extend({'path':str(path.relative_to(ROOT)), 'title':title,
                           'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                          for path, title in analysis_files if path.suffix == '.json')
    documents.extend({**item, 'group':'03-research'} for item in evidence_files)
    write(OUT/'documentation.json',{'kind':'PIPELINE_DOCUMENTATION','title':title,
        'documents':documents,'navigation':navigation,'entry_document':str((OUT/'REPORT.md').relative_to(ROOT)),
        'evidence_files':evidence_files,
        'model_calls':0,'new_model_calls':0,'experiment_request_attempts':calls,
        'scope':('Improved Luna reexperiment; report generation uses no model calls and preserves prior response analysis.' if active_experiment else 'Existing response review and report generation use no model calls; earlier experiment attempts are recorded separately.')})
    validate_document_index(documents)
    write(OUT/'migration.json',[])
    write(OUT/'summary.json',{'kind':'PIPELINE_DOCUMENTATION','documents':len(documents),
        'status':status.get('phase'),'current_review':current_review,'active_scope':status.get('active_scope'),
        'model_calls':0,'new_model_calls':0,'experiment_request_attempts':calls})
    with (OUT/'events.jsonl').open('a') as f:
        f.write(json.dumps({'at':status['updated_at'],'event':'REPORT_REFRESHED','documents':len(documents),
                            'new_model_calls':0,'model_calls':0,'experiment_request_attempts':calls})+'\n')
    print(json.dumps({'run_id':run_id,'documents':len(documents),'new_model_calls':0,
                      'experiment_request_attempts':calls}))


if __name__ == '__main__':
    build()
