# payment_fintoc

Módulo de Odoo 17 para integrar **Fintoc** como `Payment Provider` con:

- Checkout por redirección (`checkout_sessions`)
- Confirmación de estado por **webhooks firmados**
- Refunds desde Odoo hacia Fintoc
- Modo de recaudación por merchant: `collects` / `direct`
- Métodos de pago separados en UI:
  - `Fintoc - Bank transfer`
  - `Fintoc - Card`

## 1) Instalación

1. Copia la carpeta `payment_fintoc` en tu ruta de addons.
2. Reinicia Odoo.
3. Actualiza lista de apps.
4. Instala **Fintoc Payments**.

## 2) Configuración del provider

Ruta: `Contabilidad -> Configuración -> Proveedores de pago -> Fintoc`

Configura:

- `Secret Key`
- `FINTOC_WEBHOOK_SECRET`
- `Webhook Endpoint URL` (debe ser `https://...`)
- `API Base URL (Optional)` (déjalo vacío para producción; úsalo solo en sandbox/mock)
- `Collection Mode`:
  - `collects`
  - `direct` (si usas bank transfer, completa recipient account)
- Activa/desactiva:
  - `Enable Fintoc - Bank transfer`
  - `Enable Fintoc - Card`

Luego presiona:

- **Register/Update Webhook in Fintoc**

El módulo registra/sincroniza eventos:

- `checkout_session.finished`
- `payment_intent.succeeded`
- `payment_intent.failed`
- `payment_intent.rejected`
- `refund.in_progress`
- `refund.succeeded`
- `refund.failed`

## 3) Flujo de pago

1. Odoo crea checkout session en Fintoc (`/v2/checkout_sessions` con fallback a `/v1/checkout_sessions`).
2. El cliente es redirigido a `redirect_url`.
3. El estado final se confirma por webhook (no por redirect).

Notas:

- Si el método bank transfer se envía como `payment_intent` y Fintoc lo rechaza, se reintenta con `payment_initiation`.
- Se envía `customer_email` (requerido para flujo robusto de refunds).
- Se envía metadata para conciliación:
  - `odoo_tx_reference`
  - `odoo_model`
  - `odoo_document_number`
  - `partner_id` (opcional)

## 4) Refunds

Desde la transacción original en Odoo:

- Odoo crea refund en Fintoc con `POST /v1/refunds`
- Se guarda `refund_id` para trazabilidad
- Si el refund está pendiente, puedes usar botón:
  - **Cancel Refund in Fintoc**

## 5) Simular webhooks (simple)

### 5.1 Preparar payload

```bash
PAYLOAD='{"id":"evt_test_1","type":"payment_intent.succeeded","data":{"id":"pi_test_1","metadata":{"odoo_tx_reference":"TX-REF-001"}}}'
TIMESTAMP=$(date +%s)
```

### 5.2 Firmar con `FINTOC_WEBHOOK_SECRET`

```bash
SECRET='tu_webhook_secret'
SIGNED_PAYLOAD="$TIMESTAMP.$PAYLOAD"
SIGNATURE=$(printf '%s' "$SIGNED_PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" -hex | sed 's/^.* //')
```

### 5.3 Enviar webhook

```bash
curl -X POST "https://tu-dominio/payment/fintoc/webhook" \
  -H "Content-Type: application/json" \
  -H "Fintoc-Signature: t=$TIMESTAMP,v1=$SIGNATURE" \
  -d "$PAYLOAD"
```

## 6) Tests mínimos

Ejecutar:

```bash
odoo-bin -d <database> -i payment_fintoc --test-enable --test-tags /payment_fintoc
```

Incluye pruebas para:

- Configuración y firma webhook en provider
- Creación de checkout session (mock)
- Mapeo de eventos a estado de transacción
- Creación de refunds (mock)

## 7) Troubleshooting

### Error: falta Secret Key

Completa `Secret Key` en el provider Fintoc.

### Error: falta FINTOC_WEBHOOK_SECRET

Completa `FINTOC_WEBHOOK_SECRET` en el provider Fintoc.

### Warning: webhook URL en HTTP

Cambia `Webhook Endpoint URL` a `https://...`.

### Error: partner sin email

Para soporte de refunds, define email en el cliente/partner antes de pagar.

### El pago quedó pendiente

Revisa que el webhook de Fintoc llegue a `/payment/fintoc/webhook` con firma válida.
