from fastapi import Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app import config


def current_user(authorization: str = Header(default="")) -> str:
    """Accept only a Google ID token belonging to the allowed account."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    try:
        claims = id_token.verify_oauth2_token(
            authorization[len("Bearer "):], google_requests.Request(), config.GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(401, "invalid token")
    if claims.get("email") != config.ALLOWED_EMAIL or not claims.get("email_verified"):
        raise HTTPException(403, "account not allowed")
    return claims["email"]
