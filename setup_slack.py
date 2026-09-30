"""Save this project's Slack webhook in Keychain and send one test message."""
import getpass
import sys

from local_credentials import backend, SERVICE
from slack_client import SlackError, send_message, validate_webhook

SLACK_ACCOUNT = 'slack-webhook-url'
TEST_MESSAGE = 'Acme Lead Alerts connected successfully. This is a test message from your local Python integration.'


def main():
    print('This will save your webhook in macOS Keychain and send one test message to its channel.')
    url = getpass.getpass('Paste your Slack webhook URL (hidden): ').strip()
    try:
        validate_webhook(url)
    except SlackError as error:
        print(error)
        return 1
    try:
        backend().set_password(SERVICE, SLACK_ACCOUNT, url)
    except Exception:
        print('Could not save the webhook. Check that your login Keychain is unlocked. No message was sent.')
        return 1
    print('Webhook saved in Keychain.')
    try:
        send_message(url, TEST_MESSAGE)
    except SlackError as error:
        print(error)
        print('The webhook remains saved in Keychain.')
        return 1
    print('Test message sent. Open your Slack test channel to see it.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled.')
        sys.exit(1)
