"""Local CLI contract checks. No Codex/AGY model generation is performed."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

cli = __import__('finarch.shared.providers.cli', fromlist=['*'])
from finarch.shared.providers.policy import PolicyError, dispatch, hook_decision
from finarch.dataset.schemas.registry import describe


def codex_output(text='{"text":"local test"}', usage=None):
    events = [{"type": "thread.started", "thread_id": "local-test-only"}, {"type": "turn.started"},
              {"type": "item.completed", "item": {"type": "agent_message", "text": text}},
              {"type": "turn.completed", "usage": usage}]
    return "\n".join(json.dumps(e) for e in events)


class CLIChecks(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="finarch-cli-check-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.config = self.root/"config.json"
        self.value = {"provider": "codex", "execution_enabled": True,
                      "roles": {"dtt.answer": {"model": "local-test-model", "effort": "medium"}},
                      "cli_limits": {"timeout_seconds": 1},
                      "capabilities": {"dtt.answer": {"tools": [], "skills": []}}}
        self.write_config()

    def write_config(self):
        self.config.write_text(json.dumps(self.value))

    def test_unselected_model_and_provider_are_not_silently_defaulted(self):
        for key in ("provider", "model", "effort"):
            with self.subTest(key=key):
                changed = json.loads(json.dumps(self.value))
                if key == "provider":
                    changed[key] = None
                else:
                    changed["roles"]["dtt.answer"][key] = None
                self.config.write_text(json.dumps(changed))
                with self.assertRaises(cli.CLIError):
                    cli.read_settings(self.config, "dtt.answer")

    def test_allowlist_must_be_explicit_and_exact(self):
        self.value["capabilities"] = {}
        self.write_config()
        with self.assertRaises(PolicyError):
            cli.read_settings(self.config, "dtt.answer")
        for names in (["*"], ["Bash", "Bash"], "Bash"):
            with self.assertRaises(PolicyError):
                dispatch({"tools": names, "skills": []}, "tools", "Bash", {}, {})

    def test_unallowed_tool_and_skill_do_not_reach_callable(self):
        calls = []
        for kind, name in (("tools", "Bash"), ("tools", "web_search"), ("skills", "research")):
            with self.subTest(kind=kind, name=name), self.assertRaises(PolicyError):
                dispatch({"tools": [], "skills": []}, kind, name, {},
                         {(kind, name): lambda p: calls.append(p)})
        self.assertEqual(calls, [])
        payload = {"test": 1}
        value = dispatch({"tools": ["local-test-only"], "skills": []}, "tools", "local-test-only", payload,
                         {("tools", "local-test-only"): lambda p: p})
        self.assertIs(value, payload)

    def test_hook_blocks_unknown_and_malformed_calls(self):
        for event in (None, {}, {"hook_event_name": "PreToolUse", "tool_name": "Bash"},
                      {"hook_event_name": "PreToolUse", "tool_name": "Skill", "tool_input": {"skill": "unknown"}}):
            result = hook_decision(event, {"tools": [], "skills": []})
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_real_policy_entry_fails_closed_for_broken_input(self):
        policy = self.root/"policy.json"
        policy.write_text(json.dumps({"tools": [], "skills": []}))
        result = subprocess.run([sys.executable, "-I", str(Path(cli.__file__).with_name("policy.py")),
                                 "--policy", str(policy), "--audit", str(self.root/"audit.jsonl")],
                                input="invalid JSON", capture_output=True, text=True, timeout=5, check=True)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_command_uses_native_schema_and_fresh_cli_session(self):
        settings = cli.read_settings(self.config, "dtt.answer")
        argv = cli.build_command(settings, "/local/test/codex", self.root, self.root/"schema with spaces.json",
                                 self.root/"policy.json", self.root/"audit.jsonl")
        self.assertIn("--ignore-user-config", argv)
        self.assertIn("--ephemeral", argv)
        self.assertIn("--output-schema", argv)
        self.assertIn('web_search="disabled"', argv)
        self.assertIn("features.shell_tool=false", argv)
        self.assertTrue(any(s.startswith("hooks.PreToolUse=") for s in argv))
        self.assertNotIn("resume", argv)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", argv)
        settings["provider"] = "agy"
        argv = cli.build_command(settings, "/local/test/agy", self.root, self.root/"schema.json",
                                 self.root/"policy.json", self.root/"audit.jsonl")
        self.assertIn("--new-project", argv)
        self.assertIn("--json-schema", argv)
        self.assertIn("--disable-slash-commands", argv)
        self.assertNotIn("--dangerously-skip-permissions", argv)

    def test_timeout_preserves_partial_output(self):
        result = cli.run_process([sys.executable, "-c", "import time; print('partial', flush=True); time.sleep(10)"],
                                 "", self.root, 0.2, self.root/"audit.jsonl")
        self.assertEqual(result["state"], "TIMEOUT")
        self.assertIn("partial", result["stdout"])
        self.assertNotEqual(result["exit_code"], 0)
        self.assertGreater(result["elapsed_seconds"], 0)

    def test_tool_denial_terminates_the_process(self):
        audit = self.root/"audit.jsonl"
        audit.write_text('{"permissionDecision": "deny"}\n')
        result = cli.run_process([sys.executable, "-c", "import time; time.sleep(10)"], "", self.root, 1, audit)
        self.assertEqual(result["state"], "TOOL_DENIED")
        self.assertNotEqual(result["exit_code"], 0)

    def test_cli_envelope_keeps_missing_usage_unknown(self):
        raw, usage, turns = cli.parse_output("codex", codex_output())
        self.assertEqual(json.loads(raw), {"text": "local test"})
        self.assertIsNone(usage)
        self.assertIsNone(turns)
        raw, usage, turns = cli.parse_output("agy", '{"status":"SUCCESS","structured_output":{"text":"test"}}')
        self.assertIsNone(usage)
        self.assertEqual(json.loads(raw), {"text": "test"})

    def test_cli_unknown_actions_and_incomplete_turns_fail(self):
        tool = json.dumps({"type": "item.completed", "item": {"type": "command_execution"}})
        for text in (codex_output() + "\n" + tool, codex_output() + "\n" + codex_output(), "{}", "invalid"):
            with self.assertRaises((cli.CLIError, ValueError)):
                cli.parse_output("codex", text)

    def test_recovered_transport_requires_successful_final_turn(self):
        retry=json.dumps({'type':'error','message':'Reconnecting... 2/5 (unexpected status 403 Forbidden)'})
        fallback=json.dumps({'type':'item.completed','item':{'type':'error','message':'Falling back from WebSockets to HTTPS transport. connection failed'}})
        original=codex_output()
        self.assertEqual(cli.parse_output('codex', retry+'\n'+fallback+'\n'+original),cli.parse_output('codex',original))
        for text in (retry+'\n'+fallback, original+'\n'+retry,
                     json.dumps({'type':'error','message':'Authentication failed'})+'\n'+original,
                     json.dumps({'type':'turn.failed','error':{'message':'failed'}})+'\n'+original):
            with self.assertRaises(cli.CLIError):cli.parse_output('codex',text)

    def test_unverified_native_enforcement_prevents_process_start(self):
        files = {}
        with patch.object(cli, "inspect_runtime", return_value={"native_tool_enforcement": "UNVERIFIED"}), \
                patch.object(cli, "run_process") as run:
            result = cli.call(self.config, "dtt.answer", {"context": "C", "question": "Q"},
                              save=lambda key, value: files.__setitem__(key, value))
        self.assertEqual(result.status, "FAIL")
        run.assert_not_called()
        self.assertEqual(files["03-result/failure.json"]["reason"], "NATIVE_TOOL_ENFORCEMENT_UNVERIFIED")

    def test_disabled_execution_prevents_process_start(self):
        self.value["execution_enabled"] = False
        self.write_config()
        files = {}
        with patch.object(cli, "inspect_runtime", return_value={"native_tool_enforcement": "UNVERIFIED"}), \
                patch.object(cli, "run_process") as run:
            cli.call(self.config, "dtt.answer", {"context": "C", "question": "Q"},
                     save=lambda key, value: files.__setitem__(key, value))
        run.assert_not_called()
        self.assertEqual(files["03-result/failure.json"]["reason"], "MODEL_EXECUTION_DISABLED")

    def test_transport_double_gets_schema_and_invalid_response_is_preserved(self):
        # VERIFIED below is a local test double, not native CLI enforcement proof.
        runtime = {"executable": "/local/test/codex", "native_tool_enforcement": "VERIFIED"}
        seen = []
        def process(argv, prompt, work, timeout, audit):
            schema = json.loads((work/"01-input/response-schema.json").read_text())
            self.assertEqual(schema, describe("dtt.answer.response")["schema"])
            self.assertEqual(json.loads((work/"policy.json").read_text()), {"tools": [], "skills": []})
            self.assertNotIn("reference_answer", prompt)
            seen.append(work)
            return {"state": "EXITED", "exit_code": 0, "stdout": codex_output('{"text":42}'),
                    "stderr": "", "started_at": "local-test", "ended_at": "local-test", "elapsed_seconds": 0.01}
        for _ in range(2):
            files = {}
            with patch.object(cli, "inspect_runtime", return_value=runtime), patch.object(cli, "run_process", side_effect=process):
                result = cli.call(self.config, "dtt.answer", {"context": "C", "question": "Q"},
                                  save=lambda key, value: files.__setitem__(key, value))
            self.assertEqual(result.reason, "RESPONSE_SCHEMA_INVALID")
            self.assertEqual(files["02-raw-response.json"]["text"], '{"text":42}')
            self.assertIn("01-input/cli-start.json", files)
            self.assertIsNone(files["03-result/usage.json"]["actual_billed_cost"])
        self.assertNotEqual(seen[0], seen[1])
        self.assertTrue(all(not path.exists() for path in seen))


if __name__ == "__main__":
    unittest.main()
