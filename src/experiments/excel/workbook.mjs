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
const names = ['H1_NASU_Quadrant', 'H1_NASU', 'H1_SelectedMetrics', 'H1_U_Details', 'H2_CohortComparison', 'H2_ByVariant', 'H1H2_RunData', 'H1H2_RunGuide'];
const sheets = Object.fromEntries(names.map(n => [n, workbook.worksheets.add(n)]));
const colors = {ink:'#172B4D', header:'#304967', soft:'#F0F4F8', line:'#CBD5E1', red:'#FCE8E6'};
const font = 'Arial';
const inputName = 'H1H2_RunData';
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
          labels:[dataset,run.label,g==='ALL'?'Total':g==='guided'?'ON':'OFF',r==='ALL'?'Total':r.toUpperCase()]});
      }
    }
  }
}

const numericRateChecks=[];
let sheet=sheets.H1_NASU;
opening(sheet,'H1. Form of response and supporting basis',[
  'The whole original group of 5So we\x27re going to do this, and we\x27re gonna do this, we\x27re just going to do that, and we are going to do it, and we will do this, so we\x27re doing this, and then we\x27re actually going to do the whole thing.',
  'S: All the appraisals are supported. U: One or more are unsupported. D: Uncertain. Miscalculation is excluded from the denominator.',
  'N: Numeric (number answer), A: Abstention (answer=null). D and subtest are not included in the denominator of the S ratio.'
],['Dataset','Model','Guided','Reasoning','Plan response','NS','NU','AS','AU','D','Unreviewed','The total S ratio','Numeric S ratio','Abstention S ratio','The completion rate'],groups.length);
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
value(quadrant,'B3','Up: Guided / Down: Unguided. Left: Reasoning OFF / Right: ON.');
quadrant.getRange('B4:N4').merge();
value(quadrant,'B4','NS/NU/AS/AU is the whole dry. D/M is excluded from the ratio denominator.');
quadrant.getRange('B5:N5').merge();
value(quadrant,'B5',`The storage data view is: ${data.generated_at}`);
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
    'N (numeric): numerical answer / A (abstention): authorized',
    'S (Supported): Applied judgments All S/U (Unsupported) More than one U/D (Undetermined): Judgments undefined',
    'NS: Based statistical response / NU: Based unsupported statistic response',
    'AS: Well-founded denial response / AU: Well-backed denial answer',
    'ARV: Reasons for authorisation validity / DG: Support for the final judgment basis / Misreview: No valid review results'
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
    formula(quadrant,status,`"Planned: originals "&TEXT(${total(seeds,'original_count')},"#,##0")&" entries × ${variantCount} = "&TEXT('H1_NASU'!E${sourceRow},"#,##0")&" entries / reviewed "&TEXT('H1_NASU'!E${sourceRow}-'H1_NASU'!K${sourceRow},"#,##0")&" entries"`);
    addCheck(quadrant,status,`Planned: originals ${seedCount.toLocaleString('en-US')} entries × ${variantCount} = ${expectedCount(group,'planned').toLocaleString('en-US')} entries / reviewed ${(expectedCount(group,'planned')-expectedCount(group,'F')).toLocaleString('en-US')} entries`);
  } else value(quadrant,status,'Conditions not in the evaluation plan');
  const cells={};
  for(const [kind,offset,dy,inputColumn] of [
    ['NS',0,2,'F'],['NU',3,2,'G'],['AS',0,4,'H'],['AU',3,4,'I']]) {
    const start=left+offset, end=start+2, fill=kind.endsWith('S')?'#E7F2EF':'#FBEDEC';
    const label={NS:'NS (nearly numerical response)',AS:'AS (nearly rejected response)'}[kind]||kind;
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
  blockCell(left,left+1,top+7,'D (uncertain)',{fill:'#F5F6F8',horizontalAlignment:'left'});
  const dCell=blockCell(left+2,left+2,top+7,'N/A',{fill:'#F5F6F8',horizontalAlignment:'right',numberFormat:'#,##0'});
  blockCell(left+3,left+4,top+7,'Unreviewed',{fill:'#F5F6F8',horizontalAlignment:'center'});
  const fCell=blockCell(left+5,left+5,top+7,'N/A',{fill:'#F5F6F8',horizontalAlignment:'right',numberFormat:'#,##0'});
  if(group) {
    formula(quadrant,dCell,`'H1_NASU'!J${sourceRow}`);
    formula(quadrant,fCell,`'H1_NASU'!K${sourceRow}`);
  }
  for(const [cell,fields] of [[dCell,['ND','AD']],[fCell,['F']]]) quadrantChecks.push({sheet:quadrant.name,cell,
    expected:group?group.rows.reduce((s,r)=>s+fields.reduce((a,k)=>a+r[k],0),0):'N/A'});
  const sumAll=`${cells.NS}+${cells.NU}+${cells.AS}+${cells.AU}`;
  const metrics=[
    ['S ratio\n(Sighs)','(NS+AS)/\n(NS+NU+AS+AU)',`${cells.NS}+${cells.AS}`,sumAll,['NS','AS'],['NS','NU','AS','AU']],
    ['The NS ratio\n(Approximate numbers answer)','NS/(NS+NU)',cells.NS,`${cells.NS}+${cells.NU}`,['NS'],['NS','NU']],
    ['AS rate\n(Nearly rejected response)','AS/(AS+AU)',cells.AS,`${cells.AS}+${cells.AU}`,['AS'],['AS','AU']]
  ];
  metrics.forEach(([label,expression,num,den,nKeys,dKeys],i)=>{
    const row=top+8+i;
    blockCell(left,left+2,row,label,{font:{name:font,size:11,bold:true,color:colors.ink},wrapText:true,rowHeight:38});
    blockCell(left+3,left+4,row,expression,{font:{name:font,size:11,color:'#52647A'},horizontalAlignment:'center',wrapText:true});
    const cell=blockCell(left+5,left+5,row,'N/A',{numberFormat:'0.00%',font:{name:font,size:11,bold:true,color:colors.ink},horizontalAlignment:'right'});
    if(group) formula(quadrant,cell,ratio(num,den));
    quadrantChecks.push({sheet:quadrant.name,cell,expected:group?calcRate(group.rows,nKeys,dKeys):'N/A'});
  });
  blockCell(left,left+1,top+11,'S is the denominator of the ratio.',{font:{name:font,size:11,color:'#52647A'}});
  blockCell(left+2,left+4,top+11,'NS+NU+AS+AU',{font:{name:font,size:11,color:'#52647A'},horizontalAlignment:'center'});
  const denominator=blockCell(left+5,left+5,top+11,'N/A',{numberFormat:'#,##0',horizontalAlignment:'right'});
  if(group) formula(quadrant,denominator,sumAll);
  blockCell(left,right,top+12,group?'The NS/AS ratio is the S ratio within each response form.':'No data. 0It\x27s not a statistic.',
    {font:{name:font,size:10,color:'#52647A'},horizontalAlignment:'center'});
  full.format.borders={preset:'outside',style:'thin',color:'#94A3B8'};
}

