// Build H1/H2 tables from the read-only snapshot created by export.py.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [input, output, ...options] = process.argv.slice(2);
if (!input || !output) throw new Error('Usage: workbook.mjs data.json result.xlsx [--preview-dir DIR]');
const previewDir = options.includes('--preview-dir') ? options[options.indexOf('--preview-dir') + 1] : null;
const quadrantPreviewOnly = options.includes('--preview-only-quadrant');
const data = JSON.parse(await fs.readFile(input, 'utf8'));
const workbook = Workbook.create();
const names = ['H1_NASU_Quadrant', 'H1_NASU', 'H1_선택지표', 'H1_U세부분류', 'H2_집단비교', 'H2_변형별', 'H1H2_집계자료', 'H1H2_실행정보'];
const sheets = Object.fromEntries(names.map(n => [n, workbook.worksheets.add(n)]));
const colors = {ink:'#172B4D', header:'#304967', soft:'#F0F4F8', line:'#CBD5E1', red:'#FCE8E6'};
const font = 'Arial';
const inputName = 'H1H2_집계자료';
const keys = ['run','label','dataset','model','prompt_condition','reasoning','cohort','variant','original_count','planned',
  'NS','NU','AS','AU','ND','AD','F','NU_MATCH','NU_MISMATCH','NU_UNKNOWN','AU_U_U','AU_S_U','AU_U_S','AU_D_U','AU_U_D'];
const rawHeaders = ['run','model_label','dataset','model_key','guided','reasoning','original_cohort','variant',
  'original_count','planned','NS','NU','AS','AU','ND','AD','unreviewed','NU_ref_match','NU_ref_mismatch',
  'NU_ref_unknown','AU_ARV_U_DG_U','AU_ARV_S_DG_U','AU_ARV_U_DG_S','AU_ARV_D_DG_U','AU_ARV_U_DG_D'];
function col(n) {let out=''; for(n++; n; n=Math.floor((n-1)/26)) out=String.fromCharCode(65+(n-1)%26)+out; return out;}
function sum(refs) {return refs.length ? `SUM(${refs.join(',')})` : '0';}
function refs(rows, key) {return rows.map(r => `'${inputName}'!${col(keys.indexOf(key))}${r.excelRow}`);}
function total(rows, key) {return sum(refs(rows, key));}
function combined(rows, ...fields) {return sum(fields.flatMap(k => refs(rows,k)));}
function ratio(num, den) {return `IF((${den})=0,"N/A",(${num})/(${den}))`;}
function formula(sheet, cell, expression) {sheet.getRange(cell).formulas = [[`=${expression}`]];}
function value(sheet, cell, val) {sheet.getRange(cell).values = [[val]];}
function baseStyle(sheet, rows, columns, raw=false) {
  const range=sheet.getRange(`A1:${col(columns-1)}${rows}`);
  range.format.font={name:font,size:11,color:colors.ink};
  range.format.rowHeight=26;
  range.format.columnWidth=14;
  range.format.verticalAlignment='center';
  sheet.showGridLines=false;
  sheet.tabColor=raw ? '#A4AFBC' : '#304967';
}
function header(sheet,row,labels,left=0) {
  const r=sheet.getRange(`${col(left)}${row}:${col(left+labels.length-1)}${row}`);
  r.values=[labels];
  r.format={fill:colors.header,font:{name:font,size:11,bold:true,color:'#FFFFFF'},wrapText:true,
    horizontalAlignment:'center',verticalAlignment:'center',rowHeight:46};
}
function opening(sheet,title,notes,labels,nrows) {
  baseStyle(sheet,Math.max(nrows+6,12),labels.length);
  value(sheet,'A2',title);
  sheet.getRange(`A2:${col(labels.length-1)}2`).format.borders={bottom:{style:'thin',color:colors.line}};
  sheet.getRange('A2').format.font={name:font,size:16,bold:true,color:colors.ink};
  notes.forEach((s,i)=>value(sheet,`A${i+3}`,s));
  header(sheet,6,labels);
  sheet.getRange(`A7:${col(labels.length-1)}${Math.max(7,nrows+6)}`).setNumberFormat('#,##0');
  sheet.getRange(`A1:A${nrows+6}`).format.columnWidth=14;
  sheet.getRange(`B1:B${nrows+6}`).format.columnWidth=25;
  sheet.getRange(`C1:D${nrows+6}`).format.columnWidth=11;
  sheet.freezePanes.freezeRows(6);
  sheet.freezePanes.freezeColumns(2);
}
function stripe(sheet,row,last,totalRow=false,left=0) {
  if(totalRow || row%2===0) sheet.getRange(`${col(left)}${row}:${col(left+last-1)}${row}`).format.fill=colors.soft;
  if(totalRow) sheet.getRange(`${col(left)}${row}:${col(left+last-1)}${row}`).format.font.bold=true;
}
function percentages(sheet,columns,last) {
  for(const c of columns) sheet.getRange(`${c}7:${c}${last}`).setNumberFormat('0.00%');
}
function finishTable(sheet,last,width,name,left=0) {
  if(last<7) return;
  const table=sheet.tables.add(`${col(left)}6:${col(left+width-1)}${last}`,true,name);
  table.showFilterButton=true;
}

// Static source counts retain the full classification, including mixed unsupported cases.
const source=sheets[inputName];
baseStyle(source,data.aggregates.length+1,keys.length,true);
header(source,1,rawHeaders);
data.aggregates.forEach((r,i)=>r.excelRow=i+2);
source.getRange(`A2:Y${data.aggregates.length+1}`).values=data.aggregates.map(r=>keys.map(k=>r[k]));
source.getRange(`I2:Y${data.aggregates.length+1}`).setNumberFormat('#,##0');
source.getRange(`A1:A${data.aggregates.length+1}`).format.columnWidth=49;
source.getRange(`B1:D${data.aggregates.length+1}`).format.columnWidth=25;
source.getRange(`H1:H${data.aggregates.length+1}`).format.columnWidth=28;
source.freezePanes.freezeRows(1); source.freezePanes.freezeColumns(2);
source.tables.add(`A1:Y${data.aggregates.length+1}`,true,'Counts');

const groups=[];
for(const run of data.runs) {
  const all=data.aggregates.filter(r=>r.run===run.run);
  for(const dataset of [...new Set(all.map(r=>r.dataset))]) {
    for(const model of [...new Set(all.filter(r=>r.dataset===dataset).map(r=>r.model))]) {
      const rows=all.filter(r=>r.dataset===dataset && r.model===model);
      for(const [g,r] of [['unguided','off'],['unguided','on'],['guided','off'],['guided','on'],['ALL','ALL']]) {
        const selected=rows.filter(x=>g==='ALL' || (x.prompt_condition===g && x.reasoning===r));
        if(!selected.length) continue; // Unsupported conditions remain absent, never zero-valued trials.
        groups.push({run:run.run,label:run.label,dataset,model,g,r,rows:selected,
          labels:[dataset,run.label,g==='ALL'?'합계':g==='guided'?'ON':'OFF',r==='ALL'?'합계':r.toUpperCase()]});
      }
    }
  }
}

