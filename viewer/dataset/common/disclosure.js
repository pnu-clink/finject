// Shared across cases and runs; storage failure still retains this page's state.
const viewerDisclosureState=new Map();
function viewerDisclosure(key,title,content,defaultOpen=true){
 const storageKey='finarch-viewer-disclosure:'+key,area=el('details','small');
 if(!viewerDisclosureState.has(key)){let open=defaultOpen;try{const saved=localStorage.getItem(storageKey);if(saved!==null)open=saved==='open';}catch{}viewerDisclosureState.set(key,open);}
 area.open=viewerDisclosureState.get(key);area.append(el('summary','',title),content);
 area.addEventListener('toggle',()=>{if(!area.isConnected)return;viewerDisclosureState.set(key,area.open);try{localStorage.setItem(storageKey,area.open?'open':'closed');}catch{}});
 return area;
}
