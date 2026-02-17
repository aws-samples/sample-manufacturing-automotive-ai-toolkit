"""Cognito JWT Authentication for Fleet Discovery API."""
import os
import logging
import json
from urllib.request import urlopen
from typing import Optional

import jwt
from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")


class CognitoJWTValidator:
    """Validates Cognito JWT ID tokens using RS256 and cached JWKS."""

    def __init__(self, region: str, user_pool_id: str, client_id: Optional[str] = None):
        self.region = region
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        self._jwks: Optional[dict] = None

    def _get_jwks(self) -> dict:
        if self._jwks is None:
            jwks_url = f"{self.issuer}/.well-known/jwks.json"
            with urlopen(jwks_url) as response:
                self._jwks = json.loads(response.read())
        return self._jwks

    def _get_signing_key(self, token: str) -> jwt.algorithms.RSAAlgorithm:
        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid")
        jwks = self._get_jwks()
        for key_data in jwks.get("keys", []):
            if key_data["kid"] == kid:
                return jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
        raise HTTPException(status_code=401, detail="Token signing key not found")

    def validate(self, token: str) -> dict:
        try:
            public_key = self._get_signing_key(token)
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.client_id,
                options={"require": ["exp", "iss", "token_use"]},
            )
            if claims.get("token_use") != "id":
                raise HTTPException(status_code=401, detail="Not an ID token")
            return claims
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT validation failed: {type(e).__name__}")
            raise HTTPException(status_code=401, detail="Authentication failed")


# Singleton validator (created lazily when env vars are set)
_validator: Optional[CognitoJWTValidator] = None


def _get_validator() -> Optional[CognitoJWTValidator]:
    global _validator
    if _validator is None and COGNITO_USER_POOL_ID:
        _validator = CognitoJWTValidator(
            region=AWS_REGION,
            user_pool_id=COGNITO_USER_POOL_ID,
            client_id=COGNITO_CLIENT_ID,
        )
    return _validator


async def require_auth(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """FastAPI dependency that validates the Bearer token.

    Graceful degradation: if COGNITO_USER_POOL_ID is not configured,
    authentication is skipped (allows local dev without Cognito).
    """
    validator = _get_validator()
    if validator is None:
        return None

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    return validator.validate(parts[1])
