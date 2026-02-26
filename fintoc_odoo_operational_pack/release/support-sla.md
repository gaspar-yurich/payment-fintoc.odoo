# Support SLA (Template)

## Channels
- Email:
- Ticket portal:
- Escalation contact:

## Severity levels
- Sev1 (payments/refunds down): response within 1 hour, continuous updates.
- Sev2 (major degradation): response within 4 hours.
- Sev3 (minor issue): response within 1 business day.

## Required incident data from merchant
- Odoo transaction reference
- Approximate timestamp
- Screenshot of provider config warning/error
- Event id (if webhook-related)

## Internal handoff
- Support -> Plugin engineer -> API backend -> Product owner