const numericRateChecks=[];
let sheet=sheets.H1_NASU;
opening(sheet,'H1. 응답 형태와 근거 지원 여부',[
  '전체 원본 집단의 5개 변형을 집계합니다. 합계는 조건별 시행 수의 합입니다.',
  'S: 적용 판정 모두 SUPPORTED. U: 하나 이상 UNSUPPORTED. D: 미확정. 미검토는 분모에서 제외합니다.',
  'N: Numeric(수치 답변), A: Abstention(answer=null). D와 미검토는 S 비율의 분모에 포함하지 않습니다.'
],['Dataset','Model','Guided','Reasoning','계획 응답','NS','NU','AS','AU','D','미검토','전체 S 비율','Numeric S 비율','Abstention S 비율','검토 완료율'],groups.length);
groups.forEach((g,i)=>{
  const r=i+7; const rows=g.rows;
  sheet.getRange(`A${r}:D${r}`).values=[g.labels];
  const expressions=[total(rows,'planned'),total(rows,'NS'),total(rows,'NU'),total(rows,'AS'),total(rows,'AU'),
    combined(rows,'ND','AD'),total(rows,'F'),ratio(`F${r}+H${r}`,`SUM(F${r}:I${r})`),
    ratio(`F${r}`,`F${r}+G${r}`),ratio(`H${r}`,`H${r}+I${r}`),ratio(`E${r}-K${r}`,`E${r}`)];
  sheet.getRange(`E${r}:O${r}`).formulas=[expressions.map(s=>'='+s)];
  stripe(sheet,r,15,g.g==='ALL');
  numericRateChecks.push({sheet:sheet.name,cell:`L${r}`,expected:calcRate(rows,['NS','AS'],['NS','NU','AS','AU'])});
});
percentages(sheet,['L','M','N','O'],groups.length+6);
finishTable(sheet,groups.length+6,15,'H1NASU');

// One four-panel view per model, using full NASU category names and all U cases.
const quadrant=sheets.H1_NASU_Quadrant;
const quadrantModels=groups.filter(g=>g.g==='ALL');
const quadrantChecks=[];
const quadrantViews=[];
baseStyle(quadrant,quadrantModels.length*36+6,45);
quadrant.getRange(`A1:AS${quadrantModels.length*36+6}`).format.columnWidth=11;
for(const c of ['A','H','O','P','W','AD','AE','AL','AS']) quadrant.getRange(`${c}1:${c}${quadrantModels.length*36+6}`).format.columnWidth=3;
value(quadrant,'B2','H1 NASU Quadrant');
quadrant.getRange('B2:N2').merge();
quadrant.getRange('B2').format.font={name:font,size:16,bold:true,color:colors.ink};
quadrant.getRange('B3:N3').merge();
value(quadrant,'B3','위: Guided / 아래: Unguided. 왼쪽: Reasoning OFF / 오른쪽: ON.');
quadrant.getRange('B4:N4').merge();
value(quadrant,'B4','NS / NU / AS / AU 전체 건수입니다. D / 미검토는 비율 분모에서 제외합니다.');
quadrant.getRange('B5:N5').merge();
value(quadrant,'B5',`저장 자료 시각(UTC): ${data.generated_at}`);
quadrant.getRange('B5').format.font={name:font,size:11,color:'#52647A'};

