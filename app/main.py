import os
import re
import requests

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# =========================
# CONFIG
# =========================
GHL_WEBHOOK_URL = (os.getenv("GHL_WEBHOOK_URL") or "").strip()


def _digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")


def normalize_phone(phone: str) -> str:
    p = (phone or "").strip()
    if p.startswith("+"):
        return p
    d = _digits(p)
    if len(d) == 10:
        return "+1" + d
    if len(d) == 11 and d.startswith("1"):
        return "+" + d
    return p  # fallback


def fallback_email_from_phone(phone: str) -> str:
    d = _digits(phone)
    if not d:
        return "lead@whitespaintingandrenovations.invalid"
    return f"lead-{d}@whitespaintingandrenovations.invalid"


# =========================
# DEBUG
# =========================
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


# =========================
# STATIC + TEMPLATES
# =========================
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# =========================
# PAGES
# =========================
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


# =========================
# WEB LEAD SUBMISSION -> HIGHLEVEL INBOUND WEBHOOK
# =========================
@app.post("/web/lead")
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

    if not phone or not project_type or not address or not city:
        raise HTTPException(status_code=400, detail="Missing required fields: phone, project_type, address, city")

    hl_friendly = {
        "source": "website",
        "first_name": first_name,
        "phone": phone,
        "email": email,
        "project_type": project_type,
        "address": address,
        "city": city,
        "notes": notes,
        "sms_consent": sms_consent,

        # Variants to help HL mapping UI
        "Phone": phone,
        "Email": email,
        "firstName": first_name,
        "address1": address,
        "contact_phone": phone,
        "contact_email": email,
    }

    final_payload = {
        **hl_friendly,
        "data": hl_friendly,
    }

    try:
        r = requests.post(ghl_url, json=final_payload, timeout=20)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Forwarding failed: {type(e).__name__}: {e}")

    if not (200 <= r.status_code < 300):
        raise HTTPException(status_code=502, detail=f"HighLevel returned {r.status_code}: {r.text[:300]}")

    return JSONResponse({"ok": True, "forward_status": r.status_code})


# =========================
# SMS WEBHOOK (Twilio)
# =========================
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


# =========================
# VOICE ROUTES
# =========================
from app.voice.routes import router as voice_router  # noqa: E402
app.include_router(voice_router, prefix="/voice")
