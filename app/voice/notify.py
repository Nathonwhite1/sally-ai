from __future__ import annotations
import os
from twilio.rest import Client

def send_owner_sms(message: str) -> None:
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_FROM_NUMBER", "")
    to_number = os.getenv("OWNER_MOBILE", "")

    if not (sid and token and from_number and to_number):
        return

    Client(sid, token).messages.create(body=message, from_=from_number, to=to_number)
