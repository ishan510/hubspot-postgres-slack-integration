"""Milestone 2: read HubSpot contacts. Requires only Python's standard library."""

import getpass
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request_page(request):
    """Try a read up to four times; never retry invalid credentials."""
    for attempt in range(4):
        delay = 2 ** (attempt + 1)
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            error.close()
            if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
            retry_after = error.headers.get('Retry-After') if error.headers else None
            if retry_after:
                try:
                    seconds = int(retry_after)
                except ValueError:
                    try:
                        seconds = (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds()
                    except (ValueError, TypeError, OverflowError):
                        seconds = 0
                # Stop rather than retry sooner than a long server-requested delay.
                if seconds > 60:
                    raise
                delay = max(delay, seconds)
            reason = f'HTTP {error.code}'
        except (URLError, TimeoutError, ConnectionError):
            if attempt == 3:
                raise
            reason = 'connection failure'
        logging.getLogger('acme_sync').warning(
            'hubspot_retry reason=%s next_attempt=%s delay_seconds=%s', reason, attempt + 2, delay)
        time.sleep(delay)


def fetch_contacts(token):
    """Follow HubSpot pagination using a fixed, trusted API endpoint."""
    contacts = []
    after = None
    seen_cursors = set()
    while True:
        params = {"limit": 100, "properties": "firstname,lastname,email,lifecyclestage"}
        if after is not None:
            params["after"] = after
        request = Request(
            "https://api.hubapi.com/crm/v3/objects/contacts?" + urlencode(params),
            headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        )
        page = request_page(request)
        if not isinstance(page, dict) or not isinstance(page.get('results'), list):
            raise ValueError('Unexpected contacts response')
        contacts.extend(page["results"])
        after = page.get("paging", {}).get("next", {}).get("after")
        if after is None:
            return contacts
        after = str(after)
        if after in seen_cursors:
            raise ValueError("Repeated pagination cursor")
        seen_cursors.add(after)


def main():
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN", "").strip()
    if not token:
        token = getpass.getpass("Paste your HubSpot Service Key (hidden): ").strip()
    if not token:
        print("No key entered. Run the script again when your key is ready.")
        return 1
    try:
        contacts = fetch_contacts(token)
    except HTTPError as error:
        hints = {
            401: "Check that your Service Key is valid and copied completely.",
            403: "Check that your key has permission to read contacts.",
            429: "HubSpot's rate limit was reached. Try again later.",
        }
        print(f"HubSpot returned HTTP {error.code}. " + hints.get(error.code, "Try again later."))
        return 1
    except (URLError, TimeoutError, OSError):
        print("Could not connect to HubSpot. Check your internet connection and try again.")
        return 1
    except (ValueError, KeyError, TypeError):
        print("HubSpot returned an unexpected response. No contacts were saved.")
        return 1
    print(f"\nConnected successfully. Found {len(contacts)} contact(s).\n")
    for contact in contacts:
        properties = contact.get("properties", {})
        name = " ".join(filter(None, [properties.get("firstname"), properties.get("lastname")]))
        print(f"{contact['id']} | {name or '(no name)'} | {properties.get('email') or '(no email)'}")
    print("\nRead complete. Your HubSpot records were not changed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(1)