function blockCellOn(target,left,right,row,text,format={}) {
  const range=target.getRange(`${col(left)}${row}:${col(right)}${row}`);
  if(right>left) range.merge();
  range.values=[[text]];
  range.format={verticalAlignment:'center',...format};
  return `${col(left)}${row}`;
}
function blockCell(...args) {return blockCellOn(quadrant,...args);}
function groupIndex(model,guided,reasoning) {
  return groups.findIndex(g=>g.run===model.run && g.dataset===model.dataset && g.model===model.model &&
    g.g===guided && g.r===reasoning);
}
function expectedCount(group,...fields) {
  return group?group.rows.reduce((s,r)=>s+fields.reduce((n,k)=>n+r[k],0),0):'N/A';
}
function addCheck(target,cell,expected) {quadrantChecks.push({sheet:target.name,cell,expected});}
function glossary(target,left,right,row) {
  blockCellOn(target,left,right,row,[
    'N (Numeric): 수치 답변 / A (Abstention): 기권(answer=null)',
    'S (Supported): 적용 판정 모두 S / U (Unsupported): 하나 이상 U / D (Undetermined): 판정 미확정',
    'NS: 근거있는 수치 응답 / NU: 근거가 뒷받침하지 못한 수치 응답',
    'AS: 근거있는 거부 응답 / AU: 근거가 뒷받침하지 못한 거부 응답',
    'ARV: 기권 이유 타당성 / DG: 최종 판단의 근거 지원 / 미검토: 유효한 검토 결과 없음'
  ].join('\n'),{wrapText:true,font:{name:font,size:10,color:'#52647A'},rowHeight:82});
}
function panel(model,guided,reasoning,left,top) {
  const width=6, right=left+width-1;
  const full=quadrant.getRange(`${col(left)}${top}:${col(right)}${top+12}`);
  full.format.borders={preset:'outside',style:'thin',color:'#94A3B8'};
  const found=groupIndex(model,guided,reasoning);
  const group=found<0?null:groups[found], sourceRow=found+7;
  blockCell(left,right,top,`${guided==='guided'?'Guided':'Unguided'} / Reasoning ${reasoning.toUpperCase()}`,
    {fill:guided==='guided'?colors.header:'#52647A',font:{name:font,size:12,bold:true,color:'#FFFFFF'},horizontalAlignment:'center'});
  quadrant.getRange(`${col(left)}${top}:${col(right)}${top}`).format.rowHeight=30;
  const status=blockCell(left,right,top+1,'', {font:{name:font,size:11,color:'#52647A'},horizontalAlignment:'center',wrapText:true,rowHeight:36});
  if(group) {
    const seeds=group.rows.filter(r=>r.variant==='IC_VALUE_01_BEFORE');
    const seedCount=expectedCount({rows:seeds},'original_count');
    const variantCount=Object.keys(data.variants).length;
    assert.equal(seedCount*variantCount,expectedCount(group,'planned'),'Original count times variants must equal planned responses');
    formula(quadrant,status,`"계획: 원본 "&TEXT(${total(seeds,'original_count')},"#,##0")&"건 × ${variantCount} = "&TEXT('H1_NASU'!E${sourceRow},"#,##0")&"건 / 검토 "&TEXT('H1_NASU'!E${sourceRow}-'H1_NASU'!K${sourceRow},"#,##0")&"건"`);
    addCheck(quadrant,status,`계획: 원본 ${seedCount.toLocaleString('en-US')}건 × ${variantCount} = ${expectedCount(group,'planned').toLocaleString('en-US')}건 / 검토 ${(expectedCount(group,'planned')-expectedCount(group,'F')).toLocaleString('en-US')}건`);
  } else value(quadrant,status,'평가 계획에 없는 조건');
  const cells={};
  for(const [kind,offset,dy,inputColumn] of [
    ['NS',0,2,'F'],['NU',3,2,'G'],['AS',0,4,'H'],['AU',3,4,'I']]) {
    const start=left+offset, end=start+2, fill=kind.endsWith('S')?'#E7F2EF':'#FBEDEC';
    const label={NS:'NS (근거있는 수치 응답)',AS:'AS (근거있는 거부 응답)'}[kind]||kind;
    blockCell(start,end,top+dy,label,{fill,font:{name:font,size:11,bold:true,color:colors.ink},horizontalAlignment:'center',wrapText:true,rowHeight:32});
    const cell=blockCell(start,end,top+dy+1,'N/A',{
      fill,font:{name:font,size:20,bold:true,color:kind.endsWith('S')?'#17594C':'#923B3B'},horizontalAlignment:'center',numberFormat:'#,##0'});
    quadrant.getRange(`${col(start)}${top+dy+1}:${col(end)}${top+dy+1}`).format.rowHeight=33;
    if(group) formula(quadrant,cell,`'H1_NASU'!${inputColumn}${sourceRow}`);
    cells[kind]=cell;
    quadrantChecks.push({sheet:quadrant.name,cell,expected:group?group.rows.reduce((s,r)=>s+r[kind],0):'N/A'});
  }
  quadrant.getRange(`${col(left)}${top+3}:${col(right)}${top+3}`).format.borders={bottom:{style:'thin',color:'#FFFFFF'}};
  quadrant.getRange(`${col(left)}${top+6}:${col(right)}${top+6}`).format.rowHeight=9;
  blockCell(left,left+1,top+7,'D (미확정)',{fill:'#F5F6F8',horizontalAlignment:'left'});
  const dCell=blockCell(left+2,left+2,top+7,'N/A',{fill:'#F5F6F8',horizontalAlignment:'right',numberFormat:'#,##0'});
  blockCell(left+3,left+4,top+7,'미검토',{fill:'#F5F6F8',horizontalAlignment:'center'});
  const fCell=blockCell(left+5,left+5,top+7,'N/A',{fill:'#F5F6F8',horizontalAlignment:'right',numberFormat:'#,##0'});
  if(group) {
    formula(quadrant,dCell,`'H1_NASU'!J${sourceRow}`);
    formula(quadrant,fCell,`'H1_NASU'!K${sourceRow}`);
  }
  for(const [cell,fields] of [[dCell,['ND','AD']],[fCell,['F']]]) quadrantChecks.push({sheet:quadrant.name,cell,
    expected:group?group.rows.reduce((s,r)=>s+fields.reduce((a,k)=>a+r[k],0),0):'N/A'});
  const sumAll=`${cells.NS}+${cells.NU}+${cells.AS}+${cells.AU}`;
  const metrics=[
    ['S 비율\n(근거있는 답변)','(NS+AS)/\n(NS+NU+AS+AU)',`${cells.NS}+${cells.AS}`,sumAll,['NS','AS'],['NS','NU','AS','AU']],
    ['NS 비율\n(근거있는 수치 응답)','NS/(NS+NU)',cells.NS,`${cells.NS}+${cells.NU}`,['NS'],['NS','NU']],
    ['AS 비율\n(근거있는 거부 응답)','AS/(AS+AU)',cells.AS,`${cells.AS}+${cells.AU}`,['AS'],['AS','AU']]
  ];
  metrics.forEach(([label,expression,num,den,nKeys,dKeys],i)=>{
    const row=top+8+i;
    blockCell(left,left+2,row,label,{font:{name:font,size:11,bold:true,color:colors.ink},wrapText:true,rowHeight:38});
    blockCell(left+3,left+4,row,expression,{font:{name:font,size:11,color:'#52647A'},horizontalAlignment:'center',wrapText:true});
    const cell=blockCell(left+5,left+5,row,'N/A',{numberFormat:'0.00%',font:{name:font,size:11,bold:true,color:colors.ink},horizontalAlignment:'right'});
    if(group) formula(quadrant,cell,ratio(num,den));
    quadrantChecks.push({sheet:quadrant.name,cell,expected:group?calcRate(group.rows,nKeys,dKeys):'N/A'});
  });
  blockCell(left,left+1,top+11,'S 비율 분모',{font:{name:font,size:11,color:'#52647A'}});
  blockCell(left+2,left+4,top+11,'NS+NU+AS+AU',{font:{name:font,size:11,color:'#52647A'},horizontalAlignment:'center'});
  const denominator=blockCell(left+5,left+5,top+11,'N/A',{numberFormat:'#,##0',horizontalAlignment:'right'});
  if(group) formula(quadrant,denominator,sumAll);
  blockCell(left,right,top+12,group?'NS / AS 비율은 각 응답 형태 안의 S 비율입니다.':'자료 없음 — 0건으로 집계하지 않습니다.',
    {font:{name:font,size:10,color:'#52647A'},horizontalAlignment:'center'});
  full.format.borders={preset:'outside',style:'thin',color:'#94A3B8'};
}

quadrantModels.forEach((model,i)=>{
  const top=7+i*36;
  const meta=data.runs.find(r=>r.run===model.run);
  blockCell(1,13,top,`${model.label}  /  ${model.dataset}`,{font:{name:font,size:16,bold:true,color:colors.ink}});
  quadrant.getRange(`B${top}:N${top}`).format.borders={bottom:{style:'thin',color:colors.line}};
  blockCell(1,13,top+1,`${model.run}   |   Judge: ${meta.judge_models.join('; ')||'Analysis 미실행'}`,
    {font:{name:font,size:10,color:'#52647A'}});
  glossary(quadrant,1,13,top+2);
  panel(model,'guided','off',1,top+3);
  panel(model,'guided','on',8,top+3);
  panel(model,'unguided','off',1,top+18);
  panel(model,'unguided','on',8,top+18);
  quadrantViews.push({index:i,label:model.label,start:top,end:top+35});
});

blockCell(16,28,2,'H1 선택지표 Quadrant',{font:{name:font,size:16,bold:true,color:colors.ink}});
blockCell(16,28,3,'NASU와 같은 모델 / 조건입니다. 합계 = S + U + 선택 제외.');
blockCell(16,28,4,'D / 미검토는 별도 표시합니다. S 비율 = S/(S+U), U 비율 = U/(S+U).');
blockCell(16,28,5,'N: Numeric / A: Abstention. 형태 미확정 응답도 별도로 보존합니다.',
  {font:{name:font,size:11,color:'#52647A'}});

