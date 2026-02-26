# RUN_ME_FIRST

## What is already done by me
- Full Odoo module `payment_fintoc` implemented in this workspace.
- API contract pack created in `contract/`.
- Sandbox kit created in `sandbox/`.
- QA plan and matrix created in `qa/`.
- Non-dev UX checklist created in `ux/`.
- Release checklists/templates created in `release/`.

## Execution sequence (strict order)

### Phase 1: Contract freeze
1. Review `contract/openapi.yaml`.
2. Review `contract/webhooks.md`.
3. Review `contract/errors.md`.
4. Approve with stakeholders using `contract/signoff.md`.

### Phase 2: Sandbox bring-up
1. Provision test secrets and merchant.
2. Configure Odoo provider using `sandbox/sandbox-quickstart.md`.
3. Simulate webhooks with `sandbox/scripts/simulate_webhook.sh`.
4. Validate expected transaction/refund states.

### Phase 3: QA execution
1. Execute all cases in `qa/qa-matrix.csv`.
2. Capture evidence using `qa/evidence-template.md`.
3. Enforce release gate from `qa/test-runbook.md`.

### Phase 4: UX validation (non-dev merchants)
1. Run setup test with non-dev users.
2. Apply fixes for confusing wording/steps using `ux/non-dev-ux-checklist.md`.

### Phase 5: Odoo Apps release
1. Run `release/odoo-apps-release-checklist.md`.
2. Publish with updated changelog and support SLA templates.

## External accesses required
See `ACCESS_STOPPERS.md`.