quadrantModels.forEach((model,i)=>{
  const top=7+i*36;
  const meta=data.runs.find(r=>r.run===model.run);
  blockCell(1,13,top,`${model.label}  /  ${model.dataset}`,{font:{name:font,size:16,bold:true,color:colors.ink}});
  quadrant.getRange(`B${top}:N${top}`).format.borders={bottom:{style:'thin',color:colors.line}};
  blockCell(1,13,top+1,`${model.run}   |   Judge: ${meta.judge_models.join('; ')||'Analysis is missing'}`,
    {font:{name:font,size:10,color:'#52647A'}});
  glossary(quadrant,1,13,top+2);
  panel(model,'guided','off',1,top+3);
  panel(model,'guided','on',8,top+3);
  panel(model,'unguided','off',1,top+18);
  panel(model,'unguided','on',8,top+18);
  quadrantViews.push({index:i,label:model.label,start:top,end:top+35});
});

blockCell(16,28,2,'H1 Selection Quadrant',{font:{name:font,size:16,bold:true,color:colors.ink}});
blockCell(16,28,3,'It\x27s a model/condition like NASU, except for the sum = S + U + option.');
blockCell(16,28,4,'The D/microscopy also shows the star.');
blockCell(16,28,5,'N: Numeric / A: Abstention. Form uncertainty response is also kept separate.',
  {font:{name:font,size:11,color:'#52647A'}});

