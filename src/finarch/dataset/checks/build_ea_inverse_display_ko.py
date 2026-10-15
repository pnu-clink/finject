"""Create snapshot-bound Korean display strings without changing English records."""
import collections
import hashlib
import json
import re
from pathlib import Path

REASONS = '''
남은 Q/C의 정확한 합계·소계, 잔액 변동, 같은 값의 재기재, 전체를 빠짐없이 나눈 비중, 비율 또는 성장식 중 필요한 수량을 유일하게 정하는 관계가 확인되지 않았습니다. 다른 기간의 값, 무관한 수량, 반올림된 비율, 명시되지 않은 전체 범위로는 유일한 대체값을 정할 수 없습니다.
남은 Q/C에 필요한 피연산자와 해당 합계·조정·정의 관계가 명시되어 있습니다. 이 계산으로 누락 수량이 유일하게 결정됩니다.
나열된 구성 항목들이 이 표의 합계를 이룹니다. 소계를 중복하여 더하지 않습니다.
기초 잔액에 중간 변동을 부호에 맞게 더하면 기말 잔액이 됩니다.
행 이름에 적용할 회계 관계가 명시되어 있습니다.
수정 금액 = 잠정 금액 + 측정기간 조정액입니다.
질문과 공통형 손익계산서는 각 항목을 매출액 대비 비율로 나타냅니다. 매출액을 매출액으로 나누면 100%입니다.
같은 기간의 분자와 분모가 남아 있으므로 명시된 주당 값 또는 매출총이익률의 정의로 누락 비율을 정할 수 있습니다. 이 표의 표시 정밀도로 반올림합니다.
당기 금액 = 전기 금액 + 명시된 절대 변동액입니다.
남은 Context는 표의 기준일에 이 주식에 $100을 투자했다고 명시합니다. 따라서 누락된 초기 지수값은 100입니다.
같은 Context에 해당 기준일의 초기 투자금이 $100이라고 다시 명시되어 있습니다.
명시된 장부금액에서 순실현가능가치를 빼면 해당 자산의 감액 손실이 유일하게 결정됩니다.
전기 금액 = 당기 금액 - 명시된 절대 변동액입니다.
기초·기말 잔액의 연속성을 적용하면 직전 3월 31일 잔액인 3,104,563이 후보입니다. 그러나 같은 기간의 부호 있는 변동과 표시된 기말 수량 2.978478을 사용하면 다른 기초 잔액이 나옵니다. 남은 Q/C의 수량이 충돌하므로 일관된 하나의 복원값을 정할 수 없습니다.
2018년 기말 잔액과 2018년의 모든 부호 있는 변동이 남아 있어 기초 잔액을 정할 수 있습니다. 표기가 잘못된 2019년 기말 수량은 이 계산에 사용하지 않습니다.
초기 순외국자산(NFA) 총액과 특정 외화에 노출된 자산·부채가 같은 전체 범위인지는 확인되지 않습니다. 이 외화 노출이 모든 외국 자산·부채라는 설명이 없으므로 삭제된 입력을 유일하게 복원할 수 없습니다.
변동 열의 단위가 명시되지 않았습니다. -190을 베이시스포인트로 해석하려면 명시되지 않은 배율을 가정해야 하고, ROFE의 평균 투하자금 기준도 불명확합니다. 따라서 누락 비율을 유일하게 정할 수 없습니다.
지급 현금에는 프리미엄과 이연 금융비용 효과가 포함됩니다. 두 날짜의 어음 잔액만으로는 다른 발행·상환 가능성을 배제할 완전한 원금 변동 내역을 알 수 없어, 삭제된 원금이나 이전 잔액을 유일하게 정할 수 없습니다.
남은 Context에 해당 기간의 현금흐름과 전년 대비 절대 증가액 $794 million이 명시되어 있습니다. 두 값으로 누락된 인접 연도 현금흐름을 유일하게 복원할 수 있습니다.
남은 설명에서 같은 연도의 부동산 매출과 구조화금융 매출을 총매출의 전체 구성 항목으로 제시합니다.
남은 주택담보대출 조건에 수수료·추가 원금 상환을 제외한 완전 분할상환 및 고정 납입 일정이 명시되지 않았습니다. 이런 가정 없이 반올림된 월 납입액만으로 누락 원금이나 약정 이자율을 유일하게 정할 수 없습니다.
기본 주당순이익(EPS)은 순이익을 가중평균 보통주 수로 나눈 값입니다. 같은 기간의 두 값이 모두 남아 있어, 표의 소수 둘째 자리 정밀도로 누락 주당 값을 계산할 수 있습니다.
질문은 해당 부문이 정확히 이 다섯 회사로 구성된다고 명시합니다. 전체 시장점유율의 합은 100%이므로 나머지 네 비율로 누락 비율을 정할 수 있습니다.
남은 Context는 자본구조가 부채와 자기자본으로 빠짐없이 구성된다고 설명합니다. 두 배분 비율의 합은 100%입니다.
포트폴리오는 정확히 세 자산으로 구성됩니다. 전체 배분 비중의 합은 100%이고 다른 두 비중이 명시되어 있습니다.
명시된 포트폴리오는 정확히 이 세 자산으로 구성됩니다. 이 배분 비중들은 포트폴리오 전체를 이루며 합계가 100%입니다.
Context가 기록된 분기 양 끝점 사이의 선형 추세를 명시적으로 가정합니다. 누락된 중간 분기 값은 인접한 두 끝점 수익률의 중간값입니다.
연 1회 이자를 지급하는 액면가 국채에서 1년 현물금리는 1년 액면금리와 같습니다. 이전 이자를 단기 현물금리로 할인한 뒤 액면가격 식을 풀면 누락 현물금리가 유일하게 결정됩니다. 표시된 백분율의 소수 둘째 자리로 반올림합니다.
세전이익(EBT)에서 명시된 순금융손익을 빼면 EBIT가 713이지만, 개별 금융 항목을 빼면 714입니다. 표가 이 반올림 차이를 설명하지 않아 모든 남은 식이 지지하는 하나의 EBIT 표시값을 정할 수 없습니다.
남은 설명에 Vornado를 포함한 각 계열의 초기 투자금과 날짜가 명시되어 있습니다.
조정 EBITA를 매출액으로 나눈 값이 이 이익률의 정의입니다. 반올림 전 이익률은 유일하게 결정되며, 소수 첫째 자리로 약 4.7%입니다.
조정 EBITA를 매출액으로 나눈 값이 이 이익률의 정의입니다. 반올림 전 이익률은 유일하게 결정되며, 소수 첫째 자리로 약 5.3%입니다.
남은 설명에 이 성과 비교의 초기 투자금과 날짜가 다시 명시되어 있습니다.
연간 조정 내역에서 2017년 12월 31일 잔액은 같은 계정의 2018년 1월 1일 기초 잔액입니다.
예상 양의 수익에서 명시된 실제 음의 수익을 빼면 자산 수익의 부족분이 유일하게 결정됩니다.
총 금융리스 지급의무에는 이자가 포함되어 있고, 각주 [a]에는 같은 보고일의 금융리스 원금 $2,061 million이 별도로 명시되어 있습니다.
명시된 총 인수가격은 주식가치·현금·인수 부채·수수료의 합계입니다. 다른 세 항목을 빼면 주식가치를 복원할 수 있습니다.
순매출채권에 명시된 충당금을 더하면 22,445이지만, 두 충당금 구성 항목의 합 222를 사용하면 22,446입니다. 남은 Q/C에는 서로 불일치하는 복원 경로가 있어 하나의 명확한 금액을 정할 수 없습니다.
시장가격에서 행사가격을 빼면 상한을 적용하기 전 내재가치는 15입니다. Context는 내재가치에 상한이 있다고만 하고 상한값을 제시하지 않아 상한 적용 금액을 유일하게 추론할 수 없습니다.
명시된 최종 지급액까지 나열된 원금 상환이 발행분 전체를 이룹니다. 합계를 구하면 누락 원금을 복원할 수 있습니다.
바로 앞 문장에 같은 부채 금액과 날짜가 다시 명시되어 있습니다.
Context는 연말 현금흐름이 5년 연속 발생한다고 설명하고 2~5년 차를 명시합니다. 따라서 첫 연간 현금흐름은 1년 차이며 그 금액은 남아 있습니다.
같은 기간의 감소 항목이 설명되지 않은 이중 밑줄(__)로 남아 있습니다. 이를 0으로 정하는 값이나 정의가 없으며, 이 추가 미확정 변동 때문에 누락 기말 잔액을 유일하게 복원할 수 없습니다.
Context는 계약을 3-2-1 금리 할인(buydown)으로 명명하고 2·3년 차 할인폭을 2%·1%로 제시합니다. 이 순서로 1년 차 할인폭은 3 퍼센트포인트임을 알 수 있습니다.
Context에 5년 연속 연간 현금흐름과 2~5년 차 표시가 있어 첫 현금흐름의 시점은 1년 차로 유일하게 정해집니다.
채권 가격은 주어진 연간 현물 할인율을 적용한 전체 4년 현금흐름의 현재가치 합계와 같습니다. 알려진 후속 현재가치를 빼고 1년 차 할인을 되돌리면 누락 현금흐름을 구할 수 있습니다.
전체 4년 연간 내역에서 나머지 현금흐름이 2·3·4년 차로 명시되어 있으므로 첫 연간 현금흐름은 1년 차입니다.
두 번째 조건부 수익률 행에 같은 양호한 경제 시나리오의 확률 70%가 다시 명시되어 있습니다.
명시된 전체 누진 체계에서 다음 구간이 500,000 초과부터 시작하므로 첫 구간의 상한은 500,000입니다.
전체 정수 달러 누진 구간에서 두 번째 구간이 $10,001부터 시작합니다. 따라서 첫 구간의 상한은 $10,000입니다.
총액에서 다른 부문 잔액을 빼면 7,155이지만, 같은 행의 잔액 변동은 이전·기타 변동이 0일 때 5,424 + 1,758 = 7,182입니다. 남은 관계들이 충돌하여 누락 잔액을 유일하게 정할 수 없습니다.
총충당금에서 미배분 충당금을 빼면 176이지만, 총매출채권에서 순매출채권과 같은 미배분 충당금을 빼면 177입니다. 표가 불일치하여 누락 개별 충당금을 유일하게 정할 수 없습니다.
총매출채권에서 표시된 총충당금을 빼면 22,225이고, 표시된 충당금 구성 항목들을 빼면 22,224입니다. 합계들이 불일치하여 누락 순매출채권을 유일하게 복원할 수 없습니다.
같은 계정의 변동 내역에 직전 회계연도 기말 잔액 8,217이 명시되어 있어 바로 다음 기초 잔액을 정할 수 있습니다. 이 경로는 별도의 이중 밑줄(__) 변동을 0으로 취급하지 않습니다.
남은 각주는 Food Care의 과소계상이 Product Care $369.6 million과 미배분 자산 $3.3 million으로 상쇄되어 연결 자산에 영향이 없다고 명시합니다. 두 금액의 합이 누락 보정액입니다.
'''.strip().splitlines()

