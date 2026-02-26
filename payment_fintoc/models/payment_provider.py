import hashlib
import hmac
import logging
import time

from werkzeug import urls

from odoo import _, Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.payment_fintoc import const
from odoo.addons.payment_fintoc.models.fintoc_api import FintocApiClient

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('fintoc', "Fintoc")],
        ondelete={'fintoc': 'set default'},
    )

    fintoc_secret_key = fields.Char(
        string="Secret Key",
        help="Private API key used to authenticate requests against Fintoc.",
        required_if_provider='fintoc',
        groups='base.group_system',
        copy=False,
    )
    fintoc_webhook_secret = fields.Char(
        string="FINTOC_WEBHOOK_SECRET",
        help="Secret used to validate incoming webhook signatures from Fintoc.",
        required_if_provider='fintoc',
        groups='base.group_system',
        copy=False,
    )
    fintoc_webhook_endpoint_url = fields.Char(
        string="Webhook Endpoint URL",
        help="Public HTTPS URL that Fintoc will call to notify payment and refund status updates.",
        required_if_provider='fintoc',
    )
    fintoc_webhook_endpoint_id = fields.Char(
        string="Fintoc Webhook Endpoint ID",
        help="Identifier returned by Fintoc after registering the webhook endpoint.",
        copy=False,
    )
    fintoc_webhook_last_sync = fields.Datetime(
        string="Last Webhook Sync",
        readonly=True,
        copy=False,
    )
    fintoc_webhook_tolerance = fields.Integer(
        string="Webhook Timestamp Tolerance (seconds)",
        help="Maximum age accepted for webhook signatures.",
        default=const.DEFAULT_WEBHOOK_TOLERANCE_SECONDS,
    )
    fintoc_api_base_url = fields.Char(
        string="API Base URL (Optional)",
        help=(
            "Optional override for sandbox/mock environments. "
            "Leave empty to use https://api.fintoc.com."
        ),
    )

    fintoc_collection_mode = fields.Selection(
        string="Collection Mode",
        selection=[
            ('collects', "collects (Fintoc collects)"),
            ('direct', "direct (Direct payments)"),
        ],
        default='collects',
        required_if_provider='fintoc',
        help="Choose whether Fintoc collects funds or direct payments are used.",
    )

    fintoc_enable_bank_transfer = fields.Boolean(
        string="Enable Fintoc - Bank transfer",
        default=True,
        help="If enabled, customers can pay using bank transfer via Fintoc.",
    )
    fintoc_enable_card = fields.Boolean(
        string="Enable Fintoc - Card",
        default=True,
        help="If enabled, customers can pay using card via Fintoc.",
    )

    fintoc_recipient_holder_id = fields.Char(
        string="Recipient Holder ID",
        help="Recipient account holder identifier required by Fintoc direct bank transfer mode.",
    )
    fintoc_recipient_number = fields.Char(
        string="Recipient Account Number",
        help="Recipient account number used for direct bank transfer mode.",
    )
    fintoc_recipient_type = fields.Char(
        string="Recipient Account Type",
        help="Recipient account type expected by Fintoc (for example: checking_account).",
    )
    fintoc_recipient_institution_id = fields.Char(
        string="Recipient Institution ID",
        help="Institution identifier expected by Fintoc for direct bank transfer mode.",
    )

    fintoc_configuration_warning = fields.Text(
        string="Configuration Warnings",
        compute='_compute_fintoc_configuration_warning',
    )

    # === COMPUTE METHODS === #

    @api.depends(
        'code',
        'fintoc_secret_key',
        'fintoc_webhook_secret',
        'fintoc_webhook_endpoint_url',
        'fintoc_api_base_url',
    )
    def _compute_fintoc_configuration_warning(self):
        for provider in self:
            if provider.code != 'fintoc':
                provider.fintoc_configuration_warning = False
                continue

            warnings = []
            if not provider.fintoc_secret_key:
                warnings.append(_("Secret Key is missing."))
            if not provider.fintoc_webhook_secret:
                warnings.append(_("FINTOC_WEBHOOK_SECRET is missing."))
            if provider.fintoc_webhook_endpoint_url and provider.fintoc_webhook_endpoint_url.startswith('http://'):
                warnings.append(_(
                    "Webhook Endpoint URL should use HTTPS. HTTP endpoints are not secure."
                ))
            if provider.fintoc_api_base_url and not provider.fintoc_api_base_url.startswith('https://'):
                warnings.append(_(
                    "API Base URL should use HTTPS when overriding production endpoint."
                ))

            warnings.append(_(
                "Refunds require customer email on payment transactions."
            ))
            provider.fintoc_configuration_warning = "\n".join(warnings) if warnings else False

    @api.depends('code')
    def _compute_view_configuration_fields(self):
        """Override of payment to adapt the Fintoc provider form."""
        super()._compute_view_configuration_fields()
        self.filtered(lambda p: p.code == 'fintoc').update({
            'show_allow_tokenization': False,
            'show_allow_express_checkout': False,
        })

    def _compute_feature_support_fields(self):
        """Override of payment to enable refunds for Fintoc."""
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'fintoc').update({
            'support_refund': 'partial',
            'support_tokenization': False,
            'support_express_checkout': False,
            'support_manual_capture': False,
        })

    # === ONCHANGE METHODS === #

    @api.onchange('fintoc_webhook_endpoint_url')
    def _onchange_fintoc_webhook_endpoint_url(self):
        for provider in self.filtered(lambda p: p.code == 'fintoc'):
            if provider.fintoc_webhook_endpoint_url and provider.fintoc_webhook_endpoint_url.startswith('http://'):
                return {
                    'warning': {
                        'title': _("Security Warning"),
                        'message': _(
                            "Webhook Endpoint URL should use HTTPS to prevent tampering risks."
                        ),
                    }
                }
        return None

    # === CONSTRAINTS === #

    @api.constrains('code', 'fintoc_enable_bank_transfer', 'fintoc_enable_card')
    def _check_fintoc_payment_methods_selection(self):
        for provider in self.filtered(lambda p: p.code == 'fintoc'):
            if not provider.fintoc_enable_bank_transfer and not provider.fintoc_enable_card:
                raise ValidationError(_(
                    "At least one Fintoc payment method must be enabled: Bank transfer or Card."
                ))

    @api.constrains(
        'code',
        'fintoc_collection_mode',
        'fintoc_enable_bank_transfer',
        'fintoc_recipient_holder_id',
        'fintoc_recipient_number',
        'fintoc_recipient_type',
        'fintoc_recipient_institution_id',
    )
    def _check_fintoc_direct_mode_recipient_account(self):
        for provider in self.filtered(
            lambda p: p.code == 'fintoc'
            and p.fintoc_collection_mode == 'direct'
            and p.fintoc_enable_bank_transfer
        ):
            missing_labels = []
            field_mapping = {
                'fintoc_recipient_holder_id': _("Recipient Holder ID"),
                'fintoc_recipient_number': _("Recipient Account Number"),
                'fintoc_recipient_type': _("Recipient Account Type"),
                'fintoc_recipient_institution_id': _("Recipient Institution ID"),
            }
            for field_name, label in field_mapping.items():
                if not provider[field_name]:
                    missing_labels.append(label)

            if missing_labels:
                raise ValidationError(_(
                    "Direct mode for bank transfer requires recipient account fields: %s",
                    ", ".join(missing_labels),
                ))

    # === CRUD METHODS === #

    @api.model_create_multi
    def create(self, values_list):
        providers = super().create(values_list)
        providers.filtered(lambda p: p.code == 'fintoc')._fintoc_sync_payment_methods()
        return providers

    def write(self, values):
        result = super().write(values)
        if (
            not self.env.context.get('skip_fintoc_pm_sync')
            and any(
                key in values
                for key in ('code', 'fintoc_enable_bank_transfer', 'fintoc_enable_card')
            )
        ):
            self.filtered(lambda p: p.code == 'fintoc')._fintoc_sync_payment_methods()
        return result

    # === BUSINESS METHODS === #

    def _fintoc_sync_payment_methods(self):
        """Synchronize attached payment methods from the Fintoc method toggles."""
        bank_method = self.env.ref(
            'payment_fintoc.payment_method_fintoc_bank_transfer', raise_if_not_found=False
        )
        card_method = self.env.ref('payment_fintoc.payment_method_fintoc_card', raise_if_not_found=False)

        for provider in self:
            method_ids = []
            if provider.fintoc_enable_bank_transfer and bank_method:
                method_ids.append(bank_method.id)
            if provider.fintoc_enable_card and card_method:
                method_ids.append(card_method.id)

            provider.with_context(skip_fintoc_pm_sync=True).write({
                'payment_method_ids': [Command.set(method_ids)]
            })

    def _get_default_payment_method_codes(self):
        """Override of payment to return default Fintoc payment methods."""
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'fintoc':
            return default_codes

        method_codes = []
        if self.fintoc_enable_bank_transfer:
            method_codes.append('fintoc_bank_transfer')
        if self.fintoc_enable_card:
            method_codes.append('fintoc_card')
        return method_codes

    def _fintoc_get_api_client(self):
        self.ensure_one()
        if not self.fintoc_secret_key:
            raise UserError(_("Fintoc Secret Key is required."))
        return FintocApiClient(self)

    def _fintoc_make_request(self, endpoint, payload=None, method='POST', idempotency_key=None):
        self.ensure_one()
        client = self._fintoc_get_api_client()
        return client.request(
            method=method,
            endpoint=endpoint,
            payload=payload,
            idempotency_key=idempotency_key,
        )

    def _fintoc_make_request_raw(
        self,
        endpoint,
        payload=None,
        method='POST',
        idempotency_key=None,
    ):
        self.ensure_one()
        client = self._fintoc_get_api_client()
        return client.request_raw(
            method=method,
            endpoint=endpoint,
            payload=payload,
            idempotency_key=idempotency_key,
        )

    def _fintoc_create_checkout_session(self, payload, idempotency_key):
        """Create checkout session with automatic /v2 -> /v1 fallback."""
        self.ensure_one()

        status_code, response_data = self._fintoc_make_request_raw(
            endpoint='/v2/checkout_sessions',
            payload=payload,
            method='POST',
            idempotency_key=idempotency_key,
        )
        if status_code < 400:
            return response_data

        if self._fintoc_should_retry_checkout_with_v1(status_code, response_data):
            _logger.info("Retrying Fintoc checkout session creation on /v1 endpoint")
            return self._fintoc_make_request(
                endpoint='/v1/checkout_sessions',
                payload=payload,
                method='POST',
                idempotency_key=idempotency_key,
            )

        raise ValidationError(FintocApiClient._build_http_error_message(status_code, response_data))

    @staticmethod
    def _fintoc_should_retry_checkout_with_v1(status_code, response_data):
        if status_code in (404, 405, 410):
            return True
        message = str(
            response_data.get('message')
            or response_data.get('error')
            or ''
        ).lower()
        return any(token in message for token in ('unsupported', 'not found', 'version', 'v2'))

    def _fintoc_get_webhook_endpoint_url(self):
        self.ensure_one()
        return self.fintoc_webhook_endpoint_url or urls.url_join(
            self.get_base_url(), const.WEBHOOK_ROUTE
        )

    def _fintoc_get_webhook_registration_payload(self):
        self.ensure_one()
        return {
            'url': self._fintoc_get_webhook_endpoint_url(),
            'enabled_events': const.SUPPORTED_WEBHOOK_EVENTS,
        }

    def _fintoc_get_recipient_account_payload(self):
        self.ensure_one()
        return {
            'holder_id': self.fintoc_recipient_holder_id,
            'number': self.fintoc_recipient_number,
            'type': self.fintoc_recipient_type,
            'institution_id': self.fintoc_recipient_institution_id,
        }

    def action_fintoc_register_or_update_webhook(self):
        """Create/update webhook endpoint in Fintoc using provider configuration."""
        self.ensure_one()
        if self.code != 'fintoc':
            return False

        if not self.fintoc_secret_key:
            raise UserError(_("Please set the Secret Key before registering the webhook."))
        if not self.fintoc_webhook_secret:
            raise UserError(_("Please set FINTOC_WEBHOOK_SECRET before registering the webhook."))

        webhook_url = self._fintoc_get_webhook_endpoint_url()
        if not webhook_url.startswith('https://'):
            raise UserError(_("Webhook Endpoint URL must start with https://"))

        payload = self._fintoc_get_webhook_registration_payload()
        response_data = None

        if self.fintoc_webhook_endpoint_id:
            status_code, response = self._fintoc_make_request_raw(
                endpoint=f'/v1/webhook_endpoints/{self.fintoc_webhook_endpoint_id}',
                payload=payload,
                method='PUT',
            )
            if status_code < 400:
                response_data = response
            elif status_code == 404:
                response_data = self._fintoc_make_request(
                    endpoint='/v1/webhook_endpoints',
                    payload=payload,
                    method='POST',
                )
            else:
                raise ValidationError(FintocApiClient._build_http_error_message(status_code, response))
        else:
            response_data = self._fintoc_make_request(
                endpoint='/v1/webhook_endpoints',
                payload=payload,
                method='POST',
            )

        webhook_endpoint_id = response_data.get('id') or response_data.get('data', {}).get('id')
        if not webhook_endpoint_id:
            raise ValidationError(_(
                "Fintoc did not return a webhook endpoint ID. Please verify your credentials."
            ))

        self.write({
            'fintoc_webhook_endpoint_id': webhook_endpoint_id,
            'fintoc_webhook_endpoint_url': webhook_url,
            'fintoc_webhook_last_sync': fields.Datetime.now(),
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Webhook synchronized"),
                'message': _("Webhook endpoint was registered/updated successfully in Fintoc."),
                'type': 'success',
                'sticky': False,
            }
        }

    def _fintoc_validate_webhook_signature(self, signature_header, raw_body):
        """Validate Fintoc webhook signature with constant-time compare."""
        self.ensure_one()
        if not self.fintoc_webhook_secret or not signature_header:
            return False

        timestamp, signatures = self._fintoc_extract_signature_parts(signature_header)
        if not timestamp or not signatures:
            return False

        try:
            timestamp_int = int(timestamp)
        except (TypeError, ValueError):
            return False

        tolerance = self.fintoc_webhook_tolerance or const.DEFAULT_WEBHOOK_TOLERANCE_SECONDS
        if abs(int(time.time()) - timestamp_int) > tolerance:
            _logger.warning(
                "Ignoring Fintoc webhook with outdated timestamp for provider %s", self.id
            )
            return False

        try:
            body_text = raw_body.decode('utf-8')
        except UnicodeDecodeError:
            return False

        signed_payload = f"{timestamp}.{body_text}".encode('utf-8')
        expected_signature = hmac.new(
            self.fintoc_webhook_secret.encode('utf-8'),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

        return any(hmac.compare_digest(sig, expected_signature) for sig in signatures)

    @staticmethod
    def _fintoc_extract_signature_parts(signature_header):
        timestamp = None
        signatures = []
        for part in signature_header.split(','):
            key, _, value = part.partition('=')
            key = key.strip()
            value = value.strip()
            if key == 't':
                timestamp = value
            elif key == 'v1' and value:
                signatures.append(value)
        return timestamp, signatures
