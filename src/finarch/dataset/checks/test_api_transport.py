"""Shared entry API checks with a local HTTP double; no paid requests."""
import json
import tempfile
import unittest
import io
from pathlib import Path
from unittest.mock import patch
cli = __import__('finarch.shared.providers.cli', fromlist=['*'])
from finarch.shared.providers.profiles import DEFAULT
class APITransportChecks(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.config=Path(self.tmp.name)/'llm.json'
  self.config.write_text(json.dumps({'provider':'codex','execution_enabled':True,'roles':{'01-preparation.02-review-and-correct.revision':{}},'capabilities':{'01-preparation.02-review-and-correct.revision':{'tools':[],'skills':[]}},'cli_limits':{'timeout_seconds':1}}))
 def run_case(self,text,status='completed',payload=None):
  saved={}; envelope={'status':status,'usage':{'input_tokens':12,'output_tokens':4},'output':[{'type':'message','content':[{'type':'output_text','text':text}]}]}
  replies=[io.BytesIO(b'{"input_tokens":12}'),io.BytesIO(json.dumps(envelope).encode())]
  with patch('finarch.shared.providers.api.api_key',return_value='test-only-secret'),patch('finarch.shared.providers.api.urllib.request.urlopen',side_effect=replies) as http,patch.object(cli,'run_process') as process,patch.object(cli,'inspect_runtime') as runtime:
   result=cli.call(self.config,'01-preparation.02-review-and-correct.revision',payload if payload is not None else {'context':'C','question':'Q','findings':[]},save=lambda n,v:saved.update({n:v}),profile_id='luna-max-api',profiles_path=DEFAULT)
  process.assert_not_called();runtime.assert_not_called()
  self.assertNotIn('test-only-secret',json.dumps(saved))
  return result,saved,http
 def test_shared_entry_validates_and_records_api(self):
  result,saved,http=self.run_case('{"disposition":"UNCHANGED","edits":[],"reason":"No correction needed."}')
  self.assertEqual(result.status,'PASS');self.assertEqual(http.call_count,2)
  self.assertTrue(http.call_args_list[0].args[0].full_url.endswith('/responses/input_tokens'))
  body=json.loads(http.call_args.args[0].data)
  self.assertEqual(body['reasoning']['effort'],'max');self.assertEqual(body['model'],'gpt-6-luna')
  self.assertTrue(body['text']['format']['strict']);self.assertEqual(body['tools'],[])
  self.assertIn('02-raw-response.json',saved);self.assertEqual(saved['03-result/usage.json']['cli_invocations'],0)
 def test_bad_response_kept_and_rejected(self):
  result,saved,_=self.run_case('{"text":42}')
  self.assertEqual(result.status,'FAIL');self.assertIn('02-raw-response.json',saved)
 def test_invalid_input_never_calls_api(self):
  result,_,http=self.run_case('{}',payload={});self.assertEqual(result.status,'FAIL');http.assert_not_called()
 def test_incomplete_preserves_envelope_and_usage(self):
  result,saved,http=self.run_case('{}',status='incomplete');self.assertEqual(result.status,'FAIL')
  self.assertIn('02-raw-response/api-execution.json',saved);self.assertIn('03-result/usage.json',saved)
 def test_explicit_cli_remains_available(self):
  settings=cli.read_settings(self.config,'01-preparation.02-review-and-correct.revision',profile_id='luna-max-cli',profiles_path=DEFAULT)
  self.assertEqual(settings['provider'],'codex');self.assertEqual(settings['effort'],'max')
