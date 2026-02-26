import logging

import requests

from odoo import _
from odoo.exceptions import ValidationError

from odoo.addons.payment_fintoc import const

_logger = logging.getLogger(__name__)


class FintocApiClient:
    """Small API client wrapper for Fintoc requests."""

    def __init__(self, provider):
        provider.ensure_one()
        self.provider = provider

    def request(self, method, endpoint, payload=None, idempotency_key=None, timeout=None):
        """Send an API request and raise ValidationError on failures."""
        status_code, response_data = self.request_raw(
            method=method,
            endpoint=endpoint,
            payload=payload,
            idempotency_key=idempotency_key,
            timeout=timeout,
        )
        if status_code >= 400:
            raise ValidationError(self._build_http_error_message(status_code, response_data))
        return response_data

    def request_raw(self, method, endpoint, payload=None, idempotency_key=None, timeout=None):
        """Send an API request and return raw status + response json dict."""
        base_url = (self.provider.fintoc_api_base_url or const.FINTOC_API_BASE_URL).rstrip('/')
        url = f"{base_url}{endpoint}"
        headers = {
            'Authorization': self.provider.fintoc_secret_key or '',
            'Content-Type': 'application/json',
        }
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key

        request_timeout = timeout or const.DEFAULT_TIMEOUT

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=payload,
                timeout=request_timeout,
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _logger.exception("Fintoc API unreachable at endpoint %s", endpoint)
            raise ValidationError(
                _("Fintoc is not reachable right now. Please try again in a moment.")
            )

        response_data = self._safe_parse_json(response)
        return response.status_code, response_data

    @staticmethod
    def _safe_parse_json(response):
        try:
            return response.json()
        except ValueError:
            return {}

    @staticmethod
    def _build_http_error_message(status_code, response_data):
        message = (
            response_data.get('message')
            or response_data.get('error')
            or response_data.get('detail')
            or _("Unknown API error")
        )
        return _(
            "Fintoc API request failed (HTTP %(status)s): %(message)s",
            status=status_code,
            message=message,
        )
