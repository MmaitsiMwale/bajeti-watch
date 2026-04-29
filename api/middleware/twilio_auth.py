"""
api/middleware/twilio_auth.py

Validates that incoming webhook requests genuinely come from Twilio.
Twilio signs every request with your auth token — we verify the signature
before passing it to the route handler.

Without this, anyone who discovers your webhook URL could send fake messages.
"""

from __future__ import annotations

import os
from fastapi import Request, HTTPException
from twilio.request_validator import RequestValidator


async def validate_twilio_signature(request: Request) -> None:
    """
    FastAPI dependency — raises 403 if the request is not from Twilio.
    Add as a dependency to any route that receives Twilio webhooks.

    Usage in route:
        @router.post("/whatsapp", dependencies=[Depends(validate_twilio_signature)])
    """
    # Skip validation in local development if explicitly disabled
    if os.environ.get("APP_ENV") == "development" and \
       os.environ.get("SKIP_TWILIO_AUTH") == "true":
        return

    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    validator  = RequestValidator(auth_token)

    # Twilio sends the signature in this header
    signature  = request.headers.get("X-Twilio-Signature", "")

    # The full URL must match exactly what Twilio has configured
    url        = str(request.url)

    # Parse form body — Twilio sends webhook data as form fields
    form_data  = await request.form()
    params     = dict(form_data)

    valid = validator.validate(url, params, signature)

    if not valid:
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")