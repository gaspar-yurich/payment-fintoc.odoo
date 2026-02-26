# Sandbox Quickstart (15 minutes)

## Objective
Validate end-to-end flow between Fintoc and Odoo plugin in test mode.

## Prerequisites
- Odoo module `payment_fintoc` installed.
- Odoo provider `Fintoc` configured in `Test` state.
- Public HTTPS URL for Odoo webhook endpoint.

## Test credentials template
Fill and share internally as secure secret values:
- `FINTOC_SECRET_KEY_TEST=<replace>`
- `FINTOC_WEBHOOK_SECRET_TEST=<replace>`

## Step 1: Configure provider in Odoo
1. Go to `Accounting -> Configuration -> Payment Providers -> Fintoc`.
2. Fill:
   - Secret Key
   - FINTOC_WEBHOOK_SECRET
   - Webhook Endpoint URL (`https://<domain>/payment/fintoc/webhook`)
3. Choose `collects` or `direct`.
4. Enable Bank transfer/Card as needed.
5. Click `Register/Update Webhook in Fintoc`.

## Step 2: Create a test transaction in Odoo
1. Create a payable invoice or ecommerce checkout.
2. Ensure customer has email.
3. Start payment with Fintoc and capture the Odoo tx reference.

## Step 3: Simulate webhook
Use helper script:
```bash
bash sandbox/scripts/simulate_webhook.sh \
  --url "https://<odoo-domain>/payment/fintoc/webhook" \
  --secret "$FINTOC_WEBHOOK_SECRET_TEST" \
  --event payment_intent.succeeded \
  --tx-ref "<ODOO_TX_REFERENCE>" \
  --resource-id "pi_test_001"
```

## Step 4: Validate state transitions
- Payment transaction moves to `Done` on `payment_intent.succeeded`.
- For refund tests, create refund and simulate `refund.in_progress` + `refund.succeeded`.

## Step 5: Negative security checks
- Send webhook with wrong secret -> expect rejection.
- Send webhook with old timestamp -> expect rejection.
- Send same event id twice -> first processed, second ignored as duplicate.

## Troubleshooting
- If transaction stays pending, verify webhook URL is reachable and HTTPS.
- If webhook rejected, verify signature header and exact raw body used for signing.
- If refund fails to create, verify original tx has `payment_intent_id` from webhook lifecycle.
