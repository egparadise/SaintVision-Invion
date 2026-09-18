"""Disposable proxy transport fixture. It does NOT implement kernel authorization."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == '/v1/projects/project/runs/run/events':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(b'data: first\n\n'); self.wfile.flush()
            time.sleep(3)
            self.wfile.write(b'data: second\n\n'); self.wfile.flush()
            self.close_connection = True
            return
        status = 200
        if self.path == '/readyz':
            status, value = 503, {'status': 'not_ready', 'scope': 'transport-fixture'}
        elif self.path == '/v1/session':
            value = {'scope': 'transport-fixture', 'bearerReceived': self.headers.get('Authorization') == 'Bearer synthetic-proxy-test'}
        else:
            status, value = 404, {'code': 'FIXTURE-404', 'scope': 'transport-fixture'}
        raw = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers(); self.wfile.write(raw)


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
