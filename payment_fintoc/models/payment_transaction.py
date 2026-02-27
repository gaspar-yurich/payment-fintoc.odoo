import copy
import logging

from werkzeug import urls

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import hmac as hmac_tool

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_fintoc import const

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    fintoc_checkout_session_id = fields.Char(
        string="Fintoc Checkout Session ID",
        readonly=True,
        copy=False,
    )
    fintoc_redirect_url = fields.Char(
        string="Fintoc Redirect URL",
        readonly=True,
        copy=False,
    )
    fintoc_payment_intent_id = fields.Char(
        string="Fintoc Payment Intent ID",
        readonly=True,
        copy=False,
    )
    fintoc_refund_id = fields.Char(
        string="Fintoc Refund ID",
        readonly=True,
        copy=False,
    )

    # === BUSINESS METHODS === #

    def _get_specific_rendering_values(self, processing_values):
        """Override of payment to return Fintoc-specific redirect values."""
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'fintoc':
            return res

        if self.fintoc_redirect_url and self.fintoc_checkout_session_id:
            return {'api_url': self.fintoc_redirect_url}

        payload = self._fintoc_prepare_checkout_payload()
        session_data = self._fintoc_create_checkout_session_with_fallback(payload)

        checkout_session_id = session_data.get('id')
        redirect_url = session_data.get('redirect_url')
        if not checkout_session_id or not redirect_url:
            raise ValidationError(_(
                "Fintoc did not return checkout session data (id/redirect_url)."
            ))

        self.write({
            'fintoc_checkout_session_id': checkout_session_id,
            'fintoc_redirect_url': redirect_url,
            'provider_reference': checkout_session_id,
        })
        return {'api_url': redirect_url}

    def _fintoc_prepare_checkout_payload(self):
        """Build checkout session payload for Fintoc."""
        self.ensure_one()
        provider = self.provider_id

        customer_email = (self.partner_email or self.partner_id.email or '').strip()
        if not customer_email:
            raise ValidationError(_(
                "Fintoc refunds require the customer email. Please set an email on the customer "
                "before requesting this payment."
            ))

        success_url, cancel_url = self._fintoc_build_return_urls()
        payment_methods = self._fintoc_get_payment_methods_for_session()
        amount_minor = payment_utils.to_minor_currency_units(self.amount, self.currency_id)

        payload = {
            'amount': amount_minor,
            'currency': self.currency_id.name,
            'success_url': success_url,
            'cancel_url': cancel_url,
            'customer_email': customer_email,
            'metadata': self._fintoc_prepare_metadata(),
        }

        if payment_methods:
            payload['payment_methods'] = payment_methods

        if (
            provider.fintoc_collection_mode == 'direct'
            and provider.fintoc_enable_bank_transfer
            and (not payment_methods or 'payment_intent' in payment_methods)
        ):
            payload['payment_method_options'] = {
                'payment_intent': {
                    'recipient_account': provider._fintoc_get_recipient_account_payload(),
                }
            }

        return payload

    def _fintoc_prepare_metadata(self):
        """Return metadata used for reconciliation from webhook events."""
        self.ensure_one()

        model_name = 'payment.transaction'
        document_number = self.reference
        if 'sale_order_ids' in self._fields and self.sale_order_ids:
            model_name = 'sale.order'
            document_number = ', '.join(self.sale_order_ids.mapped('name'))
        elif 'invoice_ids' in self._fields and self.invoice_ids:
            model_name = 'account.move'
            document_number = ', '.join(self.invoice_ids.mapped('name'))

        metadata = {
            'odoo_tx_reference': self.reference,
            'odoo_model': model_name,
            'odoo_document_number': document_number,
        }
        if self.partner_id:
            metadata['partner_id'] = str(self.partner_id.id)
        return metadata

    def _fintoc_build_return_urls(self):
        """Build success/cancel URLs for Fintoc checkout session."""
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if not base_url:
            base_url = self.provider_id.get_base_url()
        access_token = self._fintoc_generate_return_access_token()

        success_params = {
            'reference': self.reference,
            'access_token': access_token,
        }
        cancel_params = {
            'reference': self.reference,
            'access_token': access_token,
        }

        success_url = f"{urls.url_join(base_url, const.RETURN_SUCCESS_ROUTE)}?{urls.url_encode(success_params)}"
        cancel_url = f"{urls.url_join(base_url, const.RETURN_CANCEL_ROUTE)}?{urls.url_encode(cancel_params)}"
        return success_url, cancel_url

    def _fintoc_generate_return_access_token(self):
        self.ensure_one()
        token_str = str(self.reference)
        return hmac_tool(self.env(su=True), 'generate_access_token', token_str)

    def _fintoc_get_payment_methods_for_session(self):
        """Determine payment_methods payload according to provider setup and user selection."""
        self.ensure_one()
        provider = self.provider_id

        selected_method = const.PAYMENT_METHOD_MAPPING.get(self.payment_method_code)

        if selected_method == 'payment_intent' and not provider.fintoc_enable_bank_transfer:
            raise ValidationError(_("Bank transfer is not enabled for this Fintoc provider."))
        if selected_method == 'card' and not provider.fintoc_enable_card:
            raise ValidationError(_("Card is not enabled for this Fintoc provider."))

        if selected_method:
            return [selected_method]

        if provider.fintoc_enable_bank_transfer and provider.fintoc_enable_card:
            # If no explicit user choice was made, let Fintoc show all available methods.
            return None
        if provider.fintoc_enable_bank_transfer:
            return ['payment_intent']
        if provider.fintoc_enable_card:
            return ['card']

        raise ValidationError(_(
            "At least one Fintoc payment method must be enabled on the provider."
        ))

    def _fintoc_create_checkout_session_with_fallback(self, payload):
        """Create checkout session with automatic payment_intent fallback handling."""
        self.ensure_one()
        idempotency_key = self._fintoc_build_idempotency_key('checkout')

        try:
            return self.provider_id._fintoc_create_checkout_session(payload, idempotency_key)
        except ValidationError as error:
            if (
                not self._fintoc_payload_uses_payment_intent(payload)
                or not self._fintoc_should_fallback_to_payment_initiation(error)
            ):
                raise

            fallback_payload = self._fintoc_replace_payment_intent_with_payment_initiation(payload)
            fallback_idempotency_key = self._fintoc_build_idempotency_key(
                'checkout-payment-initiation-fallback'
            )
            _logger.info(
                "Retrying Fintoc checkout with payment_initiation fallback for tx %s",
                self.reference,
            )
            return self.provider_id._fintoc_create_checkout_session(
                fallback_payload,
                fallback_idempotency_key,
            )

    def _fintoc_build_idempotency_key(self, suffix):
        """Build a deterministic idempotency key unique per transaction."""
        self.ensure_one()
        tx_identifier = self.id or self.reference
        key = f"odoo-fintoc-tx-{tx_identifier}-{suffix}"
        return key[:255]

    @staticmethod
    def _fintoc_payload_uses_payment_intent(payload):
        payment_methods = payload.get('payment_methods') or []
        return 'payment_intent' in payment_methods or 'payment_intent' in payload.get(
            'payment_method_options', {}
        )

    @staticmethod
    def _fintoc_should_fallback_to_payment_initiation(error):
        """Return whether the API error indicates payment_intent is unsupported."""
        message = str(error).lower()
        has_payment_intent_signal = 'payment_intent' in message
        has_incompatibility_signal = any(
            token in message for token in ('invalid_enum', 'unsupported', 'not supported')
        )
        return has_payment_intent_signal and has_incompatibility_signal

    @staticmethod
    def _fintoc_replace_payment_intent_with_payment_initiation(payload):
        payload_copy = copy.deepcopy(payload)

        payment_methods = payload_copy.get('payment_methods')
        if payment_methods:
            payload_copy['payment_methods'] = [
                'payment_initiation' if method == 'payment_intent' else method
                for method in payment_methods
            ]

        payment_method_options = payload_copy.get('payment_method_options') or {}
        if 'payment_intent' in payment_method_options:
            payment_method_options['payment_initiation'] = payment_method_options.pop('payment_intent')
            payload_copy['payment_method_options'] = payment_method_options

        return payload_copy

    def _send_refund_request(self, amount_to_refund=None):
        """Override of payment to send refund requests to Fintoc."""
        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
        if self.provider_code != 'fintoc':
            return refund_tx

        if not self.fintoc_payment_intent_id:
            raise UserError(_(
                "Cannot create Fintoc refund because payment_intent_id is missing on the source "
                "transaction."
            ))

        payload = {
            'resource_id': self.fintoc_payment_intent_id,
            'resource_type': 'payment_intent',
        }
        if amount_to_refund and self.currency_id.compare_amounts(amount_to_refund, self.amount) != 0:
            payload['amount'] = payment_utils.to_minor_currency_units(
                amount_to_refund,
                self.currency_id,
            )

        response_data = refund_tx.provider_id._fintoc_make_request(
            endpoint='/v1/refunds',
            payload=payload,
            method='POST',
            idempotency_key=refund_tx.reference,
        )

        refund_id = response_data.get('id')
        if not refund_id:
            raise ValidationError(_("Fintoc did not return a refund ID."))

        refund_tx.write({
            'fintoc_refund_id': refund_id,
            'fintoc_payment_intent_id': self.fintoc_payment_intent_id,
            'provider_reference': refund_id,
        })

        refund_status = (response_data.get('status') or '').lower()
        if refund_status in ('succeeded', 'done', 'success'):
            refund_tx._set_done()
        elif refund_status in ('failed', 'rejected', 'error'):
            refund_tx._set_error(_("Fintoc reported an immediate refund failure."))
        else:
            refund_tx._set_pending()

        return refund_tx

    def action_fintoc_cancel_refund(self):
        """Cancel a pending Fintoc refund from Odoo."""
        self.ensure_one()

        if self.provider_code != 'fintoc' or self.operation != 'refund':
            raise UserError(_("This action is only available for Fintoc refund transactions."))
        if self.state not in ('draft', 'pending'):
            raise UserError(_("Only draft/pending refunds can be cancelled."))
        if not self.fintoc_refund_id:
            raise UserError(_("No Fintoc refund ID found on this transaction."))

        self.provider_id._fintoc_make_request(
            endpoint=f'/v1/refunds/{self.fintoc_refund_id}/cancel',
            payload={},
            method='POST',
            idempotency_key=f'cancel-{self.reference}',
        )
        self._set_canceled(state_message=_("Refund cancellation requested in Fintoc."))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Refund cancellation requested"),
                'message': _("Fintoc received the refund cancellation request."),
                'type': 'success',
                'sticky': False,
            }
        }

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Override of payment to find transaction from Fintoc notification data."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'fintoc' or len(tx) == 1:
            return tx

        refund_id = notification_data.get('refund_id')
        if refund_id:
            tx = self.search([
                ('provider_code', '=', 'fintoc'),
                ('operation', '=', 'refund'),
                '|',
                ('fintoc_refund_id', '=', refund_id),
                ('provider_reference', '=', refund_id),
            ], limit=1)
            if tx:
                return tx

        reference = notification_data.get('odoo_tx_reference') or notification_data.get('reference')
        if reference:
            tx = self.search([
                ('reference', '=', reference),
                ('provider_code', '=', 'fintoc'),
            ], limit=1)
            if tx:
                return tx

        payment_intent_id = notification_data.get('payment_intent_id')
        if payment_intent_id:
            tx = self.search([
                ('provider_code', '=', 'fintoc'),
                ('operation', '!=', 'refund'),
                '|',
                ('fintoc_payment_intent_id', '=', payment_intent_id),
                ('provider_reference', '=', payment_intent_id),
            ], limit=1)
            if tx:
                return tx

        checkout_session_id = notification_data.get('checkout_session_id')
        if checkout_session_id:
            tx = self.search([
                ('provider_code', '=', 'fintoc'),
                ('fintoc_checkout_session_id', '=', checkout_session_id),
            ], limit=1)
            if tx:
                return tx

        raise ValidationError(_(
            "Fintoc: no transaction could be matched from webhook notification data."
        ))

    def _process_notification_data(self, notification_data):
        """Override of payment to process Fintoc webhook event data."""
        super()._process_notification_data(notification_data)
        if self.provider_code != 'fintoc':
            return

        event_type = notification_data.get('event_type')
        if not event_type:
            raise ValidationError(_("Fintoc notification is missing event type."))

        payment_intent_id = notification_data.get('payment_intent_id')
        checkout_session_id = notification_data.get('checkout_session_id')
        refund_id = notification_data.get('refund_id')
        failure_reason = notification_data.get('reason')

        updates = {}
        if payment_intent_id:
            updates['fintoc_payment_intent_id'] = payment_intent_id
            if self.operation != 'refund':
                updates['provider_reference'] = payment_intent_id
        if checkout_session_id:
            updates['fintoc_checkout_session_id'] = checkout_session_id
        if refund_id and self.operation == 'refund':
            updates['fintoc_refund_id'] = refund_id
            updates['provider_reference'] = refund_id
        if updates:
            self.write(updates)

        if event_type == 'checkout_session.finished':
            if self.state == 'draft':
                self._set_pending(state_message=_(
                    "Checkout session finished. Waiting final payment intent status from webhook."
                ))
            return

        if event_type == 'payment_intent.succeeded':
            self._set_done(extra_allowed_states=('cancel',))
            return

        if event_type in ('payment_intent.failed', 'payment_intent.rejected'):
            reason = failure_reason or _("The payment intent failed in Fintoc.")
            if event_type == 'payment_intent.rejected':
                self._set_canceled(state_message=reason)
            else:
                self._set_error(reason)
            return

        if event_type == 'refund.in_progress':
            self._set_pending(extra_allowed_states=('draft',))
            return

        if event_type == 'refund.succeeded':
            self._set_done(extra_allowed_states=('pending', 'draft'))
            self.env.ref('payment.cron_post_process_payment_tx')._trigger()
            return

        if event_type == 'refund.failed':
            self._set_error(failure_reason or _("Fintoc reported a failed refund."))
            return

        _logger.info("Ignoring unsupported Fintoc event type %s for tx %s", event_type, self.reference)
