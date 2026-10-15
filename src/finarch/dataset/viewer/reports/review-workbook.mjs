import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';

const input=process.argv[2],destination=process.argv[3];
if(!input||!destination)throw Error('Usage: build-review.mjs review-data.json output.xlsx');
const d=JSON.parse(await fs.readFile(input,'utf8')),out=path.dirname(destination);
await fs.mkdir(out,{recursive:true});
const wb=Workbook.create(),count=d.matrix.length,matrixName=`${count}문항 매트릭스`;
const summary=wb.worksheets.add('유형별 요약'),matrix=wb.worksheets.add(matrixName),failures=wb.worksheets.add('실패 상세'),texts=wb.worksheets.add('문장 비교'),excluded=wb.worksheets.add('앞단계 제외');
const col=n=>String.fromCharCode(65+n),mEnd=count+6,fEnd=Math.max(6,d.details.length+5),eEnd=Math.max(6,d.exclusions.length+5);
function base(s,range,title){s.showGridLines=false;s.getRange(range).format={font:{name:'Arial',size:11,color:'#243247'},rowHeight:25,verticalAlignment:'center'};s.getRange('A2').values=[[title]];s.getRange('A2').format.font={size:16,bold:true,color:'#172A46'};s.getRange('A2').format.rowHeight=30;}
function header(s,r){s.getRange(r).format={fill:'#253D60',font:{bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:42,verticalAlignment:'center'};}
function status(s,r){for(const [v,fill,color] of [['PASS','#E6F3EA','#23613D'],['FAIL','#FCE3E3','#AE2020'],['EXCLUDED','#E5E7EB','#526070'],['NOT_EVALUATED','#FFF0C8','#846014'],['NOT_RUN','#F2F4F7','#718096']])s.getRange(r).conditionalFormats.add('cellIs',{operator:'equal',formula:`"${v}"`,format:{fill,font:{color,bold:v==='FAIL'}}});}
const hyperlinks=[];
function link(s,cell,url,label){s.getRange(cell).values=[[label]];hyperlinks.push({sheet:s.name,cell,url,label});}
const lines=(s,width=48)=>String(s).split('\n').reduce((n,x)=>n+Math.max(1,Math.ceil(x.length/width)),0);
const chunks=s=>String(s).match(/[\s\S]{1,240}/g)||[''];

base(summary,'A1:L32',`${d.run} 유형별 실패 검토`);
summary.getRange('A4').values=[['최대 3차의 누적 자동 결과입니다. 최종 사람 판정은 미실행입니다.']];
summary.getRange('A5').values=[['처리 횟수는 새 결과를 저장한 차수 수이며, 이전 통과 결과의 이월은 제외합니다.']];
summary.getRange('A7:G7').values=[['유형','PASS','FAIL','미평가','앞단계 제외','미실행','합계']];header(summary,'A7:G7');
summary.getRange('A8:A15').values=d.names.map(x=>[x]);
for(let i=0;i<8;i++){const r=i+8,c=col(i+3);summary.getRange(`B${r}:F${r}`).formulas=[['PASS','FAIL','NOT_EVALUATED','EXCLUDED','NOT_RUN'].map(v=>`=COUNTIF('${matrixName}'!${c}$7:${c}$${mEnd},"${v}")`)];summary.getRange(`G${r}`).formulas=[[`=SUM(B${r}:F${r})`]];}
summary.getRange('A16').values=[['문항×유형 합계']];summary.getRange('B16:G16').formulas=[Array.from({length:6},(_,i)=>`=SUM(${col(i+1)}8:${col(i+1)}15)`)];summary.getRange('A16:G16').format.font={bold:true};
summary.getRange('A18:D21').values=[['Generation 차수','통과','실패','미평가'],...d.round_counts.map((x,i)=>[i+1,x.NOT_RUN?null:(x.PASS||0),x.NOT_RUN?null:(x.FAIL||0),x.NOT_RUN?null:(x.NOT_EVALUATED||0)])];header(summary,'A18:D18');
summary.getRange('I18:L21').values=[['Preparation 차수','통과','실패','신규 처리'],...d.prep_rounds.map(r=>[r.round,r.state==='NOT_RUN'?null:r.counts.PASS||0,r.state==='NOT_RUN'?null:r.counts.FAIL||0,r.state==='NOT_RUN'?null:r.attempted])];header(summary,'I18:L18');
summary.getRange('A23').values=[[`앞단계 제외 ${d.exclusions.length}문항과 Generation 실패 ${d.details.length}유형은 별도 집계입니다.`]];
summary.getRange('A26:B26').values=[['실패 구간','건수']];header(summary,'A26:B26');
if(Object.keys(d.groups).length)summary.getRange('A27').write(Object.entries(d.groups));
summary.getRange('A1:A32').format.columnWidth=43;summary.getRange('B1:G32').format.columnWidth=16;summary.getRange('I1:L32').format.columnWidth=19;summary.getRange('B8:G21').setNumberFormat('0');

base(matrix,`A1:S${mEnd}`,`${count}문항 전체 매트릭스`);
matrix.getRange('A4').values=[['PASS 통과 / FAIL 실패 / EXCLUDED 앞단계 제외. 오른쪽은 유형별 실제 처리 횟수입니다.']];
matrix.getRange('A6:S6').values=[['번호','문항','앞단계',...d.names,...d.names.map(n=>n+' 처리 횟수')]];header(matrix,'A6:S6');
matrix.getRange(`A7:S${mEnd}`).values=d.matrix.map((r,i)=>[...r,...d.attempts[i]]);
matrix.getRange(`A1:A${mEnd}`).format.columnWidth=8;matrix.getRange(`B1:C${mEnd}`).format.columnWidth=18;matrix.getRange(`D1:S${mEnd}`).format.columnWidth=23;
matrix.freezePanes.freezeRows(6);matrix.freezePanes.freezeColumns(2);matrix.tables.add(`A6:S${mEnd}`,true,'CaseMatrix').style='TableStyleLight1';status(matrix,`D7:K${mEnd}`);

base(failures,`A1:Q${fEnd}`,`실패 ${d.details.length}건 근거와 검토`);
failures.getRange('A4').values=[['저장된 실패 이유를 그대로 보존했습니다. 문장 비교와 원기록 링크로 판단 근거를 확인하십시오.']];
failures.getRange('A5:Q5').values=[['번호','문항','유형','1차','2차','3차','실패 단계','구간','실패 이유 원문','검사 설명 원문','다음 확인','문장 비교','뷰어','생성 요청','생성 응답','검사 판정','적용 지침']];header(failures,'A5:Q5');
failures.getRange(`A1:A${fEnd}`).format.columnWidth=7;failures.getRange(`B1:C${fEnd}`).format.columnWidth=21;failures.getRange(`D1:F${fEnd}`).format.columnWidth=11;failures.getRange(`G1:H${fEnd}`).format.columnWidth=25;failures.getRange(`I1:K${fEnd}`).format.columnWidth=55;failures.getRange(`L1:P${fEnd}`).format.columnWidth=20;failures.getRange(`Q1:Q${fEnd}`).format.columnWidth=65;
failures.freezePanes.freezeRows(5);failures.freezePanes.freezeColumns(3);
const maxTextRows=10+d.details.reduce((n,x)=>n+Math.max(chunks(x.original).length,chunks(x.generated).length)+chunks(x.reason).length+chunks(x.excerpt).length+chunks(x.question).length+3,0);
base(texts,`A1:D${maxTextRows}`,'문제 문장 비교');texts.getRange(`A1:B${maxTextRows}`).format.columnWidth=85;texts.getRange(`C1:D${maxTextRows}`).format.columnWidth=22;texts.freezePanes.freezeRows(5);
texts.getRange('A4').values=[['【 】는 검토용 위치 표시입니다. 실제 원문·응답은 링크에서 확인할 수 있습니다.']];
let cursor=7;
for(let i=0;i<d.details.length;i++){
 const x=d.details[i],r=i+6,anchor=cursor;
 failures.getRange(`A${r}:Q${r}`).values=[[x.number,x.case,x.type,...x.rounds,x.stage,x.category,x.reason,x.cause,x.fix,'비교 보기','뷰어 열기','요청 원문','응답 원문','판정 원문',x.instructions]];
 failures.getRange(`G${r}:K${r}`).format.wrapText=true;failures.getRange(`Q${r}`).format.wrapText=true;failures.getRange(`A${r}:Q${r}`).format.rowHeight=Math.min(400,Math.max(64,...[x.reason,x.cause,x.fix,x.instructions].map(s=>lines(s)*15+10)));
 link(failures,`L${r}`,`#'문장 비교'!A${anchor}`,'비교 보기');link(failures,`M${r}`,x.viewer,'뷰어 열기');
 for(const [c,p] of [['N',x.request_path],['O',x.response_path],['P',x.verdict_path]])if(p)link(failures,`${c}${r}`,'file://'+p,'원문 열기');
 link(matrix,`${col(d.labels.indexOf(x.label)+3)}${x.number+6}`,`#'문장 비교'!A${anchor}`,'FAIL');
 texts.getRange(`A${cursor}:B${cursor}`).values=[[`${x.case} ${x.type}`,x.text_kind]];header(texts,`A${cursor}:B${cursor}`);link(texts,`C${cursor}`,`#'실패 상세'!A${r}`,'실패 상세');link(texts,`D${cursor}`,x.viewer,'뷰어 열기');cursor++;
 for(const [title,value] of [['실패 이유',x.reason],['문제 위치',x.excerpt],['질문',x.question]]){for(const part of chunks(value)){texts.getRange(`A${cursor}:B${cursor}`).values=[[title,part]];texts.getRange(`A${cursor}:B${cursor}`).format.wrapText=true;texts.getRange(`A${cursor}:B${cursor}`).format.rowHeight=Math.max(40,lines(part,75)*17+10);cursor++;}}
 texts.getRange(`A${cursor}:B${cursor}`).values=[['입력 본문','생성 본문 / 실패 진단용 적용본']];header(texts,`A${cursor}:B${cursor}`);cursor++;
 const a=chunks(x.original),b=chunks(x.generated);
 for(let j=0;j<Math.max(a.length,b.length);j++){texts.getRange(`A${cursor}:B${cursor}`).values=[[a[j]||'',b[j]||'']];texts.getRange(`A${cursor}:B${cursor}`).format.wrapText=true;texts.getRange(`A${cursor}:B${cursor}`).format.rowHeight=Math.max(60,Math.max(lines(a[j]||'',75),lines(b[j]||'',75))*17+10);if(x.diffs.some(y=>y.start<(j+1)*240&&y.end>=j*240))texts.getRange(`B${cursor}`).format.fill='#E5F3E9';cursor++;}
 cursor++;
}
if(d.details.length){failures.tables.add(`A5:Q${fEnd}`,true,'FailureDetails').style='TableStyleLight1';status(failures,`D6:F${fEnd}`);}else failures.getRange('A6').values=[['최종 실패 없음']];
base(excluded,`A1:E${eEnd}`,`앞단계 제외 ${d.exclusions.length}문항`);excluded.getRange('A4').values=[['설정한 최대 차수 이후 남은 Preparation 실패입니다. 원본·보완 이력은 보존했습니다.']];
excluded.getRange('A5:E5').values=[['번호','문항','중단 단계','저장된 이유','다음 확인 작업']];header(excluded,'A5:E5');
if(d.exclusions.length){excluded.getRange(`A6:E${eEnd}`).values=d.exclusions;excluded.tables.add(`A5:E${eEnd}`,true,'ExcludedCases').style='TableStyleLight1';}else excluded.getRange('A6').values=[['제외 문항 없음']];
excluded.freezePanes.freezeRows(5);excluded.getRange(`A1:A${eEnd}`).format.columnWidth=8;excluded.getRange(`B1:B${eEnd}`).format.columnWidth=18;excluded.getRange(`C1:C${eEnd}`).format.columnWidth=30;excluded.getRange(`D1:E${eEnd}`).format.columnWidth=75;excluded.getRange(`C6:E${eEnd}`).format.wrapText=true;
for(let i=0;i<d.exclusions.length;i++){const x=d.exclusions[i],r=i+6;excluded.getRange(`A${r}:E${r}`).format.rowHeight=Math.max(55,Math.max(lines(x[3],65),lines(x[4],65))*16+12);link(matrix,`D${x[0]+6}`,`#'앞단계 제외'!A${r}`,d.matrix[x[0]-1][3]);}
function paint(s,cell,value){const colors={PASS:['#E6F3EA','#23613D'],FAIL:['#FCE3E3','#AE2020'],EXCLUDED:['#E5E7EB','#526070'],NOT_EVALUATED:['#FFF0C8','#846014'],NOT_RUN:['#F2F4F7','#718096']}[value];if(colors)s.getRange(cell).format={fill:colors[0],font:{color:colors[1],bold:value==='FAIL'}};}
for(let i=0;i<d.matrix.length;i++)for(let j=3;j<11;j++)paint(matrix,`${col(j)}${i+7}`,d.matrix[i][j]);
for(let i=0;i<d.details.length;i++)for(let j=0;j<3;j++)paint(failures,`${col(j+3)}${i+6}`,d.details[i].rounds[j]);
await fs.writeFile(path.join(out,'hyperlinks.json'),JSON.stringify(hyperlinks));
wb.recalculate();
await fs.writeFile(path.join(out,'workbook-checks.json'),(await wb.inspect({kind:'table',range:'유형별 요약!A7:G16',include:'values,formulas',tableMaxRows:12,tableMaxCols:7,maxChars:6000})).ndjson);
await fs.writeFile(path.join(out,'formula-errors.json'),(await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:30},maxChars:2000})).ndjson);
if(!process.argv.includes('--validate-only'))await (await SpreadsheetFile.exportXlsx(wb)).save(destination);
for(const [name,range,file] of [['유형별 요약','A7:L21','summary'],[matrixName,'A6:K17','matrix'],['실패 상세','B5:K7','failures'],['문장 비교','A7:B12','texts'],['앞단계 제외','A5:E9','excluded']]){const image=await wb.render({sheetName:name,range,scale:1,format:'png'});await fs.writeFile(path.join(out,file+'.png'),new Uint8Array(await image.arrayBuffer()));}
console.log(JSON.stringify({output:destination,cases:count,failures:d.details.length,excluded:d.exclusions.length}));
