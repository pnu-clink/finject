"""Actual source contracts and human review persistence; no model invocation."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

numbers = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['numbers']).numbers
make_request = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['make_request']).make_request
read = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['read']).read
check_response = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['check_response']).check_response
boundaries = __import__('finarch.dataset.02-generation.01-perturbation.production_plan', fromlist=['boundaries']).boundaries
candidate_current = __import__('finarch.dataset.02-generation.05-human-review.human_review', fromlist=['candidate_current']).candidate_current
from finarch.dataset.shared.calculation.python_graph import load_graph
from finarch.dataset.viewer.server import live_events, log_detail
from finarch.dataset.viewer.build import collect, record_decisions

ROOT=(Path(__file__).resolve().parent / '../../../..').resolve()/'reports/run/first-10-pot-validated-v3'


class ProductionChecks(unittest.TestCase):
    def test_sentence_ending_numbers_and_decimals_are_whole(self):
        self.assertEqual(numbers('$12,000. $450. 1.4. 3.5%.'),{Decimal('12000'):1,Decimal('450'):1,Decimal('1.4'):1,Decimal('3.5'):1})
        self.assertNotIn(Decimal('12'),numbers('$12,000.'))

    def test_decimal_dot_does_not_split_sentence_and_table_is_one_row(self):
        c='The rate is 3.5%. Next sentence.'
        self.assertEqual(c[slice(*boundaries(c,[12,16]))],'The rate is 3.5%.')
        c='year | 2019 | 2018\nrate | 1.4 | 3.5\nEnd.'
        self.assertEqual(c[slice(*boundaries(c,[25,28]))],'rate | 1.4 | 3.5')

    def test_all_saved_plans_build_valid_requests_without_bank_template(self):
        for case in ROOT.glob('test-*'):
            if not (case/'04-perturbation/00-receive-input/01-input.json').exists():continue
            spec=read(case/'04-perturbation/00-receive-input/01-input.json');sample=read(case/'00-data-preparation/01-select-input/01-input.json');program=read(case/'02-calculation/02-prepare-code/03-program.json');graph=load_graph(case)
            for v in read(case/'04-perturbation/05-list-candidates/03-result.json'):
                req=make_request(case,v,sample,program,graph,spec['value_intent'])
                self.assertEqual(req['context'],sample['context']);self.assertEqual(req['question'],sample['question'])
                self.assertNotIn('same bank and explicit past quarter',str(req['instructions'])+str(req['edit_slots']))
                for slot in req['edit_slots']:self.assertEqual(sample['context'][slot['start']:slot['end']],slot['before'])

    def test_equal_amounts_for_other_years_are_preserved_in_ea(self):
        case=ROOT/'test-0010';sample=read(case/'00-data-preparation/01-select-input/01-input.json');program=read(case/'02-calculation/02-prepare-code/03-program.json');graph=load_graph(case)
        v=next(v for v in read(case/'04-perturbation/05-list-candidates/03-result.json') if v['label']=='EA_01')
        req=make_request(case,v,sample,program,graph)
        response={'patches':[{k:s[k] for k in ('start','end','before','text','element_ids')} for s in req['edit_slots']]}
        final,_=check_response(req,response)
        self.assertEqual(final['context'].count('15.3'),2)
        self.assertEqual(final['question'],sample['question'])
        self.assertEqual(v['plan']['result']['answer'],None)

    def test_review_hash_ignores_logs_but_detects_changed_production(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'run.json').write_text('{}');(root/'context.json').write_text('{"context":"a"}')
            digest = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['digest']).digest
            review={'variant':'ANSWER','status':'AWAITING_HUMAN','review_sha256':'candidate1','reference_hashes':{'context.json':digest(root/'context.json')}}
            (root/'05-text').mkdir();(root/'06-human-review/03-result.json').write_text(json.dumps([review]))
            payload={'snapshot_sha256':'not-the-current-case-log-snapshot','decisions':[{'variant':'ANSWER','review_sha256':'candidate1','decision':'APPROVE','reviewer':'local fixture','reason':'fixture only','reviewed_at':'2026-09-09T00:00:00+09:00'}]}
            record_decisions(root,payload);(root/'events.jsonl').write_text('{}\n')
            self.assertEqual(collect(root)['decisions']['ANSWER']['decision'],'APPROVE')
            (root/'context.json').write_text('{"context":"changed"}')
            self.assertFalse(candidate_current(root,review));self.assertEqual(collect(root)['decisions'],{})
            with self.assertRaisesRegex(ValueError,'REVIEW_TARGET_CHANGED'):record_decisions(root,payload)

    def test_live_log_preserves_partial_lines_and_real_phase_ids(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);case=root/'batch/test-0001';case.mkdir(parents=True)
            (case/'events.jsonl').write_text('{"phase":"START","call_id":"x","kind":"llm"}\n{')
            out=live_events(root,'batch');self.assertEqual(out['events'][0]['phase'],'START');self.assertEqual(out['events'][0]['call_id'],'x')
            self.assertEqual(len(out['damaged']),1)
            with self.assertRaises(ValueError):live_events(root,'../other')

    def test_failure_detail_uses_exact_line_and_same_span_artifact(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);case=root/'batch/test-0001';case.mkdir(parents=True)
            (case/'reason.json').write_text('{"reason":"fixture failure"}')
            events=[{'phase':'END','call_id':'child','parent_call_id':'parent','status':'FAIL'},
                    {'phase':'ARTIFACT','call_id':'other','path':'wrong.json'},
                    {'phase':'ARTIFACT','call_id':'parent','path':'reason.json'}]
            (case/'events.jsonl').write_text('\n'.join(map(json.dumps,events)))
            result=log_detail(root,'batch','test-0001',1)
            self.assertEqual(result['event'],events[0])
            self.assertEqual(result['following_artifact']['content']['reason'],'fixture failure')
            with self.assertRaises(ValueError):log_detail(root,'batch','../outside',1)
            with self.assertRaises(ValueError):log_detail(root,'batch','test-0001',0)
            (case/'reason.json').unlink();(case/'reason.json').symlink_to(root/'secret.json')
            (root/'secret.json').write_text('{"secret":true}')
            self.assertIsNone(log_detail(root,'batch','test-0001',1)['following_artifact'])

    def test_audit_failure_uses_failed_criterion_and_own_saved_report(self):
        from finarch.dataset.shared.review.dtt_audit import audit_event_reason
        report={'status':'FAIL','state_reason':'expected deletion',
                'findings':[{'criterion':'readability','judgment':'FAIL','reason':'dangling currency'}]}
        self.assertEqual(audit_event_reason(report),'readability: dangling currency')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);case=root/'batch/test-0001';(case/'audit').mkdir(parents=True)
            (case/'audit/03-result.json').write_text(json.dumps(report))
            events=[{'phase':'START','call_id':'audit'},
                    {'phase':'ARTIFACT','call_id':'audit','path':'audit/03-result.json'},
                    {'phase':'ARTIFACT','call_id':'other','path':'wrong/03-result.json'},
                    {'phase':'END','call_id':'audit','parent_call_id':'outer','status':'FAIL','reason':'expected deletion'}]
            original='\n'.join(map(json.dumps,events));(case/'events.jsonl').write_text(original)
            result=log_detail(root,'batch','test-0001',4)
            self.assertEqual(result['audit_artifact']['content'],report)
            self.assertEqual(result['event']['reason'],'expected deletion')
            self.assertEqual((case/'events.jsonl').read_text(),original)
            events[1]['call_id']='other';(case/'events.jsonl').write_text('\n'.join(map(json.dumps,events)))
            self.assertIsNone(log_detail(root,'batch','test-0001',4)['audit_artifact'])


if __name__=='__main__':unittest.main()