sheet=sheets.H1_선택지표;
opening(sheet,'H1. 선택한 Numeric / Abstention 집단의 지원 비율',[
  'Numeric: S=NS, U=NU 중 원본 reference 불일치. Abstention: S=AS, U=ARV / DG 모두 U인 AU.',
  '선택 비율은 S/(S+U)입니다. NU reference 일치 및 AU 혼합 판정은 선택 분모에서 제외합니다.',
  'NU의 원본 reference 비교는 변형의 GOLD 판정이 아닙니다. 형태 미확정 응답은 H1_NASU의 미검토에 포함합니다.'
],['Dataset','Model','Guided','Reasoning','응답 형태','선택 S','선택 U','선택 분모','S 비율','U 비율','선택 제외','D','미검토','해당 형태 합계'],groups.length*2);
for(const [i,g] of groups.entries()) {
  for(const [j,action] of ['Numeric','Abstention'].entries()) {
    const r=7+i*2+j; const n=j===0;
    const s=total(g.rows,n?'NS':'AS'), u=total(g.rows,n?'NU_MISMATCH':'AU_U_U');
    const excluded=n ? combined(g.rows,'NU_MATCH','NU_UNKNOWN') : combined(g.rows,'AU_S_U','AU_U_S','AU_D_U','AU_U_D');
    const d=total(g.rows,n?'ND':'AD');
    const actionCode=n?'N':'A';
    const failed=data.responses.filter(x=>x.run===g.run && x.dataset===g.dataset && x.model===g.model &&
      (g.g==='ALL'||(x.prompt_condition===g.g&&x.reasoning===g.r)) && x.action===actionCode && x.nasu==='F').length;
    sheet.getRange(`A${r}:E${r}`).values=[[...g.labels,action]];
    sheet.getRange(`F${r}:L${r}`).formulas=[[s,u,`F${r}+G${r}`,ratio(`F${r}`,`H${r}`),ratio(`G${r}`,`H${r}`),excluded,d].map(v=>'='+v)];
    value(sheet,`M${r}`,failed);
    formula(sheet,`N${r}`,`SUM(F${r}:G${r},K${r}:M${r})`);
    stripe(sheet,r,14,g.g==='ALL');
    numericRateChecks.push({sheet:sheet.name,cell:`I${r}`,expected:calcRate(g.rows,[n?'NS':'AS'],n?['NS','NU_MISMATCH']:['AS','AU_U_U'])});
  }
}
percentages(sheet,['I','J'],groups.length*2+6);
sheet.getRange(`E1:E${groups.length*2+6}`).format.columnWidth=18;
finishTable(sheet,groups.length*2+6,14,'H1Selected');

function selectedPanel(model,guided,reasoning,left,top) {
  const right=left+5, found=groupIndex(model,guided,reasoning);
  const group=found<0?null:groups[found], nRow=7+found*2, aRow=nRow+1;
  const cell=(l,r,y,text,format={})=>blockCell(l,r,y,text,format);
  cell(left,right,top,`${guided==='guided'?'Guided':'Unguided'} / Reasoning ${reasoning.toUpperCase()}`,
    {fill:guided==='guided'?colors.header:'#52647A',font:{name:font,size:12,bold:true,color:'#FFFFFF'},horizontalAlignment:'center'});
  cell(left,right,top+1,group?'합계 = S + U + 선택 제외':'평가 계획에 없는 조건',
    {font:{name:font,size:11,color:'#52647A'},horizontalAlignment:'center'});
  const tableHeader={fill:'#E8EDF3',font:{name:font,size:11,bold:true,color:colors.ink},horizontalAlignment:'center'};
  cell(left,left+1,top+2,'응답 형태',tableHeader);
  for(const [i,label] of ['S','U','선택 제외','합계'].entries()) cell(left+2+i,left+2+i,top+2,label,tableHeader);
  const totals=[];
  for(const [j,label] of ['N','A'].entries()) {
    const r=top+3+j, sourceRow=j?aRow:nRow;
    cell(left,left+1,r,label,{font:{name:font,size:12,bold:true,color:colors.ink},horizontalAlignment:'center'});
    const cells=[];
    for(const [i,key] of ['F','G','K'].entries()) {
      const address=cell(left+2+i,left+2+i,r,'N/A',{numberFormat:'#,##0',horizontalAlignment:'right',
        fill:i===0?'#E7F2EF':i===1?'#FBEDEC':'#F4F0E7'});
      if(group) formula(quadrant,address,`'H1_선택지표'!${key}${sourceRow}`);
      const fields=i===0?[j?'AS':'NS']:i===1?[j?'AU_U_U':'NU_MISMATCH']:
        j?['AU_S_U','AU_U_S','AU_D_U','AU_U_D']:['NU_MATCH','NU_UNKNOWN'];
      addCheck(quadrant,address,expectedCount(group,...fields));
      cells.push(address);
    }
    const totalCell=cell(left+5,left+5,r,'N/A',{numberFormat:'#,##0',horizontalAlignment:'right',
      font:{name:font,size:11,bold:true,color:colors.ink}});
    if(group) formula(quadrant,totalCell,`SUM(${cells.join(',')})`);
    addCheck(quadrant,totalCell,expectedCount(group,...(j?['AS','AU']:['NS','NU'])));
    totals.push(totalCell);
  }
  const extras=[];
  for(const [dy,label,sourceColumn,fields] of [[5,'D (미확정)','L',['ND','AD']],[7,'미검토','M',null]]) {
    cell(left,left+1,top+dy,label,{fill:'#F5F6F8'});
    for(const [j,type] of ['N','A'].entries()) {
      cell(left+2+j*2,left+2+j*2,top+dy,type,{fill:'#F5F6F8',horizontalAlignment:'center'});
      const address=cell(left+3+j*2,left+3+j*2,top+dy,'N/A',{fill:'#F5F6F8',numberFormat:'#,##0',horizontalAlignment:'right'});
      if(group) formula(quadrant,address,`'H1_선택지표'!${sourceColumn}${j?aRow:nRow}`);
      const expected=!group?'N/A':fields?expectedCount(group,fields[j]):data.responses.filter(x=>
        x.run===group.run && x.dataset===group.dataset && x.model===group.model && x.prompt_condition===guided &&
        x.reasoning===reasoning && x.action===type && x.nasu==='F').length;
      addCheck(quadrant,address,expected);
      extras.push(address);
    }
  }
  cell(left,left+1,top+8,'형태 미확정',{font:{name:font,size:11,color:'#52647A'}});
  cell(left+2,left+4,top+8,'N/A 구분 불가',{font:{name:font,size:11,color:'#52647A'},horizontalAlignment:'center'});
  const unknown=cell(left+5,left+5,top+8,'N/A',{numberFormat:'#,##0',horizontalAlignment:'right'});
  if(group) formula(quadrant,unknown,`'H1_NASU'!K${found+7}-'H1_선택지표'!M${nRow}-'H1_선택지표'!M${aRow}`);
  addCheck(quadrant,unknown,!group?'N/A':data.responses.filter(x=>
    x.run===group.run && x.dataset===group.dataset && x.model===group.model && x.prompt_condition===guided &&
    x.reasoning===reasoning && x.action==='UNKNOWN' && x.nasu==='F').length);
  cell(left,left+1,top+9,'응답 형태',tableHeader);
  cell(left+2,left+3,top+9,'S 비율',tableHeader);
  cell(left+4,left+5,top+9,'U 비율',tableHeader);
  for(const [j,type] of ['N','A'].entries()) {
    cell(left,left+1,top+10+j,type,{horizontalAlignment:'center',font:{name:font,size:11,bold:true,color:colors.ink}});
    for(const [i,sourceColumn] of ['I','J'].entries()) {
      const address=cell(left+2+i*2,left+3+i*2,top+10+j,'N/A',{numberFormat:'0.00%',horizontalAlignment:'right',
        font:{name:font,size:11,bold:true,color:colors.ink}});
      if(group) formula(quadrant,address,`'H1_선택지표'!${sourceColumn}${j?aRow:nRow}`);
      addCheck(quadrant,address,!group?'N/A':calcRate(group.rows,
        [i?(j?'AU_U_U':'NU_MISMATCH'):(j?'AS':'NS')],j?['AS','AU_U_U']:['NS','NU_MISMATCH']));
    }
  }
  cell(left,right,top+12,'S/(S+U)  /  U/(S+U) — 선택 제외 / D / 미검토는 분모 제외',
    {font:{name:font,size:10,color:'#52647A'},horizontalAlignment:'center'});
  quadrant.getRange(`${col(left)}${top}:${col(right)}${top+12}`).format.borders={preset:'outside',style:'thin',color:'#94A3B8'};
  if(group) quadrantReconciliations.push({cells:[...totals,...extras,unknown],expected:expectedCount(group,'planned')});
}
const quadrantReconciliations=[];
quadrantModels.forEach((model,i)=>{
  const top=7+i*36, meta=data.runs.find(r=>r.run===model.run);
  blockCell(16,28,top,`${model.label}  /  ${model.dataset}`,{font:{name:font,size:16,bold:true,color:colors.ink}});
  blockCell(16,28,top+1,`Judge: ${meta.judge_models.join('; ')||'Analysis 미실행'}`,{font:{name:font,size:10,color:'#52647A'}});
  glossary(quadrant,16,28,top+2);
  selectedPanel(model,'guided','off',16,top+3);
  selectedPanel(model,'guided','on',23,top+3);
  selectedPanel(model,'unguided','off',16,top+18);
  selectedPanel(model,'unguided','on',23,top+18);
  blockCell(16,28,top+32,'선택 제외 / 오른쪽 U 세부 분류 참고 →',
    {font:{name:font,size:11,bold:true,color:colors.ink},fill:'#F4F0E7',wrapText:true});
  blockCell(16,28,top+33,'N: NU 중 원본 Gold 일치 / 비교 불가를 제외합니다. 수치가 원본 정답과 같아도 DG는 U인 응답입니다.',
    {font:{name:font,size:11,color:'#52647A'},wrapText:true,rowHeight:55});
  blockCell(16,28,top+34,'A: AU 중 ARV와 DG가 모두 U인 응답만 선택 U에 남깁니다. 나머지 AU는 선택 제외이며, 전체 NASU에는 포함합니다.',
    {font:{name:font,size:11,color:'#52647A'},wrapText:true,rowHeight:55});
});

