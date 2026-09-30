"""Copy HubSpot contacts into a local PostgreSQL database in one transaction."""

import getpass
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError

try:
    import psycopg
except ImportError:
    print('Install the project dependencies first: python -m pip install -r requirements.txt')
    sys.exit(1)

from read_contacts import fetch_contacts
from sync_logging import configure_logging


UPSERT = """
INSERT INTO contacts (hubspot_id, first_name, last_name, email, created_at, updated_at, lifecycle_stage)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (hubspot_id) DO UPDATE SET
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    email = EXCLUDED.email,
    created_at = EXCLUDED.created_at,
    updated_at = EXCLUDED.updated_at,
    lifecycle_stage = EXCLUDED.lifecycle_stage,
    synced_at = CURRENT_TIMESTAMP
"""


def main(interactive=True):
    logger = configure_logging()
    started = time.monotonic()
    logger.info('sync_started')
    try:
        result = run_sync(logger, interactive=interactive)
    except (KeyboardInterrupt, EOFError):
        logger.warning('sync_cancelled')
        raise
    except Exception as error:
        logger.error('sync_failed reason=unexpected error_type=%s', type(error).__name__)
        print('Unexpected failure. Check logs/sync.log for the error category.')
        result = 1
    logger.info('sync_finished status=%s duration_seconds=%.2f',
                'success' if result == 0 else 'failed', time.monotonic() - started)
    return result


def run_sync(logger, interactive=True):
    token = os.environ.get('HUBSPOT_ACCESS_TOKEN', '').strip()
    if not token and not interactive:
        try:
            from local_credentials import load_key
            token = (load_key() or '').strip()
        except Exception:
            logger.error('sync_failed reason=keychain_unavailable')
            print('Cannot read the saved key. Check your login Keychain and run local_credentials.py if needed.')
            return 1
    if not token and interactive:
        token = getpass.getpass('Paste your HubSpot Service Key (hidden): ').strip()
    if not token:
        logger.error('sync_failed reason=missing_key')
        print('No key available. Nothing was synced. For automatic runs, save it with local_credentials.py.')
        return 1
    try:
        contacts = fetch_contacts(token)
    except HTTPError as error:
        logger.error('sync_failed stage=hubspot http_status=%s', error.code)
        print(f'HubSpot returned HTTP {error.code}. Check your key and contact-read permission; retry later for 429 or 5xx errors.')
        return 1
    except (URLError, OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        logger.error('sync_failed stage=hubspot error_type=%s', type(error).__name__)
        print('Could not retrieve all contacts from HubSpot. Database was not changed.')
        return 1
    try:
        rows = []
        for contact in contacts:
            props = contact['properties']
            rows.append((contact['id'], props.get('firstname'), props.get('lastname'),
                         props.get('email'), contact.get('createdAt'), contact.get('updatedAt'), props.get('lifecyclestage')))
        with psycopg.connect(os.environ.get('DATABASE_URL', 'dbname=acme_crm'), connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                cursor.execute(Path(__file__).with_name('schema.sql').read_text())
                cursor.executemany(UPSERT, rows)
                cursor.executemany(
                    'INSERT INTO lead_alerts (hubspot_id) VALUES (%s) ON CONFLICT (hubspot_id) DO NOTHING',
                    [(row[0],) for row in rows if row[6] == 'salesqualifiedlead'])
                cursor.execute('SELECT COUNT(*) FROM contacts')
                total = cursor.fetchone()[0]
        print(f'Sync complete: {len(rows)} HubSpot contacts processed; {total} database rows total.')
        logger.info('sync_committed contacts_processed=%s database_rows=%s', len(rows), total)
    except psycopg.Error as error:
        logger.error('sync_failed stage=database error_type=%s', type(error).__name__)
        print(f'PostgreSQL failed ({type(error).__name__}). Sync was not confirmed; rerun after checking the connection.')
        print('Check that PostgreSQL is running and the acme_crm database exists.')
        return 1
    except (KeyError, TypeError, ValueError, AttributeError):
        logger.error('sync_failed stage=transform reason=invalid_contact')
        print('Unexpected contact data. No contacts were saved.')
        return 1
    from lead_alerts import deliver_alerts
    try:
        return deliver_alerts(os.environ.get('DATABASE_URL', 'dbname=acme_crm'), logger)
    except Exception as error:
        logger.error('alerts_failed error_type=%s', type(error).__name__)
        print('Contacts were saved, but Slack alerts could not be completed. Check logs/sync.log.')
        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled.')
        sys.exit(1)
