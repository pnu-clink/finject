"""Independent read-only dashboard server for saved project and run records."""
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

from finarch.dashboard.viewer.resources import resource
from finarch.paths import PROJECT
from finarch.shared.viewer import serve


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Host', '').split(':')[0] not in ('localhost', '127.0.0.1'):
            self.send_error(403)
            return
        route = urlsplit(self.path)
        if route.path in ('/', '/index.html', '/dashboard', '/dashboard/', '/dashboard/index.html',
                          '/dashboard/01-overview', '/dashboard/02-explorer', '/dashboard/03-project'):
            destination = ('/dashboard/02-explorer/' if route.path.endswith('/02-explorer') else
                           '/dashboard/01-overview/' if route.path.endswith('/01-overview') else
                           '/dashboard/03-project/')
            self.send_response(302)
            self.send_header('Location', destination)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return
        try:
            if route.path == '/api/health':
                body = json.dumps({'viewer': 'dashboard', 'project': str(PROJECT)}).encode()
                mime = 'application/json; charset=utf-8'
            else:
                body, mime = resource(route.path, parse_qs(route.query))
        except ValueError:
            self.send_error(404)
            return
        except OSError:
            self.send_error(503, 'Saved results temporarily unavailable')
            return
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Finarch-Viewer', 'dashboard')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    do_HEAD = do_GET

    def log_message(self, *args):
        pass


def main():
    serve(Handler, name='dashboard', port=8895, landing='/dashboard/03-project/')


if __name__ == '__main__':
    main()
