"""Send a single webhook message without exposing its secret URL in errors."""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener


class SlackError(Exception):
    pass


def validate_webhook(url):
    if not isinstance(url, str) or not re.fullmatch(
        r'https://hooks\.slack(?:-gov)?\.com/services/[A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9]+', url
    ):
        raise SlackError('Expected a Slack incoming webhook URL. Copy it again from Incoming Webhooks.')
    return url


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send_message(url, text):
    validate_webhook(url)
    request = Request(url, data=json.dumps({'text': text, 'mrkdwn': False}).encode('utf-8'),
                      headers={'Content-Type': 'application/json'}, method='POST')
    try:
        # Do not retry: a timeout can occur after Slack already accepted a message.
        with build_opener(NoRedirects()).open(request, timeout=20) as response:
            if response.status != 200 or response.read(1024).strip() != b'ok':
                raise SlackError('Slack did not confirm delivery. Check the channel before trying again.')
    except HTTPError as error:
        status = error.code
        error.close()
        raise SlackError(f'Slack returned HTTP {status}. Check the webhook and channel before trying again.') from None
    except (URLError, OSError):
        raise SlackError('Delivery could not be confirmed. Check Slack before retrying; the message may have arrived.') from None