sheet=sheets.H1_U세부분류;
const uSheet=sheet;
baseStyle(uSheet,quadrantModels.length*36+6,30);
uSheet.getRange(`A1:O${quadrantModels.length*36+6}`).format.columnWidth=11;
for(const c of ['A','H','O','P']) uSheet.getRange(`${c}1:${c}${quadrantModels.length*36+6}`).format.columnWidth=3;
const uCell=(...args)=>blockCellOn(uSheet,...args);
uCell(1,13,2,'H1 U 세부 분류 Quadrant',{font:{name:font,size:16,bold:true,color:colors.ink}});
uCell(1,13,3,'위: Guided / 아래: Unguided. 왼쪽: Reasoning OFF / 오른쪽: ON.');
uCell(1,13,4,'Gold는 원본 reference입니다. ARV S / DG S는 AS이므로 AU 합계에서 제외합니다.');
uCell(1,13,5,'미확정이 섞인 AU도 두 줄로 별도 표시합니다.',{font:{name:font,size:11,color:'#52647A'}});
// Retain the existing flat detail table to the right of the new panels.
value(uSheet,'Q2','H1. Unsupported 응답의 전체 세부 분류');
uSheet.getRange('Q2').format.font={name:font,size:16,bold:true,color:colors.ink};
value(uSheet,'Q3','Reference는 원본 정답입니다. NU 세 칸의 합은 NU, AU 다섯 칸의 합은 AU입니다.');
value(uSheet,'Q4','ARV: 기권 이유 타당성. DG: 최종 판단의 근거 지원. S=SUPPORTED, U=UNSUPPORTED, D=UNDETERMINED.');
const uFields=['NU','NU_MATCH','NU_MISMATCH','NU_UNKNOWN','AU','AU_U_U','AU_S_U','AU_U_S','AU_D_U','AU_U_D'];
header(uSheet,6,['Dataset','Model','Guided','Reasoning','NU 전체','NU ref 일치','NU ref 불일치','NU ref 미확정',
  'AU 전체','ARV U DG U','ARV S DG U','ARV U DG S','ARV D DG U','ARV U DG D'],16);
uSheet.getRange(`R1:R${groups.length+6}`).format.columnWidth=25;
uSheet.getRange(`S1:T${groups.length+6}`).format.columnWidth=11;
uSheet.getRange(`U7:AD${groups.length+6}`).setNumberFormat('#,##0');
groups.forEach((g,i)=>{
  const r=i+7;
  uSheet.getRange(`Q${r}:T${r}`).values=[g.labels];
  uSheet.getRange(`U${r}:AD${r}`).formulas=[uFields.map(k=>'='+total(g.rows,k))];
  stripe(uSheet,r,14,g.g==='ALL',16);
});
finishTable(uSheet,groups.length+6,14,'H1Details',16);

