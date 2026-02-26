from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.payment_fintoc.tests.common import FintocCommon


@tagged('-at_install', 'post_install')
class TestPaymentTransaction(FintocCommon):

    def test_get_specific_rendering_values_creates_checkout_session(self):
        tx = self._create_transaction(
            flow='redirect',
            payment_method_id=self.payment_method_bank.id,
            reference='FINTOC-TX-001',
        )

        with patch.object(
            type(self.provider),
            '_fintoc_create_checkout_session',
            return_value={
                'id': 'cs_test_1',
                'redirect_url': 'https://checkout.example.test/session/1',
            },
        ):
            rendering_values = tx._get_specific_rendering_values({})

        self.assertEqual(rendering_values['api_url'], 'https://checkout.example.test/session/1')
        self.assertEqual(tx.fintoc_checkout_session_id, 'cs_test_1')
        self.assertEqual(tx.fintoc_redirect_url, 'https://checkout.example.test/session/1')

    def test_process_notification_data_marks_transaction_done(self):
        tx = self._create_transaction(
            flow='redirect',
            payment_method_id=self.payment_method_bank.id,
            reference='FINTOC-TX-002',
        )

        tx._process_notification_data({
            'event_type': 'payment_intent.succeeded',
            'payment_intent_id': 'pi_123',
            'resource': {'id': 'pi_123'},
        })

        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.fintoc_payment_intent_id, 'pi_123')

    def test_send_refund_request_creates_pending_refund_transaction(self):
        tx = self._create_transaction(
            flow='redirect',
            payment_method_id=self.payment_method_bank.id,
            reference='FINTOC-TX-003',
            state='done',
            fintoc_payment_intent_id='pi_refundable_1',
            provider_reference='pi_refundable_1',
        )

        with patch.object(
            type(self.provider),
            '_fintoc_make_request',
            return_value={'id': 're_test_1', 'status': 'in_progress'},
        ):
            refund_tx = tx._send_refund_request(amount_to_refund=10.0)

        self.assertEqual(refund_tx.operation, 'refund')
        self.assertEqual(refund_tx.state, 'pending')
        self.assertEqual(refund_tx.fintoc_refund_id, 're_test_1')
