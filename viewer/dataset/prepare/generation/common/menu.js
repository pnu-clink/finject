function generationKind(variant){return variant.includes('ic-value')?'IC_VALUE':variant.includes('ic-source')?'IC_SOURCE':variant.includes('ic-relation')?'IC_RELATION':'EA';}
function generationGuide(row,variant,stage){
 const kind=generationKind(variant),intent={IC_VALUE:'원래 값과 충돌하는 값을 추가할 계획을 만듭니다.',IC_SOURCE:'값 충돌에 출처를 붙일 쪽을 정합니다.',IC_RELATION:'원래 수치와 충돌하는 관계를 추가할 계획을 만듭니다.',EA:'계산에 필요한 입력 근거를 삭제할 계획을 만듭니다.'}[kind];
 const guides={
  '01-perturbation':{title:intent,steps:[
   ['01-input.json · Python','승인된 원문·Python 코드·계산 그래프를 읽습니다.',[['입력',['01-input.json']]]],
   ['02-graph.json · Python',intent,[['변경 그래프',['02-graph.json']]]],
   ['03-result.json · Python','변경 계획과 계산 결과를 저장합니다. 최종 문장의 의미 검사는 03-validation에서 확인합니다.',[['계획·검사',['03-result.json']],['이전 차수 계획',['01-inherited-plan.json']]]]
  ]},
  '02-generate-text':{title:'변경 계획을 문장으로 표현하고 원문에 반영합니다.',steps:[
   ['01-input · Python',kind==='IC_SOURCE'?'대응하는 IC-VALUE 본문과 출처 배정 계획을 읽습니다.':'원문과 허용된 편집 위치·변경 요소를 생성 입력으로 준비합니다.',[['생성 입력',['01-input.json']]]],
   ['02-LLM-call · LLM',variant==='02-ic-value-after'?'앞 유형에서 만든 동일 문장을 뒤 위치로 옮깁니다. 재사용 기록에 새 호출 0회가 표시됩니다.':'허용된 위치에 넣거나 지울 문장을 생성합니다. 실제 프롬프트·입력·원응답을 남깁니다.',[['원응답',['02-LLM-call/02-raw-response.json']],['문장 재사용',['02-place-paired-sentence.json']]]],
   ['03-edit-check · Python','응답 형식·편집 위치·보존 조건을 검사합니다.',[['편집 검사',['03-edit-check.json']]]],
   ['04-observation / 05-patches · Python','수정된 본문·질문과 변경 구간을 저장합니다. 실패 응답의 미리보기는 진단용으로 표시합니다.',[['최종 본문',['04-observation.json']],['변경 구간',['05-patches.json']]]]
  ]},
  '03-validation':{title:'완성된 문장이 변경 의도와 보존 조건을 만족하는지 검사합니다.',steps:[
   ['01-input · Python','원본·최종 본문·질문·변경 의도를 검사 입력으로 묶습니다.',[['검사 입력',['01-input.json']]]],
   ['audit · LLM','의도한 변경, 원문 보존, 불필요한 의미 변화 여부를 판단합니다.',[['모델 원응답',['audit/02-raw-response.json']]]],
   ['03-result · Python','모델 응답을 검사하고 항목별 판정·이유를 기록합니다. 사람의 최종 승인은 별도입니다.',[['검사 결과',['03-result.json']],['응답 형식 검사',['audit/03-result/schema-check.json']]]],
   ['04-comparison · Python','검사에 사용한 원본과 생성 본문을 비교 자료로 저장합니다.',[['비교 자료',['04-comparison.json']]]]
  ]},
  '05-human-review':{title:'생성 문항의 변경 내용과 검사 근거를 사람이 확인합니다.',steps:[
   ['01-result · Python','자동 검사 결과와 최종 본문을 검토 자료로 모읍니다.',[['검토 자료',['01-result.json']]]],
   ['02-record-decision · 사람','그래프·문장·검증 결과를 확인한 뒤 승인·제외·대기를 기록합니다.',[['저장 판정',['02-record-decision/decision.json']]]]
  ]}
 };if(kind==='EA'&&stage==='03-validation')guides[stage].steps.push(['07-ea-inverse-review · LLM + Python','삭제 후 Q/C만 별도 LLM에 전달해 역산 여부·근거·식을 기록합니다. Python은 형식·표시 위치만 확인합니다. true/false 모두 제작 판정을 유지합니다.',[['최신 역산 기록 참조',['07-ea-inverse-review/latest.ref.json']]]]);return guides[stage];
}
function generationRow(row,variant){
 const prefix=variant+'/',artifacts=Object.fromEntries(Object.entries(row.run.generation||{}).filter(([path])=>path.startsWith(prefix)).map(([path,value])=>[path.slice(prefix.length),value]));
 for(const [path,value] of Object.entries(artifacts)){if(path.startsWith('04-human-review/'))artifacts[path.replace('04-human-review/','05-human-review/')]=value;}
 const feedback_sources=Object.fromEntries(Object.entries(row.run.generation_feedback_sources||{}).filter(([path])=>path.startsWith(prefix)).map(([path,value])=>[path.slice(prefix.length),value]));
 return {...row,axis:generationKind(variant),label:artifacts['run.json']?.label||variant,run:{...row.run,feedback_sources,path:stageFilePath(row,variant,variant+'/run.json').replace(/\/run.json$/,''),artifacts}};
}
function generationCallSource(row,variant){
 const selected=generationRow(row,variant),pair=selected.run.artifacts['02-generate-text/02-place-paired-sentence.json'];
 if(!pair||savedMenuCalls(selected,'02-generate-text/').length)return selected;
 const source=Object.entries(row.run.generation||{}).find(([path,value])=>/^[^/]+\/run\.json$/.test(path)&&value?.path===pair.source);
 return source?generationRow(row,source[0].split('/')[0]):selected;
}
function renderGenerationContent(panel,row,variant,stage){
 const reuse=row.run.generation?.[variant+'/run.json']?.source_reuse;if(reuse)panel.append(el('p','small','기존 EA 본문과 제작 판정을 복사한 확인용 실행입니다. 이번에 새로 호출한 검사는 EA 역산 검토뿐입니다. 출처: '+(reuse.path||'저장된 원본')));
 if(stage==='04-exception-handler'){renderStageRecords(panel,generationRow(row,variant),stage);return;}
 const origin=row.run.generation_origins?.[variant];if(origin&&origin!==DATA.batch.round)panel.append(el('p','small',`${origin}에서 생성한 결과를 유지합니다. 현재 차수의 새 호출 결과가 아닙니다.`));
 if(stage==='01-perturbation'){const renderers={IC_VALUE:renderValuePerturbation,IC_SOURCE:renderSourcePerturbation,IC_RELATION:renderRelationPerturbation,EA:renderEaPerturbation};renderers[generationKind(variant)](panel,row,variant);return;}
 if(stage==='02-generate-text'){renderGenerationText(panel,row,variant);return;}
 if(stage==='03-validation'){renderGenerationValidation(panel,row,variant);return;}
 if(stage==='05-human-review'){renderGenerationReview(panel,row,variant);}
}