function unsupportedPanel(model,guided,reasoning,left,top,target=uSheet) {
  const uCell=(...args)=>blockCellOn(target,...args);
  const right=left+5, found=groupIndex(model,guided,reasoning), group=found<0?null:groups[found], r=found+7;
  const link=(address,key)=>{
    if(group) formula(target,address,`'H1_U세부분류'!${col(20+uFields.indexOf(key))}${r}`);
    addCheck(target,address,expectedCount(group,key));
  };
  uCell(left,right,top,`${guided==='guided'?'Guided':'Unguided'} / Reasoning ${reasoning.toUpperCase()}`,
    {fill:guided==='guided'?colors.header:'#52647A',font:{name:font,size:12,bold:true,color:'#FFFFFF'},horizontalAlignment:'center'});
  target.getRange(`${col(left)}${top}:${col(right)}${top}`).format.rowHeight=30;
  target.getRange(`${col(left)}${top+6}:${col(right)}${top+6}`).format.rowHeight=26;
  const status=uCell(left,right,top+1,group?'':'평가 계획에 없는 조건',
    {font:{name:font,size:11,color:'#52647A'},horizontalAlignment:'center'});
  if(group) formula(target,status,`"계획 "&TEXT('H1_NASU'!E${r},"#,##0")&"건 / 검토 "&TEXT('H1_NASU'!E${r}-'H1_NASU'!K${r},"#,##0")&"건"`);
  for(const [dy,label,key] of [[2,'NU 전체','NU'],[3,'NU Gold 일치','NU_MATCH'],[4,'NU Gold 미일치','NU_MISMATCH'],[5,'NU Gold 비교 불가','NU_UNKNOWN'],[6,'AU 전체','AU']]) {
    const major=dy===2||dy===6;
    const fill=major?'#E8EDF3':key==='NU_MISMATCH'?'#FBEDEC':['NU_MATCH','NU_UNKNOWN'].includes(key)?'#F4F0E7':'#FFFFFF';
    const style={fill,font:{name:font,size:11,bold:major,color:colors.ink}};
    uCell(left,left+3,top+dy,label,style);
    const address=uCell(left+4,right,top+dy,'N/A',{...style,numberFormat:'#,##0',horizontalAlignment:'right'});
    link(address,key);
  }
  const head={fill:'#E8EDF3',font:{name:font,size:11,bold:true,color:colors.ink},horizontalAlignment:'center'};
  for(const [j,label] of ['ARV 구분','DG S','DG U'].entries()) uCell(left+j*2,left+j*2+1,top+7,label,head);
  uCell(left,left+1,top+8,'ARV S',{horizontalAlignment:'center',font:{name:font,size:11,bold:true,color:colors.ink}});
  uCell(left,left+1,top+9,'ARV U',{horizontalAlignment:'center',font:{name:font,size:11,bold:true,color:colors.ink}});
  const as=uCell(left+2,left+3,top+8,'N/A',{fill:'#EEF0F3',horizontalAlignment:'right',font:{name:font,size:11,color:'#64748B'}});
  if(group) formula(target,as,`"AS "&TEXT('H1_NASU'!H${r},"#,##0")`);
  addCheck(target,as,group?`AS ${expectedCount(group,'AS').toLocaleString('en-US')}`:'N/A');
  for(const [offset,dy,key] of [[4,8,'AU_S_U'],[2,9,'AU_U_S'],[4,9,'AU_U_U']]) {
    const address=uCell(left+offset,left+offset+1,top+dy,'N/A',{
      fill:key==='AU_U_U'?'#FBEDEC':'#F7F0E5',numberFormat:'#,##0',horizontalAlignment:'right'});
    link(address,key);
  }
  for(const [dy,label,key] of [[10,'ARV D / DG U','AU_D_U'],[11,'ARV U / DG D','AU_U_D']]) {
    uCell(left,left+3,top+dy,label,{fill:'#F5F6F8',font:{name:font,size:11,color:'#52647A'}});
    const address=uCell(left+4,right,top+dy,'N/A',{fill:'#F5F6F8',numberFormat:'#,##0',horizontalAlignment:'right'});
    link(address,key);
  }
  uCell(left,right,top+12,'회색 칸은 AS이며 AU 합계에 포함하지 않습니다.',
    {font:{name:font,size:10,color:'#52647A'},horizontalAlignment:'center'});
  target.getRange(`${col(left)}${top}:${col(right)}${top+12}`).format.borders={preset:'outside',style:'thin',color:'#94A3B8'};
}
function unsupportedNotes(target,left,right,top) {
  const notes=[
    ['NU Gold: Gold는 원본 정답입니다.\n일치: 수치가 원본 정답과 같지만 DG는 U입니다. 설명 / 계산 / 근거가 수치 답변을 뒷받침하지 못합니다.\n미일치: DG는 U이며 수치도 원본 정답과 다릅니다.','#F4F0E7'],
    ['ARV S / DG U: 기권 사유는 타당하지만, 응답의 설명과 근거가 최종 기권을 충분히 뒷받침하지 못한다는 판정입니다.\n계산 오류 등 구체적인 원인은 각 응답의 DG 판정 이유를 확인해야 합니다.','#F7F0E5'],
    ['ARV U / DG U: 제시한 기권 사유와 최종 기권의 정당화가 모두 지원되지 않는 경우입니다.\n이 판정만으로 문항 자체에 기권이 불필요했다고 확정하지는 않습니다.','#FBEDEC']
  ];
  notes.forEach(([text,fill],i)=>blockCellOn(target,left,right,top+32+i,text,
    {fill,font:{name:font,size:11,color:'#52647A'},wrapText:true,rowHeight:58}));
}
quadrantModels.forEach((model,i)=>{
  const top=7+i*36, meta=data.runs.find(r=>r.run===model.run);
  uCell(1,13,top,`${model.label}  /  ${model.dataset}`,{font:{name:font,size:16,bold:true,color:colors.ink}});
  uCell(1,13,top+1,`${model.run}   |   Judge: ${meta.judge_models.join('; ')||'Analysis 미실행'}`,
    {font:{name:font,size:10,color:'#52647A'}});
  glossary(uSheet,1,13,top+2);
  unsupportedPanel(model,'guided','off',1,top+3);
  unsupportedPanel(model,'guided','on',8,top+3);
  unsupportedPanel(model,'unguided','off',1,top+18);
  unsupportedPanel(model,'unguided','on',8,top+18);
  unsupportedNotes(uSheet,1,13,top);
});

// Align the same U breakdown beside the selected metrics on the first worksheet.
blockCell(31,43,2,'H1 U 세부 분류 Quadrant',{font:{name:font,size:16,bold:true,color:colors.ink}});
blockCell(31,43,3,'위: Guided / 아래: Unguided. 왼쪽: Reasoning OFF / 오른쪽: ON.');
blockCell(31,43,4,'N 선택 제외 = NU Gold 일치 + 비교 불가 (Gold = 원본 정답).');
blockCell(31,43,5,'A 선택 제외 = AU 전체 − (ARV와 DG가 모두 U인 건수).',{font:{name:font,size:11,color:'#52647A'}});
quadrantModels.forEach((model,i)=>{
  const top=7+i*36, meta=data.runs.find(r=>r.run===model.run);
  blockCell(31,43,top,`${model.label}  /  ${model.dataset}`,{font:{name:font,size:16,bold:true,color:colors.ink}});
  blockCell(31,43,top+1,`Judge: ${meta.judge_models.join('; ')||'Analysis 미실행'}`,{font:{name:font,size:10,color:'#52647A'}});
  glossary(quadrant,31,43,top+2);
  unsupportedPanel(model,'guided','off',31,top+3,quadrant);
  unsupportedPanel(model,'guided','on',38,top+3,quadrant);
  unsupportedPanel(model,'unguided','off',31,top+18,quadrant);
  unsupportedPanel(model,'unguided','on',38,top+18,quadrant);
  unsupportedNotes(quadrant,31,43,top);
});
for(const boundary of ['O','AD']) {
  quadrant.getRange(`${boundary}2:${boundary}${quadrantModels.length*36+6}`).format.borders={
    right:{style:'medium',color:'#94A3B8'}
  };
}