GLOSSARY = {
'common shareholders equity':'보통주 주주지분', 'allowance for doubtful accounts':'대손충당금',
'basic net income per share':'기본 주당순이익', 'net foreign exchange translation':'순외화환산액',
'net undesignated foreign-exchange derivative expense':'비지정 외환파생상품 순비용',
'unrecognized tax benefits':'미인식 세금혜택', 'asset impairment charge':'자산손상차손',
'debt carrying balance':'부채 장부잔액', 'retained-earnings adjustment':'이익잉여금 조정액',
'cumulative-effect':'누적효과', 'fully phased-in Basel III CET1':'완전 도입 기준 Basel III 보통주자본(CET1)',
'amortization and depreciation expense':'무형자산 상각 및 감가상각비', 'net ending goodwill':'기말 순영업권',
'adjusted EBITA margin':'조정 EBITA 이익률', 'deferred-compensation deferred-tax asset':'이연보상 관련 이연법인세자산',
'inventory deferred-tax asset':'재고 관련 이연법인세자산', 'raw materials inventory':'원재료 재고',
'total cost of revenue':'총매출원가', 'software maintenance revenue':'소프트웨어 유지보수 매출',
'software delivery/support/maintenance cost of revenue':'소프트웨어 제공·지원·유지보수 매출원가',
'statutory federal income tax rate':'법정 연방소득세율', 'total strategic/restructuring costs':'총전략·구조조정 비용',
'G&A expense movement':'일반관리비 변동', 'debt allocation':'부채 배분', 'equity allocation':'자기자본 배분',
'prepaid expenses':'선급비용', 'accrued receivables':'미수금', 'dilutive securities':'희석성 증권',
'number of options':'옵션 수', 'unvested share count':'미가득 주식 수', 'shares issuable on exercise':'행사 시 발행 가능한 주식',
'shares repurchased':'재매입 주식', 'shares purchased':'매입 주식', 'performance shares granted':'부여된 성과조건 주식',
'net deferred asset-return loss':'순이연 자산수익 손실', 'pension-plan':'연금제도',
'net revenues':'순매출', 'net revenue':'순매출', 'total consolidated revenues':'총연결매출',
'segment revenues':'부문 매출', 'development costs':'개발비', 'recorded investment':'기록된 투자액',
'total revenue':'총매출', 'service revenue':'서비스 매출', 'Appliances sales':'가전제품 매출',
'Total Other':'기타 합계', 'total Scope 1 and Scope 2 emissions':'Scope 1·2 총배출량',
'capital lease obligations':'금융리스 의무', 'capital lease':'금융리스',
'goodwill':'영업권', 'net income':'순이익', 'income taxes':'법인세', 'total assets':'총자산',
'net assets':'순자산', 'total liabilities':'총부채', 'net sales':'순매출액',
'cash and cash equivalents':'현금 및 현금성자산', 'cash flow':'현금흐름',
'operating activities':'영업활동', 'investing activities':'투자활동', 'financing activities':'재무활동',
'net cash':'순현금', 'beginning balance':'기초 잔액', 'ending balance':'기말 잔액',
'opening balance':'기초 잔액', 'closing balance':'기말 잔액', 'balance at':'잔액 기준일',
'accounts receivable':'매출채권', 'receivables':'채권', 'retained earnings':'이익잉여금',
'shareholders equity':'주주지분', 'stockholders equity':'주주지분', 'common stock':'보통주',
'interest expense':'이자비용', 'interest income':'이자수익', 'deferred tax assets':'이연법인세자산',
'deferred tax liabilities':'이연법인세부채', 'income before taxes':'세전이익',
'operating income':'영업이익', 'operating profit':'영업이익', 'gross profit':'매출총이익',
'net earnings':'순이익', 'net loss':'순손실', 'net sales':'순매출액', 'cost of sales':'매출원가',
'cost of revenue':'매출원가', 'total revenues':'총매출', 'total debt':'총부채',
'fair value':'공정가치', 'carrying value':'장부가치', 'carrying amount':'장부금액',
'purchased technology':'취득 기술', 'trademark/tradename':'상표·상호', 'unallocated':'미배분',
'net realizable value':'순실현가능가치', 'net receivables':'순매출채권', 'gross receivables':'총매출채권',
'unrecognized':'미인식', 'allowance':'충당금', 'principal':'원금', 'interest':'이자',
'net':'순', 'total':'합계', 'sales':'매출액', 'revenue':'매출', 'expenses':'비용', 'expense':'비용',
'assets':'자산', 'liabilities':'부채', 'balance':'잔액', 'debt':'부채', 'equity':'자기자본',
'depreciation':'감가상각', 'amortization':'상각', 'shares':'주식', 'options':'옵션',
'outstanding':'미상환·미행사', 'forfeited':'실효', 'non-vested':'미가득',
'increase':'증가', 'decrease':'감소', 'additions':'증가액', 'disposals':'처분',
'adjustments':'조정', 'restructuring':'구조조정', 'foreign exchange':'외환', 'tax':'세금',
'dollars':'달러', 'millions':'백만 단위', 'thousands':'천 단위', 'percent':'백분율',
'actual':'실제', 'target':'목표', 'revised':'수정', 'preliminary':'잠정', 'at':'기준',
'December':'12월', 'November':'11월', 'October':'10월', 'September':'9월', 'August':'8월',
'July':'7월', 'June':'6월', 'May':'5월', 'April':'4월', 'March':'3월', 'February':'2월', 'January':'1월',
}
DIRECT = {
'The omitted Sales percentage in the common-size income statement.':'공통형 손익계산서에서 누락된 매출액 비율입니다.',
'The omitted interest component of capital lease obligations, in millions.':'금융리스 의무에서 누락된 이자 구성액입니다(백만 단위).',
'The capped intrinsic value used for the LEAPS premium.':'LEAPS 프리미엄 계산에 사용하는 상한 적용 내재가치입니다.',
'The total principal of the bond issue.':'발행된 채권의 총원금입니다.',
'The missing initial aggregate NFA (EA_01), or the foreign-currency asset exposure (EA_02).':'누락된 초기 순외국자산(NFA) 총액(EA_01) 또는 외화 자산 노출액(EA_02)입니다.',
'The initial investment index value at the explicitly stated base date.':'명시된 기준일의 초기 투자 지수값입니다.',
'The explicitly stated initial investment at the matching base date.':'해당 기준일에 명시된 초기 투자금입니다.',
'The Year 1 timing label for the first $150,000 cash flow.':'첫 $150,000 현금흐름의 시점을 나타내는 1년 차 표시입니다.',
'The missing annual total revenue, with the year specified by the ordered remaining narrative.':'누락된 연간 총매출입니다. 해당 연도는 남은 설명의 순서로 지정됩니다.',
'The first-year buydown reduction in percentage points.':'1년 차 금리 할인(buydown) 폭입니다(퍼센트포인트).',
'The omitted debt/equity allocation percentage.':'누락된 부채·자기자본 배분 비율입니다.',
'The Year 1 timing label for the first stated cash flow.':'처음 제시된 현금흐름의 시점을 나타내는 1년 차 표시입니다.',
'The year-1 bond cash flow in dollars.':'1년 차 채권 현금흐름입니다(달러).',
'The year of the first $1,000 annual cash flow.':'첫 $1,000 연간 현금흐름이 발생하는 연도입니다.',
'The probability of the good economic scenario, in percent.':'양호한 경제 시나리오의 확률입니다(백분율).',
'The first progressive-tax bracket upper boundary.':'첫 누진세 구간의 상한입니다.',
'The upper dollar boundary of the first progressive-tax bracket.':'첫 누진세 구간의 달러 금액 상한입니다.',
'The omitted spot rate(s) for the stated annual-coupon sovereign bond maturities.':'명시된 연 1회 이자 지급 국채 만기에 해당하는 누락 현물금리입니다.',
'The amount by which Food Care assets were understated in 2018, in millions.':'2018년 Food Care 자산이 과소계상된 금액입니다(백만 단위).',
'Value of Hologic shares issued for the R2 acquisition, thousands.':'R2 인수를 위해 발행한 Hologic 주식의 가치입니다(천 단위).',
'Forfeited non-vested shares, as a signed movement, thousands.':'실효된 미가득 주식 수입니다. 변동 부호를 포함합니다(천 단위).',
'The October 2015 regulatory liability amount.':'2015년 10월 규제 관련 부채 금액입니다.',
'The Data Center Group goodwill balance at December 28, 2019.':'2019년 12월 28일 Data Center Group의 영업권 잔액입니다.',
'Revised Food Care assets allocated for 2018, in millions.':'2018년에 배분된 Food Care 자산의 수정 금액입니다(백만 단위).',
'Purchased technology fair value, in the table fair-value column.':'표의 공정가치 열에 있는 취득 기술의 공정가치입니다.',
'Trademark/tradename fair value, in the table fair-value column.':'표의 공정가치 열에 있는 상표·상호의 공정가치입니다.',
}

