"""Read-only local research viewer with an identity endpoint for the launcher."""
import json
from http.server import SimpleHTTPRequestHandler
from urllib.parse import urlsplit

from finarch.paths import PROJECT
from finarch.shared.viewer import serve


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT), **kwargs)

    def _health(self):
        body = json.dumps({'viewer': 'research', 'project': str(PROJECT)}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_GET(self):
        if self.headers.get('Host', '').split(':')[0] not in ('localhost', '127.0.0.1'):
            self.send_error(403)
            return
        if urlsplit(self.path).path == '/api/health':
            self._health()
            return
        super().do_GET()

    def do_HEAD(self):
        self.do_GET()


def main():
    serve(Handler, name='research', port=8896, landing='/viewer/research/')


if __name__ == '__main__':
    main()
