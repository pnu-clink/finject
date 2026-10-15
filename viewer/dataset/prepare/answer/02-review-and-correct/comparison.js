function renderWorkingComparison(panel,row){
 const comparison=row.run.artifacts['data-comparison.json'];if(!comparison)return;
 const section=el('section','panel');section.append(el('h2','','Q · C · A 보정 전·후 비교'),el('p','small','왼쪽: 보정 전 참고 데이터 · 오른쪽: 후속 처리에 사용할 데이터. 붉은색은 변경 전, 초록색은 변경 후입니다. 변경된 단어 전체에 빨간 밑줄을 표시합니다. 사람 승인은 별도입니다.'));
 const columns=el('div','cols'),left=el('div','box'),right=el('div','box');left.append(el('h3','','참고 데이터 · reference-data.json'));right.append(el('h3','','현재 데이터 · data.json'));
 for(const [field,title] of [['question','Q · 질문'],['context','C · 본문'],['reference_answer','A · 정답']]){const a=el('div','prose'),b=el('div','prose');left.append(el('h4','',title),a);right.append(el('h4','',title),b);for(const op of eaSentenceDiff(String(comparison.reference_qca[field]),String(comparison.current_qca[field]))){if(op.kind==='equal'){a.append(document.createTextNode(op.text));b.append(document.createTextNode(op.text));}else{for(const [parent,text,style] of [[a,op.before,'diff-del'],[b,op.after,'diff-add']]){const mark=el('mark',style,text);mark.style.cssText='text-decoration-line:underline;text-decoration-color:#c62828;text-decoration-thickness:2px;text-underline-offset:3px;text-decoration-skip-ink:none';parent.append(mark);}}}}
 columns.append(left,right);section.append(columns);panel.append(section);
}
