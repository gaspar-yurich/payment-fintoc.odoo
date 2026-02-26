from odoo import Command

from odoo.addons.payment.tests.common import PaymentCommon


class FintocCommon(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.payment_method_bank = cls.env.ref('payment_fintoc.payment_method_fintoc_bank_transfer')
        cls.payment_method_card = cls.env.ref('payment_fintoc.payment_method_fintoc_card')

        cls.fintoc = cls._prepare_provider('fintoc', update_values={
            'fintoc_secret_key': 'sk_test_123',
            'fintoc_webhook_secret': 'whsec_test_123',
            'fintoc_webhook_endpoint_url': 'https://example.com/payment/fintoc/webhook',
            'fintoc_collection_mode': 'collects',
            'fintoc_enable_bank_transfer': True,
            'fintoc_enable_card': True,
            'payment_method_ids': [Command.set([
                cls.payment_method_bank.id,
                cls.payment_method_card.id,
            ])],
        })

        cls.provider = cls.fintoc
        cls.payment_method = cls.payment_method_bank
        cls.payment_method_id = cls.payment_method.id
        cls.payment_method_code = cls.payment_method.code
