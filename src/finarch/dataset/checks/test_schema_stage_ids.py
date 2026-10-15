"""Stage schema names and historical lookup compatibility."""
import json
import unittest
from pathlib import Path
from finarch.dataset.schemas.registry import CONTRACTS, LEGACY_SCHEMA_IDS, describe, require_llm_schema, schema_filename, SchemaContractError

class StageSchemaIds(unittest.TestCase):
    def test_export_matches_registry(self):
        folder=Path(__file__).parents[1]/'schemas/json'
        index=json.loads((folder/'index.json').read_text())
        self.assertEqual({r['schema_id'] for r in index},set(CONTRACTS))
        for row in index:
            self.assertEqual(row['file'],row['schema_id']+'.schema.json')
            self.assertEqual(json.loads((folder/row['file']).read_text()),describe(row['schema_id'])['schema'])
    def test_role_uses_new_id(self):
        for role in ('preparation.revise','preparation.evidence','pot.author','dtt.realize','dtt.audit','dtt.feedback'):
            for direction in ('request','response'):
                self.assertEqual(require_llm_schema(role,direction)['schema_id'],LEGACY_SCHEMA_IDS[role+'.'+direction])
    def test_historical_identity_preserved(self):
        for old,new in LEGACY_SCHEMA_IDS.items():
            before=describe(old); after=describe(new)
            self.assertEqual(before['schema']['$id'],f"urn:finarch:{old}:v{before['version']}")
            a=dict(before['schema']);b=dict(after['schema']);a.pop('$id');b.pop('$id')
            if old != "dtt.feedback.request": self.assertEqual(a,b)
            self.assertEqual(schema_filename(old),schema_filename(new))
    def test_removed_role_still_blocked(self):
        with self.assertRaises(SchemaContractError): require_llm_schema('dag.review_inverse')
