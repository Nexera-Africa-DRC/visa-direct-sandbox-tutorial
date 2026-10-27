# Setup — Visa Developer Account & Project

A step-by-step walkthrough to go from zero to credentials in roughly 20 minutes.

> This document is a stub — contributions welcome. The full walkthrough with screenshots will land in Phase 2 of this project.

## Minimal checklist

1. **Create a Visa Developer account** at [developer.visa.com](https://developer.visa.com) and enable MFA on your account.

2. **Create a new project** (e.g. `my-fintech-sandbox`). Note down the project UUID that appears in the dashboard URL — Visa uses it as the `CN` of your mTLS certificates.

3. **Add products to the project**:
   - *Visa Direct* (push/pull funds, mVisa, Query, Watchlist screening).
   - *Visa Accept* (if you want card acceptance via Visa, as opposed to CyberSource).
   - *Merchant Search*, *Foreign Exchange Rates* (optional helpers).

4. **Complete API Registration** for each product. This is the step that trips people up — adding a product to a project is **not** enough; you also need to click `Start` on its *API Registration* row in the Onboarding Dashboard.

5. **Generate credentials** under *Credentials*:
   - *Two-Way SSL → Inbound*: `cert.pem`, `key.pem`, `Username` (`VISA_USER_ID`), `Password` (`VISA_PASSWORD`). Download them immediately — passwords are only shown once.
   - *X-Pay Token → Inbound* (optional for Push Funds, useful elsewhere): `API Key` and RSA-encrypted `Shared Secret`.

6. **Generate an MLE Key ID** under *Credentials → Message Level Encryption → + Generate Key ID*. Download the 3 PEM files:
   - `mle_private.pem` — your private key (decrypt Visa responses)
   - `mle_client_cert.pem` — your public cert (ties your private key to the Key ID)
   - `mle_server_cert.pem` — Visa's public key (encrypt your requests)

7. **Reformat PEM files if needed** — see Pitfall 3 in the main README.

## Shared Secret decryption

The X-Pay Token Shared Secret is RSA/OAEP-SHA256 encrypted with your own public key. To decrypt it:

```bash
echo "<encrypted_secret_b64>" | base64 -D -i - -o secret_enc.bin
openssl pkeyutl -decrypt \
  -inkey xpay_private.pem \
  -in secret_enc.bin \
  -pkeyopt rsa_padding_mode:oaep \
  -pkeyopt rsa_oaep_md:sha256 \
  -pkeyopt rsa_mgf1_md:sha256 \
  -out shared_secret.txt
```

Visa says "RSA/ECB/OAEPWithSHA-256AndMGF1Padding" — Java-standard would mean MGF1 defaults to SHA-1, but Visa uses MGF1 with SHA-256 (as above). Classic ambiguity.

## Sanity check: hello world

```bash
curl "https://sandbox.api.visa.com/vdp/helloworld" \
  --cert cert.pem --key key.pem --cacert ca-cert.pem \
  -u "YOUR_USER_ID:YOUR_PASSWORD"
```

Expected: `{"timestamp":"2026-...","message":"helloworld"}`. If this works, mTLS + Basic Auth are good. Real endpoints still need MLE.
