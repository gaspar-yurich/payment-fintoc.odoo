# PORTING.md

Checklist concreto para portar `payment_fintoc` entre versiones.

## Base objetivo actual

- Implementación principal: **Odoo 17**

## Porting a Odoo 16

1. Validar API de `payment.provider` y `payment.transaction`:
   - `_get_specific_rendering_values`
   - `_send_refund_request`
   - `_get_tx_from_notification_data`
   - `_process_notification_data`
2. Revisar sintaxis XML de vistas (`invisible`, `required`) por cambios de engine.
3. Verificar existencia de campos base en provider/transaction:
   - `redirect_form_view_id`
   - `support_refund`
   - `payment_method_ids`
4. Probar `payment.method` data model (campos obligatorios / imagen).
5. Revalidar controlador webhook:
   - `request.get_json_data()`
   - acceso a `request.httprequest.headers`
6. Ejecutar tests y ajustar imports de utilidades (`payment.utils`, `hmac_tool`) si cambian.

## Porting a Odoo 18

1. Reconfirmar hooks del framework de pagos:
   - rendering/processing
   - refunds
   - notificaciones
2. Revisar si cambian nombres de campos `support_*` o comportamiento de `payment_method_ids`.
3. Revisar compatibilidad de templates QWeb de redirect form.
4. Validar comportamiento del post-processing cron para refunds.
5. Revalidar ACL/modelo `payment.fintoc.event` con nuevas políticas de seguridad.
6. Ejecutar pruebas end-to-end:
   - Facturas
   - Checkout `website_sale`
   - Portal
7. Ajustar manifest (`version`, dependencias) y rerun tests.

## Checklist de regresión funcional (16/18)

1. Crear sesión checkout y redirigir correctamente.
2. Confirmar pago solo por webhook (no por return URL).
3. Procesar eventos duplicados sin reprocesar (idempotencia por `event_id`).
4. Crear refund completo y parcial desde Odoo.
5. Cancelar refund pendiente desde botón Odoo.
6. Validar firma de webhook (timestamp + HMAC SHA256 + compare digest).
7. Verificar warnings UX:
   - Secret Key faltante
   - Webhook secret faltante
   - URL webhook en HTTP
   - Partner sin email