function originalCount(rows,cohort) {
  return total(rows.filter(r=>r.cohort===cohort && r.variant==='IC_VALUE_01_BEFORE'),'original_count');
}
function cohortMetric(rows,cohort,metric) {
  const selected=rows.filter(r=>r.cohort===cohort);
  const fields=metric==='ALL'?['NS','AS']:metric==='N'?['NS']:['AS'];
  const den=metric==='ALL'?['NS','NU','AS','AU']:metric==='N'?['NS','NU_MISMATCH']:['AS','AU_U_U'];
  return [combined(selected,...fields),combined(selected,...den),calcRate(selected,fields,den)];
}
sheet=sheets.H2_집단비교;
opening(sheet,'H2. 원본 정답 / 오답 집단의 변형 대응 비교',[
  '정답 / 오답은 원본 reference와의 수치 일치 여부입니다. 원본 판정 불가는 별도 집단으로 보존합니다.',
  '정답 집단의 대응 비율 − 오답 집단의 대응 비율을 %p로 표시합니다. 선택 N/A와 전체 S/(S+U)를 구분합니다.',
  '각 행은 같은 모델 / 조건의 원본과 대응 변형만 연결합니다. 원본 DG는 A02의 평가 대상이 아닙니다.'
],['Dataset','Model','Guided','Reasoning','대응 지표','원본 정답 수','원본 오답 수','원본 판정 불가',
  '정답 집단 S','정답 집단 분모','정답 집단 비율','오답 집단 S','오답 집단 분모','오답 집단 비율','차이 (%p)'],groups.length*3);
for(const [i,g] of groups.entries()) {
  for(const [j,[metric,label]] of [['ALL','전체 S/(S+U)'],['N','선택 Numeric'],['A','선택 Abstention']].entries()) {
    const r=7+i*3+j;
    sheet.getRange(`A${r}:E${r}`).values=[[...g.labels,label]];
    sheet.getRange(`F${r}:H${r}`).formulas=[['CORRECT','INCORRECT','UNKNOWN'].map(c=>'='+originalCount(g.rows,c))];
    const [s1,d1,e1]=cohortMetric(g.rows,'CORRECT',metric), [s0,d0,e0]=cohortMetric(g.rows,'INCORRECT',metric);
    sheet.getRange(`I${r}:O${r}`).formulas=[[s1,d1,ratio(`I${r}`,`J${r}`),s0,d0,ratio(`L${r}`,`M${r}`),
      `IF(OR(J${r}=0,M${r}=0),"N/A",(K${r}-N${r})*100)`].map(x=>'='+x)];
    numericRateChecks.push({sheet:sheet.name,cell:`K${r}`,expected:e1},{sheet:sheet.name,cell:`N${r}`,expected:e0});
    stripe(sheet,r,15,g.g==='ALL');
  }
}
percentages(sheet,['K','N'],groups.length*3+6);
sheet.getRange(`O7:O${groups.length*3+6}`).setNumberFormat('+0.00;-0.00;0.00');
sheet.getRange(`E1:E${groups.length*3+6}`).format.columnWidth=24;
finishTable(sheet,groups.length*3+6,15,'H2Cohorts');

sheet=sheets.H2_변형별;
const variantRecords=[];
for(const g of groups.filter(g=>g.g!=='ALL')) {
  for(const cohort of ['CORRECT','INCORRECT','UNKNOWN']) {
    for(const [variant,label] of Object.entries(data.variants)) {
      const rows=g.rows.filter(r=>r.cohort===cohort && r.variant===variant);
      if(rows.length) variantRecords.push({g,cohort,variant,label,rows});
    }
  }
}
opening(sheet,'H2. 집단 / 변형별 분모와 대응 결과',[
  'S=NS+AS, U=NU+AU. 검토 분모는 S+U입니다. D와 미검토를 빼는 과정을 함께 표시합니다.',
  'S/원본 수는 고정 집단 대비 지원 응답 비율입니다. S/(S+U)와 분모가 다릅니다. IC-source는 별도 OVS 분석 대상입니다.'
],['Dataset','Model','Guided','Reasoning','원본 집단','변형','원본 수','S','U','D','미검토','S+U','S/(S+U)','S/원본 수'],variantRecords.length);
variantRecords.forEach((x,i)=>{
  const r=i+7;
  sheet.getRange(`A${r}:F${r}`).values=[[...x.g.labels,{CORRECT:'정답',INCORRECT:'오답',UNKNOWN:'판정 불가'}[x.cohort],x.label]];
  sheet.getRange(`G${r}:N${r}`).formulas=[[total(x.rows,'original_count'),combined(x.rows,'NS','AS'),combined(x.rows,'NU','AU'),
    combined(x.rows,'ND','AD'),total(x.rows,'F'),`H${r}+I${r}`,ratio(`H${r}`,`L${r}`),ratio(`H${r}`,`G${r}`)].map(v=>'='+v)];
  stripe(sheet,r,14);
});
percentages(sheet,['M','N'],variantRecords.length+6);
finishTable(sheet,variantRecords.length+6,14,'H2Variants');

