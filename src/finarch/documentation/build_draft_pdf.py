import json,re,subprocess,shutil,pathlib,html,collections,argparse
from bs4 import BeautifulSoup, NavigableString, Tag
from table_alignment import cell_alignment
ROOT=pathlib.Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description='Export the current English Draft to ACL LaTeX.')
parser.add_argument('--source',type=pathlib.Path,default=ROOT/'reports/run/20261003-paper-revision-draft/paper-review.json')
parser.add_argument('--output',type=pathlib.Path,default=ROOT/'paper/local-draft-en')
parser.add_argument('--legacy-layout',action='store_true',help='Use the historical fixed appendix layout.')
args=parser.parse_args(); CURRENT_LAYOUT=not args.legacy_layout
OUT=args.output; OUT.mkdir(parents=True,exist_ok=True)
(OUT/'sections').mkdir(exist_ok=True); (OUT/'figures').mkdir(exist_ok=True)
draft_bytes=args.source.read_bytes()
ss=[s for s in json.loads(draft_bytes) if not s.get('hidden_en')]
# The canonical Draft and original figure assets are read-only inputs.
for fn in ['acl.sty','acl_natbib.bst','review-line-numbers.tex']: shutil.copy2(ROOT/'paper/20261002-naacl-overleaf'/fn,OUT/fn)
# Parse bibliography metadata from current draft; use its current wording and author lists.
refs=BeautifulSoup(next(s['enhtml'] for s in ss if s['id']=='references'),'html.parser')
bibs=[]
for r in refs.select('.reference'):
 number=r.select_one('.reference-number')
 if number:number.decompose()
 p=r.p; a=p.find('a'); key=r['id'][4:]
 pre=''.join(str(c) for c in list(p.children)[:list(p.children).index(a)])
 pre=BeautifulSoup(pre,'html.parser').get_text().strip(); match=re.match(r'(.+)\. (\d{4})\.$',pre)
 if not match: raise ValueError(pre)
 author,year=match.groups(); author=author.replace(', and ',' and '); author=re.sub(r', (?![^,]*\.)',' and ',author) if False else author
 names=re.split(r', | and ',author); names=[n for n in names if n]
 names=['others' if 'others' in n else n for n in names]
 tail=''.join(str(c) for c in list(p.children)[list(p.children).index(a)+1:]); tail=BeautifulSoup(tail,'html.parser').get_text(' ',strip=True).lstrip('. ')
 title=a.get_text('',strip=False); url=a['href']; entry='@misc{'+key+',\n'
 for k,v in [('author',' and '.join(names)),('year',year),('title','{'+title+'}'),('howpublished',tail),('url',url)]:
  v=v.replace('&','\\&').replace('%','\\%'); entry+='  '+k+' = {'+v+'},\n'
 bibs.append(entry+'}\n')
