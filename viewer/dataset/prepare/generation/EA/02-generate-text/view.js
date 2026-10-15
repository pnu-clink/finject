function eaTextPreview(p,r,preview){
 p.append(el('h2','',preview.status==='GENERATED'?'실제 생성된 문장 · EA':'문장 편집 미리보기 · EA'),el('p','banner',preview.status==='GENERATED'?'LLM이 반환한 삭제 patch를 스키마·허용 범위 검사 후 적용한 본문입니다. '+auditStatus(r)+'.':'저장된 삭제 계획을 적용한 수정본 초안입니다. 문장 생성용 LLM 호출·최종 의미 검사는 아직 진행하지 않았습니다.'));
 eaStage15Review(p,r);p.append(el('p','',eaInputName(preview.python.missing_facts[0])+' 항목은 남기고 금액만 알 수 없게 합니다. 다른 입력값과 질문·계산법은 그대로 유지합니다.'));
 const legend=el('div','legend');legend.append(el('mark','diff-del','붉은색 · 삭제할 금액 표현'));p.append(legend);
 const cols=el('div','cols ea-text-stages'),before=el('div','box'),after=el('div','box ea-sentence-pair'),span=preview.rewritten_sentence;let taggedSentence=null;
 before.append(el('h3','','① 원문 · 전체 본문'),marked(preview.original_context,preview.intermediate?.patches||preview.patches,'before'));cols.append(before);
 if(preview.intermediate){const intermediate=el('div','box');intermediate.append(el('h3','','② 임시 태그 · 바꿀 문장 강조'));const prose=el('div','prose'),patch=preview.intermediate.patches[0],edit=preview.patches[0];
  if(span){const sourceEnd=span.end+(edit.end-edit.start)-Array.from(edit.text).length,highlight=el('mark','ea-tagged-sentence');highlight.append(document.createTextNode(sliceText(preview.original_context,span.start,patch.start)),el('mark','ea-delete-tag',preview.intermediate.tag),document.createTextNode(sliceText(preview.original_context,patch.end,sourceEnd)));taggedSentence=highlight.textContent;prose.append(document.createTextNode(sliceText(preview.original_context,0,span.start)),highlight,document.createTextNode(sliceText(preview.original_context,sourceEnd)));}
  else prose.textContent=preview.intermediate.context;
  intermediate.append(prose,el('p','small','색이 있는 문장을 아래 3번 문장으로 다듬습니다. 태그는 제작용입니다.'));cols.append(intermediate);}
 const rewritten=el('div','prose preview-prose'),sentence=span?sliceText(preview.preview_context,span.start,span.end):null;
 rewritten.append(el(sentence?'mark':'span',sentence?'ea-rewritten-sentence':'',sentence||'변경 문장 범위 기록이 없습니다.'));
 after.append(el('h3','','③ 변경 전·후 문장 비교 (②의 색상 부분)'));
 realizationEvidence(after,r,preview.status==='GENERATED');
 if(taggedSentence!==null&&sentence!==null)renderEaSentenceDiff(after,taggedSentence,sentence);
 else after.append(el('p','small','변경 전 문장 범위 기록이 없어 수정문만 표시합니다.'),rewritten);
 const status=el('span','small');status.setAttribute('role','status');const copy=button('변경 문장 복사',async()=>{try{await copyJsonText(sentence,after);status.textContent='변경 문장 복사 완료'}catch(error){status.textContent=error.message}});copy.disabled=!sentence;after.append(copy,status);cols.append(after);p.append(cols);
 for(const patch of preview.patches)p.append(box('삭제한 부분',patch.before),el('p','small',preview.status==='GENERATED'?'선택한 금액을 소개하는 표현만 제거했습니다.':patch.purpose));
 p.append(box('질문 · 그대로 유지',preview.question),box('이 계산 경로의 결과',eaInputName(preview.python.missing_facts[0])+' 값이 없어서 합계 계산을 완료할 수 없습니다. 수치 정답을 임의로 채우지 않습니다. 별도 모델의 실제 응답은 아닙니다.'));
 p.append(button('삭제 입력의 그래프 보기',()=>{tab=3;render()}));
 jsonBox(p,'문장·Python 코드·결측 그래프 연결',{target:preview.target,python:preview.python,graph_binding:preview.graph_binding,patches:preview.patches,preserved_evidence:preview.preserved_evidence});
 jsonBox(p,'삭제 위치·남은 금액·질문 보존 검사',preview.checks);
}
