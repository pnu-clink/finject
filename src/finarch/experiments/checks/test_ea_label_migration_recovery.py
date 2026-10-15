"""Safety checks for interrupted EA migration recovery; no model calls."""
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
Migration = __import__('finarch.dataset.90-operations.finish_ea_migration', fromlist=['Migration']).Migration
CHUNK = __import__('finarch.dataset.90-operations.finish_ea_migration', fromlist=['CHUNK']).CHUNK
replace_file = __import__('finarch.dataset.90-operations.migrate_ea_labels', fromlist=['replace_file']).replace_file

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        out=self.root/'log/ea-label-migration-20260920'
        out.mkdir(parents=True)
        archive=out/'originals.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('a.json',b'{"label":"EA_03"}')
        raw=archive.read_bytes()
        archive.write_bytes(raw[:raw.index(b'PK\x01\x02')])
        self.archive_bytes=archive.read_bytes()
        (self.root/'a.json').write_bytes(b'{"label":"EA_02"}')
        self.m=Migration(self.root)
        self.addCleanup(self.m.db.close)
        self.addCleanup(self.m.backup.close)

    def test_recovery_preserves_original_archive(self):
        self.assertEqual((self.m.out/'originals.zip').read_bytes(),self.archive_bytes)
        self.assertEqual(self.m.backup.read('a.json'),b'{"label":"EA_03"}')

    def test_already_applied_file_is_not_decremented_twice(self):
        self.assertFalse(self.m.apply('a.json'))
        self.assertFalse(self.m.apply('a.json'))
        self.assertEqual((self.root/'a.json').read_bytes(),b'{"label":"EA_02"}')

    def test_hash_only_reference_preserves_current_labels(self):
        self.m.apply('a.json')
        original=hashlib.sha256(b'{"label":"EA_03"}').hexdigest()
        p=self.root/'reference.json'
        p.write_text(json.dumps({'label':'EA_02','hash':original}))
        self.m.apply('reference.json',True)
        self.m.apply('reference.json',True)
        self.assertEqual(json.loads(p.read_text()),{'label':'EA_02','hash':hashlib.sha256((self.root/'a.json').read_bytes()).hexdigest()})

    def test_chunk_boundaries_preserve_one_pass_mapping(self):
        for n in range(CHUNK-4105,CHUNK-4080):
            raw=b' '*n+b'EA_02 EA_03 '+b' '*8192
            out=io.BytesIO()
            self.m.transform('a.txt',io.BytesIO(raw),out)
            self.assertEqual(out.getvalue(),raw.replace(b'EA_02',b'EA_01').replace(b'EA_03',b'EA_02'))

    def test_new_hash_mapping_revisits_previously_checked_reference(self):
        p=self.root/'later.json';old='a'*64;new='b'*64
        p.write_text(json.dumps({'label':'EA_02','hash':old}))
        self.assertFalse(self.m.apply('later.json',True))
        self.m.db.execute('insert into hashes values(?,?)',(old,new));self.m.db.commit()
        self.assertTrue(self.m.apply('later.json',True))
        self.assertEqual(json.loads(p.read_text())['hash'],new)
        self.assertEqual(json.loads(p.read_text())['label'],'EA_02')

    def test_hash_equal_to_another_original_is_not_cascaded(self):
        a=b'{"label":"EA_03"}';b=b'{"label":"EA_02"}'
        (self.root/'b.json').write_bytes(b)
        self.m.apply('b.json');self.m.apply('a.json')
        p=self.root/'reference.json';p.write_text(json.dumps({'hash':hashlib.sha256(a).hexdigest()}))
        self.m.apply('reference.json',True);self.m.apply('reference.json',True)
        self.assertEqual(json.loads(p.read_text())['hash'],hashlib.sha256(b).hexdigest())

    def test_unexpected_edits_are_not_overwritten(self):
        p=self.root/'a.json'
        p.write_bytes(b'{"label":"EA_02","manual":true}')
        with self.assertRaisesRegex(ValueError,'Unexpected current change'):
            self.m.apply('a.json')
        self.assertIn(b'manual',p.read_bytes())

    def test_existing_catalogue_category_is_preserved(self):
        raw=b'{"type":"EA_02","label":"EA_03","path":"feedback-011-017/EA_02"}'
        result=replace_file(Path('reports/feedback-011-017/item.json'),raw)
        self.assertEqual(json.loads(result),{'type':'EA_02','label':'EA_02','path':'feedback-011-017/EA_02'})

if __name__=='__main__':
    unittest.main()
