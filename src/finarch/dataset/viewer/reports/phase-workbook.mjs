import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const data=JSON.parse(await fs.readFile(process.argv[2],'utf8')),out=process.argv[3],wb=Workbook.create();
await fs.mkdir(out,{recursive:true});
const summary=wb.worksheets.add('종류별 요약'),errors=wb.worksheets.add('오류 상세');
const stages=data.phase==='preparation'?['02','03','05','06']:['01','02','03','04','05'];
const typeOrder=['IC_VALUE_01_BEFORE','IC_VALUE_01_AFTER','IC_SOURCE_A_ONLY','IC_SOURCE_B_ONLY','IC_RELATION_01','EA_01','EA_02'];
if(data.phase==='generation')data.summary.sort((a,b)=>b.category.localeCompare(a.category));
let tableNumber=0;const sheets=[summary,errors];
function table(s,title,headers,rows,header=4){
 s.showGridLines=false;s.getRange('A2').values=[[title]];s.getRange('A2').format.font={name:'Arial',size:16,bold:true};
 s.getRangeByIndexes(header,0,1,headers.length).values=[headers];
 if(rows.length)s.getRangeByIndexes(header+1,0,rows.length,headers.length).values=rows;
 const r=s.getRangeByIndexes(header,0,Math.max(1,rows.length+1),headers.length);r.format.font={name:'Arial',size:11,color:'#243247'};r.format.rowHeight=24;r.format.columnWidth=22;
 s.getRangeByIndexes(header,0,1,headers.length).format={fill:'#253D60',font:{color:'#FFFFFF',bold:true},rowHeight:30};
 r.format.horizontalAlignment='center';r.format.verticalAlignment='center';
 if(rows.length)s.tables.add(r,true,'T'+(++tableNumber)).style='TableStyleLight1';
 s.freezePanes.freezeRows(header+1);
}
table(summary,`${data.run} ${data.phase==='preparation'?'Preparation':'Generation'} 결과 리포트`,['문제 종류 / 유형','전체','통과','실패','성공비율','미평가','미실행'],data.summary.map(r=>[r.category,r.total,r.PASS,r.FAIL,null,r.NOT_EVALUATED,r.NOT_RUN]));
summary.getRange('A3').values=[[`마지막 실행 차수 상태 · 단위 ${data.unit} · ${data.generated_at}`]];
summary.getRange('A5:A30').format.columnWidth=38;
summary.getRange('B6:G30').setNumberFormat('#,##0');
for(let i=0;i<data.summary.length;i++){const r=i+6;summary.getRange(`E${r}`).formulas=[[`=IF(B${r}=0,"n.a.",C${r}/B${r})`]];}
summary.getRange(`E6:E${data.summary.length+5}`).setNumberFormat('0.0%');
table(errors,'오류 케이스',['문제번호','지식 구분','문제 종류 / 유형','오류 종류','오류 원문','원본 경로'],data.errors.map(e=>[e.case,e.knowledge,e.category,e.code,e.reason,e.source]));
errors.getRange('B5:C'+Math.max(6,data.errors.length+5)).format.columnWidth=32;
errors.getRange('C5:C'+Math.max(6,data.errors.length+5)).format.columnWidth=48;
errors.getRange('A5:E'+Math.max(6,data.errors.length+5)).format.verticalAlignment='center';
errors.getRange('C6:C'+Math.max(6,data.errors.length+5)).format.wrapText=true;
errors.getRange('E5:F'+Math.max(6,data.errors.length+5)).format.columnWidth=80;
errors.getRange('E6:F'+Math.max(6,data.errors.length+5)).format.wrapText=true;
for(let i=0;i<data.errors.length;i++)errors.getRange(`A${i+6}:F${i+6}`).format.rowHeight=Math.max(44,Math.ceil(data.errors[i].reason.length/80)*15);
// Final error maps: a dash means no final error recorded at that step, not step PASS.
const names={PASS:'통과',FAIL:'오류',ERROR:'오류',NOT_EVALUATED:'미평가',NOT_RUN:'미실행'};
function colorMap(sheet,rowCount,colCount){
 const range=sheet.getRangeByIndexes(8,1,Math.max(1,rowCount),colCount-1);
 range.format.horizontalAlignment='center';
 for(const [text,fill,color] of [['오류','#FDE2DF','#A52222'],['미평가','#FFF0CC','#855500'],['통과','#E3F1E9','#20583A'],['미실행','#EEEEEE','#666666']]){
  range.conditionalFormats.add('containsText',{text,format:{fill,font:{color}}});
 }
 sheet.getRange('A3').values=[['최종 상태 기준. —: 해당 단계 최종 오류 없음(단계 통과를 뜻하지 않음). 미평가는 별도 표시.']];
}
function knowledgeRates(sheet,items){
 const groups=[['IN-CONTEXT only',r=>r.knowledge_sources?.includes('IN_CONTEXT_DATA')&&!r.knowledge_sources.some(x=>x==='EXTERNAL_RULE'||x==='EXTERNAL_DATA')],['ER/ED',r=>r.knowledge_sources?.some(x=>x==='EXTERNAL_RULE'||x==='EXTERNAL_DATA')],['미분류',r=>!r.knowledge_sources?.length]];
 sheet.getRange('A4:F4').values=[['지식 구분','전체','통과','실패','미평가·미실행','통과율']];
 sheet.getRange('A4:F4').format={fill:'#E8EEF6',font:{bold:true},rowHeight:24};
 groups.forEach(([name,predicate],i)=>{const selected=items.filter(predicate),r=i+5,pass=selected.filter(x=>x.status==='PASS').length,fail=selected.filter(x=>['FAIL','ERROR'].includes(x.status)).length;
 sheet.getRange(`A${r}:F${r}`).values=[[name,selected.length,pass,fail,selected.length-pass-fail,null]];
 sheet.getRange(`F${r}`).formulas=[[`=IF(B${r}=0,"n.a.",C${r}/B${r})`]];
 });
 sheet.getRange('A4:F7').format.horizontalAlignment='center';sheet.getRange('A4:F7').format.verticalAlignment='center';
 sheet.getRange('B5:E7').setNumberFormat('#,##0');sheet.getRange('F5:F7').setNumberFormat('0.0%');
 sheet.getRange('A3').values=[[`통과율 = 통과 / 전체 (${data.unit}). 미평가도 분모에 포함. —: 해당 단계 최종 오류 없음.`]];
}
if(data.phase==='generation'){
 const map=wb.worksheets.add('문항 유형 지도');sheets.push(map);
 const variants=[...new Map(data.maps.map(r=>[r.variant,r.category])).entries()].sort();
 const byCase=new Map();for(const r of data.maps){if(!byCase.has(r.case))byCase.set(r.case,new Map());byCase.get(r.case).set(r.variant,r);}
 const rows=[...byCase].sort().map(([id,items])=>[id,items.values().next().value.knowledge,...variants.map(([v])=>{const r=items.get(v);return r?(names[r.status]||r.status)+(r.error_stage?' '+r.error_stage:''):'미실행';})]);
 table(map,'Generation 문항 × 유형',['문제번호','지식 구분',...variants.map(v=>v[1])],rows,7);map.getRange(`C9:I${rows.length+8}`).format.horizontalAlignment='center';map.getRange(`B8:B${rows.length+8}`).format.columnWidth=55;
 map.tabColor='#E59424';knowledgeRates(map,data.maps);
 map.getRange(`C9:I${rows.length+8}`).conditionalFormats.add('containsText',{text:'미평가',format:{fill:'#FFF0CC',font:{color:'#855500'}}});
 const allRows=map.getRange(`A9:I${rows.length+8}`);
 allRows.conditionalFormats.addCustom('COUNTIF($C9:$I9,"통과")=7',{fill:'#DCEBFC',font:{color:'#164C86'}});
 map.getRange(`C9:I${rows.length+8}`).conditionalFormats.add('containsText',{text:'오류',format:{font:{color:'#C00000',bold:true}}});
}
const groups=data.phase==='preparation'?[['Preparation',data.maps]]:[...new Set(data.maps.map(r=>r.variant))].sort().map(v=>[v,data.maps.filter(r=>r.variant===v)]);
for(const [name,items] of groups){
 const sheet=wb.worksheets.add(data.phase==='preparation'?'01-07 오류 지도':name.slice(0,3)+'단계 오류 지도');sheets.push(sheet);
 const rows=items.map(r=>[r.case,r.knowledge,names[r.status]||r.status,r.round||'미기록',...data.stage_columns.map(step=>r.error_stage===step?'오류':r.handler_error&&step==='04'?'오류(처리기)':'—'),r.error_stage===null&&r.status==='FAIL'?'단계 미기록':'',r.source||'']);
 table(sheet,name+' 단계별 최종 오류',['문제번호','지식 구분','최종 상태','실행 차수',...data.stage_columns.map(x=>x+' 단계'),'주의','근거 파일'],rows,7);
 colorMap(sheet,rows.length,4+data.stage_columns.length);
 sheet.getRange(`B8:B${rows.length+8}`).format.columnWidth=55;
 sheet.getRangeByIndexes(7,4,rows.length+1,data.stage_columns.length).format.columnWidth=13;
 sheet.getRangeByIndexes(7,5+data.stage_columns.length,rows.length+1,1).format.columnWidth=70;
 knowledgeRates(sheet,items);
}
errors.getRange(`B5:B${Math.max(6,data.errors.length+5)}`).format.columnWidth=55;
const palette=['#007DBA','#B54B16','#8137C2','#16844B'];
for(const stage of stages){
 const s=wb.worksheets.add(stage+' 토큰'),series=data.usage.series.filter(x=>x.stage===stage);
 sheets.push(s);
 const numbers=[...new Set(series.flatMap(x=>x.points.map(p=>p[0])))].sort((a,b)=>a-b),maps=series.map(x=>new Map(x.points));
 table(s,`${stage} 단계 LLM 사용량`,['문제번호',...series.map(x=>x.model)],numbers.map(n=>[n,...maps.map(m=>m.has(n)?m.get(n):null)]));
 s.getRange('A3').values=[['모든 차수 입력+출력 토큰 합계. 빈칸은 사용량 기록 없음.']];
 if(series.length&&numbers.length){
  s.getRangeByIndexes(5,1,numbers.length,series.length).setNumberFormat('#,##0');
  const chart=s.charts.add('scatter',s.getRangeByIndexes(4,0,numbers.length+1,series.length+1));
  chart.title=stage+' 단계 모델별 토큰 사용량';chart.setPosition('F5','T24');chart.legend={position:'top'};
  chart.xAxis.title.text='문제번호';chart.yAxis.title.text='사용 토큰 수';chart.yAxis.numberFormatCode='#,##0';
  chart.series.items.forEach((v,i)=>{v.fill=palette[i%palette.length];});
 }else s.getRange('F6').values=[['LLM 사용량 기록 없음 / 미실행']];
}
summary.getRange('A'+(data.summary.length+8)).values=[[`LLM 호출 기록 ${data.usage.call_records}건, 토큰 미기록 ${data.usage.missing_usage}건, 읽기 실패 ${data.usage.unreadable_records}건`]];
const grouped=new Map();for(const e of data.errors){const key=e.category+'|'+e.code;grouped.set(key,(grouped.get(key)||0)+1);}
const start=data.summary.length+11;summary.getRange(`A${start}:C${start}`).values=[['문제 종류 / 유형','오류 종류','건수']];
let rr=start+1;for(const [key,count] of [...grouped].sort((a,b)=>{const [at,ac]=a[0].split('|'),[bt,bc]=b[0].split('|');return data.phase==='generation'?(typeOrder.indexOf(at)-typeOrder.indexOf(bt)||ac.localeCompare(bc)):at.localeCompare(bt)||ac.localeCompare(bc);})){const [category,code]=key.split('|');summary.getRange(`A${rr}:C${rr}`).values=[[category,code,count]];rr++;}
summary.getRange(`B${start}:B${Math.max(start,rr)}`).format.columnWidth=48;summary.getRange(`A${start}:C${Math.max(start,rr)}`).format.wrapText=true;summary.getRange(`A${start}:C${Math.max(start,rr)}`).format.rowHeight=32;
summary.getRange(`A${start}:C${Math.max(start,rr)}`).format.horizontalAlignment='center';summary.getRange(`A${start}:C${Math.max(start,rr)}`).format.verticalAlignment='center';
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:"'종류별 요약'!A5:F14",tableMaxRows:10,tableMaxCols:6})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:20}})).ndjson);
for(const s of sheets){const image=await wb.render({sheetName:s.name,range:s.name.endsWith('토큰')?'F5:T24':s.name.includes('지도')?'A1:K18':'A1:G14',scale:1,format:'png'});await fs.writeFile(`${out}/${s.name}.png`,new Uint8Array(await image.arrayBuffer()));}
await (await SpreadsheetFile.exportXlsx(wb)).save(`${out}/${data.phase}-report.xlsx`);
