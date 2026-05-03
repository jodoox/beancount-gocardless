"""JWT signing for Enable Banking API authentication.

Enable Banking uses RS256-signed JWTs for API authentication.
The JWT must contain specific claims and headers as documented at:
https://enablebanking.com/docs/api/
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def build_jwt(
    application_id: str,
    private_key_path: str,
    ttl_seconds: int = 3600,
) -> str:
    """Build a signed JWT for Enable Banking API authentication.

    The JWT contains the required claims and headers:
    - Header: typ=JWT, alg=RS256, kid=<application_id>
    - Payload: iss=enablebanking.com, aud=api.enablebanking.com, iat, exp

    Args:
        application_id: Enable Banking application ID (used as kid).
        private_key_path: Path to the RSA private key file (PEM format).
        ttl_seconds: Token time-to-live in seconds (max 86400 = 24 hours).

    Returns:
        Signed JWT string.

    Raises:
        ValueError: If ttl_seconds exceeds 86400.
        FileNotFoundError: If private_key_path does not exist.
        ModuleNotFoundError: If PyJWT is not installed.
    """
    if ttl_seconds > 86400:
        raise ValueError(
            f"Enable Banking accepts maximum 86400 seconds TTL, got {ttl_seconds}"
        )

    try:
        import jwt
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyJWT is required for Enable Banking authentication. "
            "Install the package with its runtime dependencies."
        ) from exc

    private_key = Path(private_key_path).read_text(encoding="utf-8")
    now = datetime.now(timezone.utc)
    iat = int(now.timestamp())
    exp = int((now + timedelta(seconds=ttl_seconds)).timestamp())

    logger.debug("Building JWT: iat=%d, exp=%d, ttl=%d", iat, exp, ttl_seconds)

    payload = {
        "iss": "enablebanking.com",
        "aud": "api.enablebanking.com",
        "iat": iat,
        "exp": exp,
    }
    headers = {
        "typ": "JWT",
        "alg": "RS256",
        "kid": application_id,
    }

    token = jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
    return token


def build_auth_headers(
    application_id: str,
    private_key_path: str,
) -> dict[str, str]:
    """Build HTTP headers for Enable Banking API requests.

    Args:
        application_id: Enable Banking application ID.
        private_key_path: Path to the RSA private key file.

    Returns:
        Dictionary with Authorization, Accept, and Content-Type headers.
    """
    token = build_jwt(application_id, private_key_path)
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
