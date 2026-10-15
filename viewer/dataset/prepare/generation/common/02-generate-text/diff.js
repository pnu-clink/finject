function eaSentenceDiff(before,after){
 const tokenize=s=>s.match(/\[[^\]\r\n]*\]|[\p{L}\p{N}_]+|[^\S\r\n]+|\r\n|\r|\n|[^\p{L}\p{N}_\s]/gu)||[];
 const a=tokenize(before),b=tokenize(after),ops=[];
 const push=(kind,text)=>{if(!text)return;const last=ops.at(-1);if(last?.kind===kind)last.text+=text;else ops.push({kind,text});};
 if(a.length*b.length>1000000){
  let start=0,end=0;while(start<Math.min(a.length,b.length)&&a[start]===b[start])start++;
  while(end<Math.min(a.length,b.length)-start&&a[a.length-1-end]===b[b.length-1-end])end++;
  push('equal',a.slice(0,start).join(''));push('delete',a.slice(start,a.length-end).join(''));push('insert',b.slice(start,b.length-end).join(''));push('equal',a.slice(a.length-end).join(''));
 }else{
  const width=b.length+1,dp=new Uint32Array((a.length+1)*width);
  for(let i=a.length-1;i>=0;i--)for(let j=b.length-1;j>=0;j--)dp[i*width+j]=a[i]===b[j]?dp[(i+1)*width+j+1]+1:Math.max(dp[(i+1)*width+j],dp[i*width+j+1]);
  let i=0,j=0;while(i<a.length||j<b.length){if(i<a.length&&j<b.length&&a[i]===b[j]){push('equal',a[i++]);j++;}else if(i<a.length&&(j===b.length||dp[(i+1)*width+j]>=dp[i*width+j+1]))push('delete',a[i++]);else push('insert',b[j++]);}
 }
 const blocks=[];let change=null;
 const flush=()=>{if(change){blocks.push(change);change=null;}};
 for(let i=0;i<ops.length;i++){const op=ops[i];if(op.kind==='equal'&&!(change&&/^\s+$/.test(op.text)&&ops[i+1]&&ops[i+1].kind!=='equal')){flush();blocks.push(op);}else{change??={kind:'change',before:'',after:''};if(op.kind!=='insert')change.before+=op.text;if(op.kind!=='delete')change.after+=op.text;}}
 flush();return blocks;
}
