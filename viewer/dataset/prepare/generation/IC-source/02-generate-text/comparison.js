function sourceComparisonText(r,preview){
 const div=el('div','prose preview-prose');
 try{for(const segment of sourceComparisonSegments(r,preview)){
  const styles={VALUE:['diff-add','IC-VALUE에서 추가한 값 주장'],SOURCE_A:['source-a-add','뒤쪽 원래 값(A)의 출처'],SOURCE_B:['source-b-add','추가 값(B)의 출처']};
  if(!segment.kind){div.append(document.createTextNode(segment.text));continue;}
  const [cls,label]=styles[segment.kind]||styles.VALUE,mark=el('mark',cls,segment.text);mark.title=label;div.append(mark);
 }}catch(error){div.append(el('p','banner',error.message+' 저장된 최종 본문을 그대로 표시합니다.'),document.createTextNode(preview.preview_context));}
 return div;
}
