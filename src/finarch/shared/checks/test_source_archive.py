"""Historical evidence must match its recorded bytes, never the current code."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from finarch.shared.source_archive import ARCHIVE, read_source_reference


class SourceArchiveChecks(unittest.TestCase):
    def test_old_evidence_is_read_by_path_and_hash_and_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = b'original implementation'
            relative = 'src/finarch/old.py'
            expected = hashlib.sha256(original).hexdigest()
            current = root / relative
            current.parent.mkdir(parents=True)
            current.write_text('new implementation')
            archive = root / ARCHIVE
            archive.mkdir(parents=True)
            (archive / 'manifest.json').write_text(json.dumps({'files': {relative: expected}}))
            for payload, valid in [(original, True), (b'tampered', False)]:
                with tarfile.open(archive / 'source-before.tar.gz', 'w:gz') as stream:
                    info = tarfile.TarInfo(relative)
                    info.size = len(payload)
                    stream.addfile(info, io.BytesIO(payload))
                if valid:
                    self.assertEqual(read_source_reference(relative, expected, project=root), original)
                else:
                    with self.assertRaisesRegex(ValueError, 'ARCHIVED_SOURCE_HASH_CHANGED'):
                        read_source_reference(relative, expected, project=root)
            with self.assertRaisesRegex(ValueError, 'INVALID_SOURCE_REFERENCE'):
                read_source_reference('../outside.py', expected, project=root)
