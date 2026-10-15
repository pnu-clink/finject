"""POT receives output metadata but not the numeric reference answer."""
import importlib
import unittest
from unittest.mock import patch
from finarch.dataset.schemas.llm import ProgramRequest
from finarch.shared.providers.input_policy import validate_model_input


class MetadataChecks(unittest.TestCase):
    def setUp(self):
        self.sample = {'context':'Revenue is 25.', 'question':'Report revenue.', 'raw_id':'example',
                       'reference_answer':'25', 'reference_answer_type':'float', 'reference_precision':2,
                       'answer_metadata':{'scale':'million', 'negative':False}}

    def check_request(self, request):
        ProgramRequest.model_validate(request, strict=True)
        validate_model_input('01-preparation.03-calculation.pot', request)
        self.assertNotIn('reference_answer', request)
        for key in ('reference_answer_type', 'reference_precision', 'answer_metadata'):
            self.assertEqual(request[key], self.sample[key])

    def test_initial_request(self):
        module = importlib.import_module('finarch.dataset.01-preparation.03-calculation.stage')
        owner = self
        class Context:
            def invoke(self, stage, step, role, request, **kwargs):
                owner.check_request(request)
                raise RuntimeError('captured-before-call')
        with self.assertRaisesRegex(RuntimeError, 'captured-before-call'):
            module.calculate(Context(), None, self.sample, {})

    def test_independent_request(self):
        module = importlib.import_module('finarch.dataset.01-preparation.03-calculation.preparation_repairs')
        def capture(ctx, config, stage, role, request, prompt):
            self.check_request(request)
            raise RuntimeError('captured-before-call')
        with patch.object(module, 'invoke', side_effect=capture), self.assertRaisesRegex(RuntimeError, 'captured-before-call'):
            module.resolve_mismatch(None, None, self.sample, {}, {})

    def test_metadata_required_and_gold_forbidden(self):
        request = {k:v for k,v in self.sample.items() if k not in ('reference_answer','raw_id')}
        for key in ('reference_answer_type','reference_precision','answer_metadata'):
            with self.assertRaises(ValueError):
                ProgramRequest.model_validate({k:v for k,v in request.items() if k!=key})
        with self.assertRaises(ValueError):
            validate_model_input('01-preparation.03-calculation.pot', {**request,'reference_answer':'25'})
        request['answer_metadata'] = {'scale':None, 'negative':True}
        ProgramRequest.model_validate(request, strict=True)
