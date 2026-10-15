"""One automatic run index for the numbered artifact stages."""
from pathlib import Path
import json

STAGES = (
 ('00-data-preparation','데이터 준비'),('01-source','원문 비교'),
 ('02-calculation','계산과 정답'),('03-graph','계산 그래프 작성'),
 ('04-perturbation','그래프 변경'),('05-text','문장과 답변'),
 ('06-human-review','사람 판정'),('07-freeze-experiment','동결·실험'),
 ('08-records','전체 기록'),
)

def write_index(case, finalize=False):
    case=Path(case)
    def write(relative,value):
        p=case/relative;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    index_name='08-records/02-file-index/00-index.json'
    files=sorted(p.relative_to(case).as_posix() for p in case.rglob('*') if p.is_file() and p.name!='README.md' and p.relative_to(case).as_posix()!=index_name)
    write(index_name,{'stages':[{'directory':folder,'title':title,'files':[p for p in files if p.startswith(folder+'/')]} for folder,title in STAGES],'root_records':[p for p in files if '/' not in p]})
    write('08-records/01-run-summary/01-references.json',{'calculation':'run.json','human_review':'06-human-review/03-result.json','note':'References to actual results; human decision remains pending until recorded.'})
    RunLogs = __import__('finarch.shared.run_logging.run_logs', fromlist=['RunLogs']).RunLogs
    log_context=RunLogs.for_case(case);logs=log_context.directory
    case_logs=logs/(log_context.round or '')/(log_context.context_path or case.name)
    write('08-records/03-log-index/01-files.json',{'default_log':str(logs/'default.log'),'round_default_log':str(logs/(log_context.round or '')/'default.log'),'files':[str(p) for p in sorted(case_logs.rglob('*.log'))]})
    sections=[]
    for folder,title in STAGES:
        matches=[p for p in files if p.startswith(folder+'/')]
        sections+=['## '+folder+' · '+title,'']
        sections+=['- ['+p+']('+p+')' for p in matches] or ['미실행 또는 아직 산출물 없음.']
        sections+=['']
        if finalize and matches:
            (case/folder/'README.md').write_text('# '+title+'\n\n실제 저장 순서의 하위 폴더를 따라 읽습니다. 각 파일은 경로에 표시된 단계의 입력·원응답·검사·결과입니다.\n\n'+'\n'.join('- ['+p[len(folder)+1:]+']('+p[len(folder)+1:]+')' for p in matches)+'\n')
    (case/'README.md').write_text(Path(__file__).with_name('numbered-readme.md').read_text().format(case_name=case.name,sections='\n'.join(sections)))
