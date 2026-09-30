import unittest
from unittest.mock import MagicMock, patch
import lead_alerts


class LeadAlertTests(unittest.TestCase):
    def run_case(self, results, error=None):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = results
        with patch.object(lead_alerts.psycopg, 'connect') as connect, \
             patch.object(lead_alerts, 'backend') as backend, \
             patch.object(lead_alerts, 'send_message') as send:
            connect.return_value.__enter__.return_value = connection
            backend.return_value.get_password.return_value = 'https://hooks.slack.com/services/TTEST/BTEST/FAKE'
            send.side_effect = error
            result = lead_alerts.deliver_alerts('fake', MagicMock())
        return result, cursor, send

    def test_no_pending_means_no_message(self):
        result, cursor, send = self.run_case([(0,), (0,)])
        self.assertEqual(result, 0)
        send.assert_not_called()

    def test_send_and_record_success(self):
        result, cursor, send = self.run_case([(0,), (1,), ('1', 'Maya', 'Chen', 'maya@example.com'), None])
        self.assertEqual(result, 0)
        send.assert_called_once()
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("status = 'attempted' WHERE" in sql for sql in statements))
        self.assertTrue(any("status = 'sent'" in sql for sql in statements))

    def test_ambiguous_delivery_not_marked_sent(self):
        result, cursor, send = self.run_case([(0,), (1,), ('1', 'Maya', 'Chen', None)], lead_alerts.SlackError('timeout'))
        self.assertEqual(result, 1)
        send.assert_called_once()
        self.assertFalse(any("status = 'sent'" in call.args[0] for call in cursor.execute.call_args_list))

    def test_prior_unconfirmed_attempt_blocks_resend(self):
        result, cursor, send = self.run_case([(1,)])
        self.assertEqual(result, 1)
        send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
