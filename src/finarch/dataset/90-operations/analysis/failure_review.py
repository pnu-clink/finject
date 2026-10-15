"""Build an evidence-linked descriptive review without model calls or mutation of inputs."""
import collections
import hashlib
import json
from pathlib import Path

ROOT = (Path(__file__).resolve().parent / '../../../../..').resolve()
SOURCE = ROOT / 'reports/run/20260917-002'
OUTPUT = ROOT / 'reports/run/20260920-002-failure-review'
INPUTS = {}


def read(path):
    raw = path.read_bytes()
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def save(name, value):
    (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


# Editorial classifications describe saved observations; they do not certify semantic truth.
CAT = {}


def category(key, phase, title, owner, why, supply, fix, example, confidence='기록에 근거한 원인 분류; 개선 효과는 미검증'):
    CAT[key] = dict(id=key, phase=phase, title=title, owner=owner, why=why,
                    supply=supply, fix=fix, example=example, confidence=confidence)


category('P_PERIOD', 'Preparation', '질문의 연도·회사와 자료가 맞지 않습니다', '원본 확인·보완',
         '질문에서 요구한 시점이나 회사의 수치가 없습니다. 정답과 맞는 다른 연도를 대신 쓰면 질문 자체가 달라집니다.',
         '질문의 회사·연도와 일치하는 표, 표 제목, 주석을 함께 제공해야 합니다.',
         '원문 출처에서 질문의 오기인지 자료 누락인지 확인합니다. 확인된 정정본을 별도 버전으로 만들고 원본·변경 이유를 보존합니다.',
         'test-0022: 질문은 2014년인데 표는 2004·2003년입니다. 2004년의 875−848=27이 저장 정답과 같아도 2014년 답이라고 할 수 없습니다.')
category('P_MISSING', 'Preparation', '필요한 금액·대상·조건이 빠져 있습니다', '원본 보완 + 준비 단계 확인',
         '있어 보이는 비슷한 수치를 사용해도 질문이 요구한 값은 아닙니다. 필요한 값이나 적용 조건을 추가하지 않고는 해당 계산을 확정하기 어렵습니다.',
         '숫자마다 무엇의 값인지, 어느 범위인지, 필요한 시작값·만기·거래 방향을 명시해야 합니다.',
         '계산에 필요한 항목 목록과 제공된 항목을 먼저 대조합니다. 빠진 내용은 출처에서 보완하며 비슷한 항목이나 정답으로 대신하지 않습니다.',
         'test-0029: 발행할 수 있도록 허용된 주식 수만 있는데 실제 발행된 주식 수를 묻습니다. 두 수는 같은 뜻이 아닙니다.')
category('P_MEASURE', 'Preparation', '어떤 값·비율을 구하라는지 분명하지 않습니다', '질문 명확화 또는 검토 기준 보완',
         '표에는 여러 계산이 가능하지만 질문이 대상이나 비교 방법을 충분히 정하지 않아 검토가 멈췄습니다. 모든 사례가 원본 오류로 확정된 것은 아닙니다.',
         '예를 들어 기본 주당이익인지 희석 주당이익인지, 단순 차이인지 변화율인지 명시합니다.',
         '실제로 답이 달라지는 두 해석을 먼저 비교합니다. 금융 용어만으로 의미가 정해지는 경우는 인정하고, 그렇지 않으면 질문을 보완합니다.',
         'test-0214: 기본 주당이익은 1.563, 희석 주당이익은 1.551인데 질문에는 어느 쪽인지 없습니다.')
category('P_CONVENTION', 'Preparation', '계산 관례를 어디까지 인정할지 정하지 못했습니다', '검토 기준 우선 보완; 필요한 조건만 원본에 추가',
         '검토기는 이자 계산·평균·반올림 등에 다른 관례가 있다는 이유로 멈췄습니다. 관례를 문장에 쓰지 않았다는 사실만으로 원본이 잘못됐다고 단정할 수 없습니다.',
         '일수 기준, 복리 방식, 평균 방식, 초기값, 반올림 방식을 공통 지침이나 문항 조건으로 제공합니다.',
         '허용할 기본 관례와 적용 근거를 사전에 정합니다. 이름이 명확한 표준 방법은 사용하고, 실제로 경쟁하는 해석이 결과를 바꾸는 경우만 추가 조건을 요구합니다.',
         'test-0965: 집별 평당가격의 단순 평균은 181.64, 전체 가격÷전체 면적은 180.00입니다. 어느 평균을 원하는지 정하면 됩니다.')
category('P_SCALE', 'Preparation', '단위·정답 표기가 질문과 맞지 않습니다', '원본·정답 메타정보 확인 + 정제 보완',
         '달러와 천 달러, 소수와 백분율, 질문의 자릿수와 정답 자릿수가 섞였습니다. 숫자만 비교하면 서로 다른 뜻의 값을 비교하게 됩니다.',
         '표의 단위, 출력 단위, 자릿수, 정답 산출 근거를 함께 제공합니다.',
         '값과 단위를 함께 변환하고 변환 전후를 기록합니다. 정답에 맞추기 위해 질문이나 수치를 바꾸지 말고 어느 기록을 정정해야 하는지 출처로 확인합니다.',
         'test-0320: 713천 주×42달러는 29.946백만 달러입니다. 백만 단위의 정수 답은 30인데 저장 정답은 29,946입니다.')
category('P_TEXT', 'Preparation', '깨진 문자·날짜를 안전하게 고치지 못했습니다', '정제 규칙 보완',
         '날짜가 붙어 있거나 구두점이 숫자처럼 남았습니다. 현재 규칙은 숫자를 보호하므로 문자 깨짐까지 막거나 수정 위치를 확정하지 못합니다.',
         '깨지기 전 원문, 정제된 문장, 두 문장의 위치 대응표를 제공합니다.',
         '출처로 확인된 문자 깨짐과 실제 숫자를 구별합니다. 반복되는 문구는 위치와 주변 문장으로 지정하고 모든 편집을 원문 기준으로 한 번에 적용합니다.',
         'test-0229: “december 292000”을 날짜로 분리하는 작업이 숫자 변경으로 취급됐습니다. test-0300은 반복 문구의 수정 위치에서 멈췄습니다.')
category('P_VERIFY_UNCERTAIN', 'Preparation', '계산은 됐지만 검토가 해석을 확정하지 못했습니다', '검토 기준 우선 보완; 문항별 원본 확인',
         '계산 실행과 별개로 검토기가 질문의 뜻·관례를 확정하지 못했습니다. 이것은 틀렸다는 확정 판정과 다릅니다.',
         '선택한 항목·단위·기간·공식과 그 선택 이유, 대안 해석이 실제로 만드는 답을 함께 제공합니다.',
         '상식적인 방향·금융 관례를 무시한 과도한 모호성 판정을 먼저 재검토합니다. 남는 실질적 모호성만 질문에 보완합니다.',
         'test-0014: 1분기 60%에서 2분기 50%로 바뀌었습니다. −10%p의 변화와 감소 폭 10%p를 구분하면 됩니다. 모든 경우를 자료 부족으로 볼 필요는 없습니다.')
category('P_VERIFY_FAIL', 'Preparation', '풀이·설명·검토 판단 중 서로 맞지 않는 부분이 있습니다', '계산·검토 과정 우선 보완',
         '저장된 검토에서 계산 방법·단위·근거 또는 설명의 문제가 지적됐습니다. 일부 판단에는 이견이 있어 14건 모두 계산 오류로 확정하지 않습니다.',
         '중간 계산, 사용한 원문 구절, 단위와 마지막 반올림 규칙을 같이 제공합니다.',
         '잘못된 계산·설명은 고치고, 검토가 근거 없이 한 관례만 강제한 경우에는 검토를 고칩니다. 숫자가 우연히 맞아도 단위가 다른 계산은 통과시키지 않습니다.',
         'test-0083: 지수가 100→205이면 변화는 105포인트입니다. 이를 105%라고 설명하면 숫자는 같아도 묻는 양이 달라집니다.')
category('P_GOLD', 'Preparation', '계산과 저장 정답이 다릅니다', '원본 정답·계산을 따로 재확인',
         '의미 검토는 통과했지만 계산 결과와 저장 정답이 달라 멈췄습니다. 의미 검토 통과만으로 저장 정답이 틀렸다고 확정할 수 없습니다.',
         '정답 숫자만이 아니라 근거 행, 공식, 중간값, 단위와 반올림 규칙이 필요합니다.',
         '원문으로 양쪽 계산을 재현해 차이가 나는 지점을 찾습니다. 정답에 맞추기 위한 숫자 보정은 금지하고 기존 제외 상태와 원본을 보존합니다.',
         'test-0349: 실행값은 480.0, 저장 정답은 129.6입니다. 다르다는 사실과 어느 쪽이 맞는지는 구별해야 합니다.')
category('P_NOANSWER', 'Preparation', '필요한 정보가 없어 숫자 답을 만들지 못했습니다', '원본 보완 + 준비 단계에서 조기 확인',
         '생성된 풀이가 답을 비워 두었는데 실행기는 숫자만 받으므로 멈췄습니다. 단순한 숫자 읽기 오류가 아닙니다.',
         '질문에 필요한 수치와 조건, 없을 경우 무엇이 빠졌는지 명시한 기록을 제공합니다.',
         '실행 전 정보 부족을 별도 상태로 반환하도록 하고 출처에서 필요한 자료를 보완합니다. 0이나 정답 숫자를 임시로 넣지 않습니다.',
         'test-0324: 세금 납부액과 세금 비용을 묻는데 자료에는 미지급 세금 잔액만 있습니다.')
category('P_NUMBER', 'Preparation', '사람이 읽는 숫자 표현을 프로그램이 받지 못했습니다', '숫자 정제·등록 규칙 보완',
         'four, five, three, six months, EUR90처럼 의미는 읽을 수 있지만 숫자만 기대한 프로그램과 맞지 않았습니다.',
         '원문 표현, 뜻이 같은 숫자값, 단위, 원문 위치를 한 묶음으로 제공합니다.',
         'number-rules.json과 숫자 등록을 보완하여 문자 수량과 통화 접두어를 처리합니다. 원문과 변환 로그를 남기고 같은 표현의 회귀 검사를 합니다. 이번 분석에서는 규칙을 변경하지 않았습니다.',
         'test-0768: four를 4로 기록했지만 원문이 숫자 토큰이 아니라 거절됐습니다. 원본을 새로 만들 문제는 아닙니다.')
category('P_LINK', 'Preparation', '원문·코드의 연결 정보가 맞지 않습니다', '정제·근거 연결·검사 과정 보완',
         '인용 구절의 위치, 코드 줄, 수식 이름, 계산에 연결되는 입력 등의 약속이 맞지 않아 내용을 검사하기 전에 멈췄습니다.',
         '같은 버전의 원문과 질문, 인용 위치, 코드 줄, 값의 역할을 일관되게 제공합니다.',
         '문장 정제 후 위치를 다시 계산하고 실제 인용문과 대조합니다. 반복·조건문에서 이번 계산에 쓰지 않은 값도 구별합니다. 생성 오류와 검사기 오류를 원기록으로 나눕니다.',
         'test-1957: 인용 위치가 문장 끝 마침표까지 포함했지만 인용문에는 마침표가 없었습니다.')
category('P_CODE', 'Preparation', '생성된 코드가 실행 규칙과 맞지 않습니다', '계산 코드 생성·실행 보완',
         '리스트 위치처럼 정수를 요구하는 자리에 소수를 넘겨 계산이 중단됐습니다.',
         '숫자의 값 외에 개수·위치·금액 등 용도를 제공합니다.',
         '개수는 정수인지 확인한 뒤 정수로 사용합니다. 금액을 무조건 정수로 바꾸는 식의 일괄 보정은 하지 않습니다.',
         'test-1948: 관측 개수가 실수로 전달되어 리스트 범위를 지정하는 계산에서 멈췄습니다.')
category('P_TRANSPORT', 'Preparation', '응답을 끝까지 받지 못했습니다', '실행·재시도 관리',
         '연결 실패 또는 불완전한 응답으로 검사를 끝내지 못했습니다. 자료의 내용이 틀렸다는 증거가 아닙니다.',
         '데이터 내용은 그대로 두고 요청 식별자·완료 상태·수신 응답을 보존합니다.',
         '통신 재시도와 내용 수정 재시도를 분리하고 완료된 단계부터 안전하게 재개합니다.', 'Preparation 7건: 연결 실패 6건, 불완전 응답 1건.')

category('G_NUM_DUP', 'Generation', '삭제할 값과 같은 숫자가 보존 목록에도 남습니다', '변형 계획·숫자 검사 보완',
         '삭제할 값이 같은 편집 구간에 반복되는데 숫자 목록에서는 한 번만 뺐습니다. 실제 요청이 나머지 같은 숫자를 보존하도록 요구하므로 완전히 지우면 숫자 검사에 걸릴 수 있습니다.',
         '같은 사실이 반복되는 위치 전체와 각각의 역할, 삭제할 위치와 남길 위치를 구별해서 제공합니다.',
         '숫자가 같다는 이유만으로 모두 지우지 말고 같은 사실의 반복인지 확인한 뒤 삭제 계획에 묶습니다. 검사기도 그 계획의 남을 숫자 목록을 사용해야 합니다.',
         'test-0012: 원문은 “6% (6 %)”입니다. 저장된 요청의 허용 숫자 목록에는 6이 한 개 남습니다. 두 표현을 모두 지우는 목적과 충돌합니다.',
         '집계는 삭제 대상과 같은 숫자가 보존 목록에 남은 후보 수입니다. 같은 숫자가 다른 사실인 경우도 있어 전부 동일 원인으로 확정하지 않습니다.')
category('G_NUM', 'Generation', '남겨야 할 숫자와 실제 편집 결과가 맞지 않습니다', '편집 계획·생성·검사 보완',
         '새 숫자를 넣은 경우뿐 아니라 연도·다른 금액을 빠뜨렸거나 같은 숫자의 개수가 달라도 멈춥니다. 오류 이름만으로 숫자를 지어냈다고 단정하면 안 됩니다.',
         '삭제 대상과 보존할 연도·금액을 원문 위치별로 표시하고, 문자 깨짐으로 생긴 숫자는 먼저 구별합니다.',
         '실제 편집 전후 숫자와 개수를 비교해 추가·누락·표기 차이를 따로 표시합니다. 검사 조건이 잘못됐으면 생성문 대신 계획·검사기를 고칩니다.',
         '이 분류는 전체 숫자 검사 실패 279유형 중 삭제 대상과 같은 숫자가 보존 목록에 남은 후보 40유형을 따로 뺀 239유형입니다.')
category('G_UNCHANGED', 'Generation', '값이나 관계를 바꿔도 최종 답이 달라지지 않습니다', '변형 대상 선택 보완',
         '답에 영향을 주지 않는 입력, 0인 값, 같은 값으로 돌아오는 계산, 마지막 반올림 등에서 현재 후보는 필요한 다른 답을 만들지 못합니다. 각 원인은 별도 확인이 필요합니다.',
         '각 입력을 바꾸었을 때 반올림 전후 답이 어떻게 달라지는지와 허용 범위를 제공합니다.',
         '처음 보이는 숫자를 고정 선택하지 말고 답에 영향을 주는 다른 입력·변경폭을 탐색합니다. 범위를 벗어난 과장된 수치로 억지로 통과시키지 않습니다.',
         '값 변경 276유형, 관계 변경 32유형이 답 불변으로 멈췄습니다. 출처 유형에도 같은 사전 계산 문제가 반복 기록되어 원인 문항 수와 같지 않습니다.')
category('G_QUESTION', 'Generation', '질문에 있는 숫자를 다음 단계에 전달하지 못했습니다', '단계 간 데이터 전달 보완',
         '계산에 쓰는 숫자의 출처가 질문인데, 다음 단계가 그 질문 문자열을 받지 못해 위치를 확인할 수 없었습니다. 원본에 질문이 없다는 뜻이 아닙니다.',
         '본문·질문·각 숫자의 출처 구분·정제 버전을 함께 전달해야 합니다.',
         '본문만 전달하는 경로를 고치고 질문 출처의 값도 끝까지 유지합니다. 본문 위치와 질문 위치를 서로 섞어 정렬하지 않습니다.',
         'test-0250: 저장된 실패는 질문 출처 문자열 누락입니다. 질문을 새로 작성할 일이 아니라 단계 사이 전달을 확인할 일입니다.')
category('G_CONTROL', 'Generation', '값을 지운 뒤 조건문·반복 계산을 표현하지 못합니다', '계산 표현·검사 지원 보완',
         '숫자가 있을 때는 계산되지만 값을 지운 상태의 조건문·반복문을 현재 프로그램이 지원하지 않아 멈춥니다. 자료 부족을 만들려던 작업이 프로그램 지원 범위에 걸린 것입니다.',
         '삭제된 입력을 미정인 값으로 남긴 계산 흐름과 조건에 따라 달라지는 결과를 제공합니다.',
         '미정 값을 포함한 계산·분기를 표현하도록 보완합니다. 프로그램이 실행되지 않는다는 사실만으로 답을 알 수 없는 문제라고 인증하지 않습니다.',
         'test-0003: 삭제형 두 유형이 이 단계에서 멈췄습니다. 현재 구현은 조건·반복 계산에 미정 입력이 있으면 명시적으로 중단합니다.')
category('G_DEP', 'Generation', '앞에서 만들 충돌 문장이 통과하지 못했습니다', '앞 단계 수정 + 후속 재개',
         '출처를 붙이는 유형은 먼저 검증된 충돌 문장이 있어야 합니다. 앞 단계가 없거나 실패하면 후속 생성도 멈춥니다.',
         '같은 문항·같은 실행에서 통과한 앞쪽 또는 뒤쪽 충돌 본문과 그 판정 기록을 제공합니다.',
         '출처 문장을 새로 꾸미기 전에 연결된 값 변경 유형의 실패 원인을 해결합니다. 후속 정지는 별도 원본 결함으로 중복 계산하지 않습니다.',
         '검증된 충돌 본문이 없어 막힌 기록 116개와 선행 문장이 없어 막힌 기록 12개를 묶었습니다.')
category('G_INQUESTION', 'Generation', '본문에서 지워도 질문에 같은 숫자가 남습니다', '대상 선택·동일 사실 판별 보완',
         '질문은 고정한 채 본문만 지우려는데 질문에도 같은 숫자가 있어 삭제 후보가 차단됐습니다. 현재 비교는 숫자 겹침이어서 같은 사실인지까지 보장하지 않습니다.',
         '본문·질문에서 같은 사실을 가리키는 모든 위치와 값의 역할을 제공합니다.',
         '단순 숫자 일치 대신 같은 사실인지 확인하고 질문에 없는 다른 필수값을 선택합니다. 실제 필수값이 질문에 고정되어 있다면 그 값은 본문 삭제 대상으로 쓸 수 없습니다.',
         '109유형이 이 조건으로 차단됐습니다. 이 수가 모두 답 노출 확정 건수인 것은 아닙니다.')
category('G_SECOND', 'Generation', '두 번째로 지울 입력을 찾지 못했습니다', '입력 목록·유형 적용 가능성 확인',
         '현재 풀이에 등록된 입력이 하나뿐인데 두 번째 입력을 지우는 유형까지 요구했습니다. 원문 전체에도 반드시 값이 하나뿐이라는 뜻은 아닙니다.',
         '답에 실제로 필요한 입력 목록과 각 입력의 원문 위치를 제공합니다.',
         '누락된 필수 입력이 있으면 추출을 보완합니다. 실제로 하나만 필요한 문제라면 없는 두 번째 입력을 만들지 말고 유형 적용 기준을 별도로 결정합니다.',
         'test-0001: 두 번째 삭제 대상이 없어 생성 이전에 멈췄습니다. 문장을 다시 써 달라는 재시도로 해결되지 않습니다.')
category('G_INTENT', 'Generation', '문장을 바꿨지만 원하는 문제가 만들어지지 않았습니다', '변형 계획·문장 생성 보완',
         '삭제한 값이 다른 곳에 남거나, 충돌시킬 대상·기간·관계·출처가 계획과 달라 검토에서 거절됐습니다. 세부 원인은 문항별 저장 근거에서 확인합니다.',
         '대상 금액의 회사·기간·단위, 반복 등장 위치, 관련 합계·다른 풀이 경로, 출처를 붙일 한 주장을 명시합니다.',
         '삭제는 같은 사실의 반복과 답을 복원하는 경로까지 조사합니다. 값 충돌은 동일 대상에 대한 두 주장인지, 출처는 지정한 한 주장에만 붙는지 확인합니다.',
         'test-0004의 두 번째 삭제형: 표의 99를 지웠지만 반복된 잔액 행과 2008년 말 금액 설명에 99가 남았습니다.')
category('G_READ', 'Generation', '삭제·추가 후 문장이나 표가 깨졌습니다', '문장 경계·편집 방식 보완',
         '숫자 위치만 지우거나 문장을 부적절한 위치에 끼워 넣어 문법·표 구조가 깨졌습니다.',
         '편집할 문장·표 셀의 경계와 유지해야 할 주변 문맥을 제공합니다.',
         '표는 셀만 편집하고 산문은 금액을 지운 뒤 문법을 최소한으로 잇습니다. 원래부터 깨진 문장과 이번 편집으로 깨진 문장을 나누어 검사합니다.',
         'test-0009의 두 번째 삭제형: “the remaining .”처럼 금액을 뺀 자리의 문장이 미완성으로 남았습니다.')
category('G_EXTRA', 'Generation', '바꾸지 말아야 할 내용까지 바뀌었습니다', '편집 범위·검사 보완',
         '목표 이외의 값·대상·조건이 변해 한 종류의 변화만 비교하기 어려워졌습니다.',
         '바꿀 부분과 반드시 유지할 부분을 구절 단위로 제공합니다.',
         '수정 범위를 좁히고 편집 전후를 비교합니다. 관련 없는 문장을 통째로 다시 쓰게 하지 않습니다.', '저장된 의미 검사에서 24유형이 이 사유로 남았습니다.')
category('G_FORMAT', 'Generation', '제작용 표시나 편집 형식이 최종 문장에 남았습니다', '생성 형식·검사 규칙 보완',
         '내부 이름, 대괄호 표시, 출처 괄호, 수정 위치 등의 형식 조건을 충족하지 못했습니다. 정상적인 원문 괄호까지 잡았는지도 구별해야 합니다.',
         '사람에게 보여줄 문장과 내부 관리 정보를 별도 칸에 제공하고 수정 위치는 프로그램이 관리합니다.',
         '내부 표시는 최종 본문에 넣지 않도록 분리합니다. 대괄호 전부를 일괄 금지하기보다 실제 내부 표시인지 확인하고 형식은 가능하면 프로그램에서 조립합니다.', '제작 표시 검사 33유형을 포함합니다. 현재 검사는 일반 대괄호 표현도 잡을 수 있어 전부 내부 정보 노출로 단정하지 않습니다.')
category('G_EXEC', 'Generation', '바꾼 값으로 계산하는 과정이 멈췄습니다', '변형값 범위·계산 지원 보완',
         '변경 후보를 넣은 계산이나 계산 연결을 만들지 못했습니다. 오류 이름만으로 0 나누기 등 한 원인으로 단정할 수 없습니다.',
         '허용되는 값의 범위와 실행 실패의 구체적 연산·입력을 제공합니다.',
         '단위·범위·수학적 조건을 만족하는 후보를 고르고 실제 실패 위치를 남깁니다. 같은 실패 후보를 반복하지 않습니다.', '계산 실행 실패 22유형과 답에 연결되지 않은 입력 1유형입니다.')
category('G_TRANSPORT', 'Generation', '연결이 끊기거나 응답이 불완전했습니다', '실행·재시도 관리',
         '생성 또는 검증 응답을 확보하지 못했습니다. 데이터 제공 방식의 개선만으로 막을 수 있는 문제가 아닙니다.',
         '원래 요청과 완료 여부, 수신한 원응답을 보존합니다.',
         '통신 실패를 내용 실패와 분리해 해당 호출만 재개합니다. 검증 응답이 없으면 통과 처리하지 않습니다.', '연결 실패 65유형, 불완전 응답 8유형입니다.')
category('G_STORAGE', 'Generation', '저장하려는 위치에 이전 파일이 있어 멈췄습니다', '결과 저장·재개 방식 보완',
         '재사용 기록을 만들려는 위치에 파일이 이미 있어 새 기록을 저장하지 못했습니다. 문장이나 원본 데이터의 오류가 아닙니다.',
         '시도별 저장 위치, 기존 결과의 소유 작업과 완료 상태를 제공합니다.',
         '시도마다 고유한 저장 위치를 사용하고 이미 완료된 기록은 확인 후 재사용합니다. 이전 결과를 무조건 덮어쓰거나 지우지 않습니다.',
         'test-0259·0276·0292·1850의 값 변경 유형은 기존 reuse.json과 저장 위치가 겹쳐 멈췄습니다.')
category('G_UNKNOWN', 'Generation', '검토가 완료되지 않아 최종 판정을 남기지 못했습니다', '검토 완료 확인 + 문장 대상 명확화',
         '세 유형은 최종 미평가로 남았습니다. 검토 결과가 없다는 기록과 문장의 대상·기간이 불분명하다는 지적이 섞여 있으므로 모두 통신 실패로 보지 않습니다.',
         '추가한 값이 어느 항목·기간을 뜻하는지 명확한 문장과 실제 검토 완료 결과를 제공합니다.',
         'test-0034는 검토 완료 여부를 확인합니다. test-0165는 어느 연체 구간인지, test-0867은 어느 분기인지 문장을 명확히 한 뒤 검토합니다. 기존 미평가 표시는 보존합니다.',
         'test-0867: 원문은 네 분기의 배당 목록인데 추가 문장은 단지 “어느 분기의 배당”이라고 해 같은 분기의 충돌인지 확인하지 못했습니다.')


REVIEW_GROUPS = {
    'P_PERIOD': '0022 0079 0372 0399 0659 0796 0815 1250 1254 1292 1326 1365 1453 1550 1998 2015',
    'P_MISSING': '0029 0315 0394 0430 0477 0623 0642 0655 0772 0852 1343 1493 1499 1523 1530 1544 1570 1659 1721 1754 1766 1854 1906 1950 2043 2046 2049',
    'P_MEASURE': '0143 0214 0226 0252 0504 0658 0700 0709 0828 0898 1351 1429 1620 1874',
    'P_CONVENTION': '0914 0965 1062 1190 1398 1432 1441 1875 1920 1934 1977 2002',
    'P_SCALE': '0055 0290 0320 0395 0403 0552 0883 1517 1548 1584 1878 1958 2042',
    'P_TEXT': '0063 0229',
}
REVIEW_IDS = {f'test-{i}': group for group, ids in REVIEW_GROUPS.items() for i in ids.split()}


def prep_group(error, evidence):
    code = error['code']
    if code == 'ORIGINAL_REVIEW_NOT_PASSED':
        return REVIEW_IDS[error['case']]
    if code == 'VERIFICATION_FAILED_OR_UNKNOWN':
        findings = evidence.get('verdict', {}).get('findings', [])
        if any(x.get('judgment') == 'FAIL' for x in findings): return 'P_VERIFY_FAIL'
        if any(x.get('judgment') != 'PASS' for x in findings): return 'P_VERIFY_UNCERTAIN'
        if findings: return 'P_GOLD'
        raise ValueError('Missing verification findings')
    if code == 'NUMERIC_ANSWER_REQUIRED': return 'P_NOANSWER'
    if code == 'FACT_NUMERIC_TOKEN_REQUIRED': return 'P_NUMBER'
    if code.startswith('API_'): return 'P_TRANSPORT'
    if code == 'AMBIGUOUS_SOURCE_REVISION_ANCHOR': return 'P_TEXT'
    if code == 'QUESTION_PRECISION_INSTRUCTION_REMOVED_OR_ADDED': return 'P_SCALE'
    if code == '상세 검사 실패': return 'P_CODE'
    return 'P_LINK'


GEN_GROUPS = {
    'UNPLANNED_NUMERIC_CONTENT': 'G_NUM', 'FINAL_ANSWER_UNCHANGED': 'G_UNCHANGED',
    'RELATION_ANSWER_UNCHANGED': 'G_UNCHANGED', 'planned_change': 'G_INTENT', 'readability': 'G_READ',
    'FACT_SOURCE_MISSING': 'G_QUESTION', 'GRAPH_CONTROL_FLOW_MISSING_FACTS': 'G_CONTROL',
    'AUDITED_VALUE_DEPENDENCY_REQUIRED': 'G_DEP', 'VALUE_BEFORE_GENERATION_REQUIRED': 'G_DEP',
    'EA_VALUE_PRESENT_IN_QUESTION': 'G_INQUESTION', 'MISSING_SECOND_EA_INPUT': 'G_SECOND',
    'unintended_change': 'G_EXTRA', 'BRANCH_EXECUTION_FAILED': 'G_EXEC',
    'FACT_NOT_CONNECTED_TO_ANSWER': 'G_EXEC', 'API_CONNECTION_FAILED': 'G_TRANSPORT',
    'API_RESPONSE_INCOMPLETE': 'G_TRANSPORT', '상세 검사 실패': 'G_UNKNOWN',
    'NOT_EVALUATED': 'G_UNKNOWN',
    **{x: 'G_FORMAT' for x in ['CONSTRUCTION_TAG_IN_CONTEXT','UNAUTHORIZED_PATCH_OR_GRAPH_MAPPING',
       'PARENTHESIZED_SOURCE_REQUIRED','PYTHON_IDENTIFIER_IN_CONTEXT','STANDALONE_SENTENCE_REQUIRED','INSERTION_NEEDS_SEPARATOR']},
}


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prep = read(SOURCE / 'phase-reports/preparation/data.json')
    gen = read(SOURCE / 'phase-reports/generation/data.json')
    latest = read(SOURCE / '02-generation/summary.json')['latest']
    rows = []
    sample_refs = {}
    for case in sorted(set(latest) | {e['case'] for e in prep['errors']}):
        folder = SOURCE / '01-preparation' / case
        candidates = list(folder.glob('01-round/01-source/01-receive-input/01-input.json'))
        refs = []
        for path in candidates:
            read(path); refs.append(str(path.relative_to(ROOT)))
        sample_refs[case] = refs
    for error in prep['errors']:
        file = SOURCE / error['source']
        run = read(file)
        evidence = {'run': run}
        refs = [str(file.relative_to(ROOT)), *sample_refs[error['case']]]
        paths = {'review': '02-review/02-LLM-review-original/03-result.json',
                 'verdict': '05-verification/08-record-verdict/01-result.json',
                 'calculation': '03-calculation/02-LLM-generate-code/03-result.json',
                 'execution': '03-calculation/04-execute-python/03-result.json',
                 'sample': '01-source/01-receive-input/01-input.json'}
        for key, relative in paths.items():
            path = file.parent / relative
            if path.exists():
                evidence[key] = read(path); refs.append(str(path.relative_to(ROOT)))
        top = read(SOURCE / '01-preparation' / error['case'] / 'run.json')
        refs.append(str((SOURCE / '01-preparation' / error['case'] / 'run.json').relative_to(ROOT)))
        evidence['recovery'] = top.get('recovery', {})
        group = prep_group(error, evidence)
        rows.append(dict(phase='Preparation', case=error['case'], type='원문 준비', status='FAIL',
                         group=group, classification_code=error['code'], refs=refs, evidence=evidence))
    failing = {(e['case'], e['category']): e for e in gen['errors']}
    clean = []
    numbers = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['numbers']).numbers
    for case, variants in latest.items():
        if len(variants) == 7 and all(v['status'] == 'PASS' for v in variants.values()):
            clean.append(case)
        for variant in variants.values():
            if variant['status'] == 'PASS': continue
            error = failing.get((case, variant['label']), {})
            code = error.get('code', variant['status'])
            group = GEN_GROUPS[code]
            file = SOURCE / variant['path'] / 'run.json'
            saved = read(file)
            if code == '상세 검사 실패' and str(saved.get('reason', '')).startswith('FileExistsError:'):
                group = 'G_STORAGE'
            refs = [str(file.relative_to(ROOT)), *sample_refs[case]]
            plan = saved.get('plan', {})
            request = plan.get('request', {})
            numeric_collision = False
            if code == 'UNPLANNED_NUMERIC_CONTENT' and request.get('axis') == 'EA':
                target = plan.get('intent', {}).get('target_original', {})
                target_numbers = set(numbers(target.get('text', '')))
                numeric_collision = any(target_numbers & set(numbers(' '.join(slot.get('allowed_numbers', []))))
                                        for slot in request.get('edit_slots', []))
                if numeric_collision: group = 'G_NUM_DUP'
            evidence = dict(reason=saved.get('reason'), recovery=saved.get('recovery', {}),
                            edit_slots=request.get('edit_slots', []), question=request.get('question'),
                            target=plan.get('intent', {}).get('target_original'), numeric_collision_candidate=numeric_collision)
            for relative in ['02-generate-text/01-input.json','02-generate-text/failure.json','03-validation/03-result.json','01-perturbation/failure.json']:
                p = file.parent / relative
                if p.exists():
                    read(p); refs.append(str(p.relative_to(ROOT)))
            rows.append(dict(phase='Generation', case=case, type=variant['label'], status=variant['status'],
                             group=group, classification_code=code, refs=refs, evidence=evidence))
    for relative in ['src/finarch/dataset/02-generation/01-perturbation/generation_plan.py',
                     'src/finarch/dataset/02-generation/02-generate-text/dtt_realize.py',
                     'src/finarch/dataset/shared/calculation/python_graph.py',
                     'src/finarch/dataset/shared/calculation/python_runtime.py']:
        INPUTS[relative] = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    for row in rows:
        row['refs'] = list(dict.fromkeys(row['refs']))
    for item in CAT.values():
        chosen = [r for r in rows if r['group'] == item['id']]
        item['count'] = len(chosen)
        item['cases'] = len({r['case'] for r in chosen})
        item['types'] = dict(collections.Counter(r['type'] for r in chosen))
    counts = collections.Counter(r['phase'] for r in rows)
    gen_cases = sorted({r['case'] for r in rows if r['phase'] == 'Generation'})
    assert counts == {'Preparation': 212, 'Generation': 1667}, counts
    assert len(clean) == 1080 and len(gen_cases) == 758
    assert len({(r['phase'], r['case'], r['type']) for r in rows}) == len(rows)
    assert sum(x['count'] for x in CAT.values()) == len(rows)
    summary = dict(kind='FAILURE_CAUSE_REVIEW', title='FinanceReasoning 실패 원인·개선안',
                   preparation_failed=212, generation_nonclean_cases=758, generation_failed=1664,
                   generation_not_evaluated=3, clean_cases=1080, source_run=SOURCE.name)
    payload = dict(summary=summary, categories=list(CAT.values()), rows=rows,
                   generation_types=gen['summary'], nonclean_cases=gen_cases, clean_cases=clean,
                   method='Saved final-state census; editorial categories; saved model judgments are not ground truth; no model calls or production reruns.')
    save('failure-review.json', payload)
    save('summary.json', summary)
    report = report_text(payload)
    (OUTPUT / 'REPORT.md').write_text(report)
    template = Path(__file__).with_name('failure-review-readme-template.md').read_text()
    (OUTPUT / 'README.md').write_text(template.format(source_run=SOURCE.name, report_run=OUTPUT.name))
    save('validation.json', dict(status='PASS', rows=len(rows), preparation=counts['Preparation'],
         generation=counts['Generation'], nonclean_cases=len(gen_cases), clean_cases=len(clean),
         duplicates=0, unclassified=0, evidence_files=len(INPUTS), model_calls=0,
         scope='Counts, classification coverage and evidence availability only; no semantic certification.'))
    save('manifest.json', dict(inputs=[dict(path=p, sha256=h) for p,h in sorted(INPUTS.items())]))
    (OUTPUT / 'analysis-log.jsonl').write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in [
        dict(event='read_saved_evidence', files=len(INPUTS), source_run=SOURCE.name),
        dict(event='reconcile_final_population', preparation_failed=212, generation_failed=1664, generation_not_evaluated=3, clean=1080, nonclean=758),
        dict(event='write_editorial_review', rows=len(rows), categories=len(CAT), model_calls=0, production_changes=0)
    ]) + '\n')
    print(json.dumps(summary, ensure_ascii=False))


