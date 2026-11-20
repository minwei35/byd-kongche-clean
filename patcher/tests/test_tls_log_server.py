"""Local-only integration tests; no external service or production secrets."""
import contextlib
import http.client
import importlib.util
import json
import pathlib
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import os
from unittest import mock
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / 'tls_log_server.py'
SPEC = importlib.util.spec_from_file_location('tls_log_server', MODULE_PATH)
server_module = None
if MODULE_PATH.exists():
    server_module = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(server_module)


class LogServerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(server_module, 'Independent TLS log server must exist')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.token = self.root / 'token'
        self.token.write_text('test-log-only-token-0123456789\n', encoding='utf-8')
        self.logs = self.root / 'logs'
        self.server = server_module.LogHTTPServer(
            ('127.0.0.1', 0), token_path=self.token, log_dir=self.logs,
            socket_timeout=0.3, rate_limit=1000)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, method='POST', path='/applog', payload=None, token='correct',
                raw=None, headers=None):
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        self.addCleanup(conn.close)
        body = raw if raw is not None else json.dumps(
            {'logs': ['hello']} if payload is None else payload).encode('utf-8')
        hdr = {'Content-Type': 'application/json'}
        if token == 'correct':
            hdr['X-Log-Token'] = 'test-log-only-token-0123456789'
        elif token is not None:
            hdr['X-Log-Token'] = token
        hdr.update(headers or {})
        conn.request(method, path, body=body if method == 'POST' else None, headers=hdr)
        response = conn.getresponse()
        return response.status, json.loads(response.read()), dict(response.getheaders())

    def read_logs(self):
        return next(self.logs.glob('app-*.log')).read_text(encoding='utf-8')

    def test_correct_token_writes_existing_log_format_and_minimal_ack(self):
        status, data, _ = self.request(payload={
            'ts': '2026-11-16 12:00:00', 'device': 'local-test',
            'state': {'kind': 'thirdparty-instrument', 'app': 'trial', 'source': 'test'},
            'logs': ['first', 'second']})
        self.assertEqual(status, 200)
        self.assertEqual(data, {'ok': True, 'lines': 2})
        lines = self.read_logs().splitlines()
        self.assertTrue(lines[0].startswith('### '))
        header = json.loads(lines[0][4:])
        self.assertEqual(header['count'], 2)
        self.assertEqual(header['device'], 'local-test')
        self.assertEqual(lines[1:], ['first', 'second'])

    def test_wrong_missing_and_legacy_token_get_401(self):
        for token in ['wrong', None]:
            with self.subTest(token=token):
                self.assertEqual(self.request(token=token)[0], 401)
        self.assertEqual(self.request(token=None, headers={'X-Auth': 'test-log-only-token-0123456789'})[0], 401)
        self.assertFalse(self.logs.exists())

    def test_duplicate_token_headers_are_rejected(self):
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        self.addCleanup(conn.close)
        conn.putrequest('POST', '/applog')
        conn.putheader('X-Log-Token', 'test-log-only-token-0123456789')
        conn.putheader('X-Log-Token', 'wrong')
        conn.putheader('Content-Length', '2')
        conn.endheaders(b'{}')
        response = conn.getresponse()
        self.assertEqual(response.status, 401)
        response.read()

    def test_control_and_non_exact_upload_paths_are_404(self):
        for method in ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'HEAD', 'PATCH']:
            for path in ['/unlock', '/lock', '/state', '/ble/keyprobe', '/applog/extra',
                         '/%61pplog', '/health?verbose=1']:
                with self.subTest(method=method, path=path):
                    conn = http.client.HTTPConnection(*self.server.server_address, timeout=2)
                    conn.request(method, path)
                    response = conn.getresponse()
                    self.assertEqual(response.status, 404)
                    response.read()
                    conn.close()
        self.assertFalse(self.logs.exists())

    def test_unknown_methods_and_query_upload_are_404(self):
        self.assertEqual(self.request(path='/applog?x=1')[0], 404)
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        self.addCleanup(conn.close)
        conn.request('BREW', '/unlock')
        response = conn.getresponse()
        self.assertEqual(response.status, 404)
        response.read()

    def test_reading_logs_is_forbidden(self):
        for path in ['/applog', '/applog?tail=20']:
            self.assertEqual(self.request('GET', path)[0], 403)
        self.assertEqual(self.request('GET', '/logs/app-20261116.log')[0], 404)

    def test_health_is_secret_free(self):
        status, data, headers = self.request('GET', '/health', token=None)
        self.assertEqual(status, 200)
        self.assertEqual(data, {'ok': True})
        self.assertNotIn('Python', headers.get('Server', ''))
        self.assertNotIn(str(self.root), json.dumps(data))

    def test_byte_limit_is_413_before_read(self):
        status, _, _ = self.request(raw=b'{}', headers={'Content-Length': str(512 * 1024 + 1)})
        self.assertEqual(status, 413)
        self.assertFalse(self.logs.exists())

    def test_line_count_and_character_limits_are_413(self):
        for payload in [{'logs': ['x'] * 601}, {'logs': ['x' * 2049]}]:
            self.assertEqual(self.request(payload=payload)[0], 413)
        self.assertEqual(self.request(payload={'logs': ['x' * 2048] * 200})[0], 200)

    def test_invalid_json_shapes_and_metadata_are_400(self):
        for raw in [b'[]', b'null', b'1', b'"text"', b'{', b'{"logs":NaN}',
                    b'{"logs":[],"logs":[]}', b'\xff']:
            with self.subTest(raw=raw):
                self.assertEqual(self.request(raw=raw)[0], 400)
        for payload in [{}, {'logs': 'a'}, {'logs': [1]}, {'logs': [None]},
                        {'logs': [], 'device': {}}, {'logs': [], 'state': []},
                        {'logs': [], 'ts': 5}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.request(payload=payload)[0], 400)

    def test_cr_lf_and_unicode_separators_stay_one_physical_line(self):
        status, _, _ = self.request(payload={'logs': ['a\r\nb\rc\nd\u2028e\u0085f\x00g', 'last']})
        self.assertEqual(status, 200)
        lines = self.read_logs().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[1], r'a\nb\nc\nd\u2028e\u0085f\u0000g')
        self.assertEqual(lines[2], 'last')

    def test_vin_credentials_and_unknown_state_are_not_persisted(self):
        vin = 'L' + 'A' * 15 + '1'
        status, _, _ = self.request(payload={
            'vin': vin, 'device': vin, 'ts': 'time\n' + vin,
            'state': {'kind': 'trial', 'vin': vin, 'token': 'state-secret', 'nested': {'vin': vin}},
            'logs': ['VIN=' + vin, 'token=private-secret password=pwd-secret',
                     'Bearer bearer-secret', 'mobile=13800138000',
                     'test-log-only-token-0123456789']})
        self.assertEqual(status, 200)
        text = self.read_logs()
        for secret in [vin, 'private-secret', 'pwd-secret', 'bearer-secret',
                       'state-secret', '13800138000', 'test-log-only-token-0123456789']:
            self.assertNotIn(secret, text)
        self.assertNotIn('vin', json.loads(text.splitlines()[0][4:]))
        self.assertEqual(json.loads(text.splitlines()[0][4:])['state'], {'kind': 'trial'})

    def test_ble_frame_payload_is_redacted_but_type_preserved(self):
        frame = '5B B5 E5 05 00 01 FF FF FF FF FF FF FF A4 1B CC A0 15 F5 FA'
        compact = frame.replace(' ', '')
        self.assertEqual(self.request(payload={'logs': [frame, compact]})[0], 200)
        text = self.read_logs()
        self.assertNotIn('A4 1B CC A0', text)
        self.assertNotIn(compact, text)
        self.assertEqual(text.splitlines()[1:], ['5B B5 E5 [frame-redacted] F5 FA'] * 2)

    def test_token_rotation_is_loaded_from_file(self):
        self.token.write_text('rotated-log-only-token-0123456789\n', encoding='utf-8')
        self.assertEqual(self.request()[0], 401)
        self.assertEqual(self.request(token='rotated-log-only-token-0123456789')[0], 200)

    def test_missing_token_file_fails_closed_without_secret_errors(self):
        self.token.unlink()
        status, data, _ = self.request()
        self.assertEqual(status, 503)
        self.assertEqual(data, {'ok': False, 'error': 'unavailable'})

    def test_per_ip_rate_limit_and_retry_header(self):
        self.server.rate_limit = 2
        self.assertEqual(self.request(token='wrong')[0], 401)
        self.assertEqual(self.request(token='wrong')[0], 401)
        status, data, headers = self.request()
        self.assertEqual(status, 429)
        self.assertEqual(data['ok'], False)
        self.assertIn('Retry-After', headers)

    def test_bad_lengths_chunked_and_content_type_rejected(self):
        for headers, status in [({'Content-Length': '-1'}, 400),
                                ({'Content-Length': 'x'}, 400),
                                ({'Transfer-Encoding': 'chunked'}, 400),
                                ({'Content-Type': 'text/plain'}, 415)]:
            self.assertEqual(self.request(raw=b'{}', headers=headers)[0], status)

    def test_body_timeout_recovers_for_next_client(self):
        with socket.create_connection(self.server.server_address, timeout=2) as client:
            client.sendall(b'POST /applog HTTP/1.1\r\nHost: localhost\r\n'
                           b'X-Log-Token: test-log-only-token-0123456789\r\n'
                           b'Content-Type: application/json\r\nContent-Length: 50\r\n\r\n{')
            self.assertIn(b'408', client.recv(4096))
        self.assertEqual(self.request()[0], 200)

    def test_log_write_failure_returns_generic_500(self):
        self.logs.write_text('not-a-directory', encoding='utf-8')
        status, data, _ = self.request()
        self.assertEqual(status, 500)
        self.assertEqual(data, {'ok': False, 'error': 'write failed'})

    def test_rotation_keeps_app_log_filename_format(self):
        self.request()
        self.server.log_max_bytes = 1
        self.request(payload={'logs': ['after-rotation']})
        files = list(self.logs.glob('app-*.log'))
        self.assertEqual(len(files), 2)
        active = [p for p in files if len(p.stem) == len('app-20261116')][0]
        self.assertIn('after-rotation', active.read_text(encoding='utf-8'))


