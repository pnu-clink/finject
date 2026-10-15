"""Read-only browser timing fixture using a captured annotation API response."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


PROJECT = Path(__file__).resolve().parents[4]
LOGS = PROJECT / 'log/annotation-manager-20261001'
SETUP = r"""
window.annotationLatency = { functions: {}, localize: [], visits: 0 };
"""
PROFILE = r"""
for (const name of ['renderList', 'renderCase', 'renderManagerFilters', 'selectType', 'selectCase']) {
  const original = window[name];
  window[name] = function (...args) {
    const started = performance.now();
    try { return original.apply(this, args); }
    finally { (annotationLatency.functions[name] ||= []).push(performance.now() - started); }
  };
}
document.addEventListener('DOMContentLoaded', () => {
  const panel = document.createElement('section');
  panel.setAttribute('translate', 'no'); panel.setAttribute('data-i18n-skip', '');
  panel.style.cssText = 'position:fixed;bottom:8px;right:8px;z-index:10000;background:white;border:1px solid #888;padding:8px;font:12px monospace;max-width:600px;max-height:250px;overflow:auto';
  const run = document.createElement('button'); run.textContent = 'Run timing check'; run.id = 'latency-run';
  const output = document.createElement('pre'); output.id = 'latency-result'; output.textContent = 'Ready';
  panel.append(run, output); document.body.append(panel);
  const frame = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  run.onclick = async () => {
    run.disabled = true; output.textContent = 'Running';
    try {
      while (!annotationState.view || annotationState.busy) await frame();
      selectCase('test-0041'); await frame();
      while (document.querySelector('button.g02-link')) await frame();
      annotationLatency.functions = {}; annotationLatency.localize = []; annotationLatency.visits = 0;
      const steps = [];
      for (const type of [1, 2, 3, 4, 5, 0]) {
        const started = performance.now(); selectType(type);
        const synchronous = performance.now() - started;
        await frame();
        steps.push({ type, synchronous_ms: synchronous, frame_ms: performance.now() - started });
      }
      const summary = {};
      for (const [name, values] of Object.entries(annotationLatency.functions)) {
        summary[name] = { calls: values.length, total_ms: values.reduce((a, b) => a + b, 0) };
      }
      const values = annotationLatency.localize;
      output.textContent = JSON.stringify({ mode: new URL(location.href).searchParams.get('mode'),
        language: document.documentElement.lang, cases: document.querySelectorAll('#cases .case-link').length,
        dom_elements: document.querySelectorAll('*').length, steps, functions: summary,
        i18n: { calls: values.length, visited_nodes: annotationLatency.visits,
          total_ms: values.reduce((a, b) => a + b, 0) },
        ratings: document.querySelector('#metrics').textContent, status: 'PASS' }, null, 2);
    } catch (error) { output.textContent = JSON.stringify({status: 'FAIL', error: error.message}); }
    finally { run.disabled = false; }
  };
});
"""


def localized_source(source):
    start = 'function localize(root) {\n    if (!root) return;'
    end = 'while (walker.nextNode()) visit(walker.currentNode);\n  }'
    assert source.count(start) == source.count(end) == 1
    source = source.replace(start, start + '\n    const started = performance.now();\n    try {')
    source = source.replace('const visit = node => {', 'const visit = node => {\n      global.annotationLatency.visits++;')
    return source.replace(end, 'while (walker.nextNode()) visit(walker.currentNode);\n    } finally { global.annotationLatency.localize.push(performance.now() - started); }\n  }')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', type=Path, default=PROJECT)
    args = parser.parse_args()
    view = json.loads((LOGS / 'latency-20261003-view.json').read_text())
    links = json.loads((LOGS / 'latency-20261003-g02.json').read_text())
    api = json.dumps(view, ensure_ascii=False).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if urlsplit(self.path).path != '/api/annotation/refresh':
                self.send_error(403, 'Read-only fixture')
                return
            self.respond(api, 'application/json')

        def respond(self, body, content_type):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(200)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = urlsplit(self.path)
            query = parse_qs(route.query)
            if route.path in ('/annotation', '/annotation/'):
                source = (args.source_dir / 'viewer/dataset/annotation/index.html').read_text()
                mode = query.get('mode', ['ko'])[0]
                if mode == 'off':
                    source = source.replace('  <script src="/i18n.js" defer></script>\n', '')
                source = source.replace('<head>', '<head><script src="/latency-setup.js"></script>')
                source = source.replace('</head>', '<script src="/latency-profile.js" defer></script></head>')
                self.respond(source, 'text/html')
            elif route.path == '/latency-setup.js':
                self.respond(SETUP, 'application/javascript')
            elif route.path == '/latency-profile.js':
                self.respond(PROFILE, 'application/javascript')
            elif route.path in ('/i18n.js', '/i18n.css'):
                path = args.source_dir / 'viewer/shared' / route.path[1:]
                source = path.read_text()
                self.respond(localized_source(source) if path.suffix == '.js' else source,
                             'application/javascript' if path.suffix == '.js' else 'text/css')
            elif route.path in ('/annotation/manager.js', '/annotation/reviews.js', '/annotation/style.css'):
                path = args.source_dir / 'viewer/dataset' / route.path[1:]
                self.respond(path.read_bytes(), 'text/css' if path.suffix == '.css' else 'application/javascript')
            elif route.path == '/api/annotation':
                self.respond(api, 'application/json')
            elif route.path == '/api/annotation/g02':
                case = query.get('case', [''])[0]
                data = links if case == links['case'] else {
                    'case': case, 'group': view['groups'][0]['id'], 'links': {
                        entry['variant']: {'status': 'UNAVAILABLE', 'reason': 'Timing fixture has no other case context.'}
                        for entry in view['types']}}
                self.respond(json.dumps(data), 'application/json')
            else:
                self.send_error(404)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}/annotation/?date=20261001',
                      'source_dir': str(args.source_dir), 'mode_options': ['ko', 'en', 'off']}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
