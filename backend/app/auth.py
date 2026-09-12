"""Verify account identity; never accept user-supplied ownership claims."""
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import HTTPException


@lru_cache(maxsize=4)
def signing_keys(url: str):
    return jwt.PyJWKClient(
        url + "/auth/v1/.well-known/jwks.json", lifespan=300, timeout=5,
    )


def supabase_identity(token: str, url: str) -> str:
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") not in {"ES256", "RS256"}:
            raise ValueError("Unsupported signing algorithm")
        key = signing_keys(url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, key.key, algorithms=["ES256", "RS256"],
            audience="authenticated", issuer=url + "/auth/v1",
            options={"require": ["exp", "sub", "iss", "aud", "iat", "role"]},
        )
        if claims["role"] != "authenticated" or claims.get("is_anonymous") is True:
            raise ValueError("An account is required")
        return str(UUID(claims["sub"]))
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(503, "Account verification is temporarily unavailable") from None
    except (jwt.PyJWTError, ValueError, TypeError, AttributeError):
        raise HTTPException(401, "Please sign in again") from None
