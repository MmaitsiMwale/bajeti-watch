"""
api/routes/whatsapp.py

Twilio WhatsApp webhook receiver.

Flow:
  Twilio sends POST → extract message → run agent → reply via TwiML
"""

from __future__ import annotations

import os
import logging
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse

from agent.graph import run_agent

from api.middleware.twilio_auth import validate_twilio_signature

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/whatsapp",
    response_class=PlainTextResponse,
    dependencies=[Depends(validate_twilio_signature)],
)
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(default=""),
    From: str = Form(default=""),
    ProfileName: str = Form(default=""),
):
    """
    Receives an inbound WhatsApp message from Twilio.
    Runs the agent and returns a TwiML response.

    Twilio expects a TwiML XML response — we use MessagingResponse
    to build it. The <Message> tag tells Twilio what to send back.
    """
    sender  = From or "unknown"
    message = Body.strip()
    name    = ProfileName or "Citizen"

    logger.info(f"[whatsapp] Message from {sender} ({name}): {message!r}")

    if not message:
        reply = "Habari! Send a county name to get its budget summary.\nExample: *Kisumu*"
    else:
        try:
            reply = run_agent(message=message, channel="whatsapp")
        except Exception as e:
            logger.error(f"[whatsapp] Agent error for message {message!r}: {e}")
            reply = (
                "Samahani, nimekutana na tatizo. Tafadhali jaribu tena.\n"
                "(Sorry, something went wrong. Please try again.)"
            )

    # Build TwiML response
    twiml = MessagingResponse()
    twiml.message(reply)

    logger.info(f"[whatsapp] Reply to {sender}: {reply[:80]}...")
    return str(twiml)


@router.get("/whatsapp")
async def whatsapp_verify():
    """
    Simple GET handler — useful to confirm the webhook URL is reachable
    before pointing Twilio at it.
    """
    return {"status": "Bajeti Watch WhatsApp webhook is live"}