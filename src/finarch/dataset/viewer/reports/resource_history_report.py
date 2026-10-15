"""Build a historical resource report from preserved macOS samples; never invent gaps."""
import base64
import json
import re
from datetime import datetime
from html import escape
from pathlib import Path


def build(root, evidence):
    root,evidence=Path(root),Path(evidence)
    timing=json.loads((root/'timing-report.json').read_text())
    lifecycle=json.loads((root/'timing.json').read_text())
    dashboard=json.loads((evidence/'systemstats-dashboard.json').read_text())[0]
    page=dashboard['page_size'];total=dashboard['mem_size']
    samples=[];missing=[]
    for match in re.finditer(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\tSystemMemory \{([\s\S]*?)^\}',(evidence/'systemstats.txt').read_text(),re.M):
        values={k:int(v) for k,v in re.findall(r'"?(\w+)"?\s*=\s*(\d+);',match[2])}
        if 'purgeable_count' not in values:
            missing.append({'timestamp':match[1]+'+09:00','reason':'purgeable_count not present; not assumed zero'})
            continue
        # Report the preserved categories explicitly, rather than claiming a live Stats reading.
        used=(values['internal_page_count']+values['wired_count']+values['compressor_page_count']-values.get('purgeable_count',0))*page
        samples.append({'timestamp':match[1]+'+09:00','bytes':used,'internal_bytes':values['internal_page_count']*page,'wired_bytes':values['wired_count']*page,'compressed_bytes':values['compressor_page_count']*page,'purgeable_bytes':values.get('purgeable_count',0)*page,'swap_bytes':values['swap_used']})
    report={'run_id':root.name,'scope':'whole_computer','timezone':'Asia/Seoul','started_at':lifecycle['started_at'],'ended_at':lifecycle['ended_at'],
            'rounds':timing['rounds'],'cpu':{'status':'UNAVAILABLE','samples':[],'reason':'No timestamped total CPU utilization samples were found. Coalition CPU accounting is not substituted for host utilization.'},
            'memory':{'status':'PARTIAL','total_bytes':total,'page_size':page,'definition':'(internal_page_count + wired_count + compressor_page_count - purgeable_count) * page_size','samples':samples,'missing':missing},
            'sources':[str(evidence/'systemstats.txt'),str(evidence/'systemstats-dashboard.json'),str(evidence/'stats-coverage.json')]}
    start=datetime.fromisoformat(report['started_at']).timestamp();end=datetime.fromisoformat(report['ended_at']).timestamp()
    def x(t):return 78+(datetime.fromisoformat(t).timestamp()-start)/(end-start)*1020
    colors=['#dbeafe','#bfdbfe','#93c5fd','#dcfce7','#bbf7d0','#86efac']
    rounds=sorted(report['rounds'],key=lambda r:r['started_at'])
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="850" viewBox="0 0 1200 850"><rect width="1200" height="850" fill="white"/><g font-family="Arial,sans-serif" fill="#172b4d">',f'<text x="30" y="32" font-size="22" font-weight="bold">{escape(root.name)} | CPU / Memory history (KST)</text>',f'<text x="30" y="58" font-size="14">{escape(report["started_at"][:19])} — {escape(report["ended_at"][:19])} | Whole computer, not batch-only</text>']
    for top,title in [(190,'CPU total utilization (%) — no historical samples'),(490,'Memory: internal + wired + compressed - purgeable (GiB)')]:
        svg.append(f'<text x="30" y="{top-24}" font-size="17" font-weight="bold">{title}</text>')
        for i,r in enumerate(rounds):
            a,b=x(r['started_at']),x(r['ended_at']);svg.append(f'<rect x="{a:.2f}" y="{top}" width="{b-a:.2f}" height="190" fill="{colors[i]}" opacity="0.65"/>')
        for n in range(5):
            yy=top+190-n*47.5;value=n*25 if top==190 else n*(total/2**30)/4
            svg.append(f'<line x1="78" x2="1098" y1="{yy}" y2="{yy}" stroke="#cbd5e1"/><text x="65" y="{yy+4}" text-anchor="end" font-size="12">{value:g}</text>')
        if top==190:svg.append(f'<text x="590" y="{top+102}" text-anchor="middle" font-size="20" fill="#64748b">NO DATA — not zero utilization</text>')
        else:
            points=' '.join(f'{x(s["timestamp"]):.2f},{top+190-190*s["bytes"]/total:.2f}' for s in samples)
            svg.append(f'<polyline points="{points}" fill="none" stroke="#7c3aed" stroke-width="2" stroke-dasharray="5 4"/>')
            for s in samples:svg.append(f'<circle cx="{x(s["timestamp"]):.2f}" cy="{top+190-190*s["bytes"]/total:.2f}" r="4" fill="#7c3aed"><title>{s["timestamp"]}: {s["bytes"]/2**30:.3f} GiB</title></circle>')
        for n in range(7):
            t=start+(end-start)*n/6;label=datetime.fromtimestamp(t).strftime('%H:%M:%S')
            svg.append(f'<text x="{78+1020*n/6}" y="{top+214}" text-anchor="middle" font-size="12">{label}</text>')
    for i,r in enumerate(rounds):
        col=i%3;row=i//3;xx=30+col*390;yy=94+row*29
        name=r['round'].replace(' / ',' ').replace('차','').replace('01-round','1').replace('02-round','2').replace('03-round','3')
        svg.append(f'<rect x="{xx}" y="{yy-12}" width="14" height="14" fill="{colors[i]}"/><text x="{xx+20}" y="{yy}" font-size="13">{escape(name)} | {r["started_at"][11:19]}–{r["ended_at"][11:19]}</text>')
    svg.append(f'<text x="30" y="752" font-size="14">Memory: {len(samples)} recorded snapshots (~10 min). Dots are measurements; dashed lines only connect samples.</text><text x="30" y="779" font-size="14">No extrapolation before first / after last memory sample. Stage boundaries use saved execution events.</text><text x="30" y="806" font-size="14">CPU history unavailable in Stats. OS coalition accounting is not total CPU utilization.</text></g></svg>')
    chart=''.join(svg);(root/'resource-history.svg').write_text(chart)
    report['chart_base64']=base64.b64encode(chart.encode()).decode();(root/'resource-history.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (root/'RESOURCE-README.md').write_text(f'# CPU·메모리 과거 기록\n\n실행: {root.name}\n\nresource-history.json은 원본 기록에서 추출한 값과 계산 정의, resource-history.svg는 같은 시간축의 두 차트입니다. 뷰어의 CPU·메모리 버튼에서 확인합니다.\n\nCPU 전체 사용률은 당시 시계열을 찾지 못해 미확인으로 표시했습니다. systemstats의 coalition CPU 계정 지표를 전체 CPU 사용률로 대체하지 않았습니다. 메모리는 내부 페이지+유선 페이지+압축기 페이지−제거 가능한 페이지에 기록된 페이지 크기를 곱한 값입니다. 이 컴퓨터 전체의 기록이며 해당 배치 전용 측정값이 아닙니다. {len(samples)}개 측정 지점 사이의 점선은 가독성을 위한 연결이며 순간 사용량이나 피크를 보장하지 않습니다. 샘플이 없는 양 끝 구간은 채우지 않습니다.\n\n읽는 순서: 뷰어 → resource-history.json → outputs/batch-300-resources/systemstats.txt 및 systemstats-dashboard.json. Stats DB 사본에는 CPU/RAM 시간 키가 없고 현재 값만 있었습니다.\n')
    print(json.dumps({'run':root.name,'cpu':'UNAVAILABLE','memory_samples':len(samples),'memory_min_gib':min(s['bytes'] for s in samples)/2**30,'memory_max_gib':max(s['bytes'] for s in samples)/2**30}))
    return report

if __name__=='__main__':
    import sys
    build(sys.argv[1],sys.argv[2])
