"""Export the native rect/text/path subset of the authored evidence figures to PDF."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import toColor as HexColor

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'paper/asset/.build/v2-evidence-draft/output'
pdfmetrics.registerFont(TTFont('Arial','/System/Library/Fonts/Supplemental/Arial.ttf'))
pdfmetrics.registerFont(TTFont('ArialBold','/System/Library/Fonts/Supplemental/Arial Bold.ttf'))
for file in OUT.glob('*.svg'):
    root=ET.fromstring(file.read_text());w=float(root.attrib['width']);height=float(root.attrib['height'])
    pdf=canvas.Canvas(str(file.with_suffix('.pdf')),pagesize=(w*.75,height*.75))
    pdf.scale(.75,.75)
    for node in root:
        tag=node.tag.split('}')[-1];a=node.attrib
        if tag=='rect':
            pdf.setFillColor(HexColor(a.get('fill','#FFFFFF')))
            stroke='stroke' in a
            if stroke:pdf.setStrokeColor(HexColor(a['stroke']));pdf.setLineWidth(1)
            pdf.rect(float(a.get('x',0)),height-float(a.get('y',0))-float(a['height']),float(a['width']),float(a['height']),fill=1,stroke=int(stroke))
        elif tag=='text':
            pdf.setFillColor(HexColor(a['fill']));pdf.setFont('ArialBold' if a['font-weight']=='700' else 'Arial',float(a['font-size']))
            pdf.drawString(float(a['x']),height-float(a['y']),node.text or '')
        elif tag=='path':
            tokens=re.findall(r'[MmHhVvLlZz]|-?\d+(?:\.\d+)?',a['d']);i=0;x=y=0;path=pdf.beginPath()
            while i<len(tokens):
                op=tokens[i];i+=1
                if op=='M':x=float(tokens[i]);y=float(tokens[i+1]);i+=2;path.moveTo(x,height-y)
                elif op=='h':x+=float(tokens[i]);i+=1;path.lineTo(x,height-y)
                elif op=='H':x=float(tokens[i]);i+=1;path.lineTo(x,height-y)
                elif op=='v':y+=float(tokens[i]);i+=1;path.lineTo(x,height-y)
                elif op=='l':
                    # Repeated relative pairs after one l command.
                    while i<len(tokens) and re.match(r'^-?\d',tokens[i]):
                        x+=float(tokens[i]);y+=float(tokens[i+1]);i+=2;path.lineTo(x,height-y)
                elif op.lower()=='z':path.close()
                else:raise ValueError(op)
            fill='fill' in a;stroke='stroke' in a
            if fill:pdf.setFillColor(HexColor(a['fill']))
            if stroke:pdf.setStrokeColor(HexColor(a['stroke']));pdf.setLineWidth(float(a.get('stroke-width',1)))
            pdf.drawPath(path,fill=int(fill),stroke=int(stroke))
    pdf.showPage();pdf.save();print(file.with_suffix('.pdf'))
