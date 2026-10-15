function renderEaSentenceDiff(parent,before,after){
 const diff=el('div','ea-unified-diff');diff.setAttribute('aria-label','EA 문장 변경 비교');
 const row=(kind,sign,label,value)=>{const line=el('div','ea-diff-row ea-diff-'+kind);line.append(el('span','ea-diff-sign',sign),el('span','ea-diff-label',label),el('span','ea-diff-text'+(!value?' ea-diff-empty':''),value||'∅ 없음'));diff.append(line);};
 const blocks=eaSentenceDiff(before,after);
 parent.append(el('p','small',before===after?'차이 없음 · 두 문장이 같습니다.':'공통 부분은 한 번만 표시합니다. − 삭제 / + 추가를 위아래로 비교하세요.'));
 for(const block of blocks){if(block.kind==='equal')row('equal','=','공통',block.text);else{row('delete','−','변경 전',block.before);row('insert','+','변경 후',block.after);}}
 parent.append(diff);
}
