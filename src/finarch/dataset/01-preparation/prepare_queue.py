"""Scheduler-owned case IDs. Interrupted cases restart at source without feedback reuse."""
from pathlib import Path
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
file_hash = __import__('finarch.dataset.90-operations.staging', fromlist=['file_hash']).file_hash


class CaseQueue:
    def __init__(self, bundle, inputs, names, selected, *, resume=False, explicit=False):
        self.bundle=Path(bundle)
        self.path=self.bundle/'01-preparation/schedule-state.json'
        self.state=read(self.path) if self.path.exists() else None
        if self.state:
            if self.state['input_sha256']!=file_hash(inputs.path):
                raise ValueError('RESUME_INPUT_CHANGED')
            if self.state['selected_stages']!=list(selected):
                raise ValueError('RESUME_STAGE_RANGE_CHANGED')
            if not resume:raise ValueError('EXISTING_SCHEDULE_REQUIRES_RESUME')
        else:
            selection=read(self.bundle/'input-selection.json')['cases']
            completed=[]
            if resume:
                for name in selection:
                    marker=self.bundle/'01-preparation'/name/'run.json'
                    if marker.exists() and read(marker).get('status') in ('PASS','FAIL','ERROR'):
                        completed.append(name)
            self.state={'format':'finarch-preparation-queue-v1','case_ids':selection,
                        'input_sha256':file_hash(inputs.path),'selected_stages':list(selected),
                        'pending_ids':[n for n in selection if n not in completed],
                        'running_ids':[],'completed_ids':completed,'attempt':0}
        if selected[0]!='01-source':raise ValueError('CASE_RESTART_REQUIRES_01_SOURCE')
        if len(names)!=len(set(names)) or any(n not in self.state['case_ids'] for n in names):
            raise ValueError('INVALID_QUEUE_CASE_IDS')
        unfinished=set(self.state['pending_ids']+self.state['running_ids'])
        self.targets=list(names) if not resume or explicit else [n for n in self.state['case_ids'] if n in unfinished]
        if not resume and any((self.bundle/'01-preparation'/n).exists() for n in self.targets):
            raise ValueError('EXISTING_CASE_REQUIRES_RESUME')
        self.done=set(self.state['completed_ids'])-set(self.targets)
        # Save IDs before moving directories: a crash leaves every target recoverable.
        self.state.update(attempt=self.state['attempt']+1,status='RUNNING',
                          restart_from='01-source',attempt_ids=self.targets,
                          pending_ids=[n for n in self.state['case_ids'] if n not in self.done],
                          running_ids=[],completed_ids=[n for n in self.state['case_ids'] if n in self.done])
        self.save()
        if resume:
            archive=self.bundle/'restart-history'/f'{self.state["attempt"]:03d}-preparation'
            for name in self.targets:
                source=self.bundle/'01-preparation'/name
                if source.exists():
                    archive.mkdir(parents=True,exist_ok=True)
                    source.rename(archive/name)
            if archive.exists():
                write(archive/'restart.json',{'case_ids':self.targets,'restart_from':'01-source',
                                             'previous_outputs_reused':False})
                (archive/'README.md').write_text('Preserves the previous output of the stop phrase. It\'s not reused in current execution.\n')

    def save(self):
        write(self.path,self.state)

    def observe(self, active):
        self.state['running_ids']=[n for n in active if n not in self.done]
        self.state['pending_ids']=[n for n in self.state['case_ids']
                                  if n not in self.done and n not in self.state['running_ids']]
        self.save()

    def complete(self,name):
        self.done.add(name)
        self.state['completed_ids']=[n for n in self.state['case_ids'] if n in self.done]
        self.observe(self.state['running_ids'])

    def close(self, interrupted=False):
        self.state['status']='INTERRUPTED' if interrupted else (
            'COMPLETED' if len(self.done)==len(self.state['case_ids']) else 'PAUSED')
        self.save()

    def summary(self):
        results=[]
        for name in self.state['case_ids']:
            marker=self.bundle/'01-preparation'/name/'run.json'
            if name in self.done and marker.exists():results.append(read(marker))
        return {'status':self.state['status'],'planned':len(self.state['case_ids']),
                'processed':len(self.done),'results':results,
                'selected_stages':self.state['selected_stages'],'schedule_state':'schedule-state.json'}
