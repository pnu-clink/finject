"""Real bounded arithmetic and offline viewer artifact/review checks."""
import copy
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from finarch.dataset.shared.calculation.arithmetic import compile_handler, compile_program, evaluate_graph, interpret
from finarch.dataset.viewer.build import build, collect, import_decisions


class ArithmeticChecks(unittest.TestCase):
    def setUp(self):
        self.program = {"context": "\ub9e4\ucd9c 120 \uc6d0\uac00 80", "code": 'r = fact("r")\nc = fact("c")\nanswer = (r - c) / r * 100',
                        "facts": {"r": {"value": "120", "text": "120", "span": [3, 6]},
                                  "c": {"value": "80", "text": "80", "span": [10, 12]}}}

    def test_real_ast_and_graph_compute_exact_answer(self):
        answer, trace = interpret(self.program)
        graph, compiled = compile_program(self.program)
        self.assertEqual(answer, Fraction(100, 3))
        self.assertEqual(answer, compiled)
        self.assertEqual(evaluate_graph(graph)[0], answer)
        self.assertEqual(trace["answer"], "100/3")
        review_ids = compile_handler({"program": self.program}).data["variables"]
        self.assertEqual(set(review_ids), {node["id"] for node in graph["nodes"] if node["kind"] != "constant"})
        ids = set()
        for node in graph["nodes"]:
            self.assertTrue(set(node["inputs"]).issubset(ids))
            ids.add(node["id"])

    def test_wrong_source_number_is_rejected(self):
        self.program["facts"]["c"]["value"] = "90"
        with self.assertRaisesRegex(ValueError, "DOES_NOT_MATCH"):
            interpret(self.program)

    def test_dangerous_and_out_of_scope_syntax_is_rejected(self):
        for code in ['import os\nanswer = 1', 'answer = __import__("os")', 'answer = (1).__class__',
                     'answer = 100 ** 100', 'answer = [1]', 'answer = 42', 'r = 1\nr = 100\nanswer = r',
                     'r = fact("r")\nc = fact("c")\nanswer = 100']:
            with self.subTest(code=code), self.assertRaises(ValueError):
                interpret({**self.program, "code": code})

    def test_division_by_zero_is_not_a_missing_evidence_answer(self):
        self.program["code"] = 'r = fact("r")\nc = fact("c")\nanswer = r / (c - c)'
        with self.assertRaises(ZeroDivisionError): interpret(self.program)

    def test_fact_metadata_cannot_replace_graph_identity(self):
        self.program["facts"]["r"].update(id="injected", inputs=["bad"], kind="operation")
        graph, _ = compile_program(self.program)
        self.assertNotIn("injected", [n["id"] for n in graph["nodes"]])
        self.assertTrue(all(n["kind"] == "fact" for n in graph["nodes"] if n.get("fact_id")))


class ViewerChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="finarch-viewer-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "run"
        (self.run / "05-text").mkdir(parents=True)
        (self.run / "06-human-review").mkdir()
        (self.run / "run.json").write_text(json.dumps({"status": "AWAITING_HUMAN", "events": []}))
        (self.run / "06-human-review/03-result.json").write_text(json.dumps([
            {"variant": "IC_VALUE", "status": "AWAITING_HUMAN"}, {"variant": "EA", "status": "FAIL"}]))

    def decision_file(self, variant="IC_VALUE", decision="APPROVE"):
        payload = {"snapshot_sha256": collect(self.run)["snapshot_sha256"], "decisions": [
            {"variant": variant, "decision": decision, "reviewer": "local-test", "reason": "\uac80\uc0ac\uc6a9 \ud310\ub2e8", "reviewed_at": "2026-09-07T00:00:00Z"}]}
        path = self.root / "decision.json"
        path.write_text(json.dumps(payload))
        return path

    def test_html_escapes_embedded_script_and_contains_filter_ui(self):
        (self.run / "untrusted.json").write_text(json.dumps({"context": '</script><script>alert("bad")</script>'}))
        output = self.root / "viewer.html"
        build([self.run], output)
        html = output.read_text()
        self.assertNotIn('</script><script>alert', html)
        self.assertIn('\\u003c/script>', html)
        self.assertIn('input.type=\'checkbox\'', html)
        self.assertNotIn('__FINARCH_DATA__', html)
        with self.assertRaises(FileExistsError): build([self.run], output)

    def test_decision_import_persists_but_does_not_freeze(self):
        result = import_decisions(self.run, self.decision_file())
        self.assertFalse(result["frozen"])
        self.assertEqual(collect(self.run)["decisions"]["IC_VALUE"]["decision"], "APPROVE")
        self.assertFalse((self.run / "freeze").exists())

    def test_changed_artifacts_invalidate_approval(self):
        file = self.decision_file()
        (self.run / "run.json").write_text('{"status":"FAIL"}')
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_CHANGED"):
            import_decisions(self.run, file)

    def test_failed_candidate_and_demo_cannot_be_approved(self):
        with self.assertRaisesRegex(ValueError, "UNREADY"):
            import_decisions(self.run, self.decision_file("EA"))
        (self.run / "demo.json").write_text('{"demonstration":true}')
        with self.assertRaisesRegex(ValueError, "DEMONSTRATION"):
            import_decisions(self.run, self.decision_file())
