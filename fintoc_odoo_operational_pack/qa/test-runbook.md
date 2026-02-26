# QA Runbook

## Exit criteria
- All P0 cases in `qa-matrix.csv` are PASS.
- No unresolved blocker defects in payment, webhook security, or refunds.
- Evidence attached for every P0 test case.

## Execution order
1. Setup sanity: provider credentials, webhook endpoint registration, test customer with email.
2. Payment happy paths by channel (Invoice -> eCommerce -> Portal).
3. Direct mode coverage.
4. Security and idempotency checks.
5. Refund lifecycle tests.
6. UX warnings and merchant readability checks.

## Evidence rules
- Each test case requires:
  - Transaction reference(s)
  - Event id(s)
  - Screenshot/video of state transition
  - Timestamp and environment

## Defect severity
- P0: payment/refund/security broken (release blocker)
- P1: major usability/configuration issue (can block depending impact)
- P2: minor issue, no functional regression
