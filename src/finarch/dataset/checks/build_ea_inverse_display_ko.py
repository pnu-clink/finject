"""Create snapshot-bound Korean display strings without changing English records."""
import collections
import hashlib
import json
import re
from pathlib import Path

REASONS = '''
The exact sum/ratio of the remaining Q/C, the residual fluctuations, the re-presence of the same value, the weight, ratio or growth rate of the whole without missing the relationship is not identified as the only determinant of the required quantity. The values of different periods, the irrelevant quantities, the reversed percentages, the unspecified total range cannot determine the only substitute value.
The remaining Q/C is the ratio of the required fuel to the sum-to-ratio ratio, which is the only way to determine the amount of fuel that is missing.
The composition items listed are the sum of these tables, not the subset.
And if you add the middle fluctuations to the base residue to the symbol, it's the residual.
It's a mathematical relationship that you're going to apply to the name of the row.
The adjustment amount is the default amount plus the adjustment amount for the measurement period.
The question and the common profit statement shows each item as a percentage of revenue. 100%.
So the same period has the same denominator and the same period, so you can define the missing ratio as the specified share value or the net profit margin, and the display on this chart is exactly reversed.
The amount of the draw is equal to the electrical amount plus the absolute variable.
The remaining Context is on the reference date of the table.100So the initial index that you missed is the value of the 100.
The initial investment amount for the same context is $1.100It's re-expressed as:
If you subtract the net present value from the stated amount, the only determination is the net loss of the asset.
Electrical amount = the amount of time - the absolute variable specified.
So if we apply the continuity of the base-to-tool residue, 3month 31The rest of the work. 3,104,563This is the candidate. But the variable with the same period of time is the number of times the equation is shown. 2.978478So you use the other base residue, and the quantity of Q/C left is conflicting, so you can't get a consistent restoration.
2018And the rest of the horse. 2018So we have all the unmarked variables left over for the year, so we can set the base residual. 2019The year-end numbers are not used in this calculation.
It is not confirmed that the total amount of the net foreign assets (NFA) is the same as the total amount and the total amount in the total amount that the assets and debts exposed to foreign exchange are.
The unit of the variable column is not specified.190To interpret it as base points, we have to assume an unspecified spread, and the average investment capital ratio of ROFE is unclear, so we can't just determine the default ratio.
Payment cash includes premium and variable financial cost effects. Only the residual amounts of the two dates cannot know the full range of the variable amounts of the original money to exclude the possibility of other issues and repayments, nor can the deleted original or previous balance be determined solely.
Context to the remaining cash flow over the period and absolute increase over the previous year794 The only way to recover the cash flow is to have the two values that are missing.
In the rest of the description, we present real estate sales and restructuring finance sales for the same year as the total composition of sales.
The remaining mortgage terms do not specify a full dividend rate and fixed rate of repayment except for the repayment of the commission and the surcharge of the principal. Without these assumptions, the only way to determine the default rate or the interest rate of the principal is by the amount of the monthly repayment that is reversed.
EPS is the net profit divided by the average average average of the two shares, and we have both the same values for the same period, so we can calculate the missing share value with the second digit of the table.
The question is that the sector is made up of exactly these five companies. 100%So we can get the missing rate to the remaining four percentages.
The rest of the context explains that the capital structure is made up of debt and equity, and the sum of the two dividends is equal to the sum of two dividends. 100%.
The portfolio is made up of exactly three assets. 100%And there are two other weightings.
The portfolio is made up of exactly these three assets, and these allocation ratios make up the entire portfolio, and the sum of the assets is the sum of all the assets that are in the portfolio. 100%.
Context explicitly assumes a linear trend between the two endpoints of the quarter that we recorded, and the missing middle quarter value is the middle of the yield of the two adjacent endpoints.
I'm not sure. 1The amount of money paid to the debtor is in the national debt. 1The money is a pig. 1It's like a year's liquidity. Once you deduct the previous interest into short-term cash, and you solve the liquidity equation, you determine the only cash loss, and you reverse the percentage rate to the second place.
If you take the net financial loss from the three-year EBT, then the EBIT is equal to the net financial gain from the three years EBT. 713But, apart from the individual financial items, 714So the chart doesn't explain this reversal, so you can't set a single EBIT indicator that supports all the remaining equations.
The remaining description specifies the initial investment amount and date of each of the categories, including Vornado.
The adjustment EBITA divided by the revenue is the definition of this rate of return. 4.7%.
The adjustment EBITA divided by the revenue is the definition of this rate of return. 5.3%.
The rest of the description re-states the initial investment amount and date of this comparison.
In the annual adjustment intervals, 2017Shit. 12month 31The remaining amount is the same as the account. 2018Shit. 1month 1It's the base residue.
The only thing that determines the shortfall in asset returns is the actual negative returns that are excluded from the expected amount of returns.
The total of the financial loss payments includes interest, and each of the [a] accounts for the same amount of financial loss as $1.2,061 million is separately specified.
The total acquisition rate stated is the sum of the stock price, the current, the individual debt and the interest rate. You can restore the stock price by taking the other three items out.
Add the payout to the net debt. 22,445But the sum of the two components of the fee 222Use the 22,446The rest of the Q/Cs have a disjoint recovery path, so we can't set a single clear amount.
If you subtract the event from the market price, then the intrinsic value of the event is the value of the asset before the limit is applied. 15So, the context is not the only way to infer the amount of the application of the value of the underlying, but it's the only way that we can infer the amount that the underlying value is.
The refunds of the original money listed up to the final payment amount are the entire issue, and if you recover the sum, you can recover the missing amount.
The same amount of debt and date are again listed in the next sentence.
Context: The cash flow at the end of the year is 5And they explain that it happens in years. 2~5So the first year's cash flow is the 1The year car and the amount is left.
Double bottom line where the decrease item for the same period is not explained__And then we're going to have to go back to the first. 0There's no set value or definition, and because of this additional vague variable, it's not the only way to recover the missing balance.
Context is the contract. 3-2-1 And they call it buydown. 2·3I'm going to give you a discount. 2%·1%So, in this order, 1The discount rate for the car is... 3 And you can tell that's a percentage point.
In the context. 5And the annual cash flow, year after year. 2~5There's a year car sign. The first cash flow is at the time. 1It's the only one that's fixed in a pig car.
The bond price is the total applied to the given annual cash discount rate 4It's the sum of the current value of the year's cash flow minus the known subsequent current value. 1If you return the year car discount, you can get the cash flow back.
All 4The remaining cash flows from the yearly internal market 2·3·4So the cash flow for the first year is the 1It's a pig car.
The probability of the same favorable economic scenario on the second conditional yield line 70%And that's what we're saying.
The next section of the entire system of deflections that we have specified is 500,000 So the first half of the first half starts from the beginning. 500,000.
The second interval in the whole integer dollar slope is $10,001So the first interval is $10,000.
So, if you subtract the remaining part of the total, 7,155But the residual variation of the same line is the same as the previous guitar variation. 0When I work. 5,424 + 1,758 = 7,182So the remaining relationships collide and you can't be the only one to determine the remaining balance.
If you subtract the sub-minute fee from the gun bill, 176But if you subtract the sub-prime of the gross debt, like the gross debt of the gross 177You can't just set the individual payout that's missing, because the tolls are inconsistent.
Subtracting the stated total allowance from gross receivables 22,225So, if you subtract the items in the fee structure that you're showing, 22,224It's not the only way to recover the net debt that's gone out of balance.
The balance sheet of the same account is the balance sheet of that account. 8,217So this is just the way we can set the base residue right here.__(i.e. the change in the 0It's not treated as such.
The remaining four months are the sub-series of Food Care's Product Care $369.6 million and assets under management3.3 It's a million, and it says it has no effect on the assets that are connected.
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
