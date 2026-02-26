# Webhook Contract (v1.0.0)

## Endpoint
- Odoo route: `POST /payment/fintoc/webhook`
- Merchant-facing requirement: URL MUST be HTTPS.

## Signature
- Header: `Fintoc-Signature`
- Format: `t=UNIX_TIMESTAMP,v1=HEX_SIGNATURE`
- Signed message: `${timestamp}.${raw_body}`
- Algorithm: `HMAC-SHA256`
- Secret: `FINTOC_WEBHOOK_SECRET`
- Constant-time comparison: required (`compare_digest`)
- Default timestamp tolerance: `300 seconds`

## Supported events
- `checkout_session.finished`
- `payment_intent.succeeded`
- `payment_intent.failed`
- `payment_intent.rejected`
- `refund.in_progress`
- `refund.succeeded`
- `refund.failed`

## Canonical payload envelope
```json
{
  "id": "evt_123",
  "type": "payment_intent.succeeded",
  "created_at": "2026-02-26T14:20:00Z",
  "data": {}
}
```

## Event-specific `data` requirements

### checkout_session.finished
Required keys in `data`:
- `id` (checkout session id)
- `payment_intent_id` (if available)
- `metadata.odoo_tx_reference` (strongly recommended)

### payment_intent.succeeded
Required keys in `data`:
- `id` (payment intent id)
- `metadata.odoo_tx_reference` OR an equivalent reference key

### payment_intent.failed / payment_intent.rejected
Required keys in `data`:
- `id`
- `metadata.odoo_tx_reference` OR equivalent
Optional:
- `reason` or `failure_reason`

### refund.in_progress / refund.succeeded / refund.failed
Required keys in `data`:
- `id` (refund id)
- `resource_id` (payment intent id)
Optional:
- `reason` or `failure_reason`
- `metadata.odoo_tx_reference`

## Odoo state mapping
- `checkout_session.finished` -> keep tx pending while waiting final intent status
- `payment_intent.succeeded` -> transaction done
- `payment_intent.failed` -> transaction error
- `payment_intent.rejected` -> transaction canceled
- `refund.in_progress` -> refund tx pending
- `refund.succeeded` -> refund tx done
- `refund.failed` -> refund tx error

## Idempotency rules
- Event id (`id`) is globally unique.
- Repeated event ids MUST be accepted and ignored (200 with duplicate status is allowed).
- Plugin stores processed event ids in `payment.fintoc.event`.

## Replay prevention
- Reject events outside tolerance window.
- Reject missing/invalid signature.
- Reject malformed JSON body.
