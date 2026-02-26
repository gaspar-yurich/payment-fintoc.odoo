# Error Contract (v1.0.0)

## Standard shape
```json
{
  "error": "validation_error",
  "code": "invalid_payment_method",
  "message": "payment_intent is not supported",
  "request_id": "req_123"
}
```

## Required fields
- `error` (string) required
- `message` (string) recommended
- `code` (string) recommended for machine handling
- `request_id` (string) recommended for support tracing

## Error catalog expected by plugin
- `invalid_secret_key` -> HTTP 401
- `invalid_signature` -> webhook rejected by plugin, no API status mapping
- `invalid_payment_method` -> HTTP 422
- `missing_required_field` -> HTTP 400/422
- `resource_not_found` -> HTTP 404
- `idempotency_conflict` -> HTTP 409
- `rate_limited` -> HTTP 429
- `internal_error` -> HTTP 500

## Plugin fallback behavior
- On `/v2/checkout_sessions` errors compatible with version mismatch (`404/405/410` or explicit unsupported message), plugin retries `/v1/checkout_sessions`.
- On `payment_intent` method rejection, plugin retries using `payment_initiation`.
