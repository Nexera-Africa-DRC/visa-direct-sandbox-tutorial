# The 7 Pitfalls — Deep dive

The main `README.md` summarizes each pitfall in a few lines. This document holds the longer-form versions with full error logs, dates, and context — useful when you want to grep for an exact error string.

> This is a stub. Phase 2 will backfill it with the exact HTTP traces I captured for each pitfall. For now, see the summary section in `README.md`.

## Table of contents

1. CA cert in DER vs PEM — SSLError NO_CERTIFICATE_OR_CRL_FOUND
2. Mismatched cert.pem / key.pem — modulus md5 doesn't match
3. PEM files on a single line — EncryptedPrivateKeyInfo No supported data to decode
4. MLE is mandatory — 9125 "Expected input credential was not present"
5. Use A128GCM, not A256GCM — same 9125 even with MLE enabled
6. HTTP header keyId: is required — 9123/9125 persist until added
7. httpx vs requests mystery — httpx returns 9123, requests returns 200

Each entry will include:
- Exact error (status + response body)
- Minimal reproduction (curl / Python)
- Root cause analysis
- Fix with code snippet
- How I discovered it (where applicable)

If you want to contribute an entry while this is being backfilled, PRs welcome.