sheet=sheets.H1H2_실행정보;
opening(sheet,'실행 범위와 집계 기준',[
  `저장 결과 조회 시각(UTC): ${data.generated_at}. 새 모델 호출: 0.`,
  'A02는 최신 저장 attempt만 사용합니다. 실패한 최신 결과 대신 과거 성공 결과를 가져오지 않습니다.'
],['Model','Run','원본 시행','변형 계획','A02 계획','A02 VALID','A02 실패','이후 새 attempt','분석 상태','Judge'],data.runs.length);
data.runs.forEach((run,i)=>{
  const r=i+7, valid=run.judge_counts.VALID||0, failed=Object.entries(run.judge_counts).filter(([k])=>k!=='VALID').reduce((a,[,n])=>a+n,0);
  const status=!run.a02_requests?'미실행':valid===run.a02_requests?'A02 전체 VALID':'A02 일부 검토 가능';
  sheet.getRange(`A${r}:J${r}`).values=[[run.label,run.run,run.planned_originals,run.planned_variants,run.a02_requests,valid,failed,
    run.newer_attempts_during_read,status,run.judge_models.join('; ')||'미실행']];
  stripe(sheet,r,10);
});
sheet.getRange('A1:A45').format.columnWidth=27;
sheet.getRange('B1:B45').format.columnWidth=54;
sheet.getRange('I1:I45').format.columnWidth=26;
sheet.getRange('J1:J45').format.columnWidth=34;
const method=[
  ['H1','전체 원본 집단의 NASU. 원본 정답 여부로 선별하지 않습니다.'],
  ['H2','같은 모델 / 조건에서 원본 정답 집단과 오답 집단의 지원 비율을 비교합니다.'],
  ['원본 정답','VALID 응답이 원본 reference와 수치 일치. 원본에 대한 DG 판정은 제공되지 않습니다.'],
  ['원본 오답','VALID 응답의 수치 불일치 또는 answer=null. 형식 오류 / 미실행은 판정 불가입니다.'],
  ['S / U / D','적용 판정 모두 S / 하나 이상 U / U가 없고 D 포함. Numeric은 DG, Abstention은 ARV와 DG를 적용합니다.'],
  ['선택 Numeric','NS/(NS+NU 원본 reference 불일치). NU reference 일치 / 비교 불가는 별도 표시합니다.'],
  ['선택 Abstention','AS/(AS+AU 중 ARV / DG 모두 U). 나머지 AU 조합을 제외 / 별도 표시합니다.'],
  ['집계 범위','IC-v1, IC-v2, IC-R, EA1, EA2. IC-source는 별도 OVS 분석이 필요하므로 포함하지 않습니다.'],
  ['분석 없는 모델','평가 계획과 원본 성적은 표시합니다. 검토 분모가 0이면 비율은 N/A입니다.'],
  ['정답 기준','원본 reference는 변형의 독립 GOLD가 아닙니다. TP/FP/FN/TN과 Abstention F1을 산출하지 않습니다.'],
  ['합계','네 조건이 모두 지원되면 네 조건 합산. 같은 문항을 조건별 시행으로 집계하며 비율 평균을 사용하지 않습니다.'],
  ['검토의 의미','저장된 LLM 판정입니다. VALID는 응답 계약 / 인용 검사를 통과했다는 뜻입니다.'],
  ['원자료','동일 파일명의 .data.json에 응답 ID, NASU 세부 분류, 판정 출처와 읽은 파일 SHA-256을 보관합니다.'],
  ['갱신','등록된 runs.json의 최신 저장 결과를 다시 읽습니다. 새 모델/run은 runs.json 또는 --run으로 지정합니다.']
];
const start=data.runs.length+10;
sheet.getRange(`A${start}:J${start+method.length-1}`).format.font={name:font,size:11,color:colors.ink};
sheet.getRange(`A${start}:J${start+method.length-1}`).format.rowHeight=28;
for(const [i,row] of method.entries()) sheet.getRange(`A${start+i}:B${start+i}`).values=[row];
sheet.getRange(`A${start}:A${start+method.length-1}`).format.font.bold=true;

function calcRate(rows,num,den) {
  const n=rows.reduce((s,r)=>s+num.reduce((a,k)=>a+r[k],0),0);
  const d=rows.reduce((s,r)=>s+den.reduce((a,k)=>a+r[k],0),0);
  return d?n/d:'N/A';
}

// Verify a changed source count updates a dependent rate, then restore it.
const first=groups[0];
const sourceRow=first.rows[0].excelRow;
const sourceCell=source.getRange(`K${sourceRow}`);
const initial=sourceCell.values[0][0];
sourceCell.values=[[initial+1]];
const initialS=first.rows.reduce((n,r)=>n+r.NS+r.AS,0);
const initialResolved=first.rows.reduce((n,r)=>n+r.NS+r.NU+r.AS+r.AU,0);
assert.ok(Math.abs(sheets.H1_NASU.getRange('L7').values[0][0]-(initialS+1)/(initialResolved+1))<1e-10,
  'Changing a source count must update the output rate');
sourceCell.values=[[initial]];
workbook.recalculate();
for(const check of [...numericRateChecks,...quadrantChecks]) {
  const actual=sheets[check.sheet].getRange(check.cell).values[0][0];
  if(typeof check.expected==='string') assert.equal(actual,check.expected,`${check.sheet}!${check.cell}`);
  else assert.ok(Math.abs(actual-check.expected)<1e-10,`${check.sheet}!${check.cell}: ${actual} != ${check.expected}`);
}
for(const check of quadrantReconciliations) {
  const actual=check.cells.reduce((n,cell)=>n+quadrant.getRange(cell).values[0][0],0);
  assert.equal(actual,check.expected,`Selected counts plus unresolved/unreviewed: ${check.cells.join(',')}`);
}
const scan=await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!',
  options:{useRegex:true,maxResults:30},maxChars:2500});
console.log('Formula checks:',numericRateChecks.length+quadrantChecks.length,scan.ndjson);
console.log((await workbook.inspect({kind:'table',range:'H1_NASU!A7:O11',include:'values,formulas',
  tableMaxRows:5,tableMaxCols:15,maxChars:3500})).ndjson);
if(previewDir) {
  await fs.mkdir(previewDir,{recursive:true});
  for(const name of names) {
    if(name==='H1_NASU_Quadrant' || name==='H1_U세부분류' || quadrantPreviewOnly) continue;
    const last=name===inputName?'Y8':name==='H1H2_실행정보'?'J14':'O13';
    const blob=await workbook.render({sheetName:name,range:`A1:${last}`,scale:1.5,format:'png'});
    await fs.writeFile(path.join(previewDir,name+'.png'),new Uint8Array(await blob.arrayBuffer()));
  }
  for(const view of quadrantViews) {
    const first=view.index===0?1:view.start-1;
    for(const [sheetName,left,right,prefix] of [
      [quadrant.name,'A','O','H1_NASU_Quadrant'],
      [quadrant.name,'P','AD','H1_Selected_Quadrant'],
      [quadrant.name,'AE','AS','H1_U_Adjacent_Quadrant'],
      [uSheet.name,'A','O','H1_U_Quadrant'],
      ...(view.index===0?[[quadrant.name,'P','AS','H1_Selected_U'],[quadrant.name,'A','AS','H1_Overview']]:[])
    ]) {
      const blob=await workbook.render({sheetName,range:`${left}${first}:${right}${view.end}`,scale:1.5,format:'png'});
      await fs.writeFile(path.join(previewDir,`${prefix}-${view.index+1}.png`),new Uint8Array(await blob.arrayBuffer()));
    }
  }
  if(!quadrantPreviewOnly) {
    const definitions=await workbook.render({sheetName:'H1H2_실행정보',range:`A${start}:J${start+method.length-1}`,scale:1.5,format:'png'});
    await fs.writeFile(path.join(previewDir,'definitions.png'),new Uint8Array(await definitions.arrayBuffer()));
  }
}
const file=await SpreadsheetFile.exportXlsx(workbook);
await file.save(output);
console.log(`Exported ${names.length} worksheets to ${output}`);
