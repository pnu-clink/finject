"""Read-only bounded audit of interrupted migration local ZIP records."""
import json
import struct
import zlib
from collections import Counter
from pathlib import Path
replace_file = __import__('finarch.dataset.90-operations.migrate_ea_labels', fromlist=['replace_file']).replace_file
delegated = __import__('finarch.dataset.90-operations.migrate_ea_labels', fromlist=['delegated']).delegated

LIMIT = 8 * 1024 * 1024

def inspect(root):
    out = root / 'log/ea-label-migration-20260920'
    archive = out / 'originals.zip'
    counts = Counter()
    size = archive.stat().st_size
    with archive.open('rb') as source, (out / 'staged-audit.jsonl').open('w') as log:
        while source.tell() < size:
            offset = source.tell()
            header = source.read(30)
            if len(header) != 30:
                raise ValueError(f'Incomplete header at {offset}')
            sig, _, flags, method, _, _, crc, compressed, plain, n, extra = struct.unpack('<4s5H3I2H', header)
            if sig != b'PK\x03\x04' or flags & 8 or compressed == 0xffffffff:
                raise ValueError(f'Unsupported ZIP header at {offset}')
            name = source.read(n).decode('utf-8' if flags & 2048 else 'cp437')
            source.seek(extra, 1)
            end = source.tell() + compressed
            if end > size:
                raise ValueError(f'Incomplete payload: {name}')
            path = root / name
            row = dict(path=name, offset=offset, original_bytes=plain)
            if Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('Unsafe member path')
            if max(compressed, plain) > LIMIT:
                row['status'] = 'LARGE_DEFERRED'
            else:
                payload = source.read(compressed)
                if method == 8:
                    decoder = zlib.decompressobj(-15)
                    raw = decoder.decompress(payload, LIMIT + 1)
                    if not decoder.eof or decoder.unused_data or len(raw) > LIMIT:
                        raise ValueError(f'Invalid compressed stream: {name}')
                elif method == 0:
                    raw = payload
                else:
                    raise ValueError(f'Unsupported compression: {method}')
                if len(raw) != plain or zlib.crc32(raw) & 0xffffffff != crc:
                    raise ValueError(f'CRC mismatch: {name}')
                row['crc_verified'] = True
                if delegated(root, path):
                    status = 'DELEGATED'
                elif not path.is_file():
                    status = 'MISSING'
                elif path.stat().st_size > LIMIT:
                    status = 'CURRENT_LARGE_DEFERRED'
                elif path.suffix == '.xlsx':
                    status = 'XLSX_DEFERRED'
                else:
                    current = path.read_bytes()
                    expected = replace_file(path, raw)
                    status = 'APPLIED' if current == expected and raw != expected else 'ORIGINAL' if current == raw else 'OTHER_CHANGE'
                row['status'] = status
            source.seek(end)
            counts[row['status']] += 1
            counts['entries'] += 1
            if row.get('crc_verified'):
                counts['crc_verified'] += 1
            log.write(json.dumps(row, ensure_ascii=False) + '\n')
            if counts['entries'] % 100 == 0:
                log.flush()
                (out / 'staged-audit-progress.json').write_text(json.dumps(dict(counts), indent=2))
        summary = dict(counts, archive_bytes=size, data_modified=False, archive_modified=False,
                       scope='Main backup members only; candidate coverage and hashes not yet verified')
        (out / 'staged-audit-summary.json').write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    inspect(Path.cwd())
