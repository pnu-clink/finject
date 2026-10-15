"""English production instructions; Korean remains presentation-only."""
import json
import re
import unittest
from pathlib import Path
from finarch.shared.providers.cli import prepare_instruction
from finarch.dataset.shared.review.audit_prompts import FILES as AUDIT_TYPES
GENERATION_TYPES = __import__('finarch.dataset.02-generation.02-generate-text.realization_prompts', fromlist=['FILES']).FILES
from finarch.dataset.schemas.registry import describe
name_constants = __import__('finarch.dataset.02-generation.operations.stepwise', fromlist=['name_constants']).name_constants

HANGUL=re.compile(r'[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]')
class EnglishProductionTests(unittest.TestCase):
 def test_all_active_prompts_and_schemas(self):
  for role,axes in [('01-preparation.03-calculation.pot',[None]),('02-generation.02-generate-text.realization',GENERATION_TYPES),('shared.01-02.02-03.review-and-validation',AUDIT_TYPES),('01-preparation.02-review-and-correct.revision',[None])]:
   for axis in axes:
    with self.subTest(role=role,axis=axis):
     instruction,_=prepare_instruction(role,{'axis':axis})
     self.assertIsNone(HANGUL.search(instruction))
     self.assertIn('English',instruction)
     self.assertNotIn('specific Korean reason',instruction)
     schema=json.dumps(describe(role+'.response')['schema'],ensure_ascii=False)
     self.assertIsNone(HANGUL.search(schema))
     self.assertNotIn('Korean explanation',schema)
 def test_python_generated_annotations_are_english(self):
  result,metadata=name_constants({'code':'a = fact("principal")\nanswer = a * 2\n','facts':{}})
  self.assertIsNone(HANGUL.search(json.dumps([result,metadata],ensure_ascii=False)))
 def test_production_configuration_has_no_korean(self):
  root=Path(__file__).resolve().parents[4]/'config'
  for name in ('llm.json',):
   self.assertIsNone(HANGUL.search((root/name).read_text()),name)
