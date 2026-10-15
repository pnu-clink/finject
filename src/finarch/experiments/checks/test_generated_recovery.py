"""Offline recovery coverage and immutable-byte checks for the GPU queue."""
import importlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

m=importlib.import_module('finarch.experiments.a100.generated_recovery')


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.base=Path(temp.name);self.root=self.base/'run';self.root.mkdir()
        m.store.write(self.root/'config.json',{'evaluation':{'models':[{'key':'m'}]}})
        m.store.write_rows(self.root/'01_evaluation/02_request/m/manifest.jsonl',[{'trial_id':'one'}])
        self.files={'01_evaluation/03_execution/m/remote-state.json':{'completed':1,'status':'EVALUATION_RECEIVED'},
                    '01_evaluation/03_execution/m/remote-results/one/delivery.json':{'status':'RECEIVED'}}

    def archive(self, corrupt=False):
        stage=self.base/'stage';stage.mkdir(exist_ok=True)
        for name,value in self.files.items():m.store.write(stage/name,value)
        hashes={name:m.protocol.sha(stage/name) for name in self.files}
        m.store.write(stage/'recovery-manifest.json',{'run_id':'run','files':hashes})
        if corrupt:(stage/next(iter(self.files))).write_text('{}')
        output=self.base/'result.tar.gz'
        with tarfile.open(output,'w:gz') as tar:
            for name in [*self.files,'recovery-manifest.json']:tar.add(stage/name,arcname=name,recursive=False)
        return output

    def test_complete_and_repeated_recovery_keep_identical_bytes(self):
        archive=self.archive()
        with patch.object(m.collection,'collect') as collect:
            m.recover(self.root,archive);m.recover(self.root,archive)
        self.assertEqual(collect.call_count,2)

    def test_corruption_rejected_before_publication(self):
        with patch.object(m.collection,'collect') as collect:
            with self.assertRaisesRegex(ValueError,'RECOVERY_HASH_MISMATCH'):m.recover(self.root,self.archive(True))
        collect.assert_not_called()

    def test_existing_conflicting_bytes_not_overwritten(self):
        target=self.root/next(iter(self.files));m.store.write(target,{'different':True})
        with self.assertRaisesRegex(ValueError,'EXISTING_OUTPUT_CONFLICT'):m.recover(self.root,self.archive())
        self.assertEqual(m.store.read(target),{'different':True})

    def test_missing_trial_rejected(self):
        self.files.pop('01_evaluation/03_execution/m/remote-results/one/delivery.json')
        with patch.object(m.collection,'collect') as collect:
            with self.assertRaisesRegex(ValueError,'RECOVERY_REQUEST_COVERAGE_MISMATCH'):m.recover(self.root,self.archive())
        collect.assert_not_called()


if __name__=='__main__':unittest.main()
