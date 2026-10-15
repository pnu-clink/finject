"""Edit the Korean review draft and synchronize its existing local previews."""
from __future__ import annotations

import base64
import copy
import datetime as dt
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup

from finarch.documentation.table_alignment import align_table_cells
from finarch.paths import PROJECT
from finarch.shared.viewer import serve

PREVIEWS = Path('/Users/wooix/.codex/visualizations/2026/10/02/01a0fb53-72f4-7ca1-9765-8977e7c0b21f')
EMBEDDED = re.compile(r'(<script id="document-data" type="application/json">)(.*?)(</script>)', re.S)


class EditConflict(ValueError):
    pass


def revision(section):
    return hashlib.sha256((section['ko'] + '\0' + section['kohtml']).encode()).hexdigest()


def clean_html(content):
    """Remove editor attributes and executable markup from an edited section."""
    doc = BeautifulSoup(content, 'html.parser')
    for tag in list(doc.find_all(['script', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'style', 'link', 'meta'])):
        tag.decompose()
    for tag in doc.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith('on') or attr in ['contenteditable', 'data-editor-protected', 'spellcheck']:
                del tag[attr]
        for attr in ['href', 'src']:
            value = tag.get(attr, '').strip()
            if re.match(r'(?i)javascript:|vbscript:', value):
                del tag[attr]
            elif value.startswith('data:') and not value.startswith(('data:image/png;', 'data:image/svg+xml;', 'data:image/jpeg;', 'data:image/webp;')):
                del tag[attr]
    return str(align_table_cells(doc))


