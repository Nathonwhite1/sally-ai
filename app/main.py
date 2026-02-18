import os
import re
import requests

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# -------------------------
# Config
# -------------------------
GHL_WEBHOOK_URL = (os.getenv("GHL_WEBHOOK_URL") or "").strip()

# Serve /static/* from app/static
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


# -------------------------
# Debug helpers
# -------------------------
@app.get("/__routes", response_class=JSONResponse)
async def __routes():
    return {"routes": sorted([getattr(r, "path", "") for r in app.routes])}


@app.get("/__debug_env", response_class=JSONResponse)
async def __debug_env():
    v = (os.getenv("GHL_WEBHOOK_URL") or "").strip()
    return {
        "has_GHL_WEBHOOK_URL": bool(v),
        "GHL_WEBHOOK_URL_preview": (v[:80] + "...") if len(v) > 80 else v,
    }


def normalize_phone(phone: str) -> str:
    """
    Normalize US numbers to E.164:
      (707) 350-1569 -> +17073501569
      17073501569    -> +17073501569
    """
    s = (phone or "").strip()
    digits = re.sub(r"\D+", "", s)

    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    if s.startswith("+") and len(digits) >= 10:
        return "+" + digits
    return ""


def fallback_email_from_phone(phone_e164: str) -> str:
    """
    HighLevel contact create/update sometimes behaves better if email exists.
    This creates a harmless placeholder email if none provided.
    """
    digits = re.sub(r"\D+", "", phone_e164 or "")
    if not digits:
        return ""
    return f"lead-{digits}@whitespaintingandrenovations.invalid"


# -------------------------
# Pages
# -------------------------
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    return templates.TemplateResponse("privacy-policy.html", {"request": request})


@app.get("/privacy-policy.html", response_class=HTMLResponse)
async def privacy_policy_html(request: Request):
    return templates.TemplateResponse("privacy-policy.html", {"request": request})


@app.get("/terms-and-conditions", response_class=HTMLResponse)
async def terms_and_conditions(request: Request):
    return templates.TemplateResponse("terms-and-conditions.html", {"request": request})


@app.get("/terms-and-conditions.html", response_class=HTMLResponse)
async def terms_and_conditions_html(request: Request):
    return templates.TemplateResponse("terms-and-conditions.html", {"request": request})


# -------------------------
# WEB LEAD SUBMISSION -> HIGHLEVEL INBOUND WEBHOOK
# -------------------------
@app.post("/web/lead", response_class=JSONResponse)
async def web_lead(payload: dict):
    ghl_url = (os.getenv("GHL_WEBHOOK_URL") or "").strip()
    if not ghl_url:
        raise HTTPException(status_code=500, detail="GHL_WEBHOOK_URL is not set in Render env vars.")

    first_name = (payload.get("first_name") or "").strip()
    raw_phone = (payload.get("phone") or "").strip()
    phone = normalize_phone(raw_phone)

    raw_email = (payload.get("email") or "").strip()
    email = raw_email if raw_email else fallback_email_from_phone(phone)

    project_type = (payload.get("project_type") or "").strip()
    address = (payload.get("address") or "").strip()
    city = (payload.get("city") or "").strip()
    notes = (payload.get("notes") or "").strip()
    sms_consent = bool(payload.get("sms_consent"))

    # Required fields (match what you enforce on the front-end)
    if not phone or not project_type or not address or not city:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: phone, project_type, address, city",
        )

    webhook_payload = {
        "source": "website",
        "first_name": first_name,
        "phone": phone,          # E.164 for consistency
        "email": email,          # placeholder if empty
        "project_type": project_type,
        "address": address,
        "city": city,
        "notes": notes,
        "sms_consent": sms_consent,
    }

    try:
        r = requests.post(ghl_url, json=webhook_payload, timeout=20)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Forwarding failed: {type(e).__name__}: {e}")

    if not (200 <= r.status_code < 300):
        raise HTTPException(status_code=502, detail=f"HighLevel returned {r.status_code}: {r.text[:500]}")

    return JSONResponse({"ok": True, "forward_status": r.status_code})


# -------------------------
# SMS WEBHOOK (Twilio)
# -------------------------
@app.post("/sms", response_class=PlainTextResponse)
async def sms_webhook(
    From: str = Form(None),
    Body: str = Form(""),
):
    reply = (
        "Hi! I’m Sally 👋 Thanks for texting. "
        "What city are you in and is this interior, exterior, or cabinets?"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{reply}</Message></Response>"
    )


# -------------------------
# VOICE ROUTES
# -------------------------
from app.voice.routes import router as voice_router
app.include_router(voice_router, prefix="/voice")
