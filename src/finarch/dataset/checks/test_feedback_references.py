"""Reference integrity and actual prompt inclusion, without model calls."""
import importlib
import json
import tempfile
import unittest
from pathlib import Path
publish = __import__('finarch.dataset.90-operations.feedback_records', fromlist=['publish']).publish
load = __import__('finarch.dataset.90-operations.feedback_records', fromlist=['load']).load
record_application = __import__('finarch.dataset.90-operations.feedback_records', fromlist=['record_application']).record_application
from finarch.shared.providers.cli import prepare_instruction

context = importlib.import_module('finarch.dataset.02-generation.04-exception-handler.feedback.feedback_context')


class FeedbackReferenceChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.ref=publish(self.root/'01-round/06-exception-handler/feedback/02-round/feedback.json',
            case='test-a',variant='ANSWER',source_round='01-round',target_round='02-round',
            target_role='01-preparation.03-calculation.pot',axis='ANSWER',guidance='Correct the variable spelling.',source='failure.json')
        self.directory=self.root/'consumer';(self.directory/'pot').mkdir(parents=True)
        (self.directory/'pot/answer.json').write_text(json.dumps({'feedback_refs':[self.ref]}))

    def test_override_prompt_includes_reference_and_records_exact_text(self):
        with context.use_feedback(self.directory,case='test-a',target_round='02-round'):
            instruction,definition=prepare_instruction('01-preparation.03-calculation.pot',{},'Explicit base instruction')
        saved={};record_application(instruction,definition,'01-preparation.03-calculation.pot',lambda n,v:saved.update({n:v}))
        self.assertEqual(instruction.count('Correct the variable spelling.'),1)
        self.assertTrue(saved['01-input/feedback-ref.json']['applied'])
        self.assertEqual(saved['01-input/rendered-prompt.json']['instruction'],instruction)

    def test_wrong_case_and_round_block(self):
        for kwargs in ({'case':'test-b'},{'target_round':'03-round'}):
            with self.assertRaises(ValueError):load(self.ref,**kwargs)

    def test_changed_record_blocks(self):
        Path(self.ref['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):load(self.ref)

    def test_removed_feedback_blocks_submission(self):
        with context.use_feedback(self.directory):
            instruction,definition=prepare_instruction('01-preparation.03-calculation.pot',{})
        with self.assertRaisesRegex(ValueError,'NOT_IN_PROMPT'):
            record_application('missing',definition,'01-preparation.03-calculation.pot',lambda n,v:None)

    def test_non_target_role_records_no_application(self):
        with context.use_feedback(self.directory):
            instruction,definition=prepare_instruction('02-generation.feedback.case-feedback',{})
        saved={};record_application(instruction,definition,'02-generation.feedback.case-feedback',lambda n,v:saved.update({n:v}))
        self.assertFalse(saved['01-input/feedback-ref.json']['applied'])

    def test_context_does_not_leak(self):
        with context.use_feedback(self.directory):pass
        instruction,_=prepare_instruction('01-preparation.03-calculation.pot',{})
        self.assertNotIn('Correct the variable spelling.',instruction)
