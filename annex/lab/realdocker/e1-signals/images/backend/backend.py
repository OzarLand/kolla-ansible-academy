#!/usr/bin/python3
"""e1 helper for test (e): a slow HTTP backend behind haproxy plus a UDP syslog sink for haproxy's log lines.

GET /slow streams CHUNKS x 1 KiB, one chunk every INTERVAL s, with a Content-Length, so a client can tell a
complete response from a cut one. Every request start and end (or the write error that ended it) is logged.
Usage: backend.py <http_port> <syslog_port> <logdir>
"""
import socket
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

HTTP_PORT, SYSLOG_PORT, LOGDIR = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
CHUNKS, INTERVAL = 80, 0.25
_lock = threading.Lock()


def log(fname, msg):
    with _lock, open('%s/%s' % (LOGDIR, fname), 'a') as f:
        f.write('%.6f %s\n' % (time.time(), msg))


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path != '/slow':
            body = b'ok\n'
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        peer = '%s:%d' % self.client_address
        log('backend.log', 'GET /slow from %s: start, %d bytes over %.0f s' % (peer, CHUNKS * 1024, CHUNKS * INTERVAL))
        self.send_response(200)
        self.send_header('Content-Length', str(CHUNKS * 1024))
        self.send_header('Content-Type', 'application/octet-stream')
        self.end_headers()
        sent = 0
        try:
            for _ in range(CHUNKS):
                self.wfile.write(b'x' * 1024)
                self.wfile.flush()
                sent += 1024
                time.sleep(INTERVAL)
            log('backend.log', 'GET /slow from %s: complete, %d bytes sent' % (peer, sent))
        except OSError as e:
            log('backend.log', 'GET /slow from %s: write failed after %d bytes: %s' % (peer, sent, e))


class Server(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def syslog_sink():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('127.0.0.1', SYSLOG_PORT))
    while True:
        data, _ = s.recvfrom(65535)
        log('haproxy-syslog.log', data.decode('utf-8', 'replace').strip())


threading.Thread(target=syslog_sink, daemon=True).start()
log('backend.log', 'listening http=%d syslog=%d' % (HTTP_PORT, SYSLOG_PORT))
Server(('127.0.0.1', HTTP_PORT), Handler).serve_forever()
