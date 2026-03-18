"""
Lambda Authorizer — fn-authorizer  (zero external dependencies)

HTTP API v2.0 REQUEST authorizer with simple responses.
Validates a Cognito-issued JWT (id_token or access_token) carried in the
``Authorization: Bearer <token>`` header.

Algorithm: RS256 (RSASSA-PKCS1-v1_5 with SHA-256).
Signature verification is implemented using only Python stdlib:
  urllib.request  — JWKS fetch
  base64          — base64url decode
  hashlib         — SHA-256
  json            — decode JWKS / claims
  math            — integer modular exponentiation (pow built-in)

JWKS is fetched once per cold start and cached at module level.

Simple response shape (payloadFormatVersion 2.0):
  { "isAuthorized": true,  "context": { "sub": "...", "email": "...", "groups": "[]" } }
  { "isAuthorized": false }
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from typing import Any
from urllib.request import urlopen

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Env vars (injected by CDK) ────────────────────────────────────────────────
_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]   # e.g. us-east-1_XXXXXXXXX
_CLIENT_ID = os.environ["COGNITO_CLIENT_ID"]
_REGION = (
    os.environ.get("AWS_REGION_NAME")
    or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
)
_ISSUER = f"https://cognito-idp.{_REGION}.amazonaws.com/{_POOL_ID}"
_JWKS_URL = f"{_ISSUER}/.well-known/jwks.json"

# ── JWKS cold-start cache: { kid -> {"n": int, "e": int} } ───────────────────
_JWKS_CACHE: dict[str, dict] | None = None

# PKCS#1 v1.5 SHA-256 DigestInfo prefix (RFC 3447 §9.2, Note 1)
_SHA256_DIGEST_INFO = bytes([
    0x30, 0x31, 0x30, 0x0d, 0x06, 0x09,
    0x60, 0x86, 0x48, 0x01, 0x65, 0x03, 0x04, 0x02, 0x01,
    0x05, 0x00, 0x04, 0x20,
])


# ── Entry point ───────────────────────────────────────────────────────────────

def handler(event: dict, _context: Any) -> dict:
    token = _extract_token(event)
    if not token:
        logger.warning("No Bearer token in request")
        return {"isAuthorized": False}

    try:
        claims = _decode_and_verify(token)
    except _AuthError as exc:
        logger.warning("JWT rejected: %s", exc)
        return {"isAuthorized": False}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected authorizer error: %s", exc)
        return {"isAuthorized": False}

    context = {
        "sub": claims.get("sub", ""),
        "email": claims.get("email", ""),
        "groups": json.dumps(claims.get("cognito:groups", [])),
    }
    logger.info("Authorized sub=%s", context["sub"])
    return {"isAuthorized": True, "context": context}


# ── Token extraction ──────────────────────────────────────────────────────────

def _extract_token(event: dict) -> str | None:
    """HTTP API v2.0 lowercases header names."""
    headers: dict = event.get("headers") or {}
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


# ── JWT decode + verify ───────────────────────────────────────────────────────

def _decode_and_verify(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise _AuthError("Malformed JWT: expected 3 dot-separated parts")

    header_b64, payload_b64, sig_b64 = parts

    header: dict = json.loads(_b64url_decode(header_b64))
    if header.get("alg") != "RS256":
        raise _AuthError(f"Unsupported algorithm: {header.get('alg')}")

    kid: str = header.get("kid", "")
    if not kid:
        raise _AuthError("Missing 'kid' in JWT header")

    # Verify signature
    jwk = _get_jwk(kid)
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = _b64url_decode(sig_b64)
    _verify_rs256(signing_input, signature, jwk["n"], jwk["e"])

    # Decode claims
    claims: dict = json.loads(_b64url_decode(payload_b64))

    # Validate standard claims
    _validate_claims(claims)
    return claims


def _validate_claims(claims: dict) -> None:
    now = int(time.time())

    # Expiry
    if claims.get("exp", 0) < now:
        raise _AuthError("Token has expired")

    # Not-before (optional)
    nbf = claims.get("nbf")
    if nbf is not None and nbf > now + 5:
        raise _AuthError("Token not yet valid (nbf)")

    # Issuer
    if claims.get("iss") != _ISSUER:
        raise _AuthError(f"Issuer mismatch: {claims.get('iss')!r}")

    # Audience / client_id (support both id_token and access_token)
    aud = claims.get("aud")
    client_id_claim = claims.get("client_id")
    if aud != _CLIENT_ID and client_id_claim != _CLIENT_ID:
        raise _AuthError(
            f"Audience mismatch: aud={aud!r} client_id={client_id_claim!r}"
        )

    # token_use (reject refresh tokens)
    token_use = claims.get("token_use", "id")
    if token_use not in ("id", "access"):
        raise _AuthError(f"Unexpected token_use: {token_use!r}")


# ── JWKS fetch & cache ────────────────────────────────────────────────────────

def _get_jwk(kid: str) -> dict:
    """Return cached RSA key params {n: int, e: int} for the given kid."""
    global _JWKS_CACHE
    if _JWKS_CACHE is None:
        _JWKS_CACHE = _fetch_jwks()
    key = _JWKS_CACHE.get(kid)
    if key is None:
        # Retry once in case keys were rotated
        _JWKS_CACHE = _fetch_jwks()
        key = _JWKS_CACHE.get(kid)
    if key is None:
        raise _AuthError(f"Unknown kid: {kid!r}")
    return key


def _fetch_jwks() -> dict[str, dict]:
    """Fetch JWKS and return {kid: {n: int, e: int}}."""
    with urlopen(_JWKS_URL, timeout=5) as resp:
        data: dict = json.loads(resp.read())
    result: dict[str, dict] = {}
    for jwk in data.get("keys", []):
        if jwk.get("kty") != "RSA" or jwk.get("use") != "sig":
            continue
        kid = jwk.get("kid")
        if not kid:
            continue
        n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
        e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
        result[kid] = {"n": n, "e": e}
    logger.info("Fetched %d RSA keys from JWKS", len(result))
    return result


# ── RSA-SHA256 PKCS#1 v1.5 signature verification ────────────────────────────

def _verify_rs256(message: bytes, signature: bytes, n: int, e: int) -> None:
    """
    Verify an RS256 (RSASSA-PKCS1-v1_5 SHA-256) signature.

    Steps (RFC 3447 §8.2.2):
      1.  em = sig_int ^ e mod n          (RSA verification primitive)
      2.  Strip PKCS#1 v1.5 type-1 padding
      3.  Check DigestInfo prefix matches SHA-256 OID
      4.  Compare embedded digest with SHA-256(message)
    """
    key_bytes = (n.bit_length() + 7) // 8

    if len(signature) != key_bytes:
        raise _AuthError(
            f"Signature length {len(signature)} != key length {key_bytes}"
        )

    # 1. RSA modular exponentiation
    sig_int = int.from_bytes(signature, "big")
    em_int = pow(sig_int, e, n)
    em = em_int.to_bytes(key_bytes, "big")

    # 2. PKCS#1 v1.5 type-1 padding: 0x00 0x01 [0xff…] 0x00 DigestInfo
    if len(em) < 2 or em[0] != 0x00 or em[1] != 0x01:
        raise _AuthError("Invalid PKCS#1 v1.5 padding (no 0x00 0x01 prefix)")

    # Find the 0x00 separator after the 0xFF padding
    sep = em.find(b"\x00", 2)
    if sep == -1:
        raise _AuthError("Invalid PKCS#1 v1.5 padding (no separator byte)")

    ps = em[2:sep]
    if not ps or any(b != 0xFF for b in ps):
        raise _AuthError("Invalid PKCS#1 v1.5 padding (PS bytes not 0xFF)")

    digest_info = em[sep + 1:]

    # 3. Check DigestInfo prefix (SHA-256 OID)
    prefix_len = len(_SHA256_DIGEST_INFO)
    if not digest_info.startswith(_SHA256_DIGEST_INFO):
        raise _AuthError("DigestInfo does not match SHA-256 OID")

    # 4. Compare digests
    embedded_digest = digest_info[prefix_len:]
    expected_digest = hashlib.sha256(message).digest()
    if len(embedded_digest) != 32:
        raise _AuthError(f"Unexpected digest length: {len(embedded_digest)}")
    # Constant-time comparison via XOR
    diff = 0
    for a, b in zip(embedded_digest, expected_digest):
        diff |= a ^ b
    if diff != 0:
        raise _AuthError("Signature digest mismatch")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _b64url_decode(s: str) -> bytes:
    """Base64url decode without padding."""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


class _AuthError(Exception):
    """Raised for any JWT validation failure."""