GLOSSARY.update({
    'Total interest expense, net presented in the consolidated statements of income in which the effects of cash flow hedges are recorded':'현금흐름위험회피 효과가 반영된 연결손익계산서의 총순이자비용',
    'Basic net income attributable to American Tower Corporation common stockholders per common share':'American Tower Corporation 보통주 주주 귀속 기본 주당순이익',
    'Indemnification receivable from SSL for pre-closing taxes (see Note 13)':'거래 종결 전 세금에 대한 SSL 보상 미수금(주석 13 참조)',
    'Interim dividend for the half year ended 31 December 2018 of AU 16 cents (2017: AU 13 cents)':'2018년 12월 31일 종료 반기의 중간배당, AU 16센트(2017년: AU 13센트)',
    'Gains reclassified from accumulated other comprehensive income (loss) into revenue':'기타포괄손익 누계액에서 매출로 재분류된 이익',
    'Statutory Audit, Certification, Audit of Individual and Consolidated Financial Statements':'법정감사·인증·개별 및 연결재무제표 감사',
    'GAAP-based Professional Service and Other Gross Margin %':'GAAP 기준 전문서비스 및 기타 매출총이익률(%)',
    'Cash, restricted cash and short-term marketable securities':'현금·사용제한 현금·단기 시장성 유가증권',
    'Value of buildings and machinery, - At the beginning of the year':'건물·기계 가치 — 연초',
    'Accounted for at cost, adjusted for observable price changes':'관측 가능한 가격 변동을 조정한 원가 기준 회계처리',
    'Weighted average hedged rate for the year':'해당 연도 가중평균 위험회피 환율',
    'Basic earnings per share (cents per share)':'기본 주당이익(주당 센트)',
    'Average Urner Barry Spot Egg Market Quotations':'Urner Barry 현물 계란시장 평균 시세',
    'Weighted average common shares outstanding for diluted computations':'희석 계산용 가중평균 유통보통주 수',
    'Weighted average common shares outstanding for basic computations':'기본 계산용 가중평균 유통보통주 수',
    'Unrealized gains from foreign currency cash flow hedges':'외화 현금흐름위험회피 미실현이익',
    'Salaries, employee benefits and outsourced services':'급여·종업원 복리후생·외주서비스',
    'Gains on the sale of company-operated restaurants':'직영 음식점 매각이익',
    'other comprehensive income':'기타포괄이익', 'other comprehensive loss':'기타포괄손실',
    'accumulated other comprehensive income (loss)':'기타포괄손익 누계액',
    'cash flow hedges':'현금흐름위험회피', 'earnings per share':'주당이익',
    'net income per share':'주당순이익', 'weighted average':'가중평균',
    'common shares outstanding':'유통보통주 수', 'ordinary shares':'보통주',
    'common stockholders':'보통주 주주', 'net periodic benefit cost':'순기간 급여비용',
    'net periodic pension cost':'순기간 연금비용', 'net benefit cost':'순급여비용',
    'service cost':'근무원가', 'interest cost':'이자원가',
    'expected return on plan assets':'제도자산 기대수익', 'expected return':'기대수익',
    'fair value of plan assets':'제도자산 공정가치', 'projected benefit obligation':'예상급여채무',
    'accumulated benefit obligation':'누적급여채무', 'benefit obligation':'급여채무',
    'defined benefit':'확정급여', 'defined contribution':'확정기여',
    'stock-based compensation':'주식기준보상', 'share-based compensation':'주식기준보상',
    'stock based compensation':'주식기준보상', 'employee benefits':'종업원 복리후생',
    'property, plant and equipment':'유형자산(부동산·설비·장비)',
    'property, plant, and equipment':'유형자산(부동산·설비·장비)',
    'land and buildings':'토지·건물', 'accumulated depreciation':'감가상각 누계액',
    'plant and equipment':'설비·장비', 'construction in progress':'건설중인자산',
    'capital expenditures':'자본적 지출', 'capital expenditure':'자본적 지출',
    'right-of-use assets':'사용권자산', 'operating lease':'운용리스', 'finance lease':'금융리스',
    'long-term debt':'장기부채', 'short-term debt':'단기부채',
    'long-term borrowings':'장기차입금', 'short-term borrowings':'단기차입금',
    'current liabilities':'유동부채', 'current assets':'유동자산',
    'non-current liabilities':'비유동부채', 'non-current assets':'비유동자산',
    'noncurrent liabilities':'비유동부채', 'noncurrent assets':'비유동자산',
    'gross margin':'매출총이익률', 'operating margin':'영업이익률',
    'profit margin':'이익률', 'interest rate':'이자율', 'discount rate':'할인율',
    'exchange rate':'환율', 'effective tax rate':'유효세율', 'tax rate':'세율',
    'selling, general and administrative':'판매관리', 'general and administrative':'일반관리',
    'research and development':'연구개발', 'sales and marketing':'판매·마케팅',
    'net proceeds':'순유입액', 'proceeds from':'처분·발행 등 유입액:',
    'purchases of':'취득액:', 'payments for':'지급액:',
    'net cash provided by':'순현금 유입:', 'net cash used in':'순현금 사용:',
    'net cash provided':'제공된 순현금', 'net cash used':'사용된 순현금',
    'cash provided by':'현금 유입:', 'cash used in':'현금 사용:',
    'trade receivables':'매출채권', 'accounts payable':'매입채무', 'trade payables':'매입채무',
    'deferred revenue':'이연수익', 'accrued liabilities':'미지급부채',
    'accrued expenses':'미지급비용', 'accrued interest':'미지급·미수 이자',
    'other than temporary impairment':'일시적이지 않은 손상',
    'other-than-temporary impairment':'일시적이지 않은 손상',
    'unrealized gains':'미실현이익', 'unrealized losses':'미실현손실',
    'realized gains':'실현이익', 'realized losses':'실현손실',
    'foreign currency':'외화', 'marketable securities':'시장성 유가증권',
    'restricted cash':'사용제한 현금', 'financial instruments':'금융상품',
    'net financial result':'순금융손익', 'non-controlling interests':'비지배지분',
    'noncontrolling interests':'비지배지분', 'deferred compensation':'이연보상',
    'consolidated financial statements':'연결재무제표', 'consolidated statements of income':'연결손익계산서',
    'financial statements':'재무제표', 'statements of income':'손익계산서',
    'at the beginning of the year':'연초', 'at the end of the year':'연말',
    'beginning of year':'연초', 'end of year':'연말', 'for the year':'해당 연도',
    'during the year':'해당 연도 중', 'year ended':'회계연도 종료일',
    'period ended':'기간 종료일', 'for the period':'해당 기간',
    'for basic computations':'기본 계산용', 'for diluted computations':'희석 계산용',
    'per share':'주당', 'per common share':'보통주 1주당', 'cents per share':'주당 센트',
    'weighted':'가중', 'average':'평균', 'operating':'영업', 'current':'당기·유동',
    'noncurrent':'비유동', 'long-term':'장기', 'short-term':'단기',
    'fees':'수수료', 'equipment':'장비', 'compensation':'보상', 'benefit':'급여',
    'revenues':'매출', 'audit':'감사', 'related':'관련', 'employee':'종업원',
    'leases':'리스', 'lease':'리스', 'gains':'이익', 'gain':'이익',
    'losses':'손실', 'loss':'손실', 'costs':'비용', 'cost':'원가',
    'service':'서비스', 'services':'서비스', 'basic':'기본', 'diluted':'희석',
    'accrued':'미지급·미수', 'deferred':'이연', 'stock':'주식', 'share':'주식',
    'property':'부동산', 'capital':'자본', 'benefits':'급여·혜택',
    'statutory':'법정', 'quarter':'분기', 'land':'토지', 'buildings':'건물',
    'machinery':'기계', 'vehicles':'차량', 'dividend':'배당', 'dividends':'배당',
    'risk':'위험', 'federal':'연방', 'adjusted':'조정', 'trade':'거래',
    'research':'연구', 'development':'개발', 'impairment':'손상',
    'obligations':'의무', 'inventories':'재고', 'inventory':'재고', 'borrowings':'차입금',
    'note':'주석', 'domestic':'국내', 'consumption':'소비',
    'professional':'전문', 'payable':'미지급금', 'computations':'계산',
    'credit':'신용', 'positions':'포지션', 'pension':'연금', 'plant':'설비',
    'selling':'판매', 'price':'가격', 'securities':'유가증권',
    'gross':'총', 'free':'가용', 'restricted':'제한', 'software':'소프트웨어',
    'maintenance':'유지보수', 'instruments':'상품', 'trading':'거래',
    'state':'주', 'purchase':'매입', 'derivative':'파생상품',
    'margin':'이익률', 'acquisition':'인수', 'improvements':'개선',
    'accumulated':'누계', 'market':'시장', 'earnings':'이익', 'cents':'센트',
    'fiscal':'회계연도', 'plan':'제도', 'consolidated':'연결',
    'financial':'재무', 'attributable to':'귀속 대상:', 'transportation':'운송',
    'general':'일반', 'administrative':'관리', 'incurred':'발생',
    'foreign':'외국', 'monetary':'화폐성', 'temporary':'일시적',
    'acquired':'취득', 'investments':'투자', 'energy':'에너지',
    'indirect':'간접', 'investment':'투자', 'marketable':'시장성',
    'contract':'계약', 'integration':'통합', 'paid':'지급',
    'residential':'주거용', 'asset':'자산', 'amounts':'금액', 'owed':'지급할',
    'credits':'공제·대변', 'comprehensive':'포괄', 'funds':'자금',
    'deduction':'공제', 'performance':'성과', 'receivable':'미수금',
    'salaries':'급여', 'excess':'초과', 'payroll':'급여', 'delivery':'제공',
    'restaurants':'음식점', 'telecommunication':'통신', 'loan':'대출',
    'unvested':'미가득', 'assumed':'인수·가정', 'senior':'선순위',
    'cash':'현금', 'value':'가치', 'balances':'잔액', 'granted':'부여',
    'initial':'초기', 'other':'기타', 'year':'연도', 'period':'기간',
    'and':'및', 'or':'또는', 'non':'비', 'related to':'관련 대상:',
})


