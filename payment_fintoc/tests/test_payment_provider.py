import hashlib
import hmac
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.payment_fintoc.tests.common import FintocCommon


@tagged('-at_install', 'post_install')
class TestPaymentProvider(FintocCommon):

    def test_get_default_payment_methods_from_toggles(self):
        self.provider.write({
            'fintoc_enable_bank_transfer': True,
            'fintoc_enable_card': False,
        })
        self.assertEqual(
            self.provider._get_default_payment_method_codes(),
            ['fintoc_bank_transfer'],
        )

        self.provider.write({
            'fintoc_enable_bank_transfer': False,
            'fintoc_enable_card': True,
        })
        self.assertEqual(
            self.provider._get_default_payment_method_codes(),
            ['fintoc_card'],
        )

    def test_validate_webhook_signature_accepts_valid_signature(self):
        payload = b'{"id":"evt_1"}'
        timestamp = 1700000000
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode('utf-8')
        signature = hmac.new(
            self.provider.fintoc_webhook_secret.encode('utf-8'),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        header = f"t={timestamp},v1={signature}"

        with patch(
            'odoo.addons.payment_fintoc.models.payment_provider.time.time',
            return_value=timestamp,
        ):
            self.assertTrue(self.provider._fintoc_validate_webhook_signature(header, payload))

    def test_validate_webhook_signature_rejects_old_timestamp(self):
        payload = b'{"id":"evt_2"}'
        timestamp = 1700000000
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode('utf-8')
        signature = hmac.new(
            self.provider.fintoc_webhook_secret.encode('utf-8'),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        header = f"t={timestamp},v1={signature}"

        with patch(
            'odoo.addons.payment_fintoc.models.payment_provider.time.time',
            return_value=timestamp + 999,
        ):
            self.assertFalse(self.provider._fintoc_validate_webhook_signature(header, payload))

    def test_accounting_setup_creates_provider_payment_method_line(self):
        self.provider._fintoc_ensure_accounting_setup()

        account_payment_method = self.env['account.payment.method'].search([
            ('code', '=', 'fintoc'),
            ('payment_type', '=', 'inbound'),
        ], limit=1)
        self.assertTrue(account_payment_method)
        self.assertTrue(self.provider.journal_id)

        payment_method_line = self.env['account.payment.method.line'].search([
            ('payment_provider_id', '=', self.provider.id),
            ('journal_id', '=', self.provider.journal_id.id),
        ], limit=1)
        self.assertTrue(payment_method_line)
        self.assertEqual(payment_method_line.payment_method_id, account_payment_method)
