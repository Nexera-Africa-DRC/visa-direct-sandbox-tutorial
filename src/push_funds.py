"""Runnable Visa Direct Push Funds Transfer sample.

Usage:
    cp .env.example .env    # fill in your sandbox credentials
    pip install -r requirements.txt
    python -m src.push_funds

Expected output on success:
    HTTP 200
    actionCode   : 00  (APPROVED)
    approvalCode : XXXXXX

Pitfalls you'll avoid by using this code (see README for the full story):
    1. ca-cert in DER vs PEM format
    2. cert/key pair mismatch after dashboard rotation
    3. PEM files on a single line (openssl cries)
    4. MLE is MANDATORY on business endpoints (not optional)
    5. Use A128GCM, not A256GCM
    6. HTTP header `keyId:` is REQUIRED when MLE is used
    7. Use `requests`, not `httpx` 0.28 (returns 9123 on same payload)
"""

from __future__ import annotations

import json
import os
import sys

import requests
from dotenv import load_dotenv

from .visa_mle import unwrap_response_body, wrap_request_body


def push_funds(payload: dict) -> dict:
    """Send a Push Funds Transfer (OCT) to Visa Direct sandbox.

    Returns the parsed response dict (already decrypted if applicable).
    """
    base_url = os.environ["VISA_BASE_URL"]
    api_key = os.environ["VISA_API_KEY"]
    user_id = os.environ["VISA_USER_ID"]
    password = os.environ["VISA_PASSWORD"]
    cert_path = os.environ["VISA_CERT_PATH"]
    key_path = os.environ["VISA_KEY_PATH"]
    ca_cert_path = os.environ["VISA_CA_CERT_PATH"]
    mle_key_id = os.environ["VISA_MLE_KEY_ID"]
    mle_server_cert_path = os.environ["VISA_MLE_SERVER_CERT_PATH"]
    mle_private_key_path = os.environ["VISA_MLE_PRIVATE_KEY_PATH"]

    # 1. MLE-encrypt the payload (yes, even in sandbox — MLE is mandatory)
    body = wrap_request_body(payload, mle_server_cert_path, mle_key_id)

    # 2. Headers that actually work:
    #    - Content-Type / Accept : standard JSON
    #    - keyId : REQUIRED when MLE is used (undocumented, found by
    #              decompiling vdpplayground.jar)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "keyId": mle_key_id,
    }

    url = f"{base_url}/visadirect/fundstransfer/v1/pushfundstransactions?apikey={api_key}"

    # 3. Use `requests`, not `httpx`. On the exact same payload, httpx 0.28
    #    returns 9123 "credential missing" while requests returns 200. The
    #    diff is probably a header-ordering or chunked-encoding quirk.
    response = requests.post(
        url,
        data=body,                      # pre-serialized JSON string
        cert=(cert_path, key_path),     # mTLS client cert + key
        verify=ca_cert_path,            # Visa server cert verification
        auth=(user_id, password),       # HTTP Basic Auth
        headers=headers,
        timeout=30.0,
    )

    raw = response.json()
    data = unwrap_response_body(raw, mle_private_key_path)
    data["_http_status"] = response.status_code
    return data


def _demo():
    """Minimal demo payload for Visa Direct sandbox.

    This payload is from the official Visa Developer documentation and is
    known to be accepted in sandbox. Replace with your real values for
    production — but keep the structure identical.
    """
    load_dotenv()
    payload = {
        "acquirerCountryCode": "840",
        "acquiringBin": "408999",
        "amount": "124.05",
        "businessApplicationId": "AA",
        "cardAcceptor": {
            "address": {"country": "USA", "county": "081", "state": "CA", "zipCode": "94404"},
            "idCode": "CA-IDCode-77765",
            "name": "Visa Inc. USA-Foster City",
            "terminalId": "TID-9999",
        },
        "localTransactionDateTime": "2024-01-01T00:00:00",
        "merchantCategoryCode": "6012",
        "pointOfServiceData": {
            "motoECIIndicator": "0",
            "panEntryMode": "90",
            "posConditionCode": "00",
        },
        "recipientName": "Mohammed Qasim",
        "recipientPrimaryAccountNumber": "4957030420210454",
        "retrievalReferenceNumber": "412770451020",
        "senderAccountNumber": "4027290082585059",
        "senderAddress": "901 Metro Center Blvd",
        "senderCity": "Foster City",
        "senderCountryCode": "USA",
        "senderName": "Mohammed Qasim",
        "senderReference": "",
        "senderStateCode": "CA",
        "sourceOfFundsCode": "05",
        "systemsTraceAuditNumber": "451018",
        "transactionCurrencyCode": "USD",
        "transactionIdentifier": "381228649430015",
    }

    try:
        result = push_funds(payload)
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    status = result.pop("_http_status", "?")
    print(f"HTTP {status}")
    print(json.dumps(result, indent=2))

    action_code = result.get("actionCode")
    if action_code == "00":
        print(f"\n✅ APPROVED — approvalCode = {result.get('approvalCode')}")
    else:
        rs = result.get("responseStatus", {})
        print(f"\n❌ actionCode={action_code}, error code={rs.get('code')}, "
              f"message={rs.get('message')}")
        sys.exit(2)


if __name__ == "__main__":
    _demo()
