"""Common loopback launcher for Python viewers, including safe port reuse."""
import argparse
import json
from http.server import ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

from finarch.paths import PROJECT


def serve(handler, *, name, port, landing='/', argv=None):
    parser = argparse.ArgumentParser(description=f'fin-arch {name} viewer')
    parser.add_argument('--port', type=int, default=port)
    parser.add_argument('--open', action='store_true')
    parser.add_argument('--no-open', action='store_false', dest='open')
    args = parser.parse_args(argv)
    address = f'http://127.0.0.1:{args.port}'
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    except OSError as error:
        try:
            with urlopen(address + '/api/health', timeout=2) as response:
                existing = json.load(response)
            if existing.get('project') != str(PROJECT) or existing.get('viewer') != name:
                raise ValueError('VIEWER_IDENTITY_MISMATCH')
        except (OSError, URLError, ValueError):
            raise SystemExit(f'{name}--port is another port.{error})') from error
        if args.open:
            webbrowser.open(address + landing)
        return
    address = f'http://127.0.0.1:{server.server_port}'
    print(f'fin-arch {name}: {address}{landing}\nEnd: Ctrl + C', flush=True)
    if args.open:
        webbrowser.open(address + landing)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
