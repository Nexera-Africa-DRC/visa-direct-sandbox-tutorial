"""Visa Message Level Encryption (MLE) — Python helper.

Visa Direct and Visa Accept endpoints require JWE-wrapped payloads using
RSA-OAEP-256 (key wrap) + A128GCM (payload encryption). This module provides
`encrypt(payload, server_cert_path, key_id)` and `decrypt(enc_data, private_key_path)`.

The format matches the official vdpplayground.jar output byte-for-byte
(confirmed by decompiling with CFR 0.152).

Why A128GCM and not A256GCM? Because the Visa SDK uses A128GCM — see
EncryptionUtils.java in the decompiled playground:

    new JWEHeader.Builder(JWEAlgorithm.RSA_OAEP_256, EncryptionMethod.A128GCM)
        .keyID(this.keyID)
        .customParam("iat", System.currentTimeMillis())
"""

from __future__ import annotations

import json
import time
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from jwcrypto import jwe, jwk


def _load_server_public_key(server_cert_path: str) -> jwk.JWK:
    """Load Visa server public key from the X.509 certificate they provide."""
    with open(server_cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    pub_pem = cert.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return jwk.JWK.from_pem(pub_pem)


def _load_client_private_key(private_key_path: str) -> jwk.JWK:
    """Load our private key for decrypting Visa responses."""
    with open(private_key_path, "rb") as f:
        return jwk.JWK.from_pem(f.read())


def encrypt(payload: dict, server_cert_path: str, key_id: str) -> str:
    """Encrypt a payload dict into a JWE compact string.

    Matches the format produced by vdpplayground.jar:
    - alg: RSA-OAEP-256
    - enc: A128GCM (NOT A256GCM — Visa SDK uses 128)
    - kid: the MLE Key ID from your Visa Developer dashboard
    - iat: milliseconds since epoch (Java's System.currentTimeMillis())
    """
    protected = {
        "alg": "RSA-OAEP-256",
        "enc": "A128GCM",
        "kid": key_id,
        "iat": int(time.time() * 1000),
    }
    token = jwe.JWE(
        plaintext=json.dumps(payload).encode("utf-8"),
        protected=json.dumps(protected),
        recipient=_load_server_public_key(server_cert_path),
    )
    return token.serialize(compact=True)


def decrypt(enc_data: str, private_key_path: str) -> dict:
    """Decrypt a JWE compact string received from Visa."""
    token = jwe.JWE()
    token.deserialize(enc_data, key=_load_client_private_key(private_key_path))
    return json.loads(token.payload.decode("utf-8"))


def wrap_request_body(payload: dict, server_cert_path: str, key_id: str) -> str:
    """Produce the exact JSON string Visa expects: {"encData":"..."}

    IMPORTANT: no space after `:`. Visa accepts both forms, but staying close
    to vdpplayground.jar's raw string concatenation avoids subtle issues.
    """
    enc = encrypt(payload, server_cert_path, key_id)
    return '{"encData":"' + enc + '"}'


def unwrap_response_body(raw_json: Any, private_key_path: str) -> dict:
    """Decrypt the response if it's wrapped in {"encData": "..."}.

    Error responses ({"responseStatus": {...}}) are returned in clear text;
    only successful responses are MLE-encrypted.
    """
    if isinstance(raw_json, dict) and "encData" in raw_json:
        return decrypt(raw_json["encData"], private_key_path)
    return raw_json