sheet=sheets.H1_SelectedMetrics;
opening(sheet,'H1. Support rate for selected Numeric/Abstention group',[
  'Numeric: S=NS, U=NU origin reference inconsistency. Abstention: S=AS, U=ARV/DG are all U-in AU.',
  'The selection ratio is S/(S+U). NU reference matches and AU mixed determinations are excluded from the selection denominator.',
  'NU\x27s original reference comparison is not the GOLD judgment of the variation. The form-indefinite response is included in the H1_NASU microscope.'
],['Dataset','Model','Guided','Reasoning','The response form','Select S','Select U.','The choice denominator.','S ratio','The U percentage','Except for the choice.','D','Unreviewed','The sum of the corresponding forms'],groups.length*2);
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
  cell(left,right,top+1,group?'So the sum is equal to S + U + Selection excluded.':'Conditions not in the evaluation plan',
    {font:{name:font,size:11,color:'#52647A'},horizontalAlignment:'center'});
  const tableHeader={fill:'#E8EDF3',font:{name:font,size:11,bold:true,color:colors.ink},horizontalAlignment:'center'};
  cell(left,left+1,top+2,'The response form',tableHeader);
  for(const [i,label] of ['S','U','Except for the choice.','Total'].entries()) cell(left+2+i,left+2+i,top+2,label,tableHeader);
  const totals=[];
  for(const [j,label] of ['N','A'].entries()) {
    const r=top+3+j, sourceRow=j?aRow:nRow;
    cell(left,left+1,r,label,{font:{name:font,size:12,bold:true,color:colors.ink},horizontalAlignment:'center'});
    const cells=[];
    for(const [i,key] of ['F','G','K'].entries()) {
      const address=cell(left+2+i,left+2+i,r,'N/A',{numberFormat:'#,##0',horizontalAlignment:'right',
        fill:i===0?'#E7F2EF':i===1?'#FBEDEC':'#F4F0E7'});
      if(group) formula(quadrant,address,`'H1_SelectedMetrics'!${key}${sourceRow}`);
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
  for(const [dy,label,sourceColumn,fields] of [[5,'D (uncertain)','L',['ND','AD']],[7,'Unreviewed','M',null]]) {
    cell(left,left+1,top+dy,label,{fill:'#F5F6F8'});
    for(const [j,type] of ['N','A'].entries()) {
      cell(left+2+j*2,left+2+j*2,top+dy,type,{fill:'#F5F6F8',horizontalAlignment:'center'});
      const address=cell(left+3+j*2,left+3+j*2,top+dy,'N/A',{fill:'#F5F6F8',numberFormat:'#,##0',horizontalAlignment:'right'});
      if(group) formula(quadrant,address,`'H1_SelectedMetrics'!${sourceColumn}${j?aRow:nRow}`);
      const expected=!group?'N/A':fields?expectedCount(group,fields[j]):data.responses.filter(x=>
        x.run===group.run && x.dataset===group.dataset && x.model===group.model && x.prompt_condition===guided &&
        x.reasoning===reasoning && x.action===type && x.nasu==='F').length;
      addCheck(quadrant,address,expected);
      extras.push(address);
    }
  }
  cell(left,left+1,top+8,'Form unknown',{font:{name:font,size:11,color:'#52647A'}});
  cell(left+2,left+4,top+8,'N/A indistinguishable',{font:{name:font,size:11,color:'#52647A'},horizontalAlignment:'center'});
  const unknown=cell(left+5,left+5,top+8,'N/A',{numberFormat:'#,##0',horizontalAlignment:'right'});
  if(group) formula(quadrant,unknown,`'H1_NASU'!K${found+7}-'H1_SelectedMetrics'!M${nRow}-'H1_SelectedMetrics'!M${aRow}`);
  addCheck(quadrant,unknown,!group?'N/A':data.responses.filter(x=>
    x.run===group.run && x.dataset===group.dataset && x.model===group.model && x.prompt_condition===guided &&
    x.reasoning===reasoning && x.action==='UNKNOWN' && x.nasu==='F').length);
  cell(left,left+1,top+9,'The response form',tableHeader);
  cell(left+2,left+3,top+9,'S ratio',tableHeader);
  cell(left+4,left+5,top+9,'The U percentage',tableHeader);
  for(const [j,type] of ['N','A'].entries()) {
    cell(left,left+1,top+10+j,type,{horizontalAlignment:'center',font:{name:font,size:11,bold:true,color:colors.ink}});
    for(const [i,sourceColumn] of ['I','J'].entries()) {
      const address=cell(left+2+i*2,left+3+i*2,top+10+j,'N/A',{numberFormat:'0.00%',horizontalAlignment:'right',
        font:{name:font,size:11,bold:true,color:colors.ink}});
      if(group) formula(quadrant,address,`'H1_SelectedMetrics'!${sourceColumn}${j?aRow:nRow}`);
      addCheck(quadrant,address,!group?'N/A':calcRate(group.rows,
        [i?(j?'AU_U_U':'NU_MISMATCH'):(j?'AS':'NS')],j?['AS','AU_U_U']:['NS','NU_MISMATCH']));
    }
  }
  cell(left,right,top+12,'S/(S+U) / U/(S +U)  Selection excluded / D/ Miscreen excluded denominator',
    {font:{name:font,size:10,color:'#52647A'},horizontalAlignment:'center'});
  quadrant.getRange(`${col(left)}${top}:${col(right)}${top+12}`).format.borders={preset:'outside',style:'thin',color:'#94A3B8'};
  if(group) quadrantReconciliations.push({cells:[...totals,...extras,unknown],expected:expectedCount(group,'planned')});
}
const quadrantReconciliations=[];
quadrantModels.forEach((model,i)=>{
  const top=7+i*36, meta=data.runs.find(r=>r.run===model.run);
  blockCell(16,28,top,`${model.label}  /  ${model.dataset}`,{font:{name:font,size:16,bold:true,color:colors.ink}});
  blockCell(16,28,top+1,`Judge: ${meta.judge_models.join('; ')||'Analysis is missing'}`,{font:{name:font,size:10,color:'#52647A'}});
  glossary(quadrant,16,28,top+2);
  selectedPanel(model,'guided','off',16,top+3);
  selectedPanel(model,'guided','on',23,top+3);
  selectedPanel(model,'unguided','off',16,top+18);
  selectedPanel(model,'unguided','on',23,top+18);
  blockCell(16,28,top+32,'Select excluded / Right U Details',
    {font:{name:font,size:11,bold:true,color:colors.ink},fill:'#F4F0E7',wrapText:true});
  blockCell(16,28,top+33,'N: The original gold match/comparison value of NU is excluded, and the number is the same as the original answer, but DG is the U-person answer.',
    {font:{name:font,size:11,color:'#52647A'},wrapText:true,rowHeight:55});
  blockCell(16,28,top+34,'A: ARV and DG of the AU leave only the U-person response to the selection U. The rest of the AU is excluded, and included in the entire NASU.',
    {font:{name:font,size:11,color:'#52647A'},wrapText:true,rowHeight:55});
});

sheet=sheets.H1_U_Details;
const uSheet=sheet;
baseStyle(uSheet,quadrantModels.length*36+6,30);
uSheet.getRange(`A1:O${quadrantModels.length*36+6}`).format.columnWidth=11;
for(const c of ['A','H','O','P']) uSheet.getRange(`${c}1:${c}${quadrantModels.length*36+6}`).format.columnWidth=3;
const uCell=(...args)=>blockCellOn(uSheet,...args);
uCell(1,13,2,'H1 U Detailed Classification Quadrant',{font:{name:font,size:16,bold:true,color:colors.ink}});
uCell(1,13,3,'Up: Guided / Down: Unguided. Left: Reasoning OFF / Right: ON.');
uCell(1,13,4,'Gold is the original reference, ARV S/DG S is the AS, so it\x27s excluded from the AU sum.');
uCell(1,13,5,'And the AU that\x27s not exactly blended is also shown with two stars.',{font:{name:font,size:11,color:'#52647A'}});
// Retain the existing flat detail table to the right of the new panels.
value(uSheet,'Q2','H1. The full detailed classification of unsupported responses');
uSheet.getRange('Q2').format.font={name:font,size:16,bold:true,color:colors.ink};
value(uSheet,'Q3','Reference is the original answer. The sum of three NU-scales is NU, and AU-scales are AU.');
value(uSheet,'Q4','DG: Supporting the basis of the final judgment. S=SUPPORTED, U=UNSUPPORRED, D=UNDETERMINED.');
const uFields=['NU','NU_MATCH','NU_MISMATCH','NU_UNKNOWN','AU','AU_U_U','AU_S_U','AU_U_S','AU_D_U','AU_U_D'];
header(uSheet,6,['Dataset','Model','Guided','Reasoning','Now, the whole thing.','NU ref matched','NU ref is inconsistent','NU ref Unknown',
  'The whole AU.','ARV U DG U','ARV S DG U','ARV U DG S','ARV D DG U','ARV U DG D'],16);
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
    if(group) formula(target,address,`'H1_U_Details'!${col(20+uFields.indexOf(key))}${r}`);
    addCheck(target,address,expectedCount(group,key));
  };
  uCell(left,right,top,`${guided==='guided'?'Guided':'Unguided'} / Reasoning ${reasoning.toUpperCase()}`,
    {fill:guided==='guided'?colors.header:'#52647A',font:{name:font,size:12,bold:true,color:'#FFFFFF'},horizontalAlignment:'center'});
  target.getRange(`${col(left)}${top}:${col(right)}${top}`).format.rowHeight=30;
  target.getRange(`${col(left)}${top+6}:${col(right)}${top+6}`).format.rowHeight=26;
  const status=uCell(left,right,top+1,group?'':'Conditions not in the evaluation plan',
    {font:{name:font,size:11,color:'#52647A'},horizontalAlignment:'center'});
  if(group) formula(target,status,`"Planned "&TEXT('H1_NASU'!E${r},"#,##0")&" entries / reviewed "&TEXT('H1_NASU'!E${r}-'H1_NASU'!K${r},"#,##0")&" entries"`);
  for(const [dy,label,key] of [[2,'Now, the whole thing.','NU'],[3,'NU Gold match','NU_MATCH'],[4,'The NU Gold match','NU_MISMATCH'],[5,'NU Gold is not comparable','NU_UNKNOWN'],[6,'The whole AU.','AU']]) {
    const major=dy===2||dy===6;
    const fill=major?'#E8EDF3':key==='NU_MISMATCH'?'#FBEDEC':['NU_MATCH','NU_UNKNOWN'].includes(key)?'#F4F0E7':'#FFFFFF';
    const style={fill,font:{name:font,size:11,bold:major,color:colors.ink}};
    uCell(left,left+3,top+dy,label,style);
    const address=uCell(left+4,right,top+dy,'N/A',{...style,numberFormat:'#,##0',horizontalAlignment:'right'});
    link(address,key);
  }
  const head={fill:'#E8EDF3',font:{name:font,size:11,bold:true,color:colors.ink},horizontalAlignment:'center'};
  for(const [j,label] of ['ARV separation','DG S','DG U'].entries()) uCell(left+j*2,left+j*2+1,top+7,label,head);
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
  uCell(left,right,top+12,'The gray can is AS and not included in the AU sum.',
    {font:{name:font,size:10,color:'#52647A'},horizontalAlignment:'center'});
  target.getRange(`${col(left)}${top}:${col(right)}${top+12}`).format.borders={preset:'outside',style:'thin',color:'#94A3B8'};
}
function unsupportedNotes(target,left,right,top) {
  const notes=[
    ['NU Gold: Gold is the original answer.\nMatching: The numbers are the same as the original answer, but DG is U. Explanation/calculation/basic does not support the numerical answer.\nM: DG is U, and the number is different from the original answer.','#F4F0E7'],
    ['ARV S/DG U: The jurisdictional privilege is valid, but the explanation and the basis of the response is not sufficient to support the final jurisdiction.\nThe specific causes of the calculation errors, etc., should be determined by the DG\x27s judgment of each response.','#F7F0E5'],
    ['ARV U/DG U: The case is that the justification of the proposed sovereignty and final sovereigns are not supported.\nThis judgment alone does not confirm that the case itself is unnecessary.','#FBEDEC']
  ];
  notes.forEach(([text,fill],i)=>blockCellOn(target,left,right,top+32+i,text,
    {fill,font:{name:font,size:11,color:'#52647A'},wrapText:true,rowHeight:58}));
}
quadrantModels.forEach((model,i)=>{
  const top=7+i*36, meta=data.runs.find(r=>r.run===model.run);
  uCell(1,13,top,`${model.label}  /  ${model.dataset}`,{font:{name:font,size:16,bold:true,color:colors.ink}});
  uCell(1,13,top+1,`${model.run}   |   Judge: ${meta.judge_models.join('; ')||'Analysis is missing'}`,
    {font:{name:font,size:10,color:'#52647A'}});
  glossary(uSheet,1,13,top+2);
  unsupportedPanel(model,'guided','off',1,top+3);
  unsupportedPanel(model,'guided','on',8,top+3);
  unsupportedPanel(model,'unguided','off',1,top+18);
  unsupportedPanel(model,'unguided','on',8,top+18);
  unsupportedNotes(uSheet,1,13,top);
});

