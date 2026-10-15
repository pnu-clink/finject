"""Navigation tree over actual artifact paths, shared with the on-disk layout."""
STAGES = __import__('finarch.dataset.90-operations.numbered_layout', fromlist=['STAGES']).STAGES

def build_flow(artifacts):
    result=[]
    stages = STAGES
    if any(p.startswith(('03-calculation/', '02-review/', '02-review-and-correct/')) for p in artifacts):
        stages = (('01-source','원문 비교'),('02-review','원본 검토'),('03-calculation','계산과 정답'),('04-graph','계산 그래프'),('05-verification','계산 검증'),('06-exception-handler','오류 진단·피드백'),('07-human-review','사람 검토'))
    for directory,title in stages:
        tree={'path':directory,'title':title,'files':[],'children':{},'failures':[]}
        for path,value in sorted(artifacts.items()):
            if not path.startswith(directory+'/') or path.endswith('README.md'):continue
            parts=path[len(directory)+1:].split('/');node=tree
            failed=isinstance(value,dict) and value.get('status') in ('FAIL','ERROR','CANCELLED')
            if failed:node['failures'].append(path)
            for part in parts[:-1]:
                parent=node
                node=parent['children'].setdefault(part,{'path':parent['path']+'/'+part,'title':part,'files':[],'children':{},'failures':[]})
                if failed:node['failures'].append(path)
            node['files'].append({'path':path,'name':parts[-1],'failed':failed,'reason':value.get('reason') if isinstance(value,dict) else None})
        result.append(tree)
    return result
