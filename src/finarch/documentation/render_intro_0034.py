"""Render a source-grounded explanatory figure; no model responses are generated."""
from pathlib import Path
import json, hashlib
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'reports/run/20261002-intro-figure-0034'
SOURCE=ROOT/'reports/run/20260917-002/02-generation/03-round/test-0034/01-ic-value-before/run.json'
d=json.loads(SOURCE.read_text())
assert d['status']=='PASS' and d['plan']['alternative']=='20.9'
assert d['plan']['execution']['exact_value']=='33'
OUT.mkdir(exist_ok=True,parents=True)
record={'source':str(SOURCE.relative_to(ROOT)),'sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'generation_status':d['status'],'audit':d['audit'],'question':d['observation']['question'],'inserted_claim':d['patches'][0]['text'],'original_quote':d['plan']['original_graph']['source_usage'][0]['quote'],'context':d['observation']['context'],'answer_A':31,'conditional_answer_B':33,'figure_response_status':'AUTHOR_ILLUSTRATION_NOT_MODEL_OUTPUT_OR_GOLD_LABEL','comparison':'Original numerical QA versus controlled conflicting evidence; not an exhaustive claim about prior benchmarks.'}
(OUT/'source-evidence.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
W,H=1000,760
c=canvas.Canvas(str(OUT/'finject-introduction-0034.pdf'),pagesize=(W,H))
c.setTitle('FInject: from numerical answers to evidence-grounded decisions')
INK='#142C3C'; MUTED='#526777'; BLUE='#23628A'; TEAL='#08786E'; ORANGE='#AE5914'
def box(x,y,w,h,fill='#FFFFFF',stroke='#CED8DE',r=8):
 c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(stroke));c.setLineWidth(1);c.roundRect(x,H-y-h,w,h,r,fill=1,stroke=1)
def text(x,y,s,size=16,bold=False,color=INK):
 c.setFillColor(HexColor(color));c.setFont('Helvetica-Bold' if bold else 'Helvetica',size);c.drawString(x,H-y-size,s)
def para(x,y,w,s,size=16,color=INK,leading=None):
 st=ParagraphStyle('p',fontName='Helvetica',fontSize=size,leading=leading or size*1.25,textColor=HexColor(color))
 p=Paragraph(s,st);_,h=p.wrap(w,1000);p.drawOn(c,x,H-y-h);return h
def line(x1,y1,x2,y2,color='#97AAB5',width=1.4):
 c.setStrokeColor(HexColor(color));c.setLineWidth(width);c.line(x1,H-y1,x2,H-y2)
def arrow(x,y1,y2,color=BLUE):
 line(x,y1,x,y2,color,1.8);c.setFillColor(HexColor(color));p=c.beginPath();p.moveTo(x,H-y2);p.lineTo(x-5,H-y2+8);p.lineTo(x+5,H-y2+8);p.close();c.drawPath(p,fill=1,stroke=0)
def robot(x,y):
 box(x,y+5,26,21,'#FFFFFF','#537B8C',4);line(x+13,y,x+13,y+5,'#537B8C');
 c.setFillColor(HexColor('#537B8C'))
 for xx in (x+8,x+18):c.circle(xx,H-y-13,2,fill=1,stroke=0)
 line(x+8,y+21,x+18,y+21,'#537B8C')

text(24,18,'Beyond a number: justify answering or abstaining',26,True)
text(24,53,'FInject  |  Financial numerical reasoning under conflicting or missing evidence',16,color=MUTED)
box(24,83,952,73,'#F4F7FA')
text(40,95,'QUESTION',11,True,BLUE)
para(137,94,822,'As of December 31, 2005, what was the before-tax charge related to adopting FIN No. 47?<br/>Answer in millions, rounded to the nearest integer.',16)

text(24,174,'Conventional numerical QA',21,True,BLUE)
text(402,174,'FInject: controlled evidence conflict',21,True,TEAL)
box(24,208,350,129,'#F2F7FB','#B8CDD9')
text(40,220,'ORIGINAL CONTEXT',11,True,BLUE)
para(40,245,317,'Net-of-tax charge: <b>$19 million</b><br/>Related taxes: <b>$12 million</b>',18)
text(40,304,'Consistent inputs for the reference calculation',12,color=MUTED)
box(402,208,574,129,'#FFFFFF','#A8C9C5')
box(416,219,546,50,'#FFF1E5','#E5C3A2',5)
text(427,225,'E1  INSERTED BEFORE',10,True,ORANGE)
para(574,225,375,'2005 FIN No. 47 net-of-tax charge:<br/><b>$20.9 million</b>',14)
box(416,276,546,49,'#F2F7FB','#B8CDD9',5)
text(427,283,'E2  ORIGINAL RETAINED',10,True,BLUE)
para(574,282,375,'A charge of <b>$19 million</b>,<br/>net of taxes of <b>$12 million</b>.',14)
arrow(199,338,357);arrow(689,338,357,TEAL)
box(24,360,952,63,'#F7F9FA','#BFCBD2')
text(43,380,'FINANCE AGENTS',14,True)
for x,label in ((282,'Agent A'),(480,'Agent B'),(678,'Agent C')):
 robot(x,376);text(x+39,379,label,17,True)
text(861,383,'same inputs',12,color=MUTED)
arrow(199,424,446);arrow(689,424,446,TEAL)

box(24,450,350,231,'#F2F7FB','#B8CDD9')
text(40,466,'NUMERICAL ANSWER',11,True,BLUE)
text(40,495,'31 million',34,True,BLUE)
text(40,545,'19 + 12 = 31',21)
line(40,583,358,583,'#B8CDD9')
para(40,600,314,'Evaluation focus:<br/><b>Is the numerical answer correct?</b>',16)

box(402,450,574,231,'#F3FAF8','#A8C9C5')
text(419,465,'DECISION',11,True,TEAL)
text(520,461,'ABSTAIN  /  answer: null',20,True,TEAL)
text(419,493,'Illustrative response, not a measured agent output',11,color=MUTED)
line(419,518,959,518,'#B9D7D1')
text(419,530,'CLASSIFICATION',11,True,TEAL)
text(573,526,'IC-value: conflicting values',16,True)
text(419,562,'REASON',11,True,TEAL)
para(573,555,381,'The same charge is reported as 19 and 20.9.<br/>Using each yields a different answer: <b>31 vs. 33</b>.',14)
text(419,611,'EVIDENCE',11,True,TEAL)
para(573,604,381,'<b>E1:</b> inserted $20.9 million claim<br/><b>E2:</b> original $19 million charge and $12 million taxes',14)

text(24,697,'FInject checks the decision together with classification, reason, and cited evidence.',17,True,TEAL)
para(24,726,954,'test-0034 / IC-value before. Context excerpts are condensed. Generation audit: PASS; human judgment: pending.<br/>The abstention response illustrates the evaluation format, not a gold label. This case illustrates conflict; missing-evidence cases are also in scope.',10,color=MUTED,leading=12)
c.showPage();c.save()
print(OUT/'finject-introduction-0034.pdf')
