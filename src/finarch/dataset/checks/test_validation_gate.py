import copy
import json
import tempfile
import unittest
from pathlib import Path
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
StepStopped = __import__('finarch.dataset.90-operations.staging', fromlist=['StepStopped']).StepStopped
from finarch.dataset.shared.calculation.validation_gate import record_gate, load_eligible, require_eligible
from finarch.shared.reference import Reference, compare


class ValidationGateChecks(unittest.TestCase):
    def test_gold_failure_is_saved_and_never_loads_for_next_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx=RunContext(Path(directory)/'case',{})
            program={'code':'answer=1'}
            ctx.save('02-calculation/02-prepare-code/03-program.json',program)
            comparison=compare('1',Reference('2','integer',0))
            ctx.save('02-calculation/04-compare-answer/01-comparison.json',comparison)
            decision=record_gate(ctx,comparison,program)
            self.assertEqual(decision['disposition'],'EXCLUDED')
            self.assertFalse(decision['automatic_retry'])
            with self.assertRaises(StepStopped):load_eligible(ctx.root)
            self.assertTrue((ctx.root/'02-calculation/02-prepare-code/03-program.json').exists())

    def test_pass_accepts_same_code_but_changed_code_or_missing_gate_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx=RunContext(Path(directory)/'case',{})
            program={'code':'answer=1'}
            ctx.save('02-calculation/02-prepare-code/03-program.json',program)
            comparison=compare('1',Reference('1','integer',0))
            ctx.save('02-calculation/04-compare-answer/01-comparison.json',comparison)
            decision=record_gate(ctx,comparison,program)
            self.assertEqual(load_eligible(ctx.root)['program'],program)
            with self.assertRaises(StepStopped):require_eligible(decision,{'code':'answer=2'})
            with self.assertRaises(StepStopped):require_eligible({},program)

    def test_exact_and_display_agreement_are_distinct(self):
        result=compare('-1.25',Reference('-1.3','float',1))
        self.assertTrue(result['normalized_matches'])
        self.assertFalse(result['exact_matches'])
        self.assertTrue(compare('0',Reference('0','integer',0))['exact_matches'])