class DraftRepository:
    def __init__(self, root=PROJECT, previews=PREVIEWS):
        self.root = Path(root)
        self.directory = self.root / 'reports/run/20261003-paper-revision-draft'
        self.source = self.directory / 'paper-review.json'
        self.markdown = self.directory / 'PAPER-KO.md'
        self.previews = [Path(previews) / name for name in ['finject-introduction-redline.html', 'finject-introduction-ko-redline.html']]
        self.lock = threading.RLock()

    def read(self):
        return json.loads(self.source.read_text())

    def index(self):
        return [{'id': s['id'], 'title': s['ko'], 'level': s['level']} for s in self.read() if not s.get('hidden_ko')]

    def section(self, sid):
        section = next((s for s in self.read() if s['id'] == sid), None)
        if section is None:
            raise KeyError(sid)
        return {'id': sid, 'title': section['ko'], 'html': section['kohtml'], 'revision': revision(section)}

    def draft_revision(self):
        stat = self.source.stat()
        return f'{stat.st_mtime_ns}:{stat.st_size}'

    @staticmethod
    def markdown_bounds(markdown, sections, sid):
        positions = []
        offset = 0
        for section in sections:
            if section.get('hidden_ko'):
                continue
            heading = ('### ' if section['level'] else '## ') + section['ko']
            match = re.search(r'(?m)^' + re.escape(heading) + r'\s*$', markdown[offset:])
            if not match:
                raise ValueError('한글 원문의 절 제목이 Draft와 다릅니다: ' + section['ko'])
            start = offset + match.start()
            positions.append((section['id'], start, offset + match.end()))
            offset += match.end()
        index = next(i for i, p in enumerate(positions) if p[0] == sid)
        start = positions[index][1]
        body_start = positions[index][2]
        end = positions[index + 1][1] if index + 1 < len(positions) else len(markdown)
        return start, body_start, end

    def markdown_body(self, content, previous_markdown):
        """Keep complex figures, tables and math intact while converting prose."""
        doc = BeautifulSoup(content, 'html.parser')
        old = BeautifulSoup(previous_markdown, 'html.parser')
        local_uris = {}
        for node in old.find_all(['img', 'a']):
            attr = 'src' if node.name == 'img' else 'href'
            url = node.get(attr, '')
            if not url or url.startswith(('data:', 'http:', 'https:', '#')):
                continue
            path = (self.directory / url).resolve()
            if path.is_file() and path.suffix.lower() in ['.png', '.svg', '.jpg', '.jpeg', '.webp']:
                mime = mimetypes.guess_type(path.name)[0]
                local_uris['data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()] = url
        for node in doc.find_all(['img', 'a']):
            attr = 'src' if node.name == 'img' else 'href'
            if node.get(attr) in local_uris:
                node[attr] = local_uris[node[attr]]
            elif node.name == 'img' and node.get('src', '').startswith('data:'):
                figure = node.find_parent('figure', id=True)
                previous = old.find('figure', id=figure['id']) if figure else None
                if previous and previous.img and not previous.img.get('src', '').startswith('data:'):
                    # Reuse the existing Markdown figure path instead of copying image data.
                    node['src'] = previous.img['src']
        protected = {}
        # Outer blocks are protected first, so their nested tables and math stay together.
        for node in list(doc.select('figure, table, div.comparison, div.aside, div.reference, math, p[id], h1[id], h2[id], h3[id], h4[id], h5[id], h6[id]')):
            if node.parent is None:
                continue
            token = f'FINJECTBLOCK{len(protected):05d}PLACEHOLDER'
            protected[token] = str(node)
            placeholder = doc.new_tag('span' if node.name == 'math' and node.get('display') != 'block' else 'p')
            placeholder.string = token
            node.replace_with(placeholder)
        result = subprocess.run(['pandoc', '-f', 'html', '-t', 'gfm', '--wrap=none'], input=str(doc), text=True, capture_output=True, check=True).stdout
        for token, block in protected.items():
            result = result.replace(token, block)
        return result.strip()

    @staticmethod
    def atomic_write(path, content):
        temporary = path.with_name(path.name + '.editor-tmp')
        temporary.write_text(content)
        os.replace(temporary, path)

    def save(self, sid, payload):
        with self.lock:
            source_before = self.source.read_text()
            sections = json.loads(source_before)
            original = next((s for s in sections if s['id'] == sid), None)
            if original is None:
                raise KeyError(sid)
            if payload.get('revision') != revision(original):
                raise EditConflict('다른 수정이 먼저 반영되었습니다. 현재 내용을 복사한 뒤 최신 원문을 다시 불러와 주세요.')
            title = payload.get('title', '').strip()
            raw_html = payload.get('html')
            if not title or len(title) > 250 or any(c in title for c in '\n<>') or not isinstance(raw_html, str):
                raise ValueError('절 제목과 본문을 확인해 주세요.')
            cleaned = clean_html(raw_html)
            if title == original['ko'] and cleaned == original['kohtml']:
                return {**self.section(sid), 'saved_at': dt.datetime.now().astimezone().isoformat(), 'changed': False}
            markdown_before = self.markdown.read_text()
            start, body_start, end = self.markdown_bounds(markdown_before, sections, sid)
            body = self.markdown_body(cleaned, markdown_before[body_start:end])
            section_before = copy.deepcopy(original)
            original['ko'] = title
            original['kohtml'] = cleaned
            original['state'] = 'revised'
            heading = ('### ' if original['level'] else '## ') + title
            markdown_after = markdown_before[:start] + heading + '\n\n' + body + '\n\n' + markdown_before[end:]
            updates = {self.source: json.dumps(sections, ensure_ascii=False, indent=2) + '\n', self.markdown: markdown_after}
            before = {self.source: source_before, self.markdown: markdown_before}
            embedded = json.dumps(sections, ensure_ascii=False).replace('</script', '<\\/script')
            for path in self.previews:
                before[path] = path.read_text()
                if len(EMBEDDED.findall(before[path])) != 1:
                    raise ValueError('Draft HTML의 원문 위치를 확인할 수 없습니다.')
                updates[path] = EMBEDDED.sub(lambda m: m[1] + embedded + m[3], before[path], count=1)
            for path, content in before.items():
                if path.read_text() != content:
                    raise EditConflict('저장 중 원문이 변경되었습니다. 최신 내용을 불러와 다시 저장해 주세요.')
            backup = self.directory / 'backup/editor'
            backup.mkdir(parents=True, exist_ok=True)
            stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            (backup / f'{stamp}-{sid}.json').write_text(json.dumps(section_before, ensure_ascii=False, indent=2) + '\n')
            written = []
            try:
                for path, content in updates.items():
                    self.atomic_write(path, content)
                    written.append(path)
            except Exception:
                for path in written:
                    if path.read_text() == updates[path]:
                        self.atomic_write(path, before[path])
                raise
            return {'id': sid, 'title': title, 'html': cleaned, 'revision': revision(original), 'saved_at': dt.datetime.now().astimezone().isoformat(), 'changed': True}


REPOSITORY = DraftRepository()


class Handler(BaseHTTPRequestHandler):
    def allowed_host(self):
        return self.headers.get('Host', '').split(':')[0] in ['127.0.0.1', 'localhost']

    def reply(self, status, body, content_type='application/json; charset=utf-8'):
        if isinstance(body, dict) or isinstance(body, list):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed_host():
            return self.reply(403, {'error': '로컬 주소만 사용할 수 있습니다.'})
        path = unquote(urlsplit(self.path).path)
        try:
            if path in ['/', '/editor']:
                return self.reply(200, (PROJECT / 'viewer/research/draft-editor.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/draft-compare':
                return self.reply(200, (PROJECT / 'viewer/research/draft-compare.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/draft-side-by-side':
                return self.reply(200, (PROJECT / 'viewer/research/draft-side-by-side.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/draft-compressed':
                from finarch.documentation.draft_compare import compressed_document
                with REPOSITORY.lock:
                    data = compressed_document(REPOSITORY.directory, REPOSITORY.read(), PROJECT)
                    preview = BeautifulSoup(REPOSITORY.previews[1].read_text(), 'html.parser')
                template = (PROJECT / 'viewer/research/draft-compressed.html').read_text()
                embedded = json.dumps(data, ensure_ascii=False).replace('</script', '<\\/script')
                content = template.replace('DOCUMENT_STYLES', preview.style.get_text()).replace('DOCUMENT_DATA', embedded)
                return self.reply(200, content, 'text/html; charset=utf-8')
            if path == '/api/draft-compressed-revision':
                from finarch.documentation.draft_compare import compressed_revision
                return self.reply(200, {'revision': compressed_revision(REPOSITORY.directory)})
            if path == '/api/draft-compare':
                from finarch.documentation.draft_compare import comparison_data
                section_id = parse_qs(urlsplit(self.path).query).get('section', ['s1'])[0]
                with REPOSITORY.lock:
                    data = comparison_data(REPOSITORY.directory, REPOSITORY.read(), section_id)
                return self.reply(200, data)
            if path == '/api/health':
                return self.reply(200, {'viewer': 'draft-editor', 'project': str(PROJECT)})
            if path == '/api/index':
                return self.reply(200, REPOSITORY.index())
            if path == '/api/revision':
                return self.reply(200, {'revision': REPOSITORY.draft_revision()})
            if path.startswith('/api/section/'):
                return self.reply(200, REPOSITORY.section(path.removeprefix('/api/section/')))
            if path == '/draft':
                with REPOSITORY.lock:
                    content = REPOSITORY.previews[1].read_text()
                    current_revision = json.dumps(REPOSITORY.draft_revision())
                script = '<script>let editorRevision=' + current_revision + ';setInterval(async()=>{try{const r=await fetch("/api/revision",{cache:"no-store"}).then(x=>x.json());if(r.revision!==editorRevision)location.reload();}catch{}},2000);</script>'
                if parse_qs(urlsplit(self.path).query).get('embed') == ['1']:
                    frame_style = '<style>html{scroll-behavior:auto}body{font-size:16px}body>header,aside,.intro-panel,.footer,.old-copy,.section-top>.status{display:none!important}.layout{display:block!important;max-width:none!important;padding:20px!important}.layout>main{max-width:none!important}.paper-section{padding:24px!important;scroll-margin-top:16px;max-width:900px;margin:0 auto 18px}.new-copy.proposed>p{color:inherit!important}.section-top h2{font-size:24px!important}.paper-section.subsection .section-top h2{font-size:21px!important}</style>'
                    content = content.replace('</head>', frame_style + '</head>')
                return self.reply(200, content.replace('</body>', script + '</body>'), 'text/html; charset=utf-8')
            return self.reply(404, {'error': '페이지를 찾지 못했습니다.'})
        except KeyError:
            return self.reply(404, {'error': '절을 찾지 못했습니다.'})
        except Exception as error:
            return self.reply(500, {'error': str(error)})

    def do_POST(self):
        if not self.allowed_host():
            return self.reply(403, {'error': '로컬 주소만 사용할 수 있습니다.'})
        origin = self.headers.get('Origin', '')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.reply(403, {'error': '편집기 화면에서 저장해 주세요.'})
        path = unquote(urlsplit(self.path).path)
        comparison_paths = ['/api/draft-compare/decision', '/api/draft-compare/apply']
        if not path.startswith('/api/section/') and path not in comparison_paths:
            return self.reply(404, {'error': '저장 경로를 찾지 못했습니다.'})
        from finarch.documentation.draft_compare_review import ComparisonConflict, apply_decisions, save_decision
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 20 * 1024 * 1024:
                return self.reply(413, {'error': '본문 크기를 확인해 주세요.'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.reply(415, {'error': 'JSON 저장 요청이 필요합니다.'})
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError('저장 요청의 내용을 확인해 주세요.')
            if path == '/api/draft-compare/decision':
                return self.reply(200, save_decision(REPOSITORY, payload))
            if path == '/api/draft-compare/apply':
                return self.reply(200, apply_decisions(REPOSITORY, payload))
            return self.reply(200, REPOSITORY.save(path.removeprefix('/api/section/'), payload))
        except (EditConflict, ComparisonConflict) as error:
            return self.reply(409, {'error': str(error)})
        except (ValueError, KeyError) as error:
            return self.reply(400, {'error': str(error)})
        except Exception as error:
            return self.reply(500, {'error': str(error)})


def main():
    serve(Handler, name='draft-editor', port=8897, landing='/editor#s1')


if __name__ == '__main__':
    main()