def report_text(payload):
    category_counts = collections.Counter(row['group'] for row in payload['rows'])
    generation_types = (
        ('IC_VALUE_01_BEFORE', 'IC-v1', '앞쪽에 다른 값 주장 추가'),
        ('IC_VALUE_01_AFTER', 'IC-v2', '뒤쪽에 다른 값 주장 추가'),
        ('IC_SOURCE_A_ONLY', 'IC-s1', '원래 주장에 출처 부착'),
        ('IC_SOURCE_B_ONLY', 'IC-s2', '추가 주장에 출처 부착'),
        ('IC_RELATION_01', 'IC-r', '서로 맞지 않는 관계 추가'),
        ('EA_01', 'EA-v1', '첫 번째 필수값 삭제'),
        ('EA_02', 'EA-v2', '두 번째 필수값 삭제'),
    )
    type_names = {code: name for code, name, _ in generation_types}
    stage_order = {
        'Preparation': {
            '02-review': 'P02 원문 검토',
            '03-calculation': 'P03 풀이 생성·실행',
            '04-graph': 'P04 계산 그래프',
            '05-verification': 'P05 종합 검증',
        },
        'Generation': {
            '01-perturbation': 'G01 변형 계획',
            '02-generate-text': 'G02 문장 생성',
            '03-validation': 'G03 완성문 검증',
        },
    }
    stages = {phase: collections.defaultdict(list) for phase in stage_order}
    for row in payload['rows']:
        phase = row['phase']
        if phase == 'Preparation':
            stage = row.get('evidence', {}).get('run', {}).get('stopped_at')
        else:
            saved = json.loads((ROOT / row['refs'][0]).read_text())
            stage = saved.get('restart')
        if stage not in stage_order[phase]:
            raise ValueError(f'UNMAPPED_FAILURE_STAGE:{phase}:{row["case"]}:{stage}')
        stages[phase][(stage, row['group'])].append(row)

    def stage_table(phase):
        lines = []
        for stage, label in stage_order[phase].items():
            for category in CAT.values():
                if category['phase'] != phase:
                    continue
                records = stages[phase].get((stage, category['id']), [])
                if not records:
                    continue
                values = [label, category['title'], str(len(records))]
                if phase == 'Generation':
                    counts = collections.Counter(row['type'] for row in records)
                    unknown = set(counts) - set(type_names)
                    if unknown:
                        raise ValueError(f'UNMAPPED_GENERATION_TYPE:{sorted(unknown)}')
                    values.append(' · '.join(
                        f'{type_names[code]} {counts[code]}'
                        for code, _, _ in generation_types if counts[code]))
                    values.append(str(len({row['case'] for row in records})))
                values.append(category['owner'])
                lines.append('|' + '|'.join(values) + '|\n')
        if sum(len(records) for records in stages[phase].values()) != sum(
                row['phase'] == phase for row in payload['rows']):
            raise ValueError('FAILURE_STAGE_COUNT_MISMATCH:' + phase)
        return ''.join(lines)

    text = '''# FinanceReasoning 20260917-002: 실패 원인과 개선안

가장 먼저 구분할 것은 **원문에 필요한 정보가 없는 문제**와 **있는 정보를 프로그램이 제대로 넘기거나 편집하지 못한 문제**입니다. 둘을 같은 데이터 불량으로 처리하면 원인을 고치기 어렵습니다.

## 분석 범위와 읽는 법

Preparation의 입력은 2,050문항입니다. 이 가운데 212문항이 제외되고 1,838문항이 통과해 Generation으로 넘어갔습니다. Generation에서는 1,838문항 중 1,080문항이 일곱 유형 모두 통과했고, 758문항은 한 유형 이상 실패하거나 미평가됐습니다.

Generation 전체의 검사 단위는 **문항 × 유형**으로, 1,838 × 7 = 12,866개입니다. 모두 통과한 1,080문항에서는 1,080 × 7 = 7,560개 유형이 통과했습니다. 나머지 758문항의 758 × 7 = 5,306개 결과는 **통과 3,639개 + 실패 1,664개 + 미평가 3개**입니다. 즉 1,664와 3은 문항 수가 아니라 유형별 결과 수입니다. 한 문항에서 여러 유형이 실패할 수 있고, 같은 문항의 다른 유형은 통과할 수도 있습니다. 준비 실패 212문항은 Generation에 들어가지 않았습니다.

입력 전 제외된 188문항은 이번 212문항에 포함하지 않습니다. 차수별 이전 실패 뒤 최종 통과한 건도 최종 실패 수에 다시 넣지 않습니다. clean pass는 저장된 자동 검사 기준이며 의미 정답을 사람이 확정했다는 뜻이 아닙니다.

아래 분류는 원문 준비는 문항당 하나, 생성은 문항×유형당 하나의 주된 관찰 원인입니다. 여러 문제가 겹칠 수 있고 범주별 원문 수는 서로 겹칩니다. 저장된 검토기 설명은 근거 자료이지 확정 사실이 아닙니다. 특히 관례·모호성·검사기 오류 주장은 원문과 맞춰 판단해야 합니다.

## 먼저 바꾸면 좋은 순서

1. **자료를 그대로 옮기는 부분부터 고칩니다.** 본문과 질문을 함께 넘기고, 숫자의 원문 위치와 정제 버전을 유지합니다. 문자로 쓴 수량도 처리합니다.
2. **생성 전에 이 문항으로 각 유형을 만들 수 있는지 확인합니다.** 실제 답을 바꾸는 입력인지, 지울 두 번째 입력이 있는지, 질문에 같은 사실이 남는지 확인합니다.
3. **무엇을 지우고 무엇을 남길지 한 계획으로 맞춥니다.** 같은 사실의 반복을 모두 조사하고 편집 계획·문장 생성·숫자 검사가 같은 목록을 사용하게 합니다.
4. **필요한 정보가 없는 원문을 보완합니다.** 해당 연도·회사·단위·필요 수치를 출처에서 확인하고 버전별 정정 내역을 남깁니다.
5. **검토가 지나치게 엄격하거나 서로 모순되는 부분을 줄입니다.** 허용할 금융 관례·반올림을 먼저 정하고, 저장 정답과 다르다는 이유만으로 원문이나 계산을 고치지 않습니다.
6. **통신 실패는 따로 재개합니다.** 내용 보완 횟수와 섞지 않고, 이미 통과한 결과는 보존합니다.

이 순서는 개선 제안입니다. 이번에는 제작 코드·원문·정답을 바꾸거나 새 모델 호출을 하지 않았으므로 개선 후 통과 건수는 아직 알 수 없습니다.

## Preparation: 원본을 바꿔야 하나요, 정제를 바꿔야 하나요?

원본 전체를 교체해야 한다는 결론은 아닙니다. 빠진 정보는 출처에서 보완해야 하지만, 숫자 표현·인용 위치·통신·전달 문제는 처리 과정에서 고칠 수 있습니다. 검토가 해석을 확정하지 못한 건은 원본 오류로 일괄 계산하지 않습니다.

아래 구간은 최종 상태를 대표하는 시도에서 실패가 기록된 위치입니다. 실제 수정 책임은 오른쪽 열과 문항별 근거를 함께 확인해야 합니다. 같은 원인 분류가 여러 구간에 걸치면 구간별 행으로 나눕니다.

|구간|원인 분류|문항 수|먼저 손볼 곳|
|---|---|---:|---|
'''
    text += stage_table('Preparation')
    text += '\n### Preparation 세부내역\n'
    for c in CAT.values():
        if c['phase'] == 'Preparation': text += detail(c, category_counts[c['id']])
    text += '''
## Generation: 일곱 유형별로 보면 무엇이 막혔나요?

|type|만들려던 유형|통과|실패|미평가|
|---|---|---:|---:|---:|
'''
    type_summaries = {row['category']: row for row in payload['generation_types']}
    if set(type_summaries) != set(type_names):
        raise ValueError('GENERATION_TYPE_SUMMARY_MISMATCH')
    for code, name, meaning in generation_types:
        row = type_summaries[code]
        text += f"|{name}|{meaning}|{row['PASS']}|{row['FAIL']}|{row['NOT_EVALUATED']}|\n"
    text += '''
type 이름은 이 보고서와 뷰어의 표시명입니다. 저장된 제작 type 코드는 바꾸지 않았습니다.

같은 원문에서 값 변경이 실패하면 출처 유형도 막힐 수 있습니다. 따라서 출처 유형 실패를 모두 출처 문장 자체의 문제로 해석하면 안 됩니다. 삭제형은 값이 다른 곳에 남는 문제뿐 아니라, 미정 값을 계산 프로그램이 다루지 못하는 문제도 있습니다.

아래 구간은 최종 상태를 대표하는 시도의 중단 위치입니다. `발생 type`의 숫자를 합하면 해당 행의 실패·미평가 유형 수가 됩니다. 선행 유형 실패의 영향은 별도 원본 결함으로 해석하지 않습니다.

|구간|원인 분류|실패·미평가 유형 수|발생 type (건수)|해당 원문 수|먼저 손볼 곳|
|---|---|---:|---|---:|---|
'''
    text += stage_table('Generation')
    text += '\n### Generation 세부내역\n'
    for c in CAT.values():
        if c['phase'] == 'Generation': text += detail(c, category_counts[c['id']])
    text += '''
## 데이터가 어떻게 제공됐어야 하나요?

원문 한 건마다 **질문·본문 → 필요한 값과 뜻 → 계산 → 허용할 변경 → 같은 사실의 다른 위치**가 이어져야 합니다. 예를 들어 매출 100이 표와 설명 문장에 모두 있으면 두 위치가 같은 매출이라는 표시가 필요합니다. 한쪽만 지우면 정보 부족 문제가 되지 않습니다. 반면 날짜 100이나 다른 항목의 100까지 지우면 엉뚱한 내용이 바뀝니다.

|제공할 내용|작은 예|막으려는 문제|
|---|---|---|
|값의 뜻과 출처|2019년 A회사 매출 100, 백만 달러, 본문 표 2행|다른 회사·기간·단위 혼동|
|질문과 본문을 함께 전달|질문에 있는 만기 5년도 원문 위치와 함께 전달|질문 출처 유실|
|출처로 확인된 정제 대응|four → 4, 원문은 보존|숫자 표현 거절·위치 어긋남|
|계산 기준|증감은 뒤 기간−앞 기간, 출력은 %p|부호·백분율·자릿수 혼동|
|변경 가능한 값과 범위|양수 금액, 변경 후 답이 실제 달라짐|답이 그대로이거나 실행 불가|
|반복된 같은 사실의 위치|표의 매출 100과 본문의 동일 매출 100|하나만 삭제하거나 보존 규칙 충돌|
|연결된 합계·다른 계산 경로|전체 150과 다른 부분 50으로 삭제한 100을 복원 가능|삭제해도 답을 구할 수 있음|
|통과한 선행 본문|앞쪽·뒤쪽 충돌 문장별 검증 결과|출처 유형의 선행 입력 부재|

### 종합 세부내역

#### 채택 판단과 확인할 최소 범위

**채택:** 원문·질문 동시 전달, 위치 대응 유지, 같은 사실의 반복 위치 관리, 통신 실패 분리. 확인 방법은 대표 원기록을 넣어 누락 없이 이어지는지 보는 작은 로컬 검사입니다.

**수정 채택:** 원본 질문의 조건 명시와 변형 대상 선택 개선. 실제로 모호한 경우만 명확화하고 금융 관례가 충분한 경우까지 원본을 억지로 늘리지 않습니다. 변경 전후 의미와 결과를 함께 확인해야 합니다.

**보류:** 현재 실패한 모든 문항을 일곱 유형 모두 통과하도록 만드는 목표. 실제 필요한 입력이 하나뿐인 문항은 두 번째 삭제형의 의미부터 정해야 하며, 데이터를 꾸며 넣어 달성해서는 안 됩니다.

**기각:** 오류 이름만 보고 원본 불량으로 판정하기, 저장 정답에 맞게 수치를 바꾸기, 검사를 느슨하게 만들어 통과 수만 늘리기. 이렇게 하면 제작 품질을 확인할 수 없습니다.

#### 근거와 한계

문항별 원문, 최종 판정, 당시 검토·계산 결과, 생성 요청과 실패 기록은 공통 뷰어의 근거 버튼으로 확인할 수 있습니다. 전체 파일 해시는 manifest.json에 있습니다. 범주별 설명은 관찰된 실패 구조를 설명하며 모든 문항의 금융적 정답을 독립적으로 다시 증명한 결과는 아닙니다.

현재 코드에서 질문 출처 검사, 삭제 시 숫자 개수 검사, 미정 입력의 조건·반복 계산 중단을 확인했습니다. 현재 코드를 당시 실행 코드와 동일하다고 가정하지 않고, 당시 저장된 요청·결과와 맞는 범위에서만 사용했습니다. 예를 들어 test-0012의 중복 6은 당시 요청 자체에 남아 있어 코드 변경 이력과 무관하게 확인할 수 있습니다.
'''
    return text


def detail(c, count):
    return f"\n#### {c['title']} ({count}건)\n\n왜 멈췄나요? {c['why']}\n\n어디를 고치나요? {c['owner']}\n\n어떤 자료를 주어야 하나요? {c['supply']}\n\n어떻게 개선하나요? {c['fix']}\n\n실제 기록 예: {c['example']}\n\n판단 범위: {c['confidence']}\n"


if __name__ == '__main__':
    main()
