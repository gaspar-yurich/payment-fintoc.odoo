# Odoo Apps Release Checklist

## Packaging
- [ ] Module version updated (`17.0.x.y.z`)
- [ ] Manifest metadata final (`name`, `category`, `license`, `depends`)
- [ ] No debug credentials or test-only data in shipped files
- [ ] README updated with install/setup/troubleshooting
- [ ] PORTING.md updated

## Functional gate
- [ ] Contract sign-off completed
- [ ] All QA P0 PASS with evidence
- [ ] Security checks PASS (signature validation + replay window + idempotency)
- [ ] Refund full/partial/cancel validated

## Store assets
- [ ] Icon present
- [ ] Screenshots from real flow (provider config, checkout redirect, transaction states)
- [ ] Description in merchant language
- [ ] Support contact and SLA listed

## Post-release
- [ ] Monitor first 10 merchant installations
- [ ] Open feedback channel (support form/email)
- [ ] Plan hotfix window for first 7 days after launch
