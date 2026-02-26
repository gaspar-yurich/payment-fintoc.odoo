import json
import logging

from werkzeug.exceptions import BadRequest, Forbidden

from odoo import _, fields, http
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_fintoc import const

_logger = logging.getLogger(__name__)


class PaymentFintocController(http.Controller):

    @http.route(
        const.RETURN_SUCCESS_ROUTE,
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
        save_session=False,
    )
    def fintoc_return_success(self, reference=None, access_token=None, checkout_session_id=None, **_kwargs):
        """Handle redirect success route.

        Redirect data is informational only. Final status is set by webhook notifications.
        """
        tx_sudo = self._get_tx_from_return(reference, access_token)
        if checkout_session_id:
            tx_sudo.write({'fintoc_checkout_session_id': checkout_session_id})
        if tx_sudo.state == 'draft':
            tx_sudo._set_pending(state_message=_(
                "Returned from Fintoc checkout. Waiting final webhook confirmation."
            ))
        return request.redirect('/payment/status')

    @http.route(
        const.RETURN_CANCEL_ROUTE,
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
        save_session=False,
    )
    def fintoc_return_cancel(self, reference=None, access_token=None, checkout_session_id=None, **_kwargs):
        """Handle redirect cancel route.

        Final status still depends on webhook notifications.
        """
        tx_sudo = self._get_tx_from_return(reference, access_token)
        if checkout_session_id:
            tx_sudo.write({'fintoc_checkout_session_id': checkout_session_id})
        if tx_sudo.state == 'draft':
            tx_sudo._set_pending(state_message=_(
                "Checkout was canceled on Fintoc. Waiting webhook confirmation."
            ))
        return request.redirect('/payment/status')

    @http.route(
        const.WEBHOOK_ROUTE,
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def fintoc_webhook(self):
        """Process incoming Fintoc webhook notifications."""
        raw_body = request.httprequest.get_data(cache=False, as_text=False) or b''
        signature_header = request.httprequest.headers.get('Fintoc-Signature')
        if not signature_header:
            _logger.warning("Received Fintoc webhook without signature header")
            raise Forbidden()

        providers = request.env['payment.provider'].sudo().search([
            ('code', '=', 'fintoc'),
            ('fintoc_webhook_secret', '!=', False),
        ])
        provider = providers.filtered(
            lambda p: p._fintoc_validate_webhook_signature(signature_header, raw_body)
        )[:1]
        if not provider:
            _logger.warning("Received Fintoc webhook with invalid signature")
            raise Forbidden()

        try:
            event_payload = json.loads(raw_body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise BadRequest()

        event_id = event_payload.get('id')
        event_type = event_payload.get('type')
        if not event_id or not event_type:
            raise BadRequest()

        event_model = request.env['payment.fintoc.event'].sudo()
        existing_event = event_model.search([('event_id', '=', event_id)], limit=1)
        if existing_event:
            return request.make_json_response({'status': 'duplicate'})

        event = event_model.create({
            'event_id': event_id,
            'event_type': event_type,
            'provider_id': provider.id,
            'payload': raw_body.decode('utf-8', errors='replace'),
            'state': 'received',
        })

        notification_data = self._build_notification_data(event_payload)
        try:
            tx_sudo = request.env['payment.transaction'].sudo()._handle_notification_data(
                'fintoc', notification_data
            )
        except ValidationError as error:
            event.write({
                'state': 'error',
                'error_message': str(error),
                'processed_date': fields.Datetime.now(),
            })
            _logger.exception(
                "Unable to process Fintoc webhook event %s (%s)",
                event_id,
                event_type,
            )
            return request.make_json_response({'status': 'ignored'})

        event.write({
            'state': 'processed',
            'transaction_id': tx_sudo.id,
            'processed_date': fields.Datetime.now(),
        })
        return request.make_json_response({'status': 'ok'})

    @staticmethod
    def _build_notification_data(event_payload):
        """Normalize Fintoc event payload for payment.transaction hooks."""
        event_type = event_payload.get('type')
        resource = event_payload.get('data') or {}
        metadata = resource.get('metadata') or {}

        notification_data = {
            'event_id': event_payload.get('id'),
            'event_type': event_type,
            'resource': resource,
            'odoo_tx_reference': metadata.get('odoo_tx_reference'),
            'reference': event_payload.get('reference'),
        }

        if event_type == 'checkout_session.finished':
            notification_data.update({
                'checkout_session_id': resource.get('id') or resource.get('checkout_session_id'),
                'payment_intent_id': resource.get('payment_intent_id'),
            })
        elif event_type and event_type.startswith('payment_intent.'):
            notification_data.update({
                'payment_intent_id': resource.get('id') or resource.get('payment_intent_id'),
                'checkout_session_id': resource.get('checkout_session_id'),
                'reason': resource.get('failure_reason') or resource.get('reason'),
            })
        elif event_type and event_type.startswith('refund.'):
            notification_data.update({
                'refund_id': resource.get('id') or resource.get('refund_id'),
                'payment_intent_id': resource.get('resource_id') or resource.get('payment_intent_id'),
                'reason': resource.get('failure_reason') or resource.get('reason'),
            })

        return notification_data

    @staticmethod
    def _get_tx_from_return(reference, access_token):
        if not reference:
            raise Forbidden()
        if not payment_utils.check_access_token(access_token, reference):
            raise Forbidden()

        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', 'fintoc'),
        ], limit=1)
        if not tx_sudo:
            raise Forbidden()
        return tx_sudo
