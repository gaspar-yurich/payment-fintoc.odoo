#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage:
  $0 --url <odoo_webhook_url> --secret <webhook_secret> --event <event_type> --tx-ref <tx_ref> [--resource-id <id>] [--event-id <id>] [--reason <text>]

Example:
  $0 --url "https://odoo.example.com/payment/fintoc/webhook" \
     --secret "whsec_test_123" \
     --event payment_intent.succeeded \
     --tx-ref "TX-REF-001" \
     --resource-id "pi_test_001"
USAGE
}

URL=""
SECRET=""
EVENT=""
TX_REF=""
RESOURCE_ID=""
EVENT_ID=""
REASON=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url) URL="$2"; shift 2 ;;
    --secret) SECRET="$2"; shift 2 ;;
    --event) EVENT="$2"; shift 2 ;;
    --tx-ref) TX_REF="$2"; shift 2 ;;
    --resource-id) RESOURCE_ID="$2"; shift 2 ;;
    --event-id) EVENT_ID="$2"; shift 2 ;;
    --reason) REASON="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

if [[ -z "$URL" || -z "$SECRET" || -z "$EVENT" || -z "$TX_REF" ]]; then
  usage
  exit 1
fi

if [[ -z "$EVENT_ID" ]]; then
  EVENT_ID="evt_$(date +%s)"
fi

if [[ -z "$RESOURCE_ID" ]]; then
  if [[ "$EVENT" == refund.* ]]; then
    RESOURCE_ID="re_test_001"
  else
    RESOURCE_ID="pi_test_001"
  fi
fi

DATA_PAYLOAD="{}"
case "$EVENT" in
  checkout_session.finished)
    DATA_PAYLOAD="{\"id\":\"cs_test_001\",\"payment_intent_id\":\"pi_test_001\",\"metadata\":{\"odoo_tx_reference\":\"$TX_REF\"}}"
    ;;
  payment_intent.succeeded)
    DATA_PAYLOAD="{\"id\":\"$RESOURCE_ID\",\"status\":\"succeeded\",\"metadata\":{\"odoo_tx_reference\":\"$TX_REF\"}}"
    ;;
  payment_intent.failed)
    DATA_PAYLOAD="{\"id\":\"$RESOURCE_ID\",\"status\":\"failed\",\"failure_reason\":\"${REASON:-insufficient_funds}\",\"metadata\":{\"odoo_tx_reference\":\"$TX_REF\"}}"
    ;;
  payment_intent.rejected)
    DATA_PAYLOAD="{\"id\":\"$RESOURCE_ID\",\"status\":\"rejected\",\"reason\":\"${REASON:-compliance_check_failed}\",\"metadata\":{\"odoo_tx_reference\":\"$TX_REF\"}}"
    ;;
  refund.in_progress)
    DATA_PAYLOAD="{\"id\":\"$RESOURCE_ID\",\"status\":\"in_progress\",\"resource_id\":\"pi_test_001\",\"metadata\":{\"odoo_tx_reference\":\"$TX_REF\"}}"
    ;;
  refund.succeeded)
    DATA_PAYLOAD="{\"id\":\"$RESOURCE_ID\",\"status\":\"succeeded\",\"resource_id\":\"pi_test_001\",\"metadata\":{\"odoo_tx_reference\":\"$TX_REF\"}}"
    ;;
  refund.failed)
    DATA_PAYLOAD="{\"id\":\"$RESOURCE_ID\",\"status\":\"failed\",\"resource_id\":\"pi_test_001\",\"failure_reason\":\"${REASON:-refund_window_expired}\",\"metadata\":{\"odoo_tx_reference\":\"$TX_REF\"}}"
    ;;
  *)
    echo "Unsupported event: $EVENT"
    exit 1
    ;;
esac

BODY="{\"id\":\"$EVENT_ID\",\"type\":\"$EVENT\",\"data\":$DATA_PAYLOAD}"
TIMESTAMP="$(date +%s)"
SIGNED_PAYLOAD="$TIMESTAMP.$BODY"
SIGNATURE="$(printf '%s' "$SIGNED_PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" -hex | awk '{print $NF}')"

set -x
curl -sS -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "Fintoc-Signature: t=$TIMESTAMP,v1=$SIGNATURE" \
  -d "$BODY"
set +x

echo