class ResourceBoundTests(unittest.TestCase):
    setUp = LogServerTests.setUp
    stop_server = LogServerTests.stop_server
    request = LogServerTests.request
    read_logs = LogServerTests.read_logs
    def test_partial_header_does_not_block_health(self):
        with socket.create_connection(self.server.server_address, timeout=1) as slow:
            slow.sendall(b'GET /health HTTP/1.1\r\nHost: unfinished')
            started = time.monotonic()
            self.assertEqual(self.request('GET', '/health')[0], 200)
            self.assertLess(time.monotonic() - started, 0.22)

    def test_header_and_body_drips_have_absolute_deadline(self):
        self.server.request_deadline = 0.35
        self.server.socket_timeout = 0.25
        for prefix in [b'GET /health HTTP/1.1\r\nX: ',
                       b'POST /applog HTTP/1.1\r\nHost: localhost\r\n'
                       b'X-Log-Token: test-log-only-token-0123456789\r\n'
                       b'Content-Type: application/json\r\nContent-Length: 100\r\n\r\n']:
            with self.subTest(prefix=prefix), socket.create_connection(self.server.server_address, timeout=1) as sock:
                sock.sendall(prefix)
                closed = threading.Event()
                def drip():
                    for _ in range(14):
                        if closed.wait(0.07):
                            return
                        try:
                            sock.sendall(b'x')
                        except OSError:
                            return
                sender = threading.Thread(target=drip)
                sender.start()
                started = time.monotonic()
                try:
                    try:
                        reply = sock.recv(4096)
                    except ConnectionResetError:
                        reply = b''
                    self.assertLess(time.monotonic() - started, 0.65)
                    self.assertNotIn(b'200 OK', reply)
                finally:
                    closed.set()
                    sender.join(1)

    def test_bounded_workers_reject_overflow_and_close_joins(self):
        self.assertEqual(self.server.max_concurrency, 8)
        sockets = []
        try:
            for _ in range(8):
                sock = socket.create_connection(self.server.server_address, timeout=1)
                sockets.append(sock)
                sock.sendall(b'GET /health HTTP/1.1\r\nX: ')
            with socket.create_connection(self.server.server_address, timeout=1) as extra:
                try:
                    self.assertEqual(extra.recv(100), b'')
                except ConnectionResetError:
                    pass
            self.assertLessEqual(len(self.server._workers), 8)
        finally:
            for sock in sockets:
                sock.close()
        self.server.server_close()
        self.assertFalse(self.server._workers)

    def test_retention_days_count_and_total_protect_unrelated_files(self):
        self.server.retention_days = 7
        self.server.log_max_files = 3
        self.server.log_total_bytes = 120
        self.logs.mkdir()
        unrelated = self.logs / 'app-not-ours.log'
        unrelated.write_bytes(b'private' * 100)
        old = self.logs / 'app-20000101.log'
        old.write_bytes(b'old')
        for number in range(5):
            path = self.logs / ('app-%s-120000-%d.log' % (time.strftime('%Y%m%d'), number))
            path.write_bytes(b'x' * 35)
        self.server.append(b'new\n')
        owned = [p for p in self.logs.iterdir() if p != unrelated]
        self.assertFalse(old.exists())
        self.assertLessEqual(len(owned), 3)
        self.assertLessEqual(sum(p.stat().st_size for p in owned), 120)
        self.assertEqual(unrelated.read_bytes(), b'private' * 100)

    def test_quota_failure_is_generic_and_recovers(self):
        self.server.log_total_bytes = 1
        self.assertEqual(self.request()[0], 500)
        self.assertFalse(list(self.logs.glob('app-*.log')))
        self.server.log_total_bytes = 10000
        self.assertEqual(self.request()[0], 200)

    def test_concurrent_rate_limit_and_append_are_atomic(self):
        self.server.rate_limit = 3
        barrier = threading.Barrier(8)
        results = []
        def upload():
            barrier.wait()
            results.append(self.request()[0])
        workers = [threading.Thread(target=upload) for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(3)
        self.assertEqual(sorted(results), [200] * 3 + [429] * 5)
        self.assertEqual(self.read_logs().count('### '), 3)


class TLSTests(unittest.TestCase):
    def test_real_loopback_tls_handshake_health_and_plaintext_rejected(self):
        self.assertIsNotNone(server_module, 'Independent TLS log server must exist')
        openssl = shutil.which('openssl')
        if not openssl:
            self.skipTest('openssl is needed only to create an ephemeral test certificate')
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            cert, key, token = root / 'cert.pem', root / 'key.pem', root / 'token'
            subprocess.run([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(key), '-out', str(cert), '-days', '1',
                            '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'],
                           check=True, capture_output=True)
            token.write_text('test-tls-token-0123456789', encoding='utf-8')
            server = server_module.create_server(
                ('127.0.0.1', 0), token_path=token, log_dir=root / 'logs',
                cert_path=cert, key_path=key, socket_timeout=0.3)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                context = ssl.create_default_context(cafile=str(cert))
                with contextlib.closing(http.client.HTTPSConnection(
                        *server.server_address, context=context, timeout=2)) as conn:
                    conn.request('GET', '/health')
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read()), {'ok': True})
                with socket.create_connection(server.server_address, timeout=2) as sock:
                    sock.sendall(b'GET /health HTTP/1.0\r\n\r\n')
                    try:
                        self.assertNotIn(b'200 OK', sock.recv(1024))
                    except (ConnectionResetError, ssl.SSLError):
                        pass
                with contextlib.closing(http.client.HTTPSConnection(
                        *server.server_address, context=context, timeout=2)) as conn:
                    conn.request('GET', '/health')
                    self.assertEqual(conn.getresponse().status, 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(2)


if __name__ == '__main__':
    unittest.main()
