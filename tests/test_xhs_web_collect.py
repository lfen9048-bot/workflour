import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('web_collect', Path(__file__).resolve().parents[1] / 'scripts/xhs-web-collect.py')
web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web)


class CollectionTests(unittest.TestCase):
    def test_private_destinations_rejected(self):
        for url in ('http://example.org', 'https://localhost', 'https://127.0.0.1',
                    'https://198.18.3.105', 'https://user:password@example.org', 'https://example.org:8080'):
            with self.subTest(url=url), self.assertRaises(web.base.CollectionError):
                web.public_url(url)

    def test_fake_dns_is_explicit_and_not_other_private_ranges(self):
        row = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('198.18.3.105', 443))]
        with patch.object(web.socket, 'getaddrinfo', return_value=row), patch.dict(os.environ, {'WORKFLOUR_XHS_ALLOW_FAKE_DNS': '0'}):
            with self.assertRaises(web.base.CollectionError):
                web.public_url('https://example.org')
        with patch.object(web.socket, 'getaddrinfo', return_value=row), patch.dict(os.environ, {'WORKFLOUR_XHS_ALLOW_FAKE_DNS': '1'}):
            self.assertEqual(web.public_url('https://example.org/#fragment'), 'https://example.org/')
        row[0] = (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.0.0.1', 443))
        with patch.object(web.socket, 'getaddrinfo', return_value=row), patch.dict(os.environ, {'WORKFLOUR_XHS_ALLOW_FAKE_DNS': '1'}):
            with self.assertRaises(web.base.CollectionError):
                web.public_url('https://example.org')

    def test_existing_material_is_not_overwritten_or_refetched(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'sources.json'
            output.write_text('locked material')
            args = SimpleNamespace(url=['https://example.org'], output=str(output), keyword='test', css=None)
            with patch.object(web, 'get_page') as fetch, self.assertRaises(web.base.CollectionError):
                web.collect(args)
            fetch.assert_not_called()
            self.assertEqual(output.read_text(), 'locked material')

    def test_request_budget_rejects_four_urls_before_fetch(self):
        args = SimpleNamespace(url=[f'https://example.org/{i}' for i in range(4)])
        with patch.object(web, 'get_page') as fetch, self.assertRaises(web.base.CollectionError):
            web.collect(args)
        fetch.assert_not_called()

    def test_redirect_checks_robots_before_second_request(self):
        from scrapling.fetchers import Fetcher
        redirect = SimpleNamespace(status=302, body=b'', headers={'Location': '/private'})
        with patch.object(web, 'public_url', side_effect=lambda u: u), patch.object(Fetcher, 'get', return_value=redirect) as fetch:
            with self.assertRaises(web.base.CollectionError):
                web.get_page('https://example.org/public', access_check=lambda u: not u.endswith('/private'))
            self.assertEqual(fetch.call_count, 1)

    def test_partial_preserves_evidence_and_reports_failure(self):
        from scrapling.engines.toolbelt.custom import Response
        page = Response(url='https://example.org/article', status=200, reason='OK', cookies={},
                        headers={'content-type': 'text/html'}, request_headers={}, _log=False,
                        content='<html><head><title>Actual source</title></head><body><article><p>Verified text.</p><script>unsafe()</script></article></body></html>')
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(url=['https://example.org/article', 'https://example.org/missing'],
                                   output=str(Path(directory) / 'sources.json'), keyword='test', css=None)
            with patch.object(web, 'public_url', side_effect=lambda u: u), patch.object(web, 'get_page', side_effect=[page, OSError()]):
                self.assertEqual(web.collect(args), 3)
            data = json.loads(Path(args.output).read_text())
            self.assertEqual((data['status'], data['source_mode'], len(data['samples'])), ('partial', 'public_web', 1))
            self.assertIn('Verified text.', data['samples'][0]['body'])
            self.assertNotIn('unsafe()', data['samples'][0]['body'])
            self.assertIsNone(data['samples'][0]['published_at'])
            self.assertTrue(any('OSError' in line for line in data['limitations']))


if __name__ == '__main__':
    unittest.main()
