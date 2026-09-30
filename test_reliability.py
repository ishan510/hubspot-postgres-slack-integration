"""Offline checks: python -m unittest -v test_reliability.py"""
import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import read_contacts as client


def http_error(code, headers=None):
    return HTTPError('https://api.hubapi.com', code, 'test', headers or {}, None)


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.request = Request('https://api.hubapi.com')

    @patch.object(client.time, 'sleep')
    @patch.object(client, 'urlopen')
    def test_rate_limit_wait_then_success(self, open_url, sleep):
        open_url.side_effect = [http_error(429, {'Retry-After': '7'}), io.StringIO('{"results": []}')]
        self.assertEqual(client.request_page(self.request), {'results': []})
        sleep.assert_called_once_with(7)

    @patch.object(client.time, 'sleep')
    @patch.object(client, 'urlopen')
    def test_invalid_key_not_retried(self, open_url, sleep):
        open_url.side_effect = http_error(401)
        with self.assertRaises(HTTPError):
            client.request_page(self.request)
        self.assertEqual(open_url.call_count, 1)
        sleep.assert_not_called()

    @patch.object(client.time, 'sleep')
    @patch.object(client, 'urlopen')
    def test_network_failure_stops_after_four_attempts(self, open_url, sleep):
        open_url.side_effect = URLError('offline')
        with self.assertRaises(URLError):
            client.request_page(self.request)
        self.assertEqual(open_url.call_count, 4)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 4, 8])

    @patch.object(client.time, 'sleep')
    @patch.object(client, 'urlopen')
    def test_long_retry_after_stops_without_early_retry(self, open_url, sleep):
        open_url.side_effect = http_error(429, {'Retry-After': '120'})
        with self.assertRaises(HTTPError):
            client.request_page(self.request)
        sleep.assert_not_called()
        self.assertEqual(open_url.call_count, 1)

    @patch.object(client.time, 'sleep')
    @patch.object(client, 'urlopen')
    def test_retry_on_second_page_does_not_duplicate_first(self, open_url, sleep):
        open_url.side_effect = [
            io.StringIO('{"results": [{"id":"1"}], "paging":{"next":{"after":"2"}}}'),
            http_error(503), io.StringIO('{"results": [{"id":"2"}]}')]
        self.assertEqual(client.fetch_contacts('fake-test-key'), [{'id': '1'}, {'id': '2'}])


if __name__ == '__main__':
    unittest.main()
