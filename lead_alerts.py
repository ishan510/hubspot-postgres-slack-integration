"""One Slack send attempt per qualifying contact; uncertain delivery needs review.

The durable claim precedes the HTTP request. This prevents automatic duplicate
attempts after a crash, at the cost of possibly missing a message. Webhooks do
not provide an exactly-once transaction with PostgreSQL.
"""
import psycopg
from local_credentials import backend, SERVICE
from slack_client import send_message, validate_webhook, SlackError


def alert_text(contact):
    contact_id, first, last, email = contact
    name = ' '.join(part for part in (first, last) if part) or 'Unnamed contact'
    return (f'Acme lead alert: Sales Qualified Lead\n'
            f'Name: {name}\nEmail: {email or "Not provided"}\nHubSpot ID: {contact_id}')


def deliver_alerts(dsn, logger):
    sent = 0
    with psycopg.connect(dsn, connect_timeout=10, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM lead_alerts WHERE status = 'attempted'")
            if cursor.fetchone()[0]:
                logger.error('alerts_need_review reason=unconfirmed_delivery')
                print('An earlier Slack delivery is unconfirmed. Check Slack and lead_alerts before restarting automation.')
                return 1
            cursor.execute("SELECT COUNT(*) FROM lead_alerts WHERE status = 'pending'")
            if not cursor.fetchone()[0]:
                print('Slack alerts sent: 0 (no new qualifying contacts).')
                return 0
            try:
                url = backend().get_password(SERVICE, 'slack-webhook-url')
                validate_webhook(url)
            except Exception:
                logger.error('alerts_failed reason=webhook_unavailable')
                print('Contacts saved; alerts remain pending. Run setup_slack.py to configure the webhook.')
                return 1
            while True:
                # Claim atomically across simultaneous manual or scheduled runs.
                with connection.transaction():
                    cursor.execute("""
                        SELECT a.hubspot_id, c.first_name, c.last_name, c.email
                        FROM lead_alerts a JOIN contacts c USING (hubspot_id)
                        WHERE a.status = 'pending' ORDER BY a.created_at, a.hubspot_id
                        FOR UPDATE OF a SKIP LOCKED LIMIT 1
                    """)
                    contact = cursor.fetchone()
                    if contact is not None:
                        cursor.execute("UPDATE lead_alerts SET status = 'attempted' WHERE hubspot_id = %s", (contact[0],))
                if contact is None:
                    break
                try:
                    send_message(url, alert_text(contact))
                except SlackError:
                    logger.error('alerts_need_review reason=unconfirmed_delivery')
                    print('Slack delivery was not confirmed. Check the channel before retrying; automatic resending is disabled.')
                    return 1
                cursor.execute("UPDATE lead_alerts SET status = 'sent', sent_at = CURRENT_TIMESTAMP WHERE hubspot_id = %s", (contact[0],))
                sent += 1
                logger.info('lead_alert_sent')
    print(f'Slack alerts sent: {sent}.')
    logger.info('alerts_complete sent=%s', sent)
    return 0
