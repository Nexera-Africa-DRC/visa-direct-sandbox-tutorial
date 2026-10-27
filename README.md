# Visa Direct Sandbox in Python — 7 Pitfalls Visa Doesn't Document

A working **Visa Direct Push Funds Transfer** example in Python, with the 7 undocumented pitfalls that waste 6+ hours of a first-time integrator's life.

> 🇫🇷 Français : [`README.fr.md`](README.fr.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

---

**Author:** Henock BARAKAEL — [Nexera Africa DRC](https://nexera.africa)  
**License:** MIT  
**Status:** Validated against Visa sandbox on 2026-10-27 — Push Funds Transfer returns `actionCode: 00` (APPROVED).

---

## Who is this for?

You're a backend engineer trying to integrate Visa Direct, Visa Accept, or anything on the Visa Developer Platform (VDP), and you've hit `HTTP 400 code 9125 "Expected input credential was not present"` while all your credentials look correct. The official docs are partial, Stack Overflow is a desert, and you're starting to doubt your own sanity.

This repo captures what I had to discover the hard way — including some findings only visible by decompiling the official `vdpplayground.jar`.

## What's in the box

- **Working Python code** (`src/visa_mle.py` + `src/push_funds.py`) that performs a Push Funds Transfer and returns `actionCode: 00` against Visa sandbox.
- **The 7 pitfalls** that waste the most time, each with symptom + root cause + fix.
- **A guide to decompile the Visa SDK** (`vdpplayground.jar`) when the public docs stop helping — a technique that saved my project.
- **A ready-to-fill `.env.example`** with every single credential explained.

## Quick start

```bash
# 1. Clone
git clone https://github.com/Nexera-Africa-DRC/visa-direct-sandbox-tutorial.git
cd visa-direct-sandbox-tutorial

# 2. Install
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Follow the setup guide (first time only)
#    docs/01-setup-visa-developer-account.md — 20 min walkthrough

# 4. Copy your creds + certs to the right paths
cp .env.example .env
mkdir -p certs/mle
# ... then fill .env and drop your PEM files in certs/

# 5. Run
python -m src.push_funds
```

Expected output:

```
HTTP 200
{
  "transactionIdentifier": 381228649430015,
  "actionCode": "00",
  "approvalCode": "21324K",
  "responseCode": "5",
  "transmissionDateTime": "2026-10-27T08:24:23.000Z"
}

✅ APPROVED — approvalCode = 21324K
```

---

## The 7 pitfalls

Each pitfall below includes the **symptom** you'll see, the **root cause**, and the **one-line fix**. They're ordered the way they'll hit you.

### Pitfall 1 — `ca-cert.pem` is in DER format, not PEM

**Symptom:** `SSLError: NO_CERTIFICATE_OR_CRL_FOUND` when the Python TLS client tries to validate Visa's server certificate.

**Why:** Visa's dashboard sometimes serves the CA bundle as a binary DER file but names it `.pem`. Python's `ssl` module needs text PEM (`-----BEGIN CERTIFICATE-----` headers).

**Fix (option A — convert):**
```bash
openssl x509 -in ca-cert.pem -inform DER -out ca-cert.pem -outform PEM
```

**Fix (option B — use certifi, recommended):** The DigiCert-only root cert Visa provides isn't actually enough to validate the full chain of `sandbox.api.visa.com`. Use the Mozilla CA bundle shipped with Python's `certifi`:
```bash
cp "$(python -c 'import certifi; print(certifi.where())')" certs/ca-cert.pem
```

### Pitfall 2 — `cert.pem` and `key.pem` are a mismatched pair

**Symptom:** `SSLError: KEY_VALUES_MISMATCH`, or more cryptically, the TLS handshake succeeds (because the cert alone is valid) but Visa returns `9125 "credential not present"` because they do a second cert-matches-user check at the app layer.

**Why:** When you rotate your mTLS credentials on the dashboard, Visa gives you *both* a new `cert.pem` **and** a new `key.pem` in two separate downloads. If you only replace one, the pair is dead.

**Fix — verify the modulus matches:**
```bash
openssl x509 -in cert.pem -noout -modulus | openssl md5
openssl rsa  -in key.pem  -noout -modulus | openssl md5
# → the two outputs must be identical
```

### Pitfall 3 — PEM files that come on a single line

**Symptom:** `openssl` complains with `EncryptedPrivateKeyInfo: No supported data to decode`, even though the file isn't actually encrypted.

**Why:** Visa's dashboard sometimes serves the key as a single line (no newlines between `-----BEGIN RSA PRIVATE KEY-----`, the body, and `-----END RSA PRIVATE KEY-----`). PEM spec says the body should wrap at 64 characters.

**Fix:**
```bash
# Reformat with proper line breaks
BODY=$(cat key.pem | sed 's|-----BEGIN RSA PRIVATE KEY-----||; s|-----END RSA PRIVATE KEY-----||' | tr -d '\n\r ')
{
  echo "-----BEGIN RSA PRIVATE KEY-----"
  echo "$BODY" | fold -w 64
  echo "-----END RSA PRIVATE KEY-----"
} > key_fixed.pem
mv key_fixed.pem key.pem
```

### Pitfall 4 — MLE is **mandatory**, not optional

**Symptom:** You've set up mTLS correctly, you can call `GET /vdp/helloworld` and get `200 OK` with Basic Auth, but every real endpoint (`/visadirect/fundstransfer/v1/pushfundstransactions`, etc.) returns `HTTP 400 code 9125 "Expected input credential was not present"`.

**Why:** Visa's error message says "credential" but what's actually missing is the **MLE-encrypted payload**. All Visa Direct and Visa Accept business endpoints require Message Level Encryption. The docs mention MLE in passing but don't make it clear it's not optional.

**Fix:** Generate an MLE Key ID on the dashboard (Credentials → Message Level Encryption → "Generate key ID"), download the 3 PEM files (`mle_private.pem`, `mle_client_cert.pem`, `mle_server_cert.pem`), and wrap every request body as a JWE. See `src/visa_mle.py` for a drop-in helper.

### Pitfall 5 — Use `A128GCM`, not `A256GCM`

**Symptom:** You've implemented MLE correctly, your JWE is valid, but Visa still returns `9123/9125`. You start questioning the universe.

**Why:** Every JWE library's default encryption method is `A256GCM`, which is a stronger algorithm, so you naturally pick that. But the Visa SDK uses `A128GCM`. There's no public doc that says this.

**How I found it:** Decompiled `vdpplayground.jar` with CFR. The exact line in `com.visa.vdp.main.utils.EncryptionUtils` is:

```java
new JWEHeader.Builder(JWEAlgorithm.RSA_OAEP_256, EncryptionMethod.A128GCM)
    .keyID(this.keyID)
    .customParam("iat", System.currentTimeMillis())   // ← milliseconds, not seconds
```

**Fix:** In Python with `jwcrypto`:
```python
protected = {
    "alg": "RSA-OAEP-256",
    "enc": "A128GCM",        # NOT A256GCM
    "kid": mle_key_id,
    "iat": int(time.time() * 1000),  # milliseconds (System.currentTimeMillis)
}
```

### Pitfall 6 — The HTTP `keyId:` header is required (and undocumented)

**Symptom:** You've implemented MLE with `A128GCM`, your JWE is byte-identical to what the playground produces, but Visa still returns `9123 "credential not present"`.

**Why:** When MLE is used, Visa expects an HTTP header `keyId: <your MLE Key ID>` **in addition to** the JWE containing the same `kid` claim. The header is nowhere in the public endpoint docs — but it's there in the decompiled playground:

```java
if (isMLE) {
    request.setHeader("keyId", keyId);
    ...
}
```

**Fix:**
```python
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "keyId": mle_key_id,   # ← the one Visa doesn't tell you about
}
```

### Pitfall 7 — `httpx` 0.28 fails where `requests` succeeds

**Symptom:** Your code is 100% correct — Basic Auth, MLE, headers all right — but `httpx` returns `9123`. You switch to `requests` with the exact same payload: `HTTP 200`.

**Why:** Unclear. Likely a combination of HTTP header ordering, chunked encoding, `Connection: keep-alive` behavior, or something subtle Visa's gateway doesn't like. I spent an hour comparing `httpx.Request.headers.raw` vs curl's `-H` and couldn't nail it down.

**Fix (pragmatic):** Use `requests`. If you need async behavior, wrap it in `asyncio.to_thread`:

```python
import asyncio, requests

response = await asyncio.to_thread(
    requests.post, url, data=body, cert=(cert_path, key_path),
    verify=ca_cert_path, auth=(user, pwd), headers=headers, timeout=30.0,
)
```

If someone cracks the `httpx` mystery, please open a PR — I'd love to use `httpx` natively for the async benefit.

---

## Deep dive sections

More detail in `docs/`:

- [`docs/01-setup-visa-developer-account.md`](docs/01-setup-visa-developer-account.md) — step-by-step Visa Developer onboarding (project, products, API Registration, credentials, MLE Key ID)
- [`docs/02-the-7-pitfalls.md`](docs/02-the-7-pitfalls.md) — longer-form writeup of each pitfall with full error logs
- [`docs/03-decompiling-playground.md`](docs/03-decompiling-playground.md) — how to decompile `vdpplayground.jar` with CFR and read the Visa SDK's actual code — a debugging superpower when their public docs stop helping

---

## FAQ

**Q: Can I use this in production?**  
Not as-is. This is a sandbox tutorial. For production you'll need Visa approval, real BINs, and a reviewed security posture. But the integration patterns here apply unchanged.

**Q: What about `httpx` async? I need true async.**  
See Pitfall 7. The pragmatic workaround is `asyncio.to_thread(requests.post, …)`. If you figure out the httpx mystery, open a PR.

**Q: Does this cover Pull Funds (AFT), mVisa, Query, etc.?**  
Push Funds is covered; the others follow the exact same wrapper pattern. Replace the endpoint path and payload fields. I'll add examples for AFT and mVisa in a follow-up.

**Q: Is `Basic Auth` really preferred over `x-pay-token` for Visa Direct?**  
Yes, per the official `vdpplayground.jar` `doMutualAuthRequest` method. `x-pay-token` is useful for lighter endpoints (hello world variants, Query); `Basic Auth` + mTLS + MLE is the Push Funds trifecta.

**Q: Why Python? Will there be a Node/Java/Go version?**  
Python is what my team at Nexera uses — but the pitfalls (A128GCM, `keyId` header, request library quirks) apply to any language. PRs for ports welcome.

---

## About Nexera

[Nexera](https://nexera.africa) is a vertical SaaS for African merchants (RDC-first). Visa Direct is part of our remittance pipeline for the diaspora, which is why I had to figure all this out. If you're building something adjacent in African fintech, I'd love to hear from you.

- Website: [nexera.africa](https://nexera.africa)
- Author on LinkedIn: [Henock BARAKAEL](https://www.linkedin.com/in/henockbarakael/)
- Issues & PRs: [GitHub Issues](https://github.com/Nexera-Africa-DRC/visa-direct-sandbox-tutorial/issues)

> *Nexera · Fais-le tourner.*

---

## Contributing

Pull requests welcome, especially:
- Node.js / Java / Go ports of the Python code
- A working `httpx` solution (Pitfall 7)
- Additional endpoints (AFT pull funds, mVisa, Query API)
- Terraform / CDK for sandbox project provisioning

See `CONTRIBUTING.md` (TODO) for guidelines.