(OUT/'references.bib').write_text('\n'.join(bibs))
charmap={'−':'-','⁺':r'\textsuperscript{+}','⁻':r'\textsuperscript{-}','κ':r'\ensuremath{\kappa}','Δ':r'\ensuremath{\Delta}','→':r'\ensuremath{\rightarrow}','×':r'\ensuremath{\times}','∈':r'\ensuremath{\in}','∅':r'\ensuremath{\varnothing}','≥':r'\ensuremath{\geq}','≤':r'\ensuremath{\leq}','✓':r'\ensuremath{\checkmark}','✗':'No','○':r'\ensuremath{\circ}','●':r'\ensuremath{\bullet}','²':r'\textsuperscript{2}','₁':r'\textsubscript{1}','₂':r'\textsubscript{2}','–':'--','—':'---','’':"'",'‘':"'",'“':'``','”':"''",'\xa0':'~','α':r'\ensuremath{\alpha}','β':r'\ensuremath{\beta}','±':r'\ensuremath{\pm}'}
def esc(s):
 return ''.join(charmap.get(c,{'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}.get(c,c)) for c in s)
def inline(n,wrap_words=False):
 if isinstance(n,NavigableString):
  if wrap_words:
   # Keep the wording; allow long table labels to wrap within their column.
   pieces=re.split(r'(Qwen\d[\w.-]+|[A-Za-z]{7,})',str(n))
   return ''.join(r'\seqsplit{'+esc(p)+'}' if re.fullmatch(r'Qwen\d[\w.-]+|[A-Za-z]{7,}',p) else esc(p) for p in pieces)
  z=esc(str(n))
  return re.sub(r'(?<![A-Za-z])(?:[A-Z]|\\_){10,}',lambda m:r'\seqsplit{'+m[0]+'}',z)
 if not isinstance(n,Tag):return ''
 if n.name=='math':
  a=n.find('annotation'); return '$'+a.get_text()+'$' if a else esc(n.get_text())
 if n.name=='img' and n.get('data-inline-icon-file'):
  src=ROOT/n['data-inline-icon-file']
  if not src.is_file() or src.suffix.lower() not in ['.pdf','.png']:
   raise ValueError('Invalid inline icon: '+str(src))
  shutil.copy2(src,OUT/'figures'/src.name)
  return r'\raisebox{-0.15em}{\includegraphics[height=1em]{figures/'+src.name+'}}'
 if n.name in ['svg','img','style','script']:return ''
 z=''.join(inline(c,wrap_words) for c in n.children)
 if n.name in ['strong','b']:return r'\textbf{'+z.replace(r'\\',r'}\\\textbf{')+'}'
 if n.name=='u':return r'\underline{'+z+'}'
 if n.name in ['em','i']:return r'\emph{'+z+'}'
 if n.name=='sup':return r'\textsuperscript{'+z+'}'
 if n.name=='sub':return r'\textsubscript{'+z+'}'
 if n.name=='code':
  code=n.get_text()
  if '_' in code:return r'\nolinkurl{'+code+'}'
  return r'\texttt{'+z+'}'
 if n.name=='br':return r'\\ '
 if n.name=='a':
  href=n.get('href','')
  if href.startswith('#ref-'):return r'\citep{'+href[5:]+'}'
  if href.startswith('#'):return r'\hyperlink{'+href[1:]+'}{'+z+'}'
  if href.startswith(('https://','http://')):return r'\href{'+href.replace('%',r'\%')+'}{'+z+'}'
 if n.name in ['span','small'] and 'display:block' in n.get('style','').replace(' ',''):return z+r'\\ '
 return z

def anchor(n): return r'\hypertarget{'+n['id']+'}{}' if n.get('id') else ''
CAPTIONS={}
for section in ss:
 for node in BeautifulSoup(section['enhtml'],'html.parser').find_all('table',id=True):
  caption=node.find('caption')
  if caption:CAPTIONS[node['id']]=inline(caption)
allfig=[];alltab=[];appendix_comparison_pair={};appendix_bottom_figures={};appendix_end_figures={};appendix_top_figures={};appendix_top_anchors={};appendix_prefix_figures={};appendix_fullwidth_tables={};appendix_lead_tables={};pinned_figures=[]
appendix_top_table_ids={tid for section in ss for tid in section.get('pdf_top_table_pair',[])}
appendix_top_table_tex={}
def copy_figure(src,dest):
 shutil.copy2(src,dest)
 fonts=subprocess.run(['pdffonts',str(dest)],text=True,capture_output=True,check=True).stdout
 if any(len(row.split())>=6 and row.split()[-5]=='no' for row in fonts.splitlines()[2:]):
  # Embed fonts in the export copy; never modify the original figure asset.
  tmp=dest.with_name(dest.stem+'.embedded.pdf')
  subprocess.run(['gs','-q','-dBATCH','-dNOPAUSE','-dSAFER','-sDEVICE=pdfwrite',
   '-dEmbedAllFonts=true','-dSubsetFonts=true','-dAutoRotatePages=/None',
   '-sOutputFile='+str(tmp),'-c','<< /NeverEmbed [] >> setdistillerparams','-f',str(dest)],check=True)
  tmp.replace(dest)
def table(t,cap,*,appendix=False):
 num=t.get('data-table-number'); rows=t.find_all('tr'); n=max(sum(int(c.get('colspan',1)) for c in r.find_all(['td','th'],recursive=False)) for r in rows)
 # Fixed-width cells avoid shrinking ordinary one-column tables to tiny text.
 # Very wide numeric grids retain their original columns and remain one table.
 matrix=bool(t.get('data-check-matrix'))
 fixed=n<=6 and t.get('data-pdf-fit')!='natural-width'
 # Appendix numbering can change with the reading order; formatting follows
 # the table's stable identity rather than its displayed number.
 table_id=t.get('id')
 pad=4.0 if table_id=='table-s11-pipeline-4-1' else (3.0 if table_id=='table-s11-results-rq2-1' else (1.0 if num=='1' else (1.2 if n>6 else 2.5)))
 lens=[0]*n; data_lens=[0]*n
 for ri,row in enumerate(rows):
  ci=0
  for c in row.find_all(['td','th'],recursive=False):
   span=int(c.get('colspan',1))
   if span==1 and ci<n:
    size=len(c.get_text(' ',strip=True));lens[ci]=max(lens[ci],size)
    if ri>0 and c.name=='td':data_lens[ci]=max(data_lens[ci],size)
   ci+=span
 if matrix:
  weights=[.30]+[.70/(n-1)]*(n-1)
 elif n>6:
  weights=[1.5]+[1]*(n-1)
 else:
  weights=[max(12,min(v,180))**.7 for v in lens]
 if t.get('id')=='table-s5-2-guidance-reasoning':weights=[.32,.17,.17,.17,.17]
 if t.get('id')=='table-s5-2-1':weights=[.32,.17,.11,.20,.20]
 if num=='1' and n==5:weights=[.25,.17,.28,.14,.16]
 if num=='1' and n==2:weights=[.36,.64]
 if table_id=='table-s11-pipeline-1':weights=[.49,.17,.17,.17]
 if num=='2' or t.get('id')=='table-s11-nasu-2':weights=[1]*n
 if table_id=='table-s11-nasu-3':weights=[.30,.70]
 if t.get('id') in ['table-s11-pipeline-3-1','table-s11-pipeline-3-3']:weights=[.4,.6]
 if t.get('data-column-widths'):weights=[float(w) for w in t['data-column-widths'].split(',')]
 total=sum(weights);fractions=[w/total for w in weights]
 spec='@{}'+(''.join('C{'+f'{f:.6f}'+r'\tablewidth}' for f in fractions) if fixed else 'c'*n)+'@{}'
 if matrix:
  spec=r'@{}C{.50\tablewidth}'+'c'*(n-1)+'@{}'
 grid=[]; blocked={}; lens=[0]*n
 for ri,row in enumerate(rows):
  cells=[];ci=0
  for c in row.find_all(['td','th'],recursive=False):
   while blocked.get((ri,ci)):
    cells.append('');ci+=1
   span=int(c.get('colspan',1)); rs=int(c.get('rowspan',1))
   alignment=cell_alignment(c)
   right=alignment=='right'
   left=alignment=='left'
   cell_align={'left':'l','right':'r','center':'c'}[alignment]
   fixed_align=(r'\raggedleft\arraybackslash ' if right else (r'\raggedright\arraybackslash ' if left else r'\centering '))
   # Appendix prose wraps at word boundaries; character-level splitting makes
   # labels such as "question" and "Validity" needlessly hard to read.
   val=inline(c,wrap_words=not appendix and c.name!='th' and (fixed or (matrix and ci==0)) and num!='1' and not (table_id=='table-s11-annotation-4' and t.get('data-layout')=='two-column')).strip()
   if c.get('data-nowrap') or (table_id=='table-s11-pipeline-1' and ci==0):
    # Keep each stage on one line and its linked reason table on the next.
    val=r'\mbox{'+inline(c).strip().replace(r'\\ ',r'}\newline{}\mbox{')+'}'
   if t.get('id') in ['table-s5-2-guidance-reasoning','table-s5-2-1'] and ci==0:val=r'\mbox{'+inline(c).strip()+'}'
   if num=='1' and n==5:
    if c.get_text(strip=True)=='NOT_APPLICABLE':val=r'{\fontsize{7}{8}\selectfont\texttt{NOT\_APPLICABLE}}'
    val=r'\mbox{'+val+'}'
   if t.get('id') in ['table-s11-pipeline-3-1','table-s11-pipeline-3-3']:
    val=val.replace(r'\seqsplit{INSUFFICIENT\_EVIDENCE}',r'INSUFFICIENT\_\allowbreak{}EVIDENCE')
   if c.get('data-metric')=='delta':val=r'\textcolor{'+('red' if float(c.get('data-value','0'))>0 else 'blue')+'}{'+val+'}'
   val=re.sub(r'(\\\\\s*)+$','',val)
   txt=c.get_text(' ',strip=True)
   if span==1:lens[ci]=max(lens[ci],len(txt))
   for rr in range(ri+1,ri+rs):
    for cc in range(ci,ci+span):blocked[rr,cc]=True
   if matrix:
    val=val.replace(r'\\',r'\newline{}') if ci==0 else val
    if ri==0 and ci>0:val=r'\rotatebox{90}{'+val.replace(r'\\',' ')+'}'
   elif fixed:
    val=val.replace(r'\\',r'\newline{}')
    if c.get('data-header-lines'):val=r'\makecell['+cell_align+']{'+inline(c).strip()+'}'
    if rs>1:val=r'\multirow{'+str(rs)+r'}{=}{'+fixed_align+val+'}'
    if span>1:
     spwidth=f'{sum(fractions[ci:ci+span]):.6f}'+r'\tablewidth+'+str(2*pad*(span-1))+'pt'
     val=r'\multicolumn{'+str(span)+r'}{C{\dimexpr '+spwidth+r'\relax}}{'+(fixed_align if right or left else '')+val+'}'
   else:
    # Wrap header phrases without changing labels or the table grid.
    if c.name=='th' and span==1 and not c.find(['math','sup','sub']):
     val=val.replace(' ',r'\\ ').replace('/',r'/\\ ')
    if span>1:
     val=val.replace('Qwen3.8-',r'Qwen3.8-\\ ').replace('Qwen3-',r'Qwen3-\\ ')
    if r'\\' in val:val=r'\makecell['+cell_align+']{'+val+'}'
    if rs>1:val=r'\multirow{'+str(rs)+r'}{*}{'+val+'}'
    if span>1:val=r'\multicolumn{'+str(span)+'}{'+cell_align+'}{'+val+'}'
   if c.get('data-nowrap'):
    val=inline(c).strip()
    val=(r'\makecell['+cell_align+']{'+val+'}' if r'\\' in val else r'\mbox{'+val+'}')
    if fixed and not matrix:
     val=(r'\begin{adjustbox}{max width='+f'{sum(fractions[ci:ci+span]):.6f}'+
       r'\tablewidth}'+val+r'\end{adjustbox}')
   if c.get('data-cell-color'):
    color=c['data-cell-color']
    if not re.fullmatch(r'[0-9A-Fa-f]{6}',color):raise ValueError('Invalid table cell color: '+color)
    val=r'\cellcolor[HTML]{'+color+'}'+val
   if (right or left) and span==1:
    if (fixed and not matrix) or (matrix and ci==0):
     val=fixed_align+val
    else:
     alignment=('@{}' if ci==0 else '')+cell_align+('@{}' if ci+span==n else '')
     val=r'\multicolumn{1}{'+alignment+'}{'+val+'}'
   cells.append(val);ci+=span
  while ci<n:cells.append('');ci+=1
  prefix=r'\rowcolor{gray!15}' if t.get('data-check-matrix') and 'ours' in row.get('class',[]) else ''
  grid.append(prefix+' & '.join(cells)+r' \\')
 body='\n'.join(grid)
 env='table'
 width=r'\textwidth' if env=='table*' else r'\columnwidth'
 # One intact float per original table. Never split or transpose.
 chunks=[grid]
 out=[]
 for part,g in enumerate(chunks):
  content=r'\begin{tabular}{'+spec+'}\n'+r'\toprule'+'\n'+'\n'.join(g[:1])+'\n'+r'\midrule'+'\n'+'\n'.join(g[1:])+'\n'+r'\bottomrule\end{tabular}'
  if t.get('data-pdf-width')=='full' and not fixed:
   content=content.replace(r'\begin{tabular}{@{}',r'\begin{tabular*}{'+width+r'}{@{\extracolsep{\fill}}',1).replace(r'\end{tabular}',r'\end{tabular*}')
  content=r'\begin{adjustbox}{max width='+width+r',max totalheight=.78\textheight}'+'\n'+content+'\n'+r'\end{adjustbox}'
  caption=inline(cap) if cap else CAPTIONS.get(t.get('id'),r'Supported abstention across $G^{\pm}R^{\pm}$ settings (\%).')
  caption=re.sub(r'^Table\s+[A-Z]?\d+[.:]\s*','',caption)
  if t.get('id')=='table-s11-nasu-1':caption=caption.replace(r'\seqsplit{UNSUPPORTED}',r'\mbox{UNSUPPORTED}')
  if part:caption+=' (continued)'
  setup=''
  if num:
   match=re.match(r'(A?)(\d+)',num); setup=r'\renewcommand{\thetable}{'+('A' if match[1] else '')+r'\arabic{table}}\setcounter{table}{'+str(int(match[2])-1)+'}'
  caption_tex=(r'\caption[]{'+caption+'}' if num else r'\caption*{'+caption+'}')
  size=r'\fontsize{8}{9.6}\selectfont' if matrix else (r'\footnotesize' if n>6 else r'\small')
  if num=='1':size=r'\fontsize{9}{10.8}\selectfont'
  row_spacing=float(t.get('data-pdf-row-spacing','1.15'))
  if not .9 <= row_spacing <= 1.5:raise ValueError('Invalid table row spacing: '+str(row_spacing))
  out.append(r'\begin{'+env+'}[t]\n'+setup+'\n'+r'\centering'+size+r'\setlength{\tabcolsep}{'+str(pad)+r'pt}\renewcommand{\arraystretch}{'+format(row_spacing,'g')+'}'+'\n'+r'\setlength{\tablewidth}{\dimexpr'+width+'-'+str(2*pad*(n-1))+r'pt\relax}'+'\n'+((anchor(t)+(anchor(cap) if cap else '')) if part==0 else '')+'\n'+content+'\n'+caption_tex+'\n'+r'\end{'+env+'}\n')
 if appendix or t.get('data-placement')=='inline':
  out=[v.replace(r'\begin{table}[t]',r'\par\medskip\noindent\begin{minipage}{\columnwidth}\captionsetup{type=table}').replace(r'\end{table}',r'\end{minipage}\par\medskip') for v in out]
  if t.get('id')=='table-s11-pipeline-2':out.append(r'\FloatBarrier'+'\n')
  if appendix and t.get('data-pdf-start-column')=='true':
   out.insert(0,r'\columnbreak'+'\n')
 alltab.append((t.get('id'),num,len(rows),n))
 return '\n'.join(out)

def process(x):
 b=BeautifulSoup(x['enhtml'],'html.parser'); raw={}; paired_figures={}
 # Add a small gap only when a run-in bold explanation follows body prose.
 # Main-text floats leave the text flow, so look past them. A section heading,
 # inline asset, table caption, or first paragraph must not create this gap.
 term_gap_paragraphs=set()
 for paragraph in b.find_all('p'):
  if paragraph.find_parent(['table','figure','pre','li']):continue
  first=next((child for child in paragraph.contents if str(child).strip()),None)
  if not isinstance(first,Tag) or first.name not in ['strong','b']:continue
  if not any(child.get_text(strip=True) if isinstance(child,Tag) else str(child).strip() for child in first.next_siblings):continue
  previous=paragraph.find_previous_sibling()
  while previous is not None and not x['en'].startswith('Appendix') and previous.name in ['figure','table'] and previous.get('data-placement')!='inline':
   previous=previous.find_previous_sibling()
  if previous is not None and previous.name=='p' and previous.get_text(strip=True) and not set(previous.get('class',[])).intersection(['table-caption','table-note','response-example-label']) and not previous.get('data-equation-number') and not previous.select_one('math[display="block"]'):
   term_gap_paragraphs.add(id(paragraph))
 def put(node,tex):
  key='FINJECTRAWPLACEHOLDER'+str(len(raw))+'END';raw[key]=tex;node.replace_with(NavigableString('\n\n'+key+'\n\n'))
 for f in list(b.find_all('figure')):
  file=f.get('data-figure-file');assert file,(x['id'],f.get('id'))
  src=ROOT/file; assert src.exists(),src
  copy_figure(src,OUT/'figures'/src.name)
  caption=inline(f.find('figcaption'));caption=re.sub(r'^Figure\s+[A-Z]?\d+[.:]\s*','',caption)
  num=f.get('data-figure-number',''); setup=''
  if num:setup=r'\renewcommand{\thefigure}{'+('A' if num.startswith('A') else '')+r'\arabic{figure}}\setcounter{figure}{'+str(int(num.lstrip('A'))-1)+'}'
  max_height=float(f.get('data-pdf-max-height','0.72'))
  if not 0 < max_height <= (0.9 if f.get('data-layout')=='two-column' else 0.72):raise ValueError('Invalid figure height: '+str(max_height))
  tex=r'\begin{figure}[t]'+'\n'+setup+'\n'+r'\centering'+anchor(f)+'\n'+r'\includegraphics[width=\columnwidth,height='+format(max_height,'.2f').lstrip('0')+r'\textheight,keepaspectratio]{figures/'+src.name+'}\n'+r'\caption[]{'+caption+'}\n'+r'\label{'+f.get('id','fig-'+src.stem)+'}\n'+r'\end{figure}'
  if f.get('data-layout') == 'two-column':
   tex=tex.replace('begin{figure}', 'begin{figure*}').replace('end{figure}', 'end{figure*}').replace('width=\\columnwidth', 'width=\\textwidth')
  if f.get('data-layout')=='two-column':tex=tex.replace(r'\begin{figure}[t]',r'\begin{figure*}[t]').replace(r'\end{figure}',r'\end{figure*}').replace(r'width=\columnwidth',r'width=\textwidth')
  if x['en'].startswith('Appendix') or f.get('data-placement')=='inline':
   # Keep appendix figures and explicitly placed body figures intact.
   width=r'\textwidth' if f.get('data-layout')=='two-column' else r'\columnwidth'
   tex=re.sub(r'\\begin\{figure\*?\}\[t\]',lambda m:r'\par\medskip\noindent\begin{minipage}{'+width+r'}\captionsetup{type=figure}',tex)
   tex=re.sub(r'\\end\{figure\*?\}',lambda m:r'\end{minipage}\par\medskip',tex)
  tex=''.join(anchor(z) for z in f.select('[id]'))+tex
  if CURRENT_LAYOUT and x['en'].startswith('Appendix'):
   allfig.append((f.get('id'),src.name))
   if f.get('data-layout')=='two-column' and x.get('pdf_after_references')!='same-page':
    own_page=f.get('data-pdf-placement')=='continuation-top' and x.get('pdf_continuation_figure_own_page')
    tex=(r'\end{multicols}'+'\n'+(r'\clearpage'+'\n' if own_page else '')+tex+'\n'+
      (r'\clearpage'+'\n' if own_page else '')+r'\begin{multicols}{2}\raggedcolumns'+'\n')
   else:paired_figures[f.get('id')]='FINJECTRAWPLACEHOLDER'+str(len(raw))+'END'
   put(f,tex)
   continue
  if f.get('data-pdf-page'):
   page=f['data-pdf-page'];column=f.get('data-pdf-column')
   fullwidth=f.get('data-layout')=='two-column'
   valid_columns=['both'] if fullwidth else ['left','right']
   if not page.isdigit() or int(page)<(2 if fullwidth else 1) or column not in valid_columns or x['en'].startswith('Appendix') or any((p[1],p[2])==(int(page),column) for p in pinned_figures):
    raise ValueError('Invalid pinned figure: '+f.get('id',''))
   key=str(len(pinned_figures)+1);env='figure*' if fullwidth else 'figure'
   tex=tex.replace('\\begin{'+env+'}[t]',r'\begin{FInjectPinnedFigure}{'+key+'}{'+page+'}{'+column+'}').replace('\\end{'+env+'}',r'\end{FInjectPinnedFigure}')
   pinned_figures.append((f['id'],int(page),column,tex))
  allfig.append((f.get('id'),src.name))
  if f.get('data-pdf-page'):
   # Register early enough to reach the target column even when the Draft's
   # figure occurs later in its related section.
   put(f,'')
  elif x['en'].startswith('Appendix') and f.get('data-pdf-placement')=='section-bottom':
   if f.get('data-layout')!='two-column' or x['id'] in appendix_bottom_figures:raise ValueError('Invalid full-width bottom figure: '+x['id'])
   appendix_bottom_figures[x['id']]=tex
   put(f,'')
  elif x['en'].startswith('Appendix') and f.get('data-pdf-placement')=='section-end':
   if f.get('data-layout')!='two-column' or x['id'] in appendix_end_figures:raise ValueError('Invalid full-width section-end figure: '+x['id'])
   appendix_end_figures[x['id']]=tex
   put(f,'')
  elif x['en'].startswith('Appendix') and f.get('data-pdf-placement')=='prefix-end':
   if f.get('data-layout')!='two-column' or x['id'] in appendix_prefix_figures:raise ValueError('Invalid full-width prefix figure: '+x['id'])
   appendix_prefix_figures[x['id']]=tex
   put(f,'')
  elif x['en'].startswith('Appendix') and f.get('data-pdf-placement')=='continuation-top':
   target=f.get('data-pdf-continuation-anchor')
   if f.get('data-layout')!='two-column' or not target or not b.find(id=target) or x['id'] in appendix_top_figures:
    raise ValueError('Invalid full-width continuation figure: '+x['id'])
   appendix_top_figures[x['id']]=tex;appendix_top_anchors[x['id']]=target
   put(f,'')
  else:
   paired_figures[f.get('id')]='FINJECTRAWPLACEHOLDER'+str(len(raw))+'END';put(f,tex)
 for t in list(b.find_all('table')):
  # Some figures have an associated unnumbered tabular panel in the Draft.
  cap=t.find('caption')
  if cap is None and t.get('data-table-number'):
   cap=next((p for p in b.select('p.table-caption') if p.get('data-table-number')==t.get('data-table-number')),None)
  if not t.get('data-table-number'):
   cap=t.find_previous_sibling('p')
  tex=table(t,cap,appendix=x['en'].startswith('Appendix'))
  if CURRENT_LAYOUT and x['en'].startswith('Appendix'):
   if t.get('id') in appendix_top_table_ids:
    # Keep each comparison table intact in its requested left/right top slot.
    ancestors=[p for p in t.parents if p.name!='[document]' and p.get('id')]
    appendix_top_table_tex[t['id']]=''.join(anchor(p) for p in reversed(ancestors))+tex
    for p in ancestors:del p['id']
    if cap:cap.decompose()
    put(t,'')
    continue
   if t.get('data-paired-figure'):
    key=paired_figures[t['data-paired-figure']]
    tex+='\n'+raw[key];raw[key]=''
   if cap:cap.decompose()
   if t.get('data-layout')=='two-column':
    tex=r'\end{multicols}'+'\n'+tex.replace(r'\columnwidth',r'\textwidth')+'\n'+r'\begin{multicols}{2}\raggedcolumns'+'\n'
   put(t,tex)
   continue
  if t.get('data-paired-figure'):
   key=paired_figures[t['data-paired-figure']]
   fig=raw[key].replace(r'\begin{figure}[t]',r'\begin{minipage}{\columnwidth}\captionsetup{type=figure}\normalsize').replace(r'\end{figure}',r'\end{minipage}')
   tex=tex.replace(r'\begin{table}[t]',r'\begin{table}[!t]').replace(r'\end{table}',r'\par\medskip'+ '\n'+fig+'\n'+r'\end{table}')
   raw[key]=''
  if cap:cap.decompose()
  if t.get('data-pdf-page'):
   page=t['data-pdf-page'];column=t.get('data-pdf-column')
   if not page.isdigit() or int(page)<1 or column not in ['left','right'] or x['en'].startswith('Appendix') or t.get('data-paired-figure') or t.get('data-placement')=='inline' or any((p[1],p[2])==(int(page),column) for p in pinned_figures):
    raise ValueError('Invalid pinned table: '+t.get('id',''))
   key=str(len(pinned_figures)+1)
   tex=tex.replace(r'\begin{table}[t]',r'\begin{FInjectPinnedFigure}[table]{'+key+'}{'+page+'}{'+column+'}').replace(r'\end{table}',r'\end{FInjectPinnedFigure}')
   pinned_figures.append((t['id'],int(page),column,tex))
   put(t,'')
   continue
  if x['en'].startswith('Appendix') and t.get('data-pdf-placement')=='section-start':
   # Keep a leading wide table ahead of the section's two-column explanation.
   if t.get('data-layout')!='two-column' or x['id'] in appendix_lead_tables:
    raise ValueError('Invalid leading full-width appendix table: '+t.get('id',''))
   lead=tex.replace(r'\columnwidth',r'\textwidth')
   note=t.find_next_sibling()
   if note is not None and note.name=='p' and note.get('data-for-table')==t.get('id'):
    # Keep the table interpretation below its caption and before the next table.
    explanation=(r'\par\medskip{\normalsize\raggedright\noindent '+anchor(note)+inline(note)+r'\par}'+'\n')
    lead=lead.replace(r'\end{minipage}\par\medskip',explanation+r'\end{minipage}\par\medskip',1)
    note.decompose()
   appendix_lead_tables[x['id']]=lead
   put(t,'')
   continue
  if x['en'].startswith('Appendix') and t.get('data-pdf-placement')=='after-fullwidth-table':
   # Keep an adjacent wide table after the existing one, before the column text.
   source=BeautifulSoup(x['enhtml'],'html.parser').find('table',id=t.get('id'))
   previous=source.parent.find_previous_sibling()
   if t.get('data-layout')!='two-column' or x['id'] not in appendix_fullwidth_tables or previous is None or previous.name!='table' or previous.get('data-layout')!='two-column':
    raise ValueError('Invalid adjacent full-width appendix table: '+t.get('id',''))
   ancestors=[p for p in t.parents if p.name!='[document]' and p.get('id')]
   appendix_fullwidth_tables[x['id']]+='\n'+''.join(anchor(p) for p in reversed(ancestors))+tex.replace(r'\columnwidth',r'\textwidth')
   for p in ancestors:del p['id']
   put(t,'')
   continue
  if x['en'].startswith('Appendix') and (x['level']==0 or t.get('id') in ['tab:finject-rq1','table-s11-results-rq2-1','tab:finject-rq2','tab:retention-complete']) and t.get('data-layout')=='two-column':
   # Full-width appendix tables follow their parent title, before two-column text.
   ancestors=[p for p in t.parents if p.name!='[document]' and p.get('id')]
   appendix_fullwidth_tables[x['id']]=''.join(anchor(p) for p in reversed(ancestors))+tex.replace(r'\columnwidth',r'\textwidth')
   for p in ancestors:del p['id']
   put(t,'')
   continue
  if x['id']=='s11-comparisons' and t.get('data-table-number') in ['A3','A4']:
   # These two one-column tables precede the full-width Appendix 3 heading.
   ancestors=[p for p in t.parents if p.name!='[document]' and p.get('id')]
   appendix_comparison_pair[t['data-table-number']]=''.join(anchor(p) for p in reversed(ancestors))+tex
   for p in ancestors:del p['id']
   put(t,'')
   continue
  put(t,tex)
 # Render each research question with its shared block spacing.
 for label in list(b.select('span.question-label')):
  paragraph=label.find_parent('p')
  if paragraph is None or not re.fullmatch(r'en-rq[1-4]',paragraph.get('id','')):
   raise ValueError('Unexpected research-question label: '+x['id'])
  label.decompose()
  question=''.join(inline(c) for c in paragraph.children).strip()
  put(paragraph,r'\begin{QuestionBlock}'+'\n'+anchor(paragraph)+r'\QuestionLabel\ '+question+'\n'+r'\end{QuestionBlock}'+'\n')
 for eq in list(b.select('[data-equation-number]')):
  a=eq.find('annotation');
  if a:
   formula=re.sub(r'\\tag\{[^}]+\}', '', a.get_text())
   if eq['data-equation-number']=='1':
    input_line=r"\operatorname{TargetLLM}\!\left(Q,\{C,C'_{\mathrm{IC}_{v,f}},\ldots,C'_{\mathrm{ER}_{2}}\}\mid G^{\pm},R^{\pm}\right)"
    output_line=r'\quad\rightarrow\operatorname{TargetOutput}(\text{answer},\text{classification},\text{reason},\text{evidence}).'
    # Number the input row; keep the unnumbered output together within one column.
    put(eq,anchor(eq)+r'\begin{align}'+'\n&'+
     r'\begin{adjustbox}{max width=.88\columnwidth}$\displaystyle '+input_line+r'$\end{adjustbox}\\'+'\n&'+
     r'\begin{adjustbox}{max width=\columnwidth}$\displaystyle '+output_line+r'$\end{adjustbox}\notag'+'\n'+r'\end{align}')
    continue
   if eq['data-equation-number']=='2':
    formula=r'''\begin{aligned}
\mathrm{NS}&=\{y\mid\operatorname{Numeric}(y)\\
 &\qquad\land\operatorname{FAV}(y)=\mathrm{Supported}\},\\
\mathrm{AS}&=\{y\mid\operatorname{Abstain}(y)\\
 &\qquad\land\operatorname{ARV}(y)=\mathrm{Supported}\\
 &\qquad\land\operatorname{FAV}(y)=\mathrm{Supported}\}.
\end{aligned}'''
   put(eq,r'\begin{equation}'+anchor(eq)+r'\begin{adjustbox}{max width=.88\columnwidth}$\displaystyle '+formula+r'$\end{adjustbox}\end{equation}')
 for m in list(b.find_all('math')):
  a=m.find('annotation');
  if a:
   formula=a.get_text().strip()
   if CURRENT_LAYOUT and m.get('display')=='block':
    if x['id']=='s4-1' and 'TargetLLM' in formula:
     left,right=formula.split(r'\rightarrow',1)
     # Balance the visible gaps around this two-row equation without moving the following paragraph.
     tex=(r'\begingroup'+'\n'+r'\addtolength{\abovedisplayskip}{-6.5pt}'+'\n'+
       r'\addtolength{\belowdisplayskip}{6.5pt}'+'\n'+r'\begin{align}'+'\n&'+left+r'\label{eq:target-call}\\'+'\n&'+
       r'\begin{adjustbox}{max width=\columnwidth}$\displaystyle\rightarrow '+right+
       r'$\end{adjustbox}\notag'+'\n'+r'\end{align}'+'\n'+r'\endgroup')
    else:
     if r'\mathrm{NS}' in formula and r'\operatorname{FAV}' in formula:
      formula=formula.replace(r'\land',r'\\ &\qquad\land')
     tex=r'\['+r'\begin{adjustbox}{max width=\columnwidth}$\displaystyle '+formula+r'$\end{adjustbox}\]'
    put(m,tex)
   else:put(m,('$'+formula+'$') if m.get('display')!='block' else '\\['+formula+'\\]')
 for paragraph in list(b.select('p.repository-link')):
  put(paragraph,r'\noindent{\fontsize{9}{11}\selectfont '+inline(paragraph)+r'\par}')
 for a in list(b.select('a')):
  put(a,inline(a))
 for c in list(b.find_all('code')):
  code=c.get_text()
  long_appendix_code=x['en'].startswith('Appendix') and len(code)>=12 and ' ' not in code
  if not c.find_parent('pre') and ('/' in code or (len(code)>30 and ' ' not in code) or long_appendix_code):put(c,r'\nolinkurl{'+code+'}')
 for pre in list(b.find_all('pre')):
  example=x['id']=='s11-pipeline-3' and pre.find_parent('div',attrs={'data-response-source':True}) is not None
  end=r'\end{Verbatim}'+('\n'+r'\end{minipage}\par\medskip' if example else '')
  put(pre,r'\begin{Verbatim}[fontsize=\scriptsize,breaklines=true,breakanywhere=true]'+'\n'+pre.get_text()+'\n'+end)
 for label in list(b.select('p.response-example-label')):
  # Keep the two response-example headings compact on one line in a column.
  label_tex=''.join(inline(c) if isinstance(c,Tag) else esc(str(c)) for c in label.children)
  start=(r'\par\medskip\noindent\begin{minipage}{\columnwidth}'+'\n' if x['id']=='s11-pipeline-3' else '')
  put(label,start+r'{\fontsize{10}{12}\selectfont\mbox{'+label_tex+r'}}\par'+'\n')
 # Number the main finding topics as third-level sections within each RQ.
 if x['id'] in ['s5-1','s5-2','s5-3','s5-4']:
  # Stable section IDs survive insertions; printed numbers follow the title.
  section_number=re.match(r'^(\d+(?:\.\d+)*)\s',x['en'])
  if section_number is None:raise ValueError('Finding section number missing: '+x['id'])
  for topic_index, heading in enumerate(list(b.select('h4.finding-topic-title')), 1):
   topic_number=section_number[1]+'.'+str(topic_index)
   heading_text=heading.get_text(' ',strip=True)
   if not heading_text.startswith(topic_number+' '):
    raise ValueError('Finding topic number mismatch: '+x['id'])
   heading_title=heading_text[len(topic_number)+1:]
   put(heading,anchor(heading)+r'\subsubsection{'+esc(heading_title)+'}'+'\n')
 # Align leading bold labels with the column edge in the paper and appendices.
 # Ordinary explanation paragraphs keep the template's indentation.
 for paragraph in b.find_all('p'):
  if paragraph.find_parent(['table','figure','pre']) or paragraph.get('data-paragraph-indent')=='normal':continue
  first=next((child for child in paragraph.contents if str(child).strip()),None)
  if isinstance(first,Tag) and first.name in ['strong','b']:
   key='FINJECTNOINDENT'+str(len(raw))+'END'
   raw[key]=(r'\TermLeadGap{}' if id(paragraph) in term_gap_paragraphs else '')+r'\noindent{}'
   paragraph.insert(0,NavigableString(key))
 for el in b.select('h3'):
  if re.match(r'Table N(?:\+1)?\.',el.get_text(strip=True)):el.decompose()
 for el in b.select('script,style,button,svg'):el.decompose()
 for el in b.select('summary'):
  el.name='p';el.string=el.get_text().split(' / ')[0]
 for el in b.select('[id]'):
  el.insert_before(NavigableString('\n\nFINJECTTARGET'+str(len(raw))+'END\n\n'))
  raw['FINJECTTARGET'+str(len(raw))+'END']=anchor(el);del el['id']
 # Discard screen-only styling; retain content and limits.
 for el in b.find_all(True):
  for attr in list(el.attrs):
   if attr not in ['href','src','colspan','rowspan']:del el[attr]
 tex=subprocess.run(['pandoc','-f','html','-t','latex','--wrap=none'],input=str(b),text=True,capture_output=True,check=True).stdout
 tex=tex.replace(r'\subsubsection{',r'\subsubsection*{')
 for key,val in raw.items():tex=tex.replace(key,val)
 # FancyVerb requires its closing command to occupy its own line. Pandoc may
 # otherwise join adjacent raw placeholders (for example, a following wide table).
 tex=re.sub(r'(\\end\{Verbatim\})[ \t]+',r'\1\n',tex)
 tex=re.sub(r'(?<![A-Za-z0-9])([0-9a-f]{64})(?![A-Za-z0-9])',lambda m:r'\nolinkurl{'+m[1]+'}',tex)
 tex=re.sub(r'(\\citep\{[^}]+\})(?:\s*,\s*\\citep\{[^}]+\})+',lambda m:r'\citep{'+','.join(re.findall(r'\\citep\{([^}]+)\}',m[0]))+'}',tex)
 tex=re.sub(r'([([])[ \t]+(?=\\hyperlink\{)',r'\1',tex)
 tex=re.sub(r'(\\hyperlink\{[^{}]+\}\{[^{}]+\})[ \t]+([.,;:)\]])',r'\1\2',tex)
 tex=re.sub(r'\.\s*(\\citep\{[^}]+\})(?=\s*(?:\n|$))',r' \1.',tex)
 tex=re.sub(r'(\\citep\{[^}]+\})[ \t]+([.,;:])',r'\1\2',tex)
 # Preserve the current Draft wording, including provisional notes.
 # Unicode characters in regular text produced by pandoc are normalized without touching math.
 for char,val in charmap.items():tex=tex.replace(char,val)
 tex=tex.replace(r'IC\_VALUE\_01\_BEFORE',r'\nolinkurl{IC_VALUE_01_BEFORE}')
 if x['en'].startswith('Appendix'):
  # Prompt filenames are unchanged, but may wrap inside their appendix column.
  tex=re.sub(r'(?m)^([\w.\-]+\.md)$',lambda m:r'{\urlstyle{same}\nolinkurl{'+m[1]+'}}',tex)
 if x['id'] in ['s5-1','s5-2','s5-3','s5-4']:
  # Keep each Finding's emphasized lead with its first supporting lines.
  tex=tex.replace(r'\noindent{}\textbf{Finding ',r'\FindingLead{Finding ',1)
 return tex
def section_filename(section):
 # Appendix filenames follow the printed appendix numbers; anchors keep their IDs.
 if section['en'].startswith('Appendix'):
  match=re.match(r'^Appendix (\d+(?:\.\d+)*|P)\.',section['en'])
  if not match:raise ValueError('Appendix number missing: '+section['en'])
  return 'a'+match[1].lower().replace('.','-')+'.tex'
 return section['id']+'.tex'

parts=[]
# Preserve the legacy order only for sections that remain outside the appendices.
post_conclusion=[sid for sid in ['s8','s7','s6','s9','s10']
                 if any(x['id']==sid and not x['en'].startswith('Appendix') for x in ss)]
ordered=[x for x in ss if x['id'] not in post_conclusion]
conclusion_index=next(i for i,x in enumerate(ordered) if x['id']=='conclusion')
ordered[conclusion_index+1:conclusion_index+1]=[next(x for x in ss if x['id']==sid) for sid in post_conclusion]
for x in ordered:
 if x['id'] in ['references','s11']:continue
 fn=section_filename(x); title=re.sub(r'^\d+(?:\.\d+)*\.?\s+','',x['en'])
 body=process(x)
 if CURRENT_LAYOUT and x['en'].startswith('Appendix'):
  heading='\\'+('subsection' if x['level'] else 'section')+'*{'+esc(title)+'}'+anchor(x)
  if x.get('pdf_after_references')=='same-page':
   text=heading+'\n'+body
  elif x.get('pdf_top_table_pair'):
   pair=r'\input{sections/'+pathlib.Path(fn).stem+'-tables}'+'\n'
   columns=r'\begin{multicols}{2}\raggedcolumns'+'\n'
   text=(pair+columns+heading+'\n' if x.get('pdf_top_table_pair_before_heading') else heading+'\n'+pair+columns)+body
  else:
   text=heading+'\n'+(r'\begin{multicols}{2}\raggedcolumns'+'\n' if not x['level'] else '')+body
  (OUT/'sections'/fn).write_text(text);parts.append(x)
  continue
 if x['id'] in appendix_lead_tables and x['id'] not in appendix_fullwidth_tables:
  raise ValueError('Leading appendix table requires a full-width section: '+x['id'])
 before_fullwidth=''
 if x.get('pdf_before_fullwidth_anchor'):
  marker=r'\hypertarget{'+x['pdf_before_fullwidth_anchor']+'}{}'
  before_fullwidth,found,body=body.partition(marker)
  if x['id'] not in appendix_fullwidth_tables or not found or not before_fullwidth.strip():
   raise ValueError('Missing content before full-width table: '+x['id'])
 if x['id'] in appendix_top_figures:
  marker=r'\hypertarget{'+appendix_top_anchors[x['id']]+'}{}'
  head,found,tail=body.partition(marker)
  if not found or not head.strip() or not tail.strip():raise ValueError('Missing continuation text: '+x['id'])
  (OUT/'sections'/(pathlib.Path(fn).stem+'-continuation.tex')).write_text(marker+'\n'+tail)
  body=head
 if x['id']=='abstract':text=body
 elif x['en'].startswith('Appendix'):
  heading='\\'+('subsection' if x['level'] else 'section')+'*{'+esc(title)+'}'+anchor(x)
  if x['id'] in ['s11-pipeline-1','s11-pipeline-2','s11-validation','s11-annotation']:
   # Keep each stage heading with its first, intact exclusion table.
   first=re.match(r'(.*?\\end\{minipage\}\\par\\medskip)(.*)',body,re.S)
   if not first:raise ValueError('Missing first stage table: '+x['id'])
   text=(r'\par\medskip\noindent\begin{minipage}{\columnwidth}'+'\n'+heading+'\n'+first[1]+'\n'+r'\end{minipage}\par\medskip'+'\n'+first[2])
  elif x['id'] in appendix_fullwidth_tables:
   table_file=pathlib.Path(fn).stem+'-table.tex'
   (OUT/'sections'/table_file).write_text(appendix_fullwidth_tables[x['id']]+'\n')
   # Keep earlier one-column tables ahead of the full-width table in reading order.
   prefix=(r'\begin{multicols}{2}\raggedcolumns'+'\n'+before_fullwidth+'\n'+r'\end{multicols}'+'\n') if before_fullwidth else ''
   after_table=(r'\clearpage'+'\n') if x['id']=='s11-results-rq3' else ''
   text=heading+'\n'+(appendix_lead_tables[x['id']]+'\n' if x['id'] in appendix_lead_tables else '')+prefix+r'\input{sections/'+table_file[:-4]+'}\n'+after_table+r'\begin{multicols}{2}\raggedcolumns'+'\n'+body
  elif x['level'] or x['id']=='s11-workflow':text=heading+'\n'+body
  else:
   # Soft wraps in the prompt appendix do not add symbols to the quoted text.
   spacing=r'\fvset{vspace=3pt,breaksymbolleft={},breaksymbolright={}}' if x['id']=='s11-prompts' else ''
   text=r'\begin{multicols}{2}[{'+heading+r'}]\raggedcolumns'+spacing+'\n'+body
 elif x['id'] in ['s6','s7','s8','s9','s10']:
  text=r'\section*{'+esc(title)+'}'+anchor(x)+'\n'+body
 else:
  spacing=x.get('pdf_heading_spacing_pt')
  if spacing is not None:
   if not x['level'] or len(spacing)!=2 or any(not isinstance(v,(int,float)) or not 0 < v <= 8 for v in spacing):
    raise ValueError('Invalid subsection spacing: '+x['id'])
   before,after=(format(v,'g') for v in spacing)
   # Retain the ACL heading font and numbering; adjust only the requested gap.
   text=(r'\makeatletter'+'\n'+r'\def\FInjectCompactSubsection{\@startsection{subsection}{2}{\z@}{-'+before+'pt}{'+after+r'pt}{\normalsize\bfseries\raggedright}}'+'\n'+r'\makeatother'+'\n'+r'\FInjectCompactSubsection{'+esc(title)+'}'+anchor(x)+'\n'+body)
  else:text='\\'+('subsection' if x['level'] else 'section')+'{'+esc(title)+'}'+anchor(x)+'\n'+body
 paragraph_skip=x.get('pdf_paragraph_skip_pt')
 if paragraph_skip is not None:
  if not isinstance(paragraph_skip,(int,float)) or not 0 <= paragraph_skip <= 4:
   raise ValueError('Invalid paragraph spacing: '+x['id'])
  text=r'\begingroup\setlength{\parskip}{'+format(paragraph_skip,'g')+'pt}'+'\n'+text.rstrip()+'\n'+r'\par\endgroup'+'\n'
 if x['id']=='s11-pipeline':
  assert set(appendix_comparison_pair)=={'A3','A4'}
  pair=[]
  for num in ['A3','A4']:
   tex=appendix_comparison_pair[num].replace(r'\par\medskip\noindent','',1)
   pair.append(r'\begin{minipage}[t]{\dimexpr\textwidth/2-\columnsep/2\relax}\vspace{0pt}'+'\n'+tex+'\n'+r'\end{minipage}')
  (OUT/'sections/a2-2-tables.tex').write_text(r'\noindent'+pair[0]+'\n'+r'\hfill'+pair[1]+'\n'+r'\par\medskip'+'\n')
  text=r'\input{sections/a2-2-tables}'+'\n'+text
 if x['id']=='s11-target-prompts':
  for prompt_id in ['prompt-common','prompt-guided','prompt-unguided']:
   prompt_anchor=r'\hypertarget{'+prompt_id+'}{}'
   text=text.replace(prompt_anchor,r'\par\Needspace{5\baselineskip}'+prompt_anchor,1)
 (OUT/'sections'/fn).write_text(text);parts.append(x)
 if x['id'] in appendix_bottom_figures or x['id'] in appendix_end_figures:
  figure_tex=appendix_bottom_figures.get(x['id'],appendix_end_figures.get(x['id']))
  (OUT/'sections'/(pathlib.Path(fn).stem+'-figure.tex')).write_text(figure_tex+'\n')
 if x['id'] in appendix_top_figures:
  (OUT/'sections'/(pathlib.Path(fn).stem+'-figure.tex')).write_text(appendix_top_figures[x['id']]+'\n')
 if x['id'] in appendix_prefix_figures:
  if x['id'] not in appendix_top_figures:raise ValueError('Prefix figure requires a section continuation: '+x['id'])
  (OUT/'sections'/(pathlib.Path(fn).stem+'-prefix-figure.tex')).write_text(appendix_prefix_figures[x['id']]+'\n')
if CURRENT_LAYOUT:
 for section in ss:
  ids=section.get('pdf_top_table_pair')
  if not ids:continue
  if len(ids)!=2 or any(tid not in appendix_top_table_tex for tid in ids):
   raise ValueError('An appendix top row requires two existing tables: '+section['id'])
  pair=[]
  for tid in ids:
   tex=appendix_top_table_tex[tid].replace(r'\par\medskip\noindent','',1)
   pair.append(r'\begin{minipage}[t]{\dimexpr\textwidth/2-\columnsep/2\relax}\vspace{0pt}'+'\n'+tex+'\n'+r'\end{minipage}')
  pair_file=pathlib.Path(section_filename(section)).stem+'-tables.tex'
  (OUT/'sections'/pair_file).write_text(r'\noindent'+pair[0]+'\n'+r'\hfill'+pair[1]+'\n'+r'\par\medskip'+'\n')
preamble=r'''\documentclass[11pt,a4paper]{article}
\PassOptionsToPackage{table}{xcolor}
\usepackage{multicol}
\usepackage{cuted}
\usepackage[review]{acl}
\input{review-line-numbers}
\renewcommand{\footnoterule}{\kern-3pt\hrule width \columnwidth\kern 2.6pt}
\usepackage{fontspec}
\setmainfont{texgyretermes-regular.otf}[BoldFont=texgyretermes-bold.otf,ItalicFont=texgyretermes-italic.otf,BoldItalicFont=texgyretermes-bolditalic.otf]
\setsansfont{texgyreheros-regular.otf}[BoldFont=texgyreheros-bold.otf]
\setmonofont{lmmono10-regular.otf}[Scale=MatchLowercase]
\newcommand{\QuestionLabel}{\textbf{Question.}}
\newenvironment{QuestionBlock}{%
  \begin{list}{}{%
    \setlength{\leftmargin}{1em}%
    \setlength{\rightmargin}{1em}%
    \setlength{\topsep}{\baselineskip}%
    \setlength{\partopsep}{0pt}%
    \setlength{\parsep}{0pt}%
    \setlength{\itemsep}{0pt}%
    \setlength{\listparindent}{0pt}%
    \setlength{\itemindent}{0pt}%
  }\item[]%
}{\end{list}}

% The English draft uses the Latin fonts configured above.
\usepackage{microtype,amsmath,amssymb,graphicx,booktabs,array,multirow,makecell,adjustbox}
\usepackage{xurl,fvextra,placeins,xcolor,seqsplit,needspace,soul}
\fvset{breaksymbolleft={},breaksymbolright={},breakindent=1em}
\captionsetup{font=10pt,justification=raggedright,singlelinecheck=true}
\newcolumntype{P}[1]{>{\raggedright\arraybackslash}p{#1}}
\newcolumntype{C}[1]{>{\centering\arraybackslash}m{#1}}
\newlength{\tablewidth}
% Drop the gap at page/column starts; allow it to shrink to avoid overflow.
\newcommand{\TermLeadGap}{\par\vspace{0.15\baselineskip minus 0.15\baselineskip}}
\newcommand{\FindingLead}[1]{\par\Needspace{6\baselineskip}\noindent\textbf{#1}}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\providecommand{\pandocbounded}[1]{#1}
\sethlcolor{yellow!20}
% A new two-column block needs room for an intact figure/table, not just a heading.
\setlength{\premulticols}{170pt}
\setlength{\emergencystretch}{1.5em}
% Match the reference NAACL paper's natural paragraph and float spacing.
% Keep the ACL body font, line spacing, margins, and column widths.
\setlength{\parskip}{4pt}
\setlength{\parindent}{1em}
\clubpenalty=10000
\widowpenalty=10000
\raggedbottom
\setcounter{topnumber}{1}
\setcounter{bottomnumber}{0}
\setcounter{totalnumber}{1}
\renewcommand{\topfraction}{0.9}
\renewcommand{\textfraction}{0.1}
\renewcommand{\floatpagefraction}{0.8}
\setlength{\textfloatsep}{14pt plus 2pt minus 2pt}
\setlength{\floatsep}{12pt plus 2pt minus 2pt}
\setlength{\intextsep}{12pt plus 2pt minus 2pt}
\captionsetup{skip=6pt}
\makeatletter
\setlength{\@fptop}{0pt}
\setlength{\@fpsep}{12pt}
\makeatother
\definecolor{aclhyperlink}{HTML}{000099}
\hypersetup{colorlinks=true,citecolor=aclhyperlink,linkcolor=aclhyperlink,urlcolor=aclhyperlink,pdftitle={FInject: Grounded Answering and Abstention of Perturbation-Injected Financial Questions}}
\title{FInject: Grounded Answering and Abstention of Perturbation-Injected Financial Questions}
\author{
  \textbf{Wooik Park}\textsuperscript{1}\thanks{\protect\hypertarget{Hfootnote.1}{}Lead author.}\quad
  \textbf{Jinkyu Kim}\textsuperscript{2}\quad
  \textbf{Jinsu Kim}\textsuperscript{1}\quad
  \textbf{Yumi Jung}\textsuperscript{1} \\
  \textbf{Mujeen Sung}\textsuperscript{3}\quad
  \textbf{Mogan Gim}\textsuperscript{4}\quad
  \textbf{Donghee Choi}\textsuperscript{1}\thanks{\protect\hypertarget{Hfootnote.2}{}Corresponding author.} \\[2pt]
  {\normalfont\textsuperscript{1}Pusan National University\quad
  \textsuperscript{2}Korea University} \\
  {\normalfont\textsuperscript{3}Kyung Hee University\quad
  \textsuperscript{4}Hankuk University of Foreign Studies} \\[2pt]
  % Keep the two email rows in author order within the existing title block.
  {\normalfont\strut{\fontsize{9.5}{14}\selectfont
  \texttt{wipark@pusan.ac.kr}\enspace\texttt{jkcost2511@gmail.com}\enspace
  \texttt{\{jinsu.kim,jungyumi\}@pusan.ac.kr}}} \\
  {\normalfont\strut{\fontsize{9.5}{14}\selectfont
  \texttt{mujeensung@khu.ac.kr}\enspace\texttt{gimmogan@hufs.ac.kr}\enspace
  \texttt{dchoi@pusan.ac.kr}}}
}
\begin{document}
\maketitle
\begin{abstract}\input{sections/abstract}\end{abstract}
'''
main=preamble
if pinned_figures:
 # Hold each native float until its requested page and column start. Register
 # them before body text without changing their location in the HTML Draft.
 (OUT/'pinned-figures.tex').write_text('\n\n'.join(p[3] for p in pinned_figures)+'\n')
 pinned_preamble=r'''\makeatletter
\def\FInjectPinnedIds{FINJECTPINNEDIDS}
\@for\FInjectPinnedId:=\FInjectPinnedIds\do{%
  \expandafter\gdef\csname FInjectPinnedPending@\FInjectPinnedId\endcsname{0}%
}
\newenvironment{FInjectPinnedFigure}[4][figure]{%
  \def\FInjectPinnedId{#2}%
  \expandafter\xdef\csname FInjectPinnedPage@#2\endcsname{#3}%
  \expandafter\gdef\csname FInjectPinnedColumn@#2\endcsname{#4}%
  \def\FInjectTargetColumn{#4}%
  \def\FInjectBothColumns{both}%
  \ifx\FInjectTargetColumn\FInjectBothColumns
    \@dblfloat{#1}[!t]%
  \else
    \@float{#1}[!t]%
  \fi
}{%
  \@endfloatbox
  \@largefloatcheck
  \ifx\FInjectTargetColumn\FInjectBothColumns
    \global\dp\@currbox1sp% Native LaTeX flag for a double-column float.
  \fi
  \expandafter\global\expandafter\let\csname FInjectPinnedBox@\FInjectPinnedId\endcsname\@currbox
  \expandafter\gdef\csname FInjectPinnedPending@\FInjectPinnedId\endcsname{1}%
}
\newcommand{\FInjectReleasePinnedFigure}[1]{%
  \ifnum\csname FInjectPinnedPending@#1\endcsname=1\relax
    \ifnum\c@page=\csname FInjectPinnedPage@#1\endcsname\relax
      \def\FInjectCurrentColumn{left}%
      \if@firstcolumn\else\def\FInjectCurrentColumn{right}\fi
      \edef\FInjectTargetColumn{\csname FInjectPinnedColumn@#1\endcsname}%
      \ifx\FInjectCurrentColumn\FInjectTargetColumn
        \begingroup
          \let\@elt\relax
          \xdef\@deferlist{\@elt\csname FInjectPinnedBox@#1\endcsname\@deferlist}%
        \endgroup
        \expandafter\gdef\csname FInjectPinnedPending@#1\endcsname{0}%
        \typeout{FInject pinned figure released: page \csname FInjectPinnedPage@#1\endcsname, \FInjectCurrentColumn\space column}%
      \fi
    \fi
  \fi
}
\AddToHook{cmd/@startcolumn/before}{%
  \@for\FInjectPinnedId:=\FInjectPinnedIds\do{%
    \FInjectReleasePinnedFigure{\FInjectPinnedId}%
  }%
}
\newcommand{\FInjectReleasePinnedDoubleFigure}[1]{%
  \ifnum\csname FInjectPinnedPending@#1\endcsname=1\relax
    \ifnum\c@page=\csname FInjectPinnedPage@#1\endcsname\relax
      \def\FInjectBothColumns{both}%
      \edef\FInjectTargetColumn{\csname FInjectPinnedColumn@#1\endcsname}%
      \ifx\FInjectTargetColumn\FInjectBothColumns
        \begingroup
          \let\@elt\relax
          \xdef\@deferlist{\@elt\csname FInjectPinnedBox@#1\endcsname\@deferlist}%
        \endgroup
        \expandafter\gdef\csname FInjectPinnedPending@#1\endcsname{0}%
        \typeout{FInject pinned figure released: page \csname FInjectPinnedPage@#1\endcsname, both columns}%
      \fi
    \fi
  \fi
}
\AddToHook{cmd/@startdblcolumn/before}{%
  \@for\FInjectPinnedId:=\FInjectPinnedIds\do{%
    \FInjectReleasePinnedDoubleFigure{\FInjectPinnedId}%
  }%
}
\AtEndDocument{%
  \@for\FInjectPinnedId:=\FInjectPinnedIds\do{%
    \ifnum\csname FInjectPinnedPending@\FInjectPinnedId\endcsname=1\relax
      \PackageError{FInject}{Pinned figure did not reach its target column}{}%
    \fi
  }%
}
\makeatother
'''
 pinned_preamble=pinned_preamble.replace('FINJECTPINNEDIDS',','.join(str(i+1) for i in range(len(pinned_figures))))
 main=main.replace(r'\begin{document}',pinned_preamble+r'\begin{document}',1)
 main=main.replace(r'\maketitle',r'\maketitle'+'\n'+r'\input{pinned-figures}',1)
appendix_columns=False
for x in parts:
 if x['id']=='abstract':continue
 is_appendix=x['en'].startswith('Appendix')
 if CURRENT_LAYOUT and is_appendix:
  if x['id']=='s11-workflow':
   if x.get('pdf_after_references')=='same-page':
    # Use the free space after references for the full-width workflow.
    main+='\\FloatBarrier\n\\bibliography{references}\n\\begin{strip}\n\\appendix\n\\raggedbottom\n'
    main+=r'\input{sections/'+section_filename(x)[:-4]+'}\n'
    main+='\\end{strip}\n\\onecolumn\n\\raggedbottom\n'
    continue
   main+='\\FloatBarrier\n\\bibliography{references}\n\\onecolumn\n\\appendix\n\\raggedbottom\n'
  if (not x['level'] or x.get('pdf_top_table_pair')) and appendix_columns:
   main+='\\end{multicols}\n';appendix_columns=False
  if x.get('pdf_start_page'):
   if appendix_columns:main+='\\end{multicols}\n';appendix_columns=False
   main+='\\clearpage\n'
  if x['level'] and not appendix_columns and not x.get('pdf_top_table_pair'):
   main+='\\begin{multicols}{2}\\raggedcolumns\n'
  main+=r'\input{sections/'+section_filename(x)[:-4]+'}\n'
  appendix_columns=True
  continue
 if is_appendix and (x['level']==0 or x['id'] in appendix_fullwidth_tables) and appendix_columns:
  main+='\\end{multicols}\n';appendix_columns=False
 if x['id']=='s11-workflow':main+='\\FloatBarrier\n\\bibliography{references}\n\\onecolumn\n\\appendix\n\\raggedbottom\n'
 if not CURRENT_LAYOUT and not x['en'].startswith('Appendix') and x['level']==0 and x['id'] not in ['s11-related','s4','conclusion','s6','s7','s8','s9','s10']:main+='\\FloatBarrier\n'
 if CURRENT_LAYOUT and x['id']=='s8':main+='\\FloatBarrier\n\\clearpage\n'
 if x['id']=='s11-prompts':main+='\\FloatBarrier\n'
 if x['id'] in appendix_top_figures:
  # Start the section in two columns, then place its diagram above the continuation.
  if appendix_columns:main+='\\end{multicols}\n';appendix_columns=False
  if not x.get('pdf_continue_previous_page'):main+='\\clearpage\n'
  main+='\\begin{multicols}{2}\\raggedcolumns\n'
  main+=r'\input{sections/'+section_filename(x)[:-4]+'}\n'
  main+='\\end{multicols}\n'
  if x['id'] in appendix_prefix_figures:
   main+=r'\input{sections/'+section_filename(x)[:-4]+'-prefix-figure}\n'
  main+='\\clearpage\n'
  main+=r'\input{sections/'+section_filename(x)[:-4]+'-figure}\n'
  if x.get('pdf_continuation_figure_own_page'):
   # Keep an enlarged continuation figure on its own page before the text.
   main+='\\clearpage\n'
  main+='\\begin{multicols}{2}\\raggedcolumns\n'
  main+=r'\input{sections/'+section_filename(x)[:-4]+'-continuation}\n'
  main+='\\end{multicols}\n\\clearpage\n\\begin{multicols}{2}\\raggedcolumns\n'
  appendix_columns=True
  continue
 if x['id'] in appendix_bottom_figures:
  # Balance the section text above its full-width figure on a dedicated page.
  if appendix_columns:main+='\\end{multicols}\n';appendix_columns=False
  main+='\\clearpage\n\\begin{multicols}{2}\\raggedcolumns\n'
  main+=r'\input{sections/'+section_filename(x)[:-4]+'}\n'
  main+='\\end{multicols}\n\\vfill\n'
  main+=r'\input{sections/'+section_filename(x)[:-4]+'-figure}\n'
  if not x.get('pdf_continue_after_bottom_figure'):
   main+='\\clearpage\n\\begin{multicols}{2}\\raggedcolumns\n'
   appendix_columns=True
  continue
 if x.get('pdf_start_column'):main+='\\newpage\n'
 if x.get('pdf_start_page'):main+='\\clearpage\n'
 if is_appendix and x['level'] and not appendix_columns and x['id'] not in appendix_fullwidth_tables:
  main+='\\begin{multicols}{2}\\raggedcolumns\n';appendix_columns=True
 main+=r'\input{sections/'+section_filename(x)[:-4]+'}\n'
 if x['id'] in appendix_end_figures:
  # Full-width examples follow their section outside the two-column text.
  if not appendix_columns:raise ValueError('Section-end figure outside appendix columns: '+x['id'])
  main+='\\end{multicols}\n'
  main+=r'\input{sections/'+section_filename(x)[:-4]+'-figure}\n'
  appendix_columns=False
 if is_appendix and (x['level']==0 or x['id'] in appendix_fullwidth_tables) and x['id']!='s11-workflow':appendix_columns=True
if appendix_columns:main+='\\end{multicols}\n'
main+='\\end{document}\n'
import hashlib
source_hash=hashlib.sha256(draft_bytes).hexdigest()
main='% Canonical Draft SHA256: '+source_hash+'\n'+main
(OUT/'main.tex').write_text(main)
for x in parts:
 old=OUT/'sections'/(x['id']+'.tex')
 if old.name!=section_filename(x) and old.exists():old.unlink()
print('Converted',len(parts),'sections,',len(alltab),'intact tables,',len(allfig),'figures; Draft:',source_hash)
