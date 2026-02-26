# Compatibility Policy (v1.0.0)

## Versioning
- Contract version follows semver: `MAJOR.MINOR.PATCH`.
- Current stable: `1.0.0`.

## Non-breaking changes (allowed in 1.x)
- New optional fields in responses/webhooks.
- New optional webhook event fields.
- Additional error codes that preserve existing semantics.

## Breaking changes (require 2.0.0)
- Removing or renaming required fields.
- Changing field types.
- Changing signature format/algorithm.
- Removing existing endpoints used by plugin.
- Changing semantics of payment/refund status values.

## Deprecation policy
- Minimum deprecation window: 90 days.
- Deprecations must provide replacement and migration guide.
- Plugin team receives heads-up before public deprecation notice.

## Backward compatibility guarantees for Odoo plugin
- `/v2/checkout_sessions` preferred.
- `/v1/checkout_sessions` kept as compatibility path while plugin supports fallback.
- Webhook event names listed in contract remain stable in 1.x.