def term(text):
    text = re.sub(r'</?sup>', '', text, flags=re.I)
    for en, ko in sorted(GLOSSARY.items(), key=lambda p: -len(p[0])):
        text = re.sub(r'(?<![A-Za-z])'+re.escape(en)+r'(?![A-Za-z])', lambda m: ko, text, flags=re.I)
    return text


def missing(text):
    if text in DIRECT: return DIRECT[text]
    if text == 'The missing question-relevant quantity in the remaining Q/C.':
        return '남은 Q/C에서 이 질문에 필요하지만 누락된 수량입니다.'
    if text == 'The omitted quantity needed by this question, with the entity and period specified in the cited remaining Q/C.':
        return '이 질문에 필요한 누락 수량입니다. 대상과 기간은 인용한 남은 Q/C에 명시되어 있습니다.'
    match = re.fullmatch(r'The omitted (.+) entry in numeric column (\d+) of the remaining table; the question and table headers identify the entity, period and unit\.', text)
    if match:
        return f'남은 표의 {match[2]}번째 수치 열에서 누락된 항목: {term(match[1])}. 대상·기간·단위는 질문과 표 머리글을 따릅니다.'
    match = re.fullmatch(r'(.+), numeric column (\d+) in the remaining table\.', text)
    if match: return f'남은 표의 {match[2]}번째 수치 열에서 누락된 항목: {term(match[1])}.'
    prefix = 'The missing question-relevant quantity in the remaining Q/C: '
    if text.startswith(prefix): return '남은 Q/C에서 질문에 필요한 누락 수량: '+term(text[len(prefix):])
    return '누락 수량: '+term(re.sub(r'^The |\.$', '', text))


def main():
    project = Path(__file__).resolve().parents[4]
    path = project/'data/final/finject-20261007/EA_INVERSE_REVIEW.OFFLINE-20261008-003047-v2.jsonl'
    expected_sha = '40ac1638eb12c01853bbd1f4e8d43e56f3db24faad1e90127e6d6d61e8133ae1'
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
        raise ValueError('TRANSLATION_SOURCE_CHANGED: review translations before rebuilding')
    records = [v['review_record']['inverse_review'] for line in path.open() for v in json.loads(line)['variants']]
    reasons = collections.Counter(v['reason'] for v in records).most_common()
    if len(reasons) != len(REASONS): raise ValueError('TRANSLATION_REASON_COVERAGE')
    value = {'version': 1, 'snapshot_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
             'scope': 'Korean display aids only. English production records remain authoritative; proper names and table labels may be retained.',
             'reason': {en: ko for (en, _), ko in zip(reasons, REASONS)},
             'missing_quantity': {v['missing_quantity']: missing(v['missing_quantity']) for v in records}}
    (project/'viewer/dataset/ea-inverse-ko.json').write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'items':len(records), 'reason_strings':len(value['reason']), 'missing_quantity_strings':len(value['missing_quantity'])}))

if __name__ == '__main__': main()
