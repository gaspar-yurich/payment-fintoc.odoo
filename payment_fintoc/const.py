FINTOC_API_BASE_URL = 'https://api.fintoc.com'

DEFAULT_TIMEOUT = 20
DEFAULT_WEBHOOK_TOLERANCE_SECONDS = 300

SUPPORTED_WEBHOOK_EVENTS = [
    'checkout_session.finished',
    'payment_intent.succeeded',
    'payment_intent.failed',
    'payment_intent.rejected',
    'refund.in_progress',
    'refund.succeeded',
    'refund.failed',
]

DEFAULT_PAYMENT_METHOD_CODES = [
    'fintoc_bank_transfer',
    'fintoc_card',
]

PAYMENT_METHOD_MAPPING = {
    'fintoc_bank_transfer': 'payment_intent',
    'bank_transfer': 'payment_intent',
    'fintoc_card': 'card',
    'card': 'card',
}

RETURN_SUCCESS_ROUTE = '/payment/fintoc/return/success'
RETURN_CANCEL_ROUTE = '/payment/fintoc/return/cancel'
WEBHOOK_ROUTE = '/payment/fintoc/webhook'