// Align the same U breakdown beside the selected metrics on the first worksheet.
blockCell(31,43,2,'H1 U Detailed Classification Quadrant',{font:{name:font,size:16,bold:true,color:colors.ink}});
blockCell(31,43,3,'Up: Guided / Down: Unguided. Left: Reasoning OFF / Right: ON.');
blockCell(31,43,4,'N excluded = NU Gold match + uncomparable (Gold = original correct answer).');
blockCell(31,43,5,'Excluding A option = total AU − (both ARV and DG are U human touch).',{font:{name:font,size:11,color:'#52647A'}});
quadrantModels.forEach((model,i)=>{
  const top=7+i*36, meta=data.runs.find(r=>r.run===model.run);
  blockCell(31,43,top,`${model.label}  /  ${model.dataset}`,{font:{name:font,size:16,bold:true,color:colors.ink}});
  blockCell(31,43,top+1,`Judge: ${meta.judge_models.join('; ')||'Analysis is missing'}`,{font:{name:font,size:10,color:'#52647A'}});
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
sheet=sheets.H2_CohortComparison;
opening(sheet,'H2. Original right answer/wrong answer group variation correspondence comparison',[
  'The correct/wrong answer is whether the numerical match with the original reference is preserved as a discrete set that the original judges are not.',
  'The response rate of the correct group -- the response rate of a negative group is %p. Select N/A and separate the whole S/(S+U).',
  'Each row only connects the originals to the corresponding variations of the same model/condition.2It\x27s not an evaluation.'
],['Dataset','Model','Guided','Reasoning','The response indicator','The original answer is','Original answer mismatches','The original is unknown.',
  'The correct answer is group S.','The correct group denominator.','The percentage of the respondents','The answer is group S.','The group denominator of the answer.','The percentage of respondents','The difference is %p'],groups.length*3);
for(const [i,g] of groups.entries()) {
  for(const [j,[metric,label]] of [['ALL','So, the whole S/s+U.'],['N','Select Numeric'],['A','Choose Abstention']].entries()) {
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

sheet=sheets.H2_ByVariant;
const variantRecords=[];
for(const g of groups.filter(g=>g.g!=='ALL')) {
  for(const cohort of ['CORRECT','INCORRECT','UNKNOWN']) {
    for(const [variant,label] of Object.entries(data.variants)) {
      const rows=g.rows.filter(r=>r.cohort===cohort && r.variant===variant);
      if(rows.length) variantRecords.push({g,cohort,variant,label,rows});
    }
  }
}
opening(sheet,'H2. Group/variation denominator and corresponding results',[
  'S=NS+AS, U=NU+AU. The review denominator is S+U. It shows the process of subtracting D and subtracting subtraction.',
  'S/source is the fixed-group support response rate, different from the denominator S/(S+U. IC-source is a separate OVS analysis.'
],['Dataset','Model','Guided','Reasoning','The original group.','Variant','Original count','S','U','D','Unreviewed','S+U','S/(S+U)','S/A number of copies'],variantRecords.length);
variantRecords.forEach((x,i)=>{
  const r=i+7;
  sheet.getRange(`A${r}:F${r}`).values=[[...x.g.labels,{CORRECT:'Reference answer',INCORRECT:'Incorrect answer',UNKNOWN:'Unable to judge'}[x.cohort],x.label]];
  sheet.getRange(`G${r}:N${r}`).formulas=[[total(x.rows,'original_count'),combined(x.rows,'NS','AS'),combined(x.rows,'NU','AU'),
    combined(x.rows,'ND','AD'),total(x.rows,'F'),`H${r}+I${r}`,ratio(`H${r}`,`L${r}`),ratio(`H${r}`,`G${r}`)].map(v=>'='+v)];
  stripe(sheet,r,14);
});
percentages(sheet,['M','N'],variantRecords.length+6);
finishTable(sheet,variantRecords.length+6,14,'H2Variants');

sheet=sheets.H1H2_RunGuide;
opening(sheet,'The scope of the execution and the estimates',[
  `The result of the storage is viewed: ${data.generated_at}Call the new model: 0.`,
  'A02It uses only the latest save attempt. It doesn\x27t bring past success results instead of the latest failed results.'
],['Model','Run','The original implementation','The transformation plan.','A02 Planned','A02 VALID','A02 Fail','And then there\x27s the new attempt.','Analytical status','Judge'],data.runs.length);
data.runs.forEach((run,i)=>{
  const r=i+7, valid=run.judge_counts.VALID||0, failed=Object.entries(run.judge_counts).filter(([k])=>k!=='VALID').reduce((a,[,n])=>a+n,0);
  const status=!run.a02_requests?'Not run':valid===run.a02_requests?'A02 The whole VALID':'A02 Some review is possible';
  sheet.getRange(`A${r}:J${r}`).values=[[run.label,run.run,run.planned_originals,run.planned_variants,run.a02_requests,valid,failed,
    run.newer_attempts_during_read,status,run.judge_models.join('; ')||'Not run']];
  stripe(sheet,r,10);
});
sheet.getRange('A1:A45').format.columnWidth=27;
sheet.getRange('B1:B45').format.columnWidth=54;
sheet.getRange('I1:I45').format.columnWidth=26;
sheet.getRange('J1:J45').format.columnWidth=34;
const method=[
  ['H1','It\x27s not a NASU of the entire original group.'],
  ['H2','We compare the support ratios of the original right answer group and the wrong answer group in the same model/condition.'],
  ['Original answer','The valid response matches the reference to the original and the figure.'],
  ['The original is wrong.','VALID response is numerical inconsistency or answer=null. Format error/mismatch is undefinable.'],
  ['S / U / D','All the applicable judgments have no S/one or more U/U and include D. Numeric is DG, Abstention is ARV and DG.'],
  ['Select Numeric','NS/(NS+NU original reference inconsistency).'],
  ['Choose Abstention','ARV/DG of AS/(AS+AU are all U. Excluding the rest of the AU combinations/not showing stars.'],
  ['The range of estimates','IC-v1, IC-v2, IC-R, EA1, EA2. IC-source does not include any OVS analysis because it requires.'],
  ['The model is not analyzed.','The evaluation plan and the original score indicate that the review denominator is the 0The ratio is N/A.'],
  ['The right answer.','The original reference is not the independent GOLD of the variation, it doesn\x27t produce TP/FP/FN/TN and Abstention F1.'],
  ['Total','If all four conditions are supported, then the four conditions are added together, and we calculate the same case as a conditional implementation, and we don\x27t use a percentage average.'],
  ['The meaning of the review','It\x27s a stored LLM judgment, which means that VALID has passed the response contract/citation test.'],
  ['Raw materials','Answer ID to the same file name .data.json, NASU detailed classification, judgment source and read file SHA-256I keep it.'],
  ['Updated','I read the latest save results of the registered runs.json again, and the new model/run is either run.json or --run.']
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
    if(name==='H1_NASU_Quadrant' || name==='H1_U_Details' || quadrantPreviewOnly) continue;
    const last=name===inputName?'Y8':name==='H1H2_RunGuide'?'J14':'O13';
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
    const definitions=await workbook.render({sheetName:'H1H2_RunGuide',range:`A${start}:J${start+method.length-1}`,scale:1.5,format:'png'});
    await fs.writeFile(path.join(previewDir,'definitions.png'),new Uint8Array(await definitions.arrayBuffer()));
  }
}
const file=await SpreadsheetFile.exportXlsx(workbook);
await file.save(output);
console.log(`Exported ${names.length} worksheets to ${output}`);
