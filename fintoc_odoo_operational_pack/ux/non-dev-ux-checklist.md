# Non-Dev UX Checklist for Merchant Setup

## Objective
A merchant with no technical background can configure Fintoc payments in under 20 minutes.

## Required UI messages (must be plain language)
- Missing Secret Key:
  - "Debes ingresar tu Secret Key de Fintoc para habilitar cobros."
- Missing Webhook Secret:
  - "Debes ingresar FINTOC_WEBHOOK_SECRET para validar notificaciones de pago."
- Insecure webhook URL:
  - "La URL de webhook debe comenzar con https:// por seguridad."
- Missing customer email when required by flow:
  - "El cliente necesita correo electrónico para soportar devoluciones (refunds)."

## Setup flow script for user testing
1. Give tester only the quickstart document and credentials.
2. Ask tester to configure provider from scratch.
3. Time total completion.
4. Record where tester gets stuck.
5. Update UI help text based on confusion points.

## Pass criteria
- First-time setup success without developer intervention.
- No step requires API knowledge.
- Merchant can identify and resolve warnings by reading UI text.
